# Alpha Reliability Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the alpha runtime spine from manifest-driven compiled artifacts through Dagster, dbt, Iceberg, OpenLineage, and Marquez, while classifying the live Helm CI readiness failure.

**Architecture:** Collapse Dagster to a single runtime builder used by both `definitions.py` shims and `DagsterOrchestratorPlugin.create_definitions()`. Keep optional features explicit, but make the selected alpha proof profile strict: configured catalog, storage, dbt, Iceberg export, lineage emission, and Marquez visibility fail loudly. Add diagnosable Helm CI behavior before changing readiness or timeout settings.

**Tech Stack:** Python 3.10+, Dagster, dagster-dbt, Pydantic v2, PyIceberg, DuckDB, OpenLineage, Marquez, Helm v4, Kind, pytest.

---

## External Contracts Checked

- Helm `--wait` waits for Pods, PVCs, Services, and minimum ready Deployment/StatefulSet/ReplicaSet Pods until `--timeout`; this supports adding diagnostics before changing timeout behavior: https://helm.sh/el/docs/v3/helm/helm_install/
- OpenLineage `RunEvent` requires `eventTime`, `producer`, `schemaURL`, `run`, and `job`; event type values include `START`, `COMPLETE`, `FAIL`, and the API requires one `START` plus one terminal event per run: https://openlineage.io/apidocs/openapi/
- Marquez records lineage metadata using OpenLineage and accepts lineage events via its API: https://marquezproject.ai/docs/api/record-lineage/
- Marquez API listens on port `5000`; its admin interface listens on port `5001` and exposes `/healthcheck` and `/metrics`: https://github.com/MarquezProject/marquez

## File Structure

- Create `testing/ci/helm_diagnostics.sh`: shared CI diagnostics script that preserves useful Kind/Helm evidence on install failure.
- Create `testing/tests/unit/test_helm_ci_diagnostics.py`: unit tests that keep Helm CI diagnostics wired into the workflow.
- Modify `.github/workflows/helm-ci.yaml`: install with a diagnosable failure branch and always collect evidence before uninstall/rollback cleanup.
- Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`: canonical Dagster runtime builder from `CompiledArtifacts`.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py`: read `compiled_artifacts.json` and delegate to the runtime builder.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`: make `create_definitions()` delegate to the same runtime builder, preserving the abstract interface.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py`: add strict emission mode without changing non-alpha no-op behavior.
- Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/capabilities.py`: one place for alpha capability policy and error messages.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`: return an export result and fail on missing configured output.
- Modify Dagster plugin tests under `plugins/floe-orchestrator-dagster/tests/unit/` and integration tests under `plugins/floe-orchestrator-dagster/tests/integration/`.
- Modify E2E observability tests under `tests/e2e/` to require Marquez-visible events for the unified runtime path.
- Modify docs under `docs/validation/` with the Helm failure classification and validation commands.

## Task 1: Make Helm CI Failure Diagnosable

**Files:**
- Create: `testing/ci/helm_diagnostics.sh`
- Create: `testing/tests/unit/test_helm_ci_diagnostics.py`
- Modify: `.github/workflows/helm-ci.yaml`
- Create: `docs/validation/2026-04-25-helm-ci-failure-classification.md`

- [ ] **Step 1: Write the failing workflow diagnostics test**

Add this file:

```python
"""Tests for Helm CI failure diagnostics wiring."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "helm-ci.yaml"
DIAGNOSTICS = ROOT / "testing" / "ci" / "helm_diagnostics.sh"


def _load_workflow() -> dict[str, object]:
    with WORKFLOW.open() as handle:
        return yaml.safe_load(handle)


def test_helm_ci_invokes_shared_diagnostics_on_install_failure() -> None:
    workflow_text = WORKFLOW.read_text()

    assert "testing/ci/helm_diagnostics.sh floe-test floe-test" in workflow_text
    assert "helm uninstall floe-test --namespace floe-test" in workflow_text
    assert "--cleanup-on-fail" not in workflow_text


def test_helm_diagnostics_script_collects_dagster_marquez_and_events() -> None:
    script = DIAGNOSTICS.read_text()

    required_fragments = [
        "kubectl get all -n",
        "kubectl get events -n",
        "kubectl describe pods -n",
        "kubectl logs -n",
        "dagster-webserver",
        "dagster-daemon",
        "marquez",
        "helm status",
        "helm history",
    ]
    for fragment in required_fragments:
        assert fragment in script, f"Missing diagnostic fragment: {fragment}"


def test_helm_ci_has_integration_test_job() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]

    integration_jobs = [
        job for job in jobs.values() if "Integration Test" in str(job.get("name", ""))
    ]
    assert integration_jobs, "helm-ci.yaml must keep the Kind integration test job"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
uv run pytest testing/tests/unit/test_helm_ci_diagnostics.py -v
```

