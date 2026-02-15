# Platform Integration Design

**Work ID**: platform-integration
**Status**: designing
**Date**: 2026-02-15

## Problem Statement

After shipping WU-1 through WU-8 (Helm charts, Polaris, Dagster, OTel, dbt, plugins, secrets, polish), the E2E test suite shows **72 pass / 36 fail / 12 errors**. The failures expose real gaps between the compilation pipeline and the deployed platform — config defined in `manifest.yaml` and `floe.yaml` doesn't flow through to `CompiledArtifacts` correctly.

The charter says: *"Two YAML files compile into a complete, deployable data platform."* Currently, compilation reads the YAML but drops governance and observability config on the floor before building the output artifact.

## User Requirements

1. **Config flows from YAML, not hardcoded** — manifest.yaml observability + governance must reach CompiledArtifacts
2. **ALL platform features implemented** — governance, OTel tracing, lineage, demo products
3. **Issues are bugs or integration gaps** — not missing features, just broken wiring
4. **Target user experience** — data engineer writes floe.yaml, platform engineer writes manifest.yaml, `floe compile` produces everything needed

## Design Approach

The failures group into **three architectural gaps** and **seven wiring fixes**:

### Gap A: Governance Not Flowing to CompiledArtifacts

**Current state**: `build_artifacts()` never passes `governance=` to `CompiledArtifacts`. The field exists (`governance: ResolvedGovernance | None`, L649) but is always None.

**Root cause**: `stages.py:338` reads governance from `spec.governance` (which is None for demo floe.yaml), builds an `EnforcementResultSummary` from it, but never converts `manifest.governance` (GovernanceConfig) → `ResolvedGovernance` for the artifacts.

**Fix**: In `stages.py`, after loading manifest, convert `manifest.governance` → `ResolvedGovernance`. Pass to `build_artifacts()`. In `builder.py`, accept `governance` parameter and pass to `CompiledArtifacts()`.

```
manifest.governance.policy_enforcement_level → resolved.policy_enforcement_level
manifest.governance.pii_encryption → resolved.pii_encryption
manifest.governance.audit_logging → resolved.audit_logging
manifest.governance.data_retention_days → resolved.data_retention_days
```

**Enforcement level precedence rule**: `manifest.governance.policy_enforcement_level` is authoritative. The spec-level governance can only STRENGTHEN (never weaken) the manifest level. This aligns with the `GovernanceConfig` inheritance rule (docstring at `manifest.py:147-155`: "Child manifests can only strengthen, not weaken"). In practice:
- If manifest says `strict` and spec says `warn` → use `strict` (manifest wins)
- If manifest says `warn` and spec says `strict` → use `strict` (spec strengthens)
- If spec has no governance → use manifest level directly
- If neither has governance → default to `warn`

### Gap B: ObservabilityConfig Hardcoded Instead of From Manifest

**Current state**: `builder.py:110-125` constructs `ObservabilityConfig` with hardcoded defaults:
- `deployment_environment="dev"` (hardcoded)
- `enabled=True` (hardcoded, should be from manifest.observability.tracing.enabled)
- No OTLP endpoint configured (manifest has `http://floe-platform-otel:4317`)
- No lineage endpoint configured (manifest has `http://floe-platform-marquez:5000/api/v1/lineage`)

**Root cause**: `build_artifacts()` never reads `manifest.observability`. The `PlatformManifest` schema doesn't have an `observability` field — the demo manifest.yaml has one, but Pydantic's `extra="allow"` silently accepts it without making it available as a typed field.

**Fix (three parts)**:

**Part 1 — Manifest schema** (`manifest.py`): Add typed `observability` field to `PlatformManifest`. Define new models matching the demo YAML structure:

