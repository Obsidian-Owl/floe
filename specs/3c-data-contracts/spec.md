# Feature Specification: Data Contracts

**Epic**: 3C (Data Contracts)
**Feature Branch**: `3c-data-contracts`
**Created**: 2026-01-23
**Status**: Clarified
**Input**: User description: "Epic 3C: Data Contracts - Implement compile-time data contract validation and runtime contract monitoring using ODCS v3 standard"

## Context: Current State & Architecture

Epic 3A (Policy Enforcer Core) and Epic 3B (Policy Validation Enhancement) are complete and provide the foundation:

**Implemented Infrastructure:**
- `PolicyEnforcer` - Core orchestrator coordinating all validators
- 5 Validators: naming, coverage, documentation, semantic, custom rules
- `EnforcementResult`, `Violation`, `EnforcementSummary` - Result models
- Policy overrides with expiration support
- Export formats: JSON, SARIF, HTML
- Error codes: FLOE-E2xx (naming/coverage/docs), FLOE-E3xx (semantic), FLOE-E4xx (custom)

**Dependencies (from EPIC-OVERVIEW.md):**
- Epic 3A (Policy Enforcer) - COMPLETE
- Epic 4D (Storage Plugin) - COMPLETE (`IcebergTableManager` provides schema access)

**Architecture (from docs/architecture/data-contracts.md and ADR-0026):**
- Data contracts use **ODCS v3** (Open Data Contract Standard) - enforced, not pluggable
- ODCS backed by Linux Foundation (Bitol project), tooling via `datacontract-cli`
- Contracts can be explicit (`datacontract.yaml`) or auto-generated from `floe.yaml` ports
- Three-tier inheritance: Enterprise -> Domain -> Data Product (child cannot weaken parent)
- Compile-time validation via PolicyEnforcer, runtime monitoring via ContractMonitor (Epic 3D)

**What Epic 3C Adds:**
- Data contract parsing and generation from ports
- Contract schema validation (ODCS v3 compliance)
- Contract inheritance validation (child cannot weaken parent SLAs)
- Contract versioning rules (semantic versioning enforcement)
- Contract registration in Iceberg catalog
- Schema drift detection against actual table schemas
- Integration with CompiledArtifacts contract

---

## Scope

### In Scope

- **Contract Parsing**: Parse `datacontract.yaml` files (ODCS v3 format)
- **Contract Generation**: Auto-generate contracts from `floe.yaml` output_ports
- **Contract Merging**: Merge explicit contracts with auto-generated (explicit overrides)
- **Schema Validation**: Validate contract schema completeness and ODCS v3 compliance
- **Inheritance Validation**: Validate child contracts don't weaken parent SLAs/requirements
- **Version Bump Validation**: Enforce semantic versioning rules for contract changes
- **Catalog Registration**: Register contract metadata in Iceberg catalog namespace
- **Schema Drift Detection**: Detect differences between contract and actual table schema
- **PolicyEnforcer Integration**: Add contract validation to compile-time pipeline
- **CompiledArtifacts Extension**: Store contract definitions in compiled artifacts

### Out of Scope

- **Runtime Contract Monitoring** (Epic 3D) - Freshness, availability, quality SLA checks
- **Alerting and Metrics** (Epic 3D) - OpenLineage events, Prometheus metrics
- **Contract Deprecation Workflow** (Epic 3D) - Lifecycle state transitions
- **datacontract-cli Wrapper** (Epic 3D) - Full CLI integration for testing/validation

### Integration Points

**Entry Point**: `floe compile` CLI command (floe-core package)

**Dependencies**:
- floe-core: PolicyEnforcer, CompiledArtifacts, EnforcementResult
- floe-core.schemas.governance: GovernanceConfig, new DataContractsConfig
- Epic 4D (Storage Plugin): IcebergTableManager for actual schema access
- Epic 4C (Catalog Plugin): CatalogPlugin for contract registration
- `datacontract-cli` (external): ODCS parsing, linting, and validation (hard dependency)

**Produces**:
- `DataContract` Pydantic model (ODCS v3 schema)
- `ContractValidationResult` model (validation outcomes)
- `SchemaComparisonResult` model (drift detection)
- Extended `CompiledArtifacts.data_contracts[]` field
- Contract metadata in Iceberg catalog namespace properties

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contract Definition and Validation (Priority: P1)

