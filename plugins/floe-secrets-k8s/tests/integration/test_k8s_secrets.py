"""Integration tests for K8s Secrets operations in Kind cluster.

Tests K8sSecretsPlugin operations against a real Kubernetes cluster.

Implements:
    - T022: Integration test for K8s Secrets operations in Kind cluster
    - FR-011: Namespace-scoped secret access
    - FR-013: Support in-cluster and kubeconfig auth

Prerequisites:
    - Kind cluster running (make kind-up)
    - kubectl configured to access cluster
"""

from __future__ import annotations

import base64
import subprocess
import uuid
from typing import TYPE_CHECKING

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

if TYPE_CHECKING:
    pass


class TestK8sSecretsOperations(IntegrationTestBase):
    """Integration tests for K8s Secrets operations.

    Requires a running Kubernetes cluster (Kind or otherwise).
    Tests run in an isolated namespace that is cleaned up after tests.
    """

    # No external services required - just K8s API access
    required_services: list[tuple[str, int]] = []
    namespace = "floe-test"

    def _kubectl_available(self) -> bool:
        """Check if kubectl is available and configured."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _create_test_namespace(self, name: str) -> None:
        """Create a K8s namespace for testing."""
        subprocess.run(
            ["kubectl", "create", "namespace", name],
            capture_output=True,
            check=False,
        )

    def _delete_test_namespace(self, name: str) -> None:
        """Delete a K8s namespace."""
        subprocess.run(
            ["kubectl", "delete", "namespace", name, "--ignore-not-found"],
            capture_output=True,
            check=False,
        )

    def _create_k8s_secret(
        self, name: str, namespace: str, data: dict[str, str]
    ) -> None:
        """Create a K8s Secret using kubectl."""
        # Encode data as base64
        literal_args = []
        for key, value in data.items():
            literal_args.extend(["--from-literal", f"{key}={value}"])

        subprocess.run(
            ["kubectl", "create", "secret", "generic", name, "-n", namespace]
            + literal_args,
            capture_output=True,
            check=True,
        )

    def _get_k8s_secret(self, name: str, namespace: str) -> dict[str, str] | None:
        """Get a K8s Secret using kubectl and return decoded data."""
        result = subprocess.run(
            ["kubectl", "get", "secret", name, "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        import json

        secret_data = json.loads(result.stdout)
        if "data" not in secret_data or secret_data["data"] is None:
            return {}

        # Decode base64 values
        decoded: dict[str, str] = {}
        for key, encoded_value in secret_data["data"].items():
            decoded[key] = base64.b64decode(encoded_value).decode("utf-8")

        return decoded

    def _delete_k8s_secret(self, name: str, namespace: str) -> None:
        """Delete a K8s Secret using kubectl."""
        subprocess.run(
            [
                "kubectl",
                "delete",
                "secret",
                name,
                "-n",
                namespace,
                "--ignore-not-found",
            ],
            capture_output=True,
            check=False,
        )

    @pytest.fixture
    def test_namespace(self) -> str:
        """Create a unique test namespace."""
        ns = f"floe-test-{uuid.uuid4().hex[:8]}"
        self._create_test_namespace(ns)
        yield ns
        self._delete_test_namespace(ns)

    @pytest.mark.requirement("7A-FR-011")
    def test_get_secret_retrieves_existing(self, test_namespace: str) -> None:
        """Test get_secret retrieves an existing K8s Secret."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        # Create secret via kubectl
        secret_name = f"test-secret-{uuid.uuid4().hex[:8]}"
        secret_value = "my-secret-value"
        self._create_k8s_secret(secret_name, test_namespace, {"value": secret_value})

        try:
            # Configure and initialize plugin
            config = K8sSecretsConfig(namespace=test_namespace)
            plugin = K8sSecretsPlugin(config)
            plugin.startup()

            # Retrieve via plugin
            result = plugin.get_secret(secret_name)

            assert result == secret_value

        finally:
            plugin.shutdown()
            self._delete_k8s_secret(secret_name, test_namespace)

    @pytest.mark.requirement("7A-FR-011")
    def test_get_secret_with_specific_key(self, test_namespace: str) -> None:
        """Test get_secret with 'secret-name/key' format."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        # Create secret with multiple keys
        secret_name = f"db-creds-{uuid.uuid4().hex[:8]}"
        expected_user = "testuser"
        expected_cred = "test-value-abc"
        self._create_k8s_secret(
            secret_name,
            test_namespace,
            {"username": expected_user, "credential": expected_cred},
        )

        try:
            config = K8sSecretsConfig(namespace=test_namespace)
            plugin = K8sSecretsPlugin(config)
            plugin.startup()

            # Retrieve specific keys
            actual_user = plugin.get_secret(f"{secret_name}/username")
            actual_cred = plugin.get_secret(f"{secret_name}/credential")

            assert actual_user == expected_user
            assert actual_cred == expected_cred

        finally:
            plugin.shutdown()
            self._delete_k8s_secret(secret_name, test_namespace)

    @pytest.mark.requirement("7A-CR-004")
    def test_get_secret_returns_none_for_missing(self, test_namespace: str) -> None:
        """Test get_secret returns None for non-existent secret."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        config = K8sSecretsConfig(namespace=test_namespace)
        plugin = K8sSecretsPlugin(config)
        plugin.startup()

        try:
            result = plugin.get_secret("nonexistent-secret")
            assert result is None
        finally:
            plugin.shutdown()

    @pytest.mark.requirement("7A-FR-010")
    def test_set_secret_creates_new(self, test_namespace: str) -> None:
        """Test set_secret creates a new K8s Secret."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        secret_name = f"new-secret-{uuid.uuid4().hex[:8]}"
        secret_value = "created-by-plugin"

        config = K8sSecretsConfig(namespace=test_namespace, labels={})
        plugin = K8sSecretsPlugin(config)
        plugin.startup()

        try:
            # Create via plugin
            plugin.set_secret(secret_name, secret_value)

            # Verify via kubectl
            k8s_data = self._get_k8s_secret(secret_name, test_namespace)
            assert k8s_data is not None
            assert k8s_data.get("value") == secret_value

        finally:
            plugin.shutdown()
            self._delete_k8s_secret(secret_name, test_namespace)

    @pytest.mark.requirement("7A-FR-010")
    def test_set_secret_updates_existing(self, test_namespace: str) -> None:
        """Test set_secret updates an existing K8s Secret."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        secret_name = f"existing-secret-{uuid.uuid4().hex[:8]}"
        original_value = "original-value"
        updated_value = "updated-value"

        # Create original secret
        self._create_k8s_secret(secret_name, test_namespace, {"value": original_value})

        config = K8sSecretsConfig(namespace=test_namespace, labels={})
        plugin = K8sSecretsPlugin(config)
        plugin.startup()

        try:
            # Update via plugin
            plugin.set_secret(secret_name, updated_value)

            # Verify via kubectl
            k8s_data = self._get_k8s_secret(secret_name, test_namespace)
            assert k8s_data is not None
            assert k8s_data.get("value") == updated_value

        finally:
            plugin.shutdown()
            self._delete_k8s_secret(secret_name, test_namespace)

    @pytest.mark.requirement("7A-FR-010")
    def test_list_secrets_returns_all(self, test_namespace: str) -> None:
        """Test list_secrets returns all secrets in namespace."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        # Create multiple secrets with same label
        label_value = f"test-{uuid.uuid4().hex[:8]}"
        secret_names = [
            f"secret-a-{uuid.uuid4().hex[:8]}",
            f"secret-b-{uuid.uuid4().hex[:8]}",
        ]

        for name in secret_names:
            self._create_k8s_secret(name, test_namespace, {"key": "value"})
            # Add label
            subprocess.run(
                [
                    "kubectl",
                    "label",
                    "secret",
                    name,
                    "-n",
                    test_namespace,
                    f"managed-by={label_value}",
                ],
                capture_output=True,
            )

        config = K8sSecretsConfig(
            namespace=test_namespace, labels={"managed-by": label_value}
        )
        plugin = K8sSecretsPlugin(config)
        plugin.startup()

        try:
            secrets = plugin.list_secrets()

            # Should include our created secrets
            for name in secret_names:
                assert f"{name}/key" in secrets

        finally:
            plugin.shutdown()
            for name in secret_names:
                self._delete_k8s_secret(name, test_namespace)

    @pytest.mark.requirement("7A-FR-010")
    def test_list_secrets_filters_by_prefix(self, test_namespace: str) -> None:
        """Test list_secrets filters by prefix."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        # Create secrets with different prefixes
        label_value = f"test-{uuid.uuid4().hex[:8]}"
        db_secret = f"db-creds-{uuid.uuid4().hex[:8]}"
        api_secret = f"api-key-{uuid.uuid4().hex[:8]}"

        self._create_k8s_secret(db_secret, test_namespace, {"password": "secret"})
        self._create_k8s_secret(api_secret, test_namespace, {"token": "token123"})

        # Add labels
        for name in [db_secret, api_secret]:
            subprocess.run(
                [
                    "kubectl",
                    "label",
                    "secret",
                    name,
                    "-n",
                    test_namespace,
                    f"managed-by={label_value}",
                ],
                capture_output=True,
            )

        config = K8sSecretsConfig(
            namespace=test_namespace, labels={"managed-by": label_value}
        )
        plugin = K8sSecretsPlugin(config)
        plugin.startup()

        try:
            db_secrets = plugin.list_secrets(prefix="db-")

            assert any("db-creds" in s for s in db_secrets)
            assert not any("api-key" in s for s in db_secrets)

        finally:
            plugin.shutdown()
            self._delete_k8s_secret(db_secret, test_namespace)
            self._delete_k8s_secret(api_secret, test_namespace)

    @pytest.mark.requirement("7A-FR-011")
    def test_namespace_isolation(self, test_namespace: str) -> None:
        """Test secrets are isolated by namespace."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        # Create secret in test namespace
        secret_name = f"isolated-secret-{uuid.uuid4().hex[:8]}"
        self._create_k8s_secret(secret_name, test_namespace, {"value": "visible"})

        # Create another namespace
        other_namespace = f"other-{uuid.uuid4().hex[:8]}"
        self._create_test_namespace(other_namespace)

        try:
            # Plugin configured for other namespace
            config = K8sSecretsConfig(namespace=other_namespace)
            plugin = K8sSecretsPlugin(config)
            plugin.startup()

            # Should not see secret from test_namespace
            result = plugin.get_secret(secret_name)
            assert result is None

        finally:
            plugin.shutdown()
            self._delete_k8s_secret(secret_name, test_namespace)
            self._delete_test_namespace(other_namespace)

    @pytest.mark.requirement("7A-CR-002")
    def test_health_check_returns_healthy(self, test_namespace: str) -> None:
        """Test health_check returns HEALTHY when K8s API is accessible."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_core.plugin_metadata import HealthState

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        config = K8sSecretsConfig(namespace=test_namespace)
        plugin = K8sSecretsPlugin(config)
        plugin.startup()

        try:
            status = plugin.health_check()
            assert status.state == HealthState.HEALTHY

        finally:
            plugin.shutdown()

    @pytest.mark.requirement("7A-FR-010")
    def test_get_multi_key_secret(self, test_namespace: str) -> None:
        """Test get_multi_key_secret retrieves all key-value pairs."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        # Create secret with multiple keys
        secret_name = f"multi-key-{uuid.uuid4().hex[:8]}"
        secret_data = {
            "username": "testuser",
            "credential": "test-value-xyz",
            "host": "testhost",
            "port": "5432",
        }
        self._create_k8s_secret(secret_name, test_namespace, secret_data)

        config = K8sSecretsConfig(namespace=test_namespace)
        plugin = K8sSecretsPlugin(config)
        plugin.startup()

        try:
            result = plugin.get_multi_key_secret(secret_name)

            assert result == secret_data

        finally:
            plugin.shutdown()
            self._delete_k8s_secret(secret_name, test_namespace)


class TestK8sSecretsAuthentication(IntegrationTestBase):
    """Test authentication methods for K8sSecretsPlugin."""

    required_services: list[tuple[str, int]] = []
    namespace = "floe-test"

    def _kubectl_available(self) -> bool:
        """Check if kubectl is available and configured."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @pytest.mark.requirement("7A-FR-013")
    def test_kubeconfig_authentication(self) -> None:
        """Test plugin works with kubeconfig-based authentication."""
        if not self._kubectl_available():
            pytest.fail("kubectl not available - start Kind cluster with: make kind-up")

        from floe_secrets_k8s.config import K8sSecretsConfig
        from floe_secrets_k8s.plugin import K8sSecretsPlugin

        # Use default kubeconfig (should work on dev machines)
        config = K8sSecretsConfig(
            namespace="default",
            kubeconfig_path="~/.kube/config",
        )
        plugin = K8sSecretsPlugin(config)

        # startup() should succeed with kubeconfig auth
        plugin.startup()

        try:
            # Verify API access works
            status = plugin.health_check()
            from floe_core.plugin_metadata import HealthState

            assert status.state == HealthState.HEALTHY

        finally:
            plugin.shutdown()
