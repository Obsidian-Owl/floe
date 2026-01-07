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
                              WAVE 1
                    ┌─────────────────────────┐
                    │   Epic 1: Plugin Registry│
                    │   (FOUNDATION - Blocking)│
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
 ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
 │  Epic 2A     │        │  Epic 4A     │        │  Epic 6A     │
 │  Manifest    │        │  Compute     │        │  OpenTelemetry│
 └──────┬───────┘        └──────────────┘        └──────────────┘
        │                        │                       │
        │    ┌──────────────┐    │                       │
        │    │  Epic 4C     │    │                       │
        │    │  Catalog     │    │                       │
        │    └──────┬───────┘    │                       │
        │           │            │                       │
        │           ▼            │                       │
        │    ┌──────────────┐    │                       │
        │    │  Epic 4D     │    │                       │
        │    │  Storage     │    │                       │
        │    └──────┬───────┘    │                       │
        │           │            │                       │
        ├───────────┤            │                       │
        │           │            │                       │
        ▼           │            │                       │
 ┌──────────────┐   │            │                       │
 │  Epic 7A     │   │            │                       │
 │  Identity    │   │            │                       │
 └──────┬───────┘   │            │                       │
        │           │            │                       │
        ├───────────┼────────────┘                       │
        │           │                                    │
        ▼           │                                    │
 ┌──────────────┐   │                                    │
 │  Epic 2B     │◄──┘                                    │
 │  Compilation │                                        │
 └──────┬───────┘                                        │
        │                                                │
        ├────────────────────────┬───────────────────────┤
        │                        │                       │
        ▼                        ▼                       │
 ┌──────────────┐        ┌──────────────┐               │
 │  Epic 4B     │        │  Epic 8A     │◄──(7A)        │
 │  Orchestrator│        │  OCI Client  │               │
 └──────┬───────┘        └──────┬───────┘               │
        │                        │                       │
        │                        ▼                       │
        │                ┌──────────────┐               │
        │                │  Epic 8B     │               │
        │                │  Signing     │               │
        │                └──────┬───────┘               │
        │                        │                       │
        ▼                        │                       │
 ┌──────────────┐               │                       │
 │  Epic 3A     │◄──(2A,2B)     │                       │
 │  Policy Core │               │                       │
 └──────┬───────┘               │                       │
        │                        │                       │
        ├─────────┐              │                       │
        │         │              │                       │
        ▼         ▼              │                       │
 ┌─────────┐ ┌─────────┐        │                       │
 │Epic 3B  │ │Epic 3C  │◄──(4D) │                       │
 │Validate │ │Contract │        │                       │
 └────┬────┘ └────┬────┘        │                       │
      │           │              │                       │
      │           │              │                       │
      │           │              ▼                       │
      │           │      ┌──────────────┐               │
      └───────────┼─────►│  Epic 8C     │◄──(8A,8B)     │
                  │      │  Promotion   │               │
                  │      └──────────────┘               │
                  │                                      │
        ┌─────────┴───────────────────────┐             │
        │                                  │             │
        ▼                                  ▼             │
 ┌──────────────┐                 ┌──────────────┐      │
 │  Epic 5A     │◄──(4A,4B,2B)    │  Epic 7B     │◄──(7A)
 │  dbt Plugin  │                 │  K8s RBAC    │      │
 └──────┬───────┘                 └──────┬───────┘      │
        │                                 │             │
        │                                 ▼             │
        │                         ┌──────────────┐      │
        │                         │  Epic 7C     │      │
        │                         │  Network/Pod │      │
        │                         └──────┬───────┘      │
        │                                 │             │
        ├─────────────────────────────────┤             │
        │                                 │             │
        ▼                                 │             │
 ┌──────────────┐                        │             │
 │  Epic 5B     │                        │             │
 │  DataQuality │                        │             │
 └──────┬───────┘                        │             │
        │                                 │             │
        ▼                                 │             │
 ┌──────────────┐                        │             │
 │  Epic 6B     │◄──(4B,5A)              │             │
 │  OpenLineage │                        │             │
 └──────┬───────┘                        │             │
        │                                 │             │
        │                                 │             │
        ▼                                 ▼             ▼
 ┌──────────────┐                ┌───────────────────────┐
 │  Epic 3D     │◄──(3C,6A)      │     Epic 9A           │
 │  Monitoring  │                │ K8s Deploy            │
 └──────────────┘                │ ◄──(4A-D,7B,7C,8A,8B) │
                                 └───────────┬───────────┘
                                             │
                                             ▼
                                 ┌───────────────────────┐
                                 │     Epic 9B           │
                                 │ Helm Charts           │
                                 │ ◄──(6A,7B,7C,9A)      │
                                 └───────────┬───────────┘
                                             │
                                             ▼
                                 ┌───────────────────────┐
                                 │     Epic 9C           │
                                 │ Testing Infrastructure│
                                 └───────────────────────┘
