# REQ-221 to REQ-240: Data Contracts and Lifecycle Management

**Domain**: Data Governance
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the data contract model, ODCS v3 adoption (enforced standard), contract lifecycle management, and the DataContract **core module** that enables computational governance between data producers and consumers.

> **Note:** DataContract is now a **core module** in floe-core, not a plugin. ODCS v3 is the enforced standard, with validation handled by built-in functionality wrapping `datacontract-cli`.

**Key Principle**: Contracts as computational agreements (ADR-0026, ADR-0027, ADR-0028, ADR-0029)

## Requirements

### REQ-221: DataContract Core Module Definition **[Updated]**

**Requirement**: System MUST define DataContract module with methods for contract validation and monitoring.

**Rationale**: ODCS v3 is the enforced standard - DataContract is a core module, not a plugin.

**Acceptance Criteria**:
- [ ] DataContract module defined in floe-core
- [ ] Methods: parse_contract, generate_contract_from_ports, validate_contract, detect_schema_drift, validate_version_bump, check_freshness, check_availability
- [ ] DataContract is a core module (not pluggable)
- [ ] ODCS v3 format enforced via datacontract-cli wrapper
- [ ] Default ODCS implementation provided

**Enforcement**:
- Unit tests verify DataContractPlugin interface
- Contract tests validate plugin compliance
- Architectural tests enforce abstraction

**Constraints**:
- MUST be abstract base class (ABC)
- MUST define all contract management methods
- MUST NOT hardcode contract format in interface
- FORBIDDEN to make contract implementation optional

**Test Coverage**: `tests/contract/test_data_contract_plugin.py`

**Traceability**:
- data-contracts.md lines 247-276
- ADR-0026 (Data Contract Architecture)
- ADR-0027 (ODCS Standard Adoption)

**Files to Create**:
- `floe-core/src/floe_core/plugin_interfaces.py` - Add DataContractPlugin ABC

---

### REQ-222: ODCS v3 Schema Validation **[New]**

**Requirement**: DataContractPlugin MUST validate contract schemas against ODCS v3 specification.

**Rationale**: Ensures contracts are valid and complete.

**Acceptance Criteria**:
- [ ] validate_contract() validates ODCS v3 schema
- [ ] Validates required fields: name, version, models, slaProperties
- [ ] Validates model structure: elements (columns), types, constraints
- [ ] Validates SLA properties: freshness (ISO 8601), availability (%)
- [ ] Reports schema violations with line numbers

**Enforcement**:
- ODCS v3 schema validation tests
- Required field tests
- SLA format validation tests

**Constraints**:
- MUST use ODCS v3 standard (not v2)
- MUST validate all required fields
- FORBIDDEN to accept incomplete contracts
- MUST support additionalProperties for extensibility

**Test Coverage**: `tests/unit/test_odcs_schema_validation.py`

**Traceability**:
- data-contracts.md lines 146-206
- ADR-0027 (ODCS Standard Adoption)

---

### REQ-223: Auto-Generated Contracts from Ports **[New]**

**Requirement**: DataContractPlugin MUST generate contracts automatically from data product input/output ports.

**Rationale**: Reduces manual contract authoring while ensuring consistency.

**Acceptance Criteria**:
- [ ] generate_contract_from_ports() creates ODCS contract from ports
- [ ] Extracts schema from output port definitions
- [ ] Merges metadata from product YAML and dbt manifest
- [ ] Generates default SLAs from platform policies
- [ ] Contract suitable for human review and editing

**Enforcement**:
- Auto-generation tests
- Schema extraction tests
- Port definition tests

**Constraints**:
- MUST generate valid ODCS contracts
- MUST NOT require manual schema entry
- FORBIDDEN to fail if port metadata incomplete
- MUST support manual refinement after auto-generation

**Test Coverage**: `tests/unit/test_contract_generation.py`

**Traceability**:
- data-contracts.md lines 54-78

**Files to Create**:
- `floe-core/src/floe_core/contracts/contract_generator.py`

---

### REQ-224: Contract-to-dbt Enrichment **[New]**

**Requirement**: Contract generation MUST enrich auto-generated contracts with dbt manifest metadata.

**Rationale**: dbt manifest contains type information and test metadata.

**Acceptance Criteria**:
- [ ] generate_contract_from_ports() reads dbt manifest.json
- [ ] Extracts column types from dbt models
- [ ] Extracts test definitions and applies to contract elements
- [ ] Extracts classifications from dbt meta.floe tags
- [ ] Auto-generates freshness SLA from dbt source freshness checks

