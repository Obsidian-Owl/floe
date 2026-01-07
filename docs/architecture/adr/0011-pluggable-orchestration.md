# ADR-0011: Pluggable Orchestration via OrchestratorPlugin

## Status

Accepted

## Context

Organizations have existing orchestration platforms (Airflow, Dagster, Prefect) with different paradigms:
- Airflow: DAG-based, task-centric
- Dagster: Asset-centric, software-defined assets
- Prefect: Flow-based, dynamic workflows

## Decision

Make orchestration pluggable via `OrchestratorPlugin` interface.

### OrchestratorPlugin Interface

```python
from abc import ABC, abstractmethod
from typing import Any

class OrchestratorPlugin(ABC):
    """Plugin interface for orchestration platforms."""

    @abstractmethod
    def generate_assets_from_manifest(
        self,
        manifest: dict[str, Any]
    ) -> list[Asset]:
        """Generate orchestrator-native assets from dbt manifest."""
        pass

    @abstractmethod
    def generate_schedules(
        self,
        schedule_config: dict[str, Any]
    ) -> list[Schedule]:
        """Generate schedules from floe.yaml config."""
        pass

    @abstractmethod
    def emit_telemetry(self) -> TelemetryConfig:
        """Configure OpenTelemetry integration."""
        pass

    @abstractmethod
    def emit_lineage(self) -> LineageConfig:
        """Configure OpenLineage integration."""
        pass
```

## Reference Implementations

- `DagsterPlugin`: Software-defined assets, sensors, schedules
- `AirflowPlugin`: DAG generation, task dependencies (ADR-0033)
- `PrefectPlugin`: Flow-based orchestration

## Consequences

### Positive

- Organizations keep existing orchestration tools
- Best-of-breed selection (Dagster for assets, Airflow for complex DAGs)
- Migration path (start Airflow, migrate to Dagster)

### Negative

- Each plugin needs maintenance
- Feature parity challenges across platforms

## References

- [ADR-0033: Airflow 3.x Plugin](0033-airflow-3x.md)
- [ADR-0037: Composability Principle](0037-composability-principle.md)
