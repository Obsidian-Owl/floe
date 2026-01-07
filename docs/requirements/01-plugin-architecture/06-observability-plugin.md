# REQ-051 to REQ-060: Telemetry and Lineage Backend Plugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification (Updated - Split Architecture)

## Overview

Observability in floe is implemented via **two independent plugin types**:

1. **TelemetryBackendPlugin** (REQ-051 to REQ-055): Configures OTLP backends for traces, metrics, and logs (Jaeger, Datadog, Grafana Cloud)
2. **LineageBackendPlugin** (REQ-056 to REQ-060): Configures OpenLineage backends for data lineage (Marquez, Atlan, OpenMetadata)

**Architectural Rationale**:
- OpenTelemetry uses OTLP Collector (Layer 2) → Backend (Layer 3)
- OpenLineage uses direct HTTP transport → Backend (no collector layer)
- These are architecturally independent systems requiring separate plugins
- Enables mixed backends (e.g., Datadog for observability + Atlan for lineage)

**Key ADRs**:
- ADR-0006 (OpenTelemetry Standard)
- ADR-0007 (OpenLineage from Start)
- ADR-0035 (Telemetry and Lineage Backend Plugins) - **Revised**

**Migration Note**: This specification supersedes the original unified ObservabilityPlugin design. See ADR-0035 for migration path.

---

## TelemetryBackendPlugin Requirements (REQ-051 to REQ-055)

### REQ-051: TelemetryBackendPlugin ABC Definition **[New]**

**Requirement**: TelemetryBackendPlugin MUST define abstract methods: get_otlp_exporter_config(), get_helm_values(), validate_connection().

**Rationale**: Enforces consistent interface for OTLP backend configuration (Jaeger, Datadog, Grafana Cloud, Honeycomb).

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 3 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition
- [ ] Entry point: `floe.telemetry_backends`

**Interface Signature**:
```python
class TelemetryBackendPlugin(ABC):
    """Configures OTLP Collector backend for traces, metrics, logs."""

    @abstractmethod
    def get_otlp_exporter_config(
        self,
        environment: str
    ) -> OTLPExporterConfig:
        """Returns OTLP Collector exporter configuration.

        Returns:
            OTLPExporterConfig with:
            - endpoint: str (e.g., "https://api.datadoghq.com/api/v2/otlp")
            - protocol: Literal["grpc", "http/protobuf"]
            - headers: dict[str, str] (API keys, auth tokens)
            - compression: Literal["gzip", "none"]
        """
        pass

    @abstractmethod
    def get_helm_values(
        self,
        artifacts: CompiledArtifacts,
        environment: str
    ) -> dict[str, Any]:
        """Returns Helm values for OTLP Collector configuration."""
        pass

    @abstractmethod
    def validate_connection(self, config: OTLPExporterConfig) -> bool:
        """Validates backend reachability."""
        pass
```

**Enforcement**: ABC enforcement tests, mypy strict mode, plugin compliance test suite
**Test Coverage**: `tests/contract/test_telemetry_backend_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0035

---

### REQ-052: TelemetryBackendPlugin OTLP Exporter Config **[New]**

**Requirement**: TelemetryBackendPlugin.get_otlp_exporter_config() MUST return valid OTLP Collector exporter configuration for the telemetry backend.

**Rationale**: Configures OTLP Collector (Layer 2) to export telemetry to backend (Layer 3).

**Acceptance Criteria**:
- [ ] Returns OTLPExporterConfig matching OTLP Collector config schema
- [ ] Includes endpoint, protocol, headers, compression
- [ ] Backend-specific protocol (gRPC for Jaeger, HTTP/protobuf for Datadog)
- [ ] Credential references use ${env:VAR} syntax (no hardcoded secrets)
- [ ] Configuration validates with otelcontribcol --validate

**Enforcement**: OTLP Collector config validation tests
**Example**:
```python
OTLPExporterConfig(
    endpoint="https://api.datadoghq.com/api/v2/otlp",
    protocol="http/protobuf",
    headers={"DD-API-KEY": "${env:DD_API_KEY}"},
    compression="gzip"
)
```
**Test Coverage**: `tests/integration/test_telemetry_otlp_config.py`
**Traceability**: ADR-0035, ADR-0006

---

### REQ-053: TelemetryBackendPlugin Helm Values **[New]**

**Requirement**: TelemetryBackendPlugin.get_helm_values() MUST return Helm chart values for OTLP Collector configuration or empty dict for SaaS backends.

**Rationale**: Enables declarative deployment of OTLP Collector with backend-specific exporters.

**Acceptance Criteria**:
- [ ] For self-hosted (Jaeger): returns OTLP Collector Helm values with Jaeger exporter
- [ ] For SaaS (Datadog, Grafana Cloud): returns OTLP Collector values with HTTP exporter
- [ ] Helm values include exporter configuration (endpoint, auth, protocol)
- [ ] Values validate against otel-collector Helm chart schema

**Enforcement**: Helm validation tests, Helm dry-run tests
**Example**:
```yaml
# Jaeger self-hosted
config:
  exporters:
    jaeger:
      endpoint: jaeger:14250
      tls:
        insecure: true
  service:
    pipelines:
      traces:
        exporters: [jaeger]