**Enforcement**:
- dbt manifest parsing tests
- Metadata extraction tests
- Type mapping tests

**Constraints**:
- MUST read dbt manifest (required for compilation)
- MUST NOT require duplicate metadata entry
- FORBIDDEN to use stale manifest data
- MUST validate manifest version compatibility

**Test Coverage**: `tests/integration/test_dbt_enrichment.py`

**Traceability**:
- ADR-0009 (dbt Owns SQL)

---

### REQ-225: Contract Merging: Generated + Explicit **[New]**

**Requirement**: System MUST merge auto-generated contracts with explicit datacontract.yaml definitions (explicit overrides generated).

**Rationale**: Allows teams to provide additional contract constraints beyond auto-generation.

**Acceptance Criteria**:
- [ ] merge_contracts() combines generated and explicit contracts
- [ ] Explicit contract overrides generated contract fields
- [ ] Merge strategy: generated as base, explicit as overrides
- [ ] Validates merged contract matches ODCS v3
- [ ] Reports conflicts with resolution guidance

**Enforcement**:
- Contract merging tests
- Override behavior tests
- Conflict detection tests

**Constraints**:
- MUST use merge strategy: explicit overrides generated
- MUST NOT lose data during merge
- FORBIDDEN to allow weakening of inherited SLAs
- MUST validate merged contract

**Test Coverage**: `tests/unit/test_contract_merging.py`

**Traceability**:
- data-contracts.md lines 54-78

---

### REQ-226: Contract Identity and Versioning **[New]**

**Requirement**: Contracts MUST have unique identities and use semantic versioning.

**Rationale**: Enables independent contract evolution and tracking.

**Acceptance Criteria**:
- [ ] Contract ID format: {domain}.{product}/{contract}:{version}
- [ ] Example: "sales.customer_360/customers:1.0.0"
- [ ] Version follows semver: MAJOR.MINOR.PATCH
- [ ] MAJOR bump for breaking changes (removed columns, type changes)
- [ ] MINOR bump for additive changes (new optional columns)
- [ ] PATCH bump for documentation only
- [ ] Contract registered in catalog with schema hash

**Enforcement**:
- Contract ID validation tests
- Semantic versioning tests
- Schema hash tests

**Constraints**:
- MUST use semver versioning
- MUST prevent version downgrades
- FORBIDDEN to reuse version numbers
- MUST track schema hash for immutability

**Test Coverage**: `tests/unit/test_contract_versioning.py`

**Traceability**:
- data-contracts.md lines 80-144
- ADR-0029 (Contract Lifecycle Management)
- ADR-0030 (Namespace-Based Identity)

---

### REQ-227: Contract Registration in Catalog **[New]**

**Requirement**: Contracts MUST be registered in Iceberg catalog with namespace properties.

**Rationale**: Enables contract discovery and tracking at runtime.

**Acceptance Criteria**:
- [ ] CatalogPlugin.register_contract() stores contract metadata
- [ ] Catalog namespace properties: floe.contracts (JSON array)
- [ ] Contract properties include: name, version, owner, registered_at
- [ ] Multiple contracts per product supported
- [ ] Contract lookup by contract ID

**Enforcement**:
- Contract registration tests
- Catalog property tests
- Multi-contract tests

**Constraints**:
- MUST register all contracts
- MUST update namespace properties atomically
- FORBIDDEN to lose contract history
- MUST make contracts discoverable

**Test Coverage**: `tests/integration/test_contract_registration.py`

**Traceability**:
- data-contracts.md lines 101-134
- ADR-0030 (Namespace-Based Identity)

---

### REQ-228: Breaking Change Detection **[New]**

**Requirement**: DataContractPlugin MUST detect breaking changes when contract versions bump.

**Rationale**: Prevents silent schema evolution that breaks downstream consumers.

**Acceptance Criteria**:
- [ ] validate_version_bump() detects breaking changes
- [ ] Removes required column → MAJOR bump required
- [ ] Changes column type → MAJOR bump required
- [ ] Adds required column → MAJOR bump required
- [ ] Relaxes SLA (freshness increases) → MAJOR bump required
- [ ] Adds optional column → MINOR bump allowed
- [ ] Tightens SLA (freshness decreases) → MINOR bump allowed
- [ ] Documentation changes → PATCH bump allowed

