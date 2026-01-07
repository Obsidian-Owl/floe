# 07. Cross-Cutting Concerns

This document describes concerns that span multiple components: observability, configuration, security, and extensibility.

---

## 1. Observability

### 1.1 Strategy Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OBSERVABILITY ARCHITECTURE                            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    APPLICATION LAYER                                  │    │
│  │                                                                      │    │
│  │   floe-cli    floe-dbt    floe-iceberg    (plugins/*)              │    │
│  │      │             │             │             │                    │    │
│  │      └─────────────┴─────────────┴─────────────┘                    │    │
│  │                           │                                          │    │
│  │                           ▼                                          │    │
│  │              ┌─────────────────────────┐                            │    │
│  │              │   OpenTelemetry SDK     │                            │    │
│  │              │   ├── Traces            │                            │    │
│  │              │   ├── Metrics           │                            │    │
│  │              │   └── Logs              │                            │    │
│  │              └───────────┬─────────────┘                            │    │
│  │                          │                                          │    │
│  │              ┌───────────┴─────────────┐                            │    │
│  │              │   OpenLineage Client    │                            │    │
│  │              │   └── Lineage Events    │                            │    │
│  │              └───────────┬─────────────┘                            │    │
│  │                          │                                          │    │
│  └──────────────────────────┼──────────────────────────────────────────┘    │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    COLLECTION LAYER                                  │    │
│  │                                                                      │    │
│  │   ┌─────────────────────┐       ┌─────────────────────┐            │    │
│  │   │   OTel Collector    │       │   Marquez / DataHub │            │    │
│  │   │   └── OTLP receiver │       │   └── HTTP receiver │            │    │
│  │   └──────────┬──────────┘       └──────────┬──────────┘            │    │
│  │              │                             │                        │    │
│  └──────────────┼─────────────────────────────┼────────────────────────┘    │
│                 │                             │                              │
│                 ▼                             ▼                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    BACKEND LAYER                                     │    │
│  │                                                                      │    │
│  │   Traces: Jaeger, Tempo, Datadog                                    │    │
│  │   Metrics: Prometheus, Mimir, Datadog                               │    │
│  │   Logs: Loki, Elasticsearch, CloudWatch                             │    │
│  │   Lineage: Marquez, DataHub, Atlan                                  │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 OpenTelemetry Integration

```python
# floe_core/telemetry.py
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

def init_telemetry(
    service_name: str,
    service_version: str,
    otlp_endpoint: str | None = None,
) -> tuple[TracerProvider, MeterProvider]:
    """Initialize OpenTelemetry for the application."""

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
    })

    # Tracing
    tracer_provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = None
    if otlp_endpoint:
        metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)
        metric_reader = PeriodicExportingMetricReader(metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader] if metric_reader else [])
    metrics.set_meter_provider(meter_provider)

    return tracer_provider, meter_provider
```

### 1.3 Tracing Patterns

```python
# Instrumented function pattern
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("compile_spec")
def compile_spec(spec_path: Path) -> CompiledArtifacts:
    """Compile floe.yaml with automatic tracing."""
    span = trace.get_current_span()

    # Add attributes
    span.set_attribute("floe.spec_path", str(spec_path))

    with tracer.start_as_current_span("parse_yaml"):
        spec = parse_yaml(spec_path)

    with tracer.start_as_current_span("validate_schema"):
        validate(spec)

    with tracer.start_as_current_span("generate_artifacts"):
        artifacts = generate(spec)

    span.set_attribute("floe.artifact_count", len(artifacts.transforms))
    return artifacts
```

### 1.4 Metrics

```python
# floe_core/metrics.py
from opentelemetry import metrics

meter = metrics.get_meter(__name__)

# Counters
pipeline_runs_total = meter.create_counter(
    name="floe_pipeline_runs_total",
    description="Total pipeline runs",
    unit="1",
)

# Histograms
pipeline_duration = meter.create_histogram(
    name="floe_pipeline_duration_seconds",
    description="Pipeline execution duration",
    unit="s",
)

# Usage
def record_run_complete(duration_seconds: float, status: str):
    pipeline_runs_total.add(1, {"status": status})
    pipeline_duration.record(duration_seconds, {"status": status})
```

### 1.5 OpenLineage Integration

```python
# floe_dagster/lineage.py
from openlineage.client import OpenLineageClient
from openlineage.client.facet import (
    SqlJobFacet,
    SchemaDatasetFacet,
    SchemaDatasetFacetFields,
)
from openlineage.client.run import RunEvent, RunState, Job, Run, Dataset

class LineageEmitter:
    """Emit OpenLineage events for data operations."""

    def __init__(self, url: str, namespace: str):
        self.client = OpenLineageClient(url=url)
        self.namespace = namespace

    def emit_dbt_model_start(
        self,
        model_name: str,
        run_id: str,
        sql: str,
        inputs: list[str],
    ):
        """Emit start event for dbt model."""
        event = RunEvent(
            eventType=RunState.START,
            eventTime=datetime.now(timezone.utc).isoformat(),
            job=Job(
                namespace=self.namespace,
                name=model_name,
                facets={
                    "sql": SqlJobFacet(query=sql),
                },
            ),
            run=Run(runId=run_id),
            inputs=[
                Dataset(namespace=self.namespace, name=inp)
                for inp in inputs
            ],
        )
        self.client.emit(event)

    def emit_dbt_model_complete(
        self,
        model_name: str,
        run_id: str,
        schema: list[dict],
    ):
        """Emit complete event for dbt model."""
        event = RunEvent(
            eventType=RunState.COMPLETE,
            eventTime=datetime.now(timezone.utc).isoformat(),
            job=Job(namespace=self.namespace, name=model_name),
            run=Run(runId=run_id),
            outputs=[
                Dataset(
                    namespace=self.namespace,
                    name=model_name,
                    facets={
                        "schema": SchemaDatasetFacet(
                            fields=[
                                SchemaDatasetFacetFields(
                                    name=col["name"],
                                    type=col["type"],
                                )
                                for col in schema
                            ]
                        ),
                    },
                )
            ],
        )
        self.client.emit(event)
```

---

## 2. Configuration Management

### 2.1 Configuration Hierarchy

#### Centralized Model (Single Platform)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONFIGURATION PRECEDENCE                                │
│                      (highest to lowest)                                     │
│                                                                              │
│   1. Command-line arguments                                                  │
│      └── floe run --env production                                          │
│                                                                              │
│   2. Environment variables                                                   │
│      └── FLOE_COMPUTE_TARGET=snowflake                                      │
│                                                                              │
│   3. .env file (local development)                                          │
│      └── .env                                                               │
│                                                                              │
│   4. floe.yaml (project configuration)                                      │
│      └── floe.yaml                                                          │
│                                                                              │
│   5. manifest.yaml (platform constraints)                          │
│      └── Inherited, cannot override                                         │
│                                                                              │
│   6. Default values (built-in)                                              │
│      └── floe-core defaults                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Data Mesh Model (Federated Governance)

For Data Mesh deployments, configuration inheritance follows the three-tier hierarchy:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATA MESH CONFIGURATION PRECEDENCE                      │
│                      (highest to lowest for data products)                   │
│                                                                              │
│   1. Command-line arguments                                                  │
│                                                                              │
│   2. Environment variables                                                   │
│                                                                              │
│   3. floe.yaml (data product configuration)                                 │
│      └── kind: DataProduct                                                  │
│                                                                              │
│   4. domain-manifest.yaml (domain constraints)                              │
│      └── Inherited from domain, can extend but not override                 │
│                                                                              │
│   5. enterprise-manifest.yaml (global constraints)                          │
│      └── Inherited from enterprise, cannot override                         │
│                                                                              │
│   6. Default values (built-in)                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Inheritance Rules:**
- Enterprise policies are enforced globally (cannot be weakened)
- Domains can add stricter policies (but not weaker)
- Data products inherit all parent policies
- Plugin choices flow down: enterprise approves → domain selects → product inherits

### 2.2 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLOE_ARTIFACTS_PATH` | Path to compiled artifacts | `.floe/artifacts.json` |
| `FLOE_COMPUTE_TARGET` | Override compute target | from floe.yaml |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTel collector endpoint | None (disabled) |
| `OTEL_SERVICE_NAME` | Service name for telemetry | `floe` |
| `OPENLINEAGE_URL` | Marquez/lineage endpoint | None (disabled) |
| `OPENLINEAGE_NAMESPACE` | Lineage namespace | `floe` |

### 2.3 Secret Management

```yaml
# manifest.yaml - Compute and secret configuration (Platform Team)
plugins:
  compute:
    type: snowflake
    connection_secret_ref: snowflake-credentials  # K8s secret name

# Environment variable injection
# dbt will use: {{ env_var('SNOWFLAKE_PASSWORD') }}
```

```yaml
# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: snowflake-credentials
type: Opaque
stringData:
  SNOWFLAKE_ACCOUNT: "xxx.us-east-1"
  SNOWFLAKE_USER: "user"
  SNOWFLAKE_PASSWORD: "secret"
```

### 2.4 Configuration Validation

```python
# floe_core/config.py
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

class FloeSettings(BaseSettings):
    """Runtime configuration from environment."""

    artifacts_path: str = Field(
        default=".floe/artifacts.json",
        alias="FLOE_ARTIFACTS_PATH",
    )
    compute_target: str | None = Field(
        default=None,
        alias="FLOE_COMPUTE_TARGET",
    )
    otel_endpoint: str | None = Field(
        default=None,
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    lineage_url: str | None = Field(
        default=None,
        alias="OPENLINEAGE_URL",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

---

## 3. Security

### 3.1 Security Principles

| Principle | Implementation |
|-----------|----------------|
| **No secrets in code** | Environment variables, K8s secrets |
| **Least privilege** | Minimal IAM/RBAC permissions |
| **Secure defaults** | TLS enabled, auth required in prod |
| **Dependency scanning** | Dependabot, Snyk in CI |
| **Input validation** | Pydantic schemas, SQL parameterization |

### 3.2 Authentication Patterns

```python
# For standalone mode: no auth (local development)
# For K8s mode: OIDC/JWT via ingress or service mesh

# Example: Dagster with OIDC
# values.yaml
dagster:
  webserver:
    auth:
      enabled: true
      provider: oidc
      oidcConfig:
        clientId: dagster
        issuerUrl: https://auth.example.com
```

### 3.3 Network Security

```yaml
# NetworkPolicy for floe namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: floe
  namespace: floe
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - port: 3000  # Dagster
  egress:
    # Allow to PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app: postgresql
      ports:
        - port: 5432
    # Allow to external data warehouses
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - port: 443
```

### 3.4 Supply Chain Security

```yaml
# .github/workflows/security.yml
name: Security Scan

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Dependency scan
        uses: snyk/actions/python@master
        with:
          args: --severity-threshold=high

      - name: Container scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/floe/dagster:${{ github.sha }}
          severity: HIGH,CRITICAL
```

---

## 4. Extensibility

### 4.1 Plugin Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PLUGIN SYSTEM                                         │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  Entry Point Groups (registered via pyproject.toml)                  │   │
│   │                                                                      │   │
│   │  floe.orchestrators                                                 │   │
│   │  ├── dagster = floe_orchestrator_dagster:DagsterPlugin             │   │
│   │  └── airflow = floe_orchestrator_airflow:AirflowPlugin             │   │
│   │                                                                      │   │
│   │  floe.compute                                                       │   │
│   │  ├── duckdb = floe_compute_duckdb:DuckDBPlugin                     │   │
│   │  ├── spark = floe_compute_spark:SparkPlugin                        │   │
│   │  └── snowflake = floe_compute_snowflake:SnowflakePlugin            │   │
│   │                                                                      │   │
│   │  floe.catalogs                                                      │   │
│   │  ├── polaris = floe_catalog_polaris:PolarisPlugin                  │   │
│   │  └── glue = floe_catalog_glue:GluePlugin                           │   │
│   │                                                                      │   │
│   │  floe.semantic_layers                                               │   │
│   │  └── cube = floe_semantic_cube:CubePlugin                          │   │
│   │                                                                      │   │
│   │  floe.ingestion                                                     │   │
│   │  └── dlt = floe_ingestion_dlt:DltPlugin                            │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

See [04-building-blocks](04-building-blocks.md) for ABC interface definitions.

### 4.2 Custom Transform Example

```python
# my_plugin/transforms.py
from abc import ABC, abstractmethod
from floe_core import CompiledArtifacts, TransformConfig

class TransformExecutor(ABC):
    """Base class for transform executors."""

    @abstractmethod
    def execute(
        self,
        config: TransformConfig,
        artifacts: CompiledArtifacts,
    ) -> None:
        """Execute the transform."""
        pass

class PythonTransformExecutor(TransformExecutor):
    """Execute Python transforms."""

    def execute(
        self,
        config: TransformConfig,
        artifacts: CompiledArtifacts,
    ) -> None:
        """Run a Python script as a transform."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "transform",
            config.path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Call the transform function
        module.transform(artifacts)
```

```toml
# pyproject.toml for custom plugin
[project.entry-points."floe.transforms"]
python = "my_plugin.transforms:PythonTransformExecutor"
```

### 4.3 Custom Compute Plugin Example

```python
# my_plugin/compute.py
from floe_core.interfaces.compute import ComputePlugin

class MotherDuckPlugin(ComputePlugin):
    """MotherDuck (cloud DuckDB) compute plugin."""

    name = "motherduck"
    version = "1.0.0"
    is_self_hosted = False  # Cloud service

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        """Generate dbt profile for MotherDuck."""
        return {
            "type": "duckdb",
            "path": f"md:{config.database or 'my_db'}",
            "extensions": ["motherduck"],
            "settings": {
                "motherduck_token": "{{ env_var('MOTHERDUCK_TOKEN') }}",
            },
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-duckdb>=1.7.0"]
```

```toml
# pyproject.toml for custom plugin
[project.entry-points."floe.compute"]
motherduck = "my_plugin.compute:MotherDuckPlugin"
```

### 4.4 Plugin Discovery

```python
# floe_core/plugins.py
from importlib.metadata import entry_points

def discover_transforms() -> dict[str, type]:
    """Discover installed transform plugins."""
    eps = entry_points(group="floe.transforms")
    return {ep.name: ep.load() for ep in eps}

def discover_targets() -> dict[str, type]:
    """Discover installed compute target plugins."""
    eps = entry_points(group="floe.targets")
    return {ep.name: ep.load() for ep in eps}

# Usage
transforms = discover_transforms()
# {'dbt': DbtTransformExecutor, 'python': PythonTransformExecutor, ...}

executor_class = transforms[config.type]
executor = executor_class()
executor.execute(config, artifacts)
```

---

## 5. Error Handling

### 5.1 Error Categories

```python
# floe_core/errors.py
class FloeError(Exception):
    """Base exception for all Floe errors."""
    pass

class ConfigurationError(FloeError):
    """Invalid configuration in floe.yaml."""
    pass

class ValidationError(ConfigurationError):
    """Schema validation failure."""
    pass

class CompilationError(FloeError):
    """Failed to compile artifacts."""
    pass

class ExecutionError(FloeError):
    """Pipeline execution failure."""
    pass

class DbtError(ExecutionError):
    """dbt command failure."""
    pass

class ConnectionError(ExecutionError):
    """Failed to connect to compute target."""
    pass
```

### 5.2 Error Handling Pattern

```python
# floe_cli/commands/run.py
import sys
from rich.console import Console
from floe_core.errors import FloeError, ConfigurationError, ExecutionError

console = Console()

def run_pipeline(config_path: Path, env: str):
    """Execute pipeline with proper error handling."""
    try:
        # Load and validate
        artifacts = load_artifacts(config_path)

        # Execute
        execute(artifacts, env)

        console.print("[green]✓ Pipeline completed successfully[/green]")

    except ConfigurationError as e:
        console.print(f"[red]✗ Configuration error:[/red] {e}")
        console.print("\nCheck your floe.yaml file for errors.")
        sys.exit(1)

    except ExecutionError as e:
        console.print(f"[red]✗ Execution failed:[/red] {e}")

        if e.trace_id:
            console.print(f"\nTrace ID: {e.trace_id}")
            console.print(f"View trace: {get_trace_url(e.trace_id)}")

        sys.exit(2)

    except FloeError as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Unexpected error:[/red] {e}")
        console.print("\nPlease report this issue at:")
        console.print("https://github.com/floe/floe/issues")
        sys.exit(99)
```

### 5.3 Retry Patterns

```python
# floe_core/retry.py
import time
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")

def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = delay_seconds

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        delay *= backoff_factor

            raise last_exception

        return wrapper
    return decorator

# Usage
@retry(max_attempts=3, exceptions=(ConnectionError,))
def connect_to_warehouse(config: dict):
    """Connect with automatic retry."""
    ...
```

---

## 6. Logging

### 6.1 Structured Logging

```python
# floe_core/logging.py
import structlog
from opentelemetry import trace

def configure_logging(level: str = "INFO"):
    """Configure structured logging with trace correlation."""

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            add_trace_context,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

def add_trace_context(logger, method_name, event_dict):
    """Add OpenTelemetry trace context to logs."""
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

# Usage
import structlog
log = structlog.get_logger()

log.info("starting_compilation", spec_path="floe.yaml")
# Output: {"event": "starting_compilation", "spec_path": "floe.yaml",
#          "level": "info", "timestamp": "2024-...", "trace_id": "abc..."}
```

