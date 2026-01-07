# Platform Enforcement Model

This document describes how floe enforces platform constraints on data pipelines.

## Core Principle

**Platform configuration is immutable and versioned. Data engineers inherit guardrails without ability to override.**

```
Platform Team (Define Once)     →     Data Team (Consume & Inherit)
platform-manifest.yaml                 floe.yaml
```

## Two-File Configuration Model

### platform-manifest.yaml (Platform Team)

Defines what is allowed and how it must be done:

```yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-data-platform
  version: "1.2.3"
  scope: enterprise

plugins:
  compute:
    type: duckdb              # Set ONCE
  orchestrator:
    type: dagster
  catalog:
    type: polaris
  semantic_layer:
    type: cube
  ingestion:
    type: dlt

data_architecture:
  pattern: medallion
  naming:
    enforcement: strict       # off | warn | strict

governance:
  quality_gates:
    minimum_test_coverage: 80
    block_on_failure: true
```

### floe.yaml (Data Team)

Defines pipelines within platform constraints:

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-analytics
  version: "1.0"

platform:
  ref: oci://registry.acme.com/floe-platform:v1.2.3

transforms:
  - type: dbt
    path: models/

schedule:
  cron: "0 6 * * *"
```

## Enforcement Points

### 1. Compile-Time Validation

Non-compliant pipelines fail before runtime:

```bash
$ floe compile

[1/5] Loading platform artifacts
      ✓ Platform version: 1.2.3
      ✓ Compute: duckdb (enforced)
      ✓ Architecture: medallion (strict enforcement)

[2/5] Validating naming conventions
      ✓ bronze_customers: valid (bronze layer)
      ✗ ERROR: 'stg_payments' violates naming convention
              Expected: bronze_*, silver_*, gold_* prefix

[3/5] Checking quality gates
      ✗ ERROR: gold_revenue missing required tests
              Required: [not_null_pk, unique_pk, freshness, documentation]
              Missing: [documentation]

[4/5] Compilation FAILED
```

### 2. Schema Validation

Pydantic schemas validate both configuration files:

```python
# floe_core/schemas/manifest.py
class Manifest(BaseModel):
    apiVersion: Literal["floe.dev/v1"]
    kind: Literal["Manifest"]
    metadata: ManifestMetadata
    scope: Literal["enterprise", "domain"]
    parent: ManifestRef | None = None  # Required for domain scope
    plugins: PluginConfig | None = None
    data_architecture: DataArchitectureConfig | None = None
    governance: GovernanceConfig | None = None

# floe_core/schemas/data_product.py
class DataProduct(BaseModel):
    apiVersion: Literal["floe.dev/v1"]
    kind: Literal["DataProduct"]
    metadata: ProductMetadata
    platform: ManifestRef | None = None   # For centralized mode
    domain: ManifestRef | None = None     # For Data Mesh mode
    transforms: list[TransformConfig]
    schedule: ScheduleConfig | None = None
```

### 3. Policy Enforcement

The `PolicyEnforcer` interface validates pipelines:

```python
class PolicyEnforcer(ABC):
    @abstractmethod
    def validate_data_product(self, product: DataProduct, manifest: Manifest) -> list[ValidationError]:
        """Validate a data product against manifest constraints."""
        pass

    @abstractmethod
    def enforce_naming(self, model_name: str, layer: str) -> ValidationResult:
        """Enforce naming conventions based on data architecture pattern."""
        pass

    @abstractmethod
    def check_classification_compliance(self, model: DbtModel) -> list[PolicyViolation]:
        """Check if model handles classified data correctly."""
        pass
```

## What Gets Enforced

| Constraint | Level | Enforcement |
|------------|-------|-------------|
| Compute target | Platform | Cannot override in floe.yaml |
| Naming conventions | Platform | Compile-time validation |
| Quality gates | Platform | Compile-time validation |
| Data classification | Platform | Compile-time + runtime |
| Access control | Platform | Runtime via catalog/semantic layer |
| Test coverage | Platform | Compile-time validation |

## What Data Engineers Control

| Aspect | Control Level |
|--------|---------------|
| Transform logic (dbt SQL) | Full |
| Model dependencies | Full |
| Schedule timing | Within constraints |
| Ingestion sources | From approved list |
| Layer assignment | Via naming convention |

## Enforcement Levels

```yaml
naming:
  enforcement: strict  # off | warn | strict
