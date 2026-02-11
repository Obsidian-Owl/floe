"""Sanitize error messages for secure OpenTelemetry span recording.

Provides utilities to strip credentials and other sensitive information from
error messages before recording them in OTel span events.
"""

from __future__ import annotations

import re

# Sensitive key patterns for redaction (FR-049)
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret_key|access_key|token|api_key|authorization|credential)"
    r"\s*[=:]\s*\S+",
    re.IGNORECASE,
)
_URL_CREDENTIAL_PATTERN = re.compile(
    r"://[^@/\s]+:[^@/\s]+@",
)


def sanitize_error_message(msg: str, max_length: int = 500) -> str:
    """Sanitize an error message by redacting credentials and truncating.

    Strips URL credential patterns (e.g., ``://user:pass@host``) and  # pragma: allowlist secret
    key-value patterns for known sensitive keys (password=, secret_key=,
    etc.) before truncating to max_length.

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
    # Redact key=value patterns for sensitive keys
    sanitized = _SENSITIVE_KEY_PATTERN.sub(
        lambda m: m.group(0).split("=", 1)[0].split(":", 1)[0] + "=<REDACTED>"
        if "=" in m.group(0)
        else m.group(0).split(":", 1)[0] + ": <REDACTED>",
        sanitized,
    )
    return sanitized[:max_length]


__all__ = ["sanitize_error_message"]
