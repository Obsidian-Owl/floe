# ADR-0035: Telemetry and Lineage Backend Plugins

## Status

Accepted

## Context

ADR-0006 established **OpenTelemetry as the standard** for observability emission (traces, metrics, logs). However, it left two backend layers unspecified:

1. **Telemetry backends**: Storage and visualization for traces/metrics/logs (OTLP protocol)
2. **Lineage backends**: Storage and visualization for data lineage (OpenLineage protocol)

### Current Architecture: Three-Layer Observability Model

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: EMISSION (Enforced)                                      │
│                                                                      │
│  OpenTelemetry SDK in data pipelines/jobs                           │
│  - Python: opentelemetry-sdk, opentelemetry-instrumentation-*       │
│  - Emits OTLP to Collector                                          │
│  - Enforced standard (ADR-0006)                                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ OTLP (gRPC or HTTP)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: COLLECTION (Enforced)                                    │
│                                                                      │
│  OTLP Collector (deployed in K8s)                                   │
│  - Receives OTLP from all jobs                                      │
│  - Batching, sampling, enrichment                                   │
│  - Exports to backend-specific formats                              │
│  - Enforced deployment (ADR-0006)                                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Backend-specific protocol
                                │ (Jaeger gRPC, Datadog API, etc.)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: BACKEND (Pluggable)                                      │
│                                                                      │
│  TelemetryBackendPlugin: OTLP backends                              │
│  - Jaeger (self-hosted OSS)                                         │
│  - Datadog APM (SaaS)                                               │
│  - Grafana Cloud (SaaS)                                             │
│  - AWS X-Ray (AWS-native)                                           │
│                                                                      │
│  LineageBackendPlugin: OpenLineage backends (INDEPENDENT)           │
│  - Marquez (OSS, reference implementation)                          │
│  - Atlan (SaaS, data catalog + lineage)                             │
│  - OpenMetadata (OSS, unified metadata)                             │
└─────────────────────────────────────────────────────────────────────┘
```

### The Problem: Unified ObservabilityPlugin Couples Independent Systems

Initial design (now deprecated) used a single `ObservabilityPlugin` that configured both:
- OTLP backends (via OTLP Collector exporter config)
- OpenLineage backends (via OpenLineage transport config)

**Issues with unified approach:**

| Issue | Impact |
|-------|--------|
| **Architectural coupling** | OTLP uses Collector layer (3-layer), OpenLineage uses direct HTTP (2-layer) |
| **Independent evolution** | OpenLineage backends evolve separately from OTLP backends |
| **Mixed backend scenarios** | Cannot use Datadog for telemetry + Atlan for lineage |
| **Violation of SRP** | Single plugin responsible for two unrelated concerns |
| **Confusing abstraction** | Plugin methods couple unrelated protocols (OTLP ≠ OpenLineage) |

### Organizations Have Different Backend Needs

| Organization Type | Telemetry Backend | Lineage Backend | Rationale |
|-------------------|------------------|----------------|-----------|
| **Startup** | Jaeger (self-hosted) | Marquez (self-hosted) | Cost-effective, full ownership |
| **Enterprise with Datadog** | Datadog APM | Atlan | Existing investment, unified observability + governance |
| **Cloud-native SaaS** | Grafana Cloud | OpenMetadata | Managed telemetry, OSS lineage |
| **Regulated industry** | Self-hosted Jaeger | Self-hosted Marquez | Data sovereignty requirements |
| **AWS-first shop** | AWS X-Ray | AWS Glue + Marquez | Native AWS integration + open lineage |

**Requirement:** Telemetry and lineage backends must be **independently pluggable**.

## Decision

Create **two separate plugin interfaces** for independently pluggable telemetry and lineage backends:

1. **TelemetryBackendPlugin**: Configures OTLP backends (Jaeger, Datadog, Grafana Cloud)
2. **LineageBackendPlugin**: Configures OpenLineage backends (Marquez, Atlan, OpenMetadata)

### Architecture: Split Plugin Model

```
┌─────────────────────────────────────────────────────────────────────┐
│  TELEMETRY PATH (OTLP Protocol)                                    │
│                                                                      │
│  OTel SDK → OTLP Collector → TelemetryBackendPlugin                │
│              (Layer 2)         (Layer 3)                            │
│                                                                      │
│  TelemetryBackendPlugin responsibilities:                           │
│  - Generate OTLP Collector exporter config                          │
│  - Provide Helm values for backend services (if self-hosted)        │
│  - Validate connection to backend                                   │
│                                                                      │
│  Entry point: floe.telemetry_backends                               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  LINEAGE PATH (OpenLineage Protocol) - INDEPENDENT                 │
│                                                                      │
│  OpenLineage SDK → LineageBackendPlugin                             │
│  (Dagster/dbt)     (Direct HTTP transport)                          │
│                                                                      │
│  LineageBackendPlugin responsibilities:                             │
│  - Generate OpenLineage HTTP transport config                       │
│  - Provide namespace strategy for lineage events                    │
│  - Provide Helm values for backend services (if self-hosted)        │
│  - Validate connection to backend                                   │
│                                                                      │
│  Entry point: floe.lineage_backends                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### TelemetryBackendPlugin Interface

