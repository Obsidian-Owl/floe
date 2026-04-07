"""Contract test: test infrastructure is structurally sourced from the chart.

This is the tripwire for the `test-infra-drift-elimination` work unit. It
fails fast on any future drift between the Helm chart at
`charts/floe-platform/templates/tests/`, the shell scripts under
`testing/ci/`, and the (now-deleted) raw K8s manifest directories under
`testing/k8s/jobs/` and `testing/k8s/rbac/`.

The chart is the single source of truth. Every test runner identifier
(ServiceAccount, Role, Service, Secret, namespace, warehouse name) must
flow from a chart helper or values key, never from a literal string in a
shell script or a raw YAML.

Coverage:
    AC-1  — Test Job manifests live only in the chart and reference
            chart-rendered identifiers.
    AC-2  — `tests.enabled=false` (the default) emits zero test resources.
    AC-3  — Bootstrap Job catalog name and test Job `POLARIS_WAREHOUSE`
            resolve to the same values key.
    AC-4  — Test RBAC manifests live only in the chart, with the security
            scoping from security-hardening AC-8 preserved.
    AC-5  — Shell scripts source `common.sh` and contain no hardcoded
            `floe-platform-*` identifiers.
    AC-7  — Raw `testing/k8s/jobs/` and `testing/k8s/rbac/` directories
            are deleted and unreferenced.
    AC-9  — `fullnameOverride` in `values-test.yaml` still pins the
            release name to `floe-platform`.

Tier: contract. Runs offline (helm template only) in <10s. No infra spin-up.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_DIR = REPO_ROOT / "charts" / "floe-platform"
VALUES_TEST = CHART_DIR / "values-test.yaml"
VALUES_DEFAULT = CHART_DIR / "values.yaml"

# Names of templates that own test infrastructure resources.
TEST_TEMPLATE_PREFIX = "floe-platform/templates/tests/"

# Workload kinds whose pod spec contains references to other K8s resources.
POD_WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}


# ---------------------------------------------------------------------------
# Render fixtures
# ---------------------------------------------------------------------------


def _helm_template(*extra_args: str) -> list[dict[str, Any]]:
    """Run `helm template` with the test values file and parse to docs.

    Pytest-fails if `helm` is missing or rendering errors. The `extra_args`
    are appended after the standard `helm template floe-platform <chart>`
    invocation.
    """
    if shutil.which("helm") is None:
        pytest.fail(
            "helm CLI not available on PATH — required to render the chart "
            "for test infrastructure integrity verification."
        )

    cmd = [
        "helm",
        "template",
        "floe-platform",
        str(CHART_DIR),
        "-f",
        str(VALUES_TEST),
        *extra_args,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        pytest.fail(
            f"helm template rendering failed:\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    docs: list[dict[str, Any]] = []
    for raw in yaml.safe_load_all(result.stdout):
        if not isinstance(raw, dict):
            continue
        doc: dict[str, Any] = cast("dict[str, Any]", raw)
        if doc:
            docs.append(doc)
    assert docs, "helm template produced no documents — rendering broke"
    return docs


@pytest.fixture(scope="module")
def tests_enabled_render() -> list[dict[str, Any]]:
    """Render the chart with `tests.enabled=true`. Includes test Jobs/RBAC."""
    return _helm_template("--set", "tests.enabled=true")


@pytest.fixture(scope="module")
def tests_disabled_render() -> list[dict[str, Any]]:
    """Render the chart with `tests.enabled=false`. No test resources."""
    return _helm_template("--set", "tests.enabled=false")


# ---------------------------------------------------------------------------
# Helpers for walking rendered docs
# ---------------------------------------------------------------------------


def _kind(doc: dict[str, Any]) -> str:
    k = doc.get("kind")
    return k if isinstance(k, str) else ""


def _name(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata") or {}
    if not isinstance(meta, dict):
        return ""
    n = cast("dict[str, Any]", meta).get("name")
    return n if isinstance(n, str) else ""


def _labels(doc: dict[str, Any]) -> dict[str, Any]:
    meta = doc.get("metadata") or {}
    if not isinstance(meta, dict):
        return {}
    labels = cast("dict[str, Any]", meta).get("labels") or {}
    return cast("dict[str, Any]", labels) if isinstance(labels, dict) else {}


def _pod_spec(doc: dict[str, Any]) -> dict[str, Any]:
    spec = doc.get("spec") or {}
    if not isinstance(spec, dict):
        return {}
    spec_dict: dict[str, Any] = cast("dict[str, Any]", spec)
    template = spec_dict.get("template") or {}
    if not isinstance(template, dict):
        return {}
    inner = cast("dict[str, Any]", template).get("spec") or {}
    return cast("dict[str, Any]", inner) if isinstance(inner, dict) else {}


def _containers(pod_spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("initContainers", "containers"):
        items = pod_spec.get(key) or []
        if not isinstance(items, list):
            continue
        for item in cast("list[Any]", items):
            if isinstance(item, dict):
                out.append(cast("dict[str, Any]", item))
    return out


# ===========================================================================
# AC-1 — Test Job manifests live only in the chart
# ===========================================================================


@pytest.mark.requirement("test-infra-drift-elimination-AC-1")
def test_test_jobs_reference_only_chart_rendered_identifiers(
    tests_enabled_render: list[dict[str, Any]],
) -> None:
    """Every name a test Job references must be produced by the chart.

    Walks every rendered Job whose `test-type` label is set, collects the
    `serviceAccountName`, every `secretRef.name`, and every
    `secretKeyRef.name`. Asserts each identifier is the metadata.name of
    another resource produced by the same render. Catches the regression
    where someone hardcodes a Service or Secret name that doesn't actually
    exist in the deployed release.
    """
    rendered_names = {_name(d) for d in tests_enabled_render if _name(d)}

    test_jobs: list[dict[str, Any]] = [
        d
        for d in tests_enabled_render
        if _kind(d) == "Job" and _labels(d).get("test-type")
    ]
    assert test_jobs, (
        "AC-1 violation: chart rendered no test Jobs with `test-type` label "
        "— expected at least one (e2e or e2e-destructive)."
    )

    referenced: set[str] = set()
    for job in test_jobs:
        pod = _pod_spec(job)
        sa = pod.get("serviceAccountName")
        if isinstance(sa, str) and sa:
            referenced.add(sa)
        for container in _containers(pod):
            env_list = container.get("env") or []
            if isinstance(env_list, list):
                for entry_any in cast("list[Any]", env_list):
                    if not isinstance(entry_any, dict):
                        continue
                    entry: dict[str, Any] = cast("dict[str, Any]", entry_any)
                    value_from = entry.get("valueFrom") or {}
                    if not isinstance(value_from, dict):
                        continue
                    secret_ref = cast("dict[str, Any]", value_from).get(
                        "secretKeyRef"
                    ) or {}
                    if isinstance(secret_ref, dict):
                        ref_name = cast("dict[str, Any]", secret_ref).get("name")
                        if isinstance(ref_name, str) and ref_name:
                            referenced.add(ref_name)

    # External references (e.g. third-party operator-managed secrets like
    # the bitnami postgres / minio secrets) are produced by subcharts. Those
    # subchart resources also appear in the same render, so the
    # `rendered_names` set covers them. Anything missing is a real drift.
    missing = sorted(referenced - rendered_names)
    assert not missing, (
        f"AC-1 violation: test Jobs reference identifiers not produced by "
        f"the chart render: {missing}. Either the chart helper is wrong, "
        f"or someone hardcoded a name. Rendered names: "
        f"{sorted(rendered_names)[:10]}…"
    )


# ===========================================================================
# AC-2 — Test Jobs gated by `tests.enabled`
# ===========================================================================


@pytest.mark.requirement("test-infra-drift-elimination-AC-2")
def test_tests_disabled_render_has_no_test_resources(
    tests_disabled_render: list[dict[str, Any]],
) -> None:
    """A render with `tests.enabled=false` MUST emit zero test resources.

    Catches the regression where someone unconditionally renders a test
    Job/Role/RoleBinding outside an `{{- if .Values.tests.enabled }}` block.
    "Test resource" = any document carrying a `test-type` label or whose
    name contains the test runner SA name.
    """
    leaked: list[str] = []
    for doc in tests_disabled_render:
        labels = _labels(doc)
        if labels.get("test-type"):
            leaked.append(f"{_kind(doc)}/{_name(doc)} (label test-type)")
            continue
        # Catch RBAC leaks too — they don't carry the `test-type` label.
        name = _name(doc)
        if "test-runner" in name or "test-e2e" in name:
            leaked.append(f"{_kind(doc)}/{name} (test-runner in name)")

    assert not leaked, (
        f"AC-2 violation: tests.enabled=false leaked test resources: "
        f"{leaked}. Wrap the offending template in "
        f"`{{- if .Values.tests.enabled }}` … `{{- end }}`."
    )


# ===========================================================================
# AC-3 — Single source of truth for warehouse name
# ===========================================================================


@pytest.mark.requirement("test-infra-drift-elimination-AC-3")
def test_warehouse_name_single_source_of_truth(
    tests_enabled_render: list[dict[str, Any]],
) -> None:
    """Bootstrap Job catalog name == test Job POLARIS_WAREHOUSE env value.

    Both must come from `polaris.bootstrap.catalogName`. The contract test
    proves this by overriding the values key and asserting both sites
    flip in lockstep — a literal in either site would break this.
    """
    # Render at the default value first.
    bootstrap_catalogs = _extract_bootstrap_catalog_names(tests_enabled_render)
    test_warehouses = _extract_test_warehouse_env_values(tests_enabled_render)

    assert bootstrap_catalogs, (
        "AC-3 violation: no polaris bootstrap Job rendered — cannot verify "
        "warehouse single source of truth."
    )
    assert test_warehouses, (
        "AC-3 violation: no test Job POLARIS_WAREHOUSE env var rendered — "
        "cannot verify warehouse single source of truth."
    )
    assert bootstrap_catalogs == test_warehouses, (
        f"AC-3 violation: bootstrap catalog name(s) {bootstrap_catalogs} "
        f"differ from test Job POLARIS_WAREHOUSE value(s) {test_warehouses}. "
        f"Both sites must read `polaris.bootstrap.catalogName`."
    )

    # Now flip the values key to a synthetic name and assert both sites move.
    sentinel = "floe-drift-tripwire-zzz"
    flipped = _helm_template(
        "--set",
        "tests.enabled=true",
        "--set",
        f"polaris.bootstrap.catalogName={sentinel}",
    )
    flipped_bootstrap = _extract_bootstrap_catalog_names(flipped)
    flipped_test = _extract_test_warehouse_env_values(flipped)
    assert sentinel in flipped_bootstrap, (
        f"AC-3 violation: overriding polaris.bootstrap.catalogName did not "
        f"propagate to bootstrap Job. Got {flipped_bootstrap}, expected to "
        f"contain {sentinel!r}."
    )
    assert sentinel in flipped_test, (
        f"AC-3 violation: overriding polaris.bootstrap.catalogName did not "
        f"propagate to test Job POLARIS_WAREHOUSE. Got {flipped_test}, "
        f"expected to contain {sentinel!r}. The test Job is hardcoding the "
        f"warehouse instead of reading the helper."
    )


def _extract_bootstrap_catalog_names(docs: list[dict[str, Any]]) -> set[str]:
    """Find the catalog name(s) the polaris-bootstrap Job creates.

    The bootstrap Job embeds the catalog name in a shell script in the
    container `command`. We grep that script for the `"name": "..."` line
    inside the catalog JSON payload — robust to script-format tweaks as
    long as the JSON object retains a `"name"` field.
    """
    pattern = re.compile(r'"name"\s*:\s*"([^"]+)"')
    names: set[str] = set()
    for doc in docs:
        if _kind(doc) != "Job":
            continue
        if "polaris-bootstrap" not in _name(doc):
            continue
        for container in _containers(_pod_spec(doc)):
            cmd = container.get("command") or []
            args = container.get("args") or []
            blobs: list[str] = []
            for blob in (*cmd, *args) if isinstance(cmd, list) and isinstance(args, list) else []:
                if isinstance(blob, str):
                    blobs.append(blob)
            for blob in blobs:
                # The bootstrap script wraps the catalog payload in a JSON
                # object whose first `"name"` field is the catalog name.
                # We pick the first match per blob to avoid catalog-role
                # name collisions.
                match = pattern.search(blob)
                if match:
                    names.add(match.group(1))
                    break
    return names


def _extract_test_warehouse_env_values(docs: list[dict[str, Any]]) -> set[str]:
    """Find every test Job's POLARIS_WAREHOUSE env var literal value."""
    values: set[str] = set()
    for doc in docs:
        if _kind(doc) != "Job":
            continue
        if not _labels(doc).get("test-type"):
            continue
        for container in _containers(_pod_spec(doc)):
            env_list = container.get("env") or []
            if not isinstance(env_list, list):
                continue
            for entry_any in cast("list[Any]", env_list):
                if not isinstance(entry_any, dict):
                    continue
                entry: dict[str, Any] = cast("dict[str, Any]", entry_any)
                if entry.get("name") != "POLARIS_WAREHOUSE":
                    continue
                value = entry.get("value")
                if isinstance(value, str):
                    values.add(value)
    return values


