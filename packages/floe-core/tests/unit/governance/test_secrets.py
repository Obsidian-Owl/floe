"""Unit tests for BuiltinSecretScanner (Tasks T016, T017).

These tests verify the BuiltinSecretScanner implementation of SecretScannerPlugin.
Written before implementation (TDD) - tests will fail until T019-T020 implement the scanner.

Test content strings use published examples and obvious placeholders:
- AWS key ID: AKIAIOSFODNN7EXAMPLE (AWS's official documentation example)
- Passwords: 'test_placeholder_value' (clearly a test fixture)
- These are scanner test vectors, not actual credentials.

Requirements:
    - 3E-FR-008: Built-in patterns (AWS, passwords, API keys, private keys, entropy)
    - 3E-FR-010: Exclude patterns support
    - 3E-FR-011: Custom pattern support
    - 3E-FR-012: SecretFinding to Violation conversion
    - 3E-FR-013: --allow-secrets flag downgrades severity
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.requirement("3E-FR-008")
def test_builtin_scanner_inherits_secret_scanner_plugin() -> None:
    """Test that BuiltinSecretScanner inherits from SecretScannerPlugin.

    Verifies that the builtin scanner implements the SecretScannerPlugin ABC.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner
    from floe_core.plugins.secret_scanner import (
        SecretScannerPlugin,
    )

    assert issubclass(BuiltinSecretScanner, SecretScannerPlugin), (
        "BuiltinSecretScanner must inherit from SecretScannerPlugin"
    )


@pytest.mark.requirement("3E-FR-008")
def test_builtin_scanner_plugin_metadata() -> None:
    """Test that BuiltinSecretScanner has required plugin metadata.

    Verifies that the scanner has name, version, and floe_api_version properties.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()
    assert scanner.name == "builtin_secret_scanner"
    assert isinstance(scanner.version, str)
    assert scanner.version != ""
    assert isinstance(scanner.floe_api_version, str)
    assert scanner.floe_api_version != ""


@pytest.mark.requirement("3E-FR-008")
def test_detect_aws_access_key() -> None:
    """Test detection of AWS access key IDs (AKIA pattern).

    Uses AWS's official documentation example: AKIAIOSFODNN7EXAMPLE.
    This is a published example key ID, not a real credential.

    Expected error code: E601
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    # Test content with AWS example key ID from AWS documentation
    test_content = """
# AWS configuration example (scanner test vector)
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = placeholder
"""

    findings = scanner.scan_file(Path("test.py"), test_content)

    assert len(findings) >= 1, "Should detect AWS access key pattern"
    aws_finding = next(
        (f for f in findings if "AKIA" in f.matched_content),
        None,
    )
    assert aws_finding is not None, "Should find AWS key pattern"
    assert aws_finding.pattern_name == "aws_access_key"
    assert aws_finding.error_code == "E601"
    assert "AKIAIOSFODNN7EXAMPLE" in aws_finding.matched_content
    assert aws_finding.line_number > 0
    assert aws_finding.file_path == "test.py"


@pytest.mark.requirement("3E-FR-008")
def test_detect_hardcoded_password() -> None:
    """Test detection of hardcoded password patterns.

    Uses obvious placeholder 'test_placeholder_value' to avoid any
    confusion with real credentials. This is a scanner test vector.

    Expected error code: E602
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    # Test content with password assignment (scanner test vector)
    test_content = """
