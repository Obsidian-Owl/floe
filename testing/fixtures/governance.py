"""Reusable governance test fixtures.

Provides factory functions and pytest fixtures for governance-related testing:
- GovernanceConfig presets (RBAC, scanning, network policies)
- Token validation results (valid, expired, invalid)
- Violations (RBAC, secret scanning, network policy)
- Secret findings
- Enforcement results

Example:
    >>> from testing.fixtures.governance import (
    ...     create_governance_config_all_enabled,
    ...     create_rbac_violation,
    ...     create_valid_token_result,
    ... )
    >>> config = create_governance_config_all_enabled()
    >>> assert config.rbac.enabled is True
    >>> violation = create_rbac_violation()
    >>> assert violation.policy_type == "rbac"
    >>> token_result = create_valid_token_result()
    >>> assert token_result.valid is True
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)
from floe_core.governance.types import (
    GovernanceCheckResult,
    SecretFinding,
)
from floe_core.plugins.identity import (
    TokenValidationResult,
    UserInfo,
)
from floe_core.schemas.governance import (
    NamingConfig,
    NetworkPoliciesConfig,
    QualityGatesConfig,
    RBACConfig,
    SecretScanningConfig,
)
from floe_core.schemas.manifest import GovernanceConfig

# ============================================================================
# GovernanceConfig Factory Functions
# ============================================================================


def create_governance_config_rbac_enabled() -> GovernanceConfig:
    """Create GovernanceConfig with RBAC enabled and strict enforcement.

    Returns:
        GovernanceConfig with RBAC requiring platform-engineer role
    """
    return GovernanceConfig(
        policy_enforcement_level="strict",
        rbac=RBACConfig(
            enabled=True,
            required_role="platform-engineer",
            allow_principal_fallback=True,
        ),
    )


def create_governance_config_scanning_enabled() -> GovernanceConfig:
    """Create GovernanceConfig with secret scanning enabled.

    Returns:
        GovernanceConfig with secret scanning in error mode
    """
    return GovernanceConfig(
        policy_enforcement_level="strict",
        secret_scanning=SecretScanningConfig(
            enabled=True,
            severity="error",
        ),
    )


def create_governance_config_network_enabled() -> GovernanceConfig:
    """Create GovernanceConfig with network policies enabled.

    Returns:
        GovernanceConfig with network policies in default-deny mode
    """
    return GovernanceConfig(
        policy_enforcement_level="strict",
        network_policies=NetworkPoliciesConfig(
            enabled=True,
            default_deny=True,
        ),
    )


def create_governance_config_all_enabled() -> GovernanceConfig:
    """Create GovernanceConfig with all governance features enabled.

    Returns:
        GovernanceConfig with RBAC, secret scanning, network policies, strict naming,
        and quality gates all enabled
    """
    return GovernanceConfig(
        pii_encryption="required",
        audit_logging="enabled",
        policy_enforcement_level="strict",
        data_retention_days=90,
        naming=NamingConfig(
            enforcement="strict",
            pattern="medallion",
        ),
        quality_gates=QualityGatesConfig(
            minimum_test_coverage=80,
            require_descriptions=True,
            require_column_descriptions=True,
            block_on_failure=True,
        ),
        rbac=RBACConfig(
            enabled=True,
            required_role="platform-engineer",
            allow_principal_fallback=True,
        ),
        secret_scanning=SecretScanningConfig(
            enabled=True,
            severity="error",
        ),
        network_policies=NetworkPoliciesConfig(
            enabled=True,
            default_deny=True,
        ),
    )


def create_governance_config_all_disabled() -> GovernanceConfig:
    """Create GovernanceConfig with all governance features disabled.

    Returns:
        GovernanceConfig with enforcement level off
    """
    return GovernanceConfig(
        policy_enforcement_level="off",
    )


# ============================================================================
# Token/Identity Factory Functions
# ============================================================================


def create_valid_user_info(
    subject: str = "user123",
    email: str = "engineer@example.com",
    name: str = "Platform Engineer",
    roles: list[str] | None = None,
) -> UserInfo:
    """Create valid UserInfo for testing.

    Args:
        subject: User subject identifier
        email: User email address
        name: User display name
        roles: User roles (default: platform-engineer, viewer)

    Returns:
        UserInfo with specified attributes
    """
    if roles is None:
        roles = ["platform-engineer", "viewer"]

    return UserInfo(
        subject=subject,
        email=email,
        name=name,
        roles=roles,
    )


def create_valid_token_result(
    user_info: UserInfo | None = None,
    expires_at: str = "2099-12-31T23:59:59Z",
) -> TokenValidationResult:
    """Create valid token validation result.

    Args:
        user_info: User information (default: platform engineer)
        expires_at: Token expiration timestamp

    Returns:
        TokenValidationResult indicating valid token
    """
    if user_info is None:
        user_info = create_valid_user_info()

    return TokenValidationResult(
        valid=True,
        user_info=user_info,
        expires_at=expires_at,
    )


def create_expired_token_result() -> TokenValidationResult:
    """Create expired token validation result.

    Returns:
        TokenValidationResult indicating expired token
    """
    return TokenValidationResult(
        valid=False,
        error="Token expired",
    )


def create_invalid_token_result(
    error: str = "Invalid token signature",
) -> TokenValidationResult:
    """Create invalid token validation result.

    Args:
        error: Error description

    Returns:
        TokenValidationResult indicating invalid token
    """
    return TokenValidationResult(
        valid=False,
        error=error,
    )


# ============================================================================
# Violation Factory Functions
# ============================================================================


def create_rbac_violation(
    error_code: str = "FLOE-E501",
    model_name: str = "bronze_sensitive_data",
    message: str = "No identity token or principal provided",
) -> Violation:
    """Create RBAC policy violation.

    Args:
        error_code: Error code
        model_name: Model that violated policy
        message: Violation description

    Returns:
        Violation for RBAC policy
    """
    return Violation(
        error_code=error_code,
        severity="error",
        policy_type="rbac",
        model_name=model_name,
        message=message,
        expected="Identity token or principal name in tags",
        actual="Neither token nor principal provided",
        suggestion="Provide identity token via --token or principal via model tags",
        documentation_url="https://docs.floe.dev/governance/rbac",
        column_name=None,
        downstream_impact=None,
        first_detected=None,
        occurrences=None,
        override_applied=None,
    )


def create_secret_violation(
    error_code: str = "FLOE-E601",
    model_name: str = "bronze_customers",
    message: str = "AWS Access Key ID detected in source",
) -> Violation:
    """Create secret scanning policy violation.

    Args:
        error_code: Error code
        model_name: Model that violated policy
        message: Violation description

    Returns:
        Violation for secret scanning policy
    """
    return Violation(
        error_code=error_code,
        severity="error",
        policy_type="secret_scanning",
        model_name=model_name,
        message=message,
        expected="No hardcoded secrets in source code",
        actual="AWS Access Key ID pattern detected",
        suggestion="Use environment variables or secret management service",
        documentation_url="https://docs.floe.dev/governance/secret-scanning",
        column_name=None,
        downstream_impact=None,
        first_detected=None,
        occurrences=None,
        override_applied=None,
    )


def create_network_violation(
    error_code: str = "FLOE-E700",
    model_name: str = "bronze_external_api",
    message: str = "Network policy check failed",
) -> Violation:
    """Create network policy violation.

    Args:
        error_code: Error code
        model_name: Model that violated policy
        message: Violation description

    Returns:
        Violation for network policy
    """
    return Violation(
        error_code=error_code,
        severity="error",
        policy_type="network_policy",
        model_name=model_name,
        message=message,
        expected="Egress allowed by network policy",
        actual="No matching egress rule found",
        suggestion="Add egress rule or disable default-deny",
        documentation_url="https://docs.floe.dev/governance/network-policies",
        column_name=None,
        downstream_impact=None,
        first_detected=None,
        occurrences=None,
        override_applied=None,
    )


def create_policy_violation(
    error_code: str = "FLOE-E600",
    model_name: str = "bronze_customers",
    message: str = "Custom governance policy violated",
) -> Violation:
    """Create custom policy violation.

    Args:
        error_code: Error code
        model_name: Model that violated policy
        message: Violation description

    Returns:
        Violation for custom policy
    """
    return Violation(
        error_code=error_code,
        severity="error",
        policy_type="custom",
        model_name=model_name,
        message=message,
        expected="Model complies with custom governance rule",
        actual="Model violates custom governance rule",
        suggestion="Review custom_rules in manifest.yaml",
        documentation_url="https://docs.floe.dev/governance/custom-rules",
        column_name=None,
        downstream_impact=None,
        first_detected=None,
        occurrences=None,
        override_applied=None,
    )


# ============================================================================
# EnforcementResult Factory Functions
# ============================================================================


def create_passing_enforcement_result() -> EnforcementResult:
    """Create passing enforcement result with no violations.

    Returns:
        EnforcementResult with passed=True
    """
    return EnforcementResult(
        passed=True,
        violations=[],
        summary=EnforcementSummary(
            total_models=5,
            models_validated=5,
            naming_violations=0,
            coverage_violations=0,
            documentation_violations=0,
            semantic_violations=0,
            custom_rule_violations=0,
            overrides_applied=0,
            contract_violations=0,
            rbac_violations=0,
            secret_violations=0,
            network_policy_violations=0,
            duration_ms=100,
        ),
        enforcement_level="strict",
        manifest_version="1.0.0",
        timestamp=datetime.now(tz=timezone.utc),
    )


def create_failing_enforcement_result(
    violations: list[Violation] | None = None,
) -> EnforcementResult:
    """Create failing enforcement result with violations.

    Args:
        violations: List of violations (default: 1 RBAC + 1 secret)

    Returns:
        EnforcementResult with passed=False
    """
    if violations is None:
        violations = [
            create_rbac_violation(),
            create_secret_violation(),
        ]

    rbac_count = sum(1 for v in violations if v.policy_type == "rbac")
    secret_count = sum(1 for v in violations if v.policy_type == "secret_scanning")
    network_count = sum(1 for v in violations if v.policy_type == "network_policy")
    custom_count = sum(1 for v in violations if v.policy_type == "custom")

    return EnforcementResult(
        passed=False,
        violations=violations,
        summary=EnforcementSummary(
            total_models=5,
            models_validated=5,
            naming_violations=0,
            coverage_violations=0,
            documentation_violations=0,
            semantic_violations=0,
            custom_rule_violations=custom_count,
            overrides_applied=0,
            contract_violations=0,
            rbac_violations=rbac_count,
            secret_violations=secret_count,
            network_policy_violations=network_count,
            duration_ms=150,
        ),
        enforcement_level="strict",
        manifest_version="1.0.0",
        timestamp=datetime.now(tz=timezone.utc),
    )


# ============================================================================
# SecretFinding Factory Functions
# ============================================================================


def create_aws_key_finding(
    file_path: str = "src/config/database.py",
    line_number: int = 42,
) -> SecretFinding:
    """Create AWS access key secret finding.

    Args:
        file_path: Path to file containing secret
        line_number: Line number where secret was found

    Returns:
        SecretFinding for AWS access key
    """
    return SecretFinding(
        file_path=file_path,
        line_number=line_number,
        pattern_name="AWS Access Key ID",
        error_code="FLOE-E601",
        matched_content="AKIA***REDACTED***",
        severity="error",
        match_context='aws_access_key_id = "AKIA***REDACTED***"',
        confidence="high",
        allow_secrets=False,
    )


def create_password_finding(
    file_path: str = "src/config/settings.py",
    line_number: int = 15,
) -> SecretFinding:
    """Create hardcoded password secret finding.

    Args:
        file_path: Path to file containing secret
        line_number: Line number where secret was found

    Returns:
        SecretFinding for hardcoded password
    """
    return SecretFinding(
        file_path=file_path,
        line_number=line_number,
        pattern_name="Hardcoded Password",
        error_code="FLOE-E602",
        matched_content="test_placeholder_value",
        severity="error",
        match_context='password = "test_placeholder_value"',
        confidence="high",
        allow_secrets=False,
    )


def create_api_token_finding(
    file_path: str = "src/api/client.py",
    line_number: int = 8,
) -> SecretFinding:
    """Create API token secret finding.

    Args:
        file_path: Path to file containing secret
        line_number: Line number where secret was found

    Returns:
        SecretFinding for API token
    """
    return SecretFinding(
        file_path=file_path,
        line_number=line_number,
        pattern_name="Generic API Token",
        error_code="FLOE-E603",
        matched_content="sk_test_placeholder_token_value",
        severity="error",
        match_context='api_token = "sk_test_placeholder_token_value"',
        confidence="medium",
        allow_secrets=False,
    )


# ============================================================================
# GovernanceCheckResult Factory Functions
# ============================================================================


def create_governance_check_result(
    check_type: str = "rbac",
    violations: list[Violation] | None = None,
    duration_ms: int = 50,
    metadata: dict[str, Any] | None = None,
) -> GovernanceCheckResult:
    """Create governance check result.

    Args:
        check_type: Type of governance check performed
        violations: List of violations found (default: empty)
        duration_ms: Check duration in milliseconds
        metadata: Additional check metadata

    Returns:
        GovernanceCheckResult with specified attributes
    """
    if violations is None:
        violations = []
    if metadata is None:
        metadata = {}

    return GovernanceCheckResult(
        check_type=check_type,
        violations=violations,
        duration_ms=duration_ms,
        metadata=metadata,
    )


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture
def governance_config_all_enabled() -> GovernanceConfig:
    """Pytest fixture for GovernanceConfig with all features enabled.

    Returns:
        GovernanceConfig with all governance features enabled
    """
    return create_governance_config_all_enabled()


@pytest.fixture
def governance_config_rbac_enabled() -> GovernanceConfig:
    """Pytest fixture for GovernanceConfig with RBAC enabled.

    Returns:
        GovernanceConfig with RBAC enabled
    """
    return create_governance_config_rbac_enabled()


@pytest.fixture
def governance_config_scanning_enabled() -> GovernanceConfig:
    """Pytest fixture for GovernanceConfig with secret scanning enabled.

    Returns:
        GovernanceConfig with secret scanning enabled
    """
    return create_governance_config_scanning_enabled()


@pytest.fixture
def governance_config_network_enabled() -> GovernanceConfig:
    """Pytest fixture for GovernanceConfig with network policies enabled.

    Returns:
        GovernanceConfig with network policies enabled
    """
    return create_governance_config_network_enabled()


@pytest.fixture
def governance_config_all_disabled() -> GovernanceConfig:
    """Pytest fixture for GovernanceConfig with all features disabled.

    Returns:
        GovernanceConfig with all features disabled
    """
    return create_governance_config_all_disabled()


@pytest.fixture
def valid_token_result() -> TokenValidationResult:
    """Pytest fixture for valid token validation result.

    Returns:
        TokenValidationResult indicating valid token
    """
    return create_valid_token_result()


@pytest.fixture
def expired_token_result() -> TokenValidationResult:
    """Pytest fixture for expired token validation result.

    Returns:
        TokenValidationResult indicating expired token
    """
    return create_expired_token_result()


@pytest.fixture
def invalid_token_result() -> TokenValidationResult:
    """Pytest fixture for invalid token validation result.

    Returns:
        TokenValidationResult indicating invalid token
    """
    return create_invalid_token_result()


@pytest.fixture
def passing_enforcement_result() -> EnforcementResult:
    """Pytest fixture for passing enforcement result.

    Returns:
        EnforcementResult with no violations
    """
    return create_passing_enforcement_result()


@pytest.fixture
def failing_enforcement_result() -> EnforcementResult:
    """Pytest fixture for failing enforcement result.

    Returns:
        EnforcementResult with violations
    """
    return create_failing_enforcement_result()


@pytest.fixture
def valid_user_info() -> UserInfo:
    """Pytest fixture for valid user information.

    Returns:
        UserInfo for platform engineer
    """
    return create_valid_user_info()


@pytest.fixture
def rbac_violation() -> Violation:
    """Pytest fixture for RBAC violation.

    Returns:
        Violation for RBAC policy
    """
    return create_rbac_violation()


@pytest.fixture
def secret_violation() -> Violation:
    """Pytest fixture for secret scanning violation.

    Returns:
        Violation for secret scanning policy
    """
    return create_secret_violation()


@pytest.fixture
def network_violation() -> Violation:
    """Pytest fixture for network policy violation.

    Returns:
        Violation for network policy
    """
    return create_network_violation()


@pytest.fixture
def aws_key_finding() -> SecretFinding:
    """Pytest fixture for AWS key secret finding.

    Returns:
        SecretFinding for AWS access key
    """
    return create_aws_key_finding()


@pytest.fixture
def password_finding() -> SecretFinding:
    """Pytest fixture for password secret finding.

    Returns:
        SecretFinding for hardcoded password
    """
    return create_password_finding()


@pytest.fixture
def api_token_finding() -> SecretFinding:
    """Pytest fixture for API token secret finding.

    Returns:
        SecretFinding for API token
    """
    return create_api_token_finding()
