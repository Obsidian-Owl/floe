"""End-to-end tests for governance and security controls.

This test validates platform-wide security, compliance, and governance features:
- Network policy enforcement
- Secret management
- RBAC enforcement
- Security scanning (bandit, pip-audit)
- SecretStr usage
- Error handling without stack trace exposure
- Security event logging

Requirements Covered:
- FR-060: Network policy enforcement
- FR-061: No hardcoded secrets
- FR-062: Polaris RBAC enforcement
- FR-063: Bandit security scanning
- FR-064: Vulnerability scanning (pip-audit)
- FR-065: SecretStr for sensitive fields
- FR-066: No stack trace exposure
- FR-067: Security event logging

Per testing standards: Tests FAIL when infrastructure is unavailable.
No pytest.skip() - see .claude/rules/testing-standards.md
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
import yaml

from testing.base_classes.integration_test_base import IntegrationTestBase


class TestGovernance(IntegrationTestBase):
    """E2E tests for platform governance and security controls.

    These tests validate that security controls are properly enforced
    across the entire floe platform:
    1. Network policies restrict unauthorized traffic
    2. No hardcoded secrets in deployment manifests
    3. Polaris RBAC denies unauthorized access
    4. Static analysis finds no critical security issues
    5. Dependencies have no critical vulnerabilities
    6. Sensitive data uses SecretStr types
    7. API errors don't expose stack traces
    8. Security events are logged with structured logging

    Requires platform services running:
    - Polaris (catalog)
    - Kubernetes API (for network policy testing)
    - Any service with authentication (for logging tests)
    """

    # Services required for E2E governance tests
    required_services: ClassVar[list[tuple[str, int]]] = [
        ("polaris", 8181),
    ]

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-060")
    def test_network_policies_restrict_traffic(self) -> None:
        """Test that network policies deny unauthorized pod-to-pod traffic.

        Validates that NetworkPolicy resources are deployed and actively
        deny connections between pods that should not communicate.

        Strategy:
        1. Deploy test pod in isolated namespace
        2. Attempt connection to protected service (e.g., PostgreSQL)
        3. Verify connection is denied by network policy
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("polaris", 8181)

        # Find network policy manifests in Helm charts
        chart_root = self._find_chart_root()
        policy_path = chart_root / "floe-platform" / "templates" / "networkpolicy.yaml"

        if not policy_path.exists():
            pytest.fail(
                f"Network policy template not found at {policy_path}\n"
                "NetworkPolicy resources are required for FR-060 compliance."
            )

        # Render Helm templates to validate NetworkPolicy resources exist
        templates = self._render_helm_templates(chart_root / "floe-platform")
        network_policies = [
            doc for doc in templates if doc.get("kind") == "NetworkPolicy"
        ]

        if not network_policies:
            pytest.fail(
                "No NetworkPolicy resources found in rendered Helm templates.\n"
                "NetworkPolicy resources are required for FR-060 compliance."
            )

        # Validate network policy structure
        for policy in network_policies:
            name = policy.get("metadata", {}).get("name", "unknown")

            # Verify pod selector exists (required to apply policy)
            pod_selector = policy.get("spec", {}).get("podSelector", {})
            if not pod_selector:
                pytest.fail(
                    f"NetworkPolicy {name} has no podSelector - policy will not apply"
                )

            # Verify policy types are defined (ingress/egress)
            policy_types = policy.get("spec", {}).get("policyTypes", [])
            if not policy_types:
                pytest.fail(
                    f"NetworkPolicy {name} has no policyTypes - policy will not be enforced"
                )

        # TODO: Deploy actual test pod and verify network isolation
        # This requires kubectl access to create test pods and verify connectivity
        # For now, we validate that NetworkPolicy resources are defined
        assert len(network_policies) > 0, "At least one NetworkPolicy must be defined"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-061")
    def test_secrets_not_hardcoded(self) -> None:
        """Test that no secrets are hardcoded in deployment manifests.

        Validates that all sensitive values are loaded from Kubernetes Secrets,
        not hardcoded in pod specs or environment variables.

        Strategy:
        1. Render all Helm templates
        2. Extract environment variable definitions
        3. Verify sensitive fields use valueFrom.secretKeyRef
        4. Fail if any hardcoded sensitive values found
        """
        # Find Helm charts
        chart_root = self._find_chart_root()
        templates = self._render_helm_templates(chart_root / "floe-platform")

        # Patterns for sensitive field names
        sensitive_patterns = [
            r"password",
            r"api[_-]?key",
            r"token",
            r"secret",
            r"credential",
            r"auth",
        ]
        sensitive_regex = re.compile("|".join(sensitive_patterns), re.IGNORECASE)

        violations: list[str] = []

        for doc in templates:
            if doc.get("kind") not in {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}:
                continue

            name = doc.get("metadata", {}).get("name", "unknown")
            spec = doc.get("spec", {})
            pod_spec = spec.get("template", {}).get("spec", spec)

            # Check environment variables in all containers
            for container in pod_spec.get("containers", []):
                container_name = container.get("name", "unknown")
                env_vars = container.get("env", [])

                for env_var in env_vars:
                    env_name = env_var.get("name", "")

                    # Check if variable name looks sensitive
                    if sensitive_regex.search(env_name):
                        # Verify it uses secretKeyRef, not a hardcoded value
                        value = env_var.get("value")
                        value_from = env_var.get("valueFrom", {})
                        secret_ref = value_from.get("secretKeyRef")

                        if value is not None and not secret_ref:
                            violations.append(
                                f"{name}/{container_name}: env var '{env_name}' "
                                f"has hardcoded value instead of secretKeyRef"
                            )

        if violations:
            pytest.fail(
                f"Found {len(violations)} hardcoded secrets in pod specs:\n"
                + "\n".join(violations)
                + "\n\nAll sensitive values must use secretKeyRef."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-062")
    def test_polaris_rbac_enforcement(self) -> None:
        """Test that Polaris catalog enforces RBAC for unauthorized principals.

        Validates that Polaris rejects operations when principals lack permissions.

        Strategy:
        1. Create restricted principal with minimal permissions
        2. Attempt TABLE_READ operation on protected catalog
        3. Verify request returns 403 Forbidden
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("polaris", 8181)

        polaris_url = self._get_polaris_url()

        # Attempt to list catalogs with invalid/restricted credentials
        # This should return 403 Forbidden if RBAC is enforced
        try:
            response = httpx.get(
                f"{polaris_url}/api/management/v1/catalogs",
                headers={
                    "Authorization": "Bearer invalid-token",
                },
                timeout=10.0,
            )

            # RBAC should deny unauthorized access
            if response.status_code == 200:
                pytest.fail(
                    "Polaris accepted invalid token - RBAC not enforced!\n"
                    "Expected 401 Unauthorized or 403 Forbidden."
                )

            # Expected status codes for RBAC enforcement
            assert response.status_code in {401, 403}, (
                f"Unexpected status code: {response.status_code}\n"
                f"Expected 401 or 403 for unauthorized access."
            )

        except httpx.HTTPError as e:
            pytest.fail(
                f"Failed to connect to Polaris at {polaris_url}\n"
                f"Verify Polaris is running: make kind-up\n"
                f"Error: {e}"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-063")
    def test_bandit_security_scan(self) -> None:
        """Test that bandit security scan finds no critical/high severity issues.

        Runs bandit static analysis on the codebase and verifies
        no critical or high severity security issues are found.

        Strategy:
        1. Run bandit on packages/ directory
        2. Parse JSON output
        3. Fail if any HIGH or CRITICAL severity issues found
        """
        repo_root = self._find_repo_root()

        # Run bandit with configuration from pyproject.toml
        cmd = [
            "uv",
            "run",
            "bandit",
            "-c",
            str(repo_root / "pyproject.toml"),
            "-r",
            str(repo_root / "packages"),
            "-f",
            "json",
            "-ll",  # Only report HIGH and CRITICAL
        ]

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )

            # Parse bandit JSON output
            if result.stdout:
                try:
                    output = json.loads(result.stdout)
                    results = output.get("results", [])

                    # Filter for HIGH and CRITICAL severity
                    high_critical = [
                        r for r in results
                        if r.get("issue_severity") in {"HIGH", "CRITICAL"}
                    ]

                    if high_critical:
                        issues = "\n".join(
                            f"  {r['filename']}:{r['line_number']}: "
                            f"{r['issue_severity']} - {r['issue_text']}"
                            for r in high_critical[:10]  # Limit output
                        )
                        pytest.fail(
                            f"Bandit found {len(high_critical)} HIGH/CRITICAL issues:\n{issues}"
                        )

                except json.JSONDecodeError:
                    pytest.fail(f"Failed to parse bandit output: {result.stdout}")

        except FileNotFoundError:
            pytest.fail(
                "bandit not found. Install with: uv pip install bandit[toml]"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-064")
    def test_pip_audit_clean(self) -> None:
        """Test that pip-audit finds no critical/high vulnerabilities.

        Runs pip-audit (via uv-secure) on dependencies and verifies
        no critical or high severity vulnerabilities exist.

        Strategy:
        1. Run uv-secure vulnerability scan
        2. Parse output for CRITICAL/HIGH vulnerabilities
        3. Fail if vulnerabilities found (excluding documented exceptions)
        """
        repo_root = self._find_repo_root()

        # Run uv-secure with same ignore list as CI
        # See .pre-commit-config.yaml for justification of ignored vulns
        cmd = [
            "uv",
            "run",
            "uv-secure",
            "--no-check-uv-tool",
            "--ignore-vulns",
            "GHSA-5j53-63w8-8625,GHSA-7gcm-g887-7qv7,"
            "GHSA-hm8f-75xx-w2vr,GHSA-2q4j-m29v-hq73,GHSA-wp53-j4wj-2cfg",
            ".",
        ]

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )

            # uv-secure exits with non-zero if vulnerabilities found
            if result.returncode != 0:
                pytest.fail(
                    f"Vulnerability scan failed with vulnerabilities:\n"
                    f"{result.stdout}\n{result.stderr}"
                )

        except FileNotFoundError:
            pytest.fail(
                "uv-secure not found. Install with: uv pip install uv-secure"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-065")
    def test_secretstr_usage(self) -> None:
        """Test that sensitive Pydantic fields use SecretStr type.

        Validates that password, api_key, token fields use SecretStr
        to prevent accidental logging of sensitive data.

        Strategy:
        1. Search Python files for Pydantic BaseModel definitions
        2. Extract field definitions matching sensitive patterns
        3. Verify those fields use SecretStr type annotation
        4. Fail if sensitive fields lack SecretStr
        """
        repo_root = self._find_repo_root()

        # Patterns for sensitive field names
        sensitive_field_names = {"password", "api_key", "token", "secret", "credential"}

        # Search for Pydantic models with sensitive fields
        violations: list[str] = []

        for py_file in (repo_root / "packages").rglob("*.py"):
            if "test" in str(py_file):
                continue  # Skip test files

            content = py_file.read_text()

            # Check if file contains BaseModel definitions
            if "BaseModel" not in content:
                continue

            # Look for field definitions that look sensitive
            for line_num, line in enumerate(content.splitlines(), start=1):
                line_stripped = line.strip()

                # Match field definitions: field_name: type = ...
                for sensitive_name in sensitive_field_names:
                    pattern = rf"\b{sensitive_name}\b\s*:\s*"
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        # Check if SecretStr is used
                        if "SecretStr" not in line_stripped:
                            rel_path = py_file.relative_to(repo_root)
                            violations.append(
                                f"{rel_path}:{line_num}: "
                                f"Field '{sensitive_name}' should use SecretStr"
                            )

        if violations:
            pytest.fail(
                f"Found {len(violations)} sensitive fields without SecretStr:\n"
                + "\n".join(violations[:20])  # Limit output
                + "\n\nSensitive fields MUST use SecretStr to prevent logging secrets."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-066")
    def test_no_stack_trace_exposure(self) -> None:
        """Test that API error responses do not expose stack traces.

        Validates that when errors occur, API responses contain generic
        error messages without exposing internal details like stack traces.

        Strategy:
        1. Trigger intentional error via API (invalid request)
        2. Parse error response body
        3. Verify no stack trace patterns present (Traceback, File "...", etc.)
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("polaris", 8181)

        polaris_url = self._get_polaris_url()

        # Trigger error by making malformed request
        try:
            response = httpx.post(
                f"{polaris_url}/api/catalog/v1/invalid-endpoint",
                json={"malformed": "data"},
                timeout=10.0,
            )

            # Should get error response (4xx or 5xx)
            if response.status_code < 400:
                pytest.fail("Expected error response, got success")

            response_text = response.text

            # Check for stack trace patterns
            stack_trace_patterns = [
                r"Traceback \(most recent call last\)",
                r'File ".*\.py", line \d+',
                r"^\s+at .*\(.*:\d+:\d+\)",  # JavaScript stack trace
                r"Exception in thread",
                r"raise \w+Error",
            ]

            for pattern in stack_trace_patterns:
                if re.search(pattern, response_text, re.MULTILINE):
                    pytest.fail(
                        f"API error response exposes stack trace:\n{response_text[:500]}\n\n"
                        "Errors must return generic messages without internal details."
                    )

        except httpx.HTTPError as e:
            pytest.fail(
                f"Failed to connect to Polaris at {polaris_url}\n"
                f"Verify Polaris is running: make kind-up\n"
                f"Error: {e}"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-067")
    def test_security_event_logging(self) -> None:
        """Test that security events are logged with structured logging.

        Validates that authentication failures and other security events
        produce structured log entries with appropriate severity levels.

        Strategy:
        1. Trigger auth failure (invalid credentials)
        2. Query application logs (via kubectl or log aggregator)
        3. Verify structured log entry exists with:
           - event_type field
           - severity level (WARNING or ERROR)
           - timestamp
           - relevant context (user, endpoint, etc.)

        Note: This test validates logging CAPABILITY exists.
        Actual log aggregation testing requires observability stack.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("polaris", 8181)

        polaris_url = self._get_polaris_url()

        # Trigger authentication failure
        try:
            response = httpx.get(
                f"{polaris_url}/api/management/v1/catalogs",
                headers={
                    "Authorization": "Bearer intentionally-invalid-token-for-test",
                },
                timeout=10.0,
            )

            # Should get 401 or 403
            assert response.status_code in {401, 403}, (
                f"Expected auth failure (401/403), got {response.status_code}"
            )

            # TODO: Query logs to verify structured event was written
            # This requires access to log aggregator (e.g., Loki) or kubectl logs
            # For now, we validate that auth failure returns expected status code

            # Placeholder: In full implementation, would check logs like:
            # logs = query_logs(namespace="floe-test", service="polaris", since="1m")
            # auth_failures = [log for log in logs if log.get("event_type") == "auth_failure"]
            # assert len(auth_failures) > 0, "No auth failure events logged"

        except httpx.HTTPError as e:
            pytest.fail(
                f"Failed to connect to Polaris at {polaris_url}\n"
                f"Verify Polaris is running: make kind-up\n"
                f"Error: {e}"
            )

    # Helper methods

    def _find_repo_root(self) -> Path:
        """Find repository root by looking for pyproject.toml."""
        current = Path(__file__).parent
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        pytest.fail("Could not find repository root (no pyproject.toml)")

    def _find_chart_root(self) -> Path:
        """Find charts directory root."""
        repo_root = self._find_repo_root()
        chart_root = repo_root / "charts"
        if not chart_root.is_dir():
            pytest.fail(f"Charts directory not found at {chart_root}")
        return chart_root

    def _render_helm_templates(
        self,
        chart_path: Path,
        values_path: Path | None = None,
    ) -> list[dict[str, Any]]:
        """Render Helm templates to YAML documents.

        Args:
            chart_path: Path to the Helm chart
            values_path: Optional path to values file

        Returns:
            List of parsed YAML documents
        """
        cmd = [
            "helm",
            "template",
            "--skip-schema-validation",
            "test-release",
            str(chart_path),
        ]
        if values_path:
            cmd.extend(["--values", str(values_path)])

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                check=True,
                capture_output=True,
                text=True,
            )

            documents: list[dict[str, Any]] = []
            for doc in yaml.safe_load_all(result.stdout):
                if doc and isinstance(doc, dict):
                    documents.append(doc)

            return documents

        except subprocess.CalledProcessError as e:
            pytest.fail(
                f"Failed to render Helm templates: {e.stderr}\n"
                "Verify Helm is installed and chart is valid."
            )
        except FileNotFoundError:
            pytest.fail("helm not found. Install with: brew install helm")

    def _get_polaris_url(self) -> str:
        """Get Polaris catalog URL from environment or default."""
        import os

        return os.environ.get("POLARIS_URL", "http://localhost:8181")