Expected: FAIL because `testing/ci/helm_diagnostics.sh` does not exist and the workflow still uses `--cleanup-on-fail`.

- [ ] **Step 3: Add the diagnostics script**

Create `testing/ci/helm_diagnostics.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

RELEASE="${1:-floe-test}"
NAMESPACE="${2:-floe-test}"

section() {
  printf '\n==== %s ====\n' "$1"
}

section "Helm status"
helm status "$RELEASE" --namespace "$NAMESPACE" || true

section "Helm history"
helm history "$RELEASE" --namespace "$NAMESPACE" || true

section "Kubernetes objects"
kubectl get all -n "$NAMESPACE" -o wide || true

section "Recent events"
kubectl get events -n "$NAMESPACE" --sort-by=.lastTimestamp || true

section "Pod descriptions"
kubectl describe pods -n "$NAMESPACE" || true

section "Dagster webserver logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep dagster-webserver || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done

section "Dagster daemon logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep dagster-daemon || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done

section "Marquez logs"
for pod in $(kubectl get pods -n "$NAMESPACE" -o name | grep marquez || true); do
  kubectl logs -n "$NAMESPACE" "$pod" --all-containers=true --tail=300 || true
done
```

- [ ] **Step 4: Make the script executable**

Run:

```bash
chmod +x testing/ci/helm_diagnostics.sh
```

Expected: command exits 0.

- [ ] **Step 5: Change Helm CI to preserve evidence before cleanup**

Replace the install step in `.github/workflows/helm-ci.yaml` with:

```yaml
      - name: Install floe-platform chart with test values
        run: |
          set +e
          helm upgrade --install floe-test charts/floe-platform \
            --namespace floe-test --create-namespace \
            --values charts/floe-platform/values-test.yaml \
            --rollback-on-failure --wait --timeout 10m
          status=$?
          if [ "$status" -ne 0 ]; then
            testing/ci/helm_diagnostics.sh floe-test floe-test
            helm uninstall floe-test --namespace floe-test || true
          fi
          exit "$status"
```

Keep the existing `Get pod status on failure` step for a short fallback, but it should not be the only diagnostics source.

- [ ] **Step 6: Record the current live failure classification**

Create `docs/validation/2026-04-25-helm-ci-failure-classification.md`:

```markdown
# Helm CI Failure Classification - 2026-04-25

## Observed Failure

The post-merge Helm CI Kind integration run for commit `3b66f0f` failed during `helm upgrade --install floe-test charts/floe-platform --wait --timeout 10m`.

Helm reported these unready Deployments:

- `Deployment/floe-test/floe-test-dagster-daemon`: `Available: 0/1`
- `Deployment/floe-test/floe-test-dagster-webserver`: `Available: 0/1`

The captured teardown output showed Marquez pods terminating and Marquez probes returning HTTP 500 during cleanup, but the workflow removed the release before Dagster pod logs were captured.

## Classification

Current classification: `unclassified platform readiness failure`.

Evidence is insufficient to choose between Dagster readiness, Marquez dependency readiness, Kind resource pressure, or chart dependency timing. The next run must capture pod logs, events, Helm status, and Helm history before release cleanup.

## Decision

Do not tune timeouts or readiness probes from this evidence alone. First merge diagnosable CI behavior, then classify the next failure from retained logs.
```

- [ ] **Step 7: Run tests**

Run:

```bash
uv run pytest testing/tests/unit/test_helm_ci_diagnostics.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add .github/workflows/helm-ci.yaml testing/ci/helm_diagnostics.sh testing/tests/unit/test_helm_ci_diagnostics.py docs/validation/2026-04-25-helm-ci-failure-classification.md
git commit -m "ci: preserve helm integration diagnostics"
```

## Task 2: Collapse Dagster to One Runtime Builder

**Files:**
- Create: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py`

- [ ] **Step 1: Add failing tests for shared builder usage**

Add these tests to `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`:

```python
def test_loader_delegates_to_runtime_builder(project_dir: Path) -> None:
    artifacts_path = project_dir / "compiled_artifacts.json"
    expected_artifacts = CompiledArtifacts.model_validate_json(artifacts_path.read_text())

    with patch("floe_orchestrator_dagster.loader.build_product_definitions") as build:
        sentinel = MagicMock(spec=Definitions)
        build.return_value = sentinel

        result = load_product_definitions(PRODUCT_NAME, project_dir)

    assert result is sentinel
    build.assert_called_once()
    call = build.call_args.kwargs
    assert call["product_name"] == PRODUCT_NAME
    assert call["project_dir"] == project_dir
    assert call["artifacts"] == expected_artifacts
