# Feature Specification: Manifest Schema

**Feature Branch**: `001-manifest-schema`
**Created**: 2026-01-09
**Status**: Draft
**Input**: User description: "Define manifest.yaml schema with three-tier inheritance for platform configuration"

## Clarifications

### Session 2026-01-09

- Q: Should this feature support both 2-tier (scope=None) and 3-tier (scope=enterprise/domain) modes? → A: Both modes required - support scope=None (2-tier) and scope=enterprise/domain (3-tier) with automatic mode detection per REQ-100 and REQ-110.
- Q: How should environment differences be handled - configuration sections or runtime variables? → A: Runtime resolution via FLOE_ENV. No env_overrides in manifest. Secrets resolved per-environment at execution time per REQ-151 and ADR-0039.
- Q: Should the manifest schema enforce that child configurations cannot weaken parent security policies? → A: Yes, enforce immutability. Child manifests cannot weaken parent security policies (pii_encryption, audit_logging, policy_enforcement_level). Validation rejects attempts to weaken per REQ-103.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Platform Configuration Definition (Priority: P1)

A platform team member needs to define their organization's data platform configuration in a structured, validated file. They want to specify which technologies are approved (compute engines, orchestrators, catalogs) and set governance policies that all data engineers must follow. The schema supports both simple single-platform deployments (2-tier, scope=None) and enterprise Data Mesh configurations (3-tier, scope=enterprise/domain). The configuration file must catch errors early with clear messages.

**Why this priority**: Without a validated configuration schema, platform teams cannot standardize their data platform. This is the foundational capability that all other features depend on.

**Independent Test**: Can be fully tested by creating a configuration file and loading it - the system validates structure, required fields, and provides clear error messages. Delivers immediate value by catching configuration errors before deployment.

**Acceptance Scenarios**:

1. **Given** a valid configuration file with required fields, **When** loading the configuration, **Then** the system parses successfully and returns a structured configuration object
2. **Given** a configuration file with a missing required field, **When** loading the configuration, **Then** the system reports an error with the field name and file location
3. **Given** a configuration file with an invalid value (e.g., unknown plugin name), **When** loading the configuration, **Then** the system reports the invalid value and acceptable alternatives
4. **Given** a configuration file with an unknown field, **When** loading the configuration, **Then** the system issues a warning but continues (forward compatibility)

---

### User Story 2 - Configuration Inheritance (Priority: P1)

An enterprise architect manages platform standards across multiple domains and teams. In 3-tier mode (scope=enterprise or scope=domain), they define enterprise-wide configuration that domains can extend. Child configurations inherit parent values while being able to override specific settings. In 2-tier mode (scope=None), inheritance is not used and the manifest is self-contained.

**Why this priority**: Large organizations need hierarchical configuration to enforce standards while allowing flexibility. This enables the "opinionated by default, customizable when needed" philosophy. Smaller teams can start with 2-tier and migrate to 3-tier as they scale.

**Independent Test**: Can be fully tested by creating parent and child configuration files and verifying inheritance resolution. Delivers value by enabling enterprise-wide governance with domain-specific flexibility.

**Acceptance Scenarios**:

1. **Given** a configuration with scope=None (2-tier), **When** loading the configuration, **Then** no parent resolution occurs and the manifest is used standalone
2. **Given** a child configuration (scope=domain) that references a parent (scope=enterprise), **When** loading the child, **Then** the system resolves the parent and merges configurations with child values taking precedence
3. **Given** a parent with a list of approved plugins and a child that adds to the list, **When** loading the child, **Then** the lists are merged by default
4. **Given** a child that needs to completely replace a parent's list, **When** loading the child with an override marker, **Then** the parent's list is replaced entirely
5. **Given** configuration A extends B which extends C, **When** loading A, **Then** all three levels merge correctly with A taking highest precedence
6. **Given** configuration A extends B and B extends A (circular), **When** loading either, **Then** the system rejects with a clear circular dependency error
7. **Given** an enterprise manifest with pii_encryption=required, **When** a domain manifest attempts to set pii_encryption=optional, **Then** the system rejects with "Cannot weaken security policy" error
8. **Given** an enterprise manifest with audit_logging=enabled, **When** a domain manifest attempts to set audit_logging=disabled, **Then** the system rejects the configuration
9. **Given** an enterprise manifest with policy_enforcement_level=strict, **When** a domain manifest sets policy_enforcement_level=strict (same level), **Then** the configuration is accepted

