"""Kubeconform schema validation tests for floe-platform Helm chart.

Tests that validate the `make helm-validate` target exists, is correctly
configured, and produces valid Kubernetes manifests when run.

The tests statically parse the Makefile to verify the helm-validate target
has the correct flags and values file references, then optionally run the
target end-to-end if kubeconform is installed.

Requirements:
    AC-26.1: make helm-validate renders templates and validates with kubeconform
    AC-26.2: Validation runs against both values.yaml and values-test.yaml
    AC-26.4: kubeconform validates against K8s 1.28.0
    AC-26.5: Subchart CRDs don't cause false failures
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HELM_VALIDATE_TARGET = "helm-validate"
EXPECTED_K8S_VERSION = "1.28.0"
VALUES_FILE = "values.yaml"
VALUES_TEST_FILE = "values-test.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fail(message: str) -> NoReturn:
    """Wrapper for pytest.fail with proper type annotation.

    Args:
        message: Failure message.

    Raises:
        pytest.fail: Always.
    """
    pytest.fail(message)
    raise AssertionError("Unreachable")  # For type checker


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (directory containing Makefile).

    Returns:
        Path to the project root.

    Raises:
        pytest.fail: If Makefile is not found.
    """
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "Makefile").exists():
            return parent
    _fail("Could not find project root (directory containing Makefile).")


def _read_makefile() -> str:
    """Read the project Makefile content.

    Returns:
        Full text of the Makefile.

    Raises:
        pytest.fail: If Makefile cannot be read.
    """
    root = _find_project_root()
    makefile_path = root / "Makefile"
    try:
        return makefile_path.read_text()
    except OSError as exc:
        _fail(f"Could not read Makefile at {makefile_path}: {exc}")


def _extract_target_recipe(makefile_text: str, target_name: str) -> str:
    """Extract the full recipe (all lines) for a Makefile target.

    Handles multi-line recipes joined by backslash continuations and
    tab-indented recipe lines.

    Args:
        makefile_text: Full Makefile text.
        target_name: Name of the target to extract.

    Returns:
        The complete recipe text for the target (all recipe lines joined).

    Raises:
        pytest.fail: If the target is not found.
    """
    # Match the target line and all subsequent tab-indented lines
    # Makefile targets: <name>: [prerequisites]\n\t<recipe lines>
    pattern = rf"^{re.escape(target_name)}\s*:.*$"
    lines = makefile_text.split("\n")

    target_line_idx: int | None = None
    for idx, line in enumerate(lines):
        if re.match(pattern, line):
            target_line_idx = idx
            break

    if target_line_idx is None:
        _fail(
            f"Makefile target '{target_name}' not found.\n"
            "The helm-validate target must be added to the Makefile."
        )

    # Collect recipe lines (tab-indented lines after the target)
    recipe_lines: list[str] = []
    for idx in range(target_line_idx + 1, len(lines)):
        line = lines[idx]
        # Recipe lines start with a tab character
        if line.startswith("\t"):
            recipe_lines.append(line.lstrip("\t"))
        elif line.strip() == "" or line.startswith("#"):
            # Blank lines or comments within recipes are OK
            continue
        else:
            # Hit the next target or non-recipe line
            break

    if not recipe_lines:
        _fail(
            f"Makefile target '{target_name}' has no recipe lines.\n"
            "Expected recipe lines with kubeconform invocation."
        )

    return "\n".join(recipe_lines)


