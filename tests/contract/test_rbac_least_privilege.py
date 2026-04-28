"""Contract test: test-runner Role RBAC follows least-privilege (AC-8, AC-9).

The standard and destructive E2E test runner Roles are now rendered from
the Helm chart at `charts/floe-platform/templates/tests/rbac-*.yaml`.
This test renders those templates with `tests.enabled=true`, parses the
multi-document YAML, and asserts the secrets rules are scoped correctly:

AC-8 (standard runner):
    - Secrets rule must NOT include `list` or `watch` verbs — only `get`
      is needed for Helm release state queries.

AC-9 (destructive runner):
    - `update` and `delete` on secrets MUST carry a `resourceNames`
      constraint restricting access to Helm release secret patterns
      (prefix `sh.helm.release.v1.`). K8s does not support
      `resourceNames` with `create`, so `create` may remain unscoped;
      this is documented in the Role template.

The test fails if either constraint is relaxed in future edits. Because
the source of truth is the chart template, chart-level regressions are
caught here too.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

CHART_DIR = Path(__file__).resolve().parents[2] / "charts" / "floe-platform"
STANDARD_TEMPLATE = "templates/tests/rbac-standard.yaml"
DESTRUCTIVE_TEMPLATE = "templates/tests/rbac-destructive.yaml"
PRE_UPGRADE_HOOK_TEMPLATE = "templates/hooks/pre-upgrade-statefulset-cleanup.yaml"

# Helm 3 stores release state in secrets with this name prefix.
HELM_RELEASE_PREFIX = "sh.helm.release.v1."
HELM_PRE_UPGRADE_HOOK_NAME = "floe-platform-pre-upgrade"
HELM_PRE_UPGRADE_DASHBOARDS_HOOK_NAME = "floe-platform-grafana-dashboards"
KIND_TO_RBAC_RESOURCE = {
    "ConfigMap": ("", "configmaps"),
    "Deployment": ("apps", "deployments"),
    "Job": ("batch", "jobs"),
    "NetworkPolicy": ("networking.k8s.io", "networkpolicies"),
    "PersistentVolumeClaim": ("", "persistentvolumeclaims"),
    "PodDisruptionBudget": ("policy", "poddisruptionbudgets"),
    "Role": ("rbac.authorization.k8s.io", "roles"),
    "RoleBinding": ("rbac.authorization.k8s.io", "rolebindings"),
    "Service": ("", "services"),
    "ServiceAccount": ("", "serviceaccounts"),
    "StatefulSet": ("apps", "statefulsets"),
}
HELM_CHART_MANAGER_VERBS = {"get", "list", "watch", "create", "patch", "update", "delete"}


def _render_role(template: str) -> dict[str, Any]:
    """Render a single RBAC template from the chart and return the Role doc.

    Uses `helm template -s` with `tests.enabled=true` so the chart-gated
    test resources are emitted. Fails fast if helm is missing or the
    template renders no Role.
    """
    if shutil.which("helm") is None:
        pytest.fail(
            "helm CLI not available on PATH — required to render test RBAC "
            "for least-privilege contract verification."
        )

    result = subprocess.run(
        [
            "helm",
            "template",
            "floe-platform",
            str(CHART_DIR),
            "-f",
            str(CHART_DIR / "values-test.yaml"),
            "--set",
            "tests.enabled=true",
            "-s",
            template,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"helm template rendering failed for {template}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    roles = _roles_from_yaml(result.stdout, template)
    assert len(roles) == 1, f"Expected exactly one Role in rendered {template}, found {len(roles)}"
    return roles[0]


def _render_roles(template: str) -> list[dict[str, Any]]:
    """Render a template from the chart and return all Role docs."""
    if shutil.which("helm") is None:
        pytest.fail(
            "helm CLI not available on PATH — required to render test RBAC "
            "for least-privilege contract verification."
        )

    args = [
        "helm",
        "template",
        "floe-platform",
        str(CHART_DIR),
        "-f",
        str(CHART_DIR / "values-test.yaml"),
        "--set",
        "tests.enabled=true",
    ]
    # Helm does not support selecting hook templates with --show-only reliably,
    # so render the full chart and filter the Role documents by metadata below.
    if not template.startswith("templates/hooks/"):
        args.extend(["-s", template])

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"helm template rendering failed for {template}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    return _roles_from_yaml(result.stdout, template)


def _roles_from_yaml(rendered_yaml: str, template: str) -> list[dict[str, Any]]:
    """Parse rendered YAML and return Role documents."""
    docs = list(yaml.safe_load_all(rendered_yaml))
    roles: list[dict[str, Any]] = []
    for doc_any in docs:
        if not isinstance(doc_any, dict):
            continue
        doc: dict[str, Any] = cast("dict[str, Any]", doc_any)
        if doc.get("kind") == "Role":
            roles.append(doc)
    assert roles, f"Expected at least one Role in rendered {template}, found none"
    return roles


def _render_all_chart_docs() -> list[dict[str, Any]]:
    """Render the test chart values and return every Kubernetes document."""
    result = subprocess.run(
        [
            "helm",
            "template",
            "floe-platform",
            str(CHART_DIR),
            "-f",
            str(CHART_DIR / "values-test.yaml"),
            "--set",
            "tests.enabled=true",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"helm template rendering failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    return [
        cast("dict[str, Any]", doc)
        for doc in yaml.safe_load_all(result.stdout)
        if isinstance(doc, dict)
    ]


def _secrets_rules(role: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every rule entry that targets the core `secrets` resource."""
    return _rules_for(role, api_group="", resource="secrets")


