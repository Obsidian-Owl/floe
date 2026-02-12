"""E2E test: dbt Build Full Lifecycle (AC-2.10).

Validates the complete dbt lifecycle for each demo product:
    dbt deps → dbt seed → dbt run → dbt test → dbt docs generate

Prerequisites:
    - Kind cluster with all services: make kind-up
    - Port-forwards active: make test-e2e
    - dbt installed (via uv/pip)

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.10
    - demo/*/dbt_project.yml: dbt project configs
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Demo products that have dbt projects
DBT_PRODUCTS = [
    "customer-360",
    "iot-telemetry",
    "financial-risk",
]


def _run_dbt(
    args: list[str],
    project_dir: Path,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run dbt command in the specified project directory.

    Args:
        args: dbt command arguments (e.g., ["run", "--select", "staging"]).
        project_dir: Path to the dbt project directory.
        timeout: Command timeout in seconds.

    Returns:
        Completed process result.
    """
    return subprocess.run(
        ["dbt"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        cwd=str(project_dir),
    )


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.10")
class TestDbtLifecycle:
    """Full dbt lifecycle: deps → seed → run → test → docs.

    Validates that dbt commands execute successfully against real
    DuckDB compute (as configured in the demo products).
    """

    @pytest.mark.requirement("AC-2.10")
    def test_dbt_projects_exist(self, project_root: Path) -> None:
        """Verify all demo products have dbt_project.yml files.

        The dbt project file is the entry point for all dbt operations.
        """
        for product in DBT_PRODUCTS:
            dbt_project = project_root / "demo" / product / "dbt_project.yml"
            assert dbt_project.exists(), (
                f"dbt_project.yml not found for {product}: {dbt_project}\n"
                f"Each demo product must have a dbt project."
            )

    @pytest.mark.requirement("AC-2.10")
    def test_dbt_deps(self, project_root: Path) -> None:
        """Run dbt deps for each demo product.

        Installs dbt package dependencies (e.g., dbt-utils).
        Must succeed before any other dbt command.
        """
        for product in DBT_PRODUCTS:
            project_dir = project_root / "demo" / product
            if not (project_dir / "packages.yml").exists():
                # No packages.yml means no deps needed
                continue

            result = _run_dbt(["deps"], project_dir)
            assert result.returncode == 0, (
                f"dbt deps failed for {product}:\n"
                f"stdout: {result.stdout[-500:]}\n"
                f"stderr: {result.stderr[-500:]}"
            )

    @pytest.mark.requirement("AC-2.10")
    def test_dbt_seed(self, project_root: Path) -> None:
        """Run dbt seed for each demo product.

        Loads CSV seed data into the compute engine. Seeds provide the
        test data for staging models.
        """
        for product in DBT_PRODUCTS:
            project_dir = project_root / "demo" / product
            seeds_dir = project_dir / "seeds"

            if not seeds_dir.exists() or not list(seeds_dir.glob("*.csv")):
                # No seeds to load
                continue

            result = _run_dbt(["seed"], project_dir)
            assert result.returncode == 0, (
                f"dbt seed failed for {product}:\n"
                f"stdout: {result.stdout[-500:]}\n"
                f"stderr: {result.stderr[-500:]}"
            )

    @pytest.mark.requirement("AC-2.10")
    def test_dbt_run(self, project_root: Path) -> None:
        """Run dbt run for each demo product.

        Executes all SQL models (staging → intermediate → marts).
        This is the core transformation step.
        """
        for product in DBT_PRODUCTS:
            project_dir = project_root / "demo" / product
            result = _run_dbt(["run"], project_dir, timeout=180)
            assert result.returncode == 0, (
                f"dbt run failed for {product}:\n"
                f"stdout: {result.stdout[-500:]}\n"
                f"stderr: {result.stderr[-500:]}"
            )

    @pytest.mark.requirement("AC-2.10")
    def test_dbt_test(self, project_root: Path) -> None:
        """Run dbt test for each demo product.

        Executes data quality tests defined in the dbt project.
        Tests validate referential integrity, not-null constraints, etc.
        """
        for product in DBT_PRODUCTS:
            project_dir = project_root / "demo" / product

            # Check if tests directory exists
            tests_dir = project_dir / "tests"
            has_schema_tests = (
                any((project_dir / "models").rglob("*.yml"))
                if (project_dir / "models").exists()
                else False
            )

            if not tests_dir.exists() and not has_schema_tests:
                continue

            result = _run_dbt(["test"], project_dir)
            assert result.returncode == 0, (
                f"dbt test failed for {product}:\n"
                f"stdout: {result.stdout[-500:]}\n"
                f"stderr: {result.stderr[-500:]}"
            )

    @pytest.mark.requirement("AC-2.10")
    def test_dbt_docs_generate(self, project_root: Path) -> None:
        """Run dbt docs generate for each demo product.

        Generates the documentation catalog (catalog.json, manifest.json).
        Verifies the docs generation pipeline is functional.
        """
        for product in DBT_PRODUCTS:
            project_dir = project_root / "demo" / product
            result = _run_dbt(["docs", "generate"], project_dir, timeout=120)
            assert result.returncode == 0, (
                f"dbt docs generate failed for {product}:\n"
                f"stdout: {result.stdout[-500:]}\n"
                f"stderr: {result.stderr[-500:]}"
            )

            # Verify catalog.json was generated
            target_dir = project_dir / "target"
            if target_dir.exists():
                catalog = target_dir / "catalog.json"
                manifest = target_dir / "manifest.json"
                assert catalog.exists() or manifest.exists(), (
                    f"dbt docs generate didn't produce catalog/manifest for {product}"
                )