```

| Level | Behavior | Use Case |
|-------|----------|----------|
| `off` | No enforcement | Migration, experimentation |
| `warn` | Log warnings, continue | Gradual adoption |
| `strict` | Block on violation | Production |

## Platform Artifact Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PLATFORM TEAM                                                           │
│                                                                          │
│  platform-manifest.yaml                                                  │
│         │                                                                │
│         ▼                                                                │
│  [floe platform compile]                                                 │
│         │                                                                │
│         ▼                                                                │
│  [floe platform publish v1.2.3]                                         │
│         │                                                                │
│         ▼                                                                │
│  oci://registry.example.com/floe-platform:v1.2.3                        │
│  ├── manifest.json                                                       │
│  ├── policies/classification.json                                        │
│  ├── policies/quality-gates.json                                         │
│  └── architecture/naming-rules.json                                      │
└─────────────────────────────────────────────────────────────────────────┘
                           │
                           │ Pull (immutable)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DATA TEAM                                                               │
│                                                                          │
│  [floe init --platform=v1.2.3]                                          │
│         │                                                                │
│         ▼                                                                │
│  floe.yaml + models/                                                     │
│         │                                                                │
│         ▼                                                                │
│  [floe compile] ─────► Validates against platform constraints           │
│         │                                                                │
│         ▼                                                                │
│  [floe run] ─────► Executes with enforced guardrails                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Error Messages

Clear, actionable error messages guide compliance:

```
ERROR: Model 'stg_payments' violates naming convention

  Platform: acme-data-platform v1.2.3
  Pattern: medallion
  Enforcement: strict

  Expected prefixes: bronze_*, silver_*, gold_*
  Actual name: stg_payments

  Suggestions:
    - Rename to bronze_payments (raw data)
    - Rename to silver_payments (cleaned data)
    - Rename to gold_payments (aggregated data)

  Documentation: https://docs.floe.dev/naming-conventions
