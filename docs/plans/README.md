# floe Platform Delivery Plan

**Status**: Planning
**Initiative**: [floe Platform Delivery](https://linear.app/obsidianowl/initiative/floe-platform-delivery-25020298255a/overview)

---

## Overview

This directory contains the Epic-level delivery plan for the floe data platform. The plan covers **406+ requirements** across **24 Epics** organized into **11 categories**.

### Quick Navigation

| Category | Epics | Description |
|----------|-------|-------------|
| [01-foundation](epics/01-foundation/) | 1 | Plugin registry and discovery |
| [02-configuration](epics/02-configuration/) | 2A, 2B | Manifest schema, compilation pipeline |
| [03-enforcement](epics/03-enforcement/) | 3A-3D | Policy enforcement, data contracts |
| [04-core-plugins](epics/04-core-plugins/) | 4A-4D | Compute, orchestrator, catalog, storage |
| [05-transformation](epics/05-transformation/) | 5A, 5B | dbt integration, data quality |
| [06-observability](epics/06-observability/) | 6A, 6B | OpenTelemetry, OpenLineage |
| [07-security](epics/07-security/) | 7A-7C | Identity, RBAC, network security |
| [08-artifact-distribution](epics/08-artifact-distribution/) | 8A-8C | OCI registry, signing, promotion |
| [09-deployment](epics/09-deployment/) | 9A-9C | K8s deployment, Helm, testing |
| [10-contributor](epics/10-contributor/) | 10A, 10B | Agent memory, AI tooling |
| [12-tech-debt](epics/12-tech-debt/) | 12A | Periodic tech debt reduction |

---

## Key Documents

| Document | Purpose |
|----------|---------|
| [EPIC-OVERVIEW.md](EPIC-OVERVIEW.md) | High-level summary, dependencies, parallelization |
| [REQUIREMENTS-TRACEABILITY.md](REQUIREMENTS-TRACEABILITY.md) | Full REQ-XXX to Epic mapping |
| [epics/README.md](epics/README.md) | Epic index with status tracking |

---

## Tracking

### Linear Integration

- **Initiative**: floe Platform Delivery
- **Projects**: 24 (one per Epic)
- **Issues**: Created by `/speckit.taskstolinear`

### Workflow

```bash
# 1. Pick an Epic to work on
# 2. Run SpecKit to generate spec and tasks
/speckit.specify    # Create spec.md from Epic doc
/speckit.plan       # Generate plan.md
/speckit.tasks      # Generate tasks.md

# 3. Create Linear issues
/speckit.taskstolinear

# 4. Implement
/speckit.implement
```

---

## Architecture Alignment

This plan aligns with the target state architecture documented in `docs/architecture/`:

- **Four-Layer Model**: Foundation → Configuration → Services → Data
- **Plugin System**: 11 plugin types with ABCs in floe-core
- **Contract-Driven**: CompiledArtifacts as sole integration point
- **K8s-Native**: All deployment via Helm charts

See [EPIC-OVERVIEW.md](EPIC-OVERVIEW.md) for detailed architecture mapping.

---

## References

- **Architecture**: [`docs/architecture/`](../architecture/)
- **Requirements**: [`docs/requirements/`](../requirements/)
- **SpecKit Commands**: [`.claude/commands/`](../../.claude/commands/)