def _rules_for(role: dict[str, Any], *, api_group: str, resource: str) -> list[dict[str, Any]]:
    """Return every rule entry for a specific apiGroup/resource pair."""
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
        if not isinstance(api_groups_any, list) or not isinstance(resources_any, list):
            continue
        api_groups: list[Any] = cast("list[Any]", api_groups_any)
        resources: list[Any] = cast("list[Any]", resources_any)
        if api_group in api_groups and resource in resources:
            out.append(rule)
    return out


def _verbs(rule: dict[str, Any]) -> set[str]:
    """Return normalized string verbs from an RBAC rule."""
    verbs_any: Any = rule.get("verbs") or []
    assert isinstance(verbs_any, list), f"Role rule verbs must be a list: {rule!r}"
    return {v for v in cast("list[Any]", verbs_any) if isinstance(v, str)}


def _resource_names(rule: dict[str, Any]) -> list[str]:
    """Return normalized string resourceNames from an RBAC rule."""
    resource_names_any: Any = rule.get("resourceNames") or []
    assert isinstance(resource_names_any, list), (
        f"Role rule resourceNames must be a list when present: {rule!r}"
    )
    return [n for n in cast("list[Any]", resource_names_any) if isinstance(n, str)]


def _assert_read_only_chart_management_access(
    role: dict[str, Any],
    *,
    api_group: str,
    resource: str,
) -> None:
    """Assert Helm can inspect chart-managed resources."""
    rules = _rules_for(role, api_group=api_group, resource=resource)
    assert any({"get", "list", "watch"}.issubset(_verbs(rule)) for rule in rules), (
        f"Destructive runner must have get/list/watch on {resource} so Helm "
        "can wait on hooks and inspect chart-managed resources during rollback."
    )


def _assert_scoped_hook_delete(
    role: dict[str, Any],
    *,
    api_group: str,
    resource: str,
) -> None:
    """Assert the chart's pre-upgrade hook resource can be deleted."""
    rules = _rules_for(role, api_group=api_group, resource=resource)
    assert _has_delete_permission_for_name(rules, HELM_PRE_UPGRADE_HOOK_NAME), (
        "Destructive runner must be able to delete the pre-upgrade hook "
        f"{resource} {HELM_PRE_UPGRADE_HOOK_NAME!r}."
    )


def _has_delete_permission_for_name(rules: list[dict[str, Any]], resource_name: str) -> bool:
    """Return whether any rule can delete the given resource name."""
    for rule in rules:
        if "delete" not in _verbs(rule):
            continue
        names = _resource_names(rule)
        if not names or resource_name in names:
            return True
    return False


# =========================================================================
# AC-8: Standard test runner — read-only, no list/watch on secrets
# =========================================================================


