# Epic 3C: Data Contracts

## Summary

Data contracts define the schema, quality expectations, and SLAs for data products. This Epic implements contract definition, versioning, evolution tracking, and compatibility checking to ensure data producers and consumers have clear agreements.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-03c-data-contracts](https://linear.app/obsidianowl/project/floe-03c-data-contracts-4b302490a939)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-236 | Contract schema definition | CRITICAL |
| REQ-237 | Contract versioning | CRITICAL |
| REQ-238 | Schema evolution tracking | HIGH |
| REQ-239 | Backward compatibility checking | CRITICAL |
| REQ-240 | Forward compatibility checking | HIGH |
| REQ-241 | Breaking change detection | CRITICAL |
| REQ-242 | Contract registry | HIGH |
| REQ-243 | Contract discovery API | HIGH |
| REQ-244 | Contract documentation | MEDIUM |
| REQ-245 | Contract testing framework | HIGH |
| REQ-246 | SLA definitions | HIGH |
| REQ-247 | Quality expectations | HIGH |
| REQ-248 | Ownership metadata | HIGH |
| REQ-249 | Consumer tracking | MEDIUM |
| REQ-250 | Contract negotiation workflow | LOW |
| REQ-251 | Deprecation management | HIGH |
| REQ-252 | Migration path documentation | MEDIUM |
| REQ-253 | Contract validation hooks | HIGH |
| REQ-254 | Integration with Iceberg schemas | HIGH |
| REQ-255 | Contract diff tools | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0023](../../../architecture/adr/0023-data-contracts.md) - Data contract architecture
- [ADR-0024](../../../architecture/adr/0024-schema-evolution.md) - Schema evolution patterns

### Contracts
- `DataContract` - Contract definition model
- `ContractVersion` - Version tracking model
- `CompatibilityResult` - Compatibility check result

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── contracts/
│   ├── __init__.py
│   ├── schema.py                # DataContract model
│   ├── version.py               # ContractVersion model
│   ├── registry.py              # Contract registry
│   ├── evolution.py             # Schema evolution tracking
│   ├── compatibility.py         # Compatibility checking
│   └── sla.py                   # SLA definitions
└── cli/
    └── contracts.py             # CLI contract commands
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 3A | Uses policy engine for validation |
| Blocked By | Epic 4D | Integrates with Iceberg schemas |
| Blocks | Epic 3D | Contract monitoring tracks contracts |
| Blocks | Epic 6B | OpenLineage captures contract info |

---

## User Stories (for SpecKit)

### US1: Contract Definition (P0)
**As a** data producer
**I want** to define contracts for my data products
**So that** consumers know what to expect

**Acceptance Criteria**:
- [ ] `contract.yaml` schema defined
- [ ] Schema, quality, SLA sections supported
- [ ] Ownership metadata included
- [ ] Integration with floe.yaml

### US2: Compatibility Checking (P0)
**As a** data producer
**I want** to check if schema changes are compatible
**So that** I don't break downstream consumers

**Acceptance Criteria**:
- [ ] `floe contract check` command works
- [ ] Backward compatibility detected
- [ ] Breaking changes highlighted
- [ ] Migration suggestions provided

### US3: Contract Registry (P1)
**As a** data consumer
**I want** to discover available contracts
**So that** I can find data products to use

**Acceptance Criteria**:
- [ ] Central registry for contracts
- [ ] Search by name, owner, tags
- [ ] Version history available
- [ ] Consumer subscription tracking

### US4: Iceberg Schema Integration (P1)
**As a** data engineer
**I want** contracts synced with Iceberg schemas
**So that** schema changes are tracked end-to-end

**Acceptance Criteria**:
- [ ] Contract schema extracted from Iceberg
- [ ] Schema evolution tracked in contracts
- [ ] Partition evolution tracked
- [ ] Alerts on schema drift

---

## Technical Notes

### Key Decisions
- Contracts are immutable once published (new version required)
- Backward compatibility = consumers unchanged
- Forward compatibility = producers unchanged
- Breaking changes require deprecation period

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Schema drift from Iceberg | MEDIUM | HIGH | Automated sync, drift detection |
| Contract version explosion | MEDIUM | MEDIUM | Semantic versioning, deprecation |
| Consumer tracking accuracy | MEDIUM | MEDIUM | Lineage integration |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_contracts.py`
- **Contract**: `tests/contract/test_data_contract_schema.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/03-data-governance/`
- `docs/architecture/contracts/`
- `packages/floe-core/`

### Related Existing Code
- Iceberg schema APIs (PyIceberg)

### External Dependencies
- `pydantic>=2.0`
- `pyiceberg>=0.5.0`