```python
from abc import ABC, abstractmethod
from typing import Any

class TelemetryBackendPlugin(ABC):
    """Plugin interface for OTLP telemetry backends.

    Responsibilities:
    - Configure OTLP Collector exporter for backend-specific protocol
    - Provide Helm values for deploying backend services (if self-hosted)
    - Validate connection to backend

    Plugin Lifecycle:
    1. Discovered via entry point: floe.telemetry_backends
    2. Instantiated by PluginRegistry
    3. Invoked during compilation (generates OTLP Collector config)
    4. Invoked during deployment (generates Helm values)
    """

    # Plugin metadata
    name: str                 # e.g., "jaeger", "datadog", "grafana-cloud"
    version: str              # Plugin version (semver)
    floe_api_version: str     # Supported floe-core API version

    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector exporter configuration.

        The OTLP Collector uses this config to export traces/metrics/logs
        to the telemetry backend.

        Returns:
            Dictionary matching OTLP Collector config schema.
            Must include 'exporters' section with backend-specific config.

        Example (Jaeger):
            {
                "exporters": {
                    "jaeger": {
                        "endpoint": "jaeger:14250",
                        "tls": {"insecure": true}
                    }
                },
                "service": {
                    "pipelines": {
                        "traces": {
                            "receivers": ["otlp"],
                            "processors": ["batch"],
                            "exporters": ["jaeger"]
                        }
                    }
                }
            }

        Example (Datadog):
            {
                "exporters": {
                    "datadog": {
                        "api": {
                            "key": "${env:DD_API_KEY}",
                            "site": "datadoghq.com"
                        }
                    }
                },
                "service": {
                    "pipelines": {
                        "traces": {
                            "receivers": ["otlp"],
                            "processors": ["batch"],
                            "exporters": ["datadog"]
                        },
                        "metrics": {
                            "receivers": ["otlp"],
                            "processors": ["batch"],
                            "exporters": ["datadog"]
                        }
                    }
                }
            }
        """
        pass

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        For self-hosted backends (Jaeger), this provides Helm chart values
        for deploying the backend to Kubernetes.

        For SaaS backends (Datadog, Grafana Cloud), this returns empty dict.

        Returns:
            Helm values dictionary for backend chart.
            Empty dict if backend is external (SaaS).

        Example (Jaeger self-hosted):
            {
                "jaeger": {
                    "enabled": true,
                    "storage": {
                        "type": "memory"  # or "elasticsearch"
                    },
                    "query": {
                        "service": {
                            "type": "LoadBalancer"
                        }
                    }
                }
            }

        Example (Datadog SaaS):
            {}  # No services to deploy
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate connection to backend.

        Checks that backend is reachable and credentials are valid.
        Called during platform validation (floe validate).

        Returns:
            True if connection successful, False otherwise.

        Raises:
            ConnectionError: If backend unreachable with actionable error message.
            CredentialError: If credentials invalid or missing.
        """
        pass
```

### LineageBackendPlugin Interface

