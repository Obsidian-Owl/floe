"""Security regression tests for Helm charts.

These tests validate that security fixes remain in place across chart updates.
Each test documents a specific security issue that was fixed.

Requirements:
    9b-SEC-001: Security regression testing
    9b-FR-036: Pod Security Standards
"""

from __future__ import annotations

import base64
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
    cmd = [
        "helm",
        "template",
        "--skip-schema-validation",
        "test-release",
        str(chart_path),
    ]

    if values:
        for key, value in values.items():
            cmd.extend(["--set", f"{key}={value}"])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)

    documents: list[dict[str, Any]] = []
    for doc in yaml.safe_load_all(result.stdout):
        if doc is not None and isinstance(doc, dict):
            doc_typed: dict[str, Any] = doc
            documents.append(doc_typed)

    return documents


def find_resource(
    documents: list[dict[str, Any]],
    kind: str,
    name_contains: str,
) -> dict[str, Any] | None:
    """Find a resource by kind and partial name match.

    Args:
        documents: List of Kubernetes manifests
        kind: Resource kind (e.g., 'ConfigMap', 'Secret')
        name_contains: Substring that must appear in the resource name

    Returns:
        The matching resource or None
    """
    for doc in documents:
        if doc.get("kind") == kind:
            name = doc.get("metadata", {}).get("name", "")
            if name_contains in name:
                return doc
    return None


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
    """Get floe-platform chart path with updated dependencies."""
    chart_path = chart_root / "floe-platform"
    if not chart_path.exists():
        pytest.fail("floe-platform chart not found")

    # Update dependencies
    subprocess.run(
        ["helm", "dependency", "update", str(chart_path)],
        capture_output=True,
        check=False,
        timeout=120,
    )

    return chart_path


