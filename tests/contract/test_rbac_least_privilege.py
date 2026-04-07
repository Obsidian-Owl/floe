"""Contract test: test-runner Role RBAC follows least-privilege (AC-8, AC-9).

The standard and destructive E2E test runner Roles live in
`testing/k8s/rbac/`. This test parses them as multi-document YAML and
asserts the secrets rules are scoped correctly:

AC-8 (standard runner):
    - Secrets rule must NOT include `list` or `watch` verbs — only `get`
      is needed for Helm release state queries.

AC-9 (destructive runner):
    - `update` and `delete` on secrets MUST carry a `resourceNames`
      constraint restricting access to Helm release secret patterns
      (prefix `sh.helm.release.v1.`). K8s does not support
      `resourceNames` with `create`, so `create` may remain unscoped;
      this is documented in the Role file.

The test fails if either constraint is relaxed in future edits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

RBAC_DIR = (
    Path(__file__).resolve().parents[2] / "testing" / "k8s" / "rbac"
)
STANDARD_RUNNER_FILE = RBAC_DIR / "e2e-test-runner.yaml"
DESTRUCTIVE_RUNNER_FILE = RBAC_DIR / "e2e-destructive-runner.yaml"

# Helm 3 stores release state in secrets with this name prefix.
HELM_RELEASE_PREFIX = "sh.helm.release.v1."


def _load_role(path: Path) -> dict[str, Any]:
    """Load a multi-document YAML file and return the single Role document."""
    assert path.exists(), f"RBAC file missing: {path}"
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    roles: list[dict[str, Any]] = []
    for doc_any in docs:
        if not isinstance(doc_any, dict):
            continue
        doc: dict[str, Any] = cast("dict[str, Any]", doc_any)
        if doc.get("kind") == "Role":
            roles.append(doc)
    assert len(roles) == 1, (
        f"Expected exactly one Role in {path.name}, found {len(roles)}"
    )
    return roles[0]


def _secrets_rules(role: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every rule entry that targets the core `secrets` resource."""
    rules_any: Any = role.get("rules") or []
    assert isinstance(rules_any, list), "Role.rules must be a list"
    rules: list[Any] = cast("list[Any]", rules_any)
    out: list[dict[str, Any]] = []
    for rule_any in rules:
        if not isinstance(rule_any, dict):
            continue
        rule: dict[str, Any] = cast("dict[str, Any]", rule_any)
        api_groups_any: Any = rule.get("apiGroups") or []
        resources_any: Any = rule.get("resources") or []
        if not isinstance(api_groups_any, list) or not isinstance(
            resources_any, list
        ):
            continue
        api_groups: list[Any] = cast("list[Any]", api_groups_any)
        resources: list[Any] = cast("list[Any]", resources_any)
        if "" in api_groups and "secrets" in resources:
            out.append(rule)
    return out


# =========================================================================
# AC-8: Standard test runner — read-only, no list/watch on secrets
# =========================================================================


@pytest.mark.requirement("security-hardening-AC-8")
def test_standard_runner_secrets_rule_forbids_list_and_watch() -> None:
    """Standard runner Role MUST NOT have `list` or `watch` on secrets."""
    role = _load_role(STANDARD_RUNNER_FILE)
    rules = _secrets_rules(role)
    assert rules, (
        "AC-8 violation: standard runner Role has no secrets rule at all — "
        "expected a read-only `get` rule for Helm release state queries"
    )

    for rule in rules:
        verbs_any: Any = rule.get("verbs") or []
        assert isinstance(verbs_any, list)
        verbs: list[Any] = cast("list[Any]", verbs_any)
        forbidden = {v for v in ("list", "watch") if v in verbs}
        assert not forbidden, (
            f"AC-8 violation: standard runner secrets rule must not include "
            f"{forbidden!r}; rule: {rule!r}"
        )


@pytest.mark.requirement("security-hardening-AC-8")
def test_standard_runner_secrets_rule_still_allows_get() -> None:
    """Standard runner MUST retain `get` on secrets (Helm state queries)."""
    role = _load_role(STANDARD_RUNNER_FILE)
    rules = _secrets_rules(role)
    has_get = any(
        "get" in cast("list[Any]", (r.get("verbs") or [])) for r in rules
    )
    assert has_get, (
        "AC-8 violation: standard runner must retain `get` on secrets so "
        "Helm release state queries still work"
    )


# =========================================================================
# AC-9: Destructive runner — resourceNames on update/delete
# =========================================================================


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_update_delete_scoped_by_resource_names() -> None:
    """Destructive runner MUST scope secrets update/delete via resourceNames.

    K8s does not support resourceNames with `create`, so a separate rule may
    grant unscoped `create` on secrets. But any rule that grants `update` or
    `delete` on secrets MUST carry a `resourceNames` constraint that
    includes a Helm release secret pattern.
    """
    role = _load_role(DESTRUCTIVE_RUNNER_FILE)
    rules = _secrets_rules(role)
    assert rules, (
        "AC-9 violation: destructive runner Role has no secrets rule at all"
    )

    mutating_verbs = {"update", "delete"}
    mutating_rules: list[dict[str, Any]] = []
    for rule in rules:
        verbs_any: Any = rule.get("verbs") or []
        if not isinstance(verbs_any, list):
            continue
        verbs_list: list[Any] = cast("list[Any]", verbs_any)
        verbs_set: set[str] = {
            v for v in verbs_list if isinstance(v, str)
        }
        if verbs_set & mutating_verbs:
            mutating_rules.append(rule)

    assert mutating_rules, (
        "AC-9 violation: destructive runner has no secrets update/delete "
        "rule — expected a scoped rule for Helm release state mutation"
    )

    for rule in mutating_rules:
        resource_names_any: Any = rule.get("resourceNames")
        assert isinstance(resource_names_any, list) and resource_names_any, (
            f"AC-9 violation: secrets mutation rule must carry a non-empty "
            f"resourceNames list; rule: {rule!r}"
        )
        resource_names: list[Any] = cast("list[Any]", resource_names_any)
        # At least one entry must reference the Helm release prefix (either
        # as a literal `sh.helm.release.v1.*` or a wildcard name).
        has_helm_scope = any(
            isinstance(n, str) and HELM_RELEASE_PREFIX in n
            for n in resource_names
        )
        assert has_helm_scope, (
            f"AC-9 violation: secrets mutation rule resourceNames must "
            f"include a Helm release prefix '{HELM_RELEASE_PREFIX}*' "
            f"entry; got {resource_names!r}"
        )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_does_not_grant_unscoped_mutation() -> None:
    """No secrets rule may grant update or delete without resourceNames.

    This catches the regression where someone re-adds a broad rule like
    `verbs: [get, list, watch, create, update, delete]` without resourceNames.
    """
    role = _load_role(DESTRUCTIVE_RUNNER_FILE)
    rules = _secrets_rules(role)
    for rule in rules:
        verbs_any: Any = rule.get("verbs") or []
        if not isinstance(verbs_any, list):
            continue
        verbs_list: list[Any] = cast("list[Any]", verbs_any)
        verbs_set: set[str] = {
            v for v in verbs_list if isinstance(v, str)
        }
        if verbs_set & {"update", "delete"}:
            names_any: Any = rule.get("resourceNames")
            assert isinstance(names_any, list) and names_any, (
                f"AC-9 violation: rule grants update/delete on secrets "
                f"without resourceNames scoping; rule: {rule!r}"
            )
