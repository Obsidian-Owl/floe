# Epic 9B: Helm Charts

## Summary

Helm charts provide templated Kubernetes manifests for the floe platform. This includes the `floe-platform` meta-chart for platform services and `floe-jobs` base chart for data product workloads.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-09b-helm-charts](https://linear.app/obsidianowl/project/floe-09b-helm-charts-14ba871f8309)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-621 | floe-platform chart | CRITICAL |
| REQ-622 | floe-jobs chart | CRITICAL |
| REQ-623 | Subchart dependencies | HIGH |
| REQ-624 | Values schema | HIGH |
| REQ-625 | Chart versioning | HIGH |
| REQ-626 | Chart testing | HIGH |
| REQ-627 | Chart documentation | MEDIUM |
| REQ-628 | Helm hooks | HIGH |
| REQ-629 | Chart templating | HIGH |
| REQ-630 | Values override patterns | HIGH |
| REQ-631 | Secret management | HIGH |
| REQ-632 | ConfigMap management | HIGH |
| REQ-633 | Chart repository | HIGH |
| REQ-634 | Chart signing | MEDIUM |
| REQ-635 | Umbrella chart pattern | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0062](../../../architecture/adr/0062-helm-architecture.md) - Helm chart architecture
- [ADR-0063](../../../architecture/adr/0063-chart-patterns.md) - Chart design patterns

### Contracts
- Chart values schemas (JSON Schema)
- Chart interfaces (subcharts)

---

## File Ownership (Exclusive)

```text
charts/
├── floe-platform/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values.schema.json
│   ├── templates/
│   │   ├── _helpers.tpl
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   ├── secret.yaml
│   │   └── ...
│   └── charts/                  # Subcharts
│       ├── dagster/
│       ├── polaris/
│       └── otel-collector/
├── floe-jobs/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── templates/
│   │   ├── job.yaml
│   │   ├── cronjob.yaml
│   │   └── ...
└── testing/
    └── kind-values.yaml         # Kind cluster overrides
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 6A | OTel collector configuration |
| Blocked By | Epic 7B | RBAC templates |
| Blocked By | Epic 7C | Security templates |
| Blocked By | Epic 9A | Wraps deployment logic |
| Blocked By | Epic 9C | Test infrastructure (Wave 0) |

---

## User Stories (for SpecKit)

### US1: floe-platform Chart (P0)
**As a** platform operator
**I want** a single chart for platform services
**So that** I can deploy the entire platform easily

**Acceptance Criteria**:
- [ ] `helm install floe-platform` works
- [ ] Dagster, Polaris, OTel configured
- [ ] Subcharts version-pinned
- [ ] Resource defaults appropriate

### US2: floe-jobs Chart (P0)
**As a** data engineer
**I want** a base chart for data product jobs
**So that** I can deploy pipelines consistently

**Acceptance Criteria**:
- [ ] Job template for dbt runs
- [ ] CronJob template for schedules
- [ ] ConfigMap for CompiledArtifacts
- [ ] Secret mounting for credentials

### US3: Values Schema (P1)
**As a** platform operator
**I want** values validated by JSON Schema
**So that** misconfigurations are caught early

**Acceptance Criteria**:
- [ ] JSON Schema for all values
- [ ] Validation on `helm install`
- [ ] IDE autocomplete support
- [ ] Required vs optional clear

### US4: Chart Testing (P1)
**As a** platform developer
**I want** charts tested automatically
**So that** changes don't break deployments

**Acceptance Criteria**:
- [ ] `helm lint` passes
- [ ] `helm template` renders correctly
- [ ] ct (chart-testing) passes
- [ ] Integration test in Kind

### US5: Chart Repository (P2)
**As a** platform operator
**I want** charts in a Helm repository
**So that** I can install from a URL

**Acceptance Criteria**:
- [ ] OCI registry for charts
- [ ] GitHub Pages fallback
- [ ] Chart versioning
- [ ] Index generation

---

## Technical Notes

### Key Decisions
- Umbrella chart pattern for floe-platform
- Subcharts for external dependencies (Dagster, Polaris)
- OCI registry for chart distribution
- JSON Schema for values validation

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Subchart version conflicts | HIGH | MEDIUM | Pin versions, test upgrades |
| Values complexity | HIGH | MEDIUM | Good defaults, documentation |
| Template debugging | MEDIUM | MEDIUM | `helm template` output |

### Test Strategy
- **Unit**: `helm lint`, `helm template`
- **Integration**: `ct install` in Kind cluster
- **E2E**: Full platform deployment tests

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/07-deployment-operations/`
- `docs/architecture/deployment/`
- `charts/`

### Related Existing Code
- Deployment logic from Epic 9A
- Security templates from Epic 7B, 7C

### External Dependencies
- `helm>=3.12.0`
- `ct` (chart-testing)
- Subchart dependencies (Dagster Helm chart, etc.)