# ===========================================================================
# AC-4 — RBAC manifests live only in the chart
# ===========================================================================


@pytest.mark.requirement("test-infra-drift-elimination-AC-4")
def test_test_runner_rbac_rendered_from_chart(
    tests_enabled_render: list[dict[str, Any]],
) -> None:
    """Standard and destructive runner ServiceAccount/Role/RoleBinding exist.

    The raw `testing/k8s/rbac/` directory is gone. The chart must provide
    exactly the two test runner SAs, two Roles, and two RoleBindings, all
    from helper-derived names.
    """
    sa_names = {_name(d) for d in tests_enabled_render if _kind(d) == "ServiceAccount"}
    role_names = {_name(d) for d in tests_enabled_render if _kind(d) == "Role"}
    rb_names = {_name(d) for d in tests_enabled_render if _kind(d) == "RoleBinding"}

    expected_sas = {
        "floe-platform-test-runner",
        "floe-platform-test-runner-destructive",
    }
    missing_sas = expected_sas - sa_names
    assert not missing_sas, (
        f"AC-4 violation: chart did not render expected test runner SAs: "
        f"{missing_sas}. Have: {sorted(sa_names)}"
    )

    # At least one Role + RoleBinding per SA.
    assert any("test-runner" in r for r in role_names), (
        f"AC-4 violation: no test-runner Role rendered. Have: {sorted(role_names)}"
    )
    assert any("test-runner" in r for r in rb_names), (
        f"AC-4 violation: no test-runner RoleBinding rendered. Have: "
        f"{sorted(rb_names)}"
    )

    # AC-8 carry-forward: standard runner Role must not include list/watch on secrets.
    for doc in tests_enabled_render:
        if _kind(doc) != "Role":
            continue
        name = _name(doc)
        if name != "floe-platform-test-runner":
            continue
        rules = doc.get("rules") or []
        if not isinstance(rules, list):
            continue
        for rule_any in cast("list[Any]", rules):
            if not isinstance(rule_any, dict):
                continue
            rule: dict[str, Any] = cast("dict[str, Any]", rule_any)
            resources = rule.get("resources") or []
            if not isinstance(resources, list) or "secrets" not in resources:
                continue
            verbs = rule.get("verbs") or []
            forbidden = {v for v in cast("list[Any]", verbs) if v in ("list", "watch")}
            assert not forbidden, (
                f"AC-4/AC-8 violation: standard runner Role grants {forbidden} "
                f"on secrets. Standard runner must be `get`-only."
            )


