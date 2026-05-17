"""Sanitize error messages for secure OpenTelemetry span recording.

Provides utilities to strip credentials and other sensitive information from
error messages before recording them in OTel span events.
"""

from __future__ import annotations

import re

# Sensitive key patterns for redaction (FR-049)
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(?P<key>"
    r"x-amz-signature|x-amz-credential|x-amz-security-token|"
    r"awsaccesskeyid|signature|security-token|"
    r"password|secret_key|access_key|token|api_key|authorization|credential"
    r")"
    r"(?P<pre_sep>\s*)(?P<separator>[=:])(?P<post_sep>\s*)"
    r"(?P<value>[^\s&#]+)",
    re.IGNORECASE,
)
_URL_CREDENTIAL_PATTERN = re.compile(
    r"://[^@/\s]+:[^@/\s]+@",
)


def sanitize_error_message(msg: str, max_length: int = 500) -> str:
    """Sanitize an error message by redacting credentials and truncating.

    Strips URL credential patterns (e.g., ``://user:pass@host``),  # pragma: allowlist secret
    key-value patterns for known sensitive keys (password=, secret_key=,
    etc.), and credential-bearing URL query/fragment parameters before
    truncating to max_length.

    Args:
        msg: Raw error message to sanitize.
        max_length: Maximum length of returned message.

    Returns:
        Sanitized and truncated error message.

    Example:
        >>> sanitize_error_message("Failed: password=secret123 at host")
        'Failed: password=<REDACTED> at host'
    """
    # Redact URL credentials like ://user:pass@host
    sanitized = _URL_CREDENTIAL_PATTERN.sub("://<REDACTED>@", msg)
    # Redact key=value patterns for sensitive keys without consuming URL delimiters
    # or adjacent non-sensitive query parameters.
    sanitized = _SENSITIVE_KEY_PATTERN.sub(
        _redact_sensitive_match,
        sanitized,
    )
    return sanitized[:max_length]


def _redact_sensitive_match(match: re.Match[str]) -> str:
    key = match.group("key")
    pre_sep = match.group("pre_sep")
    separator = match.group("separator")
    replacement_space = " " if separator == ":" else ""
    return f"{key}{pre_sep}{separator}{replacement_space}<REDACTED>"


__all__ = ["sanitize_error_message"]