---

### User Story 3 - Plugin Selection (Priority: P1)

A platform team member wants to specify which approved technologies power each layer of the data platform. They need to select a compute engine (e.g., DuckDB, Snowflake), an orchestrator (e.g., Dagster), a catalog (e.g., Polaris), and other pluggable components. Each plugin may have its own configuration options.

**Why this priority**: Plugin selection is how platform teams make the "opinionated" choices. Without this, the platform cannot be configured for any specific technology stack.

**Independent Test**: Can be fully tested by defining plugin selections and verifying they resolve to known plugin types. Delivers value by enabling technology standardization.

**Acceptance Scenarios**:

1. **Given** a configuration with valid plugin selections, **When** loading the configuration, **Then** each plugin selection is validated against known plugin types
2. **Given** a plugin selection for an unknown plugin, **When** loading the configuration, **Then** the system reports which plugins are available for that category
3. **Given** a plugin that requires configuration options, **When** the configuration includes plugin-specific settings, **Then** those settings are associated with the correct plugin
4. **Given** a required plugin category without a selection, **When** loading the configuration, **Then** the system reports which plugins must be specified

---

### User Story 4 - IDE Autocomplete Support (Priority: P2)

A data engineer writing or editing configuration files wants real-time autocomplete suggestions and validation in their code editor. This helps them discover available options and avoid typos without consulting documentation.

**Why this priority**: Developer experience improvement that accelerates configuration authoring. Not strictly required for the platform to function but significantly improves usability.

**Independent Test**: Can be fully tested by generating a schema file and verifying editors recognize it for autocomplete. Delivers value by reducing configuration errors and speeding up authoring.

**Acceptance Scenarios**:

1. **Given** the platform tooling, **When** generating a configuration schema file, **Then** the output is a valid schema that editors can consume
2. **Given** a schema file and a supported editor, **When** editing a configuration file, **Then** the editor provides field suggestions
3. **Given** a configuration file with schema reference, **When** entering an invalid value, **Then** the editor highlights the error before saving

---

### User Story 5 - Secret Reference Handling (Priority: P2)

A platform team member needs to reference secrets (database passwords, API keys, service credentials) in configuration without exposing the actual values. Secrets should be referenced by name and resolved at deployment time from secure sources.

**Why this priority**: Security requirement - secrets must never be stored in configuration files. Essential for production deployments but can use placeholder values during initial development.

**Independent Test**: Can be fully tested by defining secret references and verifying they remain as placeholders until explicitly resolved. Delivers value by enabling secure configuration.

**Acceptance Scenarios**:

1. **Given** a configuration with secret reference placeholders, **When** loading the configuration, **Then** secret references remain as placeholders (not resolved)
2. **Given** a secret reference with a specific name, **When** validating the configuration, **Then** the system validates the reference format without attempting to resolve the secret
3. **Given** a configuration used in deployment, **When** secrets are resolved, **Then** the system looks up secrets from configured secure sources

---

### User Story 6 - Environment-Agnostic Configuration (Priority: P2)

A platform team member needs configuration that works identically across all environments (development, staging, production). The manifest is environment-agnostic - the same compiled artifact promotes across environments without recompilation. Environment-specific behavior (credentials, endpoints) is determined at runtime via the FLOE_ENV environment variable.

**Why this priority**: Enables immutable artifact promotion and prevents environment drift. Essential for reliable CI/CD pipelines where the same artifact is tested in staging then deployed to production.

**Independent Test**: Can be fully tested by compiling a configuration once and verifying the same artifact works when FLOE_ENV is set to different values. Delivers value by enabling "compile once, deploy everywhere."

**Acceptance Scenarios**:

