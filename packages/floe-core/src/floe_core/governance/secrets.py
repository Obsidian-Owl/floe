"""Built-in regex-based secret scanner.

This module implements the BuiltinSecretScanner, the default secret scanning
plugin that detects hardcoded secrets using regex patterns. It supports:
- AWS Access Key IDs (AKIA pattern) — E601
- Hardcoded passwords — E602
- API keys/tokens — E603
- Private keys (PEM headers) — E604
- High-entropy strings — E605
- Custom user-defined patterns — E6XX

Requirements:
    - FR-008: Built-in regex patterns
    - FR-010: Exclude patterns support
    - FR-011: Custom pattern support
    - FR-012: SecretFinding with file location
    - FR-013: --allow-secrets flag
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Literal

from floe_core.governance.types import SecretFinding, SecretPattern
from floe_core.plugins.secret_scanner import SecretScannerPlugin

# Built-in pattern definitions
_BUILTIN_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern_name, regex, error_code)
    (
        "aws_access_key",
        r"(?:^|[^A-Z0-9])(?:AKIA[0-9A-Z]{16})(?:$|[^A-Z0-9])",
        "E601",
    ),
    (
        "hardcoded_password",
        r"(?i)(?:password|passwd|pwd)\s*=\s*['\"][^'\"]+['\"]",
        "E602",
    ),
    (
        "api_token",
        r"(?i)(?:api[_-]?(?:key|token|secret))\s*=\s*['\"][^'\"]+['\"]",
        "E603",
    ),
    (
        "private_key",
        r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
        "E604",
    ),
]

# Shannon entropy threshold for high-entropy detection
_ENTROPY_THRESHOLD = 4.0
_ENTROPY_MIN_LENGTH = 20


def _shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string.

    Args:
        data: Input string to measure entropy.

    Returns:
        Shannon entropy value (bits per character).
    """
    if not data:
        return 0.0
    freq: dict[str, int] = {}
    for char in data:
        freq[char] = freq.get(char, 0) + 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


class BuiltinSecretScanner(SecretScannerPlugin):
    """Built-in regex-based secret scanner.

    Detects hardcoded secrets using regex pattern matching and optional
    Shannon entropy analysis. Supports custom patterns and the --allow-secrets
    flag for severity downgrading.

    Args:
        custom_patterns: Additional custom patterns to detect.
        allow_secrets: When True, downgrade severity to 'warning'.

    Example:
        >>> scanner = BuiltinSecretScanner()
        >>> findings = scanner.scan_file(Path("config.py"), content)
    """

    def __init__(
        self,
        custom_patterns: list[SecretPattern] | None = None,
        allow_secrets: bool = False,
    ) -> None:
        """Initialize scanner with optional custom patterns.

        Args:
            custom_patterns: Additional regex patterns to detect.
            allow_secrets: Downgrade all findings to warnings.
        """
        self._custom_patterns = custom_patterns or []
        self._allow_secrets = allow_secrets

    @property
    def name(self) -> str:
        """Plugin name."""
        return "builtin_secret_scanner"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Floe API version."""
        return "1.0.0"

    def scan_file(self, file_path: Path, content: str) -> list[SecretFinding]:
        """Scan a single file for secrets.

        Applies built-in patterns and custom patterns to each line.
        Optionally checks for high-entropy strings.

        Args:
            file_path: Path to the file being scanned.
            content: File content to scan.

        Returns:
            List of SecretFinding instances for detected secrets.
        """
        findings: list[SecretFinding] = []
        lines = content.split("\n")
        severity: Literal["error", "warning"] = "warning" if self._allow_secrets else "error"

        # Check built-in patterns
        for pattern_name, regex, error_code in _BUILTIN_PATTERNS:
            compiled = re.compile(regex)
            for line_idx, line in enumerate(lines, start=1):
                match = compiled.search(line)
                if match:
                    findings.append(
                        SecretFinding(
                            file_path=str(file_path),
                            line_number=line_idx,
                            pattern_name=pattern_name,
                            error_code=error_code,
                            matched_content=line.strip(),
                            severity=severity,
                            allow_secrets=self._allow_secrets,
                        )
                    )

        # Check custom patterns
        for custom in self._custom_patterns:
            compiled = re.compile(custom.regex)
            for line_idx, line in enumerate(lines, start=1):
                match = compiled.search(line)
                if match:
                    findings.append(
                        SecretFinding(
                            file_path=str(file_path),
                            line_number=line_idx,
                            pattern_name=custom.name,
                            error_code=custom.error_code,
                            matched_content=line.strip(),
                            severity=severity,
                            allow_secrets=self._allow_secrets,
                        )
                    )

        # Check high-entropy strings
        for line_idx, line in enumerate(lines, start=1):
            entropy_match = re.search(r"""=\s*['"]([\w/+=]{20,})['\"]""", line)
            if entropy_match:
                candidate = entropy_match.group(1)
                if (
                    len(candidate) >= _ENTROPY_MIN_LENGTH
                    and _shannon_entropy(candidate) >= _ENTROPY_THRESHOLD
                ):
                    findings.append(
                        SecretFinding(
                            file_path=str(file_path),
                            line_number=line_idx,
                            pattern_name="high_entropy",
                            error_code="E605",
                            matched_content=line.strip(),
                            severity=severity,
                            allow_secrets=self._allow_secrets,
                        )
                    )

        return findings

    def scan_directory(
        self,
        directory: Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[SecretFinding]:
        """Scan a directory tree for secrets.

        Walks the directory tree, applies exclude patterns, and scans
        each file for secrets.

        Args:
            directory: Root directory to scan.
            exclude_patterns: Glob patterns to exclude from scanning.

        Returns:
            List of secret findings across all scanned files.
        """
        findings: list[SecretFinding] = []
        exclude = exclude_patterns or []

        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue

            # Check exclude patterns
            relative = str(file_path.relative_to(directory))
            if any(file_path.match(pattern) for pattern in exclude):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            file_findings = self.scan_file(Path(relative), content)
            findings.extend(file_findings)

        return findings

    def get_supported_patterns(self) -> list[str]:
        """Return names of patterns this scanner detects.

        Returns:
            List of pattern names including built-in and custom patterns.
        """
        patterns = [name for name, _, _ in _BUILTIN_PATTERNS]
        patterns.extend(p.name for p in self._custom_patterns)
        return patterns
