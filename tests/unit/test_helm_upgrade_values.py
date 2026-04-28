"""Structural validation: test_helm_upgrade_succeeds uses clean values, not --reuse-values.

Tests that the E2E test ``test_helm_upgrade_succeeds`` in
``tests/e2e/test_helm_upgrade_e2e.py`` provides explicit values via ``-f``
pointing to ``values-test.yaml`` instead of using ``--reuse-values``, which
carries forward stale properties from the running release that are rejected
by Dagster 1.12.x schema.

AC-3: The upgrade test MUST:
  - NOT use ``--reuse-values`` (not even in comments)
  - Provide explicit values via ``-f`` pointing to ``values-test.yaml``
  - Preserve the ``--set global.annotations...`` annotation override
  - ``grep -n "reuse-values" tests/e2e/test_helm_upgrade_e2e.py`` returns no matches

These are structural (source-parsing) tests per P28/P29. They inspect the
Python source of the E2E test file. They do NOT import or execute the E2E test.

Requirements:
    AC-3: Helm upgrade test uses clean values instead of stale release values
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

import pytest

from testing.fixtures.source_parsing import get_function_source, strip_comments_and_docstrings

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_TEST_FILE = REPO_ROOT / "tests" / "e2e" / "test_helm_upgrade_e2e.py"


@pytest.fixture(scope="module")
def upgrade_file_raw() -> str:
    """Complete raw source of the E2E test file including comments and docstrings.

    Used for checks that must scan the entire file (e.g., no occurrence of
    ``--reuse-values`` anywhere, per AC-3's grep requirement).

    Returns:
        The complete raw source text of the file.
    """
    assert E2E_TEST_FILE.exists(), (
        f"E2E test file not found at {E2E_TEST_FILE}. "
        "Cannot validate helm upgrade values without the source."
    )
    return E2E_TEST_FILE.read_text()


@pytest.fixture(scope="module")
def upgrade_test_source() -> str:
    """Source text of test_helm_upgrade_succeeds from the E2E file.

    Returns:
        The complete source text of the function.
    """
    assert E2E_TEST_FILE.exists(), (
        f"E2E test file not found at {E2E_TEST_FILE}. "
        "Cannot validate helm upgrade values without the source."
    )
    return get_function_source(E2E_TEST_FILE, "test_helm_upgrade_succeeds")


@pytest.fixture(scope="module")
def upgrade_test_code(upgrade_test_source: str) -> str:
    """Executable code only (no comments/docstrings) from test_helm_upgrade_succeeds.

    This fixture strips comments and docstrings so that structural tests
    validate actual code, not comments a lazy implementer might add (P29).

    Returns:
        Source text with comments and docstrings removed.
    """
    return strip_comments_and_docstrings(upgrade_test_source)


# ---------------------------------------------------------------------------
# Test class 1: --reuse-values must NOT appear anywhere in the file
# ---------------------------------------------------------------------------


class TestNoReuseValuesAnywhere:
    """Verify --reuse-values does not appear anywhere in the E2E test file.

    AC-3 requires: ``grep -n "reuse-values" tests/e2e/test_helm_upgrade_e2e.py``
    returns no matches. This means the string must not appear even in comments
    or docstrings. The fix removes it entirely.
    """

    @pytest.mark.requirement("AC-3")
    def test_reuse_values_not_in_file(self, upgrade_file_raw: str) -> None:
        """The string ``reuse-values`` must not appear anywhere in the file.

        AC-3 explicitly requires ``grep -n "reuse-values"`` to return no
        matches. This checks the raw file content (including comments and
        docstrings) because ``grep`` does not distinguish between code and
        comments.
        """
        matches = re.findall(r"reuse-values", upgrade_file_raw)
        assert len(matches) == 0, (
            f"Found {len(matches)} occurrence(s) of 'reuse-values' in "
            f"{E2E_TEST_FILE.relative_to(REPO_ROOT)}. "
            'AC-3 requires \'grep -n "reuse-values" '
            "tests/e2e/test_helm_upgrade_e2e.py' to return no matches. "
            "The --reuse-values flag must be removed entirely (not commented out)."
        )

    @pytest.mark.requirement("AC-3")
    def test_reuse_values_not_in_upgrade_command(self, upgrade_test_code: str) -> None:
        """The upgrade command args must not contain ``--reuse-values``.

        Even if somehow the file-level check missed it (e.g., the string is
        split across lines), verify the executable code of the upgrade test
        function specifically does not contain this flag.
        """
        assert "reuse-values" not in upgrade_test_code, (
            "test_helm_upgrade_succeeds executable code still contains "
            "'reuse-values'. The --reuse-values flag carries forward stale "
            "properties from the running release that are rejected by "
            "Dagster 1.12.x schema. It must be replaced with explicit "
            "values via -f."
        )


# ---------------------------------------------------------------------------
# Test class 2: Explicit values via -f pointing to values-test.yaml
# ---------------------------------------------------------------------------


class TestExplicitValuesFile:
    """Verify the upgrade command uses ``-f`` with ``values-test.yaml``.

    The fix replaces ``--reuse-values`` with ``-f`` pointing to
    ``charts/floe-platform/values-test.yaml`` to provide clean, known values.
    """

    @pytest.mark.requirement("AC-3")
    def test_values_test_yaml_in_executable_code(self, upgrade_test_code: str) -> None:
        """Executable code must reference ``values-test.yaml``.

        The upgrade command must point to a known values file instead of
        reusing stale release values. This checks executable code (not
        comments/docstrings) to prevent bypassing via a docstring mention
        (P29).
        """
        has_values_test = bool(re.search(r"values-test\.yaml", upgrade_test_code))
        assert has_values_test, (
            "test_helm_upgrade_succeeds does not reference 'values-test.yaml' "
            "in executable code (comments and docstrings excluded). "
            "The upgrade command must provide explicit values via "
            "'-f charts/floe-platform/values-test.yaml' instead of "
            "--reuse-values."
        )

    @pytest.mark.requirement("AC-3")
    def test_f_flag_in_executable_code(self, upgrade_test_code: str) -> None:
        """Executable code must contain the ``-f`` flag for Helm values file.

        The ``-f`` (or ``--values``) flag tells Helm to use a specific values
        file. Without it, the values-test.yaml reference would be meaningless.
        """
        # Accept both -f and --values (Helm accepts both forms)
        has_f_flag = bool(re.search(r'["\']-f["\']|["\']--values["\']', upgrade_test_code))
        assert has_f_flag, (
            "test_helm_upgrade_succeeds does not contain '-f' or '--values' "
            "flag in executable code. The upgrade command must use "
            "'-f <values-file>' to provide explicit values. Without the "
            "-f flag, values-test.yaml is not actually used by Helm."
        )

    @pytest.mark.requirement("AC-3")
    def test_f_flag_and_values_file_coexist(self, upgrade_test_code: str) -> None:
        """Both ``-f`` and ``values-test.yaml`` must appear together in the code.

        A lazy implementation might add ``-f`` without specifying the values
        file, or reference ``values-test.yaml`` without ``-f``. Both must be
        present in executable code.
        """
        has_f_flag = bool(re.search(r'["\']-f["\']|["\']--values["\']', upgrade_test_code))
        has_values_file = bool(re.search(r"values-test\.yaml", upgrade_test_code))

        assert has_f_flag and has_values_file, (
            "test_helm_upgrade_succeeds must have BOTH '-f' flag AND "
            "'values-test.yaml' reference in executable code. "
            f"Found -f/--values flag: {has_f_flag}, "
            f"found values-test.yaml: {has_values_file}. "
            "Both are required for the Helm upgrade to use clean values."
        )

    @pytest.mark.requirement("AC-3")
    def test_values_file_path_includes_chart_directory(self, upgrade_test_code: str) -> None:
        """The values file path must include the chart directory prefix.

        The correct path is ``charts/floe-platform/values-test.yaml``. Just
        specifying ``values-test.yaml`` without the chart path would fail
        because Helm resolves relative to CWD, not the chart directory.
        """
        # Accept various path forms:
        #   "charts/floe-platform/values-test.yaml"
        #   Path("charts") / "floe-platform" / "values-test.yaml"
        has_full_path = bool(
            re.search(
                r"charts/floe-platform/values-test\.yaml|"
                r"charts.*floe-platform.*values-test\.yaml",
                upgrade_test_code,
            )
        )
        assert has_full_path, (
            "test_helm_upgrade_succeeds references 'values-test.yaml' but "
            "does not include the chart directory path "
            "'charts/floe-platform/values-test.yaml' in executable code. "
            "The full path is required for Helm to find the values file."
        )


# ---------------------------------------------------------------------------
# Test class 3: Annotation override preserved
# ---------------------------------------------------------------------------


class TestAnnotationOverridePreserved:
    """Verify the ``--set global.annotations...`` override is still present.

    The fix must only replace ``--reuse-values`` with ``-f values-test.yaml``.
    The annotation override (``--set global.annotations.e2e-test-revision=upgrade-test``)
    must be preserved to trigger a meaningful change for the upgrade.
    """

    @pytest.mark.requirement("AC-3")
    def test_set_flag_present(self, upgrade_test_code: str) -> None:
        """Executable code must contain ``--set`` flag.

        The ``--set`` flag is used to override the annotation value,
        creating a minimal change for the upgrade to detect.
        """
        has_set_flag = bool(re.search(r'["\']--set["\']', upgrade_test_code))
        assert has_set_flag, (
            "test_helm_upgrade_succeeds does not contain '--set' flag in "
            "executable code. The annotation override "
            "'--set global.annotations.e2e-test-revision=upgrade-test' "
            "must be preserved to trigger a meaningful upgrade change."
        )

    @pytest.mark.requirement("AC-3")
    def test_global_annotations_override_present(self, upgrade_test_code: str) -> None:
        """Executable code must contain ``global.annotations`` override.

        The specific annotation override creates a new revision during
        the Helm upgrade. Without it, the upgrade might be a no-op.
        """
        has_annotations = bool(re.search(r"global\.annotations", upgrade_test_code))
        assert has_annotations, (
            "test_helm_upgrade_succeeds does not contain 'global.annotations' "
            "in executable code. The annotation override must be preserved "
            "to ensure the Helm upgrade creates a new revision."
        )

    @pytest.mark.requirement("AC-3")
    def test_annotation_key_and_value_present(self, upgrade_test_code: str) -> None:
        """The annotation must specify both key and value for a meaningful upgrade.

        A lazy implementation might keep ``--set`` but drop the annotation
        value, which would make the upgrade a no-op. The full annotation
        string ``global.annotations.e2e-test-revision=upgrade-test`` must
        be present.
        """
        has_full_annotation = bool(
            re.search(
                r"global\.annotations\.\S+=\S+",
                upgrade_test_code,
            )
        )
        assert has_full_annotation, (
            "test_helm_upgrade_succeeds has '--set' and 'global.annotations' "
            "but the annotation override is incomplete. Expected a pattern like "
            "'global.annotations.<key>=<value>' with both key and value specified."
        )


# ---------------------------------------------------------------------------
# Test class 4: Upgrade command structure validation
# ---------------------------------------------------------------------------


class TestUpgradeCommandStructure:
    """Verify the overall structure of the upgrade command is correct.

    The upgrade command must include: upgrade, release name, chart path,
    namespace, -f <values-file>, --set <annotation>, --wait, --timeout.
    """

    @pytest.mark.requirement("AC-3")
    def test_upgrade_command_has_wait_flag(self, upgrade_test_code: str) -> None:
        """The upgrade command must include a Helm wait flag for reliable upgrades.

        The wait flag ensures Helm waits for resources to be ready before
        returning. Removing this would make the upgrade test unreliable.
        """
        has_wait = bool(re.search(r'["\']--wait(?:=legacy)?["\']', upgrade_test_code))
        assert has_wait, (
            "test_helm_upgrade_succeeds does not contain a Helm wait flag. "
            "The upgrade command must wait for resources to be ready."
        )

    @pytest.mark.requirement("AC-2.9")
    def test_upgrade_command_uses_legacy_wait_strategy_for_helm4(
        self,
        upgrade_test_code: str,
    ) -> None:
        """The destructive upgrade must avoid Helm 4 watcher false negatives.

        Helm 4 defaults ``--rollback-on-failure`` to the watcher wait strategy.
        In the in-cluster destructive lane that watcher reported a healthy
        ``cube-api`` deployment as ``Unknown`` and left the release in
        rollback. The upgrade test should use Helm's legacy readiness waiter
        explicitly.
        """
        assert '"--wait=legacy"' in upgrade_test_code or "'--wait=legacy'" in upgrade_test_code, (
            "test_helm_upgrade_succeeds must use '--wait=legacy'. Helm 4 "
            "--rollback-on-failure defaults to watcher wait, which produced "
            "false Deployment Unknown readiness during the destructive lane."
        )
        assert '"--wait"' not in upgrade_test_code and "'--wait'" not in upgrade_test_code, (
            "test_helm_upgrade_succeeds must not use bare '--wait' because "
            "Helm 4 rollback-on-failure defaults bare wait to watcher."
        )

    @pytest.mark.requirement("AC-3")
    def test_upgrade_command_has_timeout(self, upgrade_test_code: str) -> None:
        """The upgrade command must include ``--timeout`` to avoid hanging.

        Without a timeout, the upgrade could hang indefinitely if resources
        never become ready.
        """
        has_timeout = bool(re.search(r'["\']--timeout["\']', upgrade_test_code))
        assert has_timeout, (
            "test_helm_upgrade_succeeds does not contain '--timeout' flag. "
            "The upgrade command must have a timeout to avoid hanging."
        )

    @pytest.mark.requirement("AC-3")
    def test_no_install_flag_in_upgrade(self, upgrade_test_code: str) -> None:
        """The upgrade command must NOT use ``--install`` (upgrade-only).

        The test validates the upgrade path specifically. Using ``--install``
        would mask failures by creating a fresh install instead of upgrading.
        """
        has_install = bool(re.search(r'["\']--install["\']', upgrade_test_code))
        assert not has_install, (
            "test_helm_upgrade_succeeds contains '--install' flag. "
            "The upgrade test must validate the pure upgrade path, not "
            "fall back to install if the release doesn't exist."
        )


class TestUpgradeTimeoutEnvelope:
    """Validate pytest does not interrupt Helm before Helm can settle state."""

    @pytest.mark.requirement("AC-2.9")
    def test_pytest_timeout_exceeds_helm_upgrade_and_recovery_budget(
        self,
        upgrade_file_raw: str,
    ) -> None:
        """The destructive upgrade test needs an outer timeout above Helm budgets.

        ``test_helm_upgrade_succeeds`` runs ``helm upgrade --timeout 8m`` and
        may run a 5-minute recovery rollback in ``finally``. A global 300s
        pytest-timeout interrupts Helm mid-transaction and leaves the release
        in ``pending-rollback``.
        """
        tree = ast.parse(upgrade_file_raw)
        upgrade_test = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "test_helm_upgrade_succeeds"
        )

        timeout_seconds: int | None = None
        for decorator in upgrade_test.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if (
                isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "timeout"
                and isinstance(decorator.func.value, ast.Attribute)
                and decorator.func.value.attr == "mark"
            ):
                first_arg = decorator.args[0] if decorator.args else None
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, int):
                    timeout_seconds = first_arg.value

        assert timeout_seconds is not None, (
            "test_helm_upgrade_succeeds must declare @pytest.mark.timeout(...) "
            "so the global 300s timeout cannot interrupt Helm mid-upgrade."
        )
        assert timeout_seconds >= 1260, (
            "test_helm_upgrade_succeeds pytest timeout must exceed the 8m Helm "
            "upgrade budget plus the 5m recovery rollback budget and scheduling "
            f"headroom; got {timeout_seconds}s."
        )


class TestRuntimeImageOverrides:
    """Validate upgrade replays only runtime image values from the current release."""

    @pytest.mark.requirement("AC-2.9")
    def test_runtime_dagster_image_overrides_are_derived_from_helm_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The upgrade must preserve the manifest-selected demo image tag.

        DevPod/Kind loads the built demo image by its generated tag and uses
        ``imagePullPolicy: Never``. If the upgrade falls back to the test
        values file's ``latest`` tag, pods cannot start and Helm waits until
        timeout.
        """
        from tests.e2e import test_helm_upgrade_e2e as upgrade_module

        helm_values = {
            "dagster": {
                "dagsterWebserver": {
                    "image": {
                        "repository": "registry.example/floe-dagster-demo",
                        "tag": "abc123-dirty",
                    },
                },
                "dagsterDaemon": {
                    "image": {
                        "repository": "registry.example/floe-dagster-demo",
                        "tag": "abc123-dirty",
                    },
                },
                "runLauncher": {
                    "config": {
                        "k8sRunLauncher": {
                            "image": {
                                "repository": "registry.example/floe-dagster-demo",
                                "tag": "abc123-dirty",
                            },
                        },
                    },
                },
            },
        }
        calls: list[list[str]] = []

        def fake_run_helm(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(helm_values),
                stderr="",
            )

        monkeypatch.setattr(upgrade_module, "run_helm", fake_run_helm)

        overrides = upgrade_module._current_dagster_image_overrides(
            release="floe-platform",
            namespace="floe-test",
        )

        assert calls == [
            ["get", "values", "floe-platform", "-n", "floe-test", "--all", "-o", "json"],
        ]
        assert overrides == [
            "--set-string",
            "dagster.dagsterWebserver.image.repository=registry.example/floe-dagster-demo",
            "--set-string",
            "dagster.dagsterWebserver.image.tag=abc123-dirty",
            "--set-string",
            "dagster.dagsterDaemon.image.repository=registry.example/floe-dagster-demo",
            "--set-string",
            "dagster.dagsterDaemon.image.tag=abc123-dirty",
            "--set-string",
            "dagster.runLauncher.config.k8sRunLauncher.image.repository=registry.example/floe-dagster-demo",
            "--set-string",
            "dagster.runLauncher.config.k8sRunLauncher.image.tag=abc123-dirty",
        ]
