"""Runtime catalog configuration helpers for secret-free compiled artifacts."""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping
from typing import Any


def _set_if_missing(target: dict[str, Any], key: str, value: str | None) -> None:
    """Set a non-empty value only when the target field is absent or empty."""
    if value is None or value == "":
        return
    current = target.get(key)
    if current is None or current == "":
        target[key] = value


def _split_polaris_credential(value: str | None) -> tuple[str | None, str | None]:
    """Split ``POLARIS_CREDENTIAL`` without logging or exposing the secret."""
    if value is None or ":" not in value:
        return None, None
    client_id, client_secret = value.split(":", 1)
    return client_id or None, client_secret or None


def _catalog_uri_from_env(environ: Mapping[str, str]) -> str | None:
    """Return a Polaris REST catalog URI from runtime environment variables."""
    uri = environ.get("POLARIS_URI")
    if uri:
        return uri

    base_url = environ.get("POLARIS_URL")
    if not base_url:
        return None
    return base_url.rstrip("/") + "/api/catalog"


def _complete_polaris_config_from_env(
    config: dict[str, Any],
    environ: Mapping[str, str],
) -> dict[str, Any]:
    """Hydrate runtime-only Polaris fields omitted from CompiledArtifacts."""
    _set_if_missing(config, "uri", _catalog_uri_from_env(environ))
    _set_if_missing(config, "warehouse", environ.get("POLARIS_WAREHOUSE"))

    had_oauth2 = "oauth2" in config
    oauth2 = config.get("oauth2")
    if oauth2 is None:
        oauth2 = {}
    if not isinstance(oauth2, dict):
        return config

    credential_client_id, credential_client_secret = _split_polaris_credential(
        environ.get("POLARIS_CREDENTIAL")
    )
    _set_if_missing(oauth2, "client_id", environ.get("POLARIS_CLIENT_ID"))
    _set_if_missing(oauth2, "client_id", credential_client_id)
    _set_if_missing(oauth2, "client_secret", environ.get("POLARIS_CLIENT_SECRET"))
    _set_if_missing(oauth2, "client_secret", credential_client_secret)
    _set_if_missing(oauth2, "token_url", environ.get("POLARIS_TOKEN_URL"))
    _set_if_missing(oauth2, "token_url", environ.get("POLARIS_OAUTH2_URI"))
    _set_if_missing(oauth2, "scope", environ.get("POLARIS_SCOPE"))

    if had_oauth2 or oauth2:
        config["oauth2"] = oauth2
    return config


def runtime_catalog_config(
    catalog_type: str,
    config: dict[str, Any] | None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return catalog plugin config completed with runtime-only credentials."""
    runtime_config = copy.deepcopy(config or {})
    if catalog_type == "polaris":
        return _complete_polaris_config_from_env(
            runtime_config,
            os.environ if environ is None else environ,
        )
    return runtime_config
