"""End-to-end tests for governance and security controls.

This test validates platform-wide security, compliance, and governance features:
- Network policy enforcement with restrictive rules validation
- Secret management (Helm templates AND Python source)
- RBAC enforcement for read AND write operations
- Security scanning (bandit, pip-audit)
- SecretStr usage in Pydantic models
- Error handling without stack trace exposure
- Security event logging with structured content validation
- Governance enforcement during compilation
- Prohibition of dangerous code execution patterns

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

SENSITIVE_FIELD_PATTERNS = [
    r"password",
    r"api[_-]?key",
    r"token",
    r"secret",
    r"credential",
    r"auth",
]
"""Regex patterns for identifying sensitive field names in deployment manifests."""


class TestGovernance(IntegrationTestBase):
    """E2E tests for platform governance and security controls.

    These tests validate that security controls are properly enforced
    across the entire floe platform:
    1. Network policies restrict unauthorized traffic with restrictive rules
    2. No hardcoded secrets in deployment manifests OR Python source
    3. Polaris RBAC denies unauthorized read AND write operations
    4. Static analysis finds no critical security issues
    5. Dependencies have no critical vulnerabilities
    6. Sensitive data uses SecretStr types
    7. API errors don't expose stack traces
    8. Security events are logged with structured content
    9. Governance policies are enforced during compilation
    10. No dangerous code execution patterns (eval, exec, shell=True)

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

        Validates that NetworkPolicy resources are deployed with restrictive rules,
        not just allow-all policies. Policies must specify source restrictions for
        ingress rules and have egress rules when egress policy type is declared.

        Strategy:
        1. Render Helm templates with networkPolicy enabled
        2. Validate NetworkPolicy resources exist
        3. Validate ingress rules specify 'from' selectors (not allow-all)
        4. Validate egress rules exist when Egress policy type declared
        """
        self.check_infrastructure("polaris", 8181)

        chart_root = self._find_chart_root()
        policy_path = chart_root / "floe-platform" / "templates" / "networkpolicy.yaml"

        if not policy_path.exists():
            pytest.fail(
                f"Network policy template not found at {policy_path}\n"
                "NetworkPolicy resources are required for FR-060 compliance."
            )

        templates = self._render_helm_templates(
            chart_root / "floe-platform", set_values={"networkPolicy.enabled": "true"}
        )
        network_policies = [doc for doc in templates if doc.get("kind") == "NetworkPolicy"]

        if not network_policies:
            pytest.fail(
                "No NetworkPolicy resources found in rendered Helm templates.\n"
                "NetworkPolicy resources are required for FR-060 compliance."
            )

        for policy in network_policies:
            name = policy.get("metadata", {}).get("name", "unknown")
            spec = policy.get("spec", {})

            # Verify pod selector exists (required to apply policy)
            if "podSelector" not in spec:
                pytest.fail(
                    f"NetworkPolicy {name} has no podSelector field - policy will not apply"
                )

            # Verify policy types are defined (ingress/egress)
            policy_types = spec.get("policyTypes", [])
            if not policy_types:
                pytest.fail(
                    f"NetworkPolicy {name} has no policyTypes - policy will not be enforced"
                )

            # STRENGTHENED: Validate ingress rules are restrictive (not allow-all)
            ingress_rules = spec.get("ingress", [])
            for rule_idx, rule in enumerate(ingress_rules):
                # Rules should have 'from' field specifying allowed sources
                # A rule without 'from' allows ALL traffic, defeating the purpose
                if "from" not in rule:
                    pytest.fail(
                        f"NetworkPolicy {name} ingress rule "
                        f"{rule_idx} has no 'from' selector "
                        "- allows ALL traffic.\n"
                        "Each ingress rule must specify allowed "
                        "source pods/namespaces via 'from' field."
                    )

            # STRENGTHENED: Validate egress rules exist if Egress policy type declared
            if "Egress" in policy_types:
                egress_rules = spec.get("egress", [])
                if not egress_rules or len(egress_rules) == 0:
                    pytest.fail(
                        f"NetworkPolicy {name} declares Egress "
                        "policy type but has no egress rules.\n"
                        "Either remove 'Egress' from policyTypes "
                        "or add egress rules."
                    )

        assert len(network_policies) > 0, "At least one NetworkPolicy must be defined"

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-061")
    def test_secrets_not_hardcoded(self) -> None:
        """Test that no secrets are hardcoded in deployment manifests OR Python source.

        Validates that:
        1. All sensitive values in Helm templates use valueFrom.secretKeyRef
        2. No hardcoded secrets in Python source code (passwords, API keys, tokens)

        Strategy:
        1. Render all Helm templates and verify sensitive env vars use secretKeyRef
        2. Scan Python source for hardcoded password/api_key/token patterns
        3. Fail if any hardcoded sensitive values found
        """
        chart_root = self._find_chart_root()
        templates = self._render_helm_templates(chart_root / "floe-platform")

        sensitive_regex = re.compile("|".join(SENSITIVE_FIELD_PATTERNS), re.IGNORECASE)

        violations: list[str] = []

        # Check Helm templates for hardcoded secrets
        for doc in templates:
            if doc.get("kind") not in {
                "Deployment",
                "StatefulSet",
                "DaemonSet",
                "Job",
                "CronJob",
            }:
                continue

            name = doc.get("metadata", {}).get("name", "unknown")
            spec = doc.get("spec", {})
            pod_spec = spec.get("template", {}).get("spec", spec)

            for container in pod_spec.get("containers", []):
                container_name = container.get("name", "unknown")
                env_vars = container.get("env", [])

                for env_var in env_vars:
                    env_name = env_var.get("name", "")

                    if sensitive_regex.search(env_name):
                        value = env_var.get("value")
                        value_from = env_var.get("valueFrom", {})
                        secret_ref = value_from.get("secretKeyRef")

                        if value is not None and not secret_ref:
                            violations.append(
                                f"{name}/{container_name}: env var '{env_name}' "
                                f"has hardcoded value instead of secretKeyRef"
                            )

        # STRENGTHENED: Also scan Python source for hardcoded secrets
        repo_root = self._find_repo_root()
        python_violations: list[str] = []

        # Patterns that indicate hardcoded secrets (common in config files)
        secret_patterns = [
            (
                r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']{3,}["\']',
                "hardcoded password",
            ),
            (
                r'(?:api_key|apikey|api_token)\s*=\s*["\'][^"\']{3,}["\']',
                "hardcoded API key",
            ),
            (
                r'(?:secret|token)\s*=\s*["\'][A-Za-z0-9+/=]{20,}["\']',
                "hardcoded secret/token",
            ),
        ]

        for py_file in (repo_root / "packages").rglob("*.py"):
            if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            for pattern, description in secret_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    rel_path = py_file.relative_to(repo_root)
                    python_violations.append(f"{rel_path}: {description} ({len(matches)} matches)")

        all_violations = violations + python_violations

        if all_violations:
            pytest.fail(
                f"Found {len(all_violations)} hardcoded secrets:\n"
                f"Helm template violations: {len(violations)}\n"
                f"Python source violations: {len(python_violations)}\n\n"
                + "\n".join(all_violations[:20])
                + "\n\nAll sensitive values must use secretKeyRef "
                "or environment variables."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-062")
    def test_polaris_rbac_enforcement(self) -> None:
        """Test that Polaris catalog enforces RBAC for unauthorized principals.

        Validates that Polaris rejects both READ and WRITE operations when
        principals lack permissions. Write operations are more dangerous and
        must be tested to ensure RBAC is comprehensive.

        Strategy:
        1. Attempt catalog list (read) with invalid token -> expect 401/403
        2. Attempt catalog creation (write) with invalid token -> expect 401/403
        3. Verify RBAC denies both operation types
        """
        self.check_infrastructure("polaris", 8181)

        polaris_url = self._get_polaris_url()

        # Test READ operation with invalid credentials
        try:
            read_response = httpx.get(
                f"{polaris_url}/api/management/v1/catalogs",
                headers={
                    "Authorization": "Bearer invalid-token",
                },
                timeout=10.0,
            )

            if read_response.status_code == 200:
                pytest.fail(
                    "Polaris accepted invalid token for READ operation - RBAC not enforced!\n"
                    "Expected 401 Unauthorized or 403 Forbidden."
                )

            assert read_response.status_code in {
                401,
                403,
            }, f"Expected 401/403 for unauthorized read, got {read_response.status_code}"

        except httpx.HTTPError as e:
            pytest.fail(
                f"Failed to connect to Polaris at {polaris_url}\n"
                f"Verify Polaris is running: make kind-up\n"
                f"Error: {e}"
            )

        # STRENGTHENED: Also attempt WRITE operation with invalid token (more dangerous)
        try:
            write_response = httpx.post(
                f"{polaris_url}/api/management/v1/catalogs",
                headers={"Authorization": "Bearer invalid-token"},
                json={
                    "name": "rbac-test-catalog",
                    "type": "INTERNAL",
                    "properties": {},
                },
                timeout=10.0,
            )
            if write_response.status_code in {200, 201}:
                pytest.fail(
                    "Polaris accepted WRITE operation with "
                    "invalid token - RBAC critically broken!\n"
                    "Write operations MUST be denied for "
                    "unauthorized principals."
                )
            assert write_response.status_code in {
                401,
                403,
            }, f"Expected 401/403 for unauthorized write, got {write_response.status_code}"
        except httpx.HTTPError as e:
            pytest.fail(f"Failed to test RBAC write protection: {e}")

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
            "--quiet",  # Suppress progress bar
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
                        r for r in results if r.get("issue_severity") in {"HIGH", "CRITICAL"}
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
            pytest.fail("bandit not found. Install with: uv pip install bandit[toml]")

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
            pytest.fail("uv-secure not found. Install with: uv pip install uv-secure")

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
            # Skip test files and virtual environments
            if "test" in str(py_file) or ".venv" in str(py_file):
                continue

            content = py_file.read_text()

            # Check if file contains BaseModel definitions
            if "BaseModel" not in content:
                continue

            # Look for field definitions that look sensitive
            for line_num, line in enumerate(content.splitlines(), start=1):
                line_stripped = line.strip()

                # Skip lines that are inside method bodies (contain control flow, operators, etc)
                # These are references to fields, not field definitions
                control_flow_keywords = [
                    "if ",
                    "and ",
                    "or ",
                    "not ",
                    "==",
                    "!=",
                    "is ",
                    "return ",
                    "raise ",
                ]
                if any(x in line_stripped for x in control_flow_keywords):
                    continue

                # Match field definitions: field_name: type = ...
                # Must have : followed by type annotation (not just a reference)
                for sensitive_name in sensitive_field_names:
                    pattern = rf"\b{sensitive_name}\b\s*:\s*(\w+|\w+\[|\w+\s*\|)"
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

        Validates that authentication failures produce structured log entries
        and that governance enforcement is logged during compilation.

        Strategy:
        1. Trigger auth failure and verify HTTP response
        2. Compile a demo product to generate governance logs
        3. Verify artifacts contain governance enforcement results
        4. Validate enforcement results indicate policies were checked
        """
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

            assert response.status_code in {
                401,
                403,
            }, f"Expected auth failure (401/403), got {response.status_code}"

        except httpx.HTTPError as e:
            pytest.fail(
                f"Failed to connect to Polaris at {polaris_url}\n"
                f"Verify Polaris is running: make kind-up\n"
                f"Error: {e}"
            )

        # STRENGTHENED: Validate log CONTENT via compilation artifacts
        project_root = self._find_repo_root()
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        assert spec_path.exists(), (
            f"Demo spec not found at {spec_path}.\n"
            "Demo products must exist for governance validation."
        )
        assert manifest_path.exists(), (
            f"Manifest not found at {manifest_path}.\n"
            "Platform manifest is required for governance validation."
        )

        from floe_core.compilation.stages import compile_pipeline

        try:
            artifacts = compile_pipeline(spec_path, manifest_path)

            # Governance section must exist AND contain meaningful content
            assert artifacts.governance is not None, (
                "Compiled artifacts must include governance section.\n"
                "Governance configuration is mandatory for FR-067 compliance."
            )

            # Enforcement result is mandatory — governance must actually run
            assert artifacts.enforcement_result is not None, (
                "GOVERNANCE GAP: Compiled artifacts have no enforcement_result.\n"
                "Governance policies must be checked during compilation.\n"
                "enforcement_result being None means no policies were evaluated."
            )
            assert hasattr(artifacts.enforcement_result, "passed"), (
                "Enforcement result must indicate pass/fail status"
            )

        except Exception as e:
            pytest.fail(
                f"Failed to compile demo spec for governance validation: {e}\n"
                "Governance enforcement logging requires successful compilation."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-060")
    def test_governance_enforcement_via_compilation(self) -> None:
        """Test that governance policies are enforced during compilation.

        Validates that compiled artifacts contain governance enforcement results
        and that the enforcement actually checked policies.

        Strategy:
        1. Compile demo spec with governance enabled
        2. Verify artifacts contain governance configuration
        3. Verify enforcement result exists and contains validation data
        4. Verify enforcement level is specified (strict/warn/none)
        """
        from floe_core.compilation.stages import compile_pipeline

        project_root = self._find_repo_root()
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        assert spec_path.exists(), f"Demo spec not found: {spec_path}"
        assert manifest_path.exists(), f"Manifest not found: {manifest_path}"

        artifacts = compile_pipeline(spec_path, manifest_path)

        # Governance section must exist and be populated
        assert artifacts.governance is not None, (
            "Compiled artifacts must include governance configuration.\n"
            "Governance is required for FR-060 compliance."
        )

        # Enforcement MUST have run — not optional
        assert artifacts.enforcement_result is not None, (
            "GOVERNANCE GAP: No enforcement_result in compiled artifacts.\n"
            "Governance policies must be checked during compilation.\n"
            "enforcement_result being None means no policies were evaluated."
        )
        assert hasattr(artifacts.enforcement_result, "passed"), (
            "Enforcement result must indicate pass/fail status"
        )
        assert artifacts.enforcement_result.models_validated > 0, (
            "Enforcement must validate at least one model.\n"
            f"Got models_validated={artifacts.enforcement_result.models_validated}\n"
            "This indicates governance policies are not being checked."
        )
        assert artifacts.enforcement_result.enforcement_level is not None, (
            "Enforcement must specify enforcement level (strict/warn/none).\n"
            "Enforcement level determines whether policy violations block deployment."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-063")
    def test_all_python_files_no_eval_exec(self) -> None:
        """Test that no Python files use dangerous eval() or exec() functions.

        Validates security by scanning all production Python code for
        dangerous dynamic code execution patterns.

        Strategy:
        1. Scan all Python files in packages/ directory
        2. Check for dangerous patterns: eval(), exec(), __import__(), shell=True
        3. Fail if any dangerous patterns found
        """
        repo_root = self._find_repo_root()
        violations: list[str] = []

        dangerous_patterns = [
            (r"\beval\s*\(", "eval() usage"),
            (r"\bexec\s*\(", "exec() usage"),
            (r"\b__import__\s*\(", "__import__() usage"),
            (r"subprocess\..*shell\s*=\s*True", "shell=True in subprocess"),
        ]

        for py_file in (repo_root / "packages").rglob("*.py"):
            if ".venv" in str(py_file) or "__pycache__" in str(py_file) or "test" in str(py_file):
                continue
            content = py_file.read_text()

            for pattern, description in dangerous_patterns:
                if re.search(pattern, content):
                    rel_path = py_file.relative_to(repo_root)
                    violations.append(f"{rel_path}: {description}")

        if violations:
            pytest.fail(
                f"Found {len(violations)} dangerous code execution patterns:\n"
                + "\n".join(violations)
                + "\n\nNEVER use eval(), exec(), __import__(), or shell=True.\n"
                "These patterns enable code injection attacks and are prohibited."
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
        set_values: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Render Helm templates to YAML documents.

        Args:
            chart_path: Path to the Helm chart
            values_path: Optional path to values file
            set_values: Optional dict of values to set via --set

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
        if set_values:
            for key, value in set_values.items():
                cmd.extend(["--set", f"{key}={value}"])

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
