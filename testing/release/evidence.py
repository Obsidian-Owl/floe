from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
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
_GITHUB_TOKEN_RE = re.compile(
    r"\b(?:(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,})\b",
)
_SLACK_TOKEN_RE = re.compile(r"\bxox[A-Za-z0-9-]{20,}\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b[A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|ACCESS_KEY)[A-Za-z0-9_]*=[^\s&|;`]+",
    re.IGNORECASE,
)
_SENSITIVE_PARAM_RE = re.compile(
    r"(?P<prefix>^|[?&;\s])"
    r"(?P<name>X-Amz-Signature|AWSAccessKeyId|auth|token|password|secret|access_key)="
    r"(?P<value>[^\s&;`]+)",
    re.IGNORECASE,
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
_DEVPOD_ARTIFACT_PATH_RE = re.compile(
    r"^test-artifacts/devpod-run-[A-Za-z0-9][A-Za-z0-9._/-]*$",
)
_ARTIFACT_URL_RE = re.compile(r"^https?://[^\s`|]+$", re.IGNORECASE)

PackageCutlineEntry = tuple[str, str]


@dataclass(frozen=True)
class ReleaseEvidence:
    """Release-grade evidence used to gate tagged alpha releases."""

    release_sha: str
    manifest_path: Path
    package_count: int
    devpod_artifact: str
    aws_live_result: str
    cleanup_result: str
    publish_packages: Sequence[PackageCutlineEntry] = field(default_factory=tuple)
    exclude_packages: Sequence[PackageCutlineEntry] = field(default_factory=tuple)

    def validate_publishable(self) -> None:
        """Reject placeholder, failed, or implausible evidence for tagged releases."""
        _require_publishable_status("aws_live_result", self.aws_live_result)
        _require_publishable_status("cleanup_result", self.cleanup_result)
        _require_publishable_devpod_artifact(self.devpod_artifact)


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
    publish_packages: Sequence[PackageCutlineEntry] = (),
    exclude_packages: Sequence[PackageCutlineEntry] = (),
    allow_placeholders: bool = False,
) -> None:
    """Write a secret-free markdown summary for the alpha release gate."""
    evidence = ReleaseEvidence(
        release_sha=release_sha,
        manifest_path=manifest_path,
        package_count=package_count,
        devpod_artifact=devpod_artifact,
        aws_live_result=aws_live_result,
        cleanup_result=cleanup_result,
        publish_packages=publish_packages,
        exclude_packages=exclude_packages,
    )
    if not allow_placeholders:
        evidence.validate_publishable()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_lines = [
        "# Floe Alpha Release Evidence",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Release SHA | `{_clean_markdown_cell(evidence.release_sha)}` |",
        f"| Manifest | `{_clean_markdown_cell(str(evidence.manifest_path))}` |",
        f"| Python package publish count | `{evidence.package_count}` |",
        f"| DevPod artifact | `{_clean_markdown_cell(evidence.devpod_artifact)}` |",
        f"| AWS live validation result | `{_summarize_result(evidence.aws_live_result)}` |",
        f"| Cleanup result | `{_summarize_result(evidence.cleanup_result)}` |",
        "",
        "## Published package cutline",
        "",
        f"| Published package count | `{evidence.package_count}` |",
        "",
        "| Package | Evidence |",
        "| --- | --- |",
        *_cutline_rows(evidence.publish_packages),
        "",
        "## Excluded package cutline",
        "",
        f"| Excluded package count | `{len(evidence.exclude_packages)}` |",
        "",
        "| Package | Reason |",
        "| --- | --- |",
        *_cutline_rows(evidence.exclude_packages),
        "",
    ]
    output_path.write_text(
        "\n".join(summary_lines),
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


def _require_publishable_status(field_name: str, value: str) -> None:
    normalized = value.strip().lower()
    if normalized == EvidenceStatus.PASSED.value:
        return
    if not normalized:
        reason = "empty"
    elif normalized == EvidenceStatus.PRE_TAG_REQUIRED.value:
        reason = "pre-tag-required"
    elif normalized.startswith(EvidenceStatus.FAILED.value):
        reason = f"failed ({classify_live_validation_failure(value)})"
    else:
        reason = "unrecognized"
    raise EvidenceSummaryError(
        f"{field_name} must be passed for tagged release evidence; got {reason}",
    )


def _require_publishable_devpod_artifact(value: str) -> None:
    normalized = value.strip()
    lower = normalized.lower()
    if not normalized:
        raise EvidenceSummaryError("devpod_artifact must be a plausible DevPod artifact reference")
    if lower == EvidenceStatus.PRE_TAG_REQUIRED.value:
        raise EvidenceSummaryError(
            "placeholder release evidence is not publishable: devpod_artifact",
        )
    if lower.startswith(EvidenceStatus.FAILED.value):
        raise EvidenceSummaryError("devpod_artifact must be a plausible DevPod artifact reference")
    if "not-real" in lower or "fake" in lower:
        raise EvidenceSummaryError("devpod_artifact must be a plausible DevPod artifact reference")
    if _DEVPOD_ARTIFACT_PATH_RE.fullmatch(normalized):
        return
    if _ARTIFACT_URL_RE.fullmatch(normalized) and ("artifact" in lower or "actions/runs" in lower):
        return
    raise EvidenceSummaryError("devpod_artifact must be a plausible DevPod artifact reference")


def _cutline_rows(packages: Sequence[PackageCutlineEntry]) -> list[str]:
    if not packages:
        return ["| _No package details provided_ |  |"]
    return [
        f"| {_clean_markdown_cell(name)} | `{_clean_markdown_cell(detail)}` |"
        for name, detail in packages
    ]


def _clean_value(value: str) -> str:
    cleaned = _PRIVATE_KEY_RE.sub("[redacted-private-key]", value)
    cleaned = _BEARER_TOKEN_RE.sub("[redacted-bearer-token]", cleaned)
    cleaned = _AWS_ACCESS_KEY_ID_RE.sub("[redacted-aws-access-key-id]", cleaned)
    cleaned = _GITHUB_TOKEN_RE.sub("[redacted-github-token]", cleaned)
    cleaned = _SLACK_TOKEN_RE.sub("[redacted-slack-token]", cleaned)
    cleaned = _SECRET_ASSIGNMENT_RE.sub("[redacted-secret-assignment]", cleaned)
    cleaned = _SENSITIVE_PARAM_RE.sub(_redact_sensitive_param, cleaned)
    cleaned = _SECRET_NAME_RE.sub("[redacted-credential-name]", cleaned)
    return cleaned.replace("\n", "\\n")


def _clean_markdown_cell(value: str) -> str:
    return _clean_value(value).replace("|", "\\|").replace("`", "'")


def _redact_sensitive_param(match: re.Match[str]) -> str:
    return f"{match.group('prefix')}[redacted-param]"
