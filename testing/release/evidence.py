from __future__ import annotations

import re
from enum import Enum
from pathlib import Path


class EvidenceStatus(str, Enum):
    """Release evidence status values used by the alpha release gate."""

    PASSED = "passed"
    FAILED = "failed"
    PRE_TAG_REQUIRED = "pre-tag-required"


_CREDENTIAL_PATTERNS = (
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "credential",
    "credentials",
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
) -> None:
    """Write a secret-free markdown summary for the alpha release gate."""
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


def _clean_value(value: str) -> str:
    return _SECRET_NAME_RE.sub("[redacted-credential-name]", value)
