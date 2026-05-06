"""Active alpha docs and tests must use the strict MinIO storage name."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THIS_FILE = Path(__file__).resolve()
OLD_STORAGE_TYPE = "s" + "3"
OLD_STORAGE_IDENTITY_SUFFIX = r"\b(?!://|-compatible)"
ACTIVE_GLOBS = [
    "demo/**/*.yaml",
    "examples/**/*.yaml",
    "testing/**/*.py",
    "tests/**/*.py",
    "packages/**/*.py",
    "plugins/**/*.py",
    "docs/architecture/**/*.md",
    "docs/guides/**/*.md",
]
FORBIDDEN = [
    "floe-storage-" + OLD_STORAGE_TYPE,
    "floe_storage_" + OLD_STORAGE_TYPE,
    OLD_STORAGE_TYPE.upper() + "StoragePlugin",
    OLD_STORAGE_TYPE.upper() + "StorageConfig",
]
FORBIDDEN_PATTERNS = [
    re.compile(r"\bstorage\s*:\s*" + OLD_STORAGE_TYPE + OLD_STORAGE_IDENTITY_SUFFIX),
    re.compile(r"\btype\s*:\s*" + OLD_STORAGE_TYPE + OLD_STORAGE_IDENTITY_SUFFIX),
]


def _is_allowed_non_plugin_s3_reference(path: Path, line: str) -> bool:
    """Allow S3 dialect references that are not Floe storage plugin identities."""
    relative = path.relative_to(ROOT).as_posix()
    return (
        relative == "tests/e2e/conftest.py"
        and line.strip() == f'f"        - type: {OLD_STORAGE_TYPE}\\n"'
    )


def test_active_alpha_paths_do_not_reference_old_s3_plugin_name() -> None:
    """Guard active alpha paths against the retired S3 storage plugin name."""
    offenders: list[str] = []
    for pattern in ACTIVE_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_dir() or path.resolve() == THIS_FILE:
                continue
            text = path.read_text(errors="ignore")
            for token in FORBIDDEN:
                if token in text:
                    offenders.append(f"{path.relative_to(ROOT)} contains {token!r}")
            for line_number, line in enumerate(text.splitlines(), start=1):
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern.search(line):
                        if _is_allowed_non_plugin_s3_reference(path, line):
                            continue
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{line_number} matches {pattern.pattern!r}"
                        )

    assert offenders == []