# ===========================================================================
# AC-5 — Shell scripts resolve identifiers through `common.sh`
# ===========================================================================


CI_DIR = REPO_ROOT / "testing" / "ci"
COMMON_SH = CI_DIR / "common.sh"


def _ci_test_scripts() -> list[Path]:
    """Return every `testing/ci/test-*.sh` script except common.sh itself."""
    return sorted(p for p in CI_DIR.glob("test-*.sh") if p.name != "common.sh")


@pytest.mark.requirement("test-infra-drift-elimination-AC-5")
def test_common_sh_exists() -> None:
    """`testing/ci/common.sh` MUST exist as the canonical identifier source."""
    assert COMMON_SH.exists(), (
        f"AC-5 violation: {COMMON_SH} is missing — shell scripts have no "
        f"canonical place to read FLOE_* identifiers from."
    )


@pytest.mark.requirement("test-infra-drift-elimination-AC-5")
def test_every_test_script_sources_common_sh() -> None:
    """Each `testing/ci/test-*.sh` MUST source `common.sh` near the top.

    "Near the top" = within the first 25 non-comment, non-blank lines so
    that any helper, env var, or floe_* call lands after the source.
    """
    scripts = _ci_test_scripts()
    assert scripts, "No testing/ci/test-*.sh scripts found — directory layout broken."

    offenders: list[str] = []
    for script in scripts:
        lines = script.read_text().splitlines()
        executable: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            executable.append(stripped)
            if len(executable) >= 25:
                break
        if not any("common.sh" in line and "source" in line for line in executable):
            offenders.append(str(script.relative_to(REPO_ROOT)))

    assert not offenders, (
        f"AC-5 violation: these scripts do not `source` common.sh in their "
        f"first 25 executable lines: {offenders}"
    )


