# Data Model: Manifest Schema

**Feature**: 001-manifest-schema
**Date**: 2026-01-09
**Derived from**: [spec.md](spec.md)

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PlatformManifest                                   │
│  (Top-level configuration for platform)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  api_version: Literal["floe.dev/v1"]                                        │
│  kind: Literal["Manifest"]                                                  │
│  metadata: ManifestMetadata                                                 │
│  scope: Literal["enterprise", "domain"] | None                              │
│  parent_manifest: str | None  # OCI URI                                     │
│  plugins: PluginsConfig                                                     │
│  governance: GovernanceConfig | None                                        │
│  approved_plugins: dict[str, list[str]] | None  # enterprise only          │
│  approved_products: list[str] | None  # domain only                         │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ contains
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ManifestMetadata                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  name: str                    # alphanumeric + hyphens                      │
│  version: str                 # semver (MAJOR.MINOR.PATCH)                  │
│  owner: str                   # email or team name                          │
│  description: str | None      # human-readable purpose                      │
└─────────────────────────────────────────────────────────────────────────────┘

         │
         │ contains
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PluginsConfig                                      │
│  (Plugin selections for all pluggable components)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  compute: PluginSelection | None                                            │
│  orchestrator: PluginSelection | None                                       │
│  catalog: PluginSelection | None                                            │
│  storage: PluginSelection | None                                            │
│  semantic_layer: PluginSelection | None                                     │
│  ingestion: PluginSelection | None                                          │
│  secrets: PluginSelection | None                                            │
│  observability: PluginSelection | None                                      │
│  identity: PluginSelection | None                                           │
│  dbt: PluginSelection | None                                                │
│  quality: PluginSelection | None                                            │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ contains (per category)
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PluginSelection                                    │
│  (A choice of specific plugin for a platform capability)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  type: str                    # plugin name (e.g., "duckdb", "snowflake")   │
│  config: dict[str, Any] | None  # plugin-specific configuration            │
│  connection_secret_ref: str | None  # reference to K8s Secret              │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ references
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SecretReference                                    │
│  (Placeholder for sensitive values)                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  source: SecretSource         # env, kubernetes, vault, external-secrets   │
│  name: str                    # secret name (lowercase alphanumeric + -)   │
│  key: str | None              # optional key within secret                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           GovernanceConfig                                   │
│  (Security and compliance settings - immutable in inheritance)              │
├─────────────────────────────────────────────────────────────────────────────┤
│  pii_encryption: Literal["required", "optional"] | None                     │
│  audit_logging: Literal["enabled", "disabled"] | None                       │
│  policy_enforcement_level: Literal["off", "warn", "strict"] | None          │
│  data_retention_days: int | None                                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           InheritanceChain                                   │
│  (Resolved lineage of configurations - 3-tier mode only)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  enterprise: PlatformManifest | None                                        │
│  domain: PlatformManifest | None                                            │
│  product: PlatformManifest                                                  │
│  resolved: ResolvedManifest                                                 │
│  field_sources: dict[str, str]  # tracks which level provided each value   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           SecretSource (Enum)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ENV = "env"                  # Environment variable                        │
│  KUBERNETES = "kubernetes"    # Kubernetes Secret                           │
│  VAULT = "vault"              # HashiCorp Vault                             │
│  EXTERNAL_SECRETS = "external-secrets"  # External Secrets Operator         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           MergeStrategy (Enum)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  OVERRIDE = "override"        # Child completely replaces parent            │
│  EXTEND = "extend"            # Child adds to parent                        │
│  FORBID = "forbid"            # Parent immutable, child inherits only       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Entity Details

### PlatformManifest

The root configuration entity representing an organization's platform settings.

| Field | Type | Required | Constraints | Merge Strategy |
|-------|------|----------|-------------|----------------|
| api_version | Literal["floe.dev/v1"] | Yes | Fixed value | OVERRIDE |
| kind | Literal["Manifest"] | Yes | Fixed value | OVERRIDE |
| metadata | ManifestMetadata | Yes | See ManifestMetadata | OVERRIDE |
| scope | Literal["enterprise", "domain"] \| None | No | None=2-tier, enterprise/domain=3-tier | N/A |
| parent_manifest | str \| None | No | OCI URI format; required if scope=domain | N/A |
| plugins | PluginsConfig | Yes | At least one plugin selected | OVERRIDE |
| governance | GovernanceConfig \| None | No | See GovernanceConfig | FORBID |
| approved_plugins | dict[str, list[str]] \| None | No | Only for scope=enterprise | FORBID |
| approved_products | list[str] \| None | No | Only for scope=domain | FORBID |

**Validation Rules**:
- If `scope="enterprise"`: `parent_manifest` MUST be None
- If `scope="domain"`: `parent_manifest` MUST be set (OCI URI)
- If `scope=None`: `parent_manifest` MUST be None (2-tier mode)
- `approved_plugins` only valid for `scope="enterprise"`
- `approved_products` only valid for `scope="domain"`

---

### ManifestMetadata

Metadata for tracking manifest versions and ownership.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| name | str | Yes | `^[a-z0-9][a-z0-9-]*[a-z0-9]$`, 3-63 chars |
| version | str | Yes | semver format `^\d+\.\d+\.\d+$` |
| owner | str | Yes | email format or team name |
| description | str \| None | No | Max 500 characters |

---

### PluginsConfig

