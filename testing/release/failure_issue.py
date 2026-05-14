from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureIssue:
    """Issue content for release-gate and weekly validation failures."""

    lane: str
    version: str | None
    gate: str
    classification: str
    sha: str
    run_url: str
    log_excerpt: str
    cleanup_status: str
    skipped_outputs: tuple[str, ...] = ()


def issue_title(issue: FailureIssue) -> str:
    """Return a deterministic title suitable for issue deduplication."""
    if issue.lane == "release-gate":
        version = issue.version or "unknown-version"
        return f"Release gate failed: {version} {issue.gate} {issue.classification} failure"
    if issue.lane == "weekly-validation":
        return f"Weekly validation failed: {issue.gate} {issue.classification} failure"
    return f"Validation failed: {issue.lane} {issue.gate} {issue.classification} failure"


def issue_comment_body(issue: FailureIssue) -> str:
    """Return a markdown issue body or update comment for a failed validation run."""
    skipped = (
        ", ".join(f"`{name}`" for name in issue.skipped_outputs)
        if issue.skipped_outputs
        else "_none_"
    )
    version = issue.version or "_not applicable_"
    excerpt = issue.log_excerpt.strip() or "_No log excerpt captured._"
    version_line = (
        f"Requested version: `{version}`" if issue.version else f"Requested version: {version}"
    )
    return "\n".join(
        [
            "## Validation Failure",
            "",
            f"Workflow run: {issue.run_url}",
            f"Commit: `{issue.sha}`",
            version_line,
            f"Failed gate: `{issue.gate}`",
            f"Classification: `{issue.classification}`",
            f"Cleanup status: `{issue.cleanup_status}`",
            f"Skipped outputs: {skipped}",
            "",
            "### Log Excerpt",
            "",
            "```text",
            excerpt[-4000:],
            "```",
            "",
            "### Next Action",
            "",
            (
                "Triage the failed gate, preserve cleanup evidence, and rerun the "
                "workflow after the fix lands."
            ),
            "",
        ],
    )
