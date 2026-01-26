"""Fixtures for network CLI command tests.

This module provides fixtures specific to testing network CLI commands:
- NetworkPolicy manifest fixtures (valid, invalid, multi-doc)
- Mock Kubernetes API clients (NetworkingV1Api, CoreV1Api, AppsV1Api)
- CNI detection mocks (DaemonSet lists for various CNI plugins)
- Directory fixtures with test manifests

For shared fixtures across all CLI tests, see ../conftest.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


# =============================================================================
# NetworkPolicy Manifest Fixtures
# =============================================================================


@pytest.fixture
def valid_network_policy_yaml() -> str:
    """Return a valid NetworkPolicy YAML string."""
    return """apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: floe-jobs
  labels:
    app.kubernetes.io/managed-by: floe
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress: []
  egress: []
"""


@pytest.fixture
def valid_network_policy_with_rules_yaml() -> str:
    """Return a NetworkPolicy YAML with egress rules."""
    return """apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-platform-egress
  namespace: floe-jobs
  labels:
    app.kubernetes.io/managed-by: floe
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: floe-platform
      ports:
        - protocol: TCP
          port: 8181
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
"""


@pytest.fixture
def invalid_network_policy_missing_apiversion_yaml() -> str:
    """Return NetworkPolicy YAML missing apiVersion."""
    return """kind: NetworkPolicy
metadata:
  name: invalid-policy
  namespace: floe-jobs
spec:
  podSelector: {}
"""


@pytest.fixture
def invalid_network_policy_wrong_kind_yaml() -> str:
    """Return YAML with wrong kind (not NetworkPolicy)."""
    return """apiVersion: v1
kind: ConfigMap
metadata:
  name: not-a-policy
  namespace: floe-jobs
data:
  key: value
"""


@pytest.fixture
def network_policy_missing_managed_by_label_yaml() -> str:
    """Return NetworkPolicy YAML missing managed-by label."""
    return """apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: missing-label
  namespace: floe-jobs
spec:
  podSelector: {}
  policyTypes:
    - Ingress
"""


@pytest.fixture
def network_policy_wrong_managed_by_label_yaml() -> str:
    """Return NetworkPolicy YAML with wrong managed-by label value."""
    return """apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: wrong-label
  namespace: floe-jobs
  labels:
    app.kubernetes.io/managed-by: helm
spec:
  podSelector: {}
  policyTypes:
    - Ingress
"""


@pytest.fixture
def multi_doc_network_policy_yaml(valid_network_policy_yaml: str) -> str:
    """Return multi-document YAML with multiple NetworkPolicies."""
    return f"""{valid_network_policy_yaml}---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: floe-jobs
  labels:
    app.kubernetes.io/managed-by: floe
spec:
  podSelector: {{}}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
"""


@pytest.fixture
def empty_yaml() -> str:
    """Return empty YAML content."""
    return ""


@pytest.fixture
def null_doc_yaml() -> str:
    """Return YAML with null document."""
    return "---\n"


# =============================================================================
# Directory Fixtures with Manifest Files
# =============================================================================


@pytest.fixture
def manifest_dir_with_policies(
    tmp_path: Path,
    valid_network_policy_yaml: str,
    valid_network_policy_with_rules_yaml: str,
) -> Path:
    """Create a temporary directory with valid NetworkPolicy manifests."""
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    (manifest_dir / "default-deny.yaml").write_text(valid_network_policy_yaml)
    (manifest_dir / "allow-egress.yaml").write_text(valid_network_policy_with_rules_yaml)

    return manifest_dir


@pytest.fixture
def manifest_dir_with_invalid_policies(
    tmp_path: Path,
    invalid_network_policy_missing_apiversion_yaml: str,
) -> Path:
    """Create a directory with invalid NetworkPolicy manifests."""
    manifest_dir = tmp_path / "invalid-manifests"
    manifest_dir.mkdir()

    (manifest_dir / "invalid.yaml").write_text(invalid_network_policy_missing_apiversion_yaml)

    return manifest_dir


@pytest.fixture
def manifest_dir_empty(tmp_path: Path) -> Path:
    """Create an empty manifest directory."""
    manifest_dir = tmp_path / "empty-manifests"
    manifest_dir.mkdir()
    return manifest_dir


@pytest.fixture
def manifest_dir_with_yml_extension(
    tmp_path: Path,
    valid_network_policy_yaml: str,
) -> Path:
    """Create a directory with .yml extension files."""
    manifest_dir = tmp_path / "yml-manifests"
    manifest_dir.mkdir()

    (manifest_dir / "policy.yml").write_text(valid_network_policy_yaml)

    return manifest_dir


# =============================================================================
# Sample Configuration Fixtures
# =============================================================================


@pytest.fixture
def sample_manifest_yaml_with_network(tmp_path: Path) -> Path:
    """Create a sample manifest.yaml with network configuration."""
    content = """version: "1.0.0"
