from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CleanupEvidence:
    """Cleanup evidence for release and weekly validation lanes."""

    devpod: str
    hetzner: str
    aws: str


def cleanup_status(evidence: CleanupEvidence) -> str:
    """Collapse cleanup evidence into a release gate status."""
    values = (evidence.devpod, evidence.hetzner, evidence.aws)
    normalized = tuple(value.strip().lower() for value in values)
    if any(value.startswith("failed") for value in normalized):
        return "failed cleanup"
    if any(value in {"", "not-run", "skipped"} for value in normalized):
        return "not-run"
    if all(value == "passed" for value in normalized):
        return "passed"
    return "failed cleanup"


def cleanup_summary(evidence: CleanupEvidence) -> str:
    """Return a short human-readable cleanup summary."""
    return f"DevPod: {evidence.devpod}; Hetzner: {evidence.hetzner}; AWS: {evidence.aws}"