```

Add this test to `plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py`:

```python
def test_create_definitions_delegates_to_runtime_builder(
    dagster_plugin: DagsterOrchestratorPlugin,
    valid_compiled_artifacts: dict[str, Any],
) -> None:
    with patch("floe_orchestrator_dagster.plugin.build_product_definitions") as build:
        sentinel = object()
        build.return_value = sentinel

        result = dagster_plugin.create_definitions(valid_compiled_artifacts)

    assert result is sentinel
    build.assert_called_once()
    call = build.call_args.kwargs
    assert call["artifacts"].metadata.product_name == valid_compiled_artifacts["metadata"]["product_name"]
    assert call["product_name"] == valid_compiled_artifacts["metadata"]["product_name"]
    assert call["project_dir"] is None
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_loader.py::test_loader_delegates_to_runtime_builder plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py::test_create_definitions_delegates_to_runtime_builder -v
```

Expected: FAIL because `build_product_definitions` is not imported by `loader.py` or `plugin.py`.

- [ ] **Step 3: Create the runtime builder**

Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py` by moving the current `load_product_definitions()` asset/resource construction into this function:

```python
"""Canonical Dagster runtime builder for floe products."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from dagster import Definitions, ResourceDefinition
from dagster_dbt import DbtCliResource, dbt_assets
from floe_core.lineage.facets import TraceCorrelationFacetBuilder
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

from floe_orchestrator_dagster.export.iceberg import export_dbt_to_iceberg
from floe_orchestrator_dagster.resources.iceberg import try_create_iceberg_resources
from floe_orchestrator_dagster.resources.lineage import try_create_lineage_resource


def build_product_definitions(
    *,
    product_name: str,
    artifacts: CompiledArtifacts,
    project_dir: Path | None,
) -> Definitions:
    """Build Dagster Definitions from compiled artifacts.

    Args:
        product_name: Data product name from compiled metadata.
        artifacts: Validated compiled artifacts.
        project_dir: dbt project directory. Required when assets are materialized.

    Returns:
        Dagster Definitions wired with dbt, lineage, and optional Iceberg resources.

    Raises:
        ValueError: If `project_dir` is missing for runtime dbt execution.
    """
    if project_dir is None:
        raise ValueError(
            "Dagster runtime definitions require project_dir so dbt manifest, "
            "profiles.yml, and compiled_artifacts.json are resolved from one product directory."
        )

    manifest_path = project_dir / "target" / "manifest.json"

    @dbt_assets(
        manifest=manifest_path,
        name=f"{product_name.replace('-', '_')}_dbt_assets",
        required_resource_keys={"dbt", "lineage"},
    )
    def _dbt_assets_fn(context) -> object:  # type: ignore[misc]
        dbt = context.resources.dbt
        lineage = context.resources.lineage
        run_id: UUID | None = None

        run_facets: dict[str, object] = {}
        try:
            trace_facet = TraceCorrelationFacetBuilder.from_otel_context()
            if trace_facet is not None:
                run_facets["traceCorrelation"] = trace_facet
        except Exception as trace_exc:
            context.log.debug("Trace facet creation failed: %s", trace_exc)

        try:
            run_id = lineage.emit_start(product_name, run_facets=run_facets or None)
        except Exception:
            run_id = uuid4()

        try:
            yield from dbt.cli(["build"], context=context).stream()
        except Exception as exc:
            try:
                lineage.emit_fail(run_id, product_name, error_message=type(exc).__name__)
            except Exception as fail_exc:
                context.log.debug("emit_fail failed: %s", fail_exc)
            raise

        if artifacts.plugins and artifacts.plugins.catalog:
            export_dbt_to_iceberg(context, product_name, project_dir, artifacts)

        try:
            lineage.emit_complete(run_id, product_name)
        except Exception as complete_exc:
            context.log.debug("emit_complete failed: %s", complete_exc)

    project_dir_str = str(project_dir)
    plugins = artifacts.plugins

    def _dbt_resource_fn(_init_context: Any) -> Any:
        return DbtCliResource(project_dir=project_dir_str, profiles_dir=project_dir_str)

    resources: dict[str, object] = {
        "dbt": ResourceDefinition(resource_fn=_dbt_resource_fn),
        **try_create_lineage_resource(plugins),
    }

    if plugins and plugins.catalog:

        def _iceberg_resource_fn(_init_context: Any) -> Any:
            result = try_create_iceberg_resources(plugins)
            return result.get("iceberg")

        resources["iceberg"] = ResourceDefinition(resource_fn=_iceberg_resource_fn)

    return Definitions(assets=[_dbt_assets_fn], resources=resources)
```

- [ ] **Step 4: Delegate from the loader**

Replace the body of `load_product_definitions()` in `loader.py` with:

```python
    artifacts_path = project_dir / "compiled_artifacts.json"
    artifacts = CompiledArtifacts.model_validate_json(artifacts_path.read_text())
    return build_product_definitions(
        product_name=product_name,
        artifacts=artifacts,
        project_dir=project_dir,
    )
```

