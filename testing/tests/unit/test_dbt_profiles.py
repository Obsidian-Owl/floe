"""Unit tests: dbt Demo Product Profile Validation (WU5-AC1).

Validates that each demo product (customer-360, iot-telemetry, financial-risk)
has a valid profiles.yml with DuckDB target configuration. This is a structural
validation test — no dbt execution or external services required.

DuckDB-only: These tests validate YAML structure on disk. No K8s, Polaris,
or MinIO dependencies.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Demo products with expected profile names (underscore-separated)
DEMO_PRODUCTS: dict[str, str] = {
    "customer-360": "customer_360",
    "iot-telemetry": "iot_telemetry",
    "financial-risk": "financial_risk",
}


@pytest.fixture
def project_root() -> Path:
    """Project root directory for structural validation tests."""
    root = Path(__file__).parent.parent.parent.parent
    assert (root / "demo").exists(), (
        f"Project root {root} does not contain 'demo' directory"
    )
    return root


@pytest.mark.requirement("WU5-AC1")
class TestDbtProfiles:
    """Validate dbt profiles.yml structure for each demo product.

    DuckDB-only: These tests read YAML files from disk. No external
    services required.
    """

    @pytest.mark.requirement("WU5-AC1")
    @pytest.mark.parametrize(
        ("product", "profile_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_profiles_yml_exists(
        self,
        project_root: Path,
        product: str,
        profile_name: str,  # noqa: ARG002
    ) -> None:
        """Verify profiles.yml exists for each demo product.

        DuckDB-only: Checks file existence on disk.
        """
        profiles_path = project_root / "demo" / product / "profiles.yml"
        assert profiles_path.exists(), (
            f"profiles.yml not found at {profiles_path}\n"
            f"Each demo product must have a profiles.yml for dbt."
        )

    @pytest.mark.requirement("WU5-AC1")
    @pytest.mark.parametrize(
        ("product", "profile_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_profiles_yml_valid_yaml(
        self,
        project_root: Path,
        product: str,
        profile_name: str,  # noqa: ARG002
    ) -> None:
        """Verify profiles.yml is valid YAML.

        DuckDB-only: Parses YAML from disk.
        """
        profiles_path = project_root / "demo" / product / "profiles.yml"
        content = profiles_path.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), (
            f"profiles.yml for {product} should parse as a dict, got {type(parsed)}"
        )

    @pytest.mark.requirement("WU5-AC1")
    @pytest.mark.parametrize(
        ("product", "profile_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_profiles_yml_has_correct_profile_name(
        self,
        project_root: Path,
        product: str,
        profile_name: str,
    ) -> None:
        """Verify profiles.yml top-level key matches expected profile name.

        DuckDB-only: Validates YAML structure.

        The profile name must match the dbt_project.yml 'profile' field.
        Convention: product name with hyphens replaced by underscores.
        """
        profiles_path = project_root / "demo" / product / "profiles.yml"
        parsed = yaml.safe_load(profiles_path.read_text())
        assert profile_name in parsed, (
            f"profiles.yml for {product} must have profile '{profile_name}' "
            f"as top-level key. Found keys: {list(parsed.keys())}"
        )

    @pytest.mark.requirement("WU5-AC1")
    @pytest.mark.parametrize(
        ("product", "profile_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_profiles_yml_has_duckdb_target(
        self,
        project_root: Path,
        product: str,
        profile_name: str,
    ) -> None:
        """Verify profiles.yml has DuckDB target in 'dev' output.

        DuckDB-only: Validates DuckDB is the compute engine.

        Each demo product must use DuckDB for local development and E2E testing.
        The 'type: duckdb' ensures dbt uses DuckDB adapter.
        """
        profiles_path = project_root / "demo" / product / "profiles.yml"
        parsed = yaml.safe_load(profiles_path.read_text())
        profile = parsed[profile_name]

        # Must have 'target: dev'
        assert profile.get("target") == "dev", (
            f"Profile '{profile_name}' must have 'target: dev', "
            f"got target={profile.get('target')}"
        )

        # Must have outputs.dev
        outputs = profile.get("outputs", {})
        assert "dev" in outputs, (
            f"Profile '{profile_name}' must have 'outputs.dev', "
            f"got outputs: {list(outputs.keys())}"
        )

        # Dev output must use DuckDB
        dev_output = outputs["dev"]
        assert dev_output.get("type") == "duckdb", (
            f"Profile '{profile_name}' dev output must have 'type: duckdb', "
            f"got type={dev_output.get('type')}"
        )

    @pytest.mark.requirement("WU5-AC1")
    @pytest.mark.parametrize(
        ("product", "profile_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_profiles_yml_has_duckdb_path(
        self,
        project_root: Path,
        product: str,
        profile_name: str,
    ) -> None:
        """Verify profiles.yml DuckDB output has a valid path configured.

        DuckDB-only: Validates path configuration.

        The path determines where DuckDB stores its database file. Must be
        relative to the project directory (typically 'target/demo.duckdb').
        """
        profiles_path = project_root / "demo" / product / "profiles.yml"
        parsed = yaml.safe_load(profiles_path.read_text())
        dev_output = parsed[profile_name]["outputs"]["dev"]

        assert "path" in dev_output, (
            f"Profile '{profile_name}' dev output must have 'path' for DuckDB database. "
            f"Got keys: {list(dev_output.keys())}"
        )
        path_value = dev_output["path"]
        assert isinstance(path_value, str) and len(path_value) > 0, (
            f"Profile '{profile_name}' DuckDB path must be a non-empty string, "
            f"got: {path_value!r}"
        )

    @pytest.mark.requirement("WU5-AC1")
    @pytest.mark.parametrize(
        ("product", "profile_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_dbt_project_profile_matches(
        self,
        project_root: Path,
        product: str,
        profile_name: str,
    ) -> None:
        """Verify dbt_project.yml 'profile' field matches profiles.yml key.

        DuckDB-only: Cross-validates two YAML files.

        If these don't match, dbt will fail to find the correct profile
        at runtime.
        """
        dbt_project_path = project_root / "demo" / product / "dbt_project.yml"
        assert dbt_project_path.exists(), (
            f"dbt_project.yml not found for {product}"
        )

        dbt_project = yaml.safe_load(dbt_project_path.read_text())
        project_profile = dbt_project.get("profile")

        assert project_profile == profile_name, (
            f"dbt_project.yml profile '{project_profile}' does not match "
            f"profiles.yml key '{profile_name}' for {product}. "
            f"These must match for dbt to find the correct profile."
        )
