"""Unit tests for containerized Helm validation tool targets (AC-5, AC-6, AC-7).

The Makefile targets `helm-validate`, `helm-security`, and `helm-test-unit`
MUST run their respective tools (kubeconform, kubesec, helm-unittest) via
pinned Docker images, NOT host-installed binaries. This guarantees repeatable
validation on any developer machine without prior tool installation.

These are structural tests of the Makefile source — they do not execute the
targets. Executing them against a live Docker daemon is an integration
concern handled in sw-verify.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"

# Forbid `:latest` tag on containerized tool images.
_LATEST_RE = re.compile(r":latest\b")


def _read_target_body(target: str) -> str:
    """Extract the recipe body for a Makefile target.

    Returns the lines between `target:` and the next blank line or the next
    top-level target line. Crude but deterministic for this test.
    """
    text = MAKEFILE.read_text(encoding="utf-8")
    lines = text.splitlines()
    body: list[str] = []
    in_target = False
    for line in lines:
        if not in_target:
            if re.match(rf"^{re.escape(target)}\s*:", line):
                in_target = True
            continue
        # End of recipe: blank line followed by next target, or a new
        # top-level target/.PHONY declaration.
        if line.strip() == "":
            break
        if line.startswith(".PHONY") or re.match(r"^[a-zA-Z0-9_.-]+\s*:", line):
            break
        body.append(line)
    return "\n".join(body)


def _assert_pinned_docker_image(body: str, image: str, target: str) -> None:
    """Assert the body runs `docker run` with a pinned (non-latest) image."""
    assert "docker run" in body, (
        f"Target '{target}' must invoke `docker run` to containerize the tool, "
        f"body:\n{body}"
    )
    assert image in body, (
        f"Target '{target}' must reference image '{image}', body:\n{body}"
    )
    # Find the image reference and ensure it has a pinned tag.
    # Pattern: <image>:<tag> where tag is not empty and not 'latest'.
    matches = re.findall(rf"{re.escape(image)}:(\S+)", body)
    assert matches, (
        f"Target '{target}' must reference '{image}:<tag>' with a pinned tag, "
        f"body:\n{body}"
    )
    for tag in matches:
        assert tag != "latest", (
            f"Target '{target}' uses '{image}:latest' — must be pinned to a "
            f"specific version for reproducibility"
        )


@pytest.mark.requirement("security-hardening-AC-5")
def test_helm_validate_uses_containerized_kubeconform() -> None:
    """`make helm-validate` MUST run kubeconform via a pinned Docker image."""
    body = _read_target_body("helm-validate")
    assert body, "helm-validate target not found in Makefile"
    _assert_pinned_docker_image(
        body, "ghcr.io/yannh/kubeconform", "helm-validate"
    )


@pytest.mark.requirement("security-hardening-AC-6")
def test_helm_security_uses_containerized_kubesec() -> None:
    """`make helm-security` MUST run kubesec via a pinned Docker image."""
    body = _read_target_body("helm-security")
    assert body, (
        "helm-security target not found in Makefile — AC-6 requires a "
        "containerized kubesec target"
    )
    _assert_pinned_docker_image(body, "kubesec/kubesec", "helm-security")


@pytest.mark.requirement("security-hardening-AC-7")
def test_helm_test_unit_uses_containerized_helm_unittest() -> None:
    """`make helm-test-unit` MUST run helm-unittest via a pinned Docker image.

    The AC requires this target to work WITHOUT the helm-unittest plugin
    installed on the host, so host-plugin-only invocation is a violation.
    """
    body = _read_target_body("helm-test-unit")
    assert body, "helm-test-unit target not found in Makefile"
    _assert_pinned_docker_image(
        body, "helmunittest/helm-unittest", "helm-test-unit"
    )
    # Must not require the host-installed helm plugin.
    assert "helm plugin list" not in body, (
        "helm-test-unit must not require host helm-unittest plugin — AC-7 "
        "requires containerized execution so the target works without host "
        "installation"
    )


@pytest.mark.requirement("security-hardening-AC-5")
@pytest.mark.requirement("security-hardening-AC-6")
@pytest.mark.requirement("security-hardening-AC-7")
def test_containerized_targets_do_not_use_latest_tag() -> None:
    """None of the three containerized tool targets may use `:latest`.

    Redundant with individual assertions but catches drift where someone
    adds a new image reference and forgets to pin it.
    """
    for target in ("helm-validate", "helm-security", "helm-test-unit"):
        body = _read_target_body(target)
        if not body:
            continue  # individual tests will flag missing targets
        assert not _LATEST_RE.search(body), (
            f"Target '{target}' uses ':latest' tag — must be pinned"
        )