A data engineer defines a formal data contract for their data product using `datacontract.yaml`. When they run `floe compile`, the contract is validated for ODCS v3 compliance, schema completeness, and SLA validity. Any violations are reported with actionable error messages.

**Why this priority**: This is the core value proposition - formal contracts enable producer-consumer agreements and computational governance. Without validation, contracts are just documentation.

**Independent Test**: Can be fully tested by creating a `datacontract.yaml` with various valid/invalid configurations and verifying compile-time validation catches all issues with clear error messages.

**Acceptance Scenarios**:

1. **Given** a valid `datacontract.yaml` with schema, owner, and SLAs, **When** a data engineer runs `floe compile`, **Then** the contract is parsed successfully and stored in CompiledArtifacts.

2. **Given** a `datacontract.yaml` missing required `owner` field, **When** validation runs, **Then** a FLOE-E501 error is generated specifying the missing field and ODCS requirement.

3. **Given** a `datacontract.yaml` with invalid SLA duration format (e.g., "6 hours" instead of "PT6H"), **When** validation runs, **Then** a FLOE-E502 error is generated with the correct ISO 8601 format hint.

4. **Given** a `datacontract.yaml` with unsupported element type, **When** validation runs, **Then** a FLOE-E503 error lists valid ODCS element types.

---

### User Story 2 - Contract Auto-Generation from Ports (Priority: P1)

A data engineer defines output_ports in `floe.yaml`. When they run `floe compile` without an explicit `datacontract.yaml`, the system auto-generates a base contract from the port definitions, extracting schema information, ownership, and metadata.

**Why this priority**: Auto-generation lowers the barrier to entry. Data engineers get contracts without learning ODCS syntax, enabling gradual adoption from simple ports to full contracts.

**Independent Test**: Can be fully tested by creating a `floe.yaml` with output ports and verifying the generated contract matches expected structure and contains all port metadata.

**Acceptance Scenarios**:

1. **Given** a `floe.yaml` with output_ports defining a table schema, **When** `floe compile` runs without `datacontract.yaml`, **Then** a base contract is generated with model schema matching port definition.

2. **Given** a `floe.yaml` with port metadata (owner, description, tags), **When** contract is generated, **Then** metadata is correctly mapped to ODCS contract fields.

3. **Given** both `floe.yaml` ports and explicit `datacontract.yaml`, **When** `floe compile` runs, **Then** explicit contract values override auto-generated values (merge strategy).

---

### User Story 3 - Contract Inheritance Validation (Priority: P1)

A platform engineer defines enterprise-level contract requirements (minimum freshness SLA, mandatory PII classification). When a domain or data product contract is compiled, the system validates that it doesn't weaken parent requirements.

**Why this priority**: Inheritance enforcement is essential for governance at scale. Without it, teams can bypass enterprise policies by defining weaker contracts.

**Independent Test**: Can be fully tested by creating enterprise -> domain -> product contract chains with various strengthening/weakening scenarios and verifying inheritance rules are enforced.

**Acceptance Scenarios**:

1. **Given** an enterprise contract with `freshness: PT6H`, **When** a domain contract sets `freshness: PT12H` (weaker), **Then** a FLOE-E510 error is generated indicating the SLA cannot be relaxed.

2. **Given** an enterprise contract with `freshness: PT6H`, **When** a domain contract sets `freshness: PT2H` (stronger), **Then** validation passes (strengthening allowed).

3. **Given** an enterprise contract with `quality.completeness: 99%`, **When** a product contract sets `quality.completeness: 95%` (weaker), **Then** a FLOE-E510 error is generated indicating quality threshold cannot be relaxed.

4. **Given** an enterprise contract with `availability: 99.9%`, **When** a product contract sets `availability: 99.0%` (weaker), **Then** a FLOE-E510 error is generated.

---

### User Story 4 - Contract Version Bump Validation (Priority: P2)

A data engineer modifies a contract (adds column, changes SLA). The system detects the change type and enforces semantic versioning rules: breaking changes require MAJOR bump, additive changes require MINOR bump, documentation changes require PATCH bump.

