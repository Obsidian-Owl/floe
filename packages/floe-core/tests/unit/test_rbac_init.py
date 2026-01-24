"""Unit tests for floe_core.rbac module exports.

Tests that all exports in __all__ are accessible via lazy imports.

Task: T042
User Story: US4 - RBAC Manifest Generation
Requirements: FR-002
"""

from __future__ import annotations

import pytest


class TestRBACModuleExports:
    """Unit tests for rbac module public API exports."""

    @pytest.mark.requirement("FR-002")
    def test_rbac_manifest_generator_import(self) -> None:
        """Test RBACManifestGenerator can be imported."""
        from floe_core.rbac import RBACManifestGenerator

        assert RBACManifestGenerator is not None
        assert hasattr(RBACManifestGenerator, "generate")

    @pytest.mark.requirement("FR-002")
    def test_generation_result_import(self) -> None:
        """Test GenerationResult can be imported."""
        from floe_core.rbac import GenerationResult

        assert GenerationResult is not None
        # Verify it's a dataclass with expected fields
        result = GenerationResult(success=True)
        assert result.success is True

    @pytest.mark.requirement("FR-002")
    def test_manifest_files_import(self) -> None:
        """Test MANIFEST_FILES constant can be imported."""
        from floe_core.rbac import MANIFEST_FILES

        assert MANIFEST_FILES is not None
        assert isinstance(MANIFEST_FILES, list | tuple)

    @pytest.mark.requirement("FR-002")
    def test_manifest_validation_error_import(self) -> None:
        """Test ManifestValidationError can be imported."""
        from floe_core.rbac import ManifestValidationError

        assert ManifestValidationError is not None
        assert issubclass(ManifestValidationError, Exception)

    @pytest.mark.requirement("FR-051")
    def test_validate_manifest_import(self) -> None:
        """Test validate_manifest function can be imported."""
        from floe_core.rbac import validate_manifest

        assert validate_manifest is not None
        assert callable(validate_manifest)

    @pytest.mark.requirement("FR-051")
    def test_validate_all_manifests_import(self) -> None:
        """Test validate_all_manifests function can be imported."""
        from floe_core.rbac import validate_all_manifests

        assert validate_all_manifests is not None
        assert callable(validate_all_manifests)

    @pytest.mark.requirement("FR-002")
    def test_aggregate_permissions_import(self) -> None:
        """Test aggregate_permissions function can be imported."""
        from floe_core.rbac import aggregate_permissions

        assert aggregate_permissions is not None
        assert callable(aggregate_permissions)

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_import(self) -> None:
        """Test write_manifests function can be imported."""
        from floe_core.rbac import write_manifests

        assert write_manifests is not None
        assert callable(write_manifests)

    @pytest.mark.requirement("FR-073")
    def test_validate_secret_references_import(self) -> None:
        """Test validate_secret_references function can be imported."""
        from floe_core.rbac import validate_secret_references

        assert validate_secret_references is not None
        assert callable(validate_secret_references)

    @pytest.mark.requirement("FR-072")
    def test_rbac_generation_audit_event_import(self) -> None:
        """Test RBACGenerationAuditEvent can be imported."""
        from floe_core.rbac import RBACGenerationAuditEvent

        assert RBACGenerationAuditEvent is not None

    @pytest.mark.requirement("FR-072")
    def test_rbac_generation_result_import(self) -> None:
        """Test RBACGenerationResult can be imported."""
        from floe_core.rbac import RBACGenerationResult

        assert RBACGenerationResult is not None

    @pytest.mark.requirement("FR-072")
    def test_log_rbac_event_import(self) -> None:
        """Test log_rbac_event function can be imported."""
        from floe_core.rbac import log_rbac_event

        assert log_rbac_event is not None
        assert callable(log_rbac_event)

    @pytest.mark.requirement("FR-002")
    def test_all_exports_are_accessible(self) -> None:
        """Test all items in __all__ are importable."""
        from floe_core import rbac

        for name in rbac.__all__:
            attr = getattr(rbac, name, None)
            assert attr is not None, f"Export {name} should be accessible"

    @pytest.mark.requirement("FR-002")
    def test_invalid_attribute_raises_error(self) -> None:
        """Test accessing invalid attribute raises AttributeError."""
        from floe_core import rbac

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = rbac.NonExistentAttribute  # type: ignore[attr-defined]