**Enforcement**:
- Breaking change detection tests
- Version bump validation tests
- Regression prevention tests

**Constraints**:
- MUST detect all breaking changes
- MUST enforce version bump rules
- FORBIDDEN to allow breaking changes without MAJOR bump
- MUST prevent version downgrades

**Test Coverage**: `tests/unit/test_breaking_changes.py`

**Traceability**:
- data-contracts.md lines 295-309
- ADR-0029 (Contract Lifecycle Management)

---

### REQ-229: Contract Schema Drift Detection **[New]**

**Requirement**: DataContractPlugin MUST detect runtime schema drift when actual table schema differs from contract.

**Rationale**: Identifies unplanned schema evolution.

**Acceptance Criteria**:
- [ ] detect_schema_drift() compares contract schema with actual table schema
- [ ] Reports added columns not in contract
- [ ] Reports removed columns in contract
- [ ] Reports type mismatches
- [ ] Reports constraint violations (nullability, uniqueness)
- [ ] Compare operations available per compute target

**Enforcement**:
- Schema drift detection tests
- Compute-specific comparison tests
- Actual schema extraction tests

**Constraints**:
- MUST detect all schema changes
- MUST compare against actual table schema
- FORBIDDEN to accept silent schema changes
- MUST support different compute targets

**Test Coverage**: `tests/integration/test_schema_drift.py`

**Traceability**:
- data-contracts.md lines 263-267
- ADR-0028 (Runtime Contract Monitoring)

---

### REQ-230: Contract Inheritance Rules **[New]**

**Requirement**: Contracts MUST follow three-tier inheritance model (enterprise → domain → product).

**Rationale**: Enables federated governance with policy cascading.

**Acceptance Criteria**:
- [ ] Enterprise contract defines base SLAs, required fields, classification
- [ ] Domain contract inherits from enterprise, can strengthen only
- [ ] Product contract inherits from domain, can strengthen only
- [ ] PolicyEnforcer detects weakening attempts and blocks
- [ ] Clear error messages when inheritance rules violated

**Enforcement**:
- Contract inheritance tests
- Weakening prevention tests
- Three-tier validation tests

**Constraints**:
- MUST prevent weakening of inherited SLAs
- MUST allow strengthening (reduce freshness, add required fields)
- FORBIDDEN to override parent contract fields
- MUST track inheritance chain

**Test Coverage**: `tests/unit/test_contract_inheritance.py`

**Traceability**:
- data-contracts.md lines 330-354
- ADR-0026 (Data Contract Architecture)

---

### REQ-231: Contract Publication to Catalog **[New]**

**Requirement**: Compiled contracts MUST be published to OCI registry alongside platform artifacts.

**Rationale**: Enables contract discovery and external tooling integration.

**Acceptance Criteria**:
- [ ] Contracts included in CompiledArtifacts
- [ ] Contracts publishable to OCI registry via floe platform publish
- [ ] Contract versions tracked in OCI artifact tags
- [ ] Immutable contract storage in registry
- [ ] Contract digest (content hash) included in artifact manifest

**Enforcement**:
- OCI publication tests
- Immutability verification tests
- Contract versioning tests

**Constraints**:
- MUST publish all contracts
- MUST use semantic versioning for OCI tags
- FORBIDDEN to allow contract mutation after publication
- MUST include contract digest in manifest

**Test Coverage**: `tests/integration/test_contract_publication.py`

**Traceability**:
- oci-registry-requirements.md
- ADR-0026 (Data Contract Architecture)

---

### REQ-232: Contract Compliance Validation **[New]**

**Requirement**: PolicyEnforcer MUST validate all contracts during compile-time.

**Rationale**: Early detection of contract issues.

**Acceptance Criteria**:
- [ ] PolicyEnforcer calls validate_data_contracts() during floe compile
- [ ] Validates contract ODCS schema
- [ ] Validates inheritance constraints
- [ ] Validates version bumps
- [ ] Validates classification compliance
- [ ] Compilation fails if contract validation fails (strict mode)

**Enforcement**:
- Contract validation tests
- Compile-time enforcement tests
- Strict mode tests

**Constraints**:
- MUST validate all contracts during compile
- MUST fail compilation in strict mode
- FORBIDDEN to suppress validation errors
- MUST provide clear error messages

**Test Coverage**: `tests/integration/test_contract_compile_validation.py`

**Traceability**:
- REQ-202 (Compile-Time Policy Validation Hook)
- ADR-0028 (Runtime Contract Monitoring)