```

**Key**: Arrows show "blocked by" direction. Labels like `◄──(4D)` show additional dependencies.

---

## Parallelization Matrix

> **Note**: Waves are based on actual "Blocked By" dependencies from individual Epic files.

### Wave 1 (No Dependencies)
| Epic | Name | Req Count | Notes |
|------|------|-----------|-------|
| 1 | Plugin Registry | 10 | Foundation - blocks everything |

### Wave 2 (Depends on Epic 1 only)
| Epic | Name | Req Count | Parallel With |
|------|------|-----------|---------------|
| 2A | Manifest Schema | 16 | 4A, 4C, 6A |
| 4A | Compute Plugin | 10 | 2A, 4C, 6A |
| 4C | Catalog Plugin | 10 | 2A, 4A, 6A |
| 6A | OpenTelemetry | 20 | 2A, 4A, 4C |

### Wave 3 (Depends on Wave 2)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 2B | Compilation | 13 | 1, 2A |
| 4D | Storage Plugin | 10 | 1, 4C |
| 7A | Identity/Secrets | 25 | 1, 2A |

### Wave 4 (Depends on Wave 3)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 3A | Policy Enforcer | 15 | 2A, 2B |
| 4B | Orchestrator Plugin | 10 | 1, 2B |
| 7B | K8s RBAC | 16 | 1, 7A |
| 8A | OCI Client | 16 | 2B, 7A |

### Wave 5 (Depends on Wave 4)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 3B | Policy Validation | 21 | 3A |
| 3C | Data Contracts | 20 | 3A, 4D |
| 5A | dbt Plugin | 15 | 1, 2B, 4A, 4B |
| 7C | Network/Pod Security | 27 | 7B |
| 8B | Artifact Signing | 10 | 8A |

### Wave 6 (Depends on Wave 5)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 5B | Data Quality | 10 | 1, 5A |
| 6B | OpenLineage | 21 | 1, 4B, 5A |
| 8C | Promotion Lifecycle | 14 | 3B, 8A, 8B |

### Wave 7 (Depends on Wave 6)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 3D | Contract Monitoring | 15 | 3C, 6A, 6B |
| 9A | K8s Deployment | 21 | 4A-D, 7B, 7C, 8A, 8B |

### Wave 8 (Depends on Wave 7)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 9B | Helm Charts | 15 | 6A, 7B, 7C, 9A |

### Wave 9 (Final)
| Epic | Name | Req Count | Depends On |
|------|------|-----------|------------|
| 9C | Testing Infrastructure | 15 | 9B |

---

## Critical Path

The critical path determines the minimum time to complete all Epics:

```
Deployment Chain (longest path - 9 waves):
Epic 1 → 2A → 2B → 4B → 5A → 6B ─┐
   │                               │
   └→ 4A ─────────────────────────┤
   │                               ├─→ 9A → 9B → 9C
   └→ 4C → 4D ────────────────────┤
   │                               │
   └→ 7A → 7B → 7C ───────────────┤
   │                               │
   └→ 2B → 8A → 8B ───────────────┘

Governance Chain (parallel, 7 waves):
Epic 1 → 2A → 2B → 3A → 3B/3C → 5A → 5B/6B → 3D
                         │
                         └→ 8C (requires 3B, 8A, 8B)
```

**Critical Path (Deployment)**: 1 → 2A → 2B → 4B → 5A → 6B → 9A → 9B → 9C (9 waves)

**Key Bottlenecks**:
- **Epic 9A (K8s Deployment)**: Blocked by 4A-D, 7B, 7C, 8A, 8B (most dependencies)
- **Epic 5A (dbt Plugin)**: Blocked by 2B, 4A, 4B (gates 5B, 6B)
- **Epic 6B (OpenLineage)**: Blocked by 4B, 5A (gates 3D)

**Optimization Strategy**:
1. Parallelize Wave 2 aggressively (2A, 4A, 4C, 6A)
2. Prioritize 4B early (gates 5A, 6B)
3. Complete 7A → 7B → 7C chain early (gates 9A)

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
