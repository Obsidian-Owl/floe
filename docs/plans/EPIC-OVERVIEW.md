# Epic Overview

**Total Requirements**: 375+
**Total Epics**: 21
**Requirement Domains**: 7

---

## Executive Summary

The floe platform delivery is organized into 21 Epics across 9 categories. Each Epic is sized for optimal SpecKit task generation (15-25 requirements, yielding 30-60 tasks).

### Epic Sizing Rationale

| Size | Requirements | Tasks | User Stories | SpecKit Fit |
|------|--------------|-------|--------------|-------------|
| Optimal | 15-25 | 30-60 | 3-5 | Best |
| Acceptable | 10-30 | 20-80 | 2-6 | Good |
| Too Large | 30+ | 80+ | 6+ | Split required |

All Epics fall within the optimal or acceptable range.

---

## Dependency Graph

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    Epic 1: Plugin Registry                   │
                    │                    (FOUNDATION - Blocking)                   │
                    └─────────────────────────────────────────────────────────────┘
                                                   │
           ┌───────────────────────────────────────┼───────────────────────────────────────┐
           │                                       │                                       │
           ▼                                       ▼                                       ▼
   ┌───────────────┐                     ┌─────────────────┐                     ┌─────────────────┐
   │ Epic 2A       │                     │ Epics 4A-4D     │                     │ Epics 6A, 6B    │
   │ Manifest      │                     │ Core Plugins    │                     │ Observability   │
   └───────┬───────┘                     │ (Parallel)      │                     │ (Parallel)      │
           │                             └────────┬────────┘                     └─────────────────┘
           ▼                                      │
   ┌───────────────┐                              │
   │ Epic 2B       │                              │
   │ Compilation   │◄─────────────────────────────┘
   └───────┬───────┘
           │
           ├─────────────────────────────────────────────────────────────────────┐
           │                                                                      │
           ▼                                                                      ▼
   ┌───────────────┐                                                     ┌───────────────┐
   │ Epic 3A       │                                                     │ Epic 8A       │
   │ Policy Core   │                                                     │ OCI Client    │
   └───────┬───────┘                                                     └───────┬───────┘
           │                                                                      │
     ┌─────┴─────┐                                                               ▼
     │           │                                                       ┌───────────────┐
     ▼           ▼                                                       │ Epic 8B       │
┌─────────┐ ┌─────────┐                                                  │ Signing       │
│ Epic 3B │ │ Epic 3C │                                                  └───────┬───────┘
│ Validate│ │ Contract│                                                          │
└─────────┘ └────┬────┘                                                          ▼
                 │                                                       ┌───────────────┐
                 ▼                                                       │ Epic 8C       │
           ┌─────────┐                                                   │ Promotion     │
           │ Epic 3D │ ◄──── (Also depends on Epic 6B)                   └───────────────┘
           │ Monitor │
           └─────────┘

   ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
   │ Epic 7A       │     │ Epic 7B       │────►│ Epic 7C       │
   │ Identity      │     │ K8s RBAC      │     │ Network/Pod   │
   └───────────────┘     └───────────────┘     └───────────────┘

   ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
   │ Epic 9A       │────►│ Epic 9B       │────►│ Epic 9C       │
   │ K8s Deploy    │     │ Helm Charts   │     │ Testing Infra │
   └───────────────┘     └───────────────┘     └───────────────┘
         ▲
         │
   (Depends on Epics 4A-4D)