Add this import:

```python
from floe_orchestrator_dagster.runtime import build_product_definitions
```

Remove imports from `loader.py` that are now only used by `runtime.py`.

- [ ] **Step 5: Delegate from the plugin**

Add this import to `plugin.py`:

```python
from floe_orchestrator_dagster.runtime import build_product_definitions
```

Replace `create_definitions()` implementation after validation with:

```python
        tracer = get_tracer()
        with orchestrator_span(tracer, "create_definitions") as span:
            validated = self._validate_artifacts(artifacts)
            product_name = validated.metadata.product_name
            span.set_attribute(ATTR_ASSET_COUNT, len(validated.transforms.models if validated.transforms else []))
            return build_product_definitions(
                product_name=product_name,
                artifacts=validated,
                project_dir=None,
            )
```

This intentionally makes the direct plugin API fail with a clear `project_dir` error until callers pass through the loader/shim path. The product runtime path is the loader path; this avoids maintaining synthetic per-model Dagster assets that diverge from dbt manifest execution.

- [ ] **Step 6: Update old direct asset-count expectations**

Change tests that expect `len(result.assets) == number_of_models` for `create_definitions()` to assert the new contract:

```python
with pytest.raises(ValueError, match="require project_dir"):
    dagster_plugin.create_definitions(valid_compiled_artifacts_with_models)
```

Keep `create_assets_from_transforms()` tests unchanged because that helper remains available for plugin-level transform tests.

- [ ] **Step 7: Run Dagster unit tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_loader.py plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py plugins/floe-orchestrator-dagster/tests/unit/test_code_generator_iceberg.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py plugins/floe-orchestrator-dagster/tests/unit/test_loader.py plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py
git commit -m "refactor: collapse dagster definitions onto runtime loader"
```

## Task 3: Codify Strict Alpha Capability Semantics

**Files:**
- Create: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/capabilities.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py`
- Create: `plugins/floe-orchestrator-dagster/tests/unit/test_capability_policy.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_resources_lineage.py`

- [ ] **Step 1: Write failing capability policy tests**

Create `plugins/floe-orchestrator-dagster/tests/unit/test_capability_policy.py`:

```python
"""Tests for alpha capability policy."""

from __future__ import annotations

import pytest
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

from floe_orchestrator_dagster.capabilities import (
    AlphaCapabilityError,
    CapabilityPolicy,
)


def test_alpha_profile_requires_catalog_storage_and_lineage() -> None:
    policy = CapabilityPolicy.alpha()
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
        catalog=None,
        storage=None,
        lineage_backend=None,
    )

    with pytest.raises(AlphaCapabilityError, match="catalog"):
        policy.validate_required_plugins(plugins)


def test_non_alpha_profile_allows_unconfigured_lineage() -> None:
    policy = CapabilityPolicy.default()
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
        catalog=None,
        storage=None,
        lineage_backend=None,
    )

    policy.validate_required_plugins(plugins)


def test_alpha_profile_accepts_all_required_plugins() -> None:
    policy = CapabilityPolicy.alpha()
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
        catalog=PluginRef(type="polaris", version="0.1.0", config={}),
        storage=PluginRef(type="s3", version="1.0.0", config={}),
        lineage_backend=PluginRef(type="marquez", version="0.1.0", config={"url": "http://marquez:5000"}),
    )

    policy.validate_required_plugins(plugins)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_capability_policy.py -v
```

Expected: FAIL because `capabilities.py` does not exist.

- [ ] **Step 3: Add the capability policy**

Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/capabilities.py`:

```python
"""Capability policy for Dagster alpha runtime proofs."""

from __future__ import annotations

from dataclasses import dataclass

from floe_core.schemas.compiled_artifacts import ResolvedPlugins


class AlphaCapabilityError(RuntimeError):
    """Raised when a configured alpha proof profile is missing a required capability."""


@dataclass(frozen=True)
class CapabilityPolicy:
    """Runtime capability policy for Dagster definitions."""

    require_catalog: bool = False
    require_storage: bool = False
    require_lineage: bool = False

    @classmethod
    def default(cls) -> "CapabilityPolicy":
        return cls()

    @classmethod
    def alpha(cls) -> "CapabilityPolicy":
        return cls(require_catalog=True, require_storage=True, require_lineage=True)

    def validate_required_plugins(self, plugins: ResolvedPlugins | None) -> None:
        missing: list[str] = []
        if plugins is None:
            missing.extend(self._all_required_names())
        else:
            if self.require_catalog and plugins.catalog is None:
                missing.append("catalog")
            if self.require_storage and plugins.storage is None:
                missing.append("storage")
            if self.require_lineage and plugins.lineage_backend is None:
                missing.append("lineage_backend")

        if missing:
            joined = ", ".join(sorted(set(missing)))
            raise AlphaCapabilityError(
                f"Alpha runtime profile requires configured capability: {joined}"
            )

    def _all_required_names(self) -> list[str]:
        names: list[str] = []
        if self.require_catalog:
            names.append("catalog")
        if self.require_storage:
            names.append("storage")
        if self.require_lineage:
            names.append("lineage_backend")
        return names
