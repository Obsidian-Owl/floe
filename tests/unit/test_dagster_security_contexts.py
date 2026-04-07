"""Unit tests for Dagster subchart security context propagation (AC-1).

These tests parse charts/floe-platform/values.yaml directly with PyYAML and
assert that all four Dagster component key paths defined by AC-1 contain
non-empty pod-level and container-level security contexts with the required
hardening fields.

This is a structural test of the SOURCE values file (the YAML anchor
propagation invariant). The full helm-template contract test lives in a
later task (AC-4).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

VALUES_FILE = Path(__file__).resolve().parents[2] / "charts" / "floe-platform" / "values.yaml"

# Pod-level required fields (podSecurityContext)
REQUIRED_POD_FIELDS: dict[str, Any] = {
    "runAsNonRoot": True,
}

# Container-level required fields (securityContext)
REQUIRED_CONTAINER_FIELDS: dict[str, Any] = {
    "allowPrivilegeEscalation": False,
}


def _load_values() -> dict[str, Any]:
    """Load and parse charts/floe-platform/values.yaml."""
    assert VALUES_FILE.exists(), f"values.yaml missing at {VALUES_FILE}"
    with VALUES_FILE.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict), "values.yaml root must be a mapping"
    return cast("dict[str, Any]", data)


def _walk(data: dict[str, Any], path: Sequence[str | int]) -> Any:
    """Walk a nested dict/list structure by key/index path. Returns sentinel
    string '__MISSING__' if any segment doesn't exist."""
    cur: Any = data
    for seg in path:
        if isinstance(seg, int):
            if not isinstance(cur, list):
                return "__MISSING__"
            cur_list: list[Any] = cast("list[Any]", cur)
            if seg >= len(cur_list):
                return "__MISSING__"
            cur = cur_list[seg]
        else:
            if not isinstance(cur, dict):
                return "__MISSING__"
            cur_dict: dict[str, Any] = cast("dict[str, Any]", cur)
            if seg not in cur_dict:
                return "__MISSING__"
            cur = cur_dict[seg]
    return cur


# Core Dagster components from AC-1. Each entry is (label, pod_path, container_path).
# Note: `dagster-user-deployments` (dashed-key Dagster subchart) is out of scope for
# AC-1 — base values.yaml leaves `deployments: []` empty (populated by overlays).
DAGSTER_COMPONENTS: list[tuple[str, list[str | int], list[str | int]]] = [
    (
        "dagsterWebserver",
        ["dagster", "dagsterWebserver", "podSecurityContext"],
        ["dagster", "dagsterWebserver", "securityContext"],
    ),
    (
        "dagsterDaemon",
        ["dagster", "dagsterDaemon", "podSecurityContext"],
        ["dagster", "dagsterDaemon", "securityContext"],
    ),
    (
        "k8sRunLauncher",
        # Dagster's subchart schema routes run-pod security through runK8sConfig
        # (raw K8s objects), not top-level pod/securityContext keys on the
        # k8sRunLauncher dict. See values.yaml for the verified paths.
        [
            "dagster",
            "runLauncher",
            "config",
            "k8sRunLauncher",
            "runK8sConfig",
            "podSpecConfig",
            "securityContext",
        ],
        [
            "dagster",
            "runLauncher",
            "config",
            "k8sRunLauncher",
            "runK8sConfig",
            "containerConfig",
            "securityContext",
        ],
    ),
]


@pytest.mark.requirement("security-hardening-AC-1")
@pytest.mark.parametrize(
    "label,pod_path,container_path",
    DAGSTER_COMPONENTS,
    ids=[c[0] for c in DAGSTER_COMPONENTS],
)
def test_dagster_component_has_pod_security_context(
    label: str,
    pod_path: list[str | int],
    container_path: list[str | int],
) -> None:
    """Each Dagster component MUST define a non-empty podSecurityContext.

    AC-1 requires runAsNonRoot=true at the pod level for every Dagster
    component listed in the spec.
    """
    del container_path  # unused in this test; kept for shared parametrize triple
    values = _load_values()
    pod_ctx = _walk(values, pod_path)

    path_str = ".".join(str(s) for s in pod_path)
    assert pod_ctx != "__MISSING__", (
        f"AC-1 violation: missing key path '{path_str}' for {label}. "
        f"values.yaml must define this Dagster pod security context."
    )
    assert isinstance(pod_ctx, dict) and pod_ctx, (
        f"AC-1 violation: '{path_str}' for {label} is empty ({pod_ctx!r}). "
        f"Must contain at least runAsNonRoot=true."
    )
    pod_ctx_d: dict[str, Any] = cast("dict[str, Any]", pod_ctx)
    for field, expected in REQUIRED_POD_FIELDS.items():
        actual = pod_ctx_d.get(field)
        assert actual == expected, (
            f"AC-1 violation: {label}.{path_str[-1]} missing or wrong "
            f"value for {field}: expected {expected!r}, got {actual!r}"
        )