**Why this priority**: Version discipline prevents silent breaking changes that could affect downstream consumers. Automated enforcement catches mistakes before they reach production.

**Independent Test**: Can be fully tested by modifying contracts in various ways and verifying the system correctly identifies required version bump type.

**Acceptance Scenarios**:

1. **Given** a contract change that removes a required column, **When** version stays at PATCH level, **Then** a FLOE-E520 error identifies the breaking change requiring MAJOR bump.

2. **Given** a contract change that adds an optional column, **When** version has MINOR bump, **Then** validation passes.

3. **Given** a contract change that relaxes freshness SLA (e.g., 4h to 8h), **When** version lacks MAJOR bump, **Then** a FLOE-E520 error identifies the SLA degradation as breaking.

4. **Given** only description changes, **When** version has PATCH bump, **Then** validation passes.

---

### User Story 5 - Schema Drift Detection (Priority: P2)

A platform engineer wants to detect when the actual Iceberg table schema differs from the contract definition. During compilation, the system compares the contract schema against the actual table schema and reports any drift.

**Why this priority**: Schema drift catches mismatches between declared contracts and actual data, preventing consumer surprises and data quality issues.

**Independent Test**: Can be fully tested by creating contracts with schemas that differ from actual table schemas (via mock or test Iceberg tables) and verifying drift is detected with specific field-level details.

**Acceptance Scenarios**:

1. **Given** a contract defining column `customer_id: string`, **When** actual table has `customer_id: int`, **Then** a FLOE-E530 schema drift warning identifies the type mismatch.

2. **Given** a contract defining required column `email`, **When** actual table is missing the column, **Then** a FLOE-E531 drift error identifies the missing column.

3. **Given** actual table has extra column not in contract, **When** drift detection runs, **Then** an informational warning notes the undocumented column (not an error).

4. **Given** drift detection configured as `enforcement: strict`, **When** any drift is detected, **Then** compilation fails with FLOE-E53x errors.

---

### User Story 6 - Contract Registration in Catalog (Priority: P2)

A platform engineer wants contracts registered in the Iceberg catalog alongside their data products. When compilation succeeds, the contract metadata is stored in the namespace properties for discoverability and governance.

**Why this priority**: Catalog registration enables contract discovery, version tracking, and audit trails. It connects contracts to the actual data they govern.

**Independent Test**: Can be fully tested by compiling a data product with a contract and verifying the contract metadata appears in catalog namespace properties.

**Acceptance Scenarios**:

1. **Given** a valid contract `customers:1.0.0`, **When** `floe compile` succeeds, **Then** catalog namespace `sales.customer_360` contains property `floe.contracts` listing the contract.

2. **Given** a contract registration, **When** the contract version is updated, **Then** the catalog property is updated with the new version.

3. **Given** catalog is unreachable, **When** registration fails, **Then** compilation continues with a warning (soft failure) and contract is still stored in CompiledArtifacts.

---

### Edge Cases

- **Missing datacontract.yaml and no ports**: Compilation fails with FLOE-E500 error - a data product must define either explicit contracts or output ports for contract generation.
- **Circular contract dependencies**: System detects and reports with clear cycle path (similar to model circular dependency detection).
- **Contract references undefined domain contract**: System reports missing parent contract with namespace path.
- **Very large contracts (100+ models)**: System handles efficiently with streaming parser (memory bounded).
- **ODCS version mismatch**: `datacontract-cli` validates apiVersion compatibility; floe surfaces any validation errors from the CLI with FLOE-E503 wrapper.
- **Schema drift when table doesn't exist yet**: System skips drift detection with info message (table will be created on first run).

---

## Requirements *(mandatory)*

### Functional Requirements

**Contract Parsing and Generation**

- **FR-001**: System MUST parse `datacontract.yaml` files conforming to ODCS v3.x specification
- **FR-002**: System MUST validate ODCS v3 schema requirements (apiVersion, kind, name, version, owner, models)
- **FR-003**: System MUST auto-generate contracts from `floe.yaml` output_ports when no explicit contract exists; contract name = `{data_product_name}-{port_name}`, version = data product version
- **FR-004**: System MUST merge explicit contracts with auto-generated (explicit values override generated)
- **FR-005**: System MUST validate element types match ODCS v3 type system (string, int, long, float, double, decimal, boolean, date, timestamp, bytes, array, object)