name: test-platform

compute:
  plugin: duckdb
  config:
    database: ":memory:"

security:
  network_policies:
    enabled: true
    default_deny: true
    allow_external_https: true
    ingress_controller_namespace: ingress-nginx
"""
    path = tmp_path / "manifest.yaml"
    path.write_text(content)
    return path


# =============================================================================
# Mock Kubernetes Client Fixtures
# =============================================================================


@pytest.fixture
def mock_k8s_config() -> MagicMock:
    """Create a mock kubernetes.config module."""
    mock = MagicMock()
    mock.load_incluster_config = MagicMock()
    mock.load_kube_config = MagicMock()
    mock.ConfigException = Exception
    return mock


@pytest.fixture
def mock_k8s_client() -> MagicMock:
    """Create a mock kubernetes.client module."""
    mock = MagicMock()
    mock.NetworkingV1Api = MagicMock
    mock.CoreV1Api = MagicMock
    mock.AppsV1Api = MagicMock
    return mock


@pytest.fixture
def mock_networking_api() -> MagicMock:
    """Create a mock NetworkingV1Api instance."""
    mock = MagicMock()
    mock.list_namespaced_network_policy = MagicMock()
    return mock


@pytest.fixture
def mock_core_api() -> MagicMock:
    """Create a mock CoreV1Api instance."""
    mock = MagicMock()
    mock.list_namespace = MagicMock()
    mock.list_namespaced_config_map = MagicMock()
    return mock


@pytest.fixture
def mock_apps_api() -> MagicMock:
    """Create a mock AppsV1Api instance."""
    mock = MagicMock()
    mock.list_namespaced_daemon_set = MagicMock()
    return mock


# =============================================================================
# Mock Kubernetes Objects
# =============================================================================


@pytest.fixture
def mock_network_policy_factory() -> Callable[..., MagicMock]:
    """Factory to create mock NetworkPolicy objects."""

    def _create_network_policy(
        name: str = "test-policy",
        namespace: str = "default",
        pod_selector: dict[str, Any] | None = None,
        policy_types: list[str] | None = None,
        ingress: list[dict[str, Any]] | None = None,
        egress: list[dict[str, Any]] | None = None,
        labels: dict[str, str] | None = None,
    ) -> MagicMock:
        policy = MagicMock()
        policy.metadata = MagicMock()
        policy.metadata.name = name
        policy.metadata.namespace = namespace
        policy.metadata.labels = labels or {"app.kubernetes.io/managed-by": "floe"}

        policy.spec = MagicMock()
        policy.spec.pod_selector = MagicMock()
        policy.spec.pod_selector.match_labels = pod_selector or {}
        policy.spec.policy_types = policy_types or ["Ingress", "Egress"]
        policy.spec.ingress = ingress or []
        policy.spec.egress = egress or []

        return policy

    return _create_network_policy


@pytest.fixture
def mock_network_policy_list(
    mock_network_policy_factory: Callable[..., MagicMock],
) -> MagicMock:
    """Create a mock NetworkPolicyList with sample policies."""
    policy_list = MagicMock()
    policy_list.items = [
        mock_network_policy_factory(
            name="default-deny-all",
            namespace="floe-jobs",
            policy_types=["Ingress", "Egress"],
        ),
        mock_network_policy_factory(
            name="allow-dns-egress",
            namespace="floe-jobs",
            policy_types=["Egress"],
        ),
    ]
    return policy_list


@pytest.fixture
def mock_namespace_list() -> MagicMock:
    """Create a mock NamespaceList."""
    ns_list = MagicMock()

    ns1 = MagicMock()
    ns1.metadata.name = "default"
    ns2 = MagicMock()
    ns2.metadata.name = "floe-jobs"
    ns3 = MagicMock()
    ns3.metadata.name = "floe-platform"
    ns4 = MagicMock()
    ns4.metadata.name = "kube-system"

    ns_list.items = [ns1, ns2, ns3, ns4]
    return ns_list


# =============================================================================
# CNI Detection Fixtures
# =============================================================================


@pytest.fixture
def mock_daemonset_calico() -> MagicMock:
    """Create a mock DaemonSet for Calico CNI."""
    ds = MagicMock()
    ds.metadata = MagicMock()
    ds.metadata.name = "calico-node"
    ds.metadata.namespace = "kube-system"
    return ds


@pytest.fixture
def mock_daemonset_cilium() -> MagicMock:
    """Create a mock DaemonSet for Cilium CNI."""
    ds = MagicMock()
    ds.metadata = MagicMock()
    ds.metadata.name = "cilium"
    ds.metadata.namespace = "kube-system"
    return ds


@pytest.fixture
def mock_daemonset_flannel() -> MagicMock:
    """Create a mock DaemonSet for Flannel CNI (unsupported)."""
    ds = MagicMock()
    ds.metadata = MagicMock()
    ds.metadata.name = "kube-flannel-ds"
    ds.metadata.namespace = "kube-system"
    return ds


@pytest.fixture
def mock_daemonset_kindnet() -> MagicMock:
    """Create a mock DaemonSet for KindNet CNI (unsupported)."""
    ds = MagicMock()
    ds.metadata = MagicMock()
    ds.metadata.name = "kindnet"
    ds.metadata.namespace = "kube-system"
    return ds


@pytest.fixture
def mock_daemonset_aws_node() -> MagicMock:
    """Create a mock DaemonSet for AWS VPC CNI."""
    ds = MagicMock()
    ds.metadata = MagicMock()
    ds.metadata.name = "aws-node"
    ds.metadata.namespace = "kube-system"
    return ds


@pytest.fixture
def mock_daemonset_list_calico(mock_daemonset_calico: MagicMock) -> MagicMock:
    """Create a DaemonSetList with Calico."""
    ds_list = MagicMock()
    ds_list.items = [mock_daemonset_calico]
    return ds_list


@pytest.fixture
def mock_daemonset_list_cilium(mock_daemonset_cilium: MagicMock) -> MagicMock:
    """Create a DaemonSetList with Cilium."""
    ds_list = MagicMock()
    ds_list.items = [mock_daemonset_cilium]
    return ds_list


@pytest.fixture
def mock_daemonset_list_flannel(mock_daemonset_flannel: MagicMock) -> MagicMock:
    """Create a DaemonSetList with Flannel (unsupported)."""
    ds_list = MagicMock()
    ds_list.items = [mock_daemonset_flannel]
    return ds_list


@pytest.fixture
def mock_daemonset_list_empty() -> MagicMock:
    """Create an empty DaemonSetList (no CNI detected)."""
    ds_list = MagicMock()
    ds_list.items = []
    return ds_list


# =============================================================================
# API Error Fixtures
# =============================================================================


@pytest.fixture
def mock_api_exception_404() -> MagicMock:
    """Create a mock ApiException for 404 Not Found."""
    exc = MagicMock()
    exc.status = 404
    exc.reason = "Not Found"
    return exc


@pytest.fixture
def mock_api_exception_403() -> MagicMock:
    """Create a mock ApiException for 403 Forbidden."""
    exc = MagicMock()
    exc.status = 403
    exc.reason = "Forbidden"
    return exc


@pytest.fixture
def mock_api_exception_500() -> MagicMock:
    """Create a mock ApiException for 500 Internal Server Error."""
    exc = MagicMock()
    exc.status = 500
    exc.reason = "Internal Server Error"
    return exc


__all__: list[str] = [
    # Manifest fixtures
    "valid_network_policy_yaml",
    "valid_network_policy_with_rules_yaml",
    "invalid_network_policy_missing_apiversion_yaml",
    "invalid_network_policy_wrong_kind_yaml",
    "network_policy_missing_managed_by_label_yaml",
    "network_policy_wrong_managed_by_label_yaml",
    "multi_doc_network_policy_yaml",
    "empty_yaml",
    "null_doc_yaml",
    # Directory fixtures
    "manifest_dir_with_policies",
    "manifest_dir_with_invalid_policies",
    "manifest_dir_empty",
    "manifest_dir_with_yml_extension",
    # Config fixtures
    "sample_manifest_yaml_with_network",
    # K8s client mocks
    "mock_k8s_config",
    "mock_k8s_client",
    "mock_networking_api",
    "mock_core_api",
    "mock_apps_api",
    # K8s object mocks
    "mock_network_policy_factory",
    "mock_network_policy_list",
    "mock_namespace_list",
    # CNI mocks
    "mock_daemonset_calico",
    "mock_daemonset_cilium",
    "mock_daemonset_flannel",
    "mock_daemonset_kindnet",
    "mock_daemonset_aws_node",
    "mock_daemonset_list_calico",
    "mock_daemonset_list_cilium",
    "mock_daemonset_list_flannel",
    "mock_daemonset_list_empty",
    # API error mocks
    "mock_api_exception_404",
    "mock_api_exception_403",
    "mock_api_exception_500",
]