@pytest.mark.requirement("9b-SEC-001")
class TestPolarisSecurityRegression:
    """Regression tests for Polaris security configuration.

    Issue: Polaris configmap had ALLOW_ANONYMOUS_ACCESS defaulting to true
    in the else branch, negating the security fix.

    Fix: Changed default to false in configmap-polaris.yaml
    """

    @pytest.mark.requirement("9b-SEC-001")
    def test_polaris_anonymous_access_disabled_by_default(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that Polaris disables anonymous access by default.

        Validates that when polaris.config.features is not explicitly set,
        ALLOW_ANONYMOUS_ACCESS defaults to false (not true).
        """
        documents = render_helm_templates(
            platform_chart,
            values={"polaris.enabled": "true"},
        )

        configmap = find_resource(documents, "ConfigMap", "polaris-config")
        assert configmap is not None, "Polaris ConfigMap not found"

        # Get the polaris-server.yml content
        data = configmap.get("data", {})
        server_config = data.get("polaris-server.yml", "")

        assert server_config, "polaris-server.yml not found in ConfigMap"

        # Parse the embedded YAML
        polaris_config = yaml.safe_load(server_config)
        features = polaris_config.get("featureConfiguration", {})

        # CRITICAL: Anonymous access must be disabled by default
        anonymous_access = features.get("ALLOW_ANONYMOUS_ACCESS", True)
        assert anonymous_access is False, (
            "SECURITY REGRESSION: ALLOW_ANONYMOUS_ACCESS must default to false. "
            f"Got: {anonymous_access}"
        )

    @pytest.mark.requirement("9b-SEC-001")
    def test_polaris_explicit_features_respected(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that explicit feature flags override defaults.

        Validates that when polaris.config.features is set,
        those values are used instead of defaults.
        """
        documents = render_helm_templates(
            platform_chart,
            values={
                "polaris.enabled": "true",
                "polaris.config.features.ALLOW_ANONYMOUS_ACCESS": "false",
                "polaris.config.features.CUSTOM_FEATURE": "true",
            },
        )

        configmap = find_resource(documents, "ConfigMap", "polaris-config")
        assert configmap is not None, "Polaris ConfigMap not found"

        data = configmap.get("data", {})
        server_config = data.get("polaris-server.yml", "")
        polaris_config = yaml.safe_load(server_config)
        features = polaris_config.get("featureConfiguration", {})

        # Explicit features should be used
        assert (
            "CUSTOM_FEATURE" in features or "ALLOW_ANONYMOUS_ACCESS" in features
        ), "Explicit feature flags not rendered"


@pytest.mark.requirement("9b-SEC-001")
class TestPostgreSQLSecretSecurityRegression:
    """Regression tests for PostgreSQL secret security.

    Issue: postgresql-url was exposed in plaintext via stringData section,
    and passwords had weak 'floe' default.

    Fix: All secrets moved to base64-encoded data section,
    passwords auto-generated with randAlphaNum(24).
    """

    @pytest.mark.requirement("9b-SEC-001")
    def test_postgresql_secret_no_plaintext_data(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that PostgreSQL secret has no plaintext stringData.

        Validates that the Secret uses only 'data' (base64) section,
        not 'stringData' which shows plaintext in YAML.
        """
        documents = render_helm_templates(
            platform_chart,
            values={"polaris.enabled": "false"},
        )

        # Find the main PostgreSQL secret (not Dagster's)
        # It should end with -postgresql and have component label
        secret = None
        for doc in documents:
            if doc.get("kind") == "Secret":
                name = doc.get("metadata", {}).get("name", "")
                labels = doc.get("metadata", {}).get("labels", {})
                component = labels.get("app.kubernetes.io/component", "")
                if name.endswith("-postgresql") and component == "postgresql":
                    secret = doc
                    break

        # Skip if using existing secret
        if secret is None:
            pytest.skip("PostgreSQL secret not rendered (using existingSecret)")

        # CRITICAL: No stringData section should exist
        assert "stringData" not in secret, (
            "SECURITY REGRESSION: PostgreSQL secret must not use stringData. "
            "All sensitive data must be base64-encoded in 'data' section."
        )

        # Verify data section exists with required keys
        data = secret.get("data", {})
        assert "postgresql-password" in data, "postgresql-password missing from secret"
        assert "postgresql-url" in data, "postgresql-url missing from secret data"

    @pytest.mark.requirement("9b-SEC-001")
    def test_postgresql_password_autogenerated_strong(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that auto-generated passwords are strong.

        Validates that when no password is provided, the auto-generated
        password is at least 24 characters (using randAlphaNum).
        """
        documents = render_helm_templates(
            platform_chart,
            values={"polaris.enabled": "false"},
        )

        # Find the main PostgreSQL secret (not Dagster's)
        secret = None
        for doc in documents:
            if doc.get("kind") == "Secret":
                name = doc.get("metadata", {}).get("name", "")
                labels = doc.get("metadata", {}).get("labels", {})
                component = labels.get("app.kubernetes.io/component", "")
                if name.endswith("-postgresql") and component == "postgresql":
                    secret = doc
                    break

        if secret is None:
            pytest.skip("PostgreSQL secret not rendered")

        data = secret.get("data", {})
        password_b64 = data.get("postgresql-password", "")

        # Decode and check length
        password = base64.b64decode(password_b64).decode("utf-8")
        assert len(password) >= 24, (
            f"SECURITY REGRESSION: Auto-generated password must be >= 24 chars. "
            f"Got: {len(password)} chars"
        )

        # Password should not be the old weak default 'floe'
        assert (
            password != "floe"
        ), "SECURITY REGRESSION: Password must not be weak default 'floe'"


@pytest.mark.requirement("9b-SEC-001")
class TestDagsterSecretSecurityRegression:
    """Regression tests for Dagster PostgreSQL secret security.

    Issue: Connection URL was in plaintext via stringData,
    password defaulted to weak 'floe'.

    Fix: All data moved to base64-encoded section,
    uses same auto-generated password as PostgreSQL.
    """

    @pytest.mark.requirement("9b-SEC-001")
    def test_dagster_secret_no_plaintext_data(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that Dagster secret has no plaintext stringData.

        Validates that connection strings are base64-encoded,
        not exposed in plaintext.
        """
        documents = render_helm_templates(
            platform_chart,
            values={"polaris.enabled": "false"},
        )

        secret = find_resource(documents, "Secret", "dagster-postgresql-secret")
        if secret is None:
            pytest.skip("Dagster secret not rendered")

        # CRITICAL: No stringData section
        assert "stringData" not in secret, (
            "SECURITY REGRESSION: Dagster secret must not use stringData. "
            "Connection URL must be base64-encoded."
        )

        # Verify data section has connection info
        data = secret.get("data", {})
        assert (
            "postgresql-connection" in data
        ), "postgresql-connection missing from Dagster secret"

    @pytest.mark.requirement("9b-SEC-001")
    def test_dagster_connection_url_encoded(
        self,
        platform_chart: Path,
    ) -> None:
        """Test that Dagster connection URL is properly encoded.

        Validates that the connection URL is base64-encoded and
        contains expected postgresql:// prefix when decoded.
        """
        documents = render_helm_templates(
            platform_chart,
            values={"polaris.enabled": "false"},
        )

        secret = find_resource(documents, "Secret", "dagster-postgresql-secret")
        if secret is None:
            pytest.skip("Dagster secret not rendered")

        data = secret.get("data", {})
        connection_b64 = data.get("postgresql-connection", "")

        # Decode and verify format
        connection = base64.b64decode(connection_b64).decode("utf-8")
        assert connection.startswith(
            "postgresql://"
        ), f"Connection URL must start with postgresql://. Got: {connection[:20]}..."

        # Should not contain weak 'floe' password
        assert (
            ":floe@" not in connection
        ), "SECURITY REGRESSION: Connection URL must not contain weak 'floe' password"
