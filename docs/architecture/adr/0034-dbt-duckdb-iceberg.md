# ADR-0034: dbt-duckdb Iceberg Catalog Integration Workaround

## Status

Accepted

## Context

DuckDB 1.4.0 (LTS, June 2025) includes **full Iceberg REST catalog write support** via the `iceberg` extension. This allows DuckDB to:

- Attach Iceberg catalogs (Polaris, Glue, Hive) via `ATTACH`
- Create and write Iceberg tables directly
- Use credential vending for secure cloud storage access

However, **dbt-duckdb does not expose** Iceberg catalog functionality through its adapter. The adapter only supports:

- Local DuckDB files (`:memory:`, file paths)
- MotherDuck (cloud service)
- External attachments (Postgres, MySQL, SQLite)

This creates a gap between DuckDB's native Iceberg capabilities and what's available through dbt.

### Gap Analysis

| Capability | DuckDB Native | dbt-duckdb |
|------------|---------------|------------|
| Iceberg REST catalog attach | Yes | **No** |
| Create Iceberg tables | Yes | **No** |
| Write to Iceberg tables | Yes | **No** |
| Read Iceberg tables | Yes | Yes (via `external_location`) |
| Credential vending | Yes | **No** |

### Impact on floe

The `floe-compute-duckdb` plugin requires Iceberg catalog writes for:

1. **Bronze/Silver/Gold medallion layers** - dbt models must write Iceberg tables
2. **Catalog registration** - Tables must be visible in Polaris REST catalog
3. **Cross-engine queries** - Spark/Snowflake must read tables written by DuckDB

Without this capability, DuckDB cannot serve as a compute engine for the data lakehouse pattern.

## Decision

Implement a **pre-hook + custom materialization workaround** until dbt-duckdb supports Iceberg catalogs natively.

### Approach

1. **Pre-hook catalog attachment**: Use dbt `on-run-start` hooks to attach Iceberg catalog
2. **Custom materialization**: Create `iceberg_table` materialization for Iceberg writes
3. **Environment configuration**: Pass catalog credentials via environment variables
4. **Validation via SPIKE-02**: Validate approach before EPIC-04 implementation

## Consequences

### Positive

- **Unblocks DuckDB compute** - Enables full lakehouse pattern with DuckDB
- **Leverages DuckDB LTS** - Uses stable 1.4.x Iceberg extension
- **No dbt-duckdb fork** - Works with upstream adapter
- **Future-proof** - Can migrate to native support when available

### Negative

- **Maintenance overhead** - Custom materialization requires ongoing support
- **Testing complexity** - Must test pre-hook execution order
- **Documentation burden** - Non-standard pattern for users
- **Upgrade risk** - Future dbt-duckdb changes may break workaround

### Neutral

- Custom materializations are a documented dbt pattern
- Pre-hooks are stable dbt functionality
- SPIKE-02 validates approach before implementation

---

## Implementation

### SPIKE-02: Validation Required

**Before EPIC-04 implementation**, execute SPIKE-02 to validate:

1. Pre-hook catalog attachment works consistently
2. Custom materialization writes Iceberg metadata correctly
3. Tables are visible in Polaris REST API after dbt run
4. Credential vending works for S3/GCS/Azure storage

**Acceptance Criteria:**
- [ ] dbt model writes to Iceberg table via Polaris
- [ ] Table visible in Polaris REST API
- [ ] Metadata (schema, partitions) correct
- [ ] Document working configuration

---

### Pre-Hook Catalog Attachment

```sql
-- macros/hooks/attach_iceberg_catalog.sql
{% macro attach_iceberg_catalog() %}
    {% if execute %}
        -- Load Iceberg extension
        LOAD iceberg;

        -- Attach Iceberg catalog with credential vending
        ATTACH '{{ env_var("ICEBERG_CATALOG_NAME", "ice") }}' AS ice (
            TYPE ICEBERG,
            ENDPOINT '{{ env_var("POLARIS_ENDPOINT") }}',
            ACCESS_DELEGATION_MODE 'vended_credentials',
            CLIENT_ID '{{ env_var("POLARIS_CLIENT_ID") }}',
            CLIENT_SECRET '{{ env_var("POLARIS_CLIENT_SECRET") }}',
            OAUTH_ENDPOINT '{{ env_var("POLARIS_OAUTH_ENDPOINT", env_var("POLARIS_ENDPOINT") ~ "/v1/oauth/tokens") }}'
        );
    {% endif %}
{% endmacro %}
```

```yaml
# dbt_project.yml
on-run-start:
  - "{{ attach_iceberg_catalog() }}"
```

### Custom Iceberg Materialization