```python
class TracingManifestConfig(BaseModel):
    """Tracing settings from manifest.yaml."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = Field(default=True)
    exporter: Literal["otlp", "console", "none"] = Field(default="otlp")
    endpoint: str = Field(default="http://localhost:4317")

class LineageManifestConfig(BaseModel):
    """Lineage settings from manifest.yaml."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = Field(default=True)
    transport: Literal["http", "console", "noop"] = Field(default="http")
    endpoint: str = Field(default="http://localhost:5000/api/v1/lineage")

class LoggingManifestConfig(BaseModel):
    """Logging settings from manifest.yaml."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    format: Literal["json", "text"] = Field(default="json")

class ObservabilityManifestConfig(BaseModel):
    """Observability settings from manifest.yaml."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    tracing: TracingManifestConfig = Field(default_factory=TracingManifestConfig)
    lineage: LineageManifestConfig = Field(default_factory=LineageManifestConfig)
    logging: LoggingManifestConfig = Field(default_factory=LoggingManifestConfig)
```

Add to `PlatformManifest`:
```python
observability: ObservabilityManifestConfig | None = Field(
    default=None,
    description="Observability configuration (tracing, lineage, logging)",
)
```

This moves `observability` from `model_extra` to a first-class field. The `warn_on_extra_fields` validator at L434-452 must be updated to exclude `observability` from warnings. Tests that assert `observability` appears in the unknown-field warning list must be updated.

Note: `resource_presets` remains in `model_extra` for now (tracked as follow-up).

**Part 2 — CompiledArtifacts schema** (`compiled_artifacts.py`): Add lineage endpoint fields to `ObservabilityConfig`:

```python
class ObservabilityConfig(BaseModel):
    telemetry: TelemetryConfig = Field(...)
    lineage: bool = Field(default=True)
    lineage_namespace: str = Field(...)
    # NEW in 0.8.0:
    lineage_endpoint: str | None = Field(
        default=None,
        description="OpenLineage HTTP endpoint for lineage events",
    )
    lineage_transport: Literal["http", "console", "noop"] | None = Field(
        default=None,
        description="OpenLineage transport type",
    )
```

This requires bumping `COMPILED_ARTIFACTS_VERSION` from `0.7.0` to `0.8.0` (MINOR — additive optional fields). Update `versions.py` version history.

**Part 3 — Builder** (`builder.py`): Read `manifest.observability` when constructing `ObservabilityConfig`:

```python
manifest_obs = manifest.observability  # ObservabilityManifestConfig | None
tracing = manifest_obs.tracing if manifest_obs else None
lineage_cfg = manifest_obs.lineage if manifest_obs else None

observability = ObservabilityConfig(
    telemetry=TelemetryConfig(
        enabled=tracing.enabled if tracing else True,
        otlp_endpoint=tracing.endpoint if tracing else "http://localhost:4317",
        resource_attributes=ResourceAttributes(
            service_name=spec.metadata.name,
            service_version=spec.metadata.version,
            deployment_environment="dev",  # From FLOE_ENV at runtime
            floe_namespace="default",
            floe_product_name=spec.metadata.name,
            floe_product_version=spec.metadata.version,
            floe_mode="dev",
        ),
    ),
    lineage=lineage_cfg.enabled if lineage_cfg else True,
    lineage_namespace=spec.metadata.name,
    lineage_endpoint=lineage_cfg.endpoint if lineage_cfg else None,
    lineage_transport=lineage_cfg.transport if lineage_cfg else None,
)
```

Note: `deployment_environment` and `floe_mode` remain as defaults at compile time — they are resolved from `FLOE_ENV` at runtime by `TelemetryProvider`. The compile step populates the config; runtime initializes exporters. This is correct architecture.

### Gap C: Demo Code Not in Dagster Container

**Current state**: The workspace configmap generates entries like:
```yaml
- python_module:
    module_name: demo.customer_360.definitions
    working_directory: /app/demo
```
But the standard Dagster image doesn't have `/app/demo/`. The testing Dockerfile doesn't COPY demo code either.

**Fix**: The Dagster pods use the stock `dagster/dagster-celery-k8s` image (from the Dagster Helm chart). Demo code needs to be available at `/app/demo/` inside these pods.