```

- [ ] **Step 4: Wire policy into runtime builder**

Change `build_product_definitions()` signature:

```python
def build_product_definitions(
    *,
    product_name: str,
    artifacts: CompiledArtifacts,
    project_dir: Path | None,
    capability_policy: CapabilityPolicy | None = None,
) -> Definitions:
```

Add imports:

```python
from floe_orchestrator_dagster.capabilities import CapabilityPolicy
```

Add this at the start of the function after the `project_dir` check:

```python
    policy = capability_policy or CapabilityPolicy.default()
    policy.validate_required_plugins(artifacts.plugins)
```

- [ ] **Step 5: Add strict lineage resource mode**

Change `LineageResource.__init__()`:

```python
    def __init__(self, emitter: LineageEmitter, *, strict: bool = False) -> None:
        self._emitter = emitter
        self._strict = strict
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
```

Change `_run_coroutine()` exception branches:

```python
        except TimeoutError:
            future.cancel()
            logger.warning("lineage_emit_timeout", extra={"timeout": _EMIT_TIMEOUT})
            if self._strict:
                raise RuntimeError(f"Lineage emission timed out after {_EMIT_TIMEOUT}s")
            return default
        except Exception as exc:
            logger.warning("lineage_emit_error", extra={"error_type": type(exc).__name__})
            if self._strict:
                raise RuntimeError(f"Lineage emission failed: {type(exc).__name__}") from exc
            return default
```

Change `create_lineage_resource()` signature and resource creation:

```python
def create_lineage_resource(lineage_ref: PluginRef, *, strict: bool = False) -> dict[str, Any]:
    ...
    def _resource_fn(_init_context: Any) -> Any:
        resource = LineageResource(emitter=emitter, strict=strict)
```

Change `try_create_lineage_resource()` signature:

```python
def try_create_lineage_resource(
    plugins: ResolvedPlugins | None,
    *,
    strict: bool = False,
) -> dict[str, Any]:
```

Delegate with:

```python
        return create_lineage_resource(lineage_backend, strict=strict)
```

- [ ] **Step 6: Pass strict lineage mode from alpha policy**

In `runtime.py`, replace lineage resource creation with:

```python
        **try_create_lineage_resource(plugins, strict=policy.require_lineage),
```

- [ ] **Step 7: Run tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_capability_policy.py plugins/floe-orchestrator-dagster/tests/unit/test_loader.py plugins/floe-orchestrator-dagster/tests/unit/test_resources_lineage.py -v
```

Expected: PASS after updating existing lineage tests to pass `strict=False` where they instantiate `LineageResource` directly.

- [ ] **Step 8: Commit**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/capabilities.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py plugins/floe-orchestrator-dagster/tests/unit/test_capability_policy.py plugins/floe-orchestrator-dagster/tests/unit/test_loader.py plugins/floe-orchestrator-dagster/tests/unit/test_resources_lineage.py
git commit -m "feat: enforce alpha capability policy"
```

## Task 4: Make Iceberg Export a Proven Output, Not a Best-Effort Side Effect

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
- Create: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
- Create: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/__init__.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py`
- Create: `tests/e2e/test_demo_iceberg_outputs.py`

- [ ] **Step 1: Add failing unit tests for export result semantics**

Add to `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`:

```python
def test_export_fails_when_catalog_configured_but_duckdb_file_missing(tmp_path: Path) -> None:
    artifacts = _make_artifacts_with_catalog_and_storage()
    context = _MockContext()

    with pytest.raises(RuntimeError, match="DuckDB output file is missing"):
        export_dbt_to_iceberg(context, "customer-360", tmp_path, artifacts)


def test_export_returns_written_table_count(tmp_path: Path) -> None:
    artifacts = _make_artifacts_with_catalog_and_storage()
    duckdb_path = Path("/tmp/customer_360.duckdb")
    _create_duckdb_file_with_table(duckdb_path, table_name="customers", rows=[(1, "Ada")])

    try:
        context = _MockContext()
        result = export_dbt_to_iceberg(context, "customer-360", tmp_path, artifacts)
    finally:
        duckdb_path.unlink(missing_ok=True)

    assert result.tables_written == 1
    assert result.table_names == ["customer_360.customers"]
```

