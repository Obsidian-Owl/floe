from __future__ import annotations

import re
from enum import Enum
from pathlib import Path


class EvidenceSummaryError(ValueError):
    """Raised when release evidence is not safe to publish."""


class EvidenceStatus(str, Enum):
    """Release evidence status values used by the alpha release gate."""

    PASSED = "passed"
    FAILED = "failed"
    PRE_TAG_REQUIRED = "pre-tag-required"


_CREDENTIAL_PATTERNS = (
    "access denied",
    "accessdenied",
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "config profile could not be found",
    "credential should be scoped",
    "credential",
    "credentials",
    "expiredtoken",
    "invalidclienttokenid",
    "missing aws region",
    "missing profile",
    "missing region",
    "nocredentialserror",
    "noregionerror",
    "no region",
    "partialcredentialserror",
    "profile not found",
    "unable to locate credentials",
    "unrecognizedclientexception",
    "you must specify a region",
)
_INFRASTRUCTURE_PATTERNS = (
    "resource_unavailable",
    "capacity",
    "devpod",
    "network",
    "timeout",
    "timed out",
)
_CLEANUP_PATTERNS = (
    "cleanup",
    "still exists",
    "orphan",
    "delete failed",
    "deletion failed",
)
_SECRET_NAME_RE = re.compile(
    r"\b(?:AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|AWS_SESSION_TOKEN)\b",
)
_AWS_ACCESS_KEY_ID_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b[A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|ACCESS_KEY)[A-Za-z0-9_]*=[^\s&|;`]+",
    re.IGNORECASE,
)
_SENSITIVE_PARAM_RE = re.compile(
    r"(?P<prefix>^|[?&;\s])"
    r"(?P<name>X-Amz-Signature|AWSAccessKeyId|token|password|secret|access_key)="
    r"(?P<value>[^\s&;`]+)",
    re.IGNORECASE,
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)


def classify_live_validation_failure(message: str) -> str:
    """Classify a live validation failure into a deterministic release bucket."""
    normalized = message.lower()
    if any(pattern in normalized for pattern in _CLEANUP_PATTERNS):
        return "cleanup"
    if any(pattern in normalized for pattern in _CREDENTIAL_PATTERNS):
        return "credential-setup"
    if any(pattern in normalized for pattern in _INFRASTRUCTURE_PATTERNS):
        return "infrastructure"
    return "product"


def write_evidence_summary(
    *,
    output_path: Path,
    release_sha: str,
    manifest_path: Path,
    package_count: int,
    devpod_artifact: str,
    aws_live_result: str,
    cleanup_result: str,
    allow_placeholders: bool = False,
) -> None:
    """Write a secret-free markdown summary for the alpha release gate."""
    _reject_placeholders(
        {
            "devpod_artifact": devpod_artifact,
            "aws_live_result": aws_live_result,
            "cleanup_result": cleanup_result,
        },
        allow_placeholders=allow_placeholders,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            (
                "# Floe Alpha Release Evidence",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| Release SHA | `{_clean_value(release_sha)}` |",
                f"| Manifest | `{_clean_value(str(manifest_path))}` |",
                f"| Python package publish count | `{package_count}` |",
                f"| DevPod artifact | `{_clean_value(devpod_artifact)}` |",
                f"| AWS live validation result | `{_summarize_result(aws_live_result)}` |",
                f"| Cleanup result | `{_summarize_result(cleanup_result)}` |",
                "",
            ),
        ),
        encoding="utf-8",
    )


def _summarize_result(result: str) -> str:
    status = _status_for(result)
    if status is EvidenceStatus.FAILED:
        return f"{status.value} ({classify_live_validation_failure(result)})"
    return str(status.value)


def _status_for(result: str) -> EvidenceStatus:
    normalized = result.strip().lower()
    for status in EvidenceStatus:
        if normalized == status.value:
            return status
    if normalized.startswith(EvidenceStatus.FAILED.value):
        return EvidenceStatus.FAILED
    return EvidenceStatus.FAILED


def _reject_placeholders(
    evidence: dict[str, str],
    *,
    allow_placeholders: bool,
) -> None:
    if allow_placeholders:
        return
    placeholder_fields = [
        field_name
        for field_name, value in evidence.items()
        if value.strip().lower() == EvidenceStatus.PRE_TAG_REQUIRED.value
    ]
    if placeholder_fields:
        fields = ", ".join(sorted(placeholder_fields))
        raise EvidenceSummaryError(f"placeholder release evidence is not publishable: {fields}")


def _clean_value(value: str) -> str:
    cleaned = _PRIVATE_KEY_RE.sub("[redacted-private-key]", value)
    cleaned = _BEARER_TOKEN_RE.sub("[redacted-bearer-token]", cleaned)
    cleaned = _AWS_ACCESS_KEY_ID_RE.sub("[redacted-aws-access-key-id]", cleaned)
    cleaned = _SECRET_ASSIGNMENT_RE.sub("[redacted-secret-assignment]", cleaned)
    cleaned = _SENSITIVE_PARAM_RE.sub(_redact_sensitive_param, cleaned)
    cleaned = _SECRET_NAME_RE.sub("[redacted-credential-name]", cleaned)
    return cleaned.replace("\n", "\\n")


def _redact_sensitive_param(match: re.Match[str]) -> str:
    return f"{match.group('prefix')}[redacted-param]"