Configuration for all pluggable platform components.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| compute | PluginSelection \| None | No | Must be registered plugin |
| orchestrator | PluginSelection \| None | No | Must be registered plugin |
| catalog | PluginSelection \| None | No | Must be registered plugin |
| storage | PluginSelection \| None | No | Must be registered plugin |
| semantic_layer | PluginSelection \| None | No | Must be registered plugin |
| ingestion | PluginSelection \| None | No | Must be registered plugin |
| secrets | PluginSelection \| None | No | Must be registered plugin |
| observability | PluginSelection \| None | No | Must be registered plugin |
| identity | PluginSelection \| None | No | Must be registered plugin |
| dbt | PluginSelection \| None | No | Must be registered plugin |
| quality | PluginSelection \| None | No | Must be registered plugin |

**Plugin Categories** (11 total per Constitution Principle II):
1. compute (DuckDB, Snowflake, Spark, BigQuery, Databricks)
2. orchestrator (Dagster, Airflow 3.x, Prefect)
3. catalog (Polaris, AWS Glue, Hive)
4. storage (S3, GCS, Azure Blob, MinIO)
5. semantic_layer (Cube, dbt Semantic Layer)
6. ingestion (dlt, Airbyte)
7. secrets (K8s Secrets, ESO, Vault)
8. observability (Jaeger, Datadog, Grafana Cloud)
9. identity (K8s RBAC, custom)
10. dbt (local, fusion)
11. quality (Great Expectations, Soda, dbt Expectations)

---

### PluginSelection

A choice of specific plugin for a platform capability.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| type | str | Yes | Must match registered plugin name |
| config | dict[str, Any] \| None | No | Plugin-specific configuration |
| connection_secret_ref | str \| None | No | K8s Secret name for credentials |

**Validation Rules**:
- `type` validated against plugin registry at load time
- `config` schema varies by plugin (validated by plugin itself)

---

### SecretReference

A placeholder for sensitive values that references a secret by name.

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| source | SecretSource | No | Default: KUBERNETES |
| name | str | Yes | `^[a-z0-9-]+$` |
| key | str \| None | No | Key within secret |

---

### GovernanceConfig

Security and compliance settings. Security fields are immutable in inheritance.

| Field | Type | Required | Immutable | Strength Order |
|-------|------|----------|-----------|----------------|
| pii_encryption | Literal["required", "optional"] \| None | No | Yes | required > optional |
| audit_logging | Literal["enabled", "disabled"] \| None | No | Yes | enabled > disabled |
| policy_enforcement_level | Literal["off", "warn", "strict"] \| None | No | Yes | strict > warn > off |
| data_retention_days | int \| None | No | No (can strengthen) | Higher is stricter |

**Immutability Rules**:
- Child manifests can only **strengthen** security policies
- Attempting to weaken raises `SecurityPolicyViolationError`
- Strength comparisons defined per field

---

### InheritanceChain

The resolved lineage of configurations (3-tier mode only).

| Field | Type | Description |
|-------|------|-------------|
| enterprise | PlatformManifest \| None | Enterprise-level manifest (scope=enterprise) |
| domain | PlatformManifest \| None | Domain-level manifest (scope=domain) |
| product | PlatformManifest | Product manifest (scope=None in 2-tier) |
| resolved | ResolvedManifest | Final merged configuration |
| field_sources | dict[str, str] | Tracks which tier provided each field |

---

## State Transitions

### Manifest Loading States

```
┌─────────────┐     parse     ┌─────────────┐    validate    ┌─────────────┐
│    Raw      │──────────────►│   Parsed    │───────────────►│  Validated  │
│   (YAML)    │               │  (dict)     │                │ (Pydantic)  │
└─────────────┘               └─────────────┘                └─────────────┘
                                                                   │
                                                                   │ resolve
                                                                   │ inheritance
                                                                   ▼
                                                            ┌─────────────┐
                                                            │  Resolved   │
                                                            │ (Merged)    │
                                                            └─────────────┘
```

**States**:
1. **Raw**: YAML file content (string)
2. **Parsed**: Python dict from YAML parsing
3. **Validated**: Pydantic model instance (PlatformManifest)
4. **Resolved**: Merged configuration with inheritance applied

**Transitions**:
- `parse`: YAML → dict (PyYAML)
- `validate`: dict → PlatformManifest (Pydantic)
- `resolve_inheritance`: PlatformManifest → ResolvedManifest (custom logic)

---

## Validation Rules Summary

### Schema Validation (Pydantic)

| Rule ID | Field | Validation |
|---------|-------|------------|
| V001 | api_version | Must be "floe.dev/v1" |
| V002 | kind | Must be "Manifest" |
| V003 | metadata.name | Pattern `^[a-z0-9][a-z0-9-]*[a-z0-9]$`, 3-63 chars |
| V004 | metadata.version | Semver pattern `^\d+\.\d+\.\d+$` |
| V005 | parent_manifest | OCI URI pattern `^oci://.*$` if set |
| V006 | plugins.*.type | Must exist in plugin registry |

### Cross-Field Validation

| Rule ID | Fields | Validation |
|---------|--------|------------|
| C001 | scope, parent_manifest | scope=enterprise → parent_manifest=None |
| C002 | scope, parent_manifest | scope=domain → parent_manifest required |
| C003 | scope, parent_manifest | scope=None → parent_manifest=None |
| C004 | scope, approved_plugins | approved_plugins only for scope=enterprise |
| C005 | scope, approved_products | approved_products only for scope=domain |

### Security Policy Validation (Inheritance)

| Rule ID | Policy | Validation |
|---------|--------|------------|
| S001 | pii_encryption | Child cannot weaken (required > optional) |
| S002 | audit_logging | Child cannot weaken (enabled > disabled) |
| S003 | policy_enforcement_level | Child cannot weaken (strict > warn > off) |
| S004 | approved_plugins | Domain plugins must be in enterprise whitelist |
