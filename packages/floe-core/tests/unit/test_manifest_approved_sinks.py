"""Tests for PlatformManifest approved_sinks field (4G-FR-017).

This module tests the approved_sinks field on PlatformManifest and the
validate_sink_whitelist function. Tests are written TDD-style and will fail
until the implementation is complete.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.manifest import PlatformManifest
from floe_core.schemas.metadata import ManifestMetadata
from floe_core.schemas.plugins import (
    PluginsConfig,
    PluginSelection,
    SinkWhitelistError,
    validate_sink_whitelist,
)


class TestManifestApprovedSinks:
    """Tests for approved_sinks field on PlatformManifest."""

    @pytest.mark.requirement("4G-FR-017")
    def test_approved_sinks_field_on_manifest(self) -> None:
        """Test that enterprise-scope manifest can have approved_sinks list.

        Validates that the approved_sinks field is correctly set on an
        enterprise-scope PlatformManifest and can contain sink type identifiers.
        """
        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata=ManifestMetadata(
                name="enterprise-platform",
                version="1.0.0",
                owner="platform@acme.com",
            ),
            scope="enterprise",
            plugins=PluginsConfig(compute=PluginSelection(type="duckdb")),
            approved_sinks=["rest_api", "sql_database"],
        )

        assert manifest.approved_sinks == ["rest_api", "sql_database"]

    @pytest.mark.requirement("4G-FR-017")
    def test_approved_sinks_none_allows_all(self) -> None:
        """Test that approved_sinks=None maintains backwards compatibility.

        Validates that when approved_sinks is not specified (defaults to None),
        the manifest is valid and allows all sink types (no restrictions).
        """
        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata=ManifestMetadata(
                name="enterprise-platform",
                version="1.0.0",
                owner="platform@acme.com",
            ),
            scope="enterprise",
            plugins=PluginsConfig(compute=PluginSelection(type="duckdb")),
        )

        assert manifest.approved_sinks is None

    @pytest.mark.requirement("4G-FR-017")
    def test_approved_sinks_only_valid_for_enterprise_scope(self) -> None:
        """Test that approved_sinks validates successfully for enterprise scope.

        Validates that an enterprise-scope manifest with approved_sinks is valid.
        """
        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata=ManifestMetadata(
                name="enterprise-platform",
                version="1.0.0",
                owner="platform@acme.com",
            ),
            scope="enterprise",
            plugins=PluginsConfig(compute=PluginSelection(type="duckdb")),
            approved_sinks=["rest_api"],
        )

        assert manifest.scope == "enterprise"
        assert manifest.approved_sinks == ["rest_api"]

    @pytest.mark.requirement("4G-FR-017")
    def test_approved_sinks_rejected_for_domain_scope(self) -> None:
        """Test that approved_sinks is rejected for domain-scope manifest.

        Validates that setting approved_sinks on a domain-scope manifest
        raises ValidationError with appropriate message.
        """
        with pytest.raises(
            ValidationError,
            match=r"approved_sinks.*only valid for scope='enterprise'",
        ):
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata=ManifestMetadata(
                    name="domain-manifest",
                    version="1.0.0",
                    owner="team@acme.com",
                ),
                scope="domain",
                parent_manifest="oci://registry.example.com/enterprise-manifest:1.0.0",
                plugins=PluginsConfig(compute=PluginSelection(type="duckdb")),
                approved_sinks=["rest_api"],
            )

    @pytest.mark.requirement("4G-FR-017")
    def test_approved_sinks_rejected_for_no_scope(self) -> None:
        """Test that approved_sinks is rejected for 2-tier manifest.

        Validates that setting approved_sinks on a manifest without scope
        (2-tier config) raises ValidationError with appropriate message.
        """
        with pytest.raises(
            ValidationError,
            match=r"approved_sinks.*only valid for scope='enterprise'",
        ):
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata=ManifestMetadata(
                    name="simple-platform",
                    version="1.0.0",
                    owner="team@acme.com",
                ),
                plugins=PluginsConfig(compute=PluginSelection(type="duckdb")),
                approved_sinks=["rest_api"],
            )


class TestSinkWhitelistValidation:
    """Tests for validate_sink_whitelist function."""

    @pytest.mark.requirement("4G-FR-017")
    def test_sink_whitelist_error_raised_for_unapproved(self) -> None:
        """Test that validate_sink_whitelist raises for unapproved sink.

        Validates that attempting to use a sink type not in the approved list
        raises SinkWhitelistError.
        """
        with pytest.raises(SinkWhitelistError):
            validate_sink_whitelist("kafka", ["rest_api", "sql_database"])

    @pytest.mark.requirement("4G-FR-017")
    def test_sink_whitelist_error_not_raised_for_approved(self) -> None:
        """Test that validate_sink_whitelist passes for approved sink.

        Validates that using a sink type that is in the approved list
        does not raise any exception.
        """
        # Should not raise
        validate_sink_whitelist("rest_api", ["rest_api", "sql_database"])

    @pytest.mark.requirement("4G-FR-017")
    def test_validate_sink_whitelist_with_empty_list(self) -> None:
        """Test that validate_sink_whitelist raises for empty whitelist.

        Validates that an empty approved_sinks list blocks all sink types.
        """
        with pytest.raises(SinkWhitelistError):
            validate_sink_whitelist("rest_api", [])

    @pytest.mark.requirement("4G-FR-017")
    def test_sink_whitelist_error_attributes(self) -> None:
        """Test that SinkWhitelistError contains expected attributes.

        Validates that the exception has sink_type and approved_sinks attributes
        with correct values for debugging and error reporting.
        """
        try:
            validate_sink_whitelist("kafka", ["rest_api", "sql_database"])
            pytest.fail("Expected SinkWhitelistError to be raised")
        except SinkWhitelistError as e:
            assert e.sink_type == "kafka"
            assert e.approved_sinks == ["rest_api", "sql_database"]
