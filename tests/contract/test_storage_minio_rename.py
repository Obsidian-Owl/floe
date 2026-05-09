"""Contract tests for the strict MinIO storage plugin rename."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_PACKAGE_NAME = "floe-storage-" + "s3"
OLD_MODULE_NAME = "floe_storage_" + "s3"
OLD_PLUGIN_CLASS = "S3" + "StoragePlugin"
OLD_CONFIG_CLASS = "S3" + "StorageConfig"
OLD_SHORT_MINIO_CLASS = "MinIO" + "Plugin"
OLD_STORAGE_TYPE = "s" + "3"
OLD_STORAGE_IDENTITY_SUFFIX = r"\b(?!://|-compatible)"
NEW_PACKAGE_NAME = "floe-storage-minio"
ACTIVE_SCAN_ROOTS = [
    "README.md",
    "uv.lock",
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
    "docs/validation",
    "docs-site/.astro",
    "docs-site/dist",
    "docs-site/node_modules",
    "docs-site/src/content/docs",
    "docs/superpowers",
}
FORBIDDEN_REFERENCES = [
    OLD_PACKAGE_NAME,
    OLD_MODULE_NAME,
    OLD_PLUGIN_CLASS,
    OLD_CONFIG_CLASS,
    OLD_SHORT_MINIO_CLASS,
    "storage.type: " + OLD_STORAGE_TYPE,
]
FORBIDDEN_PATTERNS = [
    re.compile(r"\bstorage\s*:\s*" + OLD_STORAGE_TYPE + OLD_STORAGE_IDENTITY_SUFFIX),
    re.compile(r"\bstorage\s*:\s*\[[^\]]*\b" + OLD_STORAGE_TYPE + OLD_STORAGE_IDENTITY_SUFFIX),
    re.compile(r"\bstorage\s*:\s*\{\s*[\"']" + OLD_STORAGE_TYPE + r"[\"']\s*\}"),
    re.compile(r"\btype\s*:\s*" + OLD_STORAGE_TYPE + OLD_STORAGE_IDENTITY_SUFFIX),
    re.compile(r"\btype\s*:\s*\{\s*[\"']" + OLD_STORAGE_TYPE + r"[\"']\s*\}"),
    re.compile(r"\btype\s*:\s*f[\"']" + OLD_STORAGE_TYPE + r"[\"']"),
    re.compile(r"[\"']type[\"']\s*:\s*[\"']" + OLD_STORAGE_TYPE + r"[\"']"),
    re.compile(r"[\"']type[\"']\s*:\s*f[\"']" + OLD_STORAGE_TYPE + r"[\"']"),
    re.compile(r"\btype\s*=\s*[\"']" + OLD_STORAGE_TYPE + r"[\"']"),
    re.compile(r"\btype\s*=\s*f[\"']" + OLD_STORAGE_TYPE + r"[\"']"),
    re.compile(r"\bstorage\s*=\s*[\"']" + OLD_STORAGE_TYPE + r"[\"']"),
    re.compile(r"\bstorage\s*=\s*f[\"']" + OLD_STORAGE_TYPE + r"[\"']"),
]


def _is_allowed_non_plugin_s3_reference(path: Path, line: str) -> bool:
    """Allow S3 dialect references that are not Floe storage plugin identities."""
    relative = path.relative_to(REPO_ROOT).as_posix()
    stripped = line.strip()
    return (
        relative == "tests/e2e/conftest.py"
        and stripped == f'f"        - type: {OLD_STORAGE_TYPE}\\n"'
    ) or (
        relative == "tests/e2e/test_dbt_e2e_profile.py"
        and f'secret_entry.get("type") == "{OLD_STORAGE_TYPE}"' in line
    )


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


def test_storage_plugin_registry_rejects_old_s3_alias() -> None:
    """Registry validation must accept MinIO and reject the removed S3 alias."""
    from floe_core.schemas.plugins import PLUGIN_REGISTRY, validate_plugin_selection

    assert PLUGIN_REGISTRY["storage"] == ["minio", "gcs", "azure-blob"]
    validate_plugin_selection("storage", "minio")

    try:
        validate_plugin_selection("storage", OLD_STORAGE_TYPE)
    except ValueError as exc:
        assert OLD_STORAGE_TYPE in str(exc)
    else:
        raise AssertionError("storage s3 alias unexpectedly accepted")


def test_runtime_plugin_registry_exposes_minio_without_s3_alias() -> None:
    """Runtime entry point discovery must expose MinIO and reject the old alias."""
    from floe_core.plugin_errors import PluginNotFoundError
    from floe_core.plugin_registry import PluginRegistry
    from floe_core.plugin_types import PluginType

    registry = PluginRegistry()
    registry.discover_all()

    storage_plugins = {plugin.name for plugin in registry.list(PluginType.STORAGE)}
    assert "minio" in storage_plugins
    assert OLD_STORAGE_TYPE not in storage_plugins
    assert registry.get(PluginType.STORAGE, "minio").name == "minio"

    with pytest.raises(PluginNotFoundError):
        registry.get(PluginType.STORAGE, OLD_STORAGE_TYPE)


def test_forbidden_patterns_cover_python_and_f_string_selection_forms() -> None:
    """The active scan must catch old plugin selection forms beyond YAML."""
    old_type = OLD_STORAGE_TYPE
    forbidden_lines = [
        f'PluginSelection(type="{old_type}")',
        f"PluginRef(type='{old_type}')",
        f'selection = {{"type": "{old_type}"}}',
        f'selection = {{"type": f"{old_type}"}}',
        f'PluginSelection(type=f"{old_type}")',
        f'storage="{old_type}"',
        f'storage=f"{old_type}"',
        f'storage: {{"{old_type}"}}',
    ]

    for line in forbidden_lines:
        assert any(pattern.search(line) for pattern in FORBIDDEN_PATTERNS), line


def test_forbidden_patterns_allow_s3_protocol_forms() -> None:
    """The scan must distinguish S3-compatible protocol syntax from plugin identity."""
    allowed_lines = [
        'warehouse_uri = "s3://warehouse/bronze/"',
        'properties = {"s3.endpoint": "http://minio:9000"}',
        "storage_protocol = 's3-compatible'",
        "storage: " + OLD_STORAGE_TYPE + "://warehouse/bronze/",
        "type: " + OLD_STORAGE_TYPE + "-compatible",
    ]

    for line in allowed_lines:
        assert not any(pattern.search(line) for pattern in FORBIDDEN_PATTERNS), line


def test_allowed_non_plugin_s3_references_are_narrow() -> None:
    """DuckDB S3 secret syntax is allowed without restoring the old plugin alias."""
    assert _is_allowed_non_plugin_s3_reference(
        REPO_ROOT / "tests/e2e/conftest.py",
        '        f"        - type: ' + OLD_STORAGE_TYPE + '\\n"',
    )
    assert _is_allowed_non_plugin_s3_reference(
        REPO_ROOT / "tests/e2e/test_dbt_e2e_profile.py",
        '            isinstance(secret_entry, dict) and secret_entry.get("type") == "'
        + OLD_STORAGE_TYPE
        + '"',
    )
    assert not _is_allowed_non_plugin_s3_reference(
        REPO_ROOT / "demo/customer_360/floe.yaml",
        "type: " + OLD_STORAGE_TYPE,
    )


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
                relative == ignored
                or relative.startswith(f"{ignored}/")
                or ignored in candidate.relative_to(REPO_ROOT).parts
                for ignored in IGNORED_SCAN_PARTS
            ):
                continue
            files.append(candidate)
    return files


def test_active_scan_files_ignore_nested_generated_directories() -> None:
    """Scans must not inspect generated environments under package roots."""
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in _active_scan_files()}

    assert not any("/.venv/" in path for path in scanned)
    assert not any("/__pycache__/" in path for path in scanned)


def test_active_scan_files_ignore_historical_and_generated_docs() -> None:
    """Scans must skip historical evidence and generated docs-site output."""
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in _active_scan_files()}

    assert not any(path.startswith("docs/validation/") for path in scanned)
    assert not any(path.startswith("docs-site/.astro/") for path in scanned)
    assert not any(path.startswith("docs-site/dist/") for path in scanned)
    assert not any(path.startswith("docs-site/node_modules/") for path in scanned)
    assert not any(path.startswith("docs-site/src/content/docs/") for path in scanned)


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
                    if _is_allowed_non_plugin_s3_reference(path, line):
                        continue
                    matches.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: {pattern.pattern}"
                    )

    assert matches == []
