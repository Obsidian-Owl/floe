"""Unit test fixtures for OCI client module.

This module provides fixtures specific to OCI client unit tests, which:
- Run without external services (no registries, no network)
- Use mocks/fakes for ORAS SDK, httpx, and external dependencies
- Execute quickly (< 1s per test)

Key Fixtures:
- mock_oras_client: Mocked ORAS client for push/pull operations
- mock_registry_config: Sample RegistryConfig for testing
- mock_artifact_manifest: Sample ArtifactManifest responses
- sample_compiled_artifacts: Valid CompiledArtifacts for push tests

For shared fixtures across all test tiers, see ../../conftest.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def sample_digest() -> str:
    """Return a valid SHA256 digest for testing.

    Returns:
        A valid sha256: prefixed digest string.
    """
    return "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@pytest.fixture
def sample_registry_uri() -> str:
    """Return a sample OCI registry URI.

    Returns:
        A valid oci:// prefixed registry URI.
    """
    return "oci://harbor.example.com/floe-platform"


@pytest.fixture
def mock_oras_client() -> MagicMock:
    """Create a mock ORAS client for unit testing.

    Returns:
        A MagicMock configured to mimic oras.client.OrasClient behavior.

    Usage:
        def test_push(mock_oras_client: MagicMock) -> None:
            mock_oras_client.push.return_value = "sha256:abc..."
            # Test push operation
    """
    client = MagicMock()
    client.login = MagicMock(return_value=None)
    client.push = MagicMock(return_value="sha256:abc123...")
    client.pull = MagicMock(return_value=Path("/tmp/artifact"))
    client.manifest = MagicMock(return_value={})
    return client


@pytest.fixture
def patch_oras_client(mock_oras_client: MagicMock) -> Generator[MagicMock, None, None]:
    """Patch oras.client.OrasClient with a mock.

    Args:
        mock_oras_client: The mock ORAS client fixture.

    Yields:
        The patched mock client.

    Usage:
        def test_push(patch_oras_client: MagicMock) -> None:
            # OrasClient is now mocked globally
            ...
    """
    with patch("oras.client.OrasClient", return_value=mock_oras_client) as mock_class:
        mock_class.return_value = mock_oras_client
        yield mock_oras_client


@pytest.fixture
def sample_manifest_response() -> dict[str, Any]:
    """Return a sample OCI manifest response.

    Returns:
        A dictionary representing an OCI artifact manifest.
    """
    return {
        "schemaVersion": 2,
        "artifactType": "application/vnd.floe.compiled-artifacts.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.empty.v1+json",
            "digest": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
            "size": 2,
        },
        "layers": [
            {
                "mediaType": "application/vnd.floe.compiled-artifacts.v1+json",
                "digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "size": 12345,
                "annotations": {
                    "org.opencontainers.image.title": "compiled_artifacts.json"
                },
            }
        ],
        "annotations": {
            "org.opencontainers.image.created": "2026-01-19T10:00:00Z",
            "io.floe.product.name": "test-product",
            "io.floe.product.version": "1.0.0",
        },
    }


@pytest.fixture
def sample_compiled_artifacts_dict() -> dict[str, Any]:
    """Return sample CompiledArtifacts as a dictionary.

    Returns:
        A dictionary that can be serialized as CompiledArtifacts JSON.
    """
    return {
        "version": "0.2.0",
        "metadata": {
            "product_name": "test-product",
            "product_version": "1.0.0",
            "compiled_at": datetime.now(timezone.utc).isoformat(),
        },
        "dbt_profiles": {
            "default": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/test.duckdb",
                    }
                },
            }
        },
        "dagster_config": {},
    }


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory.

    Args:
        tmp_path: pytest's built-in temporary path fixture.

    Returns:
        Path to a temporary cache directory for testing.
    """
    cache_dir = tmp_path / "oci_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir
