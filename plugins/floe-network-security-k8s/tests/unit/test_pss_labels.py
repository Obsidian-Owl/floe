"""Unit tests for Pod Security Standards (PSS) label generation.

Task: T035
Phase: 5 - Pod Security Standards Enforcement (US3)
User Story: US3 - Pod Security Standards Enforcement
Requirement: FR-050, FR-051, FR-052, FR-053, FR-054
"""

from __future__ import annotations

import pytest


class TestPSSLabelGeneration:
    """Unit tests for PSS namespace label generation (T035).

    Pod Security Standards are enforced via namespace labels:
    - pod-security.kubernetes.io/enforce: level
    - pod-security.kubernetes.io/audit: level
    - pod-security.kubernetes.io/warn: level

    Levels: privileged, baseline, restricted
    """

    @pytest.mark.requirement("FR-050")
    def test_generate_pss_labels_returns_dict(self) -> None:
        """Test that PSS label generation returns a dictionary."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        labels = plugin.generate_pss_labels(level="restricted")
        assert isinstance(labels, dict)

    @pytest.mark.requirement("FR-050")
    def test_generate_pss_labels_has_enforce_key(self) -> None:
        """Test that PSS labels include enforce key."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        labels = plugin.generate_pss_labels(level="restricted")
        assert "pod-security.kubernetes.io/enforce" in labels

    @pytest.mark.requirement("FR-050")
    def test_generate_pss_labels_has_audit_key(self) -> None:
        """Test that PSS labels include audit key."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        labels = plugin.generate_pss_labels(level="restricted")
        assert "pod-security.kubernetes.io/audit" in labels

    @pytest.mark.requirement("FR-050")
    def test_generate_pss_labels_has_warn_key(self) -> None:
        """Test that PSS labels include warn key."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        labels = plugin.generate_pss_labels(level="restricted")
        assert "pod-security.kubernetes.io/warn" in labels

    @pytest.mark.requirement("FR-050")
    def test_pss_labels_restricted_level(self) -> None:
        """Test that restricted level is correctly set."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        labels = plugin.generate_pss_labels(level="restricted")
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

    @pytest.mark.requirement("FR-051")
    def test_pss_labels_baseline_level(self) -> None:
        """Test that baseline level is correctly set."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        labels = plugin.generate_pss_labels(level="baseline")
        assert labels["pod-security.kubernetes.io/enforce"] == "baseline"

    @pytest.mark.requirement("FR-052")
    def test_pss_labels_privileged_level(self) -> None:
        """Test that privileged level is correctly set (for system namespaces)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        labels = plugin.generate_pss_labels(level="privileged")
        assert labels["pod-security.kubernetes.io/enforce"] == "privileged"


class TestPSSLevelConfiguration:
    """Unit tests for PSS level configuration per namespace (T040).

    Different namespaces have different PSS requirements:
    - floe-jobs: restricted (hardest)
    - floe-platform: baseline (allows some host access)
    """

    @pytest.mark.requirement("FR-053")
    def test_jobs_namespace_default_level(self) -> None:
        """Test that floe-jobs defaults to restricted level."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        level = plugin.get_namespace_pss_level("floe-jobs")
        assert level == "restricted"

    @pytest.mark.requirement("FR-053")
    def test_platform_namespace_default_level(self) -> None:
        """Test that floe-platform defaults to baseline level."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        level = plugin.get_namespace_pss_level("floe-platform")
        assert level == "baseline"

    @pytest.mark.requirement("FR-053")
    def test_unknown_namespace_default_level(self) -> None:
        """Test that unknown namespaces default to restricted level."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        level = plugin.get_namespace_pss_level("some-other-namespace")
        # Unknown namespaces should be restricted by default (secure default)
        assert level == "restricted"

    @pytest.mark.requirement("FR-054")
    def test_configurable_pss_level(self) -> None:
        """Test that PSS level is configurable via override."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        # With override
        level = plugin.get_namespace_pss_level(
            "floe-jobs",
            override_levels={"floe-jobs": "baseline"},
        )
        assert level == "baseline"


class TestNamespacePSSManifest:
    """Unit tests for namespace manifest with PSS labels (T041).

    Generate complete namespace manifest with PSS labels applied.
    """

    @pytest.mark.requirement("FR-054")
    def test_generate_namespace_manifest_with_pss(self) -> None:
        """Test generation of namespace manifest with PSS labels."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        manifest = plugin.generate_namespace_manifest(
            name="floe-jobs",
            pss_level="restricted",
        )

        assert manifest["apiVersion"] == "v1"
        assert manifest["kind"] == "Namespace"
        assert manifest["metadata"]["name"] == "floe-jobs"
        assert "labels" in manifest["metadata"]

    @pytest.mark.requirement("FR-054")
    def test_namespace_manifest_has_pss_labels(self) -> None:
        """Test that namespace manifest includes PSS labels."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        manifest = plugin.generate_namespace_manifest(
            name="floe-jobs",
            pss_level="restricted",
        )

        labels = manifest["metadata"]["labels"]
        assert "pod-security.kubernetes.io/enforce" in labels
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

    @pytest.mark.requirement("FR-054")
    def test_namespace_manifest_has_managed_by_label(self) -> None:
        """Test that namespace manifest has managed-by label."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        manifest = plugin.generate_namespace_manifest(
            name="floe-jobs",
            pss_level="restricted",
        )

        labels = manifest["metadata"]["labels"]
        assert labels.get("app.kubernetes.io/managed-by") == "floe"

    @pytest.mark.requirement("FR-054")
    def test_namespace_manifest_audit_warn_same_as_enforce(self) -> None:
        """Test that audit and warn levels match enforce by default."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        manifest = plugin.generate_namespace_manifest(
            name="floe-jobs",
            pss_level="restricted",
        )

        labels = manifest["metadata"]["labels"]
        enforce_level = labels.get("pod-security.kubernetes.io/enforce")
        audit_level = labels.get("pod-security.kubernetes.io/audit")
        warn_level = labels.get("pod-security.kubernetes.io/warn")

        assert enforce_level == audit_level == warn_level == "restricted"
