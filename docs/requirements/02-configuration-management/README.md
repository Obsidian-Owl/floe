# Domain 02: Configuration Management

**Priority**: CRITICAL
**Total Requirements**: 53
**Status**: Complete specification (Updated 2026-01-07)

## Overview

This domain defines the configuration management system that enables platform teams to define standards, enforce governance, and manage secrets across single-team and multi-team (Data Mesh) deployments.

**Core Architectural Principles**:
- Two-File Configuration Model (platform-manifest.yaml + floe.yaml)
- Unified Manifest Schema with Three-Tier Inheritance (Enterprise → Domain → Product)
- Compile-Time Enforcement of Platform Constraints
- Environment-Specific Configuration Management
- Secure Secrets Management with Infisical Integration

## Configuration System Components

| Component | Scope | Purpose | Requirements |
|-----------|-------|---------|--------------|
| **Unified Manifest** | 2-tier & 3-tier | Single schema supporting both startup and Data Mesh | REQ-100 to REQ-115 |
| **Platform Enforcement** | Governance | Enforce naming, quality gates, classifications | REQ-116 to REQ-130 |
| **Secrets Management** | Security | Credential management (Infisical, K8s Secrets, Vault) | REQ-131 to REQ-140 |
| **Compilation Workflow** | Execution | floe compile → validation → artifact generation | REQ-141 to REQ-150 |
| **Environment Handling** | Configuration | Runtime environment context resolution (dev/staging/prod) | REQ-151 to REQ-152 |

## Two-Tier vs Three-Tier Configuration

### Two-Tier (Single Platform, No Data Mesh)

```yaml
# platform-manifest.yaml (scope: None - default)
plugins:
  compute: duckdb
  observability: jaeger

# floe.yaml (data-product.yaml)
platform:
  ref: oci://registry/platform-manifest:v1.0.0
transforms:
  - type: dbt
```

**Use Case**: Startup, single-team enterprise

### Three-Tier (Data Mesh with Federated Governance)

```yaml
# enterprise-manifest.yaml (scope: enterprise)
scope: enterprise
approved_plugins:
  compute: ["duckdb", "snowflake"]
plugins:
  observability: datadog

# domain-manifest.yaml (scope: domain)
scope: domain
parent_manifest: oci://registry/enterprise-manifest:v1.0.0
plugins:
  compute: snowflake
approved_products: ["customer-360"]

# floe.yaml (data-product.yaml - SAME as 2-tier!)
platform:
  ref: oci://registry/domain-manifest:v2.0.0
```

**Use Case**: Enterprise with Data Mesh, federated autonomy

**Key Insight**: data-product.yaml is identical in both models. Scaling 2-tier → 3-tier requires zero changes to data team files.

## Three-Tier Inheritance Rules

| Field | Enterprise | Domain | Product | Mergeable |
|-------|-----------|--------|---------|-----------|
| `approved_plugins` | Define | Inherit | Inherit | No (immutable) |
| `plugins.observability` | Define | Inherit | Inherit | No (immutable) |
| `governance.pii_encryption` | Define | Inherit | Inherit | No (security) |
| `plugins.compute` | Whitelist | Select | Inherit | No (platform choice) |
| `governance.data_retention_days` | Default | Override | Inherit | Yes (domain-specific) |
| `approved_products` | N/A | Define | Inherit | No (domain controls) |

**Key Principles**:
- **Security policies**: Enterprise-defined, CANNOT be overridden
- **Plugin selection**: Domain selects from enterprise whitelist
- **Domain policies**: Domain-specific governance (retention, SLOs)
- **Product focus**: Products only define transforms, inherit everything

## Key Architectural Decisions

- **ADR-0038**: Data Mesh Architecture - Three-tier inheritance model
- **ADR-0037**: Composability Principle - Unified Manifest schema
- **ADR-0016**: Platform Enforcement Architecture - Compile-time validation
- **ADR-0031**: Infisical Secrets Management - Default OSS secrets plugin
- **ADR-0021**: Data Architecture Patterns - Naming conventions, classification
- **ADR-0026**: Data Contract Architecture - ODCS contract enforcement

## Requirements Files

- [01-unified-manifest-schema.md](01-unified-manifest-schema.md) - REQ-100 to REQ-115: Manifest schema, 2/3-tier support, inheritance
- [02-platform-enforcement.md](02-platform-enforcement.md) - REQ-116 to REQ-130: Validation, naming conventions, quality gates
- [03-secrets-management.md](03-secrets-management.md) - REQ-131 to REQ-140: Infisical, K8s Secrets, credential injection
- [04-compilation-workflow.md](04-compilation-workflow.md) - REQ-141 to REQ-150: floe compile, artifact generation, validation pipeline
- [05-environment-handling.md](05-environment-handling.md) - REQ-151 to REQ-152: Environment-agnostic compilation, runtime secret resolution

## Traceability Matrix

| Requirement Range | ADR | Architecture Doc | Test Spec |
|------------------|-----|------------------|-----------|
| REQ-100 to REQ-115 | ADR-0038, ADR-0037 | platform-enforcement.md, adr/0038 | tests/contract/test_manifest_schema.py |
| REQ-116 to REQ-130 | ADR-0016 | platform-enforcement.md | tests/contract/test_platform_enforcement.py |
| REQ-131 to REQ-140 | ADR-0031 | adr/0031-infisical-secrets.md | tests/contract/test_secrets_plugin.py |
| REQ-141 to REQ-150 | ADR-0037 | platform-enforcement.md | tests/contract/test_compilation_workflow.py |
| REQ-151 to REQ-152 | ADR-0039, ADR-0031 | adr/0039-multi-environment-promotion.md | tests/unit/test_environment_resolution.py |

## Epic Mapping (Refactoring Roadmap)

This domain's requirements are satisfied across multiple Epics:

- **Epic 2: Configuration Layer Modernization** - Unified Manifest schema, 2-tier/3-tier support
  - REQ-100 to REQ-115: Unified Manifest schema with scope field
  - REQ-141 to REQ-150: Compilation workflow updates

- **Epic 6: Platform Enforcement Engine** - Compile-time validation, policy enforcement
  - REQ-116 to REQ-130: PolicyEnforcer plugin, validation rules

- **Epic 5: Secrets Management & Security** - Infisical integration, credential management
  - REQ-131 to REQ-140: SecretsPlugin implementations

## Validation Criteria

Domain 02 is complete when:

- [ ] All 53 requirements documented with complete template fields
- [ ] Unified Manifest schema defined in Pydantic (scope field, inheritance)
- [ ] Three-tier inheritance resolution algorithm implemented
- [ ] Manifest loading from OCI registry (2-tier and 3-tier support)
- [ ] PolicyEnforcer interface and default implementations
- [ ] Infisical plugin implemented with InfisicalSecret CRD support
- [ ] K8s Secrets plugin as fallback
- [ ] `floe compile` workflow with validation pipeline
- [ ] Contract tests validate manifest inheritance
- [ ] Security tests validate policy immutability
- [ ] Backward compatibility with existing 2-tier configurations
- [ ] ADRs backreference requirements
- [ ] Architecture docs backreference requirements
- [ ] Test coverage > 80% for configuration management

## Notes

- **Backward Compatibility**: Existing 2-tier configurations (scope: None) continue to work unchanged
- **Breaking Changes**: NONE - Three-tier support is opt-in via scope field
- **Migration Path**: Organizations start 2-tier, add enterprise manifest to enable Data Mesh
- **Security First**: Immutable policy enforcement prevents weakening of security constraints
- **Standalone First**: All features work without SaaS Control Plane (Infisical can be self-hosted)
