"""Contract tests for egress schema stability (Epic 4G)."""

from __future__ import annotations

import pytest
from floe_core.schemas.floe_spec import (
    DestinationConfig,
    FloeMetadata,
    FloeSpec,
    TransformSpec,
)
from floe_core.schemas.manifest import PlatformManifest
from floe_core.schemas.plugins import SinkWhitelistError


class TestEgressSchemaContract:
    """Contract tests for egress schema stability."""

    @pytest.mark.requirement("4G-SC-004")
    def test_destination_config_schema_matches_contract(self) -> None:
        """Test DestinationConfig schema matches expected contract fields.

        This test ensures schema stability for DestinationConfig.
        Any changes to these fields require a major version bump.
        """
        schema = DestinationConfig.model_json_schema()
        props = schema["properties"]

        # Verify expected fields exist
        assert "name" in props
        assert "sink_type" in props
        assert "connection_secret_ref" in props
        assert "source_table" in props
        assert "config" in props
        assert "field_mapping" in props
        assert "batch_size" in props

        # Verify required fields
        required = schema.get("required", [])
        assert set(required) == {"name", "sink_type", "connection_secret_ref"}

    @pytest.mark.requirement("4G-SC-004")
    def test_floe_spec_json_schema_includes_destinations(self) -> None:
        """Test FloeSpec schema includes destinations field.

        This test ensures FloeSpec schema properly exposes the destinations
        field for IDE autocomplete and JSON schema validation.
        """
        schema = FloeSpec.model_json_schema()
        props = schema["properties"]

        # Verify destinations field exists
        assert "destinations" in props

        # Verify destinations is optional (not required)
        required = schema.get("required", [])
        assert "destinations" not in required

    @pytest.mark.requirement("4G-SC-004")
    def test_backwards_compat_existing_fixtures_validate(self) -> None:
        """Test FloeSpec validates without destinations field.

        This test proves backwards compatibility - existing floe.yaml files
        that don't have destinations still validate successfully.
        """
        # Create minimal valid FloeSpec (pre-4G format, no destinations)
        minimal_spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="test-pipeline",
                version="1.0.0",
            ),
            transforms=[TransformSpec(name="stg_test")],
        )

        # Should validate successfully
        assert minimal_spec.metadata.name == "test-pipeline"
        assert minimal_spec.metadata.version == "1.0.0"
        # destinations should be None (not provided)
        assert minimal_spec.destinations is None

    @pytest.mark.requirement("4G-SC-005")
    def test_manifest_json_schema_includes_approved_sinks(self) -> None:
        """Test PlatformManifest schema includes approved_sinks field.

        This test ensures PlatformManifest schema properly exposes the
        approved_sinks field for IDE autocomplete and JSON schema validation.
        The field should be optional (not required) for backwards compatibility.
        """
        schema = PlatformManifest.model_json_schema()
        props = schema["properties"]

        # Verify approved_sinks field exists
        assert "approved_sinks" in props

        # Verify approved_sinks is optional (not required)
        required = schema.get("required", [])
        assert "approved_sinks" not in required

    @pytest.mark.requirement("4G-SC-005")
    def test_sink_whitelist_error_importable(self) -> None:
        """Test SinkWhitelistError is importable and is an Exception.

        This test ensures the SinkWhitelistError exception is properly
        exposed in the public API for error handling in egress validation.
        """
        # Should be importable (already imported above)
        assert SinkWhitelistError is not None

        # Should be an Exception subclass
        assert issubclass(SinkWhitelistError, Exception)