```python
from abc import ABC, abstractmethod
from typing import Any

class LineageBackendPlugin(ABC):
    """Plugin interface for OpenLineage backends.

    Responsibilities:
    - Configure OpenLineage HTTP transport for backend-specific endpoint
    - Define namespace strategy for lineage events
    - Provide Helm values for deploying backend services (if self-hosted)
    - Validate connection to backend

    Plugin Lifecycle:
    1. Discovered via entry point: floe.lineage_backends
    2. Instantiated by PluginRegistry
    3. Invoked during compilation (generates OpenLineage transport config)
    4. Invoked during deployment (generates Helm values)
    """

    # Plugin metadata
    name: str                 # e.g., "marquez", "atlan", "openmetadata"
    version: str              # Plugin version (semver)
    floe_api_version: str     # Supported floe-core API version

    @abstractmethod
    def get_transport_config(self) -> dict[str, Any]:
        """Generate OpenLineage HTTP transport configuration.

        OpenLineage events are emitted from Dagster assets and dbt runs.
        This config tells OpenLineage SDK where to send events via HTTP.

        Returns:
            Dictionary with 'type' (must be 'http') and endpoint config.

        Example (Marquez):
            {
                "type": "http",
                "url": "http://marquez:5000/api/v1/lineage",
                "timeout": 5.0,
                "endpoint": "api/v1/lineage"
            }

        Example (Atlan with auth):
            {
                "type": "http",
                "url": "https://example.atlan.com/api/service/openlineage/event",
                "auth": {
                    "type": "api_key",
                    "api_key": "${env:ATLAN_API_KEY}"
                },
                "timeout": 5.0
            }

        Example (OpenMetadata):
            {
                "type": "http",
                "url": "http://openmetadata:8585/api/v1/lineage",
                "auth": {
                    "type": "bearer",
                    "token": "${env:OPENMETADATA_TOKEN}"
                },
                "timeout": 5.0
            }
        """
        pass

    @abstractmethod
    def get_namespace_strategy(self) -> dict[str, Any]:
        """Define namespace strategy for lineage events.

        OpenLineage events include a 'namespace' field that identifies
        the data platform. Different backends have different conventions.

        Returns:
            Dictionary with namespace strategy configuration.

        Example (default strategy):
            {
                "strategy": "environment_based",
                "template": "floe-{environment}",  # e.g., "floe-production"
                "environment_var": "FLOE_ENVIRONMENT"
            }

        Example (custom strategy):
            {
                "strategy": "custom",
                "namespace": "my-company-data-platform"
            }

        Example (backend-specific strategy):
            {
                "strategy": "backend_managed",
                "description": "Backend (Atlan) manages namespace via API metadata"
            }
        """
        pass

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        For self-hosted backends (Marquez, OpenMetadata), this provides
        Helm chart values for deploying the backend to Kubernetes.

        For SaaS backends (Atlan), this returns empty dict.

        Returns:
            Helm values dictionary for backend chart.
            Empty dict if backend is external (SaaS).

        Example (Marquez self-hosted):
            {
                "marquez": {
                    "enabled": true,
                    "db": {
                        "type": "postgresql",
                        "host": "postgresql",
                        "port": 5432
                    },
                    "service": {
                        "type": "ClusterIP"
                    }
                }
            }

        Example (Atlan SaaS):
            {}  # No services to deploy
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate connection to backend.

        Checks that backend is reachable and credentials are valid.
        Called during platform validation (floe validate).

        Returns:
            True if connection successful, False otherwise.

        Raises:
            ConnectionError: If backend unreachable with actionable error message.
            CredentialError: If credentials invalid or missing.
        """
        pass
```

### Plugin Registration

```python
# pyproject.toml for floe-telemetry-jaeger plugin
[project.entry-points."floe.telemetry_backends"]
jaeger = "floe_telemetry_jaeger:JaegerPlugin"

# pyproject.toml for floe-telemetry-datadog plugin
[project.entry-points."floe.telemetry_backends"]
datadog = "floe_telemetry_datadog:DatadogPlugin"

# pyproject.toml for floe-lineage-marquez plugin
[project.entry-points."floe.lineage_backends"]
marquez = "floe_lineage_marquez:MarquezPlugin"

# pyproject.toml for floe-lineage-atlan plugin
[project.entry-points."floe.lineage_backends"]
atlan = "floe_lineage_atlan:AtlanPlugin"
```

### Platform Configuration