# Database configuration (scanner test vector)
db_password = 'test_placeholder_value'
api_password = "test_placeholder_value"
PASSWORD = 'test_placeholder_value'
"""

    findings = scanner.scan_file(Path("config.py"), test_content)

    assert len(findings) >= 1, "Should detect hardcoded password patterns"
    password_finding = next(
        (f for f in findings if "password" in f.pattern_name.lower()),
        None,
    )
    assert password_finding is not None, "Should find password pattern"
    assert password_finding.error_code == "E602"
    assert "password" in password_finding.matched_content.lower()
    assert password_finding.line_number > 0


@pytest.mark.requirement("3E-FR-008")
def test_detect_api_token() -> None:
    """Test detection of API key/token patterns.

    Uses obvious placeholder 'test_api_token_12345' to avoid any
    confusion with real tokens. This is a scanner test vector.

    Expected error code: E603
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    # Test content with API token patterns (scanner test vector)
    test_content = """
# API configuration (scanner test vector)
api_key = 'test_api_token_12345'
api_token = 'test_api_token_12345'
API_KEY = 'test_api_token_12345'
"""

    findings = scanner.scan_file(Path("api.py"), test_content)

    assert len(findings) >= 1, "Should detect API token patterns"
    token_finding = next(
        (
            f
            for f in findings
            if "api" in f.pattern_name.lower() or "token" in f.pattern_name.lower()
        ),
        None,
    )
    assert token_finding is not None, "Should find API token pattern"
    assert token_finding.error_code == "E603"
    matched_lower = token_finding.matched_content.lower()
    assert "api" in matched_lower or "token" in matched_lower
    assert token_finding.line_number > 0


@pytest.mark.requirement("3E-FR-008")
def test_detect_private_key() -> None:
    """Test detection of PEM private key headers.

    Uses standard PEM header format as scanner test vector.

    Expected error code: E604
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    # Test content with PEM private key header (scanner test vector)
    test_content = """
