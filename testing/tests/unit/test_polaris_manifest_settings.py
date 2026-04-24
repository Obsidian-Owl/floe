"""Unit tests for manifest-derived Polaris warehouse and scope helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from testing.fixtures.credentials import (
    get_polaris_scope,
    get_polaris_warehouse,
    resolve_manifest_path,
)


def _write_manifest(path: Path, content: dict[str, object]) -> Path:
    path.write_text(yaml.dump(content, default_flow_style=False))
    return path


def _make_manifest(tmp_path: Path, *, warehouse: str, scope: str | None) -> Path:
    oauth2: dict[str, str] = {
        "client_id": "demo-admin",
        "client_secret": "demo-secret",
        "token_url": "http://floe-platform-polaris:8181/api/catalog/v1/oauth/tokens",
    }
    if scope is not None:
        oauth2["scope"] = scope

    manifest = {
        "plugins": {
            "catalog": {
                "type": "polaris",
                "config": {
                    "uri": "http://floe-platform-polaris:8181/api/catalog",
                    "warehouse": warehouse,
                    "oauth2": oauth2,
                },
            }
        }
    }
    return _write_manifest(tmp_path / "manifest.yaml", manifest)


class TestGetPolarisWarehouse:
    """Tests for get_polaris_warehouse()."""

    def test_reads_manifest_value(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("POLARIS_WAREHOUSE", raising=False)
        manifest = _make_manifest(tmp_path, warehouse="custom-warehouse", scope="CUSTOM_SCOPE")

        assert get_polaris_warehouse(manifest_path=manifest) == "custom-warehouse"

    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("POLARIS_WAREHOUSE", "env-warehouse")
        manifest = _make_manifest(tmp_path, warehouse="manifest-warehouse", scope="CUSTOM_SCOPE")

        assert get_polaris_warehouse(manifest_path=manifest) == "env-warehouse"

    def test_missing_manifest_uses_demo_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("POLARIS_WAREHOUSE", raising=False)

        assert get_polaris_warehouse(manifest_path=tmp_path / "missing.yaml") == "floe-demo"

    def test_manifest_path_resolves_from_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        manifest = _make_manifest(tmp_path, warehouse="env-manifest-warehouse", scope="CUSTOM_SCOPE")
        monkeypatch.setenv("FLOE_MANIFEST_PATH", str(manifest))
        monkeypatch.delenv("POLARIS_WAREHOUSE", raising=False)

        assert resolve_manifest_path() == manifest
        assert get_polaris_warehouse() == "env-manifest-warehouse"


class TestGetPolarisScope:
    """Tests for get_polaris_scope()."""

    def test_reads_manifest_value(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("POLARIS_SCOPE", raising=False)
        manifest = _make_manifest(tmp_path, warehouse="custom-warehouse", scope="CUSTOM_SCOPE")

        assert get_polaris_scope(manifest_path=manifest) == "CUSTOM_SCOPE"

    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("POLARIS_SCOPE", "ENV_SCOPE")
        manifest = _make_manifest(tmp_path, warehouse="manifest-warehouse", scope="MANIFEST_SCOPE")

        assert get_polaris_scope(manifest_path=manifest) == "ENV_SCOPE"

    def test_missing_scope_uses_demo_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("POLARIS_SCOPE", raising=False)
        manifest = _make_manifest(tmp_path, warehouse="custom-warehouse", scope=None)

        assert get_polaris_scope(manifest_path=manifest) == "PRINCIPAL_ROLE:ALL"

    def test_scope_reads_from_manifest_path_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        manifest = _make_manifest(tmp_path, warehouse="custom-warehouse", scope="ENV_MANIFEST_SCOPE")
        monkeypatch.setenv("FLOE_MANIFEST_PATH", str(manifest))
        monkeypatch.delenv("POLARIS_SCOPE", raising=False)

        assert get_polaris_scope() == "ENV_MANIFEST_SCOPE"
