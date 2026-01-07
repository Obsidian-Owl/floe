# REQ-141 to REQ-150: Compilation Workflow and Artifact Generation

**Domain**: Configuration Management
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the `floe compile` workflow that transforms data-product.yaml + platform-manifest into compiled artifacts ready for execution.

**Key Principle**: Compile-time validation prevents runtime failures

## Requirements

### REQ-141: floe compile Command with Multi-Stage Pipeline **[New]**

**Requirement**: System MUST implement `floe compile` command that executes multi-stage pipeline: load → validate → resolve → enforce → compile → artifact generation.

**Rationale**: Structured pipeline enables clear error messages and incremental improvements.

**Acceptance Criteria**:
- [ ] Command: `floe compile [--data-product=floe.yaml] [--environment=prod]`
- [ ] Stage 1 (Load): Load floe.yaml and platform manifest
- [ ] Stage 2 (Validate): Schema validation
- [ ] Stage 3 (Resolve): Manifest resolution (2-tier or 3-tier)
- [ ] Stage 4 (Enforce): Policy validation via PolicyEnforcer
- [ ] Stage 5 (Compile): Generate dbt profiles, Dagster config
- [ ] Stage 6 (Artifacts): Output compiled artifacts
- [ ] Clear progress logging for each stage
- [ ] Stop on first error with actionable message

**Enforcement**:
- Pipeline stage tests
- Error handling tests
- Progress logging tests

**Constraints**:
- MUST execute stages in order
- MUST stop on first error
- FORBIDDEN to skip validation stages

**Test Coverage**: `tests/unit/test_compile_command.py`

**Traceability**:
- platform-enforcement.md lines 73-98
- MIGRATION-ROADMAP.md

---

### REQ-142: CompiledArtifacts Output Contract **[New]**

**Requirement**: System MUST generate CompiledArtifacts as single immutable contract containing dbt profiles, Dagster config, catalog config, computed metadata.

**Rationale**: Single contract enables floe-dbt and floe-dagster to consume compilation output reliably.

**Acceptance Criteria**:
- [ ] CompiledArtifacts defined in `floe_core/schemas/compiled_artifacts.py`
- [ ] Fields: version, metadata, compute, transforms, consumption, governance, observability
- [ ] Pydantic v2 with model_config(frozen=True, extra="forbid")
- [ ] to_json_file(path: Path) → writes JSON
- [ ] from_json_file(path: Path) → loads JSON
- [ ] Schema stable (semver changes only)
- [ ] Optional SaaS fields (lineage_namespace, environment_context)

**Enforcement**:
- Schema validation tests
- Serialization tests
- Versioning tests
- Optional field tests

**Constraints**:
- MUST use Pydantic v2 frozen model
- MUST be JSON serializable
- FORBIDDEN to change schema without version bump

**Test Coverage**: `tests/contract/test_compiled_artifacts_contract.py`

**Traceability**:
- pydantic-contracts.md
- ADR-0037 (Composability Principle)

---

### REQ-143: dbt Profiles Generation from Manifest **[New]**

**Requirement**: System MUST generate dbt profiles.yml from ComputePlugin configuration in manifest, resolving credentials from secrets backend.

**Rationale**: Enables dbt to connect to compute target without manual profile setup.

**Acceptance Criteria**:
- [ ] Generate profiles.yml from manifest.plugins.compute
- [ ] Support multiple compute targets (DuckDB, Snowflake, BigQuery, etc.)
- [ ] Resolve credentials via SecretsPlugin: {{ env_var('SECRET_NAME') }}
- [ ] Support environment-specific credentials
- [ ] Output profiles.yml compatible with dbt version
- [ ] Error if compute target not configured
- [ ] Error if required credentials missing

**Enforcement**:
- Profile generation tests
- Credential resolution tests
- dbt compatibility tests
- Error handling tests

**Constraints**:
- MUST generate valid dbt profiles.yml
- MUST resolve secrets from backend
- FORBIDDEN to hardcode credentials