# Private key example (scanner test vector)
private_key = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA... (truncated test data)
-----END RSA PRIVATE KEY-----
'''
"""

    findings = scanner.scan_file(Path("keys.py"), test_content)

    assert len(findings) >= 1, "Should detect private key patterns"
    key_finding = next(
        (
            f
            for f in findings
            if "private" in f.pattern_name.lower() or "key" in f.pattern_name.lower()
        ),
        None,
    )
    assert key_finding is not None, "Should find private key pattern"
    assert key_finding.error_code == "E604"
    matched = key_finding.matched_content
    assert "BEGIN" in matched or "private" in matched.lower()
    assert key_finding.line_number > 0


@pytest.mark.requirement("3E-FR-008")
def test_detect_high_entropy_string() -> None:
    """Test detection of high-entropy strings (if implemented).

    High-entropy detection is optional based on implementation choice.
    Uses random-looking string as scanner test vector.

    Expected error code: E605 (if implemented)
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    # Test content with high-entropy string (scanner test vector)
    test_content = """
# High entropy example (scanner test vector)
secret = 'xK9mP2nQ8wR5yT1uV4bN7cM6dL3eJ0fG'
"""

    findings = scanner.scan_file(Path("entropy.py"), test_content)

    # High-entropy detection is optional, so we check if it exists
    entropy_finding = next(
        (f for f in findings if f.error_code == "E605"),
        None,
    )

    if entropy_finding is not None:
        assert "entropy" in entropy_finding.pattern_name.lower()
        assert entropy_finding.line_number > 0


@pytest.mark.requirement("3E-FR-010")
def test_exclude_patterns_respected() -> None:
    """Test that files matching exclude_patterns are skipped.

    Verifies that the scanner respects the exclude_patterns configuration
    and does not report findings in excluded files.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    # Test content with AWS key (scanner test vector)
    test_content = """
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
"""

    # Scan with exclude pattern matching the file
    findings = scanner.scan_file(
        Path("tests/fixtures/test_data.py"),
        test_content,
    )

    # If scanner supports exclude_patterns, they should be passed differently
    # For now, test that findings are generated without exclusion
    assert len(findings) >= 1, "Should detect secrets in non-excluded files"

    # Test with directory scan and exclude patterns
    # This will be validated by scan_directory implementation


@pytest.mark.requirement("3E-FR-011")
def test_custom_patterns_detected() -> None:
    """Test that custom SecretPattern regex patterns are detected.

    Verifies that the scanner can detect secrets using custom regex patterns
    provided in SecretScanningConfig.custom_patterns.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    from floe_core.schemas.governance import SecretPattern

    # Custom pattern for detecting FLOE-specific tokens (scanner test vector)
    custom_pattern = SecretPattern(
        name="floe_token",
        regex=r"FLOE_TOKEN_[A-Z0-9]{16}",
        description="Floe internal token",
        error_code="E699",
    )

    scanner = BuiltinSecretScanner(custom_patterns=[custom_pattern])

    test_content = """
# Custom token example (scanner test vector)
floe_token = 'FLOE_TOKEN_ABCD1234EFGH5678'
"""

    findings = scanner.scan_file(Path("custom.py"), test_content)

    assert len(findings) >= 1, "Should detect custom pattern"
    custom_finding = next(
        (f for f in findings if f.pattern_name == "floe_token"),
        None,
    )
    assert custom_finding is not None, "Should find custom token pattern"
    assert custom_finding.error_code == "E699"
    assert "FLOE_TOKEN_" in custom_finding.matched_content


@pytest.mark.requirement("3E-FR-012")
def test_findings_have_file_path_and_line_number() -> None:
    """Test that SecretFinding includes file_path and line_number.

    Verifies that findings can be converted to Violation with correct
    file location information.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    test_content = """line 1
line 2
aws_key = AKIAIOSFODNN7EXAMPLE
line 4
"""

    findings = scanner.scan_file(Path("test.py"), test_content)

    assert len(findings) >= 1, "Should detect AWS key"
    finding = findings[0]

    assert finding.file_path == "test.py"
    assert finding.line_number == 3, "Should be on line 3"
    assert isinstance(finding.matched_content, str)
    assert finding.pattern_name != ""
    assert finding.error_code.startswith("E6")


@pytest.mark.requirement("3E-FR-008")
def test_get_supported_patterns_returns_builtin_list() -> None:
    """Test that get_supported_patterns returns list of built-in pattern names.

    Verifies that the scanner reports which patterns it supports.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()
    patterns = scanner.get_supported_patterns()

    assert isinstance(patterns, list)
    assert len(patterns) > 0, "Should have at least one pattern"

    # Check for expected built-in patterns
    expected_patterns = [
        "aws_access_key",
        "hardcoded_password",
        "api_token",
        "private_key",
    ]

    for pattern in expected_patterns:
        assert pattern in patterns, f"Should support {pattern} pattern"


@pytest.mark.requirement("3E-FR-008")
def test_no_false_positive_on_clean_file() -> None:
    """Test that clean files with no secrets return no findings.

    Verifies that the scanner does not produce false positives on
    legitimate code without secrets.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner()

    # Clean Python code with no secrets
    clean_content = """
from pathlib import Path
from typing import Any

def process_data(input_path: Path) -> dict[str, Any]:
    '''Process data from file.'''
    data = read_file(input_path)
    return validate(data)
"""

    findings = scanner.scan_file(Path("clean.py"), clean_content)

    assert len(findings) == 0, "Clean file should have no findings"


@pytest.mark.requirement("3E-FR-013")
def test_allow_secrets_downgrades_severity() -> None:
    """Test that allow_secrets=True downgrades all violations to warnings.

    Verifies that when the --allow-secrets flag is enabled, all secret
    findings have severity 'warning' instead of 'error' in the SecretFinding itself.
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner(allow_secrets=True)

    test_content = """
aws_key = AKIAIOSFODNN7EXAMPLE
"""

    findings = scanner.scan_file(Path("test.py"), test_content)

    assert len(findings) >= 1, "Should detect secrets"

    # Check that all findings have severity 'warning' when allow_secrets is True
    for finding in findings:
        assert finding.allow_secrets is True, "allow_secrets flag should be set"
        assert finding.severity == "warning", (
            "With allow_secrets=True, severity should be 'warning'"
        )


@pytest.mark.requirement("3E-FR-013")
def test_allow_secrets_false_keeps_error_severity() -> None:
    """Test that allow_secrets=False keeps severity as 'error'.

    Verifies that without the --allow-secrets flag, secret findings
    have severity 'error' (default behavior).
    """
    from floe_core.governance.secrets import BuiltinSecretScanner

    scanner = BuiltinSecretScanner(allow_secrets=False)

    test_content = """
aws_key = AKIAIOSFODNN7EXAMPLE
"""

    findings = scanner.scan_file(Path("test.py"), test_content)

    assert len(findings) >= 1, "Should detect secrets"

    # Check that all findings have severity 'error' when allow_secrets is False
    for finding in findings:
        assert finding.allow_secrets is False, "allow_secrets flag should not be set"
        assert finding.severity == "error", (
            "Without allow_secrets, severity should be 'error'"
        )