```

---

## Data Mesh: Three-Tier Enforcement

For Data Mesh deployments, enforcement extends to a three-tier model using the unified `Manifest` type:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ENTERPRISE MANIFEST (Global Governance)                                     │
│                                                                              │
│  kind: Manifest, scope: enterprise                                          │
│  • Approved plugins (domains select from these)                             │
│  • Global classification policies (cannot be weakened)                      │
│  • Minimum quality gates (domains can only make stricter)                   │
│  • Shared services configuration                                            │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ Inherits via parent: (cannot weaken)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DOMAIN MANIFEST (Domain Governance)                                         │
│                                                                              │
│  kind: Manifest, scope: domain, parent: ref to enterprise                   │
│  • Select from approved plugins                                             │
│  • Domain-specific extensions (can add stricter policies)                   │
│  • Catalog namespace                                                        │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ Inherits via domain: (cannot weaken)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA PRODUCT (Execution)                                                    │
│                                                                              │
│  kind: DataProduct, domain: ref to domain manifest                          │
│  • Inherits all enterprise + domain constraints                             │
│  • Defines input/output ports                                               │
│  • Declares SLAs (must meet domain minimums)                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Federated Enforcement Rules

| Policy Type | Enterprise | Domain | Product |
|-------------|------------|--------|---------|
| Classification | Sets minimum levels | Can add stricter | Inherits all |
| Quality gates | Sets baseline | Can increase requirements | Inherits all |
| Naming conventions | Sets patterns | Can restrict further | Must comply |
| Plugin selection | Approves options | Selects from approved | Inherits |
| SLAs | Sets minimums | Can require higher | Declares (≥ minimum) |

### Policy Comparison Algorithm

When validating policy inheritance, the system uses strict ordering rules to determine if a child policy strengthens (valid) or weakens (violation) a parent policy.

**Supported Policy Types:**

| Policy Type | Parent | Valid Child | Invalid Child | Comparison Method |
|-------------|--------|-------------|---------------|-------------------|
| **Classification Level** | `INTERNAL` | `CONFIDENTIAL` (stricter) | `PUBLIC` (weaker) | Enum ordering: PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED |
| **Quality Gate Threshold** | `80` | `90` (stricter) | `70` (weaker) | Numeric comparison: child ≥ parent |
| **Test Coverage Minimum** | `70%` | `80%` (stricter) | `60%` (weaker) | Percentage comparison: child ≥ parent |
| **SQL Linting Policy** | `WARN` | `ERROR` (stricter) | `DISABLED` (weaker) | Enum ordering: DISABLED < WARN < ERROR |
| **Contract Enforcement** | `WARN` | `BLOCK` (stricter) | `OFF` (weaker) | Enum ordering: OFF < WARN < ALERT_ONLY < BLOCK |

**Algorithm (Pseudo-code):**

```python
def validate_policy_inheritance(parent_policy: Policy, child_policy: Policy) -> bool:
    """Validate that child policy does not weaken parent policy.

    Returns:
        True if child policy is valid (same or stricter), False otherwise.
    """
    if parent_policy.type == "classification":
        # Enum ordering: PUBLIC=0, INTERNAL=1, CONFIDENTIAL=2, RESTRICTED=3
        return child_policy.level.value >= parent_policy.level.value

    elif parent_policy.type == "quality_gate":
        # Numeric threshold comparison
        return child_policy.threshold >= parent_policy.threshold

    elif parent_policy.type == "test_coverage":
        # Percentage comparison
        return child_policy.minimum_pct >= parent_policy.minimum_pct

    elif parent_policy.type == "sql_linting":
        # Enum ordering: DISABLED=0, WARN=1, ERROR=2
        return child_policy.enforcement.value >= parent_policy.enforcement.value

    elif parent_policy.type == "contract_enforcement":
        # Enum ordering: OFF=0, WARN=1, ALERT_ONLY=2, BLOCK=3
        return child_policy.enforcement.value >= parent_policy.enforcement.value

    else:
        raise ValueError(f"Unknown policy type: {parent_policy.type}")
```

**Validation Examples:**

```python
# ✅ VALID - Child strengthens parent
parent = Policy(type="classification", level=INTERNAL)
child = Policy(type="classification", level=CONFIDENTIAL)
assert validate_policy_inheritance(parent, child) == True

# ❌ INVALID - Child weakens parent
parent = Policy(type="quality_gate", threshold=80)
child = Policy(type="quality_gate", threshold=70)
assert validate_policy_inheritance(parent, child) == False