Use existing helper patterns in this test file for `_make_artifacts_with_catalog_and_storage()` and registry mocks; if helper names differ, add wrappers with those exact names near the test helpers.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py::test_export_fails_when_catalog_configured_but_duckdb_file_missing plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py::test_export_returns_written_table_count -v
```

Expected: FAIL because `export_dbt_to_iceberg()` returns `None` and currently skips when the DuckDB file is absent.

- [ ] **Step 3: Add export result type and loud failures**

Add near the top of `export/iceberg.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class IcebergExportResult:
    """Summary of dbt output tables exported to Iceberg."""

    tables_written: int
    table_names: list[str]
```

Change the function signature:

```python
def export_dbt_to_iceberg(
    context: Any,
    product_name: str,
    project_dir: Path,
    artifacts: CompiledArtifacts,
) -> IcebergExportResult:
```

Replace the missing DuckDB file branch with:

```python
    if not Path(duckdb_path).exists():
        raise RuntimeError(
            f"DuckDB output file is missing for configured Iceberg export: {duckdb_path}"
        )
```

Replace catalog validation skip with:

```python
    if validated_config is None:
        raise RuntimeError(f"Catalog plugin config for {catalog_type} could not be validated")
```

Track written tables inside the loop:

```python
        written_table_names: list[str] = []
        for schema_name, table_name in tables_df:
            ...
            written_table_names.append(iceberg_id)
```

Return after the loop:

```python
        if not written_table_names:
            raise RuntimeError(
                f"Configured Iceberg export wrote no tables for product {product_name}"
            )
        return IcebergExportResult(
            tables_written=len(written_table_names),
            table_names=written_table_names,
        )
```

- [ ] **Step 4: Make runtime fail if export result is empty**

In `runtime.py`, replace the export call with:

```python
            export_result = export_dbt_to_iceberg(context, product_name, project_dir, artifacts)
            if export_result.tables_written == 0:
                raise RuntimeError(
                    f"Iceberg export completed without writing tables for {product_name}"
                )
```

- [ ] **Step 5: Add E2E assertion for demo Iceberg outputs**

Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/__init__.py`:

```python
"""Runtime validation helpers for deployed Dagster environments."""
```

Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`:

```python
"""Validate expected Iceberg tables from deployed runtime artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from floe_core.schemas.compiled_artifacts import CompiledArtifacts


def _connect_catalog(artifacts: CompiledArtifacts):
    if artifacts.plugins is None or artifacts.plugins.catalog is None:
        raise RuntimeError("compiled artifacts do not configure a catalog plugin")

    catalog_ref = artifacts.plugins.catalog
    storage_config = {}
    if artifacts.plugins.storage is not None:
        storage_config = artifacts.plugins.storage.config or {}

    registry = get_registry()
    registry.configure(PluginType.CATALOG, catalog_ref.type, catalog_ref.config or {})
    catalog_plugin = registry.get(PluginType.CATALOG, catalog_ref.type)
    return catalog_plugin.connect(config={f"s3.{key}": value for key, value in storage_config.items()})


def validate_expected_tables(
    *,
    artifacts_path: Path,
    expected_tables: list[str],
) -> None:
    artifacts = CompiledArtifacts.model_validate_json(artifacts_path.read_text())
    catalog = _connect_catalog(artifacts)

    missing = [table for table in expected_tables if not catalog.table_exists(table)]
    if missing:
        raise RuntimeError(f"Missing expected Iceberg tables: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", default="compiled_artifacts.json")
    parser.add_argument("--product", required=True)
    parser.add_argument("--expect-table", action="append", required=True)
    args = parser.parse_args()

    validate_expected_tables(
        artifacts_path=Path(args.artifacts),
        expected_tables=args.expect_table,
    )
    print(f"validated Iceberg outputs for {args.product}: {', '.join(args.expect_table)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `tests/e2e/test_demo_iceberg_outputs.py`:

```python
"""E2E proof that demo materialization creates Iceberg outputs."""

from __future__ import annotations

import os
import subprocess

import pytest


@pytest.mark.e2e
@pytest.mark.requirement("ALPHA-ICEBERG")
def test_demo_materialization_creates_expected_iceberg_tables() -> None:
    namespace = os.environ.get("FLOE_E2E_NAMESPACE", "floe-test")
    result = subprocess.run(
        [
            "kubectl",
            "exec",
            "-n",
            namespace,
            "deploy/floe-test-dagster-webserver",
            "--",
            "python",
            "-m",
            "floe_orchestrator_dagster.validation.iceberg_outputs",
            "--product",
            "customer-360",
            "--expect-table",
            "customer_360.customers",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Demo did not create expected Iceberg tables.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
```

- [ ] **Step 6: Run tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py plugins/floe-orchestrator-dagster/tests/unit/test_loader.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py tests/e2e/test_demo_iceberg_outputs.py
git commit -m "feat: require proven iceberg exports"
```

## Task 5: Prove OpenLineage Lifecycle Events Through Marquez

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py`
- Modify: `tests/e2e/test_observability.py`
- Modify: `tests/e2e/test_lineage_roundtrip_e2e.py`
- Create: `plugins/floe-orchestrator-dagster/tests/unit/test_runtime_lineage_strictness.py`

- [ ] **Step 1: Add failing strict runtime lineage tests**

Create `plugins/floe-orchestrator-dagster/tests/unit/test_runtime_lineage_strictness.py`:

```python
"""Tests for strict lineage behavior in the unified runtime path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from floe_orchestrator_dagster.capabilities import CapabilityPolicy
from floe_orchestrator_dagster.runtime import build_product_definitions
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    ObservabilityConfig,
    PluginRef,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig


