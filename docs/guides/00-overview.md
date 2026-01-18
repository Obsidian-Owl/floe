# 00. Overview

## Document Purpose

This is the architecture documentation for **floe**, the open-source Data Execution Layer. It follows the [arc42](https://arc42.org/) template and serves as the authoritative reference for understanding, extending, and contributing to the runtime.

---

## 1. What is floe?

floe is an **open-source data pipeline execution framework** that integrates best-in-class tools into a cohesive, developer-friendly experience:

- **Dagster** for asset-centric orchestration
- **dbt** for SQL transformations
- **Apache Iceberg** for open table format storage
- **Apache Polaris** for catalog management
- **OpenTelemetry** for observability
- **OpenLineage** for data lineage

### The Core Promise

Define your data pipeline in `floe.yaml`, and floe handles the complexity of orchestrating multiple tools, managing dependencies, and providing observability—all while inheriting platform guardrails.

```yaml
# floe.yaml - DataProduct definition (Data Team)
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-analytics
  version: "1.0"

platform:
  ref: oci://registry.example.com/floe-platform:v1.2.3  # Inherit platform config

transforms:
  - type: dbt
    path: models/

schedule:
  cron: "0 6 * * *"
```

The platform configuration (compute target, governance, naming conventions) is defined separately in `manifest.yaml` by the Platform Team. See [03-solution-strategy](03-solution-strategy.md) for details on the two-file configuration model.

---

## 2. Open Source Philosophy

### 2.1 Apache 2.0 License

floe is licensed under Apache 2.0, providing:

- **Freedom to use** in any project, commercial or personal
- **Freedom to modify** and create derivative works
- **Freedom to distribute** original or modified versions
- **Patent protection** from contributors

### 2.2 Standalone-First Design

Every feature in floe works as a **100% standalone open-source project**. We stand on the shoulders of open-source giants—Dagster, dbt, Apache Iceberg, Apache Polaris, Cube, OpenTelemetry, and OpenLineage—integrating best-in-class tools into a cohesive experience with no proprietary dependencies.

### 2.3 Community-Driven Development

We believe in:

- **Transparency**: All architectural decisions documented as ADRs
- **Extensibility**: Clear extension points for custom integrations
- **Contribution-friendly**: Comprehensive test coverage and documentation
- **No vendor lock-in**: Standard formats (Iceberg, OpenLineage, OTel)

---

## 3. Business Goals

| Priority | Goal | Description |
|----------|------|-------------|
| 1 | **Developer Experience** | Simple CLI, instant feedback, minimal configuration |
| 2 | **Tool Integration** | Seamless integration of Dagster, dbt, Iceberg, Polaris |
| 3 | **Portability** | Run anywhere: laptop, Docker, Kubernetes, any cloud |
| 4 | **Observability** | Built-in tracing, metrics, and lineage from day one |
| 5 | **Extensibility** | Clear interfaces for custom transforms and targets |

---

## 4. Quality Goals

| Quality | Target | How Measured |
|---------|--------|--------------|
| **Portability** | Works on macOS, Linux, Windows | CI matrix testing |
| **Simplicity** | < 5 min from install to first run | User testing |
| **Performance** | < 1s CLI startup time | Benchmark tests |
| **Reliability** | Zero data loss during execution | Integration tests |
| **Extensibility** | Custom transforms without forking | Plugin architecture |

---

## 5. Stakeholders

### 5.1 Open Source Users

| Persona | Goals | Key Concerns |
|---------|-------|--------------|
| **Data Engineer** | Build and run pipelines locally | Ease of use, debugging |
| **Analytics Engineer** | Develop dbt models with orchestration | dbt compatibility |
| **Platform Engineer** | Deploy to Kubernetes | Helm charts, observability |
| **Contributor** | Add features, fix bugs | Code quality, documentation |

### 5.2 Enterprise Self-Hosters

| Persona | Goals | Key Concerns |
|---------|-------|--------------|
| **Data Platform Team** | Run floe on internal K8s | Security, air-gapped support |
| **DevOps** | Maintain infrastructure | Monitoring, upgrades |
| **Security Team** | Ensure compliance | No external dependencies |

---

## 6. Architecture Principles

### 6.1 Core Principles

1. **dbt owns SQL** — Floe never parses, transpiles, or validates SQL. dbt handles all SQL operations.

2. **Target agnostic** — Users choose their compute target. DuckDB is a viable production choice, as is Snowflake—Floe doesn't prescribe. Same configuration works across all environments.

3. **Observability first** — Every operation emits traces, metrics, and lineage. Built-in, not bolted-on.

4. **Standard formats** — Iceberg for storage, OpenLineage for lineage, OTel for observability. No proprietary formats.

5. **Explicit over implicit** — Configuration is declarative. No magic, no hidden behavior.

### 6.2 Design Guidelines

- Keep packages focused and single-purpose
- Prefer composition over inheritance
- Use type hints everywhere
- Document public APIs with docstrings
- Test at integration boundaries, not just units

---

## 7. Technology Summary

| Component | Technology | Rationale |
|-----------|------------|-----------|
| CLI | Python (Click) | Native to data engineering ecosystem |
| Orchestration | Dagster | Asset-centric, OpenLineage native |
| Transformation | dbt | Industry standard, target-agnostic |
| Storage | Apache Iceberg | Open table format, multi-engine |
| Catalog | Apache Polaris | REST API, vendor-neutral |
| Observability | OpenTelemetry | Vendor-neutral standard |
| Lineage | OpenLineage | Industry standard, Marquez backend |

See [03-solution-strategy](03-solution-strategy.md) for detailed rationale.

---

## 8. Document Conventions

### Diagrams

- **ASCII art** for inline diagrams (version-controllable)
- **C4 Model** for system architecture
- **Sequence diagrams** for runtime flows

### Code Examples

All code examples are tested and runnable:

```python
# Examples use type hints
from floe_core import CompiledArtifacts

def process(artifacts: CompiledArtifacts) -> None:
    ...
```

### Links

- External links point to stable documentation
- Internal links use relative paths

---

## 9. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01 | Floe Team | Initial runtime documentation |
