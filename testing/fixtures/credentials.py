"""Centralized test credentials module.

Provides functions to retrieve credentials for MinIO and Polaris services.
Each function reads from environment variables first, falling back to
demo/manifest.yaml values, with sensible hardcoded defaults as a last resort.

This is the SINGLE SOURCE of credential access for all Python tests and
fixtures. No test file should hardcode ``minioadmin``, ``demo-admin``, or
``demo-secret`` — import from here instead.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded defaults — used when both env vars and manifest are unavailable.
# These match the canonical values in demo/manifest.yaml.
# ---------------------------------------------------------------------------
_DEFAULT_POLARIS_CLIENT_ID = "demo-admin"
_DEFAULT_POLARIS_CLIENT_SECRET = "demo-secret"  # pragma: allowlist secret  # noqa: S105
_DEFAULT_POLARIS_ENDPOINT = "http://floe-platform-polaris:8181/api/catalog"
_DEFAULT_MINIO_ACCESS_KEY = "minioadmin"
_DEFAULT_MINIO_SECRET_KEY = "minioadmin"  # pragma: allowlist secret  # noqa: S105


def _default_manifest_path() -> Path:
    """Return the default path to ``demo/manifest.yaml`` relative to the repo root."""
    return Path(__file__).resolve().parents[2] / "demo" / "manifest.yaml"


def _read_manifest(manifest_path: Path | None) -> dict[str, Any]:
    """Safely read and parse a manifest YAML file.

    Returns an empty dict on any failure (missing file, invalid YAML, etc.)
    so callers can always fall through to defaults.

    Args:
        manifest_path: Path to the manifest file, or None for the default.

    Returns:
        Parsed YAML as a dict, or empty dict on failure.
    """
    if manifest_path is None:
        manifest_path = _default_manifest_path()

    if not manifest_path.is_file():
        return {}

    try:
        raw = yaml.safe_load(manifest_path.read_text())
        if not isinstance(raw, dict):
            return {}
        return raw
    except Exception:
        logger.debug("manifest_parse_failed", exc_info=True)
        return {}


def _env_or_none(name: str) -> str | None:
    """Read an env var, treating empty strings as unset.

    Args:
        name: Environment variable name.

    Returns:
        The value if non-empty, else None.
    """
    value = os.environ.get(name)
    if value is not None and value.strip() == "":
        return None
    return value


def get_minio_credentials(manifest_path: Path | None = None) -> tuple[str, str]:
    """Return (access_key, secret_key) for MinIO.

    Priority: env vars ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY``,
    then hardcoded MinIO defaults (``minioadmin`` / ``minioadmin``).

    MinIO credentials are not stored in the manifest — the manifest only
    has the storage endpoint/bucket/region. The ``manifest_path`` parameter
    is accepted for API consistency.

    Args:
        manifest_path: Unused — accepted for API consistency with other
            credential functions.

    Returns:
        Tuple of (access_key, secret_key).
    """
    access_key = _env_or_none("AWS_ACCESS_KEY_ID") or _DEFAULT_MINIO_ACCESS_KEY
    secret_key = _env_or_none("AWS_SECRET_ACCESS_KEY") or _DEFAULT_MINIO_SECRET_KEY
    return (access_key, secret_key)


def get_polaris_credentials(manifest_path: Path | None = None) -> tuple[str, str]:
    """Return (client_id, client_secret) for Polaris.

    Priority: env vars ``POLARIS_CLIENT_ID`` / ``POLARIS_CLIENT_SECRET``,
    then ``manifest_path`` (or default ``demo/manifest.yaml``),
    then hardcoded demo defaults.

    Args:
        manifest_path: Optional path to manifest.yaml. Defaults to
            ``demo/manifest.yaml`` relative to the repo root.

    Returns:
        Tuple of (client_id, client_secret).
    """
    env_id = _env_or_none("POLARIS_CLIENT_ID")
    env_secret = _env_or_none("POLARIS_CLIENT_SECRET")

    # If both env vars are set, skip manifest entirely
    if env_id is not None and env_secret is not None:
        return (env_id, env_secret)

    # Read manifest for any values not provided via env vars
    raw = _read_manifest(manifest_path)
    oauth2: dict[str, Any] = (
        raw.get("plugins", {}).get("catalog", {}).get("config", {}).get("oauth2", {})
    )

    client_id = env_id or str(oauth2.get("client_id", _DEFAULT_POLARIS_CLIENT_ID))
    client_secret = env_secret or str(oauth2.get("client_secret", _DEFAULT_POLARIS_CLIENT_SECRET))
    return (client_id, client_secret)


def get_polaris_endpoint(manifest_path: Path | None = None) -> str:
    """Return the Polaris REST catalog endpoint URI.

    Priority: env var ``POLARIS_ENDPOINT``, then ``manifest_path``
    (or default ``demo/manifest.yaml``), then hardcoded default.

    Args:
        manifest_path: Optional path to manifest.yaml.

    Returns:
        Polaris endpoint URI string.
    """
    env_endpoint = _env_or_none("POLARIS_ENDPOINT")
    if env_endpoint is not None:
        return env_endpoint

    raw = _read_manifest(manifest_path)
    uri = raw.get("plugins", {}).get("catalog", {}).get("config", {}).get("uri")

    if uri is not None:
        return str(uri)

    return _DEFAULT_POLARIS_ENDPOINT
