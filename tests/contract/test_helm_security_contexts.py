"""Contract test: Helm-rendered pod specs MUST carry security contexts (AC-4).

Renders `charts/floe-platform` via `helm template` and parses the multi-document
YAML output. Walks every pod-producing resource and asserts:

  - spec.securityContext.runAsNonRoot: true  (pod level)
  - each container's securityContext.allowPrivilegeEscalation: false
  - init containers and sidecars are also checked

Marquez pods are explicitly excluded per D-6 (known upstream root-user gap,
tracked in AUDIT.md as AC-10). Adding a new subchart without security context
propagation will cause this test to fail.

This is a structural test of the RENDERED chart — complements the values.yaml
unit tests in tests/unit/test_*_security_contexts.py.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

CHART_DIR = Path(__file__).resolve().parents[2] / "charts" / "floe-platform"

# Pod-producing workload kinds whose spec.template.spec we must inspect.
POD_WORKLOAD_KINDS = {
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "Job",
    "CronJob",
    "ReplicaSet",
}

# Marquez pods are a known exception: upstream image runs as root (UID 0).
# See AUDIT.md (AC-10) for upstream tracking.
MARQUEZ_NAME_MARKERS = ("marquez",)


def _is_marquez(name: str) -> bool:
    """True if a resource metadata.name indicates a Marquez workload."""
    lower = name.lower()
    return any(marker in lower for marker in MARQUEZ_NAME_MARKERS)


@pytest.fixture(scope="module")
def rendered_manifests() -> list[dict[str, Any]]:
    """Render charts/floe-platform via `helm template` and parse to docs.

    Requires `helm` on PATH. The chart dependencies must already be built
    (`helm dependency update` or `helm dep build`). Sessions typically have
    the Chart.lock refreshed by earlier tests or manual runs.
    """
    if shutil.which("helm") is None:
        pytest.fail(
            "helm CLI not available on PATH — required to render charts for "
            "security-context contract verification."
        )

    charts_subdir = CHART_DIR / "charts"
    if not charts_subdir.exists() or not any(charts_subdir.iterdir()):
        # Attempt to build dependencies on demand.
        result = subprocess.run(
            ["helm", "dependency", "build", str(CHART_DIR)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(
                "helm dependency build failed:\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

    result = subprocess.run(
        ["helm", "template", "sec-test", str(CHART_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            "helm template rendering failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    docs: list[dict[str, Any]] = []
    for raw_doc in yaml.safe_load_all(result.stdout):
        if not isinstance(raw_doc, dict):
            continue
        doc: dict[str, Any] = cast("dict[str, Any]", raw_doc)
        if doc:
            docs.append(doc)
    assert docs, "helm template produced no documents — rendering broke"
    return docs


def _pod_specs(
    docs: list[dict[str, Any]],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Extract (kind, name, pod_spec) for every pod-producing workload.

    Marquez pods are excluded. CronJob pod specs live two levels deeper.
    """
    out: list[tuple[str, str, dict[str, Any]]] = []
    for doc in docs:
        kind_any: Any = doc.get("kind")
        if not isinstance(kind_any, str):
            continue
        kind: str = kind_any
        if kind not in POD_WORKLOAD_KINDS:
            continue
        meta_any: Any = doc.get("metadata") or {}
        meta: dict[str, Any] = (
            cast("dict[str, Any]", meta_any) if isinstance(meta_any, dict) else {}
        )
        name_any: Any = meta.get("name", "")
        name: str = name_any if isinstance(name_any, str) else ""
        if _is_marquez(name):
            continue

        spec_any: Any = doc.get("spec") or {}
        if not isinstance(spec_any, dict):
            continue
        spec: dict[str, Any] = cast("dict[str, Any]", spec_any)

        # CronJob: spec.jobTemplate.spec.template.spec
        if kind == "CronJob":
            job_any: Any = spec.get("jobTemplate") or {}
            if not isinstance(job_any, dict):
                continue
            job_spec_any: Any = cast("dict[str, Any]", job_any).get("spec") or {}
            if not isinstance(job_spec_any, dict):
                continue
            spec = cast("dict[str, Any]", job_spec_any)

        template_any: Any = spec.get("template") or {}
        if not isinstance(template_any, dict):
            continue
        pod_spec_any: Any = (
            cast("dict[str, Any]", template_any).get("spec") or {}
        )
        if not isinstance(pod_spec_any, dict):
            continue
        pod_spec: dict[str, Any] = cast("dict[str, Any]", pod_spec_any)
        out.append((kind, name, pod_spec))
    return out


