"""Unit tests for floe-secrets-k8s package __init__.py.

Tests for lazy imports and module-level attributes.

Task: Coverage improvement for 7a-identity-secrets
"""

from __future__ import annotations

import pytest


class TestLazyImports:
    """Tests for lazy import functionality."""

    @pytest.mark.requirement("CR-004")
    def test_import_k8s_secrets_plugin(self) -> None:
        """Test lazy import of K8sSecretsPlugin."""
        from floe_secrets_k8s import K8sSecretsPlugin

        assert K8sSecretsPlugin is not None
        assert hasattr(K8sSecretsPlugin, "get_secret")

    @pytest.mark.requirement("CR-004")
    def test_import_k8s_secrets_config(self) -> None:
        """Test lazy import of K8sSecretsConfig."""
        from floe_secrets_k8s import K8sSecretsConfig

        assert K8sSecretsConfig is not None

    @pytest.mark.requirement("CR-004")
    def test_invalid_attribute_raises_error(self) -> None:
        """Test that invalid attribute raises AttributeError."""
        import floe_secrets_k8s

        with pytest.raises(AttributeError) as exc_info:
            _ = floe_secrets_k8s.NonExistentAttribute  # type: ignore[attr-defined]

        assert "NonExistentAttribute" in str(exc_info.value)


class TestModuleAttributes:
    """Tests for module-level attributes."""

    @pytest.mark.requirement("CR-004")
    def test_version_attribute(self) -> None:
        """Test __version__ attribute."""
        import floe_secrets_k8s

        assert hasattr(floe_secrets_k8s, "__version__")
        assert isinstance(floe_secrets_k8s.__version__, str)

    @pytest.mark.requirement("CR-004")
    def test_all_attribute(self) -> None:
        """Test __all__ attribute contains expected exports."""
        import floe_secrets_k8s

        assert hasattr(floe_secrets_k8s, "__all__")
        expected = ["K8sSecretsPlugin", "K8sSecretsConfig"]
        for name in expected:
            assert name in floe_secrets_k8s.__all__
