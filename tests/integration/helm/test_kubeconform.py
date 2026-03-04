"""Kubeconform schema validation tests for floe-platform Helm chart.

Tests that validate the `make helm-validate` target exists, is correctly
configured, and produces valid Kubernetes manifests when run.

The tests statically parse the Makefile to verify the helm-validate target
has the correct flags and values file references, then optionally run the
target end-to-end if kubeconform is installed.

Requirements:
    AC-26.1: make helm-validate renders templates and validates with kubeconform
    AC-26.2: Validation runs against both values.yaml and values-test.yaml
    AC-26.3: CI workflow includes kubeconform stage
    AC-26.4: kubeconform validates against K8s 1.28.0
    AC-26.5: Subchart CRDs don't cause false failures
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HELM_VALIDATE_TARGET = "helm-validate"
EXPECTED_K8S_VERSION = "1.28.0"
VALUES_FILE = "values.yaml"
VALUES_TEST_FILE = "values-test.yaml"
CHART_PATH = "charts/floe-platform"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    pytest.fail("Could not find project root (directory containing Makefile).")


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
        pytest.fail(f"Could not read Makefile at {makefile_path}: {exc}")


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
        pytest.fail(
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
        pytest.fail(
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
        has_target = bool(re.search(rf"^{HELM_VALIDATE_TARGET}\s*:", makefile_text, re.MULTILINE))
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
            pytest.fail(f"Could not read Chart.yaml: {exc}")

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

    @pytest.mark.requirement("AC-27.2")
    def test_helm_validate_enforces_schema_validation(self) -> None:
        """Verify helm template does NOT use --skip-schema-validation.

        Dagster chart 1.12+ fixed dead kubernetesjsonschema.dev $ref URLs,
        so schema validation is now enforced. The helm-validate target must
        not bypass it.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert "--skip-schema-validation" not in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe still includes "
            "'--skip-schema-validation'.\n"
            f"Recipe:\n{recipe}\n"
            "Dagster 1.12+ fixed dead schema URLs. Schema validation "
            "should now be enforced."
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

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_uses_summary_flag(self) -> None:
        """Verify kubeconform uses -summary for aggregate output.

        The -summary flag provides a summary of validation results,
        making it easier to see pass/fail counts in CI output.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert "-summary" in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not include '-summary'.\n"
            f"Recipe:\n{recipe}\n"
            "kubeconform -summary provides aggregate validation results."
        )

    @pytest.mark.requirement("AC-26.1")
    def test_helm_validate_targets_correct_chart(self) -> None:
        """Verify helm template targets the floe-platform chart directory.

        The recipe must reference charts/floe-platform to render the
        correct chart's templates for validation.
        """
        makefile_text = _read_makefile()
        recipe = _extract_target_recipe(makefile_text, HELM_VALIDATE_TARGET)

        assert CHART_PATH in recipe, (
            f"The '{HELM_VALIDATE_TARGET}' recipe does not reference "
            f"'{CHART_PATH}'.\n"
            f"Recipe:\n{recipe}\n"
            "Expected helm template to target the floe-platform chart."
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
            pytest.fail(
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
            pytest.fail(
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

        combined_output = (result.stdout.decode() if result.stdout else "") + (
            result.stderr.decode() if result.stderr else ""
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
            pytest.fail(
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

        combined_output = (result.stdout.decode() if result.stdout else "") + (
            result.stderr.decode() if result.stderr else ""
        )

        # Match the exact Makefile echo messages for each values file pass
        mentions_default = "production defaults" in combined_output.lower()
        mentions_test = "test overrides" in combined_output.lower()

        assert mentions_default and mentions_test, (
            f"`make {HELM_VALIDATE_TARGET}` output does not indicate both "
            "values files were validated.\n"
            f"Output:\n{combined_output}\n"
            "Expected references to both values.yaml and values-test.yaml."
        )

    @pytest.mark.requirement("AC-26.1")
    @pytest.mark.usefixtures("helm_available")
    def test_kubeconform_rejects_invalid_manifest(self) -> None:
        """Verify kubeconform catches invalid K8s manifests.

        Feeds a deliberately invalid Deployment (wrong apiVersion) through
        kubeconform with the same flags used in the Makefile to confirm
        the tool actually catches schema violations.
        """
        if not _check_kubeconform_available():
            pytest.fail(
                "kubeconform is not installed.\n"
                "Install it: https://github.com/yannh/kubeconform#installation"
            )

        invalid_manifest = (
            "apiVersion: apps/v999\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: invalid-test\n"
            "spec:\n"
            "  replicas: 1\n"
        )

        result = subprocess.run(
            [
                "kubeconform",
                "--strict",
                "--kubernetes-version",
                EXPECTED_K8S_VERSION,
            ],
            input=invalid_manifest.encode(),
            capture_output=True,
            timeout=30,
            check=False,
        )

        assert result.returncode != 0, (
            "kubeconform accepted an invalid manifest (apiVersion: apps/v999).\n"
            "Expected non-zero exit code for schema violation.\n"
            f"STDOUT: {result.stdout.decode()}\n"
            f"STDERR: {result.stderr.decode()}"
        )


# ---------------------------------------------------------------------------
# Test class: CI workflow (helm-ci.yaml) kubeconform stage
# ---------------------------------------------------------------------------


# Constants for CI workflow tests
HELM_CI_WORKFLOW = ".github/workflows/helm-ci.yaml"
MAIN_BRANCH_CONDITION = "github.ref == 'refs/heads/main'"


def _load_helm_ci_workflow() -> dict[str, object]:
    """Load and parse the helm-ci.yaml GitHub Actions workflow.

    Returns:
        Parsed YAML as a dictionary.

    Raises:
        pytest.fail: If the workflow file does not exist or is invalid YAML.
    """
    import yaml

    root = _find_project_root()
    workflow_path = root / HELM_CI_WORKFLOW

    if not workflow_path.exists():
        pytest.fail(
            f"Helm CI workflow not found at {workflow_path}.\n"
            "Expected .github/workflows/helm-ci.yaml to exist."
        )

    try:
        content = workflow_path.read_text()
        parsed = yaml.safe_load(content)
    except (OSError, yaml.YAMLError) as exc:
        pytest.fail(f"Could not parse {HELM_CI_WORKFLOW}: {exc}")

    if not isinstance(parsed, dict):
        pytest.fail(f"{HELM_CI_WORKFLOW} did not parse as a YAML dictionary.")

    return parsed  # type: ignore[return-value]


def _find_kubeconform_job(
    workflow: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    """Find the kubeconform job in the workflow.

    Searches for a job whose key contains 'kubeconform' (case-insensitive)
    or whose 'name' field contains 'kubeconform' (case-insensitive).

    Args:
        workflow: Parsed workflow dictionary.

    Returns:
        Tuple of (job_key, job_dict) if found, None otherwise.
    """
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return None

    for job_key, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue
        # Check job key
        if "kubeconform" in job_key.lower():
            return (job_key, job_config)
        # Check job name
        job_name = job_config.get("name", "")
        if isinstance(job_name, str) and "kubeconform" in job_name.lower():
            return (job_key, job_config)

    return None


def _get_all_step_runs(job_config: dict[str, object]) -> list[str]:
    """Extract all 'run' strings from a job's steps.

    Args:
        job_config: Parsed job configuration dictionary.

    Returns:
        List of run command strings from all steps.
    """
    steps = job_config.get("steps", [])
    if not isinstance(steps, list):
        return []

    runs: list[str] = []
    for step in steps:
        if isinstance(step, dict) and "run" in step:
            run_val = step["run"]
            if isinstance(run_val, str):
                runs.append(run_val)
    return runs


def _get_all_step_names(job_config: dict[str, object]) -> list[str]:
    """Extract all 'name' strings from a job's steps.

    Args:
        job_config: Parsed job configuration dictionary.

    Returns:
        List of step name strings.
    """
    steps = job_config.get("steps", [])
    if not isinstance(steps, list):
        return []

    names: list[str] = []
    for step in steps:
        if isinstance(step, dict) and "name" in step:
            name_val = step["name"]
            if isinstance(name_val, str):
                names.append(name_val)
    return names


class TestHelmCIKubeconform:
    """Tests that verify the kubeconform CI stage exists in helm-ci.yaml.

    AC-26.3 requires a kubeconform validation stage in the GitHub Actions
    workflow that runs on every PR (not just main). These tests parse the
    workflow YAML and verify the stage structure, conditions, and commands.
    """

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_exists_in_workflow(self) -> None:
        """Verify helm-ci.yaml contains a job with 'kubeconform' in its key or name.

        AC-26.3 requires a kubeconform validation stage. This test fails
        if no job with 'kubeconform' in its identifier or display name
        is found in the workflow file.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, (
            f"No kubeconform job found in {HELM_CI_WORKFLOW}.\n"
            "Expected a job with 'kubeconform' in its key or name field.\n"
            f"Current jobs: {list(workflow.get('jobs', {}).keys())}"
        )

        job_key, _ = result
        assert "kubeconform" in job_key.lower(), (
            f"Found kubeconform job but its key '{job_key}' does not contain "
            "'kubeconform'. The job key itself should include 'kubeconform' "
            "for discoverability."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_not_conditional_on_main(self) -> None:
        """Verify the kubeconform job does NOT have a main-branch-only condition.

        AC-26.3 requires kubeconform to run on every PR, not just main.
        The integration job has `if: github.ref == 'refs/heads/main'` but
        the kubeconform job must NOT have this restriction.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, (
            f"No kubeconform job found in {HELM_CI_WORKFLOW}. "
            "Cannot verify branch condition without the job."
        )

        job_key, job_config = result
        job_if = job_config.get("if", "")

        # The job should either have no 'if' condition or one that
        # does NOT restrict to main branch only
        if isinstance(job_if, str) and job_if.strip():
            assert "refs/heads/main" not in job_if, (
                f"Kubeconform job '{job_key}' has an 'if' condition that "
                f"restricts to main branch: '{job_if}'.\n"
                "AC-26.3 requires kubeconform to run on EVERY PR, not just main."
            )
            assert "github.ref ==" not in job_if or "main" not in job_if, (
                f"Kubeconform job '{job_key}' appears to be conditional on "
                f"a specific branch: '{job_if}'.\n"
                "AC-26.3 requires kubeconform to run on every PR."
            )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_has_no_ref_condition_at_all(self) -> None:
        """Verify the kubeconform job has no 'if' condition referencing github.ref.

        A sloppy implementation might add `if: github.ref != 'refs/heads/main'`
        (only on PRs, not on main pushes) or other ref-based conditions. The
        kubeconform job should run unconditionally on all triggers.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        job_key, job_config = result
        job_if = job_config.get("if", "")

        if isinstance(job_if, str) and job_if.strip():
            assert "github.ref" not in job_if, (
                f"Kubeconform job '{job_key}' has a condition referencing "
                f"github.ref: '{job_if}'.\n"
                "The kubeconform stage should run unconditionally on all "
                "workflow triggers (push to main AND pull_request)."
            )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_installs_kubeconform(self) -> None:
        """Verify the kubeconform job has a step that installs the kubeconform binary.

        The CI runner does not have kubeconform pre-installed. The job must
        download and install it before running validation.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        _, job_config = result
        all_runs = _get_all_step_runs(job_config)
        all_names = _get_all_step_names(job_config)

        # Check for kubeconform installation in run commands
        install_keywords = ("install", "curl", "wget", "go install", "tar")
        has_install_in_run = any(
            "kubeconform" in run and any(kw in run.lower() for kw in install_keywords)
            for run in all_runs
        )

        # Also check step names for installation indication
        has_install_in_name = any(
            "kubeconform" in name.lower() and "install" in name.lower() for name in all_names
        )

        assert has_install_in_run or has_install_in_name, (
            "Kubeconform job does not appear to install kubeconform.\n"
            f"Step names: {all_names}\n"
            f"Run commands (first 200 chars each): "
            f"{[r[:200] for r in all_runs]}\n"
            "Expected a step that downloads/installs kubeconform "
            "(e.g., via curl, go install, or tar extraction)."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_runs_make_helm_validate(self) -> None:
        """Verify the kubeconform job runs `make helm-validate` or kubeconform directly.

        AC-26.3 requires the stage to run kubeconform validation. The
        preferred method is `make helm-validate`, but direct kubeconform
        invocation is also acceptable.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        _, job_config = result
        all_runs = _get_all_step_runs(job_config)

        has_make_target = any("make helm-validate" in run for run in all_runs)

        has_direct_kubeconform = any(
            "kubeconform" in run and ("helm template" in run or "validate" in run.lower())
            for run in all_runs
        )

        assert has_make_target or has_direct_kubeconform, (
            "Kubeconform job does not run `make helm-validate` or invoke "
            "kubeconform for validation.\n"
            f"Run commands: {[r[:200] for r in all_runs]}\n"
            "Expected either `make helm-validate` or a direct kubeconform "
            "invocation with helm template piping."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_depends_on_lint(self) -> None:
        """Verify the kubeconform job has a dependency on the lint job.

        The kubeconform stage should run after lint to ensure charts are
        syntactically valid before schema validation. This is expressed
        via the 'needs' field in the job configuration.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        job_key, job_config = result
        needs = job_config.get("needs", [])

        # 'needs' can be a string or list
        if isinstance(needs, str):
            needs_list = [needs]
        elif isinstance(needs, list):
            needs_list = [str(n) for n in needs]
        else:
            needs_list = []

        assert "lint" in needs_list, (
            f"Kubeconform job '{job_key}' does not depend on the 'lint' job.\n"
            f"Current 'needs': {needs_list}\n"
            "The kubeconform stage should run after lint "
            "(add `needs: lint` or include 'lint' in the needs list)."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_runs_on_ubuntu(self) -> None:
        """Verify the kubeconform job runs on ubuntu-latest.

        All existing jobs in the workflow run on ubuntu-latest. The
        kubeconform job should follow the same convention for consistency
        and because kubeconform is a Linux binary.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        job_key, job_config = result
        runs_on = job_config.get("runs-on", "")

        assert isinstance(runs_on, str) and "ubuntu" in runs_on, (
            f"Kubeconform job '{job_key}' does not run on ubuntu.\n"
            f"Current 'runs-on': {runs_on}\n"
            "Expected 'runs-on: ubuntu-latest' to match other jobs in the workflow."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_checks_out_code(self) -> None:
        """Verify the kubeconform job has a checkout step.

        The job needs access to the chart source files. Without a checkout
        step, make helm-validate cannot find the charts directory.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        _, job_config = result
        steps = job_config.get("steps", [])

        has_checkout = False
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict):
                    uses = step.get("uses", "")
                    if isinstance(uses, str) and "actions/checkout" in uses:
                        has_checkout = True
                        break

        assert has_checkout, (
            "Kubeconform job does not have a checkout step.\n"
            "The job needs `uses: actions/checkout@v4` (or pinned hash) to "
            "access chart files."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_is_between_template_and_security(self) -> None:
        """Verify kubeconform is positioned logically in the pipeline.

        The kubeconform stage should come after template rendering (it
        validates rendered templates) and before or alongside security
        scanning. We verify this by checking job ordering in the YAML
        and the dependency graph.
        """
        workflow = _load_helm_ci_workflow()
        jobs = workflow.get("jobs", {})

        assert isinstance(jobs, dict), "Workflow 'jobs' is not a dictionary."

        result = _find_kubeconform_job(workflow)
        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        job_key, job_config = result

        # Verify it does NOT depend on security (it should run before/alongside)
        needs = job_config.get("needs", [])
        if isinstance(needs, str):
            needs_list = [needs]
        elif isinstance(needs, list):
            needs_list = [str(n) for n in needs]
        else:
            needs_list = []

        assert "security" not in needs_list, (
            f"Kubeconform job '{job_key}' depends on the 'security' job.\n"
            "kubeconform should run BEFORE or ALONGSIDE security, not after it."
        )

        assert "integration" not in needs_list, (
            f"Kubeconform job '{job_key}' depends on the 'integration' job.\n"
            "kubeconform should run much earlier in the pipeline, not after "
            "integration tests."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_job_sets_up_helm(self) -> None:
        """Verify the kubeconform job sets up Helm.

        If the job runs `make helm-validate`, it needs helm installed.
        All other jobs in the workflow use azure/setup-helm for this.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        _, job_config = result
        steps = job_config.get("steps", [])

        has_helm_setup = False
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict):
                    uses = step.get("uses", "")
                    if isinstance(uses, str) and "setup-helm" in uses:
                        has_helm_setup = True
                        break

        assert has_helm_setup, (
            "Kubeconform job does not set up Helm.\n"
            "The job needs `uses: azure/setup-helm@...` to install Helm CLI "
            "for template rendering."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_workflow_still_has_existing_stages(self) -> None:
        """Verify adding kubeconform did not remove existing stages.

        The workflow should still contain lint, template, schema, security,
        and integration jobs. Adding kubeconform must not break existing
        pipeline stages.
        """
        workflow = _load_helm_ci_workflow()
        jobs = workflow.get("jobs", {})
        assert isinstance(jobs, dict), "Workflow 'jobs' is not a dictionary."

        expected_existing_jobs = ["lint", "template", "schema", "security", "integration"]
        job_keys = list(jobs.keys())

        for expected_job in expected_existing_jobs:
            assert expected_job in job_keys, (
                f"Existing job '{expected_job}' is missing from {HELM_CI_WORKFLOW}.\n"
                f"Current jobs: {job_keys}\n"
                "Adding the kubeconform stage must not remove existing stages."
            )

    @pytest.mark.requirement("AC-26.3")
    def test_integration_job_still_conditional_on_main(self) -> None:
        """Verify the integration job remains conditional on main branch.

        The integration job should still have its main-branch-only condition.
        This test ensures that the kubeconform addition did not accidentally
        remove the condition from the integration job.
        """
        workflow = _load_helm_ci_workflow()
        jobs = workflow.get("jobs", {})
        assert isinstance(jobs, dict), "Workflow 'jobs' is not a dictionary."

        integration_job = jobs.get("integration", {})
        assert isinstance(integration_job, dict), "Integration job not found or not a dictionary."

        integration_if = integration_job.get("if", "")
        assert isinstance(integration_if, str) and "refs/heads/main" in integration_if, (
            f"Integration job 'if' condition changed: '{integration_if}'.\n"
            "The integration job must remain conditional on main branch "
            "(if: github.ref == 'refs/heads/main')."
        )

    @pytest.mark.requirement("AC-26.3")
    def test_kubeconform_install_verifies_checksum(self) -> None:
        """Verify kubeconform install step includes SHA-256 verification.

        CWE-494: Binary installs without integrity checks risk
        supply-chain compromise. The install step must verify the
        download checksum before extracting.
        """
        workflow = _load_helm_ci_workflow()
        result = _find_kubeconform_job(workflow)

        assert result is not None, f"No kubeconform job found in {HELM_CI_WORKFLOW}."

        _, job_config = result
        all_runs = _get_all_step_runs(job_config)

        has_checksum = any("sha256sum" in run or "shasum" in run for run in all_runs)

        assert has_checksum, (
            "Kubeconform install step does not verify SHA-256 checksum.\n"
            "Binary installs must include integrity verification (CWE-494).\n"
            "Pattern: echo '<hash>  file' | sha256sum -c -"
        )