```sql
-- macros/materializations/iceberg_table.sql
{% materialization iceberg_table, adapter='duckdb' %}
    {%- set target_catalog = config.get('catalog', 'ice') -%}
    {%- set target_namespace = config.get('namespace', target.schema) -%}
    {%- set target_table = config.get('alias', this.identifier) -%}
    {%- set full_table_name = target_catalog ~ '.' ~ target_namespace ~ '.' ~ target_table -%}

    {%- set partition_by = config.get('partition_by', none) -%}

    -- Create namespace if not exists
    {% call statement('create_namespace', fetch_result=False) %}
        CREATE SCHEMA IF NOT EXISTS {{ target_catalog }}.{{ target_namespace }};
    {% endcall %}

    -- Build partition clause
    {% if partition_by %}
        {%- set partition_clause = 'PARTITIONED BY (' ~ partition_by ~ ')' -%}
    {% else %}
        {%- set partition_clause = '' -%}
    {% endif %}

    -- Check if table exists
    {% set table_exists_query %}
        SELECT 1 FROM information_schema.tables
        WHERE table_catalog = '{{ target_catalog }}'
          AND table_schema = '{{ target_namespace }}'
          AND table_name = '{{ target_table }}'
    {% endset %}

    {% set table_exists = run_query(table_exists_query).rows | length > 0 %}

    {% if table_exists %}
        -- Table exists: INSERT OR REPLACE (Iceberg merge-on-read)
        {% call statement('main') %}
            INSERT OR REPLACE INTO {{ full_table_name }}
            {{ sql }}
        {% endcall %}
    {% else %}
        -- Table doesn't exist: CREATE TABLE AS
        {% call statement('main') %}
            CREATE TABLE {{ full_table_name }} {{ partition_clause }} AS
            {{ sql }}
        {% endcall %}
    {% endif %}

    {{ return({'relations': [this]}) }}
{% endmaterialization %}
```

### Model Configuration

```sql
-- models/gold/gold_customers.sql
{{
    config(
        materialized='iceberg_table',
        catalog='ice',
        namespace='gold',
        partition_by='MONTH(created_at)'
    )
}}

SELECT
    customer_id,
    customer_name,
    total_orders,
    lifetime_value,
    created_at,
    updated_at
FROM {{ ref('silver_customers') }}
WHERE is_active = true
```

### Environment Configuration

```yaml
# platform-manifest.yaml
plugins:
  compute:
    type: duckdb
    config:
      iceberg:
        catalog_name: ice
        endpoint: "{{ env.POLARIS_ENDPOINT }}"
        oauth_endpoint: "{{ env.POLARIS_OAUTH_ENDPOINT }}"
        client_id_secret: polaris-credentials
        client_secret_secret: polaris-credentials
        access_delegation_mode: vended_credentials
```

```yaml
# K8s ConfigMap for dbt jobs
apiVersion: v1
kind: ConfigMap
metadata:
  name: dbt-duckdb-iceberg-config
  namespace: floe-jobs
data:
  ICEBERG_CATALOG_NAME: "ice"
  POLARIS_ENDPOINT: "http://polaris:8181/api/catalog"
  POLARIS_OAUTH_ENDPOINT: "http://polaris:8181/api/catalog/v1/oauth/tokens"
---
# Secrets injected via Infisical
# POLARIS_CLIENT_ID
# POLARIS_CLIENT_SECRET
```

---

## Alternative Approaches Considered

### 1. Fork dbt-duckdb

**Approach:** Maintain fork with Iceberg catalog support

**Rejected because:**
- High maintenance burden
- Merge conflicts with upstream
- Delays adoption of new features
- Community fragmentation

### 2. External Python script for table registration

**Approach:** Run PyIceberg after dbt to register tables in catalog

**Rejected because:**
- Two-step process increases failure modes
- Metadata may be inconsistent
- Loses atomic commit semantics

### 3. Use dbt-spark for Iceberg writes

**Approach:** Use Spark for all Iceberg table writes

**Rejected because:**
- Loses DuckDB performance benefits
- Increases infrastructure complexity
- Not aligned with "DuckDB-first" compute strategy

### 4. Wait for upstream dbt-duckdb support

**Approach:** Delay until dbt-duckdb adds native Iceberg support

**Rejected because:**
- No timeline from maintainers
- Blocks MVP delivery
- May require significant advocacy work

---

## Iceberg Extension Details

### DuckDB Iceberg Extension (1.4.0+)

