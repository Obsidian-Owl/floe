"""Integration tests for Helm values schema validation.

Tests that values files conform to JSON Schema specifications.

Requirements tested:
- 9b-FR-004: Values schema validation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

# Try to import jsonschema, skip tests if not available
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


CHARTS_DIR = Path(__file__).parent.parent.parent.parent / "charts"


@pytest.fixture
def floe_platform_schema() -> dict[str, Any]:
    """Load floe-platform values schema."""
    schema_path = CHARTS_DIR / "floe-platform" / "values.schema.json"
    if not schema_path.exists():
        pytest.skip(f"Schema not found: {schema_path}")
    with schema_path.open() as f:
        return json.load(f)


@pytest.fixture
def floe_jobs_schema() -> dict[str, Any]:
    """Load floe-jobs values schema."""
    schema_path = CHARTS_DIR / "floe-jobs" / "values.schema.json"
    if not schema_path.exists():
        pytest.skip(f"Schema not found: {schema_path}")
    with schema_path.open() as f:
        return json.load(f)


def load_values_file(chart: str, filename: str = "values.yaml") -> dict[str, Any]:
    """Load a values file from a chart directory."""
    values_path = CHARTS_DIR / chart / filename
    if not values_path.exists():
        pytest.skip(f"Values file not found: {values_path}")
    with values_path.open() as f:
        return yaml.safe_load(f) or {}


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFloePlatformSchema:
    """Tests for floe-platform values schema validation."""

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_is_valid_json_schema(
        self, floe_platform_schema: dict[str, Any]
    ) -> None:
        """Test that the schema itself is a valid JSON Schema."""
        # This will raise if schema is invalid
        jsonschema.Draft7Validator.check_schema(floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_default_values_conform_to_schema(
        self, floe_platform_schema: dict[str, Any]
    ) -> None:
        """Test that default values.yaml conforms to schema."""
        values = load_values_file("floe-platform")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_dev_values_conform_to_schema(
        self, floe_platform_schema: dict[str, Any]
    ) -> None:
        """Test that values-dev.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-dev.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_staging_values_conform_to_schema(
        self, floe_platform_schema: dict[str, Any]
    ) -> None:
        """Test that values-staging.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-staging.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_prod_values_conform_to_schema(
        self, floe_platform_schema: dict[str, Any]
    ) -> None:
        """Test that values-prod.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-prod.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_invalid_environment_rejected(
        self, floe_platform_schema: dict[str, Any]
    ) -> None:
        """Test that invalid environment value is rejected."""
        invalid_values = {"global": {"environment": "invalid"}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_has_required_sections(
        self, floe_platform_schema: dict[str, Any]
    ) -> None:
        """Test that schema defines expected top-level sections."""
        properties = floe_platform_schema.get("properties", {})
        expected = [
            "global",
            "namespace",
            "clusterMapping",
            "dagster",
            "postgresql",
            "polaris",
            "minio",
            "ingress",
        ]
        for section in expected:
            assert section in properties, f"Missing schema section: {section}"


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFloeJobsSchema:
    """Tests for floe-jobs values schema validation."""

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_is_valid_json_schema(
        self, floe_jobs_schema: dict[str, Any]
    ) -> None:
        """Test that the schema itself is a valid JSON Schema."""
        jsonschema.Draft7Validator.check_schema(floe_jobs_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_default_values_conform_to_schema(
        self, floe_jobs_schema: dict[str, Any]
    ) -> None:
        """Test that default values.yaml conforms to schema."""
        values = load_values_file("floe-jobs")
        jsonschema.validate(values, floe_jobs_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_has_required_sections(
        self, floe_jobs_schema: dict[str, Any]
    ) -> None:
        """Test that schema defines expected top-level sections."""
        properties = floe_jobs_schema.get("properties", {})
        expected = ["global", "platform", "dbt", "ingestion", "custom", "resources"]
        for section in expected:
            assert section in properties, f"Missing schema section: {section}"

    @pytest.mark.requirement("9b-FR-004")
    def test_invalid_environment_rejected(
        self, floe_jobs_schema: dict[str, Any]
    ) -> None:
        """Test that invalid environment value is rejected."""
        invalid_values = {"global": {"environment": "invalid"}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_values, floe_jobs_schema)