# Datadog SaaS
config:
  exporters:
    otlphttp:
      endpoint: https://api.datadoghq.com/api/v2/otlp
      headers:
        DD-API-KEY: ${env:DD_API_KEY}
  service:
    pipelines:
      traces:
        exporters: [otlphttp]
```
**Test Coverage**: `tests/unit/test_telemetry_helm_values.py`
**Traceability**: ADR-0035

---

### REQ-054: TelemetryBackendPlugin Connection Validation **[New]**

**Requirement**: TelemetryBackendPlugin.validate_connection() MUST verify telemetry backend credentials are valid and endpoint is accessible.

**Rationale**: Pre-deployment validation ensures OTLP backend connectivity.

**Acceptance Criteria**:
- [ ] Checks environment variable presence (e.g., DD_API_KEY, GRAFANA_CLOUD_API_KEY)
- [ ] Returns boolean success/failure
- [ ] For SaaS backends: verifies API key validity via test API call
- [ ] For self-hosted backends: verifies endpoint reachability (TCP connect)
- [ ] Credentials never logged or exposed

**Enforcement**: Connection validation tests, security tests
**Test Coverage**: `tests/unit/test_telemetry_connection_validation.py`
**Traceability**: security.md, ADR-0035

---

### REQ-055: TelemetryBackendPlugin Reference Implementations **[New]**

**Requirement**: System MUST provide reference implementations for Jaeger (self-hosted), Datadog (SaaS), and Grafana Cloud (SaaS) telemetry backends.

**Rationale**: Covers self-hosted and SaaS use cases for OpenTelemetry backend storage.

**Acceptance Criteria**:
- [ ] JaegerTelemetryPlugin: self-hosted open-source (gRPC protocol)
- [ ] DatadogTelemetryPlugin: SaaS with API key auth (HTTP/protobuf protocol)
- [ ] GrafanaCloudTelemetryPlugin: SaaS with Loki/Prometheus endpoints
- [ ] All implementations pass BaseTelemetryBackendPluginTests compliance suite
- [ ] Each implementation includes documentation and examples

**Plugin Entry Points**:
```python
# setup.py
entry_points={
    "floe.telemetry_backends": [
        "jaeger = floe_telemetry_jaeger:JaegerTelemetryPlugin",
        "datadog = floe_telemetry_datadog:DatadogTelemetryPlugin",
        "grafana-cloud = floe_telemetry_grafana:GrafanaCloudTelemetryPlugin",
    ]
}
```

**Enforcement**: Plugin compliance tests for each backend
**Test Coverage**:
- `plugins/floe-telemetry-jaeger/tests/integration/test_jaeger_backend.py`
- `plugins/floe-telemetry-datadog/tests/integration/test_datadog_backend.py`
- `plugins/floe-telemetry-grafana/tests/integration/test_grafana_backend.py`
**Traceability**: ADR-0035

---

## LineageBackendPlugin Requirements (REQ-056 to REQ-060)

### REQ-056: LineageBackendPlugin ABC Definition **[New]**

**Requirement**: LineageBackendPlugin MUST define abstract methods: get_transport_config(), get_namespace_strategy(), get_helm_values(), validate_connection().

**Rationale**: Enforces consistent interface for OpenLineage backend configuration (Marquez, Atlan, OpenMetadata).

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 4 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition
- [ ] Entry point: `floe.lineage_backends`

**Interface Signature**:
```python
class LineageBackendPlugin(ABC):
    """Configures OpenLineage transport to lineage backend."""

    @abstractmethod
    def get_transport_config(self, environment: str) -> OpenLineageTransport:
        """Returns OpenLineage transport configuration.

        Returns:
            OpenLineageTransport with:
            - type: Literal["http", "kafka", "console", "file"]
            - url: str (for HTTP transport)
            - auth: dict[str, str] (API keys, tokens)
            - timeout: float
            - headers: dict[str, str]
        """
        pass

    @abstractmethod
    def get_namespace_strategy(self) -> NamespaceStrategy:
        """Returns namespace strategy (Simple, Centralized, Mesh).

        Per ADR-0007 lines 72-79:
        - Simple: single-tenant/{product}
        - Centralized: organization/domain/{product}
        - Mesh: domain-{domain}/{product}
        """
        pass

    @abstractmethod
    def get_helm_values(
        self,
        artifacts: CompiledArtifacts,
        environment: str
    ) -> dict[str, Any]:
        """Returns Helm values for lineage backend connectivity."""
        pass

    @abstractmethod
    def validate_connection(self, config: OpenLineageTransport) -> bool:
        """Validates backend reachability."""
        pass
