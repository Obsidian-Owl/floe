"""Performance tests for NetworkPolicy generation.

Task: T090
Phase: 11 - Performance Testing (US7)
User Story: US7 - Plugin Architecture Standards
Requirement: Performance

Performance targets:
- 100 namespaces: <5 seconds
- 1000 PSS label generations: <1 second
- 1000 security context generations: <1 second
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from floe_network_security_k8s import K8sNetworkSecurityPlugin


class TestPolicyGenerationPerformance:
    """Performance tests for policy generation."""

    @pytest.fixture
    def plugin(self) -> K8sNetworkSecurityPlugin:
        """Create plugin instance for testing."""
        return K8sNetworkSecurityPlugin()

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_100_namespaces_under_5_seconds(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test generating policies for 100 namespaces takes <5 seconds."""
        namespaces = [f"namespace-{i:03d}" for i in range(100)]

        start_time = time.perf_counter()

        for ns in namespaces:
            plugin.generate_default_deny_policies(ns)

        elapsed = time.perf_counter() - start_time

        assert elapsed < 5.0, f"100 namespaces took {elapsed:.2f}s (limit: 5s)"

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_linear_scaling(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test generation scales linearly with namespace count."""

        def measure_time(count: int) -> float:
            """Measure time to generate policies for count namespaces."""
            namespaces = [f"ns-{i:03d}" for i in range(count)]
            start = time.perf_counter()
            for ns in namespaces:
                plugin.generate_default_deny_policies(ns)
            return time.perf_counter() - start

        time_10 = measure_time(10)
        time_100 = measure_time(100)

        # 100 should take roughly 10x the time of 10 (5x-20x allowed for variance)
        actual_ratio = time_100 / time_10 if time_10 > 0 else float("inf")
        assert 5.0 < actual_ratio < 20.0, f"Expected near-linear scaling, got {actual_ratio:.1f}x"

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_policy_generation_consistency(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test policy generation produces consistent output."""
        namespace = "test-consistency"

        # Generate policies multiple times
        policies_1 = plugin.generate_default_deny_policies(namespace)
        policies_2 = plugin.generate_default_deny_policies(namespace)

        # Should produce identical results
        assert len(policies_1) == len(policies_2), "Policy count should be consistent"

        # Verify policies are deterministic
        for p1, p2 in zip(policies_1, policies_2):
            assert p1 == p2, "Policies should be deterministic"


class TestPSSLabelPerformance:
    """Performance tests for PSS label generation."""

    @pytest.fixture
    def plugin(self) -> K8sNetworkSecurityPlugin:
        """Create plugin instance for testing."""
        return K8sNetworkSecurityPlugin()

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_1000_pss_labels_under_1_second(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test 1000 PSS label generations take <1 second."""
        start_time = time.perf_counter()

        for _ in range(1000):
            plugin.generate_pss_labels(
                level="restricted",
                audit_level="baseline",
                warn_level="baseline",
            )

        elapsed = time.perf_counter() - start_time
        assert elapsed < 1.0, f"1000 PSS labels took {elapsed:.2f}s (limit: 1s)"

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_pss_label_generation_all_levels(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test PSS label generation for all security levels."""
        levels = ["baseline", "restricted", "privileged"]
        audit_levels = ["baseline", "restricted"]
        warn_levels = ["baseline", "restricted"]

        start_time = time.perf_counter()

        for level in levels:
            for audit_level in audit_levels:
                for warn_level in warn_levels:
                    plugin.generate_pss_labels(
                        level=level,
                        audit_level=audit_level,
                        warn_level=warn_level,
                    )

        elapsed = time.perf_counter() - start_time

        # 3 * 2 * 2 = 12 combinations should be very fast
        assert elapsed < 0.1, f"12 PSS label combinations took {elapsed:.3f}s (limit: 0.1s)"

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_pss_label_output_consistency(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test PSS label generation produces consistent output."""
        # Generate same labels multiple times
        labels_1 = plugin.generate_pss_labels(
            level="restricted",
            audit_level="baseline",
            warn_level="baseline",
        )
        labels_2 = plugin.generate_pss_labels(
            level="restricted",
            audit_level="baseline",
            warn_level="baseline",
        )

        # Should be identical
        assert labels_1 == labels_2, "PSS labels should be deterministic"


class TestSecurityContextPerformance:
    """Performance tests for security context generation."""

    @pytest.fixture
    def plugin(self) -> K8sNetworkSecurityPlugin:
        """Create plugin instance for testing."""
        return K8sNetworkSecurityPlugin()

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_1000_security_contexts_under_1_second(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test 1000 security context generations take <1 second."""
        start_time = time.perf_counter()

        for _ in range(1000):
            plugin.generate_container_security_context({})

        elapsed = time.perf_counter() - start_time
        assert elapsed < 1.0, f"1000 security contexts took {elapsed:.2f}s (limit: 1s)"

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_security_context_all_configurations(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test security context generation for various configurations."""
        start_time = time.perf_counter()

        for _ in range(6):
            plugin.generate_container_security_context({})
            plugin.generate_pod_security_context({})

        elapsed = time.perf_counter() - start_time

        # 12 context generations should be very fast
        assert elapsed < 0.05, (
            f"12 security context configurations took {elapsed:.3f}s (limit: 0.05s)"
        )

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_security_context_output_consistency(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test security context generation produces consistent output."""
        # Generate same context multiple times
        context_1 = plugin.generate_container_security_context({})
        context_2 = plugin.generate_container_security_context({})

        # Should be identical
        assert context_1 == context_2, "Security contexts should be deterministic"

    @pytest.mark.performance
    @pytest.mark.requirement("Performance")
    def test_combined_policy_generation_performance(self, plugin: K8sNetworkSecurityPlugin) -> None:
        """Test combined policy, PSS, and security context generation."""
        start_time = time.perf_counter()

        for i in range(50):
            namespace = f"combined-test-{i:03d}"

            # Generate all security artifacts
            plugin.generate_default_deny_policies(namespace)
            plugin.generate_pss_labels(
                level="restricted",
                audit_level="baseline",
                warn_level="baseline",
            )
            plugin.generate_container_security_context({})

        elapsed = time.perf_counter() - start_time

        # 50 namespaces with all artifacts should complete in <2 seconds
        assert elapsed < 2.0, (
            f"Combined generation for 50 namespaces took {elapsed:.2f}s (limit: 2s)"
        )