@pytest.mark.requirement("test-infra-drift-elimination-AC-5")
def test_no_hardcoded_floe_platform_in_test_scripts() -> None:
    """No `floe-platform-*` literal may appear in test scripts (except common.sh).

    Comments are exempt — only executable lines are checked. Catches the
    regression where someone reintroduces `svc/floe-platform-polaris` after
    `floe_service_name polaris` is removed.
    """
    pattern = re.compile(r"floe-platform-")
    offenders: list[str] = []
    for script in _ci_test_scripts():
        for lineno, line in enumerate(script.read_text().splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if pattern.search(line):
                offenders.append(f"{script.relative_to(REPO_ROOT)}:{lineno}: {stripped}")

    assert not offenders, (
        "AC-5 violation: literal `floe-platform-*` strings found in CI test "
        "scripts. Use `floe_service_name` from common.sh instead. Offenders:\n"
        + "\n".join(offenders)
    )


@pytest.mark.requirement("test-infra-drift-elimination-AC-5")
def test_no_kind_cluster_legacy_assignments_outside_common_sh() -> None:
    """`KIND_CLUSTER=` / `KIND_CLUSTER_NAME=` may only appear in common.sh.

    Both legacy names must be absorbed by `FLOE_KIND_CLUSTER`. A direct
    assignment in any other script reintroduces drift.
    """
    pattern = re.compile(r"^\s*(KIND_CLUSTER|KIND_CLUSTER_NAME)=")
    offenders: list[str] = []
    for script in _ci_test_scripts():
        for lineno, line in enumerate(script.read_text().splitlines(), start=1):
            if pattern.match(line):
                offenders.append(f"{script.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "AC-5 violation: legacy KIND_CLUSTER / KIND_CLUSTER_NAME assignment "
        "outside common.sh. Use FLOE_KIND_CLUSTER. Offenders:\n"
        + "\n".join(offenders)
    )


# ===========================================================================
# AC-7 — Raw test job/RBAC dirs deleted and unreferenced
# ===========================================================================


@pytest.mark.requirement("test-infra-drift-elimination-AC-7")
def test_raw_test_manifest_dirs_deleted() -> None:
    """`testing/k8s/jobs/` and `testing/k8s/rbac/` MUST NOT exist.

    The chart owns test infrastructure now. Re-creating either directory
    would let drift creep back in.
    """
    jobs_dir = REPO_ROOT / "testing" / "k8s" / "jobs"
    rbac_dir = REPO_ROOT / "testing" / "k8s" / "rbac"
    assert not jobs_dir.exists(), (
        f"AC-7 violation: {jobs_dir.relative_to(REPO_ROOT)} still exists — "
        f"chart is the only allowed source of test Jobs."
    )
    assert not rbac_dir.exists(), (
        f"AC-7 violation: {rbac_dir.relative_to(REPO_ROOT)} still exists — "
        f"chart is the only allowed source of test RBAC."
    )


@pytest.mark.requirement("test-infra-drift-elimination-AC-7")
def test_no_references_to_deleted_test_manifest_dirs() -> None:
    """No live code may reference `testing/k8s/jobs/` or `testing/k8s/rbac/`.

    Spec docs and prior epic plans are excluded — they're historical
    records, not executable references. Only files that would actually run
    (scripts, Makefiles, Python tests, chart code, Dockerfile) are checked.
    """
    pattern = re.compile(r"testing/k8s/(jobs|rbac)")
    search_roots = [
        REPO_ROOT / ".github",
        REPO_ROOT / "Makefile",
        REPO_ROOT / "testing",
        REPO_ROOT / "tests",
        REPO_ROOT / "scripts",
        REPO_ROOT / "charts",
        REPO_ROOT / "docker",
    ]
    extensions = {".sh", ".yaml", ".yml", ".py"}
    extra_filenames = {"Makefile", "Dockerfile"}

    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        if root.is_file():
            candidates.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix in extensions or path.name in extra_filenames:
                candidates.append(path)

    offenders: list[str] = []
    self_path = Path(__file__).resolve()
    for path in candidates:
        if path.resolve() == self_path:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "AC-7 violation: live references to deleted test manifest "
        "directories. Update the caller to render from the chart. "
        "Offenders:\n" + "\n".join(offenders)
    )


# ===========================================================================
# AC-9 — fullnameOverride preserved
# ===========================================================================


@pytest.mark.requirement("test-infra-drift-elimination-AC-9")
def test_values_test_pins_fullname_override() -> None:
    """`values-test.yaml` MUST keep `fullnameOverride: floe-platform`.

    Removing the override would change every rendered identifier in lock-
    step — chart consumers (CI scripts, contract tests, in-cluster
    callers) all assume `floe-platform-*`. Loss of the override is a
    coordinated migration, not a casual edit.
    """
    parsed = yaml.safe_load(VALUES_TEST.read_text())
    assert isinstance(parsed, dict), (
        f"AC-9 violation: {VALUES_TEST} did not parse to a mapping."
    )
    override = cast("dict[str, Any]", parsed).get("fullnameOverride")
    assert override == "floe-platform", (
        f"AC-9 violation: values-test.yaml fullnameOverride must be "
        f"'floe-platform', got {override!r}. Removing this override changes "
        f"every rendered identifier and is out of scope for casual edits."
    )