def _make_artifacts() -> CompiledArtifacts:
    from datetime import datetime, timezone

    return CompiledArtifacts(
        version="0.5.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version="0.5.0",
            source_hash="sha256:abc123def456",
            product_name="customer-360",
            product_version="1.0.0",
        ),
        identity={
            "product_id": "default.customer_360",
            "domain": "default",
            "repository": "github.com/test/customer-360",
        },
        mode="simple",
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="customer-360",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="default",
                    floe_product_name="customer-360",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage=True,
            lineage_namespace="customer-360",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=None,
            storage=None,
            lineage_backend=None,
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="stg_customers", compute="duckdb")],
            default_compute="duckdb",
        ),
    )


def _write_artifacts_and_manifest(project_dir: Path, artifacts: CompiledArtifacts) -> None:
    import json
    from datetime import datetime, timezone

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "compiled_artifacts.json").write_text(artifacts.model_dump_json(indent=2))
    target = project_dir / "target"
    target.mkdir()
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
                    "dbt_version": "1.7.0",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "invocation_id": str(uuid4()),
                },
                "nodes": {},
                "sources": {},
                "exposures": {},
                "metrics": {},
                "groups": {},
                "selectors": {},
                "disabled": [],
                "parent_map": {},
                "child_map": {},
                "group_map": {},
                "semantic_models": {},
                "unit_tests": {},
                "saved_queries": {},
            }
        )
    )


