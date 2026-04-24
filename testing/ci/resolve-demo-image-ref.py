"""Resolve the demo Dagster image reference for local validation flows.

This helper centralizes image-ref selection so Make, shell runners, and tests
do not each invent their own mutable-tag behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_REPOSITORY = "floe-dagster-demo"
IGNORED_UNTRACKED_PREFIXES = (
    ".git/",
    ".venv/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "test-artifacts/",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_output(repo_root: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def _iter_untracked_files(repo_root: Path) -> list[Path]:
    output = _git_output(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        text=False,
    )
    files: list[Path] = []
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        rel_path = raw_path.decode("utf-8", errors="surrogateescape")
        if rel_path.startswith(IGNORED_UNTRACKED_PREFIXES):
            continue
        path = repo_root / rel_path
        if path.is_file():
            files.append(path)
    return sorted(files)


def _compute_default_tag(repo_root: Path) -> str:
    head = str(_git_output(repo_root, "rev-parse", "--short=12", "HEAD")).strip()
    status = str(_git_output(repo_root, "status", "--porcelain=v1", "--untracked-files=all"))
    if not status.strip():
        return head

    hasher = hashlib.sha256()
    tracked_diff = _git_output(repo_root, "diff", "--no-ext-diff", "--binary", "HEAD", text=False)
    hasher.update(tracked_diff)

    for path in _iter_untracked_files(repo_root):
        rel_path = path.relative_to(repo_root).as_posix()
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")

    return f"{head}-dirty-{hasher.hexdigest()[:12]}"


def resolve_demo_image_ref(repo_root: Path | None = None) -> dict[str, str]:
    """Return repository, tag, and full image ref for the demo Dagster image."""
    repo_root = repo_root or _repo_root()
    repository = os.environ.get("FLOE_DEMO_IMAGE_REPOSITORY", DEFAULT_REPOSITORY).strip()
    if not repository:
        raise SystemExit("FLOE_DEMO_IMAGE_REPOSITORY cannot be empty")

    tag = os.environ.get("FLOE_DEMO_IMAGE_TAG", "").strip()
    if not tag:
        try:
            tag = _compute_default_tag(repo_root)
        except (subprocess.CalledProcessError, FileNotFoundError):
            tag = "local"

    ref = f"{repository}:{tag}"
    return {
        "FLOE_DEMO_IMAGE_REPOSITORY": repository,
        "FLOE_DEMO_IMAGE_TAG": tag,
        "FLOE_DEMO_IMAGE": ref,
    }


def _shell_quote(value: str) -> str:
    return shlex.quote(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--field",
        choices=("repository", "tag", "ref", "exports"),
        default="exports",
        help="Single field to print, or shell exports (default).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    resolved = resolve_demo_image_ref()
    field_map = {
        "repository": resolved["FLOE_DEMO_IMAGE_REPOSITORY"],
        "tag": resolved["FLOE_DEMO_IMAGE_TAG"],
        "ref": resolved["FLOE_DEMO_IMAGE"],
    }
    if args.field == "exports":
        for key, value in resolved.items():
            print(f"export {key}={_shell_quote(value)}")
        return
    sys.stdout.write(field_map[args.field])


if __name__ == "__main__":
    main()
