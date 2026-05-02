"""Unit tests for centralized credentials module.

Tests for testing.fixtures.credentials module. Validates that each credential
function correctly prioritises environment variables over manifest values,
and returns sensible defaults when neither source is available.

All tests use monkeypatch for env var manipulation and tmp_path for manifest
file mocking -- no real filesystem side-effects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from testing.fixtures.credentials import (
    get_minio_credentials,
    get_polaris_credentials,
    get_polaris_endpoint,
    get_polaris_oauth2_server_uri,
)

# ---------------------------------------------------------------------------
# Constants: canonical values from demo/manifest.yaml
# ---------------------------------------------------------------------------
MANIFEST_POLARIS_CLIENT_ID = "demo-admin"
MANIFEST_POLARIS_CLIENT_SECRET = "demo-secret"  # pragma: allowlist secret
MANIFEST_POLARIS_URI = "http://floe-platform-polaris:8181/api/catalog"
MANIFEST_POLARIS_OAUTH2_URI = "http://floe-platform-polaris:8181/api/catalog/v1/oauth/tokens"
MINIO_DEFAULT_ACCESS_KEY = "minioadmin"
MINIO_DEFAULT_SECRET_KEY = "minioadmin123"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_manifest(path: Path, content: dict[str, Any]) -> Path:
    """Write a YAML manifest to the given path and return it."""
    path.write_text(yaml.dump(content, default_flow_style=False))
    return path


def _make_valid_manifest(tmp_path: Path) -> Path:
    """Create a valid demo manifest and return its path."""
    manifest = {
        "plugins": {
            "catalog": {
                "type": "polaris",
                "config": {
                    "uri": MANIFEST_POLARIS_URI,
                    "warehouse": "floe-demo",
                    "oauth2": {
                        "client_id": MANIFEST_POLARIS_CLIENT_ID,
                        "client_secret": MANIFEST_POLARIS_CLIENT_SECRET,
                        "token_url": MANIFEST_POLARIS_OAUTH2_URI,
                    },
                },
            },
            "storage": {
                "type": "s3",
                "config": {
                    "endpoint": "http://floe-platform-minio:9000",
                    "bucket": "floe-iceberg",
                    "region": "us-east-1",
                    "path_style_access": True,
                },
            },
        },
    }
    return _write_manifest(tmp_path / "manifest.yaml", manifest)


# ---------------------------------------------------------------------------
# get_minio_credentials
# ---------------------------------------------------------------------------


class TestGetMinioCredentials:
    """Tests for get_minio_credentials()."""

    @pytest.mark.requirement("AC-2")
    def test_returns_defaults_when_no_env_vars(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When no env vars are set, returns minioadmin/minioadmin defaults."""
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        access_key, secret_key = get_minio_credentials(manifest_path=manifest)

        assert access_key == MINIO_DEFAULT_ACCESS_KEY
        assert secret_key == MINIO_DEFAULT_SECRET_KEY

    @pytest.mark.requirement("AC-2")
    def test_env_vars_override_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Env vars AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY take priority."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "custom-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "custom-secret")
        manifest = _make_valid_manifest(tmp_path)

        access_key, secret_key = get_minio_credentials(manifest_path=manifest)

        assert access_key == "custom-key"
        assert secret_key == "custom-secret"  # pragma: allowlist secret

    @pytest.mark.requirement("AC-2")
    def test_returns_defaults_when_manifest_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When manifest does not exist and no env vars, returns defaults."""
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        nonexistent = tmp_path / "does-not-exist.yaml"

        access_key, secret_key = get_minio_credentials(manifest_path=nonexistent)

        assert access_key == MINIO_DEFAULT_ACCESS_KEY
        assert secret_key == MINIO_DEFAULT_SECRET_KEY

    @pytest.mark.requirement("AC-2")
    def test_returns_tuple_of_two_strings(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Return type is a tuple of exactly two strings."""
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

        result = get_minio_credentials(manifest_path=tmp_path / "nonexistent.yaml")

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    @pytest.mark.requirement("AC-2")
    def test_env_var_only_access_key_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When only access key env var is set, secret should still come from env or default."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "only-key")
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        access_key, secret_key = get_minio_credentials(manifest_path=manifest)

        # Access key from env var
        assert access_key == "only-key"
        # Secret key falls back to default since env var not set
        assert secret_key == MINIO_DEFAULT_SECRET_KEY

    @pytest.mark.requirement("AC-2")
    def test_env_var_only_secret_key_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When only secret key env var is set, access key should fall back to default."""
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "only-secret")
        manifest = _make_valid_manifest(tmp_path)

        access_key, secret_key = get_minio_credentials(manifest_path=manifest)

        assert access_key == MINIO_DEFAULT_ACCESS_KEY
        assert secret_key == "only-secret"  # pragma: allowlist secret

    @pytest.mark.requirement("AC-2")
    def test_empty_env_vars_treated_as_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Empty string env vars should fall back to defaults (not return empty)."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "")

        access_key, secret_key = get_minio_credentials(manifest_path=tmp_path / "nonexistent.yaml")

        # Empty env vars should not be used -- fall back to defaults
        assert access_key == MINIO_DEFAULT_ACCESS_KEY
        assert secret_key == MINIO_DEFAULT_SECRET_KEY


# ---------------------------------------------------------------------------
# get_polaris_credentials
# ---------------------------------------------------------------------------


class TestGetPolarisCredentials:
    """Tests for get_polaris_credentials()."""

    @pytest.mark.requirement("AC-2")
    def test_reads_from_manifest_when_no_env_vars(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When no env vars set, reads client_id/client_secret from manifest."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        client_id, client_secret = get_polaris_credentials(manifest_path=manifest)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_env_vars_override_manifest(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Env vars POLARIS_CLIENT_ID/POLARIS_CLIENT_SECRET take priority over manifest."""
        monkeypatch.setenv("POLARIS_CLIENT_ID", "env-client")
        monkeypatch.setenv("POLARIS_CLIENT_SECRET", "env-secret")
        manifest = _make_valid_manifest(tmp_path)

        client_id, client_secret = get_polaris_credentials(manifest_path=manifest)

        assert client_id == "env-client"
        assert client_secret == "env-secret"  # pragma: allowlist secret

    @pytest.mark.requirement("AC-2")
    def test_returns_defaults_when_manifest_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When manifest is absent and no env vars, returns demo defaults."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        nonexistent = tmp_path / "no-such-file.yaml"

        client_id, client_secret = get_polaris_credentials(manifest_path=nonexistent)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_returns_tuple_of_two_strings(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Return type is a tuple of exactly two strings."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        result = get_polaris_credentials(manifest_path=manifest)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    @pytest.mark.requirement("AC-2")
    def test_manifest_wrong_structure_returns_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest exists but has wrong structure -- returns defaults, not crash."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        # Manifest with completely wrong structure
        bad_manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {"wrong_key": {"nested": "value"}},
        )

        client_id, client_secret = get_polaris_credentials(manifest_path=bad_manifest)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_manifest_missing_oauth2_section(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest exists with plugins.catalog but no oauth2 section."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        partial_manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "uri": "http://example.com",
                            # No oauth2 section
                        }
                    }
                }
            },
        )

        client_id, client_secret = get_polaris_credentials(manifest_path=partial_manifest)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_manifest_partial_oauth2_only_client_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest has oauth2.client_id but no client_secret -- secret gets default."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        partial_manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "oauth2": {
                                "client_id": "manifest-only-id",
                                # No client_secret
                            }
                        }
                    }
                }
            },
        )

        client_id, client_secret = get_polaris_credentials(manifest_path=partial_manifest)

        assert client_id == "manifest-only-id"
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_env_var_only_client_id_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When only POLARIS_CLIENT_ID env var set, secret comes from manifest."""
        monkeypatch.setenv("POLARIS_CLIENT_ID", "env-id-only")
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        client_id, client_secret = get_polaris_credentials(manifest_path=manifest)

        assert client_id == "env-id-only"
        # Secret should come from manifest since env var not set
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_env_var_only_client_secret_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When only POLARIS_CLIENT_SECRET env var set, id comes from manifest."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.setenv("POLARIS_CLIENT_SECRET", "env-secret-only")
        manifest = _make_valid_manifest(tmp_path)

        client_id, client_secret = get_polaris_credentials(manifest_path=manifest)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == "env-secret-only"  # pragma: allowlist secret

    @pytest.mark.requirement("AC-2")
    def test_empty_env_vars_treated_as_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Empty string env vars should fall back to manifest (not return empty)."""
        monkeypatch.setenv("POLARIS_CLIENT_ID", "")
        monkeypatch.setenv("POLARIS_CLIENT_SECRET", "")
        manifest = _make_valid_manifest(tmp_path)

        client_id, client_secret = get_polaris_credentials(manifest_path=manifest)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_manifest_with_different_credentials(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest with non-default credentials is correctly read (not hardcoded)."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        custom_manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "oauth2": {
                                "client_id": "production-admin",
                                "client_secret": "production-secret",  # pragma: allowlist secret
                            }
                        }
                    }
                }
            },
        )

        client_id, client_secret = get_polaris_credentials(manifest_path=custom_manifest)

        assert client_id == "production-admin"
        assert client_secret == "production-secret"  # pragma: allowlist secret

    @pytest.mark.requirement("AC-2")
    def test_manifest_yaml_is_empty_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Empty YAML file should return defaults, not crash."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        empty_manifest = tmp_path / "manifest.yaml"
        empty_manifest.write_text("")

        client_id, client_secret = get_polaris_credentials(manifest_path=empty_manifest)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET

    @pytest.mark.requirement("AC-2")
    def test_manifest_yaml_is_invalid_yaml(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Invalid YAML should return defaults, not raise."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        bad_yaml = tmp_path / "manifest.yaml"
        bad_yaml.write_text("{{not: valid: yaml: [[[")

        client_id, client_secret = get_polaris_credentials(manifest_path=bad_yaml)

        assert client_id == MANIFEST_POLARIS_CLIENT_ID
        assert client_secret == MANIFEST_POLARIS_CLIENT_SECRET


# ---------------------------------------------------------------------------
# get_polaris_endpoint
# ---------------------------------------------------------------------------


class TestGetPolarisEndpoint:
    """Tests for get_polaris_endpoint()."""

    @pytest.mark.requirement("AC-2")
    def test_reads_from_manifest_when_no_env_var(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When POLARIS_ENDPOINT env var is not set, reads URI from manifest."""
        monkeypatch.delenv("POLARIS_ENDPOINT", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        endpoint = get_polaris_endpoint(manifest_path=manifest)

        assert endpoint == MANIFEST_POLARIS_URI

    @pytest.mark.requirement("AC-2")
    def test_env_var_overrides_manifest(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """POLARIS_ENDPOINT env var takes priority over manifest."""
        monkeypatch.setenv("POLARIS_ENDPOINT", "http://custom:8181/api/catalog")
        manifest = _make_valid_manifest(tmp_path)

        endpoint = get_polaris_endpoint(manifest_path=manifest)

        assert endpoint == "http://custom:8181/api/catalog"

    @pytest.mark.requirement("AC-2")
    def test_returns_string(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Return type is a string."""
        monkeypatch.delenv("POLARIS_ENDPOINT", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        result = get_polaris_endpoint(manifest_path=manifest)

        assert isinstance(result, str)

    @pytest.mark.requirement("AC-2")
    def test_manifest_missing_returns_sensible_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When manifest missing and no env var, returns a default endpoint."""
        monkeypatch.delenv("POLARIS_ENDPOINT", raising=False)
        nonexistent = tmp_path / "no-manifest.yaml"

        endpoint = get_polaris_endpoint(manifest_path=nonexistent)

        # Should return a non-empty string as a sensible default
        assert isinstance(endpoint, str)
        assert len(endpoint) > 0
        # Default should contain the standard Polaris API path
        assert "/api/catalog" in endpoint

    @pytest.mark.requirement("AC-2")
    def test_manifest_wrong_structure_returns_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest with wrong structure returns default, not crash."""
        monkeypatch.delenv("POLARIS_ENDPOINT", raising=False)
        bad_manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {"unrelated": {"structure": True}},
        )

        endpoint = get_polaris_endpoint(manifest_path=bad_manifest)

        assert isinstance(endpoint, str)
        assert len(endpoint) > 0
        assert "/api/catalog" in endpoint

    @pytest.mark.requirement("AC-2")
    def test_manifest_with_different_uri(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest with non-default URI is correctly read (not hardcoded)."""
        monkeypatch.delenv("POLARIS_ENDPOINT", raising=False)
        custom_manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "uri": "http://production-polaris:9999/api/catalog",
                        }
                    }
                }
            },
        )

        endpoint = get_polaris_endpoint(manifest_path=custom_manifest)

        assert endpoint == "http://production-polaris:9999/api/catalog"

    @pytest.mark.requirement("AC-2")
    def test_empty_env_var_treated_as_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Empty POLARIS_ENDPOINT env var should fall back to manifest."""
        monkeypatch.setenv("POLARIS_ENDPOINT", "")
        manifest = _make_valid_manifest(tmp_path)

        endpoint = get_polaris_endpoint(manifest_path=manifest)

        assert endpoint == MANIFEST_POLARIS_URI

    @pytest.mark.requirement("AC-2")
    def test_manifest_catalog_missing_uri_field(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest has plugins.catalog.config but no uri field."""
        monkeypatch.delenv("POLARIS_ENDPOINT", raising=False)
        partial_manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "warehouse": "some-warehouse",
                            # No uri field
                        }
                    }
                }
            },
        )

        endpoint = get_polaris_endpoint(manifest_path=partial_manifest)

        assert isinstance(endpoint, str)
        assert len(endpoint) > 0
        assert "/api/catalog" in endpoint


# ---------------------------------------------------------------------------
# get_polaris_oauth2_server_uri
# ---------------------------------------------------------------------------


class TestGetPolarisOAuth2ServerUri:
    """Tests for get_polaris_oauth2_server_uri()."""

    @pytest.mark.requirement("AC-2")
    def test_env_var_overrides_manifest(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Explicit token endpoint env vars take priority."""
        monkeypatch.setenv("POLARIS_OAUTH2_SERVER_URI", "http://auth.example/token")
        manifest = _make_valid_manifest(tmp_path)

        uri = get_polaris_oauth2_server_uri(manifest_path=manifest)

        assert uri == "http://auth.example/token"

    @pytest.mark.requirement("AC-2")
    def test_derives_from_runtime_catalog_endpoint_before_manifest(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Runtime catalog endpoints should keep host and in-cluster paths aligned."""
        monkeypatch.delenv("POLARIS_OAUTH2_SERVER_URI", raising=False)
        monkeypatch.delenv("FLOE_E2E_POLARIS_OAUTH2_URI", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        uri = get_polaris_oauth2_server_uri(
            manifest_path=manifest,
            catalog_endpoint="http://localhost:18181/api/catalog",
        )

        assert uri == "http://localhost:18181/api/catalog/v1/oauth/tokens"

    @pytest.mark.requirement("AC-2")
    def test_reads_token_url_from_manifest_when_no_runtime_endpoint(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Manifest token_url is used when there is no explicit runtime endpoint."""
        monkeypatch.delenv("POLARIS_OAUTH2_SERVER_URI", raising=False)
        monkeypatch.delenv("FLOE_E2E_POLARIS_OAUTH2_URI", raising=False)
        manifest = _make_valid_manifest(tmp_path)

        uri = get_polaris_oauth2_server_uri(manifest_path=manifest)

        assert uri == MANIFEST_POLARIS_OAUTH2_URI

    @pytest.mark.requirement("AC-2")
    def test_derives_from_manifest_endpoint_when_token_url_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Missing token_url falls back to the manifest catalog endpoint."""
        monkeypatch.delenv("POLARIS_OAUTH2_SERVER_URI", raising=False)
        monkeypatch.delenv("FLOE_E2E_POLARIS_OAUTH2_URI", raising=False)
        manifest = _write_manifest(
            tmp_path / "manifest.yaml",
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "uri": "http://polaris.example/api/catalog",
                            "oauth2": {
                                "client_id": "id",
                                "client_secret": "secret",  # pragma: allowlist secret
                            },
                        }
                    }
                }
            },
        )

        uri = get_polaris_oauth2_server_uri(manifest_path=manifest)

        assert uri == "http://polaris.example/api/catalog/v1/oauth/tokens"


# ---------------------------------------------------------------------------
# Cross-cutting: API contract tests
# ---------------------------------------------------------------------------


class TestCredentialsAPIContract:
    """Tests that validate the module's public API shape."""

    @pytest.mark.requirement("AC-2")
    def test_module_exports_all_three_functions(self) -> None:
        """Module must export all three credential functions."""
        import testing.fixtures.credentials as creds_mod

        assert callable(getattr(creds_mod, "get_minio_credentials", None))
        assert callable(getattr(creds_mod, "get_polaris_credentials", None))
        assert callable(getattr(creds_mod, "get_polaris_endpoint", None))

    @pytest.mark.requirement("AC-2")
    def test_functions_accept_manifest_path_kwarg(self, tmp_path: Path) -> None:
        """All functions must accept manifest_path as a keyword argument."""
        manifest = _make_valid_manifest(tmp_path)

        # These should not raise TypeError for unexpected keyword argument.
        # They will raise NotImplementedError from the stub, which is expected
        # in the red phase. The real test is that manifest_path is accepted.
        for func in [get_minio_credentials, get_polaris_credentials, get_polaris_endpoint]:
            try:
                func(manifest_path=manifest)
            except NotImplementedError:
                pass  # Expected from stub
            except TypeError as exc:
                pytest.fail(f"{func.__name__} does not accept manifest_path kwarg: {exc}")

    @pytest.mark.requirement("AC-2")
    def test_credentials_isolation_between_calls(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Successive calls with different env vars return different results."""
        manifest = _make_valid_manifest(tmp_path)

        monkeypatch.setenv("POLARIS_CLIENT_ID", "first-call-id")
        monkeypatch.setenv("POLARIS_CLIENT_SECRET", "first-call-secret")
        first_id, first_secret = get_polaris_credentials(manifest_path=manifest)

        monkeypatch.setenv("POLARIS_CLIENT_ID", "second-call-id")
        monkeypatch.setenv("POLARIS_CLIENT_SECRET", "second-call-secret")
        second_id, second_secret = get_polaris_credentials(manifest_path=manifest)

        assert first_id == "first-call-id"
        assert first_secret == "first-call-secret"  # pragma: allowlist secret
        assert second_id == "second-call-id"
        assert second_secret == "second-call-secret"  # pragma: allowlist secret
        # Prove they are different (not cached/stale)
        assert first_id != second_id
        assert first_secret != second_secret

    @pytest.mark.requirement("AC-2")
    def test_no_caching_of_manifest_values(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Function must re-read manifest on each call, not cache stale values."""
        monkeypatch.delenv("POLARIS_CLIENT_ID", raising=False)
        monkeypatch.delenv("POLARIS_CLIENT_SECRET", raising=False)
        manifest_path = tmp_path / "manifest.yaml"

        # Write first manifest
        _write_manifest(
            manifest_path,
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "oauth2": {
                                "client_id": "first-id",
                                "client_secret": "first-secret",  # pragma: allowlist secret
                            }
                        }
                    }
                }
            },
        )
        first_id, first_secret = get_polaris_credentials(manifest_path=manifest_path)

        # Overwrite manifest with new values
        _write_manifest(
            manifest_path,
            {
                "plugins": {
                    "catalog": {
                        "config": {
                            "oauth2": {
                                "client_id": "second-id",
                                "client_secret": "second-secret",  # pragma: allowlist secret
                            }
                        }
                    }
                }
            },
        )
        second_id, second_secret = get_polaris_credentials(manifest_path=manifest_path)

        assert first_id == "first-id"
        assert second_id == "second-id"
        assert first_id != second_id