# ✅ VALID - Child matches parent (allowed)
parent = Policy(type="test_coverage", minimum_pct=70)
child = Policy(type="test_coverage", minimum_pct=70)
assert validate_policy_inheritance(parent, child) == True
```

**See REQ-103** for complete policy comparison specification and ADR-0038 for Data Mesh inheritance rules.

### Manifest Merge Strategies

When inheriting from parent manifests (enterprise → domain → product), the system uses different merge strategies based on the field type.

**Merge Strategy Table:**

| Field | Strategy | Description | Example |
|-------|----------|-------------|---------|
| **plugins** | `OVERRIDE` | Child replaces parent | Parent: `compute: duckdb`, Child: `compute: snowflake` → Result: `snowflake` |
| **classification_levels** | `EXTEND` | Child adds to parent set | Parent: `[PUBLIC, INTERNAL]`, Child: `[CONFIDENTIAL]` → Result: `[PUBLIC, INTERNAL, CONFIDENTIAL]` |
| **quality_gates** | `OVERRIDE_IF_STRICTER` | Child replaces if ≥ parent | Parent: `threshold: 80`, Child: `threshold: 90` → Result: `90` |
| **naming_conventions** | `EXTEND` | Child patterns append to parent | Parent: `raw_*`, Child: `raw_v2_*` → Result: Both patterns enforced |
| **approved_plugins** | `INTERSECT` | Child must be subset of parent | Parent: `[duckdb, snowflake]`, Child: `[snowflake]` → Result: `[snowflake]` |
| **test_coverage** | `OVERRIDE_IF_STRICTER` | Child ≥ parent or reject | Parent: `min: 70%`, Child: `min: 80%` → Result: `80%` |
| **secrets_backend** | `OVERRIDE` | Child replaces parent | Parent: `k8s-secrets`, Child: `infisical` → Result: `infisical` |
| **data_contracts** | `EXTEND` | Child adds to parent contracts | Parent: `odcs_v3`, Child: Custom validators → Result: Both enforced |
| **sla_minimums** | `OVERRIDE_IF_STRICTER` | Child ≥ parent or reject | Parent: `freshness: 24h`, Child: `freshness: 12h` → Result: `12h` |

**Merge Strategy Enforcement:**

```python
def merge_manifests(parent: Manifest, child: Manifest) -> Manifest:
    """Merge child manifest with parent, validating inheritance rules.

    Raises:
        PolicyViolationError: If child weakens parent policy.
    """
    merged = Manifest()

    # OVERRIDE strategy
    merged.plugins = child.plugins or parent.plugins
    merged.secrets_backend = child.secrets_backend or parent.secrets_backend

    # EXTEND strategy
    merged.classification_levels = parent.classification_levels + child.classification_levels
    merged.naming_conventions = parent.naming_conventions + child.naming_conventions
    merged.data_contracts = parent.data_contracts + child.data_contracts

    # INTERSECT strategy
    if child.approved_plugins:
        if not set(child.approved_plugins).issubset(set(parent.approved_plugins)):
            raise PolicyViolationError(
                f"Child approved_plugins must be subset of parent. "
                f"Invalid: {set(child.approved_plugins) - set(parent.approved_plugins)}"
            )
        merged.approved_plugins = child.approved_plugins
    else:
        merged.approved_plugins = parent.approved_plugins

    # OVERRIDE_IF_STRICTER strategy
    if child.quality_gates:
        if child.quality_gates.threshold < parent.quality_gates.threshold:
            raise PolicyViolationError(
                f"Child quality gate ({child.quality_gates.threshold}) "
                f"weakens parent ({parent.quality_gates.threshold})"
            )
        merged.quality_gates = child.quality_gates
    else:
        merged.quality_gates = parent.quality_gates

    return merged
```

**Validation Example (Data Mesh):**

```yaml
# enterprise-manifest.yaml
classification_levels: [PUBLIC, INTERNAL]
quality_gates:
  threshold: 80
approved_plugins:
  compute: [duckdb, snowflake, bigquery]

# domain-manifest.yaml (sales domain)
parent: ref/enterprise-manifest/v1.2.3
classification_levels: [CONFIDENTIAL]  # EXTEND: Adds to parent
quality_gates:
  threshold: 90                         # OVERRIDE_IF_STRICTER: Valid (90 ≥ 80)
approved_plugins:
  compute: [snowflake]                  # INTERSECT: Valid (subset)

# Merged Result:
classification_levels: [PUBLIC, INTERNAL, CONFIDENTIAL]
quality_gates:
  threshold: 90
approved_plugins:
  compute: [snowflake]
```

**Error Example (Invalid Weakening):**

```yaml
# ❌ INVALID - Child weakens quality gate
# enterprise: threshold: 80
# domain: threshold: 70  # ERROR: Weakens parent (70 < 80)
```

**See REQ-103** for complete manifest merge specification and ADR-0038 for Data Mesh inheritance patterns.

### Data Contract Enforcement

Data contracts are enforced at both compile-time and runtime using the ODCS (Open Data Contract Standard) format.

#### Compile-Time Contract Validation

The PolicyEnforcer validates contracts during `floe compile`:

```python
class PolicyEnforcer:
    def validate_data_contracts(
        self,
        contracts: list[DataContract],
        manifest: Manifest,
    ) -> list[ValidationError]:
        """Validate contracts against manifest constraints."""
        errors = []

        for contract in contracts:
            # Check schema validity
            schema_errors = self._contract_plugin.validate_contract(contract)
            errors.extend(schema_errors)

            # Check inheritance (child can't weaken parent)
            if manifest.parent:
                parent_errors = self._validate_inheritance(contract, manifest)
                errors.extend(parent_errors)

            # Check version bump rules
            if previous := self._get_previous_contract(contract.name):
                valid, reason = self._contract_plugin.validate_version_bump(
                    previous, contract
                )
                if not valid:
                    errors.append(ValidationError(reason))

        return errors