```yaml
# platform-manifest.yaml
plugins:
  telemetry_backend: jaeger        # Discovered via floe.telemetry_backends
  lineage_backend: marquez          # Discovered via floe.lineage_backends

# Mixed backends example:
plugins:
  telemetry_backend: datadog        # Datadog APM for telemetry
  lineage_backend: atlan             # Atlan for lineage/governance
```

## Consequences

### Positive

- **Architectural correctness** - Respects independent evolution of OTLP vs OpenLineage
- **Composability** - Mix and match backends (Datadog telemetry + Atlan lineage)
- **Single Responsibility Principle** - Each plugin has one clear concern
- **Flexibility** - Organizations choose backends independently without forking
- **Testability** - Mock each plugin interface separately for unit tests
- **Extensibility** - Community can build plugins for custom backends
- **Standards compliance** - OTLP and OpenLineage configs follow respective standards

### Negative

- **More plugin types** - 13 plugin types instead of 12 (split from 1 to 2)
- **Plugin development** - Requires implementing two ABCs instead of one unified interface
- **Discovery complexity** - Two entry point groups instead of one
- **Initial setup** - Must install two plugin packages instead of one

### Neutral

- **Default plugins** - `floe-telemetry-jaeger` and `floe-lineage-marquez` ship together (batteries included)
- **Migration path** - Existing unified ObservabilityPlugin deprecated but coexists during transition
- **Ecosystem growth** - Community maintains backend-specific plugins

## Implementation Details

### Reference Implementation: JaegerPlugin (Telemetry)

```python
# floe-telemetry-jaeger/src/floe_telemetry_jaeger/plugin.py
from __future__ import annotations

from typing import Any
from floe_core.plugins import TelemetryBackendPlugin


class JaegerPlugin(TelemetryBackendPlugin):
    """Telemetry backend plugin for Jaeger (self-hosted OSS)."""

    name = "jaeger"
    version = "0.1.0"
    floe_api_version = "2.0.0"

    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector config for Jaeger."""
        return {
            "exporters": {
                "jaeger": {
                    "endpoint": "jaeger:14250",
                    "tls": {"insecure": True},
                }
            },
            "service": {
                "pipelines": {
                    "traces": {
                        "receivers": ["otlp"],
                        "processors": ["batch"],
                        "exporters": ["jaeger"],
                    }
                }
            },
        }

    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying Jaeger."""
        return {
            "jaeger": {
                "enabled": True,
                "storage": {
                    "type": "memory",  # In-memory for local dev
                },
                "query": {
                    "service": {
                        "type": "LoadBalancer",
                    }
                },
            }
        }

    def validate_connection(self) -> bool:
        """Validate Jaeger is reachable."""
        import requests
        try:
            response = requests.get("http://jaeger:16686/", timeout=5.0)
            return response.status_code == 200
        except requests.RequestException:
            return False
```

### Reference Implementation: MarquezPlugin (Lineage)

```python
# floe-lineage-marquez/src/floe_lineage_marquez/plugin.py
from __future__ import annotations

from typing import Any
from floe_core.plugins import LineageBackendPlugin


class MarquezPlugin(LineageBackendPlugin):
    """Lineage backend plugin for Marquez (OSS reference implementation)."""

    name = "marquez"
    version = "0.1.0"
    floe_api_version = "2.0.0"

    def get_transport_config(self) -> dict[str, Any]:
        """Generate OpenLineage HTTP transport config for Marquez."""
        return {
            "type": "http",
            "url": "http://marquez:5000/api/v1/lineage",
            "timeout": 5.0,
            "endpoint": "api/v1/lineage",
        }

    def get_namespace_strategy(self) -> dict[str, Any]:
        """Define namespace strategy for Marquez."""
        return {
            "strategy": "environment_based",
            "template": "floe-{environment}",
            "environment_var": "FLOE_ENVIRONMENT",
        }

    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying Marquez."""
        return {
            "marquez": {
                "enabled": True,
                "db": {
                    "type": "postgresql",
                    "host": "postgresql",
                    "port": 5432,
                },
                "service": {
                    "type": "ClusterIP",
                },
            }
        }

    def validate_connection(self) -> bool:
        """Validate Marquez is reachable."""
        import requests
        try:
            response = requests.get("http://marquez:5000/api/v1/namespaces", timeout=5.0)
            return response.status_code == 200
        except requests.RequestException:
            return False
```