```

---

## Parallelization Matrix

### Wave 1 (No Dependencies)
| Epic | Name | Req Count | Can Start Immediately |
|------|------|-----------|----------------------|
| 1 | Plugin Registry | 10 | Yes (blocking) |

### Wave 2 (Depends on Epic 1 only)
| Epic | Name | Req Count | Parallel With |
|------|------|-----------|---------------|
| 2A | Manifest Schema | 16 | 4A, 4B, 4C, 4D, 5B, 6A, 6B, 7A, 7B |
| 4A | Compute Plugin | 10 | 2A, 4B, 4C, 4D, 5B, 6A, 6B, 7A, 7B |
| 4B | Orchestrator Plugin | 10 | 2A, 4A, 4C, 4D, 5B, 6A, 6B, 7A, 7B |
| 4C | Catalog Plugin | 10 | 2A, 4A, 4B, 4D, 5B, 6A, 6B, 7A, 7B |
| 4D | Storage Plugin | 10 | 2A, 4A, 4B, 4C, 5B, 6A, 6B, 7A, 7B |
| 5B | Data Quality | 10 | 2A, 4A-D, 6A, 6B, 7A, 7B |
| 6A | OpenTelemetry | 20 | 2A, 4A-D, 5B, 6B, 7A, 7B |
| 6B | OpenLineage | 21 | 2A, 4A-D, 5B, 6A, 7A, 7B |
| 7A | Identity/Secrets | 25 | 2A, 4A-D, 5B, 6A, 6B, 7B |
| 7B | K8s RBAC | 16 | 2A, 4A-D, 5B, 6A, 6B, 7A |

### Wave 3 (Depends on Wave 2)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 2B | Compilation | 13 | 1, 2A |
| 5A | dbt Plugin | 15 | 1, 4B |
| 7C | Network/Pod Security | 27 | 7B |
| 9A | K8s Deployment | 21 | 4A-D |

### Wave 4 (Depends on Wave 3)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 3A | Policy Enforcer | 15 | 2A, 2B |
| 8A | OCI Client | 16 | 2B |
| 9B | Helm Charts | 15 | 9A, 6A |

### Wave 5 (Depends on Wave 4)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 3B | Policy Validation | 21 | 3A |
| 3C | Data Contracts | 20 | 3A |
| 8B | Artifact Signing | 10 | 8A |
| 9C | Testing Infra | 15 | 9B |

### Wave 6 (Final)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 3D | Contract Monitoring | 15 | 3C, 6B |
| 8C | Promotion Lifecycle | 14 | 8B |

---

## Critical Path

The critical path determines the minimum time to complete all Epics:

```
Epic 1 → Epic 2A → Epic 2B → Epic 3A → Epic 3C → Epic 3D
   │
   └──→ Epic 4A-D → Epic 9A → Epic 9B → Epic 9C
```

**Critical Path Epics**: 1, 2A, 2B, 3A, 3C, 3D, 4A-D, 9A, 9B, 9C

**Optimization**: Parallelize Wave 2 Epics aggressively to minimize total delivery time.

---

## File Ownership Matrix

Each Epic has exclusive ownership of specific files to prevent merge conflicts:

| Epic | Package/Directory | Key Files |
|------|-------------------|-----------|
| 1 | `floe-core/src/floe_core/` | `plugin_registry.py`, `plugin_interfaces.py` |
| 2A | `floe-core/src/floe_core/schemas/` | `manifest.py`, `inheritance.py` |
| 2B | `floe-core/src/floe_core/` | `compiler.py`, `compiled_artifacts.py` |
| 3A-D | `floe-core/src/floe_core/governance/` | Policy and contract modules |
| 4A | `plugins/floe-compute-duckdb/` | All files |
| 4B | `plugins/floe-orchestrator-dagster/` | All files |
| 4C | `plugins/floe-catalog-polaris/` | All files |
| 4D | `floe-iceberg/` | All files |
| 5A | `floe-dbt/` | All files |
| 5B | `plugins/floe-quality-*/` | All files |
| 6A | `floe-core/src/floe_core/plugins/telemetry.py` | Telemetry ABC |
| 6B | `floe-core/src/floe_core/plugins/lineage.py` | Lineage ABC |
| 7A-C | `floe-core/src/floe_core/security/` | Security modules |
| 8A-C | `floe-core/src/floe_core/oci/` | OCI modules |
| 9A-B | `charts/` | Helm charts |
| 9C | `testing/` | Test infrastructure |

---

## Architecture Alignment

### Four-Layer Model Mapping

| Layer | Epics | Responsibility |
|-------|-------|----------------|
| 1: Foundation | 1, 4A-D, 5A-B, 6A-B, 7A | PyPI packages, plugin interfaces |
| 2: Configuration | 2A, 2B, 3A-D | OCI registry artifacts (manifest.yaml) |
| 3: Services | 9A, 9B | K8s Deployments (Dagster, Polaris, Cube) |
| 4: Data | 5A, 9C | K8s Jobs (dbt run, dlt ingestion) |

### ADR References

| Epic Category | Relevant ADRs |
|---------------|---------------|
| Plugin System | ADR-0001, ADR-0003 |
| Configuration | ADR-0010, ADR-0011 |
| Governance | ADR-0020, ADR-0021 |
| Observability | ADR-0030, ADR-0031 |
| Security | ADR-0040 |
| Deployment | ADR-0050, ADR-0051 |

---

## Quality Gates

Before an Epic is considered complete:

- [ ] All requirements mapped to tasks
- [ ] All tasks have Linear issues
- [ ] All tests passing (>80% coverage)
- [ ] Contract tests passing
- [ ] Security scan passing
- [ ] Documentation updated
- [ ] ADR references validated
