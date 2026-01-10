# Implementation Plan: OpenTelemetry Integration

**Branch**: `001-opentelemetry` | **Date**: 2026-01-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-opentelemetry/spec.md`

## Summary

Implement OpenTelemetry integration for distributed tracing, metrics, and logging across all floe components. This follows the three-layer architecture: Layer 1 (Emission) uses ENFORCED OpenTelemetry SDK, Layer 2 (Collection) uses ENFORCED OTLP Collector, and Layer 3 (Backend) is PLUGGABLE via TelemetryBackendPlugin. All telemetry includes Floe semantic conventions (`floe.namespace`, `floe.product.name`, `floe.product.version`, `floe.mode`).

## Technical Context

**Language/Version**: Python 3.10+ (required for floe-core compatibility)
**Primary Dependencies**: opentelemetry-api>=1.20.0, opentelemetry-sdk>=1.20.0, opentelemetry-exporter-otlp>=1.20.0, structlog
**Storage**: N/A (telemetry flows to OTLP Collector, not stored locally)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Linux containers (Kubernetes), local development via console exporter
**Project Type**: Python library (floe-core telemetry module + TelemetryBackendPlugin ABC)
**Performance Goals**: <5% latency overhead under normal sampling (SC-004)
**Constraints**: Async export (non-blocking), graceful degradation when backend unavailable
**Scale/Scope**: All floe packages emit telemetry; 30 functional requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core, floe-dbt, plugins/, etc.)
  - Telemetry module in `packages/floe-core/src/floe_core/telemetry/`
  - TelemetryBackendPlugin ABC in `packages/floe-core/src/floe_core/interfaces/`
  - Backend plugins in `plugins/floe-telemetry-*/`
- [x] No SQL parsing/validation in Python (dbt owns SQL) - N/A for this feature
- [x] No orchestration logic outside floe-dagster - N/A for this feature

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC)
  - TelemetryBackendPlugin ABC for backend configuration
- [x] Plugin registered via entry point (not direct import)
  - Entry point: `floe.telemetry_backends`
- [x] PluginMetadata declares name, version, floe_api_version
  - All TelemetryBackendPlugin implementations require metadata

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
  - OpenTelemetry SDK and OTLP Collector are ENFORCED (Layer 1, Layer 2)
- [x] Pluggable choices documented in manifest.yaml
  - `plugins.telemetry_backend` selects backend (Layer 3)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling)
  - TelemetryConfig included in CompiledArtifacts
- [x] Pydantic v2 models for all schemas
  - TelemetryConfig, ResourceAttributes, SpanConfig use Pydantic v2
- [x] Contract changes follow versioning rules
  - Adding telemetry to CompiledArtifacts is MINOR change (additive)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
  - OTLP Collector integration tests in K8s
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic
  - TelemetryConfig validated at compile time
- [x] Credentials use SecretStr
  - OTLP authentication uses SecretStr for API keys
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only
  - TelemetryBackendPlugin selected in manifest.yaml (Layer 2)
  - Data pipelines inherit telemetry config (Layer 4)
- [x] Layer ownership respected (Data Team vs Platform Team)
  - Platform Team selects telemetry_backend in manifest
  - Data Engineers just emit telemetry (no configuration)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted
  - THIS IS THE FEATURE - implementing OTel emission
- [x] OpenLineage events for data transformations
  - Separate epic (6B), but OTel and OpenLineage share correlation IDs

## Project Structure

### Documentation (this feature)

```text
specs/001-opentelemetry/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (Pydantic schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
packages/floe-core/
├── src/floe_core/
│   ├── telemetry/                    # NEW: Core telemetry module
│   │   ├── __init__.py               # Public API exports
│   │   ├── provider.py               # TelemetryProvider (SDK init)
│   │   ├── tracing.py                # Tracing utilities, decorators
│   │   ├── metrics.py                # MetricRecorder implementation
│   │   ├── logging.py                # Log correlation, structlog integration
│   │   ├── propagation.py            # W3C Trace Context & Baggage
│   │   └── conventions.py            # Floe semantic conventions
│   └── interfaces/
│       └── telemetry_backend.py      # NEW: TelemetryBackendPlugin ABC
└── tests/
    ├── unit/
    │   └── test_telemetry/           # Unit tests for telemetry module
    └── integration/
        └── test_otel_export.py       # OTLP Collector integration tests

plugins/
├── floe-telemetry-jaeger/            # NEW: Jaeger backend plugin
│   ├── src/floe_telemetry_jaeger/
│   │   ├── __init__.py
│   │   └── plugin.py                 # JaegerTelemetryPlugin
│   ├── pyproject.toml                # Entry point: floe.telemetry_backends
│   └── tests/
└── floe-telemetry-console/           # NEW: Console/dev backend plugin
    ├── src/floe_telemetry_console/
    │   ├── __init__.py
    │   └── plugin.py                 # ConsoleTelemetryPlugin
    ├── pyproject.toml
    └── tests/

tests/
└── contract/
    └── test_telemetry_backend_contract.py  # ABC compliance tests
```

**Structure Decision**: Monorepo structure per floe architecture. Core telemetry module in floe-core (ENFORCED), backend plugins in plugins/ directory (PLUGGABLE). Contract tests at root level validate cross-package integration.

## Complexity Tracking

> **No violations - Constitution Check passes**

All gates pass. No complexity justifications required.