def test_alpha_runtime_passes_strict_lineage_flag(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    artifacts = _make_artifacts()
    _write_artifacts_and_manifest(project_dir, artifacts)

    with patch("floe_orchestrator_dagster.runtime.try_create_lineage_resource") as lineage:
        lineage.return_value = {"lineage": MagicMock()}
        build_product_definitions(
            product_name="customer-360",
            artifacts=artifacts,
            project_dir=project_dir,
            capability_policy=CapabilityPolicy.default(),
        )

    assert lineage.call_args.kwargs["strict"] is False


def test_lineage_emit_failure_raises_in_strict_mode() -> None:
    from floe_orchestrator_dagster.resources.lineage import LineageResource

    emitter = MagicMock()
    emitter.emit_start.side_effect = RuntimeError("marquez unavailable")
    resource = LineageResource(emitter=emitter, strict=True)
    try:
        with pytest.raises(RuntimeError, match="Lineage emission failed"):
            resource.emit_start("customer-360")
    finally:
        resource.close()
```

- [ ] **Step 2: Run the strict lineage tests and verify they fail**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_runtime_lineage_strictness.py -v
```

Expected: FAIL until strict lineage mode is fully wired.

- [ ] **Step 3: Ensure terminal events are emitted after Iceberg success**

In `runtime.py`, keep `emit_complete()` after `export_dbt_to_iceberg()`. Do not move completion before export. The relevant block must stay in this order:

```python
        if artifacts.plugins and artifacts.plugins.catalog:
            export_result = export_dbt_to_iceberg(context, product_name, project_dir, artifacts)
            if export_result.tables_written == 0:
                raise RuntimeError(
                    f"Iceberg export completed without writing tables for {product_name}"
                )

        lineage.emit_complete(run_id, product_name)
```

This makes OpenLineage completion represent dbt plus Iceberg materialization, not only dbt.

- [ ] **Step 4: Tighten Marquez E2E validation**

In `tests/e2e/test_observability.py`, assert actual run lifecycle events are visible for the product namespace/job. Use this helper inside the test class:

```python
    def _assert_marquez_has_lifecycle(self, marquez_client: httpx.Client, namespace: str, job_name: str) -> None:
        runs_response = marquez_client.get(f"/api/v1/namespaces/{namespace}/jobs/{job_name}/runs")
        assert runs_response.status_code == 200, (
            f"Marquez runs query failed for {namespace}/{job_name}: "
            f"{runs_response.status_code} {runs_response.text}"
        )
        runs = runs_response.json().get("runs", [])
        assert runs, f"No Marquez runs found for {namespace}/{job_name}"

        states = {run.get("state") for run in runs}
        assert states & {"COMPLETED", "FAILED"}, (
            f"Marquez has no terminal run state for {namespace}/{job_name}; states={states}"
        )
```

Call it from the OpenLineage E2E test for the demo product job that the runtime emits, using namespace from compiled artifacts rather than a hardcoded namespace string.

- [ ] **Step 5: Run lineage tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_runtime_lineage_strictness.py tests/e2e/test_lineage_roundtrip_e2e.py -v
```

Expected: unit tests PASS. E2E tests PASS only when Marquez is running and reachable through the configured test environment.

- [ ] **Step 6: Commit**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py plugins/floe-orchestrator-dagster/tests/unit/test_runtime_lineage_strictness.py tests/e2e/test_observability.py tests/e2e/test_lineage_roundtrip_e2e.py
git commit -m "feat: require marquez-visible lineage proof"
```

## Task 6: Run the Validation Ladder and Catalogue Remaining Product Failures

**Files:**
- Create: `docs/validation/2026-04-25-alpha-reliability-validation.md`
- Modify: `.pre-commit-config.yaml` or hook config only if local hooks miss a deterministic check that CI runs.

- [ ] **Step 1: Run local fast checks**

Run:

```bash
make lint
make typecheck
make test-unit
```

Expected: PASS. If a command fails, fix the failing code or test in the same task before moving on.

- [ ] **Step 2: Run focused Dagster integration tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py plugins/floe-orchestrator-dagster/tests/integration/test_loud_failure_integration.py -v
```

Expected: PASS with real integration fixtures available.

- [ ] **Step 3: Run K8s-native platform validation**

Run:

```bash
make deploy-local
make demo-e2e
```

Expected: `make deploy-local` deploys services into Kind and `make demo-e2e` proves the demo materialization path.

- [ ] **Step 4: Run DevPod + Hetzner validation**

Run the project’s DevPod/Hetzner validation entrypoint:

```bash
make test
make demo-e2e
```

Expected: E2E, integration tests, and demo validation run against the remote environment with stable network. If the train-network transient class appears again, record concrete timestamps and failing endpoints instead of reclassifying product bugs.

- [ ] **Step 5: Run pre-push hooks**

Run:

```bash
pre-commit run --hook-stage push --all-files
```

Expected: PASS. If CI catches deterministic formatting, lint, type, or test selection issues not covered here, update local hooks in the same commit.

- [ ] **Step 6: Write validation summary**

Create `docs/validation/2026-04-25-alpha-reliability-validation.md`:

```markdown
# Alpha Reliability Closure Validation - 2026-04-25

## Commands

| Command | Result | Evidence |
| --- | --- | --- |

## Remaining Failures

| Class | Failure | Owner Path | Blocking Alpha |
| --- | --- | --- | --- |

## Decision

Alpha reliability closure is complete only when the unified Dagster runtime path writes expected Iceberg tables and Marquez exposes lifecycle lineage for the demo run.
```

Add one command row for every command executed in steps 1-5. Use `PASS` or `FAIL` as the result value and include the first actionable failure line for every failed command. Add one remaining-failure row for every unresolved issue using the classes already listed in the table header.

- [ ] **Step 7: Commit**

Run:

```bash
git add docs/validation/2026-04-25-alpha-reliability-validation.md .pre-commit-config.yaml
git commit -m "test: validate alpha reliability closure"
```

If `.pre-commit-config.yaml` did not change, omit it from `git add`.

## Task 7: Ship the PR

**Files:**
- Modify only files changed by Tasks 1-6.

- [ ] **Step 1: Inspect final diff**

Run:

```bash
git status --short
git diff --stat origin/main...HEAD
git log --oneline origin/main..HEAD
```

Expected: only alpha reliability closure changes are present.

- [ ] **Step 2: Run final verification**

Run:

```bash
make check
```

Expected: PASS locally. If `make check` excludes E2E by design, cite Task 6 E2E evidence in the PR.

- [ ] **Step 3: Push branch**

Run:

```bash
git push -u origin HEAD
```

Expected: branch is pushed successfully.

- [ ] **Step 4: Open PR**

Run:

```bash
gh pr create \
  --title "Close alpha reliability runtime spine" \
  --body-file docs/validation/2026-04-25-alpha-reliability-validation.md
```

Expected: PR opens against `main`.

- [ ] **Step 5: Watch CI**

Run:

```bash
gh pr checks --watch
```

Expected: CI and Helm CI pass. If Helm CI fails, use the new diagnostics output to classify the failure and fix the specific readiness/runtime issue in a follow-up commit on the PR branch.

## Plan Coverage Check

- Dagster path collapse: Task 2.
- Strict configured capabilities: Task 3.
- Iceberg write proof: Task 4.
- OpenLineage and Marquez proof: Task 5.
- Live Helm CI classification: Task 1 and Task 6.
- DevPod/Hetzner validation: Task 6.
- Local/CI hook alignment: Task 6.