**Approach**: Build a custom test Dagster image that extends the base with demo code. The testing Dockerfile is at `testing/Dockerfile` (builds `floe-test-runner:latest` for the test runner pod), but the Dagster webserver/daemon pods use a separate image.

Options:
- **(A)** Create `testing/Dockerfile.dagster` that extends `dagster/dagster-celery-k8s` with `COPY demo/ /app/demo/` and pip-installs the demo packages. Override the image in `values-test.yaml`.
- **(B)** Use an init container to copy demo code from a ConfigMap or shared volume into the Dagster pod at startup.

**(A) is recommended** — it's explicit, reproducible, and follows the same pattern as the test-runner image. Production values.yaml does NOT reference demo code locations (verified — `codeLocations` is only in `values-test.yaml`), so this stays test-only.

---

## Wiring Fixes (Non-Architectural)

### Fix 1: Remove stale xfail markers (Cat 2 — 5 failures)

Tests marked `@pytest.mark.xfail(strict=True)` that now pass. Remove the markers entirely — these tests are working.

### Fix 2: Polaris 1.3.0 compatibility (Cat 6 — 6 errors + 5 failures)

Polaris 1.3.0 returns 'PUT' as HTTP method in config response. PyIceberg 0.11.0rc2's `HttpMethod` enum only has GET/HEAD/POST/DELETE — PUT is missing.

**Research result**: pyiceberg 0.11.0rc2 does NOT handle PUT. No released version does.

**Recommended approach**: Pin Polaris to `1.2.1-incubating` in `values-test.yaml` for now (known compatible). File an upstream issue on pyiceberg for PUT support. When pyiceberg adds it, upgrade and unpin.

This is the pragmatic choice because:
- We control the Polaris version in our Helm values
- The PUT method gap is a pyiceberg bug, not ours
- Pinning is explicit and documented, not a silent workaround
- Tests will fail loudly if we accidentally upgrade Polaris past 1.2.x

### Fix 3: dbt profile generation (Cat 7 — 2 failures)

dbt profiles generated by `compile_pipeline` use the compute plugin's connection config. For in-cluster execution, the profile needs to reference the DuckDB instance at the right path. Verify profiles.yml output matches what dbt expects when running inside K8s.

### Fix 4: Infrastructure bootstrap timing (Cat 8 — 4 failures)

MinIO bucket creation and test-connection pod timing. The Helm chart's init job may not complete before tests start. Fix: add readiness check or increase bootstrap job timeout.

### Fix 5: STORAGE plugin type (Cat 9 — 1 failure)

The E2E test expects a registered STORAGE plugin, but `s3` storage is a manifest config section, not a discovered plugin. The test assertion is wrong — storage config flows through manifest, not plugin registry. Fix the test to validate storage config presence in `CompiledArtifacts.plugins.storage` rather than plugin registry lookup.

### Fix 6: Health check mock (Cat 10 — 1 failure)

MagicMock comparison issue in health check test. Fix the mock setup to return comparable values.

### Fix 7: Secrets/CVE cleanup (Cat 5 — 2 failures)

Test file pattern detection for hardcoded strings, devtools pip-audit vulnerability. Bump affected package or add pragma allowlists for test fixtures.

---

## Architecture Alignment

### Config Flow (Target State)

```
manifest.yaml                    floe.yaml
    │                                │
    ├─ plugins.*                     ├─ transforms[]
    ├─ governance.*          ──►     ├─ schedule
    ├─ observability.*       ──►     └─ platform.manifest (ref)
    └─ resource_presets
         │                           │
         ▼                           ▼
    ┌─────────────────────────────────────┐
    │        compile_pipeline()           │
    │  stages.py → loader → resolver →   │
    │  enforce → compile → generate      │
    └──────────────┬──────────────────────┘
                   │
                   ▼
         CompiledArtifacts
           ├─ metadata
           ├─ identity
           ├─ observability  ← FROM manifest.observability
           ├─ governance     ← FROM manifest.governance  (NEW)
           ├─ plugins        ← FROM manifest.plugins
           ├─ transforms     ← FROM floe.yaml transforms
           ├─ dbt_profiles   ← generated from compute plugin
           ├─ enforcement_result ← FROM governance checks
           └─ quality_config ← FROM manifest.governance.quality_gates
```

