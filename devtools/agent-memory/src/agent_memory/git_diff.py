"""Git diff utilities for detecting changed files.

Provides functions to detect which files have changed since a given commit,
filtered by configurable source patterns. Used by sync commands to identify
files needing re-indexing.

Example:
    >>> from agent_memory.git_diff import get_changed_files
    >>> changed = get_changed_files(since="HEAD~1")
    >>> for path in changed:
    ...     print(f"Changed: {path}")
"""

from __future__ import annotations

import fnmatch
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Safe pattern for git references (commits, branches, tags, relative refs)
# Allows: alphanumeric, dots, slashes, tildes, carets, hyphens, underscores, colons
# Examples: HEAD~1, main, feature/my-branch, v1.0.0, abc123def, HEAD^2, origin/main
_SAFE_GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9._/~^:\-]+$")


class GitError(Exception):
    """Error executing git command."""

    pass


def _validate_git_ref(ref: str) -> None:
    """Validate a git reference for safe subprocess usage.

    Defense-in-depth: While shell=False prevents shell injection,
    this validation ensures only valid git references are passed.

    Args:
        ref: Git reference to validate.

    Raises:
        GitError: If the reference contains invalid characters.
    """
    if not ref:
        raise GitError("Git reference cannot be empty")
    if not _SAFE_GIT_REF_PATTERN.match(ref):
        raise GitError(
            f"Invalid git reference: {ref!r}. "
            "Only alphanumeric characters, dots, slashes, tildes, "
            "carets, hyphens, underscores, and colons are allowed."
        )