1. **Given** a manifest without environment-specific sections, **When** compiling the configuration, **Then** the output artifact is identical regardless of target environment
2. **Given** a compiled artifact and FLOE_ENV=dev, **When** executing a pipeline, **Then** credentials are resolved from the dev environment in the secrets backend
3. **Given** a compiled artifact and FLOE_ENV=production, **When** executing the same pipeline, **Then** credentials are resolved from the production environment in the secrets backend
4. **Given** FLOE_ENV set to an invalid value, **When** executing a pipeline, **Then** the system reports valid environment options (dev, staging, production)

---

### Edge Cases

- What happens when a configuration file has syntax errors (not schema errors)?
- How does the system handle extremely deep inheritance chains (more than 5 levels)?
- What happens when a parent configuration file is deleted but children still reference it?
- How does the system behave with very large configuration files (thousands of lines)?
- What happens when two sibling configurations inherit from the same parent but define conflicting values?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load configuration from YAML files and validate against the defined schema
- **FR-002**: System MUST provide validation error messages that include the field path and location in the file
- **FR-016**: System MUST support both 2-tier (scope=None) and 3-tier (scope=enterprise/domain) modes with automatic detection based on scope field value
- **FR-003**: System MUST support configuration inheritance where child configurations extend parent configurations (3-tier mode only)
- **FR-004**: System MUST resolve inheritance by merging parent and child values with child taking precedence
- **FR-005**: System MUST detect and reject circular inheritance dependencies
- **FR-006**: System MUST support plugin selection for all pluggable platform components (compute, orchestrator, catalog, semantic layer, ingestion)
- **FR-007**: System MUST validate plugin selections against the plugin registry
- **FR-008**: System MUST support plugin-specific configuration nested under each plugin selection
- **FR-009**: System MUST export configuration schema in a format consumable by IDEs for autocomplete
- **FR-010**: System MUST support secret reference placeholders that are validated but not resolved at configuration time
- **FR-011**: System MUST produce environment-agnostic compiled artifacts; environment context (FLOE_ENV) is resolved at runtime, not compilation time
- **FR-012**: System MUST issue warnings (not errors) for unknown fields to support forward compatibility
- **FR-013**: System MUST enforce required fields and reject configurations missing them
- **FR-014**: System MUST support array merging in inheritance with an option to replace rather than merge
- **FR-015**: System MUST validate cross-field dependencies (e.g., if feature X enabled, then setting Y required)
- **FR-017**: System MUST enforce security policy immutability in 3-tier mode: child manifests cannot weaken parent security policies (pii_encryption, audit_logging, policy_enforcement_level); children may only strengthen or maintain parent levels
- **FR-018**: System MUST validate that domain plugin selections are within enterprise approved_plugins whitelist (3-tier mode)

### Key Entities

- **PlatformManifest**: The top-level configuration representing an organization's platform settings. Contains scope field (None for 2-tier, "enterprise" or "domain" for 3-tier), plugin selections, governance policies, metadata (apiVersion, kind, name, version, owner), and optional parent_manifest reference.
- **PluginSelection**: A choice of specific plugin for a platform capability (e.g., compute: duckdb). Includes the plugin identifier and plugin-specific configuration.
- **SecretReference**: A placeholder for sensitive values that references a secret by name. Contains the secret source (environment variable, secrets manager) and key name.
- **GovernanceConfig**: Security and compliance settings including pii_encryption (required/optional), audit_logging (enabled/disabled), policy_enforcement_level (off/warn/strict), and data_retention_days. Security fields are immutable in inheritance - children cannot weaken parent policies.
- **InheritanceChain**: The resolved lineage of configurations from enterprise to domain to product level (3-tier mode only). Tracks which configuration provided each value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform teams can define complete platform configuration in under 30 minutes using documentation and IDE autocomplete
- **SC-002**: Configuration validation errors are resolved by users on first attempt in 80% of cases (clear error messages)
- **SC-003**: Inheritance chains of up to 5 levels resolve correctly and load within 2 seconds
- **SC-004**: 100% of configuration errors are caught at validation time (no runtime surprises from invalid configuration)
- **SC-005**: IDE autocomplete covers all configuration fields and provides valid option suggestions
- **SC-006**: Configuration changes at enterprise level propagate correctly to all child configurations without manual updates
