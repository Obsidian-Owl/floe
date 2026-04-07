"""Unit tests for OTel / Jaeger / MinIO security context propagation.

Covers AC-2 (OTel collector, Jaeger) and AC-3 (MinIO Bitnami schema) from the
security-hardening work unit. These tests parse charts/floe-platform/values.yaml
with PyYAML and assert the subchart key paths have correct hardening fields.

The full helm-template contract test lives in a later task (AC-4). These are
structural unit tests of the SOURCE values file.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

VALUES_FILE = (
    Path(__file__).resolve().parents[2]
    / "charts"
    / "floe-platform"
    / "values.yaml"
)

# Jaeger's upstream image is built for UID 10001. We must preserve it, not
# override with the PSS default of 1000.
JAEGER_REQUIRED_UID = 10001


def _load_values() -> dict[str, Any]:
    """Load and parse charts/floe-platform/values.yaml."""
    assert VALUES_FILE.exists(), f"values.yaml missing at {VALUES_FILE}"
    with VALUES_FILE.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict), "values.yaml root must be a mapping"
    return cast("dict[str, Any]", data)


def _walk(data: dict[str, Any], path: Sequence[str | int]) -> Any:
    """Walk a nested dict/list structure. Returns '__MISSING__' on miss."""
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


# =========================================================================
# AC-2: OTel collector
# =========================================================================


@pytest.mark.requirement("security-hardening-AC-2")
def test_otel_collector_has_pod_security_context() -> None:
    """OTel collector subchart MUST define pod-level runAsNonRoot=true.

    The subchart is aliased as `otel` in Chart.yaml (real name
    `opentelemetry-collector`). Standard Helm pattern: top-level
    `podSecurityContext` and `securityContext` keys.
    """
    values = _load_values()
    pod_ctx = _walk(values, ["otel", "podSecurityContext"])
    assert pod_ctx != "__MISSING__", (
        "AC-2 violation: missing key 'otel.podSecurityContext'. "
        "OTel collector subchart needs pod-level security context."
    )
    assert isinstance(pod_ctx, dict) and pod_ctx, (
        f"AC-2 violation: 'otel.podSecurityContext' is empty ({pod_ctx!r})"
    )
    pod_ctx_d: dict[str, Any] = cast("dict[str, Any]", pod_ctx)
    assert pod_ctx_d.get("runAsNonRoot") is True, (
        f"AC-2 violation: otel.podSecurityContext.runAsNonRoot must be True, "
        f"got {pod_ctx_d.get('runAsNonRoot')!r}"
    )


@pytest.mark.requirement("security-hardening-AC-2")
def test_otel_collector_has_container_security_context() -> None:
    """OTel collector container MUST drop ALL capabilities and forbid PE."""
    values = _load_values()
    ctr_ctx = _walk(values, ["otel", "securityContext"])
    assert ctr_ctx != "__MISSING__", (
        "AC-2 violation: missing key 'otel.securityContext'. "
        "OTel collector needs container-level security context."
    )
    assert isinstance(ctr_ctx, dict) and ctr_ctx, (
        f"AC-2 violation: 'otel.securityContext' is empty ({ctr_ctx!r})"
    )
    ctr_ctx_d: dict[str, Any] = cast("dict[str, Any]", ctr_ctx)
    assert ctr_ctx_d.get("allowPrivilegeEscalation") is False, (
        f"AC-2 violation: otel.securityContext.allowPrivilegeEscalation must "
        f"be False, got {ctr_ctx_d.get('allowPrivilegeEscalation')!r}"
    )
    caps: Any = ctr_ctx_d.get("capabilities")
    assert isinstance(caps, dict), (
        f"AC-2 violation: otel.securityContext.capabilities must be a mapping "
        f"(got {caps!r})"
    )
    caps_d: dict[str, Any] = cast("dict[str, Any]", caps)
    drop: Any = caps_d.get("drop")
    assert isinstance(drop, list) and "ALL" in cast("list[Any]", drop), (
        f"AC-2 violation: otel capabilities.drop must include 'ALL', got {drop!r}"
    )


# =========================================================================
# AC-2: Jaeger (preserve UID 10001)
# =========================================================================


@pytest.mark.requirement("security-hardening-AC-2")
def test_jaeger_preserves_uid_10001() -> None:
    """Jaeger's container image is built for UID 10001 — MUST NOT be overridden.

    We cannot use the shared PSS anchor (runAsUser=1000) verbatim because
    Jaeger's binary expects 10001. The contract: runAsUser at pod OR container
    level must be 10001, AND capabilities.drop must still include ALL.
    """
    values = _load_values()
    pod_ctx = _walk(values, ["jaeger", "allInOne", "podSecurityContext"])
    ctr_ctx = _walk(values, ["jaeger", "allInOne", "securityContext"])

    assert pod_ctx != "__MISSING__", (
        "AC-2 violation: missing 'jaeger.allInOne.podSecurityContext'"
    )
    assert ctr_ctx != "__MISSING__", (
        "AC-2 violation: missing 'jaeger.allInOne.securityContext'"
    )

    pod_d: dict[str, Any] = cast("dict[str, Any]", pod_ctx)
    ctr_d: dict[str, Any] = cast("dict[str, Any]", ctr_ctx)

    # UID 10001 must appear somewhere (pod OR container level)
    pod_uid = pod_d.get("runAsUser")
    ctr_uid = ctr_d.get("runAsUser")
    assert JAEGER_REQUIRED_UID in {pod_uid, ctr_uid}, (
        f"AC-2 violation: Jaeger must preserve runAsUser={JAEGER_REQUIRED_UID} "
        f"(pod={pod_uid!r}, container={ctr_uid!r}). Overriding this UID breaks "
        f"the upstream Jaeger image."
    )

    # Container-level hardening
    assert ctr_d.get("allowPrivilegeEscalation") is False, (
        f"AC-2 violation: jaeger container must disallow PE, "
        f"got {ctr_d.get('allowPrivilegeEscalation')!r}"
    )
    caps: Any = ctr_d.get("capabilities")
    assert isinstance(caps, dict), (
        f"AC-2 violation: jaeger capabilities must be a mapping (got {caps!r})"
    )
    caps_d: dict[str, Any] = cast("dict[str, Any]", caps)
    drop: Any = caps_d.get("drop")
    assert isinstance(drop, list) and "ALL" in cast("list[Any]", drop), (
        f"AC-2 violation: jaeger capabilities.drop must include 'ALL', got {drop!r}"
    )


# =========================================================================
# AC-3: MinIO (Bitnami schema with `enabled: true`)
# =========================================================================


@pytest.mark.requirement("security-hardening-AC-3")
def test_minio_pod_security_context_enabled_and_hardened() -> None:
    """MinIO Bitnami subchart MUST set podSecurityContext.enabled=true.

    Bitnami charts use a toggle-based schema: the context block has an
    `enabled:` flag alongside the actual fields.
    """
    values = _load_values()
    pod_ctx = _walk(values, ["minio", "podSecurityContext"])
    assert pod_ctx != "__MISSING__", (
        "AC-3 violation: missing 'minio.podSecurityContext'"
    )
    assert isinstance(pod_ctx, dict), (
        f"AC-3 violation: minio.podSecurityContext must be a mapping "
        f"(got {pod_ctx!r})"
    )
    pod_d: dict[str, Any] = cast("dict[str, Any]", pod_ctx)
    assert pod_d.get("enabled") is True, (
        f"AC-3 violation: minio.podSecurityContext.enabled must be True "
        f"(Bitnami toggle), got {pod_d.get('enabled')!r}"
    )
    assert pod_d.get("fsGroup") == 1000, (
        f"AC-3 violation: minio.podSecurityContext.fsGroup must be 1000, "
        f"got {pod_d.get('fsGroup')!r}"
    )


@pytest.mark.requirement("security-hardening-AC-3")
def test_minio_container_security_context_enabled_and_hardened() -> None:
    """MinIO Bitnami container context MUST set enabled=true and PSS fields."""
    values = _load_values()
    ctr_ctx = _walk(values, ["minio", "containerSecurityContext"])
    assert ctr_ctx != "__MISSING__", (
        "AC-3 violation: missing 'minio.containerSecurityContext'"
    )
    assert isinstance(ctr_ctx, dict), (
        f"AC-3 violation: minio.containerSecurityContext must be a mapping "
        f"(got {ctr_ctx!r})"
    )
    ctr_d: dict[str, Any] = cast("dict[str, Any]", ctr_ctx)
    assert ctr_d.get("enabled") is True, (
        f"AC-3 violation: minio.containerSecurityContext.enabled must be "
        f"True (Bitnami toggle), got {ctr_d.get('enabled')!r}"
    )
    assert ctr_d.get("runAsNonRoot") is True, (
        f"AC-3 violation: minio.containerSecurityContext.runAsNonRoot must "
        f"be True, got {ctr_d.get('runAsNonRoot')!r}"
    )
    assert ctr_d.get("runAsUser") == 1000, (
        f"AC-3 violation: minio.containerSecurityContext.runAsUser must be "
        f"1000, got {ctr_d.get('runAsUser')!r}"
    )
    assert ctr_d.get("allowPrivilegeEscalation") is False, (
        f"AC-3 violation: minio.containerSecurityContext."
        f"allowPrivilegeEscalation must be False, "
        f"got {ctr_d.get('allowPrivilegeEscalation')!r}"
    )