**Contract Schema Validation**

- **FR-006**: System MUST validate model schema completeness (all required elements have types)
- **FR-007**: System MUST validate SLA duration formats (ISO 8601 duration: PT6H, P1D, etc.)
- **FR-008**: System MUST validate classification values (public, internal, confidential, pii, phi, sensitive, restricted)
- **FR-009**: System MUST validate format constraints (email, uri, uuid, phone, date, date-time, ipv4, ipv6)
- **FR-010**: System MUST assign error codes FLOE-E500 (no contract or ports defined), FLOE-E501 (missing required field), FLOE-E502 (invalid format), FLOE-E503 (invalid type)

**Contract Inheritance**

- **FR-011**: System MUST support three-tier contract inheritance (enterprise -> domain -> product)
- **FR-012**: System MUST validate child contracts cannot weaken parent SLA properties (freshness, availability, quality)
- **FR-013**: System MUST validate child contracts cannot remove or weaken explicit field classifications defined in parent contracts
- **FR-014**: System MUST assign error code FLOE-E510 (SLA weakening)

**Contract Versioning**

- **FR-015**: System MUST retrieve baseline contract from catalog-registered version for comparison; first registration has no baseline (always valid)
- **FR-016**: System MUST detect breaking changes: remove element, change element type, make optional required, relax SLA
- **FR-017**: System MUST detect non-breaking changes: add optional element, make required optional, stricter SLA
- **FR-018**: System MUST detect patch changes: documentation, tags, links
- **FR-019**: System MUST enforce semantic versioning rules (breaking -> MAJOR, non-breaking -> MINOR, patch -> PATCH)
- **FR-020**: System MUST assign error code FLOE-E520 (version bump required)

**Schema Drift Detection**

- **FR-021**: System MUST compare contract schema against actual Iceberg table schema via IcebergTableManager
- **FR-022**: System MUST detect type mismatches between contract and actual schema
- **FR-023**: System MUST detect missing columns (in contract but not in table)
- **FR-024**: System MUST detect extra columns (in table but not in contract) as informational
- **FR-025**: System MUST assign error codes FLOE-E530 (type mismatch), FLOE-E531 (missing column), FLOE-E532 (extra column)

**Catalog Registration**

- **FR-026**: System MUST register contract metadata in Iceberg catalog namespace properties
- **FR-027**: System MUST store contract version, schema hash, owner, and registration timestamp
- **FR-028**: System MUST handle catalog unreachability gracefully (soft failure with warning)

**PolicyEnforcer Integration**

- **FR-029**: System MUST add ContractValidator to PolicyEnforcer's validator chain
- **FR-030**: ContractValidator MUST run AFTER semantic validator (depends on manifest parsing)
- **FR-031**: Contract violations MUST be included in EnforcementResult alongside existing violations
- **FR-032**: Contract validation MUST respect governance.data_contracts.enforcement level (off, warn, strict)

**CompiledArtifacts Extension**

- **FR-033**: System MUST extend CompiledArtifacts with `data_contracts: list[DataContract]` field
- **FR-034**: DataContract MUST include full ODCS schema plus validation metadata (schema_hash, validated_at)
- **FR-035**: ~~System MUST version CompiledArtifacts schema~~ N/A - project is pre-release; no version bump required

**Manifest Configuration**

- **FR-036**: System MUST support `data_contracts` section in manifest.yaml governance block
- **FR-037**: Configuration MUST include: enforcement level, auto_generation settings, drift_detection settings
- **FR-038**: Configuration MUST include: inheritance_mode

### Key Entities

- **DataContract**: Pydantic model representing ODCS v3 contract. Includes apiVersion, kind, name, version, status, owner, domain, description, models, slaProperties, terms, deprecation, tags, links.

- **DataContractModel**: Individual model within a contract. Includes name, description, elements (columns).

- **DataContractElement**: Column definition within a model. Includes name, type, required, primaryKey, unique, format, classification, enum, description.