**Test Coverage**: `tests/integration/test_dbt_profiles_generation.py`

**Traceability**:
- floe-dbt integration
- REQ-136 (Secret Reference Injection)

---

### REQ-144: Dagster Configuration Generation from CompiledArtifacts **[New]**

**Requirement**: System MUST generate Dagster configuration (definitions, assets, schedules, resources) from CompiledArtifacts, ready for `dagster dev` or K8s deployment.

**Rationale**: Enables Dagster to orchestrate compiled data products without custom Python code.

**Acceptance Criteria**:
- [ ] Generate Dagster Definitions object with assets
- [ ] Create @asset for each dbt model
- [ ] Create @asset for each external source
- [ ] Create @schedule for each product schedule
- [ ] Create @sensor for triggers/webhooks
- [ ] Configure resources (catalog, compute, storage)
- [ ] Output: Python module or YAML manifest
- [ ] Error if Dagster config invalid

**Enforcement**:
- Dagster configuration tests
- Asset generation tests
- Schedule generation tests
- Resource configuration tests

**Constraints**:
- MUST generate valid Dagster config
- MUST support K8s job execution
- FORBIDDEN to require manual code changes

**Test Coverage**: `tests/integration/test_dagster_config_generation.py`

**Traceability**:
- floe-dagster integration
- REQ-142 (CompiledArtifacts Output Contract)

---

### REQ-145: Catalog Configuration and Namespace Registration **[New]**

**Requirement**: System MUST generate catalog configuration (namespace, properties) from DataProduct metadata and register product namespace atomically in catalog.

**Rationale**: Ensures product owns its namespace and properties are set for identity/tracking.

**Acceptance Criteria**:
- [ ] Generate namespace: {domain}.{product_name}
- [ ] Set namespace properties: floe.product.name, floe.product.domain, floe.product.owner, floe.product.repo
- [ ] Atomic registration: createNamespace fails if exists with different owner
- [ ] Error if namespace owned by different repository
- [ ] Clear error with namespace owner contact
- [ ] Support all catalogs: Polaris, Unity, Glue, Nessie

**Enforcement**:
- Namespace generation tests
- Property setting tests
- Atomic registration tests
- Catalog-specific tests

**Constraints**:
- MUST use atomic operations
- MUST set required namespace properties
- FORBIDDEN to allow namespace collisions

**Test Coverage**: `tests/integration/test_catalog_registration.py`

**Traceability**:
- REQ-124 (Catalog Namespace Validation)
- ADR-0030 (Namespace-Based Identity)

---

### REQ-146: Data Contract Generation and Validation **[New]**

**Requirement**: System MUST generate data contracts in ODCS v3 format from floe.yaml and dbt manifest, and validate contracts against manifest constraints.

**Rationale**: Enables contract-driven development and runtime validation.

**Acceptance Criteria**:
- [ ] Generate ODCS v3 contract for each data product
- [ ] Extract schema from dbt manifest
- [ ] Extract SLAs from product schedule and governance
- [ ] Extract classifications from dbt column metadata
- [ ] Validate contract schema matches dbt models
- [ ] Validate contract SLAs >= domain/enterprise minimums
- [ ] Output: datacontract.yaml alongside compiled artifacts
- [ ] Error if contract invalid or missing required fields

**Enforcement**:
- Contract generation tests
- Schema validation tests
- SLA validation tests
- ODCS compliance tests

**Constraints**:
- MUST follow ODCS v3 standard
- MUST validate all required fields
- FORBIDDEN to generate incomplete contracts

**Test Coverage**: `tests/contract/test_data_contract_generation.py`

**Traceability**:
- ADR-0026 (Data Contract Architecture)
- ADR-0027 (ODCS Standard Adoption)

---

### REQ-147: Artifact Versioning and Metadata **[New]**

**Requirement**: System MUST include artifact versioning, generation timestamp, platform version, and product version in compiled artifacts for reproducibility and debugging.

**Rationale**: Enables tracking which platform/product generated artifacts and when.