def _check_kubeconform_available() -> bool:
    """Check if kubeconform binary is available on the system.

    Returns:
        True if kubeconform can be executed.
    """
    try:
        result = subprocess.run(
            ["kubeconform", "-v"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Test class: Makefile static analysis
# ---------------------------------------------------------------------------


class TestHelmValidateMakefileTarget:
    """Static analysis tests for the helm-validate Makefile target.

    These tests parse the Makefile and verify the target is defined
    with the correct flags, values files, and version pinning. They do
    NOT require kubeconform to be installed.
    """

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_target_exists_in_makefile(self) -> None:
        """Verify the helm-validate target is defined in the Makefile.

        AC-26.1 requires `make helm-validate` to be a valid target.
        This test fails if the target is missing entirely.
        """
        makefile_text = _read_makefile()

        # Look for the target definition line (not just a .PHONY reference)
        has_target = bool(
            re.search(rf"^{HELM_VALIDATE_TARGET}\s*:", makefile_text, re.MULTILINE)
        )
        assert has_target, (
            f"Makefile does not contain a '{HELM_VALIDATE_TARGET}' target.\n"
            "Add a helm-validate target that runs kubeconform validation."
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_target_is_phony(self) -> None:
        """Verify helm-validate is declared as .PHONY.

        Makefile targets that don't produce files must be .PHONY to prevent
        stale-file issues. All existing helm targets follow this convention.
        """
        makefile_text = _read_makefile()

        # Find .PHONY declarations that include helm-validate
        phony_pattern = r"^\.PHONY\s*:.*\b" + re.escape(HELM_VALIDATE_TARGET) + r"\b"
        has_phony = bool(re.search(phony_pattern, makefile_text, re.MULTILINE))
        assert has_phony, (
            f"Makefile target '{HELM_VALIDATE_TARGET}' is not declared as .PHONY.\n"
            f"Add: .PHONY: {HELM_VALIDATE_TARGET}"
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_invokes_kubeconform(self) -> None:
        """Verify the helm-validate recipe invokes kubeconform.

        AC-26.1 requires that the target renders templates and validates
        them with kubeconform. The recipe must contain a kubeconform command.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert "kubeconform" in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not invoke kubeconform.\n"
            f"Recipe:\n{recipe}\n"
            "Expected kubeconform to be called for schema validation."
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_invokes_helm_template(self) -> None:
        """Verify the helm-validate recipe renders templates via helm template.

        The target must render templates before piping to kubeconform.
        This could be via direct `helm template` call or piping.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert "helm template" in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not invoke 'helm template'.\n"
            f"Recipe:\n{recipe}\n"
            "Templates must be rendered before kubeconform validation."
        )

    @pytest.mark.requirement("AC-26.2")
    def test_helm_validate_uses_production_values(self) -> None:
        """Verify the recipe validates against values.yaml (production defaults).

        AC-26.2 requires validation against both values.yaml and values-test.yaml.
        This test checks that values.yaml is referenced in the recipe.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert VALUES_FILE in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not reference '{VALUES_FILE}'.\n"
            f"Recipe:\n{recipe}\n"
            "AC-26.2 requires validation against production defaults (values.yaml)."
        )

    @pytest.mark.requirement("AC-26.2")
    def test_helm_validate_uses_test_values(self) -> None:
        """Verify the recipe validates against values-test.yaml.

        AC-26.2 requires validation against both values.yaml and values-test.yaml.
        A schema violation in either file must fail the target.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert VALUES_TEST_FILE in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not reference '{VALUES_TEST_FILE}'.\n"
            f"Recipe:\n{recipe}\n"
            "AC-26.2 requires validation against test overrides (values-test.yaml)."
        )

    @pytest.mark.requirement("AC-26.2")
    def test_helm_validate_validates_both_values_files_independently(self) -> None:
        """Verify both values files produce separate validation passes.

        A lazy implementation might only validate values.yaml OR only validate
        with both files merged. The recipe must invoke kubeconform (or helm
        template piped to kubeconform) at least twice, once for each values file.
        Alternatively, both values files must be rendered and validated.

        We check that the recipe contains references to both files in contexts
        that would produce separate template renders (separate helm template
        calls or separate --values flags leading to separate kubeconform pipes).
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        # Count how many times helm template appears -- there should be at least 2
        # (one for values.yaml, one for values-test.yaml), OR the recipe should
        # use a loop/for construct that iterates over both files
        helm_template_count = recipe.count("helm template")
        has_loop = "for " in recipe or "foreach" in recipe

        assert helm_template_count >= 2 or has_loop, (
            f"The '{HELM_VALIDATE_TARGET}' recipe appears to render templates "
            f"only once (helm template appears {helm_template_count} time(s), "
            f"no loop found).\n"
            f"Recipe:\n{recipe}\n"
            "AC-26.2 requires BOTH values.yaml and values-test.yaml to be "
            "validated independently. Either use two separate helm template | "
            "kubeconform pipelines or loop over both values files."
        )

    @pytest.mark.requirement("AC-26.4")
    def test_helm_validate_pins_kubernetes_version(self) -> None:
        """Verify kubeconform is called with --kubernetes-version 1.28.0.

        AC-26.4 requires validation against K8s 1.28.0, matching
        Chart.yaml's kubeVersion constraint (>=1.28.0-0).
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert f"--kubernetes-version {EXPECTED_K8S_VERSION}" in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not pin "
            f"--kubernetes-version {EXPECTED_K8S_VERSION}.\n"
            f"Recipe:\n{recipe}\n"
            "AC-26.4 requires kubeconform to validate against K8s 1.28.0, "
            "matching Chart.yaml kubeVersion: '>=1.28.0-0'."
        )

    @pytest.mark.requirement("AC-26.4")
    def test_kubernetes_version_matches_chart_constraint(self) -> None:
        """Verify the pinned K8s version satisfies Chart.yaml kubeVersion.

        Cross-checks that Chart.yaml's kubeVersion constraint and the
        kubeconform --kubernetes-version flag are consistent.
        """
        import yaml

        root = _find_project_root()
        chart_yaml_path = root / "charts" / "floe-platform" / "Chart.yaml"

        try:
            chart_data = yaml.safe_load(chart_yaml_path.read_text())
        except (OSError, yaml.YAMLError) as exc:
            _fail(f"Could not read Chart.yaml: {exc}")

        kube_version_constraint = chart_data.get("kubeVersion", "")
        assert kube_version_constraint, "Chart.yaml is missing kubeVersion field."

        # The constraint should be satisfied by 1.28.0
        # Chart.yaml uses >=1.28.0-0, so 1.28.0 satisfies it
        assert "1.28" in kube_version_constraint, (
            f"Chart.yaml kubeVersion is '{kube_version_constraint}' which "
            f"may not match the expected kubeconform version {EXPECTED_K8S_VERSION}. "
            "Ensure Chart.yaml and kubeconform version are aligned."
        )

    @pytest.mark.requirement("AC-26.5")
    def test_helm_validate_ignores_missing_schemas(self) -> None:
        """Verify kubeconform uses --ignore-missing-schemas for CRD tolerance.

        AC-26.5 requires that subchart CRDs (Dagster, OTel) don't cause
        false failures. --ignore-missing-schemas tells kubeconform to skip
        resources whose schemas aren't in the catalog.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert "--ignore-missing-schemas" in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not include "
            "'--ignore-missing-schemas'.\n"
            f"Recipe:\n{recipe}\n"
            "AC-26.5 requires CRD tolerance. Without --ignore-missing-schemas, "
            "Dagster and OTel CRDs will cause false validation failures."
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_uses_strict_mode(self) -> None:
        """Verify kubeconform uses --strict for strict validation.

        Strict mode rejects resources with additional properties not
        defined in the schema, catching typos and misconfigurations.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert "--strict" in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not include '--strict'.\n"
            f"Recipe:\n{recipe}\n"
            "kubeconform --strict mode rejects additional properties not in "
            "the K8s schema, catching configuration typos."
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_pipes_template_to_kubeconform(self) -> None:
        """Verify helm template output is piped to kubeconform.

        The typical pattern is: helm template ... | kubeconform ...
        This ensures the rendered YAML goes directly into validation.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        # The recipe should pipe helm template output to kubeconform
        # This could be: helm template ... | kubeconform ...
        has_pipe = bool(re.search(r"helm\s+template\b.*\|\s*kubeconform", recipe))
        assert has_pipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not pipe helm template "
            "output to kubeconform.\n"
            f"Recipe:\n{recipe}\n"
            "Expected pattern: helm template ... | kubeconform ..."
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_uses_skip_schema_validation(self) -> None:
        """Verify helm template uses --skip-schema-validation.

        The Dagster subchart references an external JSON schema URL that
        returns 404. All existing helm template invocations in this project
        use --skip-schema-validation to work around this. The helm-validate
        target must do the same.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert "--skip-schema-validation" in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not include "
            "'--skip-schema-validation' for helm template.\n"
            f"Recipe:\n{recipe}\n"
            "The Dagster subchart references an external JSON schema URL that "
            "returns 404. Without --skip-schema-validation, helm template fails."
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_help_text_present(self) -> None:
        """Verify helm-validate is documented in the Makefile help target.

        All Makefile targets in this project use the `## Comment` convention
        on the target line for self-documenting help (e.g.,
        `helm-lint: ## Lint Helm charts`). The helm-validate target must
        follow the same convention so it appears in `make help` output.
        """
        makefile_text = _read_makefile()

        # The project convention is: target: [deps] ## Help text
        # This is what the help target parses to generate output.
        has_help_comment = bool(
            re.search(
                rf"^{re.escape(HELM_VALIDATE_TARGET)}\s*:.*##\s*\S",
                makefile_text,
                re.MULTILINE,
            )
        )

        assert has_help_comment, (
            f"The '{HELM_VALIDATE_TARGET}' target does not have a '## Description' "
            "help comment on its definition line.\n"
            "All Makefile targets in this project use the convention:\n"
            f"  {HELM_VALIDATE_TARGET}: [deps] ## Validate Helm templates with kubeconform\n"
            "This is required so the target appears in `make help` output."
        )


# ---------------------------------------------------------------------------
# Test class: Values file prerequisites
# ---------------------------------------------------------------------------


class TestHelmValidatePrerequisites:
    """Tests that verify prerequisites for helm-validate are in place."""

    @pytest.mark.requirement("AC-26.2")
    def test_values_yaml_exists(self) -> None:
        """Verify charts/floe-platform/values.yaml exists.

        The helm-validate target needs this file to render production defaults.
        """
        root = _find_project_root()
        values_path = root / "charts" / "floe-platform" / VALUES_FILE

        assert values_path.exists(), (
            f"Production values file not found at {values_path}.\n"
            "The helm-validate target requires values.yaml to exist."
        )

    @pytest.mark.requirement("AC-26.2")
    def test_values_test_yaml_exists(self) -> None:
        """Verify charts/floe-platform/values-test.yaml exists.

        The helm-validate target needs this file to render test overrides.
        """
        root = _find_project_root()
        values_test_path = root / "charts" / "floe-platform" / VALUES_TEST_FILE

        assert values_test_path.exists(), (
            f"Test values file not found at {values_test_path}.\n"
            "The helm-validate target requires values-test.yaml to exist."
        )


# ---------------------------------------------------------------------------
# Test class: Functional (requires kubeconform + helm)
# ---------------------------------------------------------------------------


class TestHelmValidateFunctional:
    """Functional tests that actually run `make helm-validate`.

    These tests require both kubeconform and helm to be installed.
    If either is missing, the test FAILs (never skips) per project policy.
    """

    @pytest.mark.requirement("AC-26.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_make_helm_validate_succeeds(self) -> None:
        """Run `make helm-validate` and verify it exits with code 0.

        AC-26.1 requires that running the target locally produces either
        a clean pass or explicit validation errors. This test verifies
        the clean pass case on valid templates.
        """
        if not _check_kubeconform_available():
            _fail(
                "kubeconform is not installed.\n"
                "Install it: https://github.com/yannh/kubeconform#installation\n"
                "Or: go install github.com/yannh/kubeconform/cmd/kubeconform@latest"
            )

        root = _find_project_root()
        result = subprocess.run(
            ["make", HELM_VALIDATE_TARGET],
            capture_output=True,
            timeout=120,
            check=False,
            cwd=str(root),
        )

        stdout = result.stdout.decode() if result.stdout else ""
        stderr = result.stderr.decode() if result.stderr else ""

        assert result.returncode == 0, (
            f"`make {HELM_VALIDATE_TARGET}` failed with exit code "
            f"{result.returncode}.\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

    @pytest.mark.requirement("AC-26.1")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_make_helm_validate_produces_output(self) -> None:
        """Verify `make helm-validate` produces meaningful output.

        A no-op target that silently succeeds is not acceptable.
        The target must produce output indicating validation was performed.
        """
        if not _check_kubeconform_available():
            _fail(
                "kubeconform is not installed.\n"
                "Install it: https://github.com/yannh/kubeconform#installation"
            )

        root = _find_project_root()
        result = subprocess.run(
            ["make", HELM_VALIDATE_TARGET],
            capture_output=True,
            timeout=120,
            check=False,
            cwd=str(root),
        )

        combined_output = (
            (result.stdout.decode() if result.stdout else "")
            + (result.stderr.decode() if result.stderr else "")
        )

        # The output should mention validation or kubeconform activity
        assert len(combined_output.strip()) > 0, (
            f"`make {HELM_VALIDATE_TARGET}` produced no output.\n"
            "The target should print validation progress or results."
        )

    @pytest.mark.requirement("AC-26.2")
    @pytest.mark.usefixtures("helm_available", "update_helm_dependencies")
    def test_make_helm_validate_validates_both_files(self) -> None:
        """Verify the output references both values files being validated.

        AC-26.2 requires both values.yaml and values-test.yaml are validated.
        The output should indicate that both were processed.
        """
        if not _check_kubeconform_available():
            _fail(
                "kubeconform is not installed.\n"
                "Install it: https://github.com/yannh/kubeconform#installation"
            )

        root = _find_project_root()
        result = subprocess.run(
            ["make", HELM_VALIDATE_TARGET],
            capture_output=True,
            timeout=120,
            check=False,
            cwd=str(root),
        )

        combined_output = (
            (result.stdout.decode() if result.stdout else "")
            + (result.stderr.decode() if result.stderr else "")
        )

        # The output should reference both values files or "values" and "test"
        mentions_default = "values.yaml" in combined_output or "default" in combined_output.lower()
        mentions_test = "values-test" in combined_output or "test" in combined_output.lower()

        assert mentions_default and mentions_test, (
            f"`make {HELM_VALIDATE_TARGET}` output does not indicate both "
            "values files were validated.\n"
            f"Output:\n{combined_output}\n"
            "Expected references to both values.yaml and values-test.yaml."
        )
