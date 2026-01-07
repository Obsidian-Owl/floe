# Component Ownership and Boundaries

## Technology Ownership

Each component **owns** its domain - NEVER cross boundaries:

### dbt: Owns ALL SQL

**dbt owns SQL and SQL dialect translation:**

❌ **NEVER** parse SQL in Python
❌ **NEVER** validate SQL syntax in Python
❌ **NEVER** transform SQL dialects manually
❌ **NEVER** modify dbt-generated SQL
✅ **ALWAYS** let dbt handle all SQL compilation and execution
✅ **ALWAYS** trust dbt for dialect-specific features

```python
# ❌ FORBIDDEN - Parsing SQL in Python
def parse_sql(sql: str) -> dict:
    """DON'T DO THIS - dbt owns SQL parsing."""
    # Never implement SQL parser in Python
    pass

# ✅ CORRECT - Let dbt handle SQL
def compile_dbt_models() -> Path:
    """Let dbt compile SQL - we just invoke it."""
    from dbt.cli.main import dbtRunner
    dbt = dbtRunner()
    dbt.invoke(["compile"])
    return Path("target/manifest.json")
```

### Dagster: Owns Orchestration

**Dagster owns orchestration and asset management:**

- Software-defined assets
- Schedules and sensors
- Run coordination
- Asset dependencies
- Metadata tracking

```python
# ✅ CORRECT - Dagster manages orchestration
from dagster import asset, Definitions

@asset
def customers() -> None:
    """Dagster orchestrates, dbt executes SQL."""
    dbt.invoke(["run", "--select", "customers"])
```

### Iceberg: Owns Storage Format

**Iceberg owns storage format and ACID guarantees:**

- Table format specification
- Snapshot isolation
- Time travel
- Schema evolution
- Partition management

```python
# ✅ CORRECT - Use PyIceberg for Iceberg operations
from pyiceberg.catalog import load_catalog

catalog = load_catalog("default")
table = catalog.load_table("my_namespace.my_table")
# PyIceberg handles all Iceberg-specific logic
```

### Polaris: Owns Catalog Management

**Polaris owns catalog and metadata:**

- Catalog organization
- Namespace hierarchy
- Access control
- Metadata storage

```python
# ✅ CORRECT - Polaris manages catalog
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    "polaris",
    type="rest",
    uri="https://polaris.example.com/api/catalog"
)
```

### Cube: Owns Semantic Layer

**Cube owns semantic layer and consumption APIs:**

- Metrics definitions
- Dimension modeling
- Pre-aggregations
- REST/GraphQL/SQL APIs

```yaml
# ✅ CORRECT - Cube defines semantic layer
cubes:
  - name: orders
    sql: SELECT * FROM {{ dbt.ref('orders') }}
    measures:
      - name: count
        type: count
    dimensions:
      - name: status
        sql: status
        type: string
```

### OpenTelemetry/OpenLineage: Own Observability

**OTel/OpenLineage own observability and lineage:**

- Trace collection
- Span management
- Lineage graphs
- Metadata extraction

## Package Boundaries

Seven focused packages with clear responsibilities:

```
floe-cli (entry point)
  ├─► floe-core (schemas, validation, compilation)
  ├─► floe-dagster (orchestration, assets)
  ├─► floe-dbt (SQL transformations)
  │    ├─► floe-iceberg (storage)
  │    └─► floe-polaris (catalog)
  └─► floe-cube (consumption APIs)
```

### floe-core: Schemas and Compilation

**Responsibilities:**
- FloeSpec schema (Pydantic)
- CompiledArtifacts schema (Pydantic)
- Compiler: FloeSpec → CompiledArtifacts
- JSON Schema export
- Validation logic

**NEVER:**
- ❌ Execute dbt commands
- ❌ Create Dagster assets
- ❌ Manage Iceberg tables
- ❌ Define semantic layer

### floe-dagster: Orchestration

**Responsibilities:**
- Load CompiledArtifacts
- Create Dagster assets from dbt models
- Define schedules and sensors
- Emit OpenTelemetry traces
- Emit OpenLineage events

**NEVER:**
- ❌ Parse floe.yaml directly
- ❌ Execute SQL
- ❌ Manage Iceberg tables directly

### floe-dbt: SQL Transformations

**Responsibilities:**
- dbt project structure
- profiles.yml generation
- dbt command execution (via dbtRunner)
- manifest.json parsing

**NEVER:**
- ❌ Parse SQL
- ❌ Validate SQL syntax
- ❌ Transform SQL dialects
- ❌ Create Dagster assets directly

### floe-iceberg: Storage

**Responsibilities:**
- PyIceberg integration
- Custom IOManager for Dagster
- Iceberg table operations
- ACID transaction management

**NEVER:**
- ❌ Define orchestration logic
- ❌ Execute SQL
- ❌ Manage catalog (that's Polaris)

### floe-polaris: Catalog

**Responsibilities:**
- Polaris catalog integration
- Namespace management
- Principal/role management
- Access control

**NEVER:**
- ❌ Execute SQL
- ❌ Manage Iceberg snapshots directly
- ❌ Define orchestration logic

### floe-cube: Consumption

**Responsibilities:**
- Cube integration
- cube_dbt package usage
- Semantic layer definitions
- REST API exposure

**NEVER:**
- ❌ Execute SQL directly
- ❌ Define orchestration
- ❌ Manage storage

## Integration Contracts

### CompiledArtifacts: The Sole Contract

**CompiledArtifacts is the ONLY integration point between components:**

```python
# floe-core compiles
artifacts = compile_floe_spec(spec)
artifacts.to_json_file("target/compiled_artifacts.json")

# floe-dagster loads
artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")
assets = create_assets_from_artifacts(artifacts)
```

**Rules:**
- **NEVER** pass FloeSpec to other packages
- **ALWAYS** use CompiledArtifacts as the contract
- **NEVER** create ad-hoc integration formats
- **ALWAYS** version CompiledArtifacts changes

## Testing Package Boundaries

```python
# ✅ CORRECT - Test packages independently
def test_floe_core_compilation():
    """Test floe-core in isolation."""
    spec = FloeSpec(...)
    artifacts = compile_floe_spec(spec)
    assert artifacts.version == "1.0.0"

def test_floe_dagster_loading():
    """Test floe-dagster with mock CompiledArtifacts."""
    artifacts = CompiledArtifacts(...)
    assets = create_assets(artifacts)
    assert len(assets) > 0
```

**Each package is independently testable:**
- Mock dependencies with CompiledArtifacts
- No cross-package imports in tests
- Integration tests at the boundary only
