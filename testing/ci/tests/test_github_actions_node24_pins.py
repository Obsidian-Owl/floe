from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS_DIR = Path(".github/workflows")

OLD_ACTION_PINS = {
    "actions/checkout": "34e114876b0b11c390a56381ad16ebd13914f8d5",  # pragma: allowlist secret
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",  # pragma: allowlist secret
    "astral-sh/setup-uv": "e4db8464a088ece1b920f60402e813ea4de65b8f",  # pragma: allowlist secret
    "azure/setup-helm": "1a275c3b69536ee54be43f2070a358922e12c8d4",  # pragma: allowlist secret
    "helm/kind-action": "a1b0e391336a6ee6713a0583f8c6240d70863de3",  # pragma: allowlist secret
}

NODE24_ACTION_PINS = {
    "actions/checkout": "de0fac2e4500dabe0009e67214ff5f5447ce83dd",  # pragma: allowlist secret
    "actions/setup-node": "48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e",  # pragma: allowlist secret
    "actions/setup-python": "a309ff8b426b58ec0e2a45f0f869d46889d02405",  # pragma: allowlist secret
    "astral-sh/setup-uv": "08807647e7069bb48b6ef5acd8ec9567f424441b",  # pragma: allowlist secret
    "Azure/setup-helm": "dda3372f752e03dde6b3237bc9431cdc2f7a02a2",  # pragma: allowlist secret
    "helm/kind-action": "ef37e7f390d99f746eb8b610417061a60e82a6cc",  # pragma: allowlist secret
}

USES_RE = re.compile(r"^\s*uses:\s*(?P<action>[^@\s#]+)@(?P<ref>[^\s#]+)")


def _workflow_files() -> list[Path]:
    return sorted(path for pattern in ("*.yml", "*.yaml") for path in WORKFLOWS_DIR.glob(pattern))


def _uses_entries() -> list[tuple[Path, int, str, str]]:
    entries: list[tuple[Path, int, str, str]] = []
    for workflow in _workflow_files():
        for line_number, line in enumerate(workflow.read_text().splitlines(), start=1):
            match = USES_RE.match(line)
            if match:
                entries.append(
                    (
                        workflow,
                        line_number,
                        match.group("action"),
                        match.group("ref"),
                    ),
                )
    return entries


@pytest.mark.requirement("github-actions-node24")
def test_no_known_old_node20_action_pins_remain() -> None:
    """Workflow files do not reference Node 20 action SHAs that block #271."""
    stale_pins = []
    old_refs = set(OLD_ACTION_PINS.values())

    for workflow, line_number, action, ref in _uses_entries():
        if ref in old_refs:
            stale_pins.append(f"{workflow}:{line_number}: {action}@{ref}")

    assert stale_pins == []


@pytest.mark.requirement("github-actions-node24")
def test_known_actions_use_exact_node24_compatible_pins() -> None:
    """Known workflow actions use the exact Node 24-compatible pinned refs."""
    invalid_refs = []

    for workflow, line_number, action, ref in _uses_entries():
        expected_ref = NODE24_ACTION_PINS.get(action)
        if expected_ref is not None and ref != expected_ref:
            invalid_refs.append(
                f"{workflow}:{line_number}: expected {action}@{expected_ref}, got {action}@{ref}",
            )

    assert invalid_refs == []


@pytest.mark.requirement("github-actions-node24")
def test_setup_helm_action_owner_uses_canonical_case() -> None:
    """The setup-helm owner is case-sensitive to prevent stale azure/setup-helm pins."""
    lowercase_setup_helm = []

    for workflow, line_number, action, ref in _uses_entries():
        if action == "azure/setup-helm":
            lowercase_setup_helm.append(f"{workflow}:{line_number}: {action}@{ref}")

    assert lowercase_setup_helm == []