---

### REQ-233: Contract Deprecation Workflow **[New]**

**Requirement**: Contracts MUST support deprecation with timeline and migration guidance.

**Rationale**: Enables smooth contract evolution without breaking downstream consumers.

**Acceptance Criteria**:
- [ ] Contract status field: active, deprecated, sunset, retired
- [ ] Deprecation includes: announced_date, sunset_date, replacement, migration_guide
- [ ] DEPRECATED: Warnings emitted for 30 days
- [ ] SUNSET: Errors emitted for 7 days
- [ ] RETIRED: Contract removed, no longer available
- [ ] Consumers notified of deprecation via OpenLineage

**Enforcement**:
- Deprecation workflow tests
- Timeline enforcement tests
- Migration guidance tests

**Constraints**:
- MUST enforce deprecation timeline
- MUST provide migration path
- FORBIDDEN to retire contracts without warning
- MUST track replacement contract

**Test Coverage**: `tests/unit/test_contract_deprecation.py`

**Traceability**:
- data-contracts.md lines 310-329
- ADR-0029 (Contract Lifecycle Management)

---

### REQ-234: Contract Owner Management **[New]**

**Requirement**: Contracts MUST specify owner and support owner change workflows.

**Rationale**: Enables governance responsibility tracking.

**Acceptance Criteria**:
- [ ] Contract owner field: email or team identifier
- [ ] Owner required for all contracts
- [ ] Owner contacts notified of violations
- [ ] Owner approval required for breaking changes
- [ ] Owner specified in ODCS contract definition

**Enforcement**:
- Owner validation tests
- Notification tests
- Approval workflow tests

**Constraints**:
- MUST require contract owner
- MUST support owner contact notifications
- FORBIDDEN to allow contracts without ownership
- MUST track owner changes in audit trail

**Test Coverage**: `tests/unit/test_contract_ownership.py`

**Traceability**:
- ADR-0029 (Contract Lifecycle Management)

---

### REQ-235: Contract Classification Compliance **[New]**

**Requirement**: Contracts MUST validate that classified columns match platform classification policies.

**Rationale**: Ensures consistent classification across contract definitions and dbt models.

**Acceptance Criteria**:
- [ ] Contract element classification must match dbt model classification
- [ ] PII elements must have proper classification
- [ ] PHI elements must have proper classification
- [ ] Financial elements must have proper classification
- [ ] Violations reported with remediation (add missing classification)

**Enforcement**:
- Classification compliance tests
- dbt + contract alignment tests
- Policy enforcement tests

**Constraints**:
- MUST validate classification in contracts
- MUST match dbt classifications
- FORBIDDEN to allow unclassified PII
- MUST support custom classifications

**Test Coverage**: `tests/unit/test_contract_classification.py`

**Traceability**:
- REQ-203 (Classification Metadata Validation)
- ADR-0012 (Data Classification)

---

### REQ-236: Contract Tagging and Discovery **[New]**

**Requirement**: Contracts MUST support tags for discovery and filtering.

**Rationale**: Enables contract queries by domain, layer, sensitivity, etc.

**Acceptance Criteria**:
- [ ] ODCS tags field supported (array of strings)
- [ ] Common tags: customer-data, product-data, gold-layer, pii-handling
- [ ] Query contracts by tag (DataContractPlugin.find_contracts_by_tag)
- [ ] Tag validation against allowed values (optional)
- [ ] Tag metadata included in catalog registration

**Enforcement**:
- Tag validation tests
- Discovery tests
- Tag query tests

**Constraints**:
- MUST support arbitrary tags
- MUST include tags in catalog
- FORBIDDEN to require tags (optional)
- MUST support tag-based discovery

**Test Coverage**: `tests/unit/test_contract_tagging.py`

**Traceability**:
- data-contracts.md lines 157-206
- ADR-0026 (Data Contract Architecture)

---

### REQ-237: Contract Usage Statistics **[New]**

**Requirement**: System MUST track contract usage (how many downstream consumers, how often accessed).

**Rationale**: Enables impact analysis for contract changes.

**Acceptance Criteria**:
- [ ] Track contract access in OpenLineage lineage events
- [ ] Count downstream lineage to identify consumers
- [ ] Calculate last_accessed timestamp
- [ ] Include usage statistics in catalog metadata
- [ ] Support query: "which products consume this contract?"

**Enforcement**:
- Usage tracking tests
- Lineage integration tests
- Consumer discovery tests

