# Epic 2B: Compilation Pipeline

## Summary

The compilation pipeline transforms FloeSpec (floe.yaml) + PlatformManifest into CompiledArtifacts - the sole contract between packages. This includes generating dbt profiles.yml and Dagster configuration.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-02b-compilation](https://linear.app/obsidianowl/project/floe-02b-compilation-3b5102b58136)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-116 | FloeSpec (floe.yaml) parsing | CRITICAL |
| REQ-117 | Compilation engine | CRITICAL |
| REQ-118 | CompiledArtifacts generation | CRITICAL |
| REQ-119 | dbt profiles.yml generation | CRITICAL |
| REQ-120 | Dagster configuration export | CRITICAL |
| REQ-121 | Manifest + FloeSpec merging | HIGH |
| REQ-122 | Plugin resolution | HIGH |
| REQ-123 | Credential placeholder resolution | HIGH |
| REQ-124 | Target environment handling | HIGH |
| REQ-125 | Compilation caching | MEDIUM |
| REQ-126 | Incremental compilation | LOW |
| REQ-127 | Compilation validation | HIGH |
| REQ-128 | CLI compile command | HIGH |

---

## Architecture References

### ADRs
- [ADR-0012](../../../architecture/adr/0012-compiled-artifacts.md) - CompiledArtifacts contract
- [ADR-0013](../../../architecture/adr/0013-credential-resolution.md) - Runtime credential resolution

### Contracts
- `CompiledArtifacts` - THE contract between packages
- `FloeSpec` - Data engineer's configuration

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── compiler.py                 # Compilation engine
├── compiled_artifacts.py       # CompiledArtifacts schema
├── schemas/
│   └── floe_spec.py           # FloeSpec model
└── cli/
    └── compile.py             # CLI compile command
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 2A | Uses PlatformManifest |
| Blocks | Epic 3A | Policies check CompiledArtifacts |
| Blocks | Epic 8A | OCI client packages CompiledArtifacts |

---

## User Stories (for SpecKit)

### US1: Compilation Engine (P0)
**As a** data engineer
**I want** to compile my floe.yaml with platform manifest
**So that** I get validated, deployable artifacts

**Acceptance Criteria**:
- [ ] `floe compile` command works
- [ ] Outputs CompiledArtifacts JSON
- [ ] Validation errors are actionable

### US2: dbt Profile Generation (P0)
**As a** data engineer
**I want** profiles.yml generated automatically
**So that** I don't have to manually configure dbt connections

**Acceptance Criteria**:
- [ ] `target/profiles.yml` generated
- [ ] Credential placeholders resolve to env vars
- [ ] Multiple targets supported (dev, staging, prod)

### US3: CompiledArtifacts Contract (P1)
**As a** platform developer
**I want** CompiledArtifacts to be the sole integration point
**So that** packages remain decoupled

**Acceptance Criteria**:
- [ ] `CompiledArtifacts.to_json_file(path)` serializes
- [ ] `CompiledArtifacts.from_json_file(path)` deserializes
- [ ] Schema versioned with backward compatibility

---

## Technical Notes

### Key Decisions
- CompiledArtifacts is frozen (immutable) after compilation
- Credential resolution happens at runtime, not compile time
- JSON format for portability across languages

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_compiler.py`
- **Contract**: `tests/contract/test_compiled_artifacts_schema.py`
- **Contract**: `tests/contract/test_core_to_dagster_contract.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/02-configuration-management/`
- `packages/floe-core/`

### External Dependencies
- `pydantic>=2.0`
