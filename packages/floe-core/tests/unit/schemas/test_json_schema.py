"""Unit tests for JSON Schema export functionality.

Tests for JSON Schema generation and IDE autocomplete support (US4) including:
- JSON Schema export from Pydantic models
- Schema validity and structure
- IDE autocomplete compatibility

Task: T047
Requirements: FR-009
"""

from __future__ import annotations

import json
from typing import Any

import pytest


class TestJsonSchemaExport:
    """Tests for JSON Schema export (T047)."""

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_returns_valid_json(self) -> None:
        """Test that export_json_schema returns valid JSON.

        Given the PlatformManifest model,
        When exporting JSON Schema,
        Then the output is valid JSON that can be parsed.
        """
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()

        # Should be a valid dict (JSON-serializable)
        assert isinstance(schema, dict)
        # Should be serializable to JSON string
        json_str = json.dumps(schema, indent=2)
        assert isinstance(json_str, str)
        # Should be parseable back to dict
        parsed = json.loads(json_str)
        assert parsed == schema

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_has_schema_id(self) -> None:
        """Test that exported schema has $schema and $id fields.

        Given the PlatformManifest model,
        When exporting JSON Schema,
        Then the output includes $schema (JSON Schema version) and $id (schema identifier).
        """
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()

        # Must have $schema field pointing to JSON Schema draft
        assert "$schema" in schema
        assert "json-schema.org" in schema["$schema"]

        # Must have $id field for schema identification
        assert "$id" in schema
        assert "manifest" in schema["$id"].lower()

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_has_title_and_description(self) -> None:
        """Test that exported schema has title and description."""
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()

        assert "title" in schema
        assert "description" in schema
        assert "PlatformManifest" in schema["title"]

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_includes_required_fields(self) -> None:
        """Test that exported schema includes required fields list.

        Given the PlatformManifest model has required fields (apiVersion, kind, metadata, plugins),
        When exporting JSON Schema,
        Then the 'required' array includes these fields (using alias names).
        """
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()

        assert "required" in schema
        required = schema["required"]
        # Note: JSON Schema uses alias (apiVersion) not field name (api_version)
        assert "apiVersion" in required
        assert "kind" in required
        assert "metadata" in required
        assert "plugins" in required

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_includes_properties(self) -> None:
        """Test that exported schema includes all manifest properties."""
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()

        assert "properties" in schema
        props = schema["properties"]

        # Core fields (Note: api_version uses alias apiVersion in JSON Schema)
        assert "apiVersion" in props
        assert "kind" in props
        assert "metadata" in props
        assert "plugins" in props

        # Optional fields
        assert "scope" in props
        assert "governance" in props
        assert "parent_manifest" in props

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_api_version_enum(self) -> None:
        """Test that apiVersion field has enum constraint."""
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()
        # Note: JSON Schema uses alias (apiVersion)
        api_version = schema["properties"]["apiVersion"]

        # Should have const or enum for "floe.dev/v1"
        assert "const" in api_version or "enum" in api_version
        if "const" in api_version:
            assert api_version["const"] == "floe.dev/v1"
        else:
            assert "floe.dev/v1" in api_version["enum"]

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_scope_enum(self) -> None:
        """Test that scope field has enum constraint for valid values."""
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()

        # Scope should be in properties (may be nested in anyOf/oneOf due to Optional)
        props = schema["properties"]
        assert "scope" in props

        # The scope should allow enterprise, domain, or null
        scope_def = props["scope"]
        # Check that enterprise and domain are valid options somewhere in the definition
        scope_str = json.dumps(scope_def)
        assert "enterprise" in scope_str
        assert "domain" in scope_str

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_has_definitions(self) -> None:
        """Test that exported schema includes definitions for nested models."""
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()

        # Pydantic v2 uses $defs for nested model definitions
        assert "$defs" in schema or "definitions" in schema

        defs = schema.get("$defs", schema.get("definitions", {}))
        # Should have definitions for nested models
        assert len(defs) > 0

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_metadata_nested(self) -> None:
        """Test that metadata field references nested ManifestMetadata schema."""
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()
        metadata = schema["properties"]["metadata"]

        # Should be a reference or have nested properties
        assert "$ref" in metadata or "properties" in metadata

    @pytest.mark.requirement("001-FR-009")
    def test_export_json_schema_to_file(self) -> None:
        """Test that schema can be exported to a file path."""
        import tempfile
        from pathlib import Path

        from floe_core.schemas.json_schema import export_json_schema_to_file

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "manifest.schema.json"

            export_json_schema_to_file(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            schema = json.loads(content)
            assert "$schema" in schema
            assert "properties" in schema


class TestJsonSchemaIdeCompatibility:
    """Tests for IDE compatibility of JSON Schema."""

    @pytest.mark.requirement("001-FR-009")
    def test_schema_validates_valid_manifest(self) -> None:
        """Test that valid manifests pass JSON Schema validation.

        Given a valid manifest YAML/JSON,
        When validating against the exported schema,
        Then validation passes.
        """
        from floe_core.schemas.json_schema import export_json_schema, validate_against_schema

        schema = export_json_schema()

        # Note: JSON Schema expects apiVersion (alias) not api_version
        valid_manifest: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "test-platform",
                "version": "1.0.0",
                "owner": "team@example.com",
            },
            "plugins": {
                "compute": {"type": "duckdb"},
            },
        }

        # Should not raise
        validate_against_schema(valid_manifest, schema)

    @pytest.mark.requirement("001-FR-009")
    def test_schema_rejects_invalid_api_version(self) -> None:
        """Test that schema rejects invalid apiVersion."""
        from floe_core.schemas.json_schema import (
            JsonSchemaValidationError,
            export_json_schema,
            validate_against_schema,
        )

        schema = export_json_schema()

        # Note: JSON Schema expects apiVersion (alias)
        invalid_manifest: dict[str, Any] = {
            "apiVersion": "invalid/v99",  # Invalid
            "kind": "Manifest",
            "metadata": {
                "name": "test",
                "version": "1.0.0",
                "owner": "team@example.com",
            },
            "plugins": {},
        }

        with pytest.raises(JsonSchemaValidationError) as exc_info:
            validate_against_schema(invalid_manifest, schema)

        # Error should reference apiVersion
        error_str = str(exc_info.value).lower()
        assert "apiversion" in error_str or "api_version" in error_str

    @pytest.mark.requirement("001-FR-009")
    def test_schema_rejects_missing_required_field(self) -> None:
        """Test that schema rejects manifest missing required fields."""
        from floe_core.schemas.json_schema import (
            JsonSchemaValidationError,
            export_json_schema,
            validate_against_schema,
        )

        schema = export_json_schema()

        # Missing 'metadata' field (Note: JSON Schema expects apiVersion)
        invalid_manifest: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "Manifest",
            "plugins": {},
        }

        with pytest.raises(JsonSchemaValidationError) as exc_info:
            validate_against_schema(invalid_manifest, schema)

        error_msg = str(exc_info.value).lower()
        assert "metadata" in error_msg or "required" in error_msg

    @pytest.mark.requirement("001-FR-009")
    def test_schema_field_descriptions_present(self) -> None:
        """Test that schema includes field descriptions for IDE tooltips."""
        from floe_core.schemas.json_schema import export_json_schema

        schema = export_json_schema()
        props = schema["properties"]

        # Key fields should have descriptions (Note: api_version uses alias apiVersion)
        for field_name in ["apiVersion", "kind", "metadata", "plugins", "scope"]:
            assert field_name in props, f"Field {field_name} not found in properties"
            field_def = props[field_name]
            # Description might be in the field or in a $ref target
            has_description = "description" in field_def
            has_ref = "$ref" in field_def
            assert has_description or has_ref, f"Field {field_name} should have description or $ref"