### Reference Implementation: DatadogPlugin (Telemetry)

```python
# floe-telemetry-datadog/src/floe_telemetry_datadog/plugin.py
from __future__ import annotations

import os
from typing import Any
from floe_core.plugins import TelemetryBackendPlugin


class DatadogPlugin(TelemetryBackendPlugin):
    """Telemetry backend plugin for Datadog APM (SaaS)."""

    name = "datadog"
    version = "0.1.0"
    floe_api_version = "2.0.0"

    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector config for Datadog."""
        return {
            "exporters": {
                "datadog": {
                    "api": {
                        "key": "${env:DD_API_KEY}",
                        "site": os.getenv("DD_SITE", "datadoghq.com"),
                    }
                }
            },
            "service": {
                "pipelines": {
                    "traces": {
                        "receivers": ["otlp"],
                        "processors": ["batch"],
                        "exporters": ["datadog"],
                    },
                    "metrics": {
                        "receivers": ["otlp"],
                        "processors": ["batch"],
                        "exporters": ["datadog"],
                    },
                }
            },
        }

    def get_helm_values(self) -> dict[str, Any]:
        """No services to deploy for Datadog SaaS."""
        return {}  # External SaaS backend

    def validate_connection(self) -> bool:
        """Validate DD_API_KEY is set."""
        return "DD_API_KEY" in os.environ
```

### Reference Implementation: AtlanPlugin (Lineage)

```python
# floe-lineage-atlan/src/floe_lineage_atlan/plugin.py
from __future__ import annotations

import os
from typing import Any
from floe_core.plugins import LineageBackendPlugin


class AtlanPlugin(LineageBackendPlugin):
    """Lineage backend plugin for Atlan (SaaS data catalog + lineage)."""

    name = "atlan"
    version = "0.1.0"
    floe_api_version = "2.0.0"

    def get_transport_config(self) -> dict[str, Any]:
        """Generate OpenLineage HTTP transport config for Atlan."""
        return {
            "type": "http",
            "url": f"https://{os.getenv('ATLAN_HOST')}/api/service/openlineage/event",
            "auth": {
                "type": "api_key",
                "api_key": "${env:ATLAN_API_KEY}",
            },
            "timeout": 5.0,
        }

    def get_namespace_strategy(self) -> dict[str, Any]:
        """Atlan manages namespace via backend metadata."""
        return {
            "strategy": "backend_managed",
            "description": "Atlan extracts namespace from connection metadata",
        }

    def get_helm_values(self) -> dict[str, Any]:
        """No services to deploy for Atlan SaaS."""
        return {}  # External SaaS backend

    def validate_connection(self) -> bool:
        """Validate Atlan credentials."""
        return all(k in os.environ for k in ["ATLAN_HOST", "ATLAN_API_KEY"])
```

## Decision Criteria: When to Split Plugins

Per ADR-0037 (Composability Principle):

| Criterion | TelemetryBackendPlugin vs LineageBackendPlugin | Rationale |
|-----------|-------------------------------------------|-----------|
| **Protocol independence** | OTLP (3-layer) vs OpenLineage (2-layer, HTTP-only) | Architecturally distinct transport mechanisms |
| **Independent evolution** | OTLP standards evolve separately from OpenLineage | Different standards bodies, release cycles |
| **Mixed backend scenarios** | Datadog telemetry + Atlan lineage | Enterprise preference for best-of-breed |
| **Single Responsibility** | Telemetry ≠ Lineage | Different concerns, different backends |

**Why split:**
- OpenLineage has NO OTLP transport in ecosystem (researched, deferred to Epic 8+)
- Organizations want mixed backends (e.g., Datadog + Atlan)
- OTLP Collector architecture doesn't apply to OpenLineage (direct HTTP)
- Simplifies plugin implementation (single concern)

**Why NOT unified:**
- Violates SRP (two unrelated concerns)
- Prevents mixed backends
- Couples independent protocols
- Confusing abstraction (methods unrelated)

## Migration Strategy

### Phase 1: Deprecate ObservabilityPlugin (ADR Update)

Update ADR-0035 to document split architecture (this revision).