```

#### Runtime Contract Monitoring

The ContractMonitor validates contracts during execution:

| Check | Interval | Description |
|-------|----------|-------------|
| Freshness | 15 min | Data updated within SLA window |
| Schema drift | 1 hour | Actual schema matches contract |
| Quality | 6 hours | Data quality above threshold |
| Availability | 5 min | Data source accessible |

Violations are emitted as OpenLineage FAIL events with the `contractViolation` facet.

#### Platform Manifest Configuration

```yaml
# platform-manifest.yaml
data_contracts:
  enforcement: alert_only   # off | warn | alert_only | block
  standard: odcs_v3         # ODCS v3.x

  plugin:
    type: odcs              # datacontract-cli wrapper

  auto_generation:
    enabled: true
    from_ports: true        # Generate from input/output ports
    from_dbt_manifest: true # Enrich from dbt manifest

  monitoring:
    enabled: true
    mode: scheduled         # scheduled | continuous | on_demand
    freshness:
      check_interval: 15m
    schema_drift:
      check_interval: 1h
    quality:
      check_interval: 6h

  alerting:
    openlineage_events: true
    prometheus_metrics: true
```

#### Contract Inheritance Rules

Contracts follow the three-tier inheritance model:

| Tier | Can Define | Can Override |
|------|------------|--------------|
| Enterprise | Base SLAs, required fields, classification policies | N/A |
| Domain | Domain-specific additions | Can STRENGTHEN, not weaken |
| Data Product | Specific schema, specific SLAs | Can STRENGTHEN, not weaken |

Example: If enterprise sets freshness minimum as 24h, domain can require 6h, and product can implement 4h, but none can be worse than parent.

#### Example: ODCS Data Contract

```yaml
# datacontract.yaml (alongside data-product.yaml)
apiVersion: v3.0.2
kind: DataContract
name: sales-customer-360-customers
version: 2.1.0

owner: sales-analytics@acme.com
domain: sales

models:
  customers:
    elements:
      customer_id:
        type: string
        primaryKey: true
      email:
        type: string
        classification: pii

slaProperties:
  freshness:
    value: "PT6H"
    element: updated_at
  availability:
    value: "99.9%"
```

See [Data Contracts Architecture](data-contracts.md) and [ADR-0026](adr/0026-data-contract-architecture.md) for full documentation.

---

## Product Identity Enforcement

In distributed Data Mesh environments, multiple teams may independently create data products. Without identity enforcement, naming collisions can occur, leading to:

- Tables overwriting each other
- Contract conflicts
- Corrupted lineage

### Namespace-Based Identity Model

Products are identified by their namespace: `{domain}.{product}`

```
Product ID:   {domain}.{product}
              └──────┬──────────┘
              "sales.customer_360"

Contract ID:  {domain}.{product}/{contract}:{version}
              └──────────────────┬─────────────────────┘
              "sales.customer_360/customers:1.0.0"
```

The Iceberg catalog serves as the product registry via namespace properties.

### Compile-Time Identity Validation

Identity is validated during `floe compile`:

```bash
$ floe compile

[1/6] Loading platform artifacts
      ✓ Platform version: 1.2.3

[2/6] Validating product identity
      Product ID: sales.customer_360
      Repository: github.com/acme/sales-customer-360
      ✓ Namespace available, registering...
      ✓ Product registered in catalog

# OR, if conflict:

[2/6] Validating product identity
      ✗ ERROR: Namespace 'sales.customer_360' owned by different repository
              Owner: github.com/acme/other-repo
              Expected: github.com/acme/sales-customer-360

      Resolution: Choose a different product name or contact
                 the namespace owner: other-team@acme.com
