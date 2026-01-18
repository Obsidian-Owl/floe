"""Unit tests for generate_pod_env_spec().

Tests the K8s pod spec generation for secret injection.

Implements:
    - T020: Unit test for generate_pod_env_spec()
    - FR-012: K8sSecretsPlugin MUST generate pod spec fragments with envFrom
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_secrets_k8s.plugin import K8sSecretsPlugin


class TestGeneratePodEnvSpec:
    """Test generate_pod_env_spec method."""

    @pytest.mark.requirement("7A-FR-012")
    def test_generate_pod_env_spec_basic(self) -> None:
        """Test generate_pod_env_spec returns correct structure."""
        plugin = K8sSecretsPlugin()

        result: dict[str, Any] = plugin.generate_pod_env_spec("db-creds")

        assert result == {"envFrom": [{"secretRef": {"name": "db-creds"}}]}

    @pytest.mark.requirement("7A-FR-012")
    def test_generate_pod_env_spec_has_envfrom(self) -> None:
        """Test result contains envFrom key."""
        plugin = K8sSecretsPlugin()

        result: dict[str, Any] = plugin.generate_pod_env_spec("my-secret")

        assert "envFrom" in result

    @pytest.mark.requirement("7A-FR-012")
    def test_generate_pod_env_spec_has_secret_ref(self) -> None:
        """Test result has secretRef structure."""
        plugin = K8sSecretsPlugin()

        result: dict[str, Any] = plugin.generate_pod_env_spec("my-secret")

        assert len(result["envFrom"]) == 1
        assert "secretRef" in result["envFrom"][0]

    @pytest.mark.requirement("7A-FR-012")
    def test_generate_pod_env_spec_has_name(self) -> None:
        """Test secretRef contains correct secret name."""
        plugin = K8sSecretsPlugin()
        secret_name = "polaris-credentials"

        result: dict[str, Any] = plugin.generate_pod_env_spec(secret_name)

        assert result["envFrom"][0]["secretRef"]["name"] == secret_name

    @pytest.mark.requirement("7A-FR-012")
    def test_generate_pod_env_spec_different_names(self) -> None:
        """Test generate_pod_env_spec works with various secret names."""
        plugin = K8sSecretsPlugin()
        secret_names = [
            "db-credentials",
            "api-key",
            "oauth-tokens",
            "my-app-secrets",
        ]

        for name in secret_names:
            result: dict[str, Any] = plugin.generate_pod_env_spec(name)
            assert result["envFrom"][0]["secretRef"]["name"] == name

    @pytest.mark.requirement("7A-FR-012")
    def test_generate_pod_env_spec_k8s_compatible(self) -> None:
        """Test generated spec is valid K8s pod spec fragment.

        The generated spec should be directly usable in a K8s pod definition:
        ```yaml
        spec:
          containers:
            - name: my-container
              envFrom:
                - secretRef:
                    name: db-creds
        ```
        """
        plugin = K8sSecretsPlugin()

        result: dict[str, Any] = plugin.generate_pod_env_spec("db-creds")

        # Verify structure matches K8s API
        assert isinstance(result, dict)
        assert isinstance(result.get("envFrom"), list)
        assert len(result["envFrom"]) == 1

        secret_ref_item = result["envFrom"][0]
        assert isinstance(secret_ref_item, dict)
        assert "secretRef" in secret_ref_item

        secret_ref = secret_ref_item["secretRef"]
        assert isinstance(secret_ref, dict)
        assert "name" in secret_ref
        assert isinstance(secret_ref["name"], str)

    @pytest.mark.requirement("7A-FR-012")
    def test_generate_pod_env_spec_does_not_require_initialization(self) -> None:
        """Test generate_pod_env_spec works without startup().

        This method generates a spec fragment and doesn't need K8s API access.
        """
        plugin = K8sSecretsPlugin()
        # Note: startup() NOT called

        result: dict[str, Any] = plugin.generate_pod_env_spec("my-secret")

        assert result is not None
        assert "envFrom" in result


class TestPodEnvSpecIntegration:
    """Test pod env spec in context of pod definitions."""

    @pytest.mark.requirement("7A-FR-012")
    def test_spec_can_be_merged_with_pod_template(self) -> None:
        """Test spec can be merged into a pod template."""
        plugin = K8sSecretsPlugin()

        # Simulate a pod container spec
        container_spec: dict[str, Any] = {
            "name": "my-app",
            "image": "my-image:latest",
            "ports": [{"containerPort": 8080}],
        }

        # Get env spec and merge
        env_spec = plugin.generate_pod_env_spec("db-creds")
        container_spec.update(env_spec)

        # Verify merged result
        assert container_spec["name"] == "my-app"
        assert container_spec["image"] == "my-image:latest"
        assert container_spec["envFrom"] == [{"secretRef": {"name": "db-creds"}}]

    @pytest.mark.requirement("7A-FR-012")
    def test_multiple_secrets_can_be_combined(self) -> None:
        """Test multiple secret refs can be combined in a pod spec."""
        plugin = K8sSecretsPlugin()

        # Get specs for multiple secrets
        spec1 = plugin.generate_pod_env_spec("db-creds")
        spec2 = plugin.generate_pod_env_spec("api-keys")

        # Combine envFrom lists
        combined_env_from = spec1["envFrom"] + spec2["envFrom"]

        assert len(combined_env_from) == 2
        assert combined_env_from[0]["secretRef"]["name"] == "db-creds"
        assert combined_env_from[1]["secretRef"]["name"] == "api-keys"