def get_repo_root() -> Path:
    """Get the root directory of the git repository.

    Returns:
        Path to the repository root.

    Raises:
        GitError: If not in a git repository or git command fails.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        msg = f"Failed to get repo root: {e.stderr.strip()}"
        raise GitError(msg) from e
    except FileNotFoundError as e:
        msg = "git command not found"
        raise GitError(msg) from e


def get_changed_files(
    since: str = "HEAD~1",
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    include_staged: bool = True,
    include_unstaged: bool = True,
) -> list[Path]:
    """Get list of files changed since a given commit.

    Uses `git diff --name-only` to detect changes. Supports filtering
    by include/exclude glob patterns.

    Args:
        since: Git reference to compare against (default: HEAD~1).
               Can be a commit hash, branch name, or relative reference.
        include_patterns: Glob patterns to include (e.g., ["*.py", "*.md"]).
                         If None, includes all files.
        exclude_patterns: Glob patterns to exclude (e.g., ["**/test_*", "**/__pycache__/*"]).
                         If None, excludes nothing.
        include_staged: Include staged changes (default: True).
        include_unstaged: Include unstaged changes (default: True).

    Returns:
        List of Path objects for changed files, relative to repo root.
        Only includes files that exist on filesystem (excludes deleted files).

    Raises:
        GitError: If git command fails or not in a git repository.

    Examples:
        >>> # Get all changed Python files since last commit
        >>> changed = get_changed_files(
        ...     since="HEAD~1",
        ...     include_patterns=["*.py"],
        ...     exclude_patterns=["**/test_*.py"]
        ... )

        >>> # Get changes on a feature branch
        >>> changed = get_changed_files(since="main")
    """
    # Validate git reference (defense-in-depth)
    _validate_git_ref(since)

    repo_root = get_repo_root()
    changed_files: set[str] = set()

    try:
        # Get committed changes since reference
        result = subprocess.run(
            ["git", "diff", "--name-only", since],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
        if result.stdout.strip():
            changed_files.update(result.stdout.strip().split("\n"))

        # Get staged changes (if requested)
        if include_staged:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_root,
            )
            if result.stdout.strip():
                changed_files.update(result.stdout.strip().split("\n"))

        # Get unstaged changes (if requested)
        if include_unstaged:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_root,
            )
            if result.stdout.strip():
                changed_files.update(result.stdout.strip().split("\n"))

    except subprocess.CalledProcessError as e:
        # Check if it's a "bad revision" error (e.g., no commits yet)
        if "unknown revision" in e.stderr or "bad revision" in e.stderr:
            logger.warning("Reference '%s' not found, returning empty list", since)
            return []
        msg = f"Git diff failed: {e.stderr.strip()}"
        raise GitError(msg) from e
    except FileNotFoundError as e:
        msg = "git command not found"
        raise GitError(msg) from e

    # Filter and convert to paths
    result_paths: list[Path] = []

    for file_str in changed_files:
        if not file_str:  # Skip empty strings
            continue

        file_path = Path(file_str)
        abs_path = repo_root / file_path

        # Skip deleted files (only include files that exist)
        if not abs_path.exists():
            logger.debug("Skipping deleted file: %s", file_path)
            continue

        # Apply include patterns
        if include_patterns:
            if not _matches_any_pattern(file_str, include_patterns):
                continue

        # Apply exclude patterns
        if exclude_patterns:
            if _matches_any_pattern(file_str, exclude_patterns):
                continue

        result_paths.append(file_path)

    # Sort for consistent ordering
    return sorted(result_paths)


def get_staged_files(
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[Path]:
    """Get list of files currently staged for commit.

    Convenience function for pre-commit hook integration.

    Args:
        include_patterns: Glob patterns to include.
        exclude_patterns: Glob patterns to exclude.

    Returns:
        List of Path objects for staged files.

    Raises:
        GitError: If git command fails.
    """
    repo_root = get_repo_root()

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
    except subprocess.CalledProcessError as e:
        msg = f"Git diff --cached failed: {e.stderr.strip()}"
        raise GitError(msg) from e

    if not result.stdout.strip():
        return []

    staged_files = result.stdout.strip().split("\n")
    result_paths: list[Path] = []

    for file_str in staged_files:
        if not file_str:
            continue

        file_path = Path(file_str)
        abs_path = repo_root / file_path

        # Skip deleted files
        if not abs_path.exists():
            continue

        # Apply include patterns
        if include_patterns:
            if not _matches_any_pattern(file_str, include_patterns):
                continue

        # Apply exclude patterns
        if exclude_patterns:
            if _matches_any_pattern(file_str, exclude_patterns):
                continue

        result_paths.append(file_path)

    return sorted(result_paths)


def _matches_any_pattern(path_str: str, patterns: list[str]) -> bool:
    """Check if a path matches any of the given glob patterns.

    Args:
        path_str: Path string to check.
        patterns: List of glob patterns.

    Returns:
        True if path matches any pattern.
    """
    for pattern in patterns:
        # Handle patterns with **
        if "**" in pattern:
            # fnmatch doesn't handle ** well, use custom logic
            if _matches_double_star_pattern(path_str, pattern):
                return True
        elif fnmatch.fnmatch(path_str, pattern):
            return True
        # Also try matching just the filename for simple patterns
        elif fnmatch.fnmatch(Path(path_str).name, pattern):
            return True
    return False


def _matches_double_star_pattern(path_str: str, pattern: str) -> bool:
    """Match a path against a pattern containing **.

    Args:
        path_str: Path string to check.
        pattern: Glob pattern with **.

    Returns:
        True if path matches pattern.
    """
    # Convert ** pattern to regex-like matching
    # **/ matches any directory depth
    parts = pattern.split("**/")

    if len(parts) == 2:
        prefix, suffix = parts
        # If prefix is empty, just match the suffix anywhere in path
        if not prefix:
            # Match suffix at any depth
            return fnmatch.fnmatch(path_str, f"*{suffix}") or fnmatch.fnmatch(
                Path(path_str).name, suffix.lstrip("/")
            )
        # Match prefix at start and suffix anywhere after
        if path_str.startswith(prefix):
            remaining = path_str[len(prefix) :]
            return fnmatch.fnmatch(remaining, f"*{suffix}") or remaining.endswith(suffix)

    # Fallback to simple fnmatch
    return fnmatch.fnmatch(path_str, pattern)
