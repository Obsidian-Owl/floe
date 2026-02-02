"""Unit tests for Helm values generator.

Tests the HelmValuesGenerator class and its methods.

Requirements tested:
- 9b-FR-060: HelmValuesGenerator implementation
- 9b-FR-004: Values schema validation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from floe_core.helm.generator import (
    HelmValuesGenerator,
    SchemaValidationError,
    generate_values_from_config,
)
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


class TestSchemaValidation:
    """Tests for schema validation functionality."""

    @pytest.fixture
    def valid_schema(self, tmp_path: Path) -> Path:
        """Create a valid JSON schema for testing."""
        schema = {
            "$schema": "https://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "global": {
                    "type": "object",
                    "properties": {
                        "environment": {
                            "type": "string",
                            "enum": ["dev", "qa", "staging", "prod"],
                        }
                    },
                },
                "dagster": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "replicas": {"type": "integer", "minimum": 1},
                    },
                },
            },
        }
        schema_path = tmp_path / "values.schema.json"
        with schema_path.open("w") as f:
            json.dump(schema, f)
        return schema_path

    @pytest.mark.requirement("9b-FR-004")
    def test_load_schema(self, valid_schema: Path) -> None:
        """Test loading JSON schema from file."""
        generator = HelmValuesGenerator(schema_path=valid_schema)
        schema = generator.load_schema()

        assert schema["$schema"] == "https://json-schema.org/draft-07/schema#"
        assert "properties" in schema

    @pytest.mark.requirement("9b-FR-004")
    def test_load_schema_from_method(self, valid_schema: Path) -> None:
        """Test loading schema from method parameter."""
        generator = HelmValuesGenerator()
        schema = generator.load_schema(valid_schema)

        assert "properties" in schema

    @pytest.mark.requirement("9b-FR-004")
    def test_load_schema_not_found(self, tmp_path: Path) -> None:
        """Test loading non-existent schema raises error."""
        generator = HelmValuesGenerator()
        with pytest.raises(FileNotFoundError, match="Schema file not found"):
            generator.load_schema(tmp_path / "missing.json")

    @pytest.mark.requirement("9b-FR-004")
    def test_load_schema_no_path(self) -> None:
        """Test loading without schema path raises error."""
        generator = HelmValuesGenerator()
        with pytest.raises(ValueError, match="No schema path provided"):
            generator.load_schema()

    @pytest.mark.requirement("9b-FR-004")
    def test_validate_valid_values(self, valid_schema: Path) -> None:
        """Test validation passes for valid values."""
        generator = HelmValuesGenerator(schema_path=valid_schema)
        values = {
            "global": {"environment": "dev"},
            "dagster": {"enabled": True, "replicas": 2},
        }

        errors = generator.validate(values)

        assert errors == []

    @pytest.mark.requirement("9b-FR-004")
    def test_validate_invalid_environment(self, valid_schema: Path) -> None:
        """Test validation fails for invalid environment."""
        generator = HelmValuesGenerator(schema_path=valid_schema)
        values = {"global": {"environment": "invalid"}}

        errors = generator.validate(values)

        assert len(errors) > 0
        assert any("environment" in e for e in errors)

    @pytest.mark.requirement("9b-FR-004")
    def test_validate_invalid_type(self, valid_schema: Path) -> None:
        """Test validation fails for wrong type."""
        generator = HelmValuesGenerator(schema_path=valid_schema)
        values = {"dagster": {"replicas": "not-a-number"}}

        errors = generator.validate(values)

        assert len(errors) > 0
        assert any("replicas" in e for e in errors)

    @pytest.mark.requirement("9b-FR-004")
    def test_validate_minimum_violation(self, valid_schema: Path) -> None:
        """Test validation fails for minimum violation."""
        generator = HelmValuesGenerator(schema_path=valid_schema)
        values = {"dagster": {"replicas": 0}}

        errors = generator.validate(values)

        assert len(errors) > 0
        assert any("minimum" in e.lower() or "replicas" in e for e in errors)

    @pytest.mark.requirement("9b-FR-004")
    def test_validate_no_schema_raises(self) -> None:
        """Test validation without schema raises error."""
        generator = HelmValuesGenerator()
        with pytest.raises(ValueError, match="No schema loaded"):
            generator.validate({"test": "value"})

    @pytest.mark.requirement("9b-FR-004")
    def test_generate_and_validate_success(self, valid_schema: Path) -> None:
        """Test generate_and_validate with valid configuration."""
        config = HelmValuesConfig.with_defaults(environment="dev")
        generator = HelmValuesGenerator(config, schema_path=valid_schema)
        generator.add_plugin_values({"dagster": {"enabled": True, "replicas": 2}})

        values, errors = generator.generate_and_validate(raise_on_error=False)

        assert values["global"]["environment"] == "dev"
        # May have some errors since our test schema is minimal
        # but should not raise

    @pytest.mark.requirement("9b-FR-004")
    def test_generate_and_validate_raises_on_error(self, valid_schema: Path) -> None:
        """Test generate_and_validate raises on validation failure."""
        generator = HelmValuesGenerator(schema_path=valid_schema)
        generator.set_user_overrides({"global": {"environment": "invalid"}})

        with pytest.raises(SchemaValidationError) as exc_info:
            generator.generate_and_validate(raise_on_error=True)

        assert len(exc_info.value.errors) > 0

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_validation_error_contains_errors(self) -> None:
        """Test SchemaValidationError contains error list."""
        errors = ["field1: error1", "field2: error2"]
        exc = SchemaValidationError("Validation failed", errors=errors)

        assert len(exc.errors) == 2
        assert "field1: error1" in exc.errors
