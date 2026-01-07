# ADR-0033: Target Airflow 3.x

## Status

Accepted

**RFC 2119 Compliance:** This ADR uses MUST/SHOULD/MAY keywords per [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119.txt). See [glossary](../../contracts/glossary.md#documentation-keywords-rfc-2119).

## Context

Apache Airflow 3.0 was released in April 2025, the first major release in 5 years. The floe Airflow orchestrator plugin must decide between:

1. **Target Airflow 2.10.x**: Stable, well-documented, minimal breaking changes
2. **Target Airflow 3.x**: Latest features but significant breaking changes from 2.x

### Airflow 3.x Features

| Feature | Description | Benefit for floe |
|---------|-------------|--------------------------|
| **Task SDK** | Language-agnostic task execution | Run dbt in any runtime |
| **Edge Executor** | Distributed computing at edge | Hybrid cloud deployments |
| **DAG Versioning** | Track DAG changes over time | Audit trail for pipelines |
| **Event-driven Scheduling** | AWS SQS, cloud events | Real-time data pipelines |
| **Service-oriented Architecture** | Modular services | Better K8s deployment |
| **Native OpenLineage** | Built-in lineage (since 2.7) | Already supported |

### Airflow 3.x Breaking Changes

| Change | Impact | Migration |
|--------|--------|-----------|
| `--ignore-depends-on-past` removed | CLI flag change | Use `--depends-on-past ignore` |
| `use_dill` parameter removed | Serialization change | Use `serializer='dill'` |
| `use_task_execution_date` removed | Context variable change | Use `use_task_logical_date` |
| MS SQL Server meta DB removed | Database support | Use PostgreSQL/MySQL |
| New `airflow.sdk` namespace | Import paths change | Update all imports |
| Python 3.9 dropped | Version requirement | Python 3.10+ required |

## Decision

Target **Airflow 3.x** for the floe Airflow orchestrator plugin.

### Rationale

1. **New features valuable**: Task SDK and DAG versioning align with floe goals
2. **Long-term investment**: Airflow 2.x will eventually be deprecated
3. **Greenfield development**: No existing 2.x code to migrate
4. **Cosmos compatibility**: Astronomer Cosmos actively supports 3.x
5. **Python alignment**: floe already targets Python 3.10+

## Consequences

### Positive

- **Latest features**: Task SDK, DAG versioning, event-driven scheduling
- **Future-proof**: No future migration from 2.x to 3.x
- **Better architecture**: Service-oriented design for K8s
- **Active development**: Latest bug fixes and improvements

### Negative

- **Documentation lag**: Some documentation may reference 2.x patterns
- **Community examples**: Many tutorials still target 2.x
- **Plugin compatibility**: Some Airflow plugins may not yet support 3.x

### Neutral

- Cosmos dbt integration works on both 2.x and 3.x
- OpenLineage provider available for both versions
- Helm chart works for both versions

---

## Implementation

### OrchestratorPlugin Interface

```python
# floe_core/interfaces/orchestrator.py
from abc import ABC, abstractmethod

class OrchestratorPlugin(ABC):
    """Interface for workflow orchestration (Dagster, Airflow, etc.)."""

    name: str
    version: str

    @abstractmethod
    def create_definitions(self, compiled_artifacts: CompiledArtifacts) -> None:
        """Generate orchestrator definitions from compiled artifacts."""
        pass

    @abstractmethod
    def create_assets_from_transforms(self, transforms: list[Transform]) -> list:
        """Create orchestrator assets from dbt models."""
        pass

    @abstractmethod
    def emit_lineage_event(self, event_type: str, metadata: dict) -> None:
        """Emit OpenLineage event."""
        pass
```

### Airflow 3.x Plugin Implementation

```python
# plugins/floe-orchestrator-airflow/plugin.py
from cosmos import DbtDag, ProjectConfig, ProfileConfig
from airflow.sdk import DAG, task  # Airflow 3.x namespace

class AirflowOrchestratorPlugin(OrchestratorPlugin):
    """Airflow 3.x orchestrator with Cosmos dbt integration."""

    name = "airflow"
    version = "3.0.0"

    def __init__(self, project_path: str, profile_config: dict):
        self.project_path = project_path
        self.profile_config = profile_config

    def create_definitions(self, compiled_artifacts: CompiledArtifacts) -> None:
        """Generate Airflow DAG from compiled artifacts."""
        # Create Cosmos DbtDag
        dag = DbtDag(
            project_config=ProjectConfig(self.project_path),
            profile_config=ProfileConfig(
                profile_name="floe",
                target_name=compiled_artifacts.target,
            ),
            dag_id=compiled_artifacts.data_product.name,
            schedule=compiled_artifacts.schedule.cron,
            # Airflow 3.x uses logical_date
            start_date=compiled_artifacts.schedule.start_date,
        )
        return dag

    def create_assets_from_transforms(self, transforms: list) -> list:
        """Create Airflow tasks from dbt models via Cosmos."""
        # Cosmos handles model-to-task mapping
        return DbtDag(
            project_config=ProjectConfig(self.project_path),
            render_config=RenderConfig(
                select=transforms,
            ),
        )

    def emit_lineage_event(self, event_type: str, metadata: dict) -> None:
        """Emit OpenLineage event via Airflow provider."""
        from airflow.providers.openlineage.plugins.listener import (
            OpenLineageListener,
        )
        listener = OpenLineageListener()
        listener.emit(event_type, metadata)
```

### Airflow 3.x DAG Generation

```python
# Generated DAG for data product
from airflow.sdk import DAG
from cosmos import DbtDag, ProjectConfig, ProfileConfig, RenderConfig

# Airflow 3.x uses airflow.sdk namespace
with DAG(
    dag_id="customer_360",
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    # DAG versioning (Airflow 3.x feature)
    version="1.0.0",
) as dag:

    dbt_dag = DbtDag(
        project_config=ProjectConfig("/app/dbt"),
        profile_config=ProfileConfig(
            profile_name="floe",
            target_name="prod",
        ),
        render_config=RenderConfig(
            select=["gold_customers", "gold_orders"],
        ),
        # Airflow 3.x: use logical_date instead of execution_date
        execution_date="{{ logical_date }}",
    )
```

---

## Key Airflow 3.x Patterns

### Task SDK (Language-Agnostic)

```python
# Airflow 3.x Task SDK allows external execution
from airflow.sdk import task

@task.external_python(python="/opt/airflow/dbt-venv/bin/python")
def run_dbt_model(model_name: str):
    """Run dbt model in separate Python environment."""
    import subprocess
    subprocess.run(["dbt", "run", "--select", model_name])
```

### DAG Versioning

```python
# Airflow 3.x tracks DAG versions
with DAG(
    dag_id="customer_360",
    version="2.1.0",  # Semantic versioning
    changelog="Added new customer segments",
) as dag:
    pass
```

### Event-Driven Scheduling

```python
# Airflow 3.x event triggers
from airflow.triggers.external_task import ExternalTaskTrigger

@task
async def wait_for_upstream():
    """Wait for upstream data product to complete."""
    trigger = ExternalTaskTrigger(
        external_dag_id="upstream_product",
        external_task_id="final_model",
    )
    await trigger.wait()
```

---

## Breaking Changes Migration

### Import Paths

```python
# Airflow 2.x
from airflow import DAG
from airflow.operators.python import PythonOperator

# Airflow 3.x
from airflow.sdk import DAG
from airflow.sdk.operators.python import PythonOperator
```

### Context Variables

```python
# Airflow 2.x
execution_date = context["execution_date"]

# Airflow 3.x
logical_date = context["logical_date"]  # Renamed
data_interval_start = context["data_interval_start"]
data_interval_end = context["data_interval_end"]
```

### CLI Flags

```bash
# Airflow 2.x
airflow dags backfill --ignore-depends-on-past

# Airflow 3.x
airflow dags backfill --depends-on-past ignore
```

### Serialization

```python
# Airflow 2.x
@task(use_dill=True)
def my_task():
    pass

# Airflow 3.x
@task(serializer="dill")
def my_task():
    pass
```

---

## Platform Manifest Configuration

```yaml
# manifest.yaml
plugins:
  orchestrator:
    type: airflow  # Targets Airflow 3.x
    config:
      version: "3.x"
      helm_chart: apache-airflow/airflow
      helm_version: "1.15.0"  # Supports Airflow 3.x
      executor: KubernetesExecutor
      dbt_integration: cosmos

      # Airflow 3.x specific
      features:
        dag_versioning: true
        task_sdk: true
        event_triggers: false  # Enable when needed
```

---

## Helm Chart Configuration

```yaml
# values.yaml for Airflow 3.x
defaultAirflowRepository: apache/airflow
defaultAirflowTag: "3.1.5"

executor: KubernetesExecutor

# PostgreSQL required (MS SQL removed in 3.x)
postgresql:
  enabled: true

# OpenLineage provider
extraPipPackages:
  - apache-airflow-providers-openlineage>=1.0.0
  - astronomer-cosmos>=1.10.0

# Environment for lineage
env:
  - name: OPENLINEAGE_URL
    value: "http://marquez:5000"
  - name: OPENLINEAGE_NAMESPACE
    value: "floe"
```

---

## Cosmos Integration

Astronomer Cosmos provides dbt integration for Airflow:

```python
# Using Cosmos with Airflow 3.x
from cosmos import DbtDag, ProjectConfig, ProfileConfig

customer_dag = DbtDag(
    project_config=ProjectConfig(
        dbt_project_path="/app/dbt",
        manifest_path="/app/dbt/target/manifest.json",
    ),
    profile_config=ProfileConfig(
        profile_name="floe",
        target_name="prod",
    ),
    dag_id="customer_360",
    schedule="0 6 * * *",
    # Cosmos handles model-to-task conversion
    # Each dbt model becomes an Airflow task
)
```

### Cosmos Features

| Feature | Support |
|---------|---------|
| dbt run per model | Yes |
| dbt test after model | Yes |
| OpenLineage emission | Yes (via Airflow provider) |
| DbtProject resource | Yes (dbt Fusion support) |
| Python models | Yes |

---

## Testing

### Unit Tests

```python
def test_airflow_3x_dag_generation():
    """Test DAG generation uses Airflow 3.x patterns."""
    plugin = AirflowOrchestratorPlugin(
        project_path="/app/dbt",
        profile_config={"target": "prod"},
    )

    dag = plugin.create_definitions(compiled_artifacts)

    # Verify Airflow 3.x patterns
    assert hasattr(dag, "version")  # DAG versioning
    assert "logical_date" not in dag.template_searchpath  # Not execution_date
```

### Integration Tests

```python
def test_cosmos_dbt_tasks():
    """Test Cosmos creates tasks for each dbt model."""
    dag = DbtDag(
        project_config=ProjectConfig("/app/dbt"),
        dag_id="test_dag",
    )

    # Each dbt model MUST have a corresponding Airflow task (testable requirement)
    task_ids = [t.task_id for t in dag.tasks]
    assert "gold_customers" in task_ids
    assert "gold_orders" in task_ids
```

---

## Documentation Requirements

The following documentation MUST be created for implementation completion:

1. **Airflow 3.x Features Guide**: Document Task SDK, DAG versioning, event triggers
2. **Cosmos Integration Guide**: dbt + Airflow patterns
3. **Breaking Changes Reference**: Migration from 2.x patterns (for users coming from 2.x)

---

## References

- [Apache Airflow 3.0 Announcement](https://airflow.apache.org/blog/airflow-3.0.0/)
- [Airflow 3.0 Breaking Changes](https://cwiki.apache.org/confluence/display/AIRFLOW/Airflow+3+breaking+changes)
- [Astronomer Cosmos](https://www.astronomer.io/cosmos/)
- [OpenLineage Airflow Provider](https://airflow.apache.org/docs/apache-airflow-providers-openlineage/stable/)
- [Airflow Helm Chart](https://airflow.apache.org/docs/helm-chart/stable/)