**Acceptance Criteria**:
- [ ] CompiledArtifacts.version: artifact schema version
- [ ] CompiledArtifacts.metadata.product_version: from product YAML
- [ ] CompiledArtifacts.metadata.platform_version: from manifest
- [ ] CompiledArtifacts.metadata.generated_at: ISO 8601 timestamp
- [ ] CompiledArtifacts.metadata.generated_by: user/service
- [ ] CompiledArtifacts.metadata.git_commit: source repository commit hash
- [ ] Include in all outputs (JSON, YAML, OCI artifacts)

**Enforcement**:
- Metadata inclusion tests
- Version format tests
- Timestamp tests
- Git commit tracking tests

**Constraints**:
- MUST include all metadata fields
- MUST use ISO 8601 timestamps
- FORBIDDEN to omit versioning info

**Test Coverage**: `tests/unit/test_artifact_versioning.py`

**Traceability**:
- REQ-142 (CompiledArtifacts Output Contract)

---

### REQ-148: Incremental Compilation and Caching **[New]**

**Requirement**: System MUST support incremental compilation by caching resolved manifests and skipping unchanged stages to improve compile speed.

**Rationale**: Enables fast feedback during development without full recompilation.

**Acceptance Criteria**:
- [ ] Cache resolved manifests (avoid repeated OCI loads)
- [ ] Cache dbt manifest.json parse
- [ ] Skip stages if inputs unchanged
- [ ] Clear cache: `floe compile --no-cache`
- [ ] Cache validation: detect manifest version changes
- [ ] Performance: repeat compile 10x faster than initial

**Enforcement**:
- Caching behavior tests
- Cache invalidation tests
- Performance tests
- No-cache flag tests

**Constraints**:
- MUST invalidate cache on manifest version change
- MUST use timestamp-based cache expiry
- FORBIDDEN to use stale cache

**Test Coverage**: `tests/unit/test_incremental_compilation.py`

**Traceability**:
- REQ-141 (floe compile Command)

---

### REQ-149: Compile Output Formats (JSON, YAML, OCI) **[New]**

**Requirement**: System MUST support multiple output formats for compiled artifacts: JSON (default), YAML, and OCI artifact (for registry publication).

**Rationale**: Enables different workflows (debugging with YAML, distribution via OCI registry).

**Acceptance Criteria**:
- [ ] JSON output: `floe compile --output=target/compiled.json`
- [ ] YAML output: `floe compile --output=target/compiled.yaml`
- [ ] OCI output: `floe compile --output=oci://registry/product:version`
- [ ] All formats contain identical data
- [ ] OCI format signed with cosign
- [ ] Error on unsupported format

**Enforcement**:
- Format conversion tests
- JSON schema validation tests
- YAML schema validation tests
- OCI artifact tests
- Format parity tests

**Constraints**:
- MUST support JSON and YAML
- MUST support OCI push
- FORBIDDEN to lose data in format conversion

**Test Coverage**: `tests/unit/test_compile_output_formats.py`

**Traceability**:
- REQ-141 (floe compile Command)
- REQ-142 (CompiledArtifacts Output Contract)

---

### REQ-150: Compilation Dry-Run and Validation Mode **[New]**

**Requirement**: System MUST support `floe compile --dry-run` mode that validates compilation without generating artifacts, and `--validate-only` to check only policy compliance.

**Rationale**: Enables safe pre-flight checks without side effects.

**Acceptance Criteria**:
- [ ] `--dry-run` flag: validate all stages, skip artifact generation
- [ ] `--validate-only` flag: skip dbt/Dagster compilation, check policies only
- [ ] Output: validation report with all errors/warnings
- [ ] Exit code: non-zero on validation failure
- [ ] No side effects: no files written, no catalog changes
- [ ] Clear indication: "DRY RUN - No artifacts generated"

**Enforcement**:
- Dry-run tests
- Validate-only tests
- Exit code tests
- Side effect tests

**Constraints**:
- MUST NOT write files in dry-run mode
- MUST NOT modify catalog in dry-run mode
- FORBIDDEN to skip validation stages

