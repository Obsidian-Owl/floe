"""Contract tests for the strict MinIO storage plugin rename."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_PACKAGE_NAME = "floe-storage-" + "s3"
OLD_MODULE_NAME = "floe_storage_" + "s3"
OLD_PLUGIN_CLASS = "S3" + "StoragePlugin"
OLD_CONFIG_CLASS = "S3" + "StorageConfig"
OLD_SHORT_MINIO_CLASS = "MinIO" + "Plugin"
NEW_PACKAGE_NAME = "floe-storage-minio"
ACTIVE_SCAN_ROOTS = [
    "pyproject.toml",
    "plugins",
    "tests",
    "packages",
    "docker",
    ".github",
    ".claude",
    "demo",
    "testing",
    "scripts",
    "docs",
    "charts",
    "examples",
    "docs-site",
    "specs",
]
IGNORED_SCAN_PARTS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "docs/superpowers",
}
FORBIDDEN_REFERENCES = [
    OLD_PACKAGE_NAME,
    OLD_MODULE_NAME,
    OLD_PLUGIN_CLASS,
    OLD_CONFIG_CLASS,
    OLD_SHORT_MINIO_CLASS,
    "storage.type: " + "s3",
]
FORBIDDEN_PATTERNS = [
    re.compile(r"\bstorage\s*:\s*" + "s3" + r"\b"),
    re.compile(r"\bstorage\s*:\s*\[[^\]]*\b" + "s3" + r"\b"),
    re.compile(r"\btype\s*:\s*" + "s3" + r"\b"),
    re.compile(r"\btype\s*:\s*\{\s*[\"']" + "s3" + r"[\"']\s*\}"),
    re.compile(r"[\"']type[\"']\s*:\s*[\"']" + "s3" + r"[\"']"),
    re.compile(r"\btype\s*=\s*[\"']" + "s3" + r"[\"']"),
    re.compile(r"\bstorage\s*=\s*[\"']" + "s3" + r"[\"']"),
]


def test_storage_plugin_directory_is_strictly_minio() -> None:
    """Storage plugin directory must use the MinIO package name only."""
    assert not (REPO_ROOT / "plugins" / OLD_PACKAGE_NAME).exists()
    assert (REPO_ROOT / "plugins" / NEW_PACKAGE_NAME).is_dir()


def test_root_pyproject_uses_minio_workspace_package() -> None:
    """Root workspace metadata must depend on the MinIO plugin only."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert f'"{NEW_PACKAGE_NAME}"' in pyproject
    assert OLD_PACKAGE_NAME not in pyproject
    assert f'{NEW_PACKAGE_NAME} = {{ path = "plugins/{NEW_PACKAGE_NAME}"' in pyproject


def test_plugin_pyproject_uses_minio_entry_point_only() -> None:
    """Plugin metadata must expose the MinIO entry point and no S3 alias."""
    pyproject = (REPO_ROOT / "plugins" / NEW_PACKAGE_NAME / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    assert f'name = "{NEW_PACKAGE_NAME}"' in pyproject
    assert 'minio = "floe_storage_minio.plugin:MinIOStoragePlugin"' in pyproject
    assert f's3 = "{OLD_MODULE_NAME}.plugin:{OLD_PLUGIN_CLASS}"' not in pyproject


def _active_scan_files() -> list[Path]:
    files: list[Path] = []
    for root_name in ACTIVE_SCAN_ROOTS:
        root = REPO_ROOT / root_name
        candidates = [root] if root.is_file() else root.rglob("*")
        for candidate in candidates:
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(REPO_ROOT).as_posix()
            if any(
                relative == ignored or relative.startswith(f"{ignored}/")
                for ignored in IGNORED_SCAN_PARTS
            ):
                continue
            files.append(candidate)
    return files


def test_active_references_do_not_use_old_s3_plugin_names() -> None:
    """Active docs, code, and config must not reference the old S3 plugin."""
    matches: list[str] = []
    for path in _active_scan_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for forbidden in FORBIDDEN_REFERENCES:
                if forbidden in line:
                    matches.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {forbidden}")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    matches.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: {pattern.pattern}"
                    )

    assert matches == []