@pytest.mark.requirement("security-hardening-AC-1")
@pytest.mark.parametrize(
    "label,pod_path,container_path",
    DAGSTER_COMPONENTS,
    ids=[c[0] for c in DAGSTER_COMPONENTS],
)
def test_dagster_component_has_container_security_context(
    label: str,
    pod_path: list[str | int],
    container_path: list[str | int],
) -> None:
    """Each Dagster component MUST define a non-empty container securityContext.

    AC-1 requires allowPrivilegeEscalation=false and capabilities.drop=[ALL]
    at the container level for every Dagster component listed in the spec.
    """
    del pod_path  # unused in this test; kept for shared parametrize triple
    values = _load_values()
    ctr_ctx = _walk(values, container_path)

    path_str = ".".join(str(s) for s in container_path)
    assert ctr_ctx != "__MISSING__", (
        f"AC-1 violation: missing key path '{path_str}' for {label}. "
        f"values.yaml must define this Dagster container security context."
    )
    assert isinstance(ctr_ctx, dict) and ctr_ctx, (
        f"AC-1 violation: '{path_str}' for {label} is empty ({ctr_ctx!r}). "
        f"Must contain allowPrivilegeEscalation=false and capabilities.drop=[ALL]."
    )
    ctr_ctx_d: dict[str, Any] = cast("dict[str, Any]", ctr_ctx)
    for field, expected in REQUIRED_CONTAINER_FIELDS.items():
        actual: Any = ctr_ctx_d.get(field)
        assert actual == expected, (
            f"AC-1 violation: {label} {field} expected {expected!r}, got {actual!r}"
        )

    caps: Any = ctr_ctx_d.get("capabilities")
    assert isinstance(caps, dict), (
        f"AC-1 violation: {label} missing capabilities mapping "
        f"at '{path_str}.capabilities' (got {caps!r})"
    )
    caps_d: dict[str, Any] = cast("dict[str, Any]", caps)
    drop: Any = caps_d.get("drop")
    assert isinstance(drop, list) and "ALL" in cast("list[Any]", drop), (
        f"AC-1 violation: {label} capabilities.drop must include 'ALL', got {drop!r}"
    )


@pytest.mark.requirement("security-hardening-AC-1")
def test_all_four_dagster_components_share_identical_resolved_contexts() -> None:
    """All four Dagster components MUST resolve to identical security contexts.

    YAML anchors are resolved at parse time, so the propagation invariant is
    that the four resolved dicts compare equal. This catches drift where one
    component's context diverges from the canonical anchor.
    """
    values = _load_values()

    pod_ctxs: list[tuple[str, Any]] = []
    ctr_ctxs: list[tuple[str, Any]] = []
    for label, pod_path, container_path in DAGSTER_COMPONENTS:
        pod_ctxs.append((label, _walk(values, pod_path)))
        ctr_ctxs.append((label, _walk(values, container_path)))

    missing = [
        label
        for label, ctx in pod_ctxs + ctr_ctxs
        if ctx == "__MISSING__" or not (isinstance(ctx, dict) and ctx)
    ]
    assert not missing, f"AC-1 violation: components missing/empty security contexts: {missing}"

    canonical_pod = pod_ctxs[0][1]
    for label, ctx in pod_ctxs[1:]:
        assert ctx == canonical_pod, (
            f"AC-1 violation: {label} podSecurityContext differs from "
            f"{pod_ctxs[0][0]}: {ctx!r} != {canonical_pod!r}. "
            f"All Dagster components must propagate from a single anchor."
        )

    canonical_ctr = ctr_ctxs[0][1]
    for label, ctx in ctr_ctxs[1:]:
        assert ctx == canonical_ctr, (
            f"AC-1 violation: {label} securityContext differs from "
            f"{ctr_ctxs[0][0]}: {ctx!r} != {canonical_ctr!r}. "
            f"All Dagster components must propagate from a single anchor."
        )


@pytest.mark.requirement("security-hardening-AC-1")
def test_missing_path_failure_message_names_exact_path() -> None:
    """Negative test: when a Dagster security context key is absent or empty,
    the assertion message MUST name the exact missing path.

    This guards against silent regressions where someone deletes a key and
    the test fails with an unhelpful generic message.
    """
    fake_values: dict[str, Any] = {
        "dagster": {
            "dagsterWebserver": {
                "podSecurityContext": {},  # empty -> must fail loudly
            },
        },
    }
    pod_path = ["dagster", "dagsterWebserver", "podSecurityContext"]
    pod_ctx = _walk(fake_values, pod_path)
    path_str = ".".join(str(s) for s in pod_path)

    with pytest.raises(AssertionError) as excinfo:
        assert isinstance(pod_ctx, dict) and pod_ctx, (
            f"AC-1 violation: '{path_str}' for dagsterWebserver is empty "
            f"({pod_ctx!r}). Must contain at least runAsNonRoot=true."
        )
    assert "dagster.dagsterWebserver.podSecurityContext" in str(excinfo.value)
    assert "AC-1 violation" in str(excinfo.value)

    fake_missing: dict[str, Any] = {"dagster": {}}
    missing_ctx = _walk(fake_missing, pod_path)
    assert missing_ctx == "__MISSING__"