**Constraints**:
- MUST track usage via OpenLineage
- MUST identify all consumers
- FORBIDDEN to lose usage history
- MUST support impact analysis queries

**Test Coverage**: `tests/integration/test_contract_usage.py`

**Traceability**:
- ADR-0007 (OpenLineage from Start)

---

### REQ-238: Explicit Contract Files (datacontract.yaml) **[New]**

**Requirement**: Data products MAY provide explicit datacontract.yaml alongside data-product.yaml.

**Rationale**: Allows teams to define detailed contracts beyond auto-generation.

**Acceptance Criteria**:
- [ ] datacontract.yaml parsed alongside data-product.yaml
- [ ] File location: same directory as data-product.yaml
- [ ] Explicit contract overrides generated contract
- [ ] Merging applies: generated base, explicit overrides
- [ ] Validation ensures merged contract is valid ODCS v3

**Enforcement**:
- Contract file discovery tests
- Merging logic tests
- Validation tests

**Constraints**:
- MUST support explicit contracts
- FORBIDDEN to require them (auto-generation should suffice)
- MUST validate explicit contracts
- MUST merge correctly with generated contracts

**Test Coverage**: `tests/unit/test_explicit_contracts.py`

**Traceability**:
- data-contracts.md lines 43-52

---

### REQ-239: Contract Documentation **[New]**

**Requirement**: Contracts MUST support documentation fields for human-readable description.

**Rationale**: Enables contract understanding without reading schema.

**Acceptance Criteria**:
- [ ] ODCS description field for contract-level documentation
- [ ] ODCS description field per model
- [ ] Description field per element (column)
- [ ] Descriptions required for gold-layer contracts
- [ ] Descriptions included in catalog display

**Enforcement**:
- Documentation presence tests
- Documentation quality tests (not empty, not "TODO")
- Layer-specific enforcement tests

**Constraints**:
- MUST support documentation fields
- MUST NOT allow empty descriptions
- FORBIDDEN to require for all contracts (optional by default)
- MUST display documentation in catalog

**Test Coverage**: `tests/unit/test_contract_documentation.py`

**Traceability**:
- data-contracts.md lines 157-206

---

### REQ-240: Contract Metrics and Statistics **[New]**

**Requirement**: System MUST compute and expose contract metrics (compliance score, coverage, etc.).

**Rationale**: Enables governance dashboard and reporting.

**Acceptance Criteria**:
- [ ] Contract compliance score: % of SLAs met
- [ ] Contract coverage: % of columns with descriptions
- [ ] Contract freshness: age of last published version
- [ ] Violation trend: % of violations over time
- [ ] Metrics exported as Prometheus metrics
- [ ] Metrics queryable via API

**Enforcement**:
- Metric computation tests
- Prometheus export tests
- API query tests

**Constraints**:
- MUST compute metrics accurately
- MUST track metrics over time
- FORBIDDEN to expose sensitive data in metrics
- MUST support dashboarding

**Test Coverage**: `tests/integration/test_contract_metrics.py`

**Traceability**:
- ADR-0006 (OpenTelemetry Observability)

---

## Domain Acceptance Criteria

Data Contracts and Lifecycle Management (REQ-221 to REQ-240) is complete when:

- [ ] All 20 requirements have complete template fields
- [ ] DataContractPlugin ABC defined and documented
- [ ] All 8 contract management methods implemented
- [ ] ODCS v3 parsing and validation working
- [ ] Auto-contract generation from ports working
- [ ] Contract merging (generated + explicit) working
- [ ] Contract registration in catalog working
- [ ] Contract inheritance validation working
- [ ] Schema drift detection working
- [ ] Breaking change detection working
- [ ] Contract deprecation workflow working
- [ ] Unit tests pass with >80% coverage
- [ ] Integration tests validate contract workflows
- [ ] Contract tests validate plugin boundaries
- [ ] Documentation updated:
  - [ ] data-contracts.md backreferences requirements
  - [ ] ADR-0026 backreferences requirements
  - [ ] ADR-0027 backreferences requirements
  - [ ] ADR-0028 backreferences requirements
  - [ ] ADR-0029 backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 7: Contract Monitoring**:
- Phase 1: Implement DataContractPlugin interface
- Phase 2: ODCS v3 adoption and parsing
- Phase 3: Contract auto-generation and merging
- Phase 4: Runtime contract monitoring (ContractMonitor service)
- Phase 5: Contract lifecycle management (deprecation, versioning)
