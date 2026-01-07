# Epic 4C: Catalog Plugin

## Summary

The CatalogPlugin ABC defines the interface for metadata catalog management. The reference implementation uses Apache Polaris for Iceberg REST catalog, with adapter interfaces for AWS Glue and Hive Metastore.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-04c-catalog-plugin](https://linear.app/obsidianowl/project/floe-04c-catalog-plugin-6cda94e2eb31)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-031 | CatalogPlugin ABC definition | CRITICAL |
| REQ-032 | Polaris reference implementation | CRITICAL |
| REQ-033 | Namespace management | HIGH |
| REQ-034 | Table registration | CRITICAL |
| REQ-035 | AWS Glue adapter interface | MEDIUM |
| REQ-036 | Hive Metastore adapter interface | LOW |
| REQ-037 | Catalog synchronization | HIGH |
| REQ-038 | Access control integration | HIGH |
| REQ-039 | Schema versioning | HIGH |
| REQ-040 | Catalog health monitoring | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0001](../../../architecture/adr/0001-plugin-architecture.md) - Plugin architecture
- [ADR-0006](../../../architecture/adr/0006-catalog-abstraction.md) - Catalog abstraction

### Interface Docs
- [plugin-interfaces.md](../../../architecture/plugin-system/plugin-interfaces.md) - Plugin interface definitions

### Contracts
- `CatalogPlugin` - Catalog management ABC
- `NamespaceConfig` - Namespace configuration model
- `TableRegistration` - Table registration model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── plugin_interfaces.py         # CatalogPlugin ABC (shared)
└── plugins/
    └── catalog/
        └── __init__.py

plugins/floe-catalog-polaris/
├── src/floe_catalog_polaris/
│   ├── __init__.py
│   ├── plugin.py                # PolarisCatalogPlugin
│   ├── client.py                # Polaris REST client
│   ├── namespace.py             # Namespace management
│   └── config.py                # Polaris config
└── tests/
    ├── unit/
    └── integration/
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocks | Epic 4D | Storage plugin uses catalog |
| Blocks | Epic 5A | dbt needs catalog for table resolution |
| Blocks | Epic 7A | Access control via catalog |

---

## User Stories (for SpecKit)

### US1: CatalogPlugin ABC (P0)
**As a** plugin developer
**I want** a clear ABC for catalog plugins
**So that** I can implement adapters for new catalogs

**Acceptance Criteria**:
- [ ] `CatalogPlugin.create_namespace(name)` defined
- [ ] `CatalogPlugin.register_table(namespace, table)` defined
- [ ] `CatalogPlugin.list_tables(namespace)` defined
- [ ] Configuration via Pydantic models

### US2: Polaris Reference Implementation (P0)
**As a** platform operator
**I want** Polaris as the default catalog
**So that** I get Iceberg REST catalog with access control

**Acceptance Criteria**:
- [ ] `PolarisCatalogPlugin` implements ABC
- [ ] REST API client for Polaris
- [ ] OAuth2 authentication support
- [ ] Namespace hierarchy management

### US3: Namespace Management (P1)
**As a** platform operator
**I want** namespaces created automatically
**So that** table organization matches our structure

**Acceptance Criteria**:
- [ ] Namespace from floe.yaml configuration
- [ ] Hierarchical namespaces (domain.product.layer)
- [ ] Namespace properties (location, owner)
- [ ] Namespace cleanup on product removal

### US4: Access Control Integration (P1)
**As a** security engineer
**I want** catalog access controlled by roles
**So that** data access is governed

**Acceptance Criteria**:
- [ ] Principal management via plugin
- [ ] Role assignment via plugin
- [ ] Privilege grants via plugin
- [ ] Integration with external identity (Epic 7A)

---

## Technical Notes

### Key Decisions
- Polaris is the default (open-source, Iceberg-native)
- Catalog is the source of truth for table metadata
- PyIceberg is used for catalog client operations
- Access control is optional (not all catalogs support it)

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Polaris availability | MEDIUM | HIGH | Retry logic, health checks |
| Catalog state drift | MEDIUM | HIGH | Reconciliation jobs |
| Access control complexity | MEDIUM | MEDIUM | Clear permission model |

### Test Strategy
- **Unit**: `plugins/floe-catalog-polaris/tests/unit/test_plugin.py`
- **Integration**: `plugins/floe-catalog-polaris/tests/integration/test_polaris_catalog.py`
- **Contract**: `tests/contract/test_catalog_plugin_abc.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/01-plugin-architecture/`
- `docs/architecture/plugin-system/`
- `plugins/floe-catalog-polaris/`

### Related Existing Code
- PluginRegistry from Epic 1

### External Dependencies
- `pyiceberg>=0.5.0`
- Polaris server (deployed separately)
