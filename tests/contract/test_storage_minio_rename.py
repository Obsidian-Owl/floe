"""Contract tests for the strict MinIO storage plugin rename."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_PACKAGE_NAME = "floe-storage-" + "s3"
OLD_MODULE_NAME = "floe_storage_" + "s3"
OLD_PLUGIN_CLASS = "S3" + "StoragePlugin"
NEW_PACKAGE_NAME = "floe-storage-minio"


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