- **SLAProperties**: SLA definitions. Includes freshness (duration + element), availability (percentage), quality (completeness, uniqueness, accuracy).

- **ContractValidationResult**: Result of contract validation. Includes valid (bool), violations (list), warnings (list), schema_hash, validated_at.

- **SchemaComparisonResult**: Result of schema drift detection. Includes matches (bool), type_mismatches, missing_columns, extra_columns.

- **DataContractsConfig**: Governance configuration for data contracts. Includes enforcement level, auto_generation, drift_detection, inheritance_mode.

- **ContractValidator**: Validator implementation for PolicyEnforcer. Validates contracts against ODCS, inheritance, versioning, and drift rules.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Data engineers can define contracts in `datacontract.yaml` and have them validated at compile time within 2 seconds for contracts with up to 50 models.

- **SC-002**: Contract validation produces actionable error messages with error code, expected/actual values, ODCS specification reference, and remediation suggestion.

- **SC-003**: Auto-generation creates valid ODCS v3 contracts from `floe.yaml` ports with 100% of required fields populated.

- **SC-004**: Three-tier inheritance correctly prevents weakening in 100% of test cases (enterprise -> domain -> product).

- **SC-005**: Semantic versioning rules are enforced with 100% accuracy for all change types (breaking, non-breaking, patch).

- **SC-006**: Schema drift detection identifies type mismatches and missing columns with field-level precision within 5 seconds for tables with up to 100 columns.

- **SC-007**: Contracts are registered in catalog namespace properties, enabling discovery via catalog API.


---

## Assumptions

1. Epic 3A (PolicyEnforcer) and Epic 3B (Policy Validation) are complete and stable.
2. Epic 4D (Storage Plugin) is **complete** - `IcebergTableManager` in `packages/floe-iceberg/` provides schema access.
3. Epic 4C (Catalog Plugin) provides CatalogPlugin for namespace property operations.
4. ODCS v3.x is the target specification (v3.0.2 current at time of writing).
5. `datacontract-cli` is a **hard dependency** for ODCS parsing, linting, and validation. This ensures full ODCS ecosystem compatibility and consistency with Epic 3D runtime features.
6. Runtime monitoring (freshness, availability SLA checks) is deferred to Epic 3D.
7. Schema drift detection requires table to exist; new tables skip drift check with info message.
8. Contract inheritance uses manifest hierarchy (same as policy inheritance from Epic 3A).
9. CompiledArtifacts schema change is MINOR version bump (additive, backward compatible).

---

## Clarifications

- Q: How should the system handle the `datacontract-cli` dependency for ODCS validation? A: Hard dependency - require `datacontract-cli` be installed. This ensures consistency with Epic 3D runtime features and full ODCS ecosystem compatibility.
- Q: For version bump validation, where should the system retrieve the PREVIOUS contract version to compare against? A: Catalog-registered version - compare against the contract currently registered in catalog namespace properties. First registration has no baseline (always valid).
- Q: When auto-generating contracts from floe.yaml ports, how should contract name and version be derived? A: Derive from data product metadata - contract name = `{data_product_name}-{port_name}`, version = data product version from floe.yaml.
- Q: Should floe implement custom linting rules (e.g., classification pattern enforcement)? A: No - all linting is delegated to `datacontract-cli`. Floe invokes datacontract-cli for ODCS validation and linting rather than reimplementing linting logic.

---

## Out of Scope

- **Runtime Contract Monitoring** - Freshness SLA enforcement, availability checks, quality threshold monitoring (Epic 3D)
- **Alerting** - OpenLineage FAIL events on contract violations (Epic 3D)
- **Prometheus Metrics** - `floe_contract_violations_total`, `floe_contract_freshness_hours` (Epic 3D)
- **Contract Deprecation Workflow** - ACTIVE -> DEPRECATED -> SUNSET -> RETIRED lifecycle (Epic 3D)
- **datacontract-cli Full Integration** - `floe contract test` command wrapping datacontract-cli (Epic 3D)
- **Contract Import/Export** - Converting from other contract formats to ODCS (future epic)
- **Contract Visualization** - Dashboard for contract status and drift trends (future epic)
