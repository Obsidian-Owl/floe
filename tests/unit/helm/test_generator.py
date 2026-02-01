"""Unit tests for Helm values generator.

Tests the HelmValuesGenerator class and its methods.

Requirements tested:
- 9b-FR-060: HelmValuesGenerator implementation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_core.helm.generator import HelmValuesGenerator, generate_values_from_config
from floe_core.helm.schemas import HelmValuesConfig


class TestHelmValuesGenerator:
    """Tests for HelmValuesGenerator class."""

    @pytest.mark.requirement("9b-FR-060")
    def test_create_with_defaults(self) -> None:
        """Test creating generator with default configuration."""
        generator = HelmValuesGenerator()
        assert generator.config.environment == "dev"

    @pytest.mark.requirement("9b-FR-060")
    def test_create_with_config(self, sample_helm_config: HelmValuesConfig) -> None:
        """Test creating generator with custom configuration."""
        generator = HelmValuesGenerator(sample_helm_config)
        assert generator.config.environment == "staging"

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_basic_values(self) -> None:
        """Test generating basic values without plugins."""
        config = HelmValuesConfig.with_defaults(environment="dev")
        generator = HelmValuesGenerator(config)
        values = generator.generate()

        assert values["global"]["environment"] == "dev"
        assert "namespace" in values
        assert "autoscaling" in values

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_with_base_values(self) -> None:
        """Test generating values with base values."""
        base = {"dagster": {"enabled": True, "replicas": 1}}
        generator = HelmValuesGenerator(
            HelmValuesConfig.with_defaults(),
            base_values=base,
        )
        values = generator.generate()

        assert values["dagster"]["enabled"] is True
        assert values["dagster"]["replicas"] == 1

    @pytest.mark.requirement("9b-FR-060")
    def test_add_plugin_values(self) -> None:
        """Test adding plugin values."""
        generator = HelmValuesGenerator()
        generator.add_plugin_values({"polaris": {"enabled": True}})
        generator.add_plugin_values({"otel": {"enabled": True}})
        values = generator.generate()

        assert values["polaris"]["enabled"] is True
        assert values["otel"]["enabled"] is True

    @pytest.mark.requirement("9b-FR-060")
    def test_plugin_values_merge(self) -> None:
        """Test that plugin values merge correctly."""
        generator = HelmValuesGenerator()
        generator.add_plugin_values({"dagster": {"replicas": 1}})
        generator.add_plugin_values({"dagster": {"resources": {"cpu": "100m"}}})
        values = generator.generate()

        assert values["dagster"]["replicas"] == 1
        assert values["dagster"]["resources"]["cpu"] == "100m"

    @pytest.mark.requirement("9b-FR-060")
    def test_user_overrides_precedence(self) -> None:
        """Test that user overrides take precedence."""
        generator = HelmValuesGenerator()
        generator.add_plugin_values({"dagster": {"replicas": 1}})
        generator.set_user_overrides({"dagster": {"replicas": 5}})
        values = generator.generate()

        assert values["dagster"]["replicas"] == 5

    @pytest.mark.requirement("9b-FR-060")
    def test_generate_for_environments(self) -> None:
        """Test generating values for multiple environments."""
        generator = HelmValuesGenerator(HelmValuesConfig.with_defaults())
        generator.add_plugin_values({"dagster": {"enabled": True}})

        results = generator.generate_for_environments(["dev", "staging", "prod"])

        assert len(results) == 3
        assert results["dev"]["global"]["environment"] == "dev"
        assert results["staging"]["global"]["environment"] == "staging"
        assert results["prod"]["global"]["environment"] == "prod"
        # All should have plugin values
        assert all(r["dagster"]["enabled"] for r in results.values())

    @pytest.mark.requirement("9b-FR-060")
    def test_prod_environment_features(self) -> None:
        """Test that prod environment enables production features."""
        generator = HelmValuesGenerator(HelmValuesConfig.with_defaults())
        results = generator.generate_for_environments(["prod"])

        assert results["prod"]["autoscaling"]["enabled"] is True
        assert results["prod"]["networkPolicy"]["enabled"] is True
        assert results["prod"]["podDisruptionBudget"]["enabled"] is True

    @pytest.mark.requirement("9b-FR-060")
    def test_write_values(self, tmp_path: Path) -> None:
        """Test writing values to file."""
        generator = HelmValuesGenerator()
        values = {"test": "value"}
        output_path = tmp_path / "values.yaml"

        result_path = generator.write_values(output_path, values)

        assert result_path.exists()
        with output_path.open() as f:
            loaded = yaml.safe_load(f)
        assert loaded == {"test": "value"}

    @pytest.mark.requirement("9b-FR-060")
    def test_write_values_creates_dirs(self, tmp_path: Path) -> None:
        """Test that write_values creates parent directories."""
        generator = HelmValuesGenerator()
        output_path = tmp_path / "nested" / "dir" / "values.yaml"

        generator.write_values(output_path, {"test": "value"})

        assert output_path.exists()

    @pytest.mark.requirement("9b-FR-060")
    def test_write_environment_values(self, tmp_path: Path) -> None:
        """Test writing values for multiple environments."""
        generator = HelmValuesGenerator(HelmValuesConfig.with_defaults())

        paths = generator.write_environment_values(
            tmp_path, ["dev", "staging"], filename_template="values-{env}.yaml"
        )

        assert len(paths) == 2
        assert (tmp_path / "values-dev.yaml").exists()
        assert (tmp_path / "values-staging.yaml").exists()

    @pytest.mark.requirement("9b-FR-060")
    def test_to_helm_set_args(self) -> None:
        """Test converting values to --set arguments."""
        generator = HelmValuesGenerator()
        values: dict[str, Any] = {
            "dagster": {"replicas": 2, "enabled": True},
            "name": "test",
        }

        args = generator.to_helm_set_args(values)

        assert "--set=dagster.replicas=2" in args
        assert "--set=dagster.enabled=true" in args
        assert "--set=name=test" in args


class TestGenerateValuesFromConfig:
    """Tests for generate_values_from_config function."""

    @pytest.mark.requirement("9b-FR-060")
    def test_basic_generation(self) -> None:
        """Test basic value generation."""
        config = HelmValuesConfig.with_defaults(environment="staging")
        values = generate_values_from_config(config)

        assert values["global"]["environment"] == "staging"

    @pytest.mark.requirement("9b-FR-060")
    def test_with_plugin_values(self) -> None:
        """Test generation with plugin values."""
        config = HelmValuesConfig.with_defaults()
        plugin_values = [
            {"dagster": {"enabled": True}},
            {"polaris": {"enabled": True}},
        ]
        values = generate_values_from_config(config, plugin_values=plugin_values)

        assert values["dagster"]["enabled"] is True
        assert values["polaris"]["enabled"] is True

    @pytest.mark.requirement("9b-FR-060")
    def test_with_user_overrides(self) -> None:
        """Test generation with user overrides."""
        config = HelmValuesConfig.with_defaults()
        overrides = {"custom": {"setting": "value"}}
        values = generate_values_from_config(config, user_overrides=overrides)

        assert values["custom"]["setting"] == "value"