### What This Design Does NOT Change

1. **OpenLineage at compile time** — Lineage events are correctly emitted at runtime by the orchestrator. The compilation step only configures the lineage endpoint in CompiledArtifacts.
2. **Plugin discovery mechanism** — Entry points remain the plugin discovery pattern. No changes to plugin registry.
3. **CompiledArtifacts contract version** — Governance flow uses existing `governance` field (already v0.2.0+). Lineage endpoint fields are NEW optional fields → bump `COMPILED_ARTIFACTS_VERSION` from `0.7.0` to `0.8.0` (MINOR).
4. **Helm chart architecture** — No changes to chart templates (Cube fixes already committed).

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Manifest observability schema breaks existing tests | Medium | High | Add as optional field with defaults; existing tests pass None |
| Governance flow changes enforcement behavior | Low | Medium | Demo manifest already has `policy_enforcement_level: warn` — same as current default |
| Polaris 1.2.1 pin limits future features | Low | Low | Temporary — unpin when pyiceberg adds PUT support |
| Custom Dagster test image adds CI build time | Low | Low | Only built for E2E; production uses stock image |
| CompiledArtifacts 0.8.0 bump breaks consumers | Low | Medium | MINOR bump — only adds optional fields. Contract tests verify backwards compat |

---

## Alternatives Considered

### Alt 1: Add observability as dynamic extra fields
Instead of adding `observability` to `PlatformManifest` schema, read it from `model_extra`. **Rejected**: Typed fields are better for validation, autocomplete, and schema export.

### Alt 2: Initialize TelemetryProvider during compilation
Have `compile_pipeline()` set up OTLP exporter so spans actually export. **Rejected**: Compilation runs on developer machines where the OTLP endpoint may not be reachable. Config goes in artifacts; runtime initializes exporters.

### Alt 3: Skip Polaris tests until pyiceberg fix
Mark Polaris 1.3.0 tests as xfail. **Rejected**: Tests FAIL never skip (constitution). Need a real fix.

---

## Critic Review Resolution

The design was challenged by the architect agent. Key findings and resolutions:

| Finding | Severity | Resolution |
|---------|----------|------------|
| `ObservabilityManifestConfig` schema must be fully specified | BLOCK | Added exact Pydantic model definitions (TracingManifestConfig, LineageManifestConfig, LoggingManifestConfig) matching demo YAML structure |
| No `lineage_endpoint` field in `ObservabilityConfig` | BLOCK | Added `lineage_endpoint` and `lineage_transport` fields to `ObservabilityConfig`. Acknowledged contract version bump to 0.8.0 |
| "No schema version bump" claim was incorrect | WARN | Corrected — COMPILED_ARTIFACTS_VERSION bumps from 0.7.0 to 0.8.0 (MINOR) |
| Governance enforcement_level precedence underspecified | WARN | Added explicit precedence rule: manifest is authoritative, spec can only strengthen |
| Polaris fix lacks analysis | WARN | Researched: pyiceberg 0.11.0rc2 does NOT support PUT. Recommended pinning Polaris 1.2.1 |
| Demo Dockerfile path unspecified | WARN | Specified: custom `testing/Dockerfile.dagster` extending stock image, test-only |
| `resource_presets` also in model_extra | INFO | Tracked as follow-up, out of scope for this design |

---

## User Preferences

(From original request):
- **No hardcoded config** — everything from manifest or floe YAML
- **All features implemented** — failures are bugs, not missing features
- **Target user experience** — two files compile into deployable platform

---

## Handoff

After approval, this design goes to `/sw-plan` for work unit decomposition and task ordering.