```

### PolicyEnforcer Identity Validation

```python
class PolicyEnforcer:
    def validate_product_identity(
        self,
        product: DataProduct,
        catalog: CatalogPlugin,
    ) -> list[EnforcementViolation]:
        """Validate product can claim its namespace."""
        product_id = f"{product.domain}.{product.name}"

        result = catalog.validate_product_identity(
            namespace=product_id,
            expected_repo=product.repository,
        )

        if result.status == "conflict":
            return [
                EnforcementViolation(
                    severity=Severity.ERROR,
                    code="IDENTITY_CONFLICT",
                    message=f"Namespace '{product_id}' is owned by "
                            f"'{result.repository}', not '{product.repository}'",
                    resolution="Choose a different product name or contact "
                              f"the namespace owner: {result.owner}",
                )
            ]

        return []
```

### Atomic Registration and Race Condition Prevention

Namespace registration uses **atomic compare-and-swap** semantics to prevent race conditions when multiple CI pipelines attempt to claim the same namespace concurrently.

#### CatalogPlugin Atomicity Contract

```python
class CatalogPlugin(ABC):
    @abstractmethod
    def register_product_identity(
        self,
        namespace: str,
        repository: str,
        owner: str,
        if_not_exists: bool = True,
    ) -> RegistrationResult:
        """
        Atomically register a product namespace.

        This operation MUST be atomic:
        - If namespace doesn't exist: create with provided properties → SUCCESS
        - If namespace exists with same repository: no-op → ALREADY_OWNED
        - If namespace exists with different repository: fail → CONFLICT

        The catalog MUST guarantee that concurrent calls cannot both succeed
        with different repository values for the same namespace.

        Returns:
            RegistrationResult with status: SUCCESS | ALREADY_OWNED | CONFLICT
        """
        pass
