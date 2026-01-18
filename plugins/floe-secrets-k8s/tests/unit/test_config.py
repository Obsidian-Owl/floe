"""Unit tests for K8sSecretsConfig validation.

Tests Pydantic configuration model for K8sSecretsPlugin.

Implements:
    - T018: Unit test for K8sSecretsConfig validation
    - FR-011: Namespace-scoped secret access configuration
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from floe_secrets_k8s.config import K8sSecretsConfig


class TestK8sSecretsConfigDefaults:
    """Test default configuration values."""

    @pytest.mark.requirement("7A-FR-011")
    def test_default_namespace(self) -> None:
        """Test default namespace is 'floe-jobs'."""
        config = K8sSecretsConfig()
        assert config.namespace == "floe-jobs"

    @pytest.mark.requirement("7A-FR-013")
    def test_default_kubeconfig_path_is_none(self) -> None:
        """Test default kubeconfig_path is None (in-cluster mode)."""
        config = K8sSecretsConfig()
        assert config.kubeconfig_path is None

    @pytest.mark.requirement("7A-FR-013")
    def test_default_context_is_none(self) -> None:
        """Test default context is None (current context)."""
        config = K8sSecretsConfig()
        assert config.context is None

    @pytest.mark.requirement("7A-FR-010")
    def test_default_labels(self) -> None:
        """Test default labels include managed-by: floe."""
        config = K8sSecretsConfig()
        assert config.labels == {"managed-by": "floe"}

    @pytest.mark.requirement("7A-FR-010")
    def test_default_secret_prefix(self) -> None:
        """Test default secret_prefix is 'floe-'."""
        config = K8sSecretsConfig()
        assert config.secret_prefix == "floe-"


class TestK8sSecretsConfigNamespace:
    """Test namespace validation."""

    @pytest.mark.requirement("7A-FR-011")
    def test_valid_namespace(self) -> None:
        """Test valid namespace names are accepted."""
        valid_names = [
            "floe-jobs",
            "production",
            "staging",
            "default",
            "my-namespace",
            "namespace123",
            "a",  # Single character
        ]
        for name in valid_names:
            config = K8sSecretsConfig(namespace=name)
            assert config.namespace == name

    @pytest.mark.requirement("7A-FR-011")
    def test_invalid_namespace_uppercase(self) -> None:
        """Test uppercase namespace names are rejected."""
        with pytest.raises(ValidationError, match="namespace"):
            K8sSecretsConfig(namespace="MyNamespace")

    @pytest.mark.requirement("7A-FR-011")
    def test_invalid_namespace_special_chars(self) -> None:
        """Test namespace with special characters is rejected."""
        with pytest.raises(ValidationError, match="namespace"):
            K8sSecretsConfig(namespace="my_namespace")

    @pytest.mark.requirement("7A-FR-011")
    def test_invalid_namespace_empty(self) -> None:
        """Test empty namespace is rejected."""
        with pytest.raises(ValidationError, match="namespace"):
            K8sSecretsConfig(namespace="")

    @pytest.mark.requirement("7A-FR-011")
    def test_invalid_namespace_too_long(self) -> None:
        """Test namespace exceeding 63 characters is rejected."""
        long_name = "a" * 64
        with pytest.raises(ValidationError, match="namespace"):
            K8sSecretsConfig(namespace=long_name)

    @pytest.mark.requirement("7A-FR-011")
    def test_invalid_namespace_starts_with_hyphen(self) -> None:
        """Test namespace starting with hyphen is rejected."""
        with pytest.raises(ValidationError, match="namespace"):
            K8sSecretsConfig(namespace="-invalid")

    @pytest.mark.requirement("7A-FR-011")
    def test_invalid_namespace_ends_with_hyphen(self) -> None:
        """Test namespace ending with hyphen is rejected."""
        with pytest.raises(ValidationError, match="namespace"):
            K8sSecretsConfig(namespace="invalid-")


class TestK8sSecretsConfigKubeconfig:
    """Test kubeconfig path handling."""

    @pytest.mark.requirement("7A-FR-013")
    def test_kubeconfig_path_expansion(self, tmp_path: Path) -> None:
        """Test kubeconfig path with tilde is expanded."""
        config = K8sSecretsConfig(kubeconfig_path="~/.kube/config")
        assert config.kubeconfig_path is not None
        assert not config.kubeconfig_path.startswith("~")
        assert "/.kube/config" in config.kubeconfig_path

    @pytest.mark.requirement("7A-FR-013")
    def test_kubeconfig_with_context(self) -> None:
        """Test kubeconfig with specific context."""
        config = K8sSecretsConfig(
            kubeconfig_path="~/.kube/config",
            context="my-cluster",
        )
        assert config.context == "my-cluster"

    @pytest.mark.requirement("7A-FR-013")
    def test_explicit_kubeconfig_path(self) -> None:
        """Test explicit kubeconfig path without expansion."""
        config = K8sSecretsConfig(kubeconfig_path="/etc/kubernetes/admin.conf")
        assert config.kubeconfig_path == "/etc/kubernetes/admin.conf"


class TestK8sSecretsConfigLabels:
    """Test labels validation."""

    @pytest.mark.requirement("7A-FR-010")
    def test_custom_labels(self) -> None:
        """Test custom labels are accepted."""
        labels = {"managed-by": "floe", "environment": "production", "team": "data"}
        config = K8sSecretsConfig(labels=labels)
        assert config.labels == labels

    @pytest.mark.requirement("7A-FR-010")
    def test_label_key_too_long(self) -> None:
        """Test label key exceeding max length is rejected."""
        long_key = "a" * 254  # Max is 253
        with pytest.raises(ValidationError, match="Label key too long"):
            K8sSecretsConfig(labels={long_key: "value"})

    @pytest.mark.requirement("7A-FR-010")
    def test_label_value_too_long(self) -> None:
        """Test label value exceeding max length is rejected."""
        long_value = "a" * 64  # Max is 63
        with pytest.raises(ValidationError, match="Label value too long"):
            K8sSecretsConfig(labels={"key": long_value})

    @pytest.mark.requirement("7A-FR-010")
    def test_empty_labels(self) -> None:
        """Test empty labels dictionary is accepted."""
        config = K8sSecretsConfig(labels={})
        assert config.labels == {}


class TestK8sSecretsConfigSecretPrefix:
    """Test secret prefix configuration."""

    @pytest.mark.requirement("7A-FR-010")
    def test_custom_secret_prefix(self) -> None:
        """Test custom secret prefix is accepted."""
        config = K8sSecretsConfig(secret_prefix="myapp-secrets-")
        assert config.secret_prefix == "myapp-secrets-"

    @pytest.mark.requirement("7A-FR-010")
    def test_empty_secret_prefix(self) -> None:
        """Test empty secret prefix is accepted."""
        config = K8sSecretsConfig(secret_prefix="")
        assert config.secret_prefix == ""

    @pytest.mark.requirement("7A-FR-010")
    def test_secret_prefix_too_long(self) -> None:
        """Test secret prefix exceeding max length is rejected."""
        long_prefix = "a" * 51  # Max is 50
        with pytest.raises(ValidationError, match="secret_prefix"):
            K8sSecretsConfig(secret_prefix=long_prefix)


class TestK8sSecretsConfigImmutability:
    """Test configuration immutability (frozen=True)."""

    @pytest.mark.requirement("CR-003")
    def test_config_is_frozen(self) -> None:
        """Test config is immutable after creation."""
        config = K8sSecretsConfig()
        with pytest.raises(ValidationError):
            config.namespace = "new-namespace"  # type: ignore[misc]

    @pytest.mark.requirement("CR-003")
    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError, match="extra"):
            K8sSecretsConfig(unknown_field="value")  # type: ignore[call-arg]


class TestK8sSecretsConfigJsonSchema:
    """Test JSON schema generation."""

    @pytest.mark.requirement("CR-003")
    def test_json_schema_generation(self) -> None:
        """Test JSON schema can be generated."""
        schema: dict[str, Any] = K8sSecretsConfig.model_json_schema()
        assert "properties" in schema
        assert "namespace" in schema["properties"]
        assert "kubeconfig_path" in schema["properties"]
        assert "context" in schema["properties"]
        assert "labels" in schema["properties"]
        assert "secret_prefix" in schema["properties"]

    @pytest.mark.requirement("CR-003")
    def test_json_schema_examples(self) -> None:
        """Test JSON schema includes examples."""
        schema: dict[str, Any] = K8sSecretsConfig.model_json_schema()
        assert "examples" in schema