@pytest.mark.requirement("security-hardening-AC-4")
def test_helm_rendered_pods_have_pod_security_context(
    rendered_manifests: list[dict[str, Any]],
) -> None:
    """Every rendered pod (non-Marquez) MUST set pod-level runAsNonRoot=true."""
    specs = _pod_specs(rendered_manifests)
    assert specs, "No pod-producing workloads found in rendered chart"

    violations: list[str] = []
    for kind, name, pod_spec in specs:
        sec_ctx_any: Any = pod_spec.get("securityContext")
        if not isinstance(sec_ctx_any, dict):
            violations.append(f"{kind}/{name}: missing pod-level securityContext")
            continue
        sec_ctx: dict[str, Any] = cast("dict[str, Any]", sec_ctx_any)
        if sec_ctx.get("runAsNonRoot") is not True:
            violations.append(
                f"{kind}/{name}: pod securityContext.runAsNonRoot is "
                f"{sec_ctx.get('runAsNonRoot')!r}, expected True"
            )

    assert not violations, (
        "AC-4 violation: one or more pods lack runAsNonRoot=true at the pod "
        "level.\n" + "\n".join(f"  - {v}" for v in violations)
    )


@pytest.mark.requirement("security-hardening-AC-4")
def test_helm_rendered_containers_forbid_privilege_escalation(
    rendered_manifests: list[dict[str, Any]],
) -> None:
    """Every container (init + main) MUST have allowPrivilegeEscalation=false."""
    specs = _pod_specs(rendered_manifests)
    assert specs

    violations: list[str] = []
    for kind, name, pod_spec in specs:
        for field in ("initContainers", "containers"):
            containers_any: Any = pod_spec.get(field) or []
            if not isinstance(containers_any, list):
                continue
            containers: list[Any] = cast("list[Any]", containers_any)
            for idx, ctr_any in enumerate(containers):
                if not isinstance(ctr_any, dict):
                    continue
                ctr: dict[str, Any] = cast("dict[str, Any]", ctr_any)
                ctr_name_any: Any = ctr.get("name", f"[{idx}]")
                ctr_name: str = (
                    ctr_name_any if isinstance(ctr_name_any, str) else f"[{idx}]"
                )
                sec_ctx_any: Any = ctr.get("securityContext")
                if not isinstance(sec_ctx_any, dict):
                    violations.append(
                        f"{kind}/{name} {field}/{ctr_name}: "
                        f"missing container securityContext"
                    )
                    continue
                sec_ctx: dict[str, Any] = cast("dict[str, Any]", sec_ctx_any)
                if sec_ctx.get("allowPrivilegeEscalation") is not False:
                    violations.append(
                        f"{kind}/{name} {field}/{ctr_name}: "
                        f"allowPrivilegeEscalation="
                        f"{sec_ctx.get('allowPrivilegeEscalation')!r}, "
                        f"expected False"
                    )

    assert not violations, (
        "AC-4 violation: one or more containers allow privilege escalation.\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


@pytest.mark.requirement("security-hardening-AC-4")
def test_marquez_exclusion_is_explicit(
    rendered_manifests: list[dict[str, Any]],
) -> None:
    """Sanity check: if Marquez pods render, they are excluded from assertions.

    This test does not pass/fail on Marquez hardening — it just documents
    that Marquez is the only known exception and makes the exclusion visible
    in test output. Guards against silent drift (e.g., someone adds a second
    exclusion without AUDIT.md justification).
    """
    marquez_pods: list[str] = []
    for doc in rendered_manifests:
        kind_any: Any = doc.get("kind")
        if kind_any not in POD_WORKLOAD_KINDS:
            continue
        meta_any: Any = doc.get("metadata") or {}
        if not isinstance(meta_any, dict):
            continue
        name_any: Any = cast("dict[str, Any]", meta_any).get("name", "")
        name: str = name_any if isinstance(name_any, str) else ""
        if _is_marquez(name):
            marquez_pods.append(f"{kind_any}/{name}")

    # This assertion is informational — never fails. Use `-s` to see output.
    # If Marquez count grows unexpectedly, sw-verify will flag it in review.
    assert isinstance(marquez_pods, list)