@pytest.mark.requirement("security-hardening-AC-8")
def test_standard_runner_secrets_rule_forbids_list_and_watch() -> None:
    """Standard runner Role MUST NOT have `list` or `watch` on secrets."""
    role = _render_role(STANDARD_TEMPLATE)
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
    role = _render_role(STANDARD_TEMPLATE)
    rules = _secrets_rules(role)
    has_get = any("get" in cast("list[Any]", (r.get("verbs") or [])) for r in rules)
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
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    rules = _secrets_rules(role)
    assert rules, "AC-9 violation: destructive runner Role has no secrets rule at all"

    mutating_verbs = {"update", "delete"}
    mutating_rules: list[dict[str, Any]] = []
    for rule in rules:
        verbs_any: Any = rule.get("verbs") or []
        if not isinstance(verbs_any, list):
            continue
        verbs_list: list[Any] = cast("list[Any]", verbs_any)
        verbs_set: set[str] = {v for v in verbs_list if isinstance(v, str)}
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
            isinstance(n, str) and HELM_RELEASE_PREFIX in n for n in resource_names
        )
        assert has_helm_scope, (
            f"AC-9 violation: secrets mutation rule resourceNames must "
            f"include a Helm release prefix '{HELM_RELEASE_PREFIX}*' "
            f"entry; got {resource_names!r}"
        )
        # Revision-window regression guard. The range loop in
        # templates/tests/rbac-destructive.yaml expands
        # `tests.destructive.helmRevisionWindow` (default 20) into a
        # literal list of `sh.helm.release.v1.<release>.vN` names. If
        # somebody lowers that default to a tiny number (or the range
        # loop accidentally collapses), destructive E2E tests will fail
        # with an opaque RBAC 403 on the Nth helm upgrade. A minimum
        # window of 10 gives enough headroom for any realistic test
        # suite's worth of consecutive `helm upgrade` calls before
        # cleanup. Raising the floor requires conscious review.
        helm_scoped_names = [
            n for n in resource_names if isinstance(n, str) and HELM_RELEASE_PREFIX in n
        ]
        assert len(helm_scoped_names) >= 10, (
            f"AC-9 regression guard: destructive runner authorizes only "
            f"{len(helm_scoped_names)} Helm release revisions — minimum is 10 "
            f"to cover realistic helm-upgrade test sequences. If this is "
            f"intentional, raise tests.destructive.helmRevisionWindow in "
            f"values.yaml and update this assertion together."
        )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_does_not_grant_unscoped_mutation() -> None:
    """No secrets rule may grant update or delete without resourceNames.

    This catches the regression where someone re-adds a broad rule like
    `verbs: [get, list, watch, create, update, delete]` without resourceNames.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    rules = _secrets_rules(role)
    for rule in rules:
        verbs_any: Any = rule.get("verbs") or []
        if not isinstance(verbs_any, list):
            continue
        verbs_list: list[Any] = cast("list[Any]", verbs_any)
        verbs_set: set[str] = {v for v in verbs_list if isinstance(v, str)}
        if verbs_set & {"update", "delete"}:
            names_any: Any = rule.get("resourceNames")
            assert isinstance(names_any, list) and names_any, (
                f"AC-9 violation: rule grants update/delete on secrets "
                f"without resourceNames scoping; rule: {rule!r}"
            )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_splits_read_only_pod_subresources() -> None:
    """Pod log/status subresources must not inherit pod create/delete verbs."""
    role = _render_role(DESTRUCTIVE_TEMPLATE)

    assert set().union(
        *(_verbs(rule) for rule in _rules_for(role, api_group="", resource="pods/log"))
    ) == {
        "get",
        "list",
        "watch",
    }
    assert set().union(
        *(_verbs(rule) for rule in _rules_for(role, api_group="", resource="pods/status"))
    ) == {
        "get",
        "list",
        "watch",
        "patch",
        "update",
    }


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_limits_events_to_read_only() -> None:
    """Destructive runner keeps event verbs aligned with rendered Dagster Role.

    The upstream Dagster chart grants event mutation verbs. Because destructive
    tests run ``helm upgrade`` in-cluster, Kubernetes rejects Role patching
    unless the acting identity already holds every verb in that rendered Role.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    assert set().union(
        *(_verbs(rule) for rule in _rules_for(role, api_group="", resource="events"))
    ) == {
        "create",
        "delete",
        "deletecollection",
        "get",
        "list",
        "patch",
        "update",
        "watch",
    }


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_limits_jobs_status_to_status_verbs() -> None:
    """Job status keeps only verbs needed by status access and Dagster Role patching."""
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    assert set().union(
        *(_verbs(rule) for rule in _rules_for(role, api_group="batch", resource="jobs/status"))
    ) == {
        "get",
        "list",
        "patch",
        "update",
        "watch",
    }


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_can_manage_pre_upgrade_hook_identity_scoped() -> None:
    """Destructive runner may manage only the chart's pre-upgrade hook identity.

    Helm executes the destructive upgrade test as the destructive test-runner
    ServiceAccount. The chart's pre-upgrade hook is annotated with
    `before-hook-creation`, so Helm must delete and recreate the hook
    ServiceAccount, Role, and RoleBinding during `helm upgrade`.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)

    _assert_read_only_chart_management_access(
        role,
        api_group="",
        resource="serviceaccounts",
    )
    core_rules = _rules_for(role, api_group="", resource="serviceaccounts")
    assert any("create" in _verbs(rule) for rule in core_rules), (
        "Destructive runner must be able to create the pre-upgrade hook "
        "ServiceAccount; Kubernetes RBAC cannot scope create by resourceNames."
    )
    _assert_scoped_hook_delete(role, api_group="", resource="serviceaccounts")

    for resource in ("roles", "rolebindings"):
        _assert_read_only_chart_management_access(
            role,
            api_group="rbac.authorization.k8s.io",
            resource=resource,
        )
        rbac_rules = _rules_for(
            role,
            api_group="rbac.authorization.k8s.io",
            resource=resource,
        )
        assert any("create" in _verbs(rule) for rule in rbac_rules), (
            f"Destructive runner must be able to create pre-upgrade hook {resource}; "
            "Kubernetes RBAC cannot scope create by resourceNames."
        )
        _assert_scoped_hook_delete(
            role,
            api_group="rbac.authorization.k8s.io",
            resource=resource,
        )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_can_grant_pre_upgrade_hook_role_without_escalation() -> None:
    """Destructive runner must already hold permissions granted by hook Roles.

    Kubernetes rejects Role creation when a ServiceAccount attempts to grant
    permissions it does not already hold. Helm creates the pre-upgrade hook
    Role during `helm upgrade`, so the destructive runner must cover the hook
    Role's statefulsets verbs or upgrades fail before the chart is applied.
    """
    destructive_role = _render_role(DESTRUCTIVE_TEMPLATE)
    hook_roles = [
        role
        for role in _render_roles(PRE_UPGRADE_HOOK_TEMPLATE)
        if role.get("metadata", {}).get("name") == HELM_PRE_UPGRADE_HOOK_NAME
    ]
    assert hook_roles, f"Expected rendered hook Role {HELM_PRE_UPGRADE_HOOK_NAME!r}"

    for hook_role in hook_roles:
        for hook_rule in cast("list[dict[str, Any]]", hook_role.get("rules") or []):
            api_groups = cast("list[str]", hook_rule.get("apiGroups") or [])
            resources = cast("list[str]", hook_rule.get("resources") or [])
            required_verbs = _verbs(hook_rule)
            for api_group in api_groups:
                for resource in resources:
                    destructive_rules = _rules_for(
                        destructive_role,
                        api_group=api_group,
                        resource=resource,
                    )
                    available_verbs = set().union(*(_verbs(rule) for rule in destructive_rules))
                    assert required_verbs.issubset(available_verbs), (
                        "Destructive runner cannot create the pre-upgrade hook "
                        "Role without RBAC escalation. Missing verbs "
                        f"{required_verbs - available_verbs!r} for "
                        f"{api_group or 'core'}/{resource}."
                    )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_can_grant_all_rendered_chart_roles_without_escalation() -> None:
    """Destructive runner must already hold permissions granted by rendered Roles.

    Kubernetes rejects Role create/update/patch when the acting identity would
    grant permissions it does not already hold. The destructive test pod runs
    ``helm upgrade`` in-cluster, so it must hold a superset of every chart Role
    Helm may patch during upgrade.
    """
    destructive_role = _render_role(DESTRUCTIVE_TEMPLATE)
    destructive_name = destructive_role["metadata"]["name"]
    rendered_roles = [
        role
        for role in _render_all_chart_docs()
        if role.get("kind") == "Role" and role.get("metadata", {}).get("name") != destructive_name
    ]
    assert rendered_roles, "Expected chart to render Roles besides the destructive runner"

    for rendered_role in rendered_roles:
        role_name = rendered_role.get("metadata", {}).get("name")
        for rendered_rule in cast("list[dict[str, Any]]", rendered_role.get("rules") or []):
            api_groups = cast("list[str]", rendered_rule.get("apiGroups") or [])
            resources = cast("list[str]", rendered_rule.get("resources") or [])
            required_verbs = _verbs(rendered_rule)
            for api_group in api_groups:
                for resource in resources:
                    destructive_rules = _rules_for(
                        destructive_role,
                        api_group=api_group,
                        resource=resource,
                    )
                    available_verbs = set().union(*(_verbs(rule) for rule in destructive_rules))
                    assert required_verbs.issubset(available_verbs), (
                        "Destructive runner cannot patch rendered Role "
                        f"{role_name!r} without RBAC escalation. Missing verbs "
                        f"{required_verbs - available_verbs!r} for "
                        f"{api_group or 'core'}/{resource}."
                    )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_can_manage_pre_upgrade_hook_resources() -> None:
    """Destructive runner must manage rendered pre-upgrade hook resources.

    Helm deletes/recreates and watches hook resources during upgrade. If the
    runner cannot manage every rendered pre-upgrade hook resource, the failure
    surfaces as an opaque Helm upgrade RBAC error.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    docs = _render_all_chart_docs()
    pre_upgrade_hooks: list[dict[str, Any]] = []
    for doc in docs:
        metadata_any = doc.get("metadata") or {}
        if not isinstance(metadata_any, dict):
            continue
        metadata: dict[str, Any] = cast("dict[str, Any]", metadata_any)
        annotations_any = metadata.get("annotations") or {}
        if not isinstance(annotations_any, dict):
            continue
        annotations: dict[str, Any] = cast("dict[str, Any]", annotations_any)
        if "pre-upgrade" in str(annotations.get("helm.sh/hook", "")):
            pre_upgrade_hooks.append(doc)
    assert pre_upgrade_hooks, "Expected at least one rendered pre-upgrade hook resource"

    for hook in pre_upgrade_hooks:
        kind = hook.get("kind")
        if kind not in KIND_TO_RBAC_RESOURCE:
            continue
        api_group, resource = KIND_TO_RBAC_RESOURCE[kind]
        name = hook.get("metadata", {}).get("name")
        assert isinstance(name, str) and name, f"Hook {kind} must have a metadata.name"
        rules = _rules_for(role, api_group=api_group, resource=resource)
        assert any({"get", "list", "watch"}.issubset(_verbs(rule)) for rule in rules), (
            f"Destructive runner must watch pre-upgrade hook {kind} {name!r}."
        )
        assert any("create" in _verbs(rule) for rule in rules), (
            f"Destructive runner must create pre-upgrade hook {kind} {name!r}; "
            "Kubernetes RBAC cannot scope create by resourceNames."
        )
        assert _has_delete_permission_for_name(rules, name), (
            f"Destructive runner must delete pre-upgrade hook {kind} {name!r}."
        )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_can_manage_rendered_chart_resource_kinds_for_helm_upgrade() -> None:
    """Destructive runner must act as a namespaced Helm chart manager.

    The destructive suite runs `helm upgrade charts/floe-platform` from inside
    the test pod. Helm may create, patch, update, or delete any namespaced kind
    rendered by the chart during upgrade or rollback, so this contract derives
    the required resource kinds from the rendered manifest instead of encoding
    one-off permissions after each RBAC 403.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    docs = _render_all_chart_docs()

    rendered_resources = {
        KIND_TO_RBAC_RESOURCE[kind]
        for doc in docs
        if (kind := doc.get("kind")) in KIND_TO_RBAC_RESOURCE
    }
    assert rendered_resources, "Expected rendered chart resources with RBAC mappings"

    for api_group, resource in sorted(rendered_resources):
        rules = _rules_for(role, api_group=api_group, resource=resource)
        available_verbs = set().union(*(_verbs(rule) for rule in rules))
        assert HELM_CHART_MANAGER_VERBS.issubset(available_verbs), (
            "Destructive runner is not a complete Helm chart manager for "
            f"{api_group or 'core'}/{resource}. Missing verbs: "
            f"{HELM_CHART_MANAGER_VERBS - available_verbs!r}."
        )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_can_suspend_flux_helmrelease_for_direct_helm_upgrade() -> None:
    """Destructive runner must suspend Flux before direct Helm operations.

    The destructive Helm upgrade test runs inside the cluster and may not have
    the ``flux`` CLI installed. It uses ``kubectl patch helmrelease`` as the
    portable path, so RBAC must allow patch/update on namespace-local
    HelmRelease resources.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    rules = _rules_for(
        role,
        api_group="helm.toolkit.fluxcd.io",
        resource="helmreleases",
    )
    available_verbs = set().union(*(_verbs(rule) for rule in rules))

    assert {"get", "list", "watch", "patch", "update"}.issubset(available_verbs), (
        "Destructive runner must be able to inspect and suspend Flux "
        "HelmReleases before direct Helm upgrade tests. Missing verbs: "
        f"{ {'get', 'list', 'watch', 'patch', 'update'} - available_verbs!r}."
    )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_can_read_replicasets_for_helm_legacy_wait() -> None:
    """Destructive runner must read ReplicaSets for Helm legacy readiness.

    ReplicaSets are controller-created, not rendered by the chart, so the
    rendered-manifest chart-manager contract cannot derive this permission.
    Helm's legacy waiter lists ReplicaSets while evaluating Deployment rollout
    readiness during ``helm upgrade --wait=legacy``.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    rules = _rules_for(role, api_group="apps", resource="replicasets")
    available_verbs = set().union(*(_verbs(rule) for rule in rules))

    assert {"get", "list", "watch"}.issubset(available_verbs), (
        "Destructive runner must get/list/watch apps/replicasets so Helm "
        "legacy wait can evaluate Deployment readiness. Missing verbs: "
        f"{ {'get', 'list', 'watch'} - available_verbs!r}."
    )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_has_limited_networkpolicy_patch_access_for_helm_rollback() -> None:
    """Destructive runner needs NetworkPolicy chart-manager access.

    The chart renders NetworkPolicies in test values. When a Helm upgrade
    fails and `--rollback-on-failure` runs, Helm may create, patch, update, or
    delete rendered resources to restore release state.
    """
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    rules = _rules_for(
        role,
        api_group="networking.k8s.io",
        resource="networkpolicies",
    )

    assert any(HELM_CHART_MANAGER_VERBS.issubset(_verbs(rule)) for rule in rules), (
        "Destructive runner must have chart-manager access to NetworkPolicies "
        "so Helm upgrade/rollback can restore chart-managed policies."
    )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_has_limited_pdb_patch_access_for_helm_rollback() -> None:
    """Destructive runner needs PodDisruptionBudget chart-manager access."""
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    rules = _rules_for(
        role,
        api_group="policy",
        resource="poddisruptionbudgets",
    )

    assert any(HELM_CHART_MANAGER_VERBS.issubset(_verbs(rule)) for rule in rules), (
        "Destructive runner must have chart-manager access to "
        "PodDisruptionBudgets so Helm upgrade/rollback can restore chart-managed PDBs."
    )


@pytest.mark.requirement("security-hardening-AC-9")
def test_destructive_runner_has_limited_service_patch_access_for_helm_rollback() -> None:
    """Destructive runner needs Service chart-manager access."""
    role = _render_role(DESTRUCTIVE_TEMPLATE)
    rules = _rules_for(role, api_group="", resource="services")

    assert any(HELM_CHART_MANAGER_VERBS.issubset(_verbs(rule)) for rule in rules), (
        "Destructive runner must have chart-manager access to Services so "
        "Helm upgrade/rollback can restore chart-managed Services."
    )