```sql
-- Install and load
INSTALL iceberg;
LOAD iceberg;

-- Attach REST catalog (Polaris)
ATTACH 'ice' AS ice (
    TYPE ICEBERG,
    ENDPOINT 'http://polaris:8181/api/catalog',
    ACCESS_DELEGATION_MODE 'vended_credentials',
    CLIENT_ID 'my-client-id',
    CLIENT_SECRET 'my-client-secret'
);

-- Create namespace
CREATE SCHEMA ice.bronze;

-- Create table
CREATE TABLE ice.bronze.events (
    event_id UUID,
    event_type VARCHAR,
    payload JSON,
    created_at TIMESTAMP
) PARTITIONED BY (MONTH(created_at));

-- Insert data
INSERT INTO ice.bronze.events
SELECT * FROM read_parquet('s3://bucket/raw/events/*.parquet');

-- Query
SELECT * FROM ice.bronze.events WHERE created_at > '2025-01-01';
```

### Credential Vending Flow

```
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│      DuckDB       │────►│  Polaris Catalog  │────►│    S3/GCS/Azure   │
│                   │     │                   │     │                   │
│  ATTACH with      │     │  OAuth2 token     │     │  Vended creds     │
│  client creds     │     │  exchange         │     │  for data access  │
└───────────────────┘     └───────────────────┘     └───────────────────┘
        │                         │                         │
        │  1. Authenticate        │                         │
        ├────────────────────────►│                         │
        │                         │                         │
        │  2. Request table loc   │                         │
        ├────────────────────────►│                         │
        │                         │                         │
        │  3. Return location +   │                         │
        │     vended credentials  │                         │
        │◄────────────────────────┤                         │
        │                         │                         │
        │  4. Access data with    │                         │
        │     vended credentials  │                         │
        ├─────────────────────────┼────────────────────────►│
        │                         │                         │
```

---

## Testing Strategy

### Unit Tests

```python
def test_iceberg_table_materialization_creates_table():
    """Test custom materialization creates Iceberg table."""
    # Run dbt with test model
    result = dbt.invoke(["run", "--select", "test_iceberg_model"])
    assert result.success

    # Verify table exists in catalog
    catalog = load_catalog("ice", uri=POLARIS_ENDPOINT)
    table = catalog.load_table("test_namespace.test_iceberg_model")
    assert table is not None


def test_pre_hook_attaches_catalog():
    """Test pre-hook successfully attaches Iceberg catalog."""
    result = dbt.invoke(["run-operation", "attach_iceberg_catalog"])
    assert result.success

    # Verify catalog is attached
    conn = duckdb.connect()
    result = conn.execute("SELECT * FROM duckdb_databases()").fetchall()
    catalog_names = [r[0] for r in result]
    assert "ice" in catalog_names
```

### Integration Tests

```python
def test_full_medallion_pipeline():
    """Test bronze -> silver -> gold pipeline with Iceberg tables."""
    # Run full pipeline
    result = dbt.invoke([
        "run",
        "--select", "bronze_events+",  # Run with downstream
    ])
    assert result.success

    # Verify all tables in catalog
    catalog = load_catalog("ice", uri=POLARIS_ENDPOINT)

    bronze_table = catalog.load_table("bronze.events")
    silver_table = catalog.load_table("silver.events_cleaned")
    gold_table = catalog.load_table("gold.event_summary")

    assert bronze_table is not None
    assert silver_table is not None
    assert gold_table is not None

    # Verify data flows through
    assert bronze_table.current_snapshot() is not None
    assert gold_table.current_snapshot() is not None
```

---

## Rollback Plan

If the workaround proves unstable:

1. **Short-term:** Fall back to Parquet-based dbt models with PyIceberg registration
2. **Medium-term:** Evaluate Spark compute for Iceberg writes
3. **Long-term:** Contribute Iceberg support upstream to dbt-duckdb

---

## Documentation Requirements

1. **User Guide:** Document custom materialization usage and configuration
2. **Troubleshooting:** Common issues with pre-hook execution and catalog attachment
3. **Migration Guide:** How to migrate when native dbt-duckdb support arrives

---

## Timeline and Dependencies

### Dependencies

- **SPIKE-02:** Must complete before EPIC-04 begins
- **ADR-0006:** DuckDB compute decision (already accepted)
- **Polaris deployment:** Catalog must be available for testing

### Estimated Effort

| Task | Story Points |
|------|--------------|
| SPIKE-02 validation | 3 |
| Implement pre-hook macro | 1 |
| Implement custom materialization | 3 |
| Integration tests | 2 |
| Documentation | 1 |
| **Total** | **10** |

---

## References

- [DuckDB Iceberg Extension](https://duckdb.org/docs/extensions/iceberg)
- [DuckDB 1.4.0 Release Notes](https://duckdb.org/2025/06/03/announcing-duckdb-140)
- [dbt Custom Materializations](https://docs.getdbt.com/guides/create-new-materializations)
- [dbt Pre-hooks and Post-hooks](https://docs.getdbt.com/reference/resource-configs/pre-hook-post-hook)
- [Apache Polaris REST Catalog](https://polaris.apache.org/)
- [ADR-0006: OpenTelemetry Observability](0006-opentelemetry-observability.md)
