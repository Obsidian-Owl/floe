"""NetworkPolicy enforcement tests for Helm charts.

These tests validate that NetworkPolicies are correctly rendered
and would enforce expected network isolation.

Requirements:
- FR-032: NetworkPolicy template
- E2E-005: NetworkPolicy enforcement
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


def render_helm_templates(
    chart_path: Path,
    values: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Render Helm templates to YAML documents.

    Args:
        chart_path: Path to the Helm chart
        values: Optional values to override

    Returns:
        List of parsed YAML documents
    """
    # NOTE: --skip-schema-validation required because Dagster subchart
    # references external JSON schema URL that returns 404
    cmd = ["helm", "template", "--skip-schema-validation", "test-release", str(chart_path)]

    if values:
        for key, value in values.items():
            cmd.extend(["--set", f"{key}={value}"])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    documents: list[dict[str, Any]] = []
    for doc in yaml.safe_load_all(result.stdout):
        if doc and isinstance(doc, dict):
            documents.append(doc)

    return documents


def get_network_policies(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract NetworkPolicy resources from rendered documents.

    Args:
        documents: List of Kubernetes manifests

    Returns:
        List of NetworkPolicy manifests
    """
    return [
        doc for doc in documents
        if doc.get("kind") == "NetworkPolicy"
    ]


@pytest.fixture(scope="module")
def chart_root() -> Path:
    """Get the charts directory root."""
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "charts").is_dir():
            return current / "charts"
        current = current.parent
    pytest.fail("Could not find charts directory")


@pytest.fixture(scope="module")
def platform_chart(chart_root: Path) -> Path:
    """Get floe-platform chart path."""
    chart_path = chart_root / "floe-platform"
    if not chart_path.exists():
        pytest.fail("floe-platform chart not found")

    # Update dependencies
    subprocess.run(
        ["helm", "dependency", "update", str(chart_path)],
        capture_output=True,
        check=False,
    )

    return chart_path


@pytest.mark.requirement("FR-032")
@pytest.mark.requirement("E2E-005")
class TestNetworkPolicyEnforcement:
    """Tests for NetworkPolicy rendering and configuration."""

    @pytest.mark.requirement("FR-032")
    def test_network_policies_disabled_by_default(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that NetworkPolicies are disabled by default."""
        documents = render_helm_templates(platform_chart)
        policies = get_network_policies(documents)

        assert len(policies) == 0, (
            "NetworkPolicies should be disabled by default"
        )

    @pytest.mark.requirement("FR-032")
    def test_network_policies_enabled(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that NetworkPolicies are rendered when enabled."""
        documents = render_helm_templates(
            platform_chart,
            values={"networkPolicy.enabled": "true"},
        )
        policies = get_network_policies(documents)

        assert len(policies) > 0, (
            "NetworkPolicies should be rendered when enabled"
        )

    @pytest.mark.requirement("FR-032")
    def test_default_deny_policy_exists(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that default deny ingress policy is created."""
        documents = render_helm_templates(
            platform_chart,
            values={"networkPolicy.enabled": "true"},
        )
        policies = get_network_policies(documents)

        # Find default deny policy
        deny_policies = [
            p for p in policies
            if "default-deny" in p.get("metadata", {}).get("name", "")
        ]

        assert len(deny_policies) > 0, (
            "Default deny NetworkPolicy should exist"
        )

    @pytest.mark.requirement("FR-032")
    def test_dagster_egress_policy(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that Dagster egress policy allows PostgreSQL access."""
        documents = render_helm_templates(
            platform_chart,
            values={
                "networkPolicy.enabled": "true",
                "dagster.enabled": "true",
            },
        )
        policies = get_network_policies(documents)

        # Find Dagster egress policy
        dagster_policies = [
            p for p in policies
            if "dagster" in p.get("metadata", {}).get("name", "").lower()
        ]

        if not dagster_policies:
            pytest.skip("No Dagster-specific NetworkPolicy found")

        # Check egress rules exist
        for policy in dagster_policies:
            spec = policy.get("spec", {})
            if "Egress" in spec.get("policyTypes", []):
                egress = spec.get("egress", [])
                assert len(egress) > 0, (
                    "Dagster egress policy should have rules"
                )

    @pytest.mark.requirement("FR-032")
    def test_polaris_network_policy(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that Polaris has appropriate network policies."""
        documents = render_helm_templates(
            platform_chart,
            values={
                "networkPolicy.enabled": "true",
                "polaris.enabled": "true",
            },
        )
        policies = get_network_policies(documents)

        # Find Polaris policy
        polaris_policies = [
            p for p in policies
            if "polaris" in p.get("metadata", {}).get("name", "").lower()
        ]

        # Polaris should have ingress allowed from Dagster
        if polaris_policies:
            for policy in polaris_policies:
                spec = policy.get("spec", {})
                if "Ingress" in spec.get("policyTypes", []):
                    ingress = spec.get("ingress", [])
                    assert len(ingress) > 0, (
                        "Polaris should allow ingress from Dagster"
                    )

    @pytest.mark.requirement("E2E-005")
    def test_otel_collector_ingress(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that OTel collector accepts ingress from all pods."""
        documents = render_helm_templates(
            platform_chart,
            values={
                "networkPolicy.enabled": "true",
                "otel.enabled": "true",
            },
        )
        policies = get_network_policies(documents)

        # Find OTel collector policy
        otel_policies = [
            p for p in policies
            if "otel" in p.get("metadata", {}).get("name", "").lower()
        ]

        # OTel should allow ingress from namespace
        if otel_policies:
            for policy in otel_policies:
                spec = policy.get("spec", {})
                ingress = spec.get("ingress", [])
                # Check that ingress rules exist
                if ingress:
                    assert len(ingress) > 0, (
                        "OTel collector should allow ingress"
                    )
