# Epic 2A: Manifest Schema

## Summary

Defines the `manifest.yaml` schema using Pydantic models, implementing three-tier inheritance (Enterprise → Domain → Product) for platform-wide configuration. This enables platform teams to define standards that data engineers inherit.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-02a-manifest-schema](https://linear.app/obsidianowl/project/floe-02a-manifest-schema-56626c900a2b)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-100 | manifest.yaml schema definition | CRITICAL |
| REQ-101 | Pydantic model validation | CRITICAL |
| REQ-102 | Three-tier inheritance (Enterprise) | HIGH |
| REQ-103 | Three-tier inheritance (Domain) | HIGH |
| REQ-104 | Three-tier inheritance (Product) | HIGH |
| REQ-105 | Plugin selection configuration | CRITICAL |
| REQ-106 | JSON Schema export | HIGH |
| REQ-107 | IDE autocomplete support | MEDIUM |
| REQ-108 | Environment-specific overrides | HIGH |
| REQ-109 | Secret reference placeholders | HIGH |
| REQ-110 | Validation error messages | HIGH |
| REQ-111 | Default value handling | MEDIUM |
| REQ-112 | Required field enforcement | HIGH |
| REQ-113 | Cross-field validation | MEDIUM |
| REQ-114 | Version compatibility | HIGH |
| REQ-115 | Deprecation warnings | LOW |

---

## Architecture References

### ADRs
- [ADR-0010](../../../architecture/adr/0010-configuration-model.md) - Two-file configuration model
- [ADR-0011](../../../architecture/adr/0011-manifest-inheritance.md) - Three-tier inheritance

### Interface Docs
- [configuration/manifest-schema.md](../../../architecture/configuration/manifest-schema.md) - Schema reference

### Contracts
- `PlatformManifest` - Top-level manifest model
- `PluginSelection` - Plugin configuration model
- `SecretReference` - Secret placeholder model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/schemas/
├── manifest.py                 # PlatformManifest model
├── inheritance.py              # Inheritance resolution
├── plugin_selection.py         # PluginSelection model
├── secret_reference.py         # SecretReference model
└── validators.py               # Cross-field validators
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin type definitions |
| Blocks | Epic 2B | Compilation uses manifest |
| Blocks | Epic 3A | Policies defined in manifest |

---

## User Stories (for SpecKit)

### US1: Manifest Parsing (P0)
**As a** platform team member
**I want** to define platform configuration in manifest.yaml
**So that** data engineers get opinionated defaults

**Acceptance Criteria**:
- [ ] `PlatformManifest.from_yaml(path)` loads and validates
- [ ] Validation errors include file path and line numbers
- [ ] Unknown fields raise warnings (not errors) for forward compatibility

### US2: Three-Tier Inheritance (P1)
**As a** enterprise architect
**I want** manifests to inherit from parent manifests
**So that** standards cascade from enterprise to domain to product

**Acceptance Criteria**:
- [ ] `extends: path/to/parent.yaml` field supported
- [ ] Child values override parent values
- [ ] Arrays merge by default, can be replaced with `!override`
- [ ] Circular inheritance detected and rejected

### US3: Plugin Selection (P1)
**As a** platform team member
**I want** to select which plugins are active
**So that** I can standardize on approved technologies

**Acceptance Criteria**:
- [ ] `plugins.compute: duckdb` syntax for plugin selection
- [ ] Plugin existence validated against registry
- [ ] Plugin-specific config nested under plugin key

### US4: JSON Schema Export (P2)
**As a** data engineer
**I want** IDE autocomplete for manifest.yaml
**So that** I can write correct configuration faster

**Acceptance Criteria**:
- [ ] `floe manifest schema > manifest.schema.json`
- [ ] Schema registered in `$schema` field
- [ ] VS Code / PyCharm autocomplete works

---

## Technical Notes

### Key Decisions
- Use Pydantic v2 with `model_json_schema()` for JSON Schema export
- Inheritance resolved at parse time, not runtime
- `SecretReference` values remain as placeholders until compilation

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Schema evolution breaks existing manifests | MEDIUM | HIGH | Semver for schema, deprecation period |
| Inheritance complexity confuses users | MEDIUM | MEDIUM | Clear documentation, `--show-resolved` flag |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_manifest_schema.py`
  - Test parsing, validation, inheritance
- **Contract**: `tests/contract/test_manifest_to_compiled_contract.py`
  - Verify manifest → CompiledArtifacts contract

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/02-configuration-management/` - Requirements
- `docs/architecture/configuration/` - Architecture
- `packages/floe-core/src/floe_core/schemas/` - Target

### Related Existing Code
- None (greenfield, but follow Pydantic patterns from other projects)

### External Dependencies
- `pydantic>=2.0` (validation)
- `pyyaml>=6.0` (YAML parsing)