**Test Coverage**: `tests/unit/test_compile_dry_run.py`

**Traceability**:
- REQ-141 (floe compile Command)
- REQ-130 (Manifest Validation and Dry-Run Testing)

---

## Domain Acceptance Criteria

Compilation Workflow and Artifact Generation (REQ-141 to REQ-150) is complete when:

- [ ] All 10 requirements have complete template fields
- [ ] `floe compile` command fully implemented
- [ ] CompiledArtifacts contract defined and stable
- [ ] dbt profiles.yml generation
- [ ] Dagster configuration generation
- [ ] Catalog namespace registration
- [ ] Data contract generation
- [ ] Artifact versioning and metadata
- [ ] Incremental compilation and caching
- [ ] Multiple output formats (JSON, YAML, OCI)
- [ ] Dry-run and validation modes
- [ ] Unit tests pass with >80% coverage
- [ ] Integration tests pass with real dbt/Dagster
- [ ] Documentation updated:
  - [ ] MIGRATION-ROADMAP.md backreferences requirements
  - [ ] platform-enforcement.md backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 2: Configuration Layer Modernization**:
- Phase 1: Compilation pipeline stages
- Phase 2: CompiledArtifacts contract
- Phase 3: Output format support
- Phase 4: Validation and dry-run modes

## Example: floe compile Execution

```bash
$ floe compile --data-product=floe.yaml --environment=prod

[1/6] Loading data product
      ✓ Data product: customer-360
      ✓ Platform manifest: oci://registry/sales-domain-manifest:v2.0.0

[2/6] Validating schemas
      ✓ Data product schema valid
      ✓ Platform manifest schema valid

[3/6] Resolving manifests (3-tier)
      ✓ Enterprise manifest: oci://registry/enterprise-manifest:v1.0.0
      ✓ Domain manifest: oci://registry/sales-domain-manifest:v2.0.0
      ✓ Inheritance chain validated

[4/6] Enforcing policies
      ✓ Naming convention (medallion): valid
      ✓ Quality gates: 95% coverage > 80% required
      ✓ PII classification: 3 PII fields tagged
      ✓ Product approval: customer-360 in approved_products
      ✓ Namespace registration: sales.customer_360 (atomic)

[5/6] Compiling artifacts
      ✓ Generated dbt profiles.yml
      ✓ Generated Dagster definitions
      ✓ Generated data contract (ODCS v3)
      ✓ Generated catalog configuration

[6/6] Artifact generation
      ✓ Output: target/compiled.json (2.3 MB)
      ✓ Version: artifacts/v2.0.0
      ✓ Timestamp: 2026-01-06T14:32:45Z
      ✓ Checksum: sha256:abc123def456...

✅ Compilation successful (1.2s total)
```

## Failure Example: floe compile Policy Violation

```bash
$ floe compile --data-product=floe.yaml

[1/6] Loading data product
      ✓ Data product: customer-360
      ✓ Platform manifest: oci://registry/sales-domain-manifest:v2.0.0

[2/6] Validating schemas
      ✓ Schemas valid

[3/6] Resolving manifests (3-tier)
      ✓ Inheritance chain validated

[4/6] Enforcing policies
      ✗ NAMING VIOLATION: Model 'stg_customers' violates medallion pattern
        Expected: bronze_*, silver_*, gold_* prefix
        Actual: stg_customers
        Platform: acme-data-platform v1.2.3
        Enforcement: strict

        Suggestions:
          - Rename to bronze_customers (raw data)
          - Rename to silver_customers (cleaned data)
          - Rename to gold_customers (aggregated data)

        Documentation: https://docs.floe.dev/naming-conventions
        Severity: ERROR

      ✗ PRODUCT APPROVAL: Product 'customer-360' not in approved_products for sales domain
        Approved products: [lead-scoring, opportunity-forecasting]
        Contact: sales-owner@acme.com
        Severity: ERROR

[4/6] Compilation FAILED

❌ 2 policy violations. Fix and retry.
```