```

#### Catalog-Specific Implementations

| Catalog | Atomicity Mechanism | Behavior |
|---------|---------------------|----------|
| **Polaris** | Transactional namespace creation | `createNamespace` fails if exists; properties immutable after creation |
| **Unity Catalog** | Optimistic locking via `DBPROPERTIES` | First write wins; subsequent writes with different `floe.product.repo` fail |
| **AWS Glue** | Conditional put on `Database.Parameters` | Uses DynamoDB conditional writes under the hood |
| **Nessie** | Git-like versioned transactions | Commit fails if namespace was modified since read |

#### Polaris Atomic Registration Example

```python
# polaris_catalog_plugin.py
class PolarisCatalogPlugin(CatalogPlugin):
    def register_product_identity(
        self,
        namespace: str,
        repository: str,
        owner: str,
        if_not_exists: bool = True,
    ) -> RegistrationResult:
        """Atomic namespace registration using Polaris transactions."""
        try:
            # Polaris createNamespace is atomic - fails if namespace exists
            self._client.create_namespace(
                namespace=namespace,
                properties={
                    "floe.product.repo": repository,
                    "floe.product.owner": owner,
                    "floe.product.registered_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            return RegistrationResult(status="SUCCESS")

        except NamespaceAlreadyExistsError:
            # Namespace exists - check if we own it
            existing = self._client.get_namespace(namespace)
            existing_repo = existing.properties.get("floe.product.repo")

            if existing_repo == repository:
                return RegistrationResult(status="ALREADY_OWNED")
            else:
                return RegistrationResult(
                    status="CONFLICT",
                    repository=existing_repo,
                    owner=existing.properties.get("floe.product.owner"),
                )
```

#### Race Condition Handling

When two CI pipelines race to register the same namespace:

```
Pipeline A (repo-1)          Catalog              Pipeline B (repo-2)
      │                         │                        │
      ├── createNamespace ──────►                        │
      │   (namespace=sales.foo) │                        │
      │                         │◄── createNamespace ────┤
      │                         │    (namespace=sales.foo)
      │                         │                        │
      ◄── SUCCESS ──────────────┤                        │
      │                         ├── NamespaceAlreadyExists ──►
      │                         │                        │
      │                         │    (checks properties) │
      │                         ├── CONFLICT ────────────►
      │                         │                        │
      ✓ Continues with compile  │                        ✗ Fails with clear error
```

**Guarantees:**
1. Exactly one pipeline succeeds in registering the namespace
2. The losing pipeline receives a clear `CONFLICT` error with owner information
3. No partial or inconsistent state is possible

#### Distributed Lock Alternative

For catalogs that don't support atomic conditional operations, a distributed lock can be used:

```python
class LockingCatalogPlugin(CatalogPlugin):
    def register_product_identity(
        self,
        namespace: str,
        repository: str,
        owner: str,
        if_not_exists: bool = True,
    ) -> RegistrationResult:
        """Use distributed lock for catalogs without atomic operations."""
        lock_key = f"floe:namespace:lock:{namespace}"

        # Acquire distributed lock (Redis-based)
        with self._lock_manager.acquire(lock_key, timeout=30):
            # Check if namespace exists
            existing = self._catalog.get_namespace_properties(namespace)

            if existing:
                existing_repo = existing.get("floe.product.repo")
                if existing_repo == repository:
                    return RegistrationResult(status="ALREADY_OWNED")
                else:
                    return RegistrationResult(
                        status="CONFLICT",
                        repository=existing_repo,
                        owner=existing.get("floe.product.owner"),
                    )

            # Create namespace while holding lock
            self._catalog.create_namespace(
                namespace=namespace,
                properties={
                    "floe.product.repo": repository,
                    "floe.product.owner": owner,
                }
            )
            return RegistrationResult(status="SUCCESS")
```

#### CI Pipeline Retry Behavior

On transient failures during registration:

```yaml
# Exponential backoff with jitter for registration retries
registration:
  max_attempts: 3
  initial_backoff: 1s
  max_backoff: 10s
  jitter: 0.2  # ±20% randomization
```

If registration fails with `CONFLICT`, the error is **not retried** - it indicates a genuine ownership conflict that requires human resolution.

### Catalog Namespace Properties

Product identity is stored in Iceberg catalog namespace properties:

| Property | Description |
|----------|-------------|
| `floe.product.name` | Product name |
| `floe.product.domain` | Parent domain |
| `floe.product.owner` | Owner email |
| `floe.product.repo` | Source repository (ownership proof) |
| `floe.product.version` | Current version |
| `floe.product.registered_at` | Registration timestamp |
| `floe.contracts` | JSON array of registered contracts |

### data-product.yaml Repository Field

Products must declare their source repository:

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-360
  version: "1.2.3"
  owner: sales-analytics@acme.com
  domain: sales
  repository: github.com/acme/sales-customer-360  # Required for identity
```

### Platform Manifest Configuration

```yaml
# platform-manifest.yaml
identity:
  enforcement: enforce   # off | warn | register | enforce
  auto_register: true    # Auto-register unregistered products
```

| Level | Behavior |
|-------|----------|
| `off` | No identity validation |
| `warn` | Log warnings for unregistered products |
| `register` | Auto-register, fail on conflict |
| `enforce` | Require registration, fail on conflict |

### Universal Catalog Support

Identity enforcement works with all Iceberg-compatible catalogs:

| Catalog | Property Storage |
|---------|-----------------|
| Polaris | `createNamespace(properties)` |
| Unity Catalog | `DBPROPERTIES` |
| AWS Glue | `Database.Parameters` |
| Hive Metastore | `DBPROPERTIES` |
| Nessie | Namespace properties |

See [ADR-0030: Namespace-Based Identity](adr/0030-namespace-identity.md) for full documentation.

## Related Documents

- [ADR-0016: Platform Enforcement Architecture](adr/0016-platform-enforcement-architecture.md)
- [ADR-0018: Opinionation Boundaries](adr/0018-opinionation-boundaries.md)
- [ADR-0021: Data Architecture Patterns](adr/0021-data-architecture-patterns.md)
- [ADR-0026: Data Contract Architecture](adr/0026-data-contract-architecture.md)
- [ADR-0027: ODCS Standard Adoption](adr/0027-odcs-standard-adoption.md)
- [ADR-0028: Runtime Contract Monitoring](adr/0028-runtime-contract-monitoring.md)
- [ADR-0030: Namespace-Based Identity](adr/0030-namespace-identity.md)
- [Data Contracts Architecture](data-contracts.md)
- [Four-Layer Overview](four-layer-overview.md)
- [Opinionation Boundaries](opinionation-boundaries.md)