```python
# floe-core: Mark ObservabilityPlugin as deprecated
class ObservabilityPlugin(ABC):
    """DEPRECATED: Use TelemetryBackendPlugin and LineageBackendPlugin instead.

    This unified interface will be removed in floe-core 3.0.0.
    See ADR-0035 for migration guide.
    """
    pass
```

### Phase 2: Implement New Interfaces (Backward Compatible)

Create TelemetryBackendPlugin and LineageBackendPlugin ABCs alongside deprecated ObservabilityPlugin.

```python
# floe-core/src/floe_core/plugins.py
from abc import ABC, abstractmethod

# New interfaces
class TelemetryBackendPlugin(ABC): ...
class LineageBackendPlugin(ABC): ...

# Deprecated (coexists during migration)
class ObservabilityPlugin(ABC): ...
```

### Phase 3: Migrate Reference Implementations

Split existing plugins:
- `floe-observability-jaeger` → `floe-telemetry-jaeger` + `floe-lineage-marquez`
- `floe-observability-datadog` → `floe-telemetry-datadog` + (Atlan/OpenMetadata)

### Phase 4: Update Compiler (Dual Support)

Compiler supports BOTH legacy unified plugin AND new split plugins:

```yaml
# Legacy (deprecated, still works)
plugins:
  observability: jaeger

# New split approach (preferred)
plugins:
  telemetry_backend: jaeger
  lineage_backend: marquez
```

### Phase 5: Remove Deprecated Interface (Breaking Change)

Remove `ObservabilityPlugin` ABC in floe-core 3.0.0 (major version bump).

## Testing Strategy

### Unit Tests (Mock Plugins)

```python
# tests/unit/test_telemetry_plugin.py
from unittest.mock import Mock
from floe_core.plugins import TelemetryBackendPlugin


def test_compiler_with_mock_telemetry():
    """Test compiler with mocked telemetry plugin."""
    mock_plugin = Mock(spec=TelemetryBackendPlugin)
    mock_plugin.get_otlp_exporter_config.return_value = {
        "exporters": {"mock": {}}
    }

    compiler = Compiler(telemetry_plugin=mock_plugin)
    artifacts = compiler.compile(spec)

    assert "otlp_collector_config" in artifacts
    mock_plugin.get_otlp_exporter_config.assert_called_once()


# tests/unit/test_lineage_plugin.py
from unittest.mock import Mock
from floe_core.plugins import LineageBackendPlugin


def test_compiler_with_mock_lineage():
    """Test compiler with mocked lineage plugin."""
    mock_plugin = Mock(spec=LineageBackendPlugin)
    mock_plugin.get_transport_config.return_value = {
        "type": "http",
        "url": "http://mock:5000/api/v1/lineage"
    }

    compiler = Compiler(lineage_plugin=mock_plugin)
    artifacts = compiler.compile(spec)

    assert "openlineage_config" in artifacts
    mock_plugin.get_transport_config.assert_called_once()
```

### Integration Tests (Real Plugins)

```python
# tests/integration/test_jaeger_plugin.py
from floe_telemetry_jaeger import JaegerPlugin


def test_jaeger_plugin_generates_valid_config():
    """Test JaegerPlugin generates valid OTLP Collector config."""
    plugin = JaegerPlugin()
    config = plugin.get_otlp_exporter_config()

    assert "exporters" in config
    assert "jaeger" in config["exporters"]
    assert config["exporters"]["jaeger"]["endpoint"] == "jaeger:14250"


# tests/integration/test_marquez_plugin.py
from floe_lineage_marquez import MarquezPlugin


def test_marquez_plugin_generates_valid_config():
    """Test MarquezPlugin generates valid OpenLineage transport config."""
    plugin = MarquezPlugin()
    config = plugin.get_transport_config()

    assert config["type"] == "http"
    assert "marquez" in config["url"]
    assert config["timeout"] == 5.0
```

## Anti-Patterns

### DON'T: Unified plugin for independent protocols

```python
# ❌ ANTI-PATTERN: Couples OTLP and OpenLineage
class ObservabilityPlugin(ABC):
    @abstractmethod
    def get_otlp_exporter_config(self) -> dict: ...  # OTLP concern

    @abstractmethod
    def get_lineage_config(self) -> dict: ...  # OpenLineage concern (unrelated!)
```

### DON'T: Hardcode backend logic in core

