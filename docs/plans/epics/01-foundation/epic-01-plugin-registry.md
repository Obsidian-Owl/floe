# Epic 1: Plugin Registry Foundation

## Summary

The plugin registry is the foundation of the floe platform, enabling discovery and management of all pluggable components. This Epic establishes the core abstractions (PluginMetadata, plugin ABCs) that all other Epics depend on.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-01-plugin-registry](https://linear.app/obsidianowl/project/floe-01-plugin-registry-c25c7e7d9d53)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-001 | Plugin discovery via entry points | CRITICAL |
| REQ-002 | PluginMetadata ABC definition | CRITICAL |
| REQ-003 | Plugin registration API | HIGH |
| REQ-004 | Plugin lookup by type/name | HIGH |
| REQ-005 | Version compatibility checking | HIGH |
| REQ-006 | Plugin dependency resolution | MEDIUM |
| REQ-007 | Hot reload support (dev mode) | LOW |
| REQ-008 | Plugin health checks | MEDIUM |
| REQ-009 | Plugin configuration validation | HIGH |
| REQ-010 | Plugin lifecycle hooks | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0001](../../../architecture/adr/0001-plugin-architecture.md) - Plugin architecture overview
- [ADR-0003](../../../architecture/adr/0003-entry-point-discovery.md) - Entry point discovery pattern

### Interface Docs
- [plugin-system/index.md](../../../architecture/plugin-system/index.md) - Plugin system overview
- [plugin-interfaces.md](../../../architecture/plugin-system/plugin-interfaces.md) - Interface definitions

### Contracts
- `PluginMetadata` - Core plugin metadata ABC
- `PluginRegistry` - Central registry singleton

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── plugin_registry.py          # Registry implementation
├── plugin_interfaces.py        # ABC definitions
├── plugin_metadata.py          # PluginMetadata ABC
└── plugins/
    └── __init__.py             # Plugin package init
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | None | Foundation - no dependencies |
| Blocks | 2A | Manifest references plugin types |
| Blocks | 4A-D | All plugins implement ABCs |
| Blocks | 5A-B | dbt/Quality plugins implement ABCs |
| Blocks | 6A-B | Telemetry/Lineage plugins implement ABCs |
| Blocks | 7A | Identity/Secrets plugins implement ABCs |

---

## User Stories (for SpecKit)

### US1: Plugin Discovery (P0)
**As a** platform developer
**I want** plugins to be discoverable via entry points
**So that** I can add new capabilities without modifying core code

**Acceptance Criteria**:
- [ ] Entry point group `floe.plugins` defined in pyproject.toml
- [ ] Plugins discovered at import time
- [ ] Plugin metadata extracted from entry point
- [ ] Discovery errors logged, don't crash startup

### US2: Plugin Registration (P1)
**As a** platform developer
**I want** a central registry for all plugins
**So that** I can look up plugins by type and name

**Acceptance Criteria**:
- [ ] `PluginRegistry.register(plugin)` API
- [ ] `PluginRegistry.get(type, name)` API
- [ ] `PluginRegistry.list(type)` API
- [ ] Duplicate registration raises error

### US3: Version Compatibility (P1)
**As a** platform operator
**I want** version compatibility checking
**So that** incompatible plugins are rejected at startup

**Acceptance Criteria**:
- [ ] `PluginMetadata.floe_api_version` field
- [ ] Version compatibility check during registration
- [ ] Clear error message for incompatible versions
- [ ] Semver-based compatibility rules

### US4: Plugin Configuration (P2)
**As a** platform operator
**I want** plugin configuration validated
**So that** misconfigured plugins are caught early

**Acceptance Criteria**:
- [ ] `PluginMetadata.config_schema` returns Pydantic model
- [ ] Configuration validated on load
- [ ] Validation errors include field paths
- [ ] Defaults applied from schema

---

## Technical Notes

### Key Decisions
- Use `importlib.metadata.entry_points()` for discovery (Python 3.10+)
- Singleton `PluginRegistry` accessible via `get_registry()`
- Lazy loading: plugins loaded on first access, not at import

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Entry point conflicts | LOW | MEDIUM | Namespace plugins under `floe.` |
| Circular imports | MEDIUM | HIGH | Defer imports, use TYPE_CHECKING |
| Version fragmentation | MEDIUM | MEDIUM | Clear versioning policy in ADR |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_plugin_registry.py`
  - Mock entry points for discovery tests
  - Test registration, lookup, version checks
- **Contract**: `tests/contract/test_plugin_abc_contract.py`
  - Verify ABC contracts stable across versions
- **Integration**: Not required (no external services)

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/01-plugin-architecture/` - Requirements source
- `docs/architecture/plugin-system/` - Architecture context
- `packages/floe-core/` - Implementation target

### Related Existing Code
- None (greenfield)

### External Dependencies
- `importlib.metadata` (stdlib)
- `pydantic` (config validation)
