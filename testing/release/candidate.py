from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from testing.release.manifest import load_release_manifest, validate_release_manifest

_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class ReleaseCandidateError(ValueError):
    """Raised when a release candidate cannot safely create a tag."""


@dataclass(frozen=True)
class ReleaseCandidate:
    """Validated release candidate metadata."""

    version: str
    release_sha: str
    python_version: str
    helm_chart_version: str
    helm_cli_version: str
    publish_count: int


def validate_release_candidate(
    *,
    requested_version: str,
    release_sha: str,
    manifest_path: Path,
    repo_root: Path,
    existing_tags: tuple[str, ...],
) -> ReleaseCandidate:
    """Validate that a requested release can create a new tag."""
    version = requested_version.strip()
    normalized_sha = release_sha.strip()
    if not version:
        raise ReleaseCandidateError("requested version is required")
    if not version.startswith("v"):
        raise ReleaseCandidateError("requested version must start with 'v'")
    if not _COMMIT_SHA_RE.fullmatch(normalized_sha):
        raise ReleaseCandidateError("release_sha must be a 40-character commit SHA")
    if version in existing_tags:
        raise ReleaseCandidateError(f"release tag already exists: {version}")

    manifest = load_release_manifest(manifest_path)
    if manifest.release.git_tag != version:
        raise ReleaseCandidateError(
            f"requested version {version} does not match manifest git_tag "
            f"{manifest.release.git_tag}",
        )

    result = validate_release_manifest(manifest, repo_root=repo_root, tag=version)
    return ReleaseCandidate(
        version=version,
        release_sha=normalized_sha,
        python_version=result.python_version,
        helm_chart_version=result.helm_chart_version,
        helm_cli_version=result.helm_cli_version,
        publish_count=result.publish_count,
    )