```python
# ❌ ANTI-PATTERN: Core knows about specific backends
def get_telemetry_config(config: dict) -> dict:
    if config["backend"] == "jaeger":
        return {"endpoint": "jaeger:14250"}
    elif config["backend"] == "datadog":
        return {"api_key": os.getenv("DD_API_KEY")}
```

### DO: Separate plugins for separate concerns

```python
# ✅ CORRECT: Two independent plugins
class TelemetryBackendPlugin(ABC):
    """OTLP backend configuration ONLY."""
    @abstractmethod
    def get_otlp_exporter_config(self) -> dict: ...

class LineageBackendPlugin(ABC):
    """OpenLineage backend configuration ONLY."""
    @abstractmethod
    def get_transport_config(self) -> dict: ...
```

## Security Considerations

### Credential Management

- **API Keys** (Datadog, Atlan): Use K8s Secrets, environment variables
- **NEVER** hardcode credentials in platform-manifest.yaml
- Plugins access credentials via `${env:VAR_NAME}` syntax
- `validate_connection()` method checks presence before deployment

### Transport Security

- **OTLP Collector**: Production MUST use TLS for Collector → Backend
- **OpenLineage HTTP**: HTTPS for SaaS backends (Atlan)
- **Authentication**: SaaS backends require API key/bearer token
- **Network policies**: K8s NetworkPolicy restricts backend access

## Open Questions

### Q: What about custom telemetry/lineage backends?

**A:** Organizations implement respective plugin interface and register via entry points. No core changes needed.

Example: Custom enterprise telemetry backend

```python
# my-company-telemetry/src/my_company/plugin.py
class EnterpriseTelemetryPlugin(TelemetryBackendPlugin):
    name = "enterprise-telemetry"
    # Implement interface for proprietary backend
```

### Q: Can we use different backends per environment (dev vs prod)?

**A:** Yes, platform-manifest.yaml is environment-specific. Use different manifests:

```yaml
# dev/platform-manifest.yaml
plugins:
  telemetry_backend: jaeger  # Self-hosted for dev
  lineage_backend: marquez

# prod/platform-manifest.yaml
plugins:
  telemetry_backend: datadog  # SaaS for production
  lineage_backend: atlan
```

### Q: How do we handle backend-specific advanced features?

**A:** Plugin can include extra methods beyond ABC for backend-specific features. Core uses only ABC methods. Users can access plugin directly for advanced features via PluginRegistry.

## References

- [ADR-0006: OpenTelemetry Observability](0006-opentelemetry-observability.md) - Establishes OTel standard (Layer 1 + Layer 2)
- [ADR-0007: OpenLineage Data Lineage](0007-openlineage-data-lineage.md) - Establishes OpenLineage standard
- [ADR-0037: Composability Principle](0037-composability-principle.md) - Plugin architecture rationale
- [plugin-architecture.md](../plugin-architecture.md) - Plugin patterns
- [interfaces/telemetry-backend-plugin.md](../interfaces/telemetry-backend-plugin.md) + [lineage-backend-plugin.md](../interfaces/lineage-backend-plugin.md) - ABC definitions
- **Requirements Traceability:**
  - [REQ-051 to REQ-055](../../plan/requirements/01-plugin-architecture/06-observability-plugin.md) - TelemetryBackendPlugin requirements
  - [REQ-056 to REQ-060](../../plan/requirements/01-plugin-architecture/06-observability-plugin.md) - LineageBackendPlugin requirements
  - [REQ-002](../../plan/requirements/01-plugin-architecture/01-plugin-discovery.md) - Plugin discovery (14 entry point groups)
- **Industry References:**
  - [OpenTelemetry Collector Configuration](https://opentelemetry.io/docs/collector/configuration/)
  - [OpenLineage Transport Configuration](https://openlineage.io/docs/client/python)
  - [Jaeger Deployment](https://www.jaegertracing.io/docs/latest/deployment/)
  - [Datadog OTLP Ingestion](https://docs.datadoghq.com/tracing/trace_collection/open_standards/otlp_ingest_in_the_agent/)
  - [Marquez Documentation](https://marquezproject.github.io/marquez/)
  - [Atlan OpenLineage Integration](https://ask.atlan.com/hc/en-us/articles/8312499534097-OpenLineage)