```

**Enforcement**: ABC enforcement tests, mypy strict mode, plugin compliance test suite
**Test Coverage**: `tests/contract/test_lineage_backend_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0035, ADR-0007

---

### REQ-057: LineageBackendPlugin Transport Config **[New]**

**Requirement**: LineageBackendPlugin.get_transport_config() MUST return OpenLineage HTTP transport configuration for the lineage backend.

**Rationale**: Configures where OpenLineage events (from dbt/Dagster/quality checks) are sent via HTTP.

**Acceptance Criteria**:
- [ ] Returns OpenLineageTransport with type="http" (primary)
- [ ] Includes backend HTTP endpoint URL
- [ ] Includes authentication headers (API keys, tokens)
- [ ] Supports timeout and retry configuration
- [ ] Credential references use ${env:VAR} syntax
- [ ] Configuration validates with openlineage-python SDK

**Enforcement**: OpenLineage transport validation tests
**Example**:
```python
OpenLineageTransport(
    type="http",
    url="https://acme.atlan.com/api/openlineage",
    auth={"X-Atlan-API-Key": "${env:ATLAN_API_TOKEN}"},
    timeout=5.0,
    headers={"Content-Type": "application/json"}
)
```
**Test Coverage**: `tests/integration/test_lineage_transport_config.py`
**Traceability**: ADR-0035, ADR-0007

**Note**: OTLP transport for OpenLineage is NOT supported in initial implementation (deferred to Epic 8+). HTTP transport aligns with OpenLineage ecosystem standards.

---

### REQ-058: LineageBackendPlugin Namespace Strategy **[New]**

**Requirement**: LineageBackendPlugin.get_namespace_strategy() MUST return the lineage namespace strategy enforced by the backend.

**Rationale**: Different backends enforce different namespace hierarchies (single-tenant vs multi-tenant vs Data Mesh).

**Acceptance Criteria**:
- [ ] Returns NamespaceStrategy enum (Simple, Centralized, Mesh)
- [ ] Strategy determines namespace formatting for lineage events
- [ ] Marquez: defaults to Simple (single-tenant/{product})
- [ ] Atlan: defaults to Centralized (organization/domain/{product})
- [ ] OpenMetadata: defaults to Centralized
- [ ] Strategy documented in plugin README

**Enforcement**: Namespace strategy validation tests
**Example**:
```python
class MarquezLineagePlugin(LineageBackendPlugin):
    def get_namespace_strategy(self) -> NamespaceStrategy:
        return NamespaceStrategy.SIMPLE

class AtlanLineagePlugin(LineageBackendPlugin):
    def get_namespace_strategy(self) -> NamespaceStrategy:
        return NamespaceStrategy.CENTRALIZED
```
**Test Coverage**: `tests/unit/test_lineage_namespace_strategy.py`
**Traceability**: ADR-0007 lines 72-79

---

### REQ-059: LineageBackendPlugin Helm Values **[New]**

**Requirement**: LineageBackendPlugin.get_helm_values() MUST return Helm chart values for lineage backend connectivity or empty dict for SaaS backends.

**Rationale**: Enables declarative deployment of lineage client configuration in Dagster/dbt jobs.

**Acceptance Criteria**:
- [ ] For self-hosted (Marquez): returns Helm values with HTTP endpoint config
- [ ] For SaaS (Atlan, OpenMetadata): returns Helm values with API endpoint + credentials
- [ ] Helm values include environment variables for OpenLineage SDK
- [ ] Values validate against job Helm chart schema

**Enforcement**: Helm validation tests
**Example**:
```yaml
# Marquez self-hosted
env:
  - name: OPENLINEAGE_URL
    value: "http://marquez:5000/api/v1/lineage"
  - name: OPENLINEAGE_NAMESPACE
    value: "floe-platform"

# Atlan SaaS
env:
  - name: OPENLINEAGE_URL
    value: "https://acme.atlan.com/api/openlineage"
  - name: OPENLINEAGE_API_KEY
    valueFrom:
      secretKeyRef:
        name: atlan-credentials
        key: api_key
```
**Test Coverage**: `tests/unit/test_lineage_helm_values.py`
**Traceability**: ADR-0035

---

### REQ-060: LineageBackendPlugin Reference Implementations **[New]**

**Requirement**: System MUST provide reference implementations for Marquez (self-hosted) and Atlan (SaaS) lineage backends.

**Rationale**: Covers self-hosted and SaaS use cases for OpenLineage backend storage.

**Acceptance Criteria**:
- [ ] MarquezLineagePlugin: self-hosted open-source
- [ ] AtlanLineagePlugin: SaaS with API key auth
- [ ] All implementations pass BaseLineageBackendPluginTests compliance suite
- [ ] Each implementation includes documentation and examples
- [ ] Connection validation verifies backend availability

**Plugin Entry Points**:
```python
# setup.py
entry_points={
    "floe.lineage_backends": [
        "marquez = floe_lineage_marquez:MarquezLineagePlugin",
        "atlan = floe_lineage_atlan:AtlanLineagePlugin",
    ]
}
```

**Enforcement**: Plugin compliance tests for each backend
**Test Coverage**:
- `plugins/floe-lineage-marquez/tests/integration/test_marquez_backend.py`
- `plugins/floe-lineage-atlan/tests/integration/test_atlan_backend.py`
**Traceability**: ADR-0035, ADR-0007

---

## Cross-Cutting Requirements

### Type Safety (Applies to Both Plugin Types)

**Requirement**: All TelemetryBackendPlugin and LineageBackendPlugin implementations MUST pass mypy --strict with full type annotations.

**Acceptance Criteria**:
- [ ] All methods have type hints
- [ ] Return types match ABC signature
- [ ] mypy --strict passes on plugin implementations
- [ ] No use of Any except for truly dynamic values (dict[str, Any] for Helm values)

**Enforcement**: mypy in CI/CD, type checking tests
**Traceability**: python-standards.md

---

### Error Handling (Applies to Both Plugin Types)

**Requirement**: Plugins MUST handle configuration failures gracefully.

**Rationale**: Observability/lineage failures should not break data pipelines.

**Acceptance Criteria**:
- [ ] Catches backend-specific exceptions
- [ ] Translates to PluginExecutionError with context
- [ ] Error messages actionable (not stack traces)
- [ ] Fallback: logs error and continues (graceful degradation)
- [ ] Includes debug context in structured logs

**Enforcement**: Error handling tests, graceful degradation tests
**Traceability**: ADR-0025 (Exception Handling)

---

### Compliance Test Suites

**Requirement**: System MUST provide base test classes that all backend plugin implementations inherit to validate compliance.

**Acceptance Criteria**:
- [ ] BaseTelemetryBackendPluginTests in testing/base_classes/
  - Tests all TelemetryBackendPlugin ABC methods
  - Tests OTLP exporter config generation
  - Tests Helm values for OTLP Collector
  - Tests connection validation
- [ ] BaseLineageBackendPluginTests in testing/base_classes/
  - Tests all LineageBackendPlugin ABC methods
  - Tests OpenLineage transport config generation
  - Tests namespace strategy enforcement
  - Tests Helm values for lineage connectivity
  - Tests connection validation

**Enforcement**: Plugin compliance tests must pass for all backend implementations
**Test Coverage**:
- `testing/base_classes/base_telemetry_backend_plugin_tests.py`
- `testing/base_classes/base_lineage_backend_plugin_tests.py`
**Traceability**: TESTING.md

---

## Domain Acceptance Criteria

Telemetry and Lineage Backend Plugin Standards (REQ-051 to REQ-060) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] TelemetryBackendPlugin ABC defined in floe-core
- [ ] LineageBackendPlugin ABC defined in floe-core
- [ ] At least 3 telemetry backend implementations (Jaeger, Datadog, Grafana Cloud)
- [ ] At least 2 lineage backend implementations (Marquez, Atlan)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate telemetry flow end-to-end
- [ ] Integration tests validate lineage flow end-to-end
- [ ] Documentation backreferences all requirements
- [ ] ADR-0035 revised to document split architecture

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract telemetry and lineage backend configuration to separate plugins

## Migration Notes

**From ObservabilityPlugin (Deprecated)**:

The original `ObservabilityPlugin` (floe 0.1.0-0.3.0) coupled telemetry and lineage configuration. This has been split into two independent plugin types:

**Migration Steps**:
1. Replace `observability:` in platform-manifest.yaml with `telemetry_backend:` and `lineage_backend:`
2. Update entry points from `floe.observability` to `floe.telemetry_backends` and `floe.lineage_backends`
3. Implement TelemetryBackendPlugin and LineageBackendPlugin separately
4. Update tests to use BaseTelemetryBackendPluginTests and BaseLineageBackendPluginTests

**Backward Compatibility**: ObservabilityPlugin will be deprecated in Epic 4, with warning messages. Removal scheduled for Epic 8.

**See**: ADR-0035 for detailed migration guide.
