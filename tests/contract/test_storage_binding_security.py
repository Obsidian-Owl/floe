"""Security assertions for compiled storage bindings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from floe_core.cli.helm.generate import _storage_helm_values
from floe_core.compilation.stages import compile_pipeline

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_STORAGE_SECRET_VALUES = [
    "minio" + "admin",
    "minio" + "admin123",
    "rootPassword",
]
EXPECTED_MINIO_CREDENTIAL_SECRET = "floe-platform-minio-credentials"  # pragma: allowlist secret


def _compile_demo_artifacts() -> Any:
    """Compile the demo product without emitting external lineage events."""
    return compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        ROOT / "demo" / "manifest.yaml",
        emit_lineage=False,
    )


def test_compiled_demo_storage_binding_does_not_contain_secret_values() -> None:
    """Compiled storage binding must reference credentials without raw values."""
    artifacts = _compile_demo_artifacts()

    assert artifacts.plugins.storage.type == "minio"
    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    assert artifacts.deployment.storage.provider == "minio"

    payload = artifacts.deployment.storage.model_dump_json()
    assert "floe-platform-minio-credentials" in payload
    for forbidden in FORBIDDEN_STORAGE_SECRET_VALUES:
        assert forbidden not in payload


def test_compiled_artifact_does_not_contain_minio_secret_values() -> None:
    """Full compiled artifact must not contain raw MinIO credential values."""
    artifacts = _compile_demo_artifacts()

    assert artifacts.plugins is not None
    assert artifacts.plugins.storage is not None
    assert artifacts.plugins.storage.config is not None
    assert "credential_secret_name" in artifacts.plugins.storage.config

    payload = artifacts.model_dump_json()

    for forbidden in FORBIDDEN_STORAGE_SECRET_VALUES:
        assert forbidden not in payload


def test_storage_helm_values_use_secret_refs_not_storage_secret_values() -> None:
    """Artifact-derived Helm values must carry Secret refs, not credential values."""
    artifacts = _compile_demo_artifacts()

    values = _storage_helm_values(artifacts)
    polaris_s3 = values["polaris"]["storage"]["s3"]

    assert values["minio"]["auth"] == {"existingSecret": EXPECTED_MINIO_CREDENTIAL_SECRET}
    assert polaris_s3["credentialSecretName"] == EXPECTED_MINIO_CREDENTIAL_SECRET
    assert polaris_s3["accessKeySecretKey"] == "root-user"  # pragma: allowlist secret
    assert polaris_s3["secretKeySecretKey"] == "root-password"  # pragma: allowlist secret
    assert "accessKey" not in polaris_s3
    assert "secretKey" not in polaris_s3

    payload = str(values)
    for forbidden in FORBIDDEN_STORAGE_SECRET_VALUES:
        assert forbidden not in payload


def test_first_party_runtime_paths_do_not_consume_storage_pyiceberg_helper() -> None:
    """Dagster and writer runtime code must not consume storage-owned catalog config."""
    repo_root = Path(__file__).resolve().parents[2]
    searched_roots = [
        repo_root / "plugins" / "floe-orchestrator-dagster" / "src",
        repo_root / "packages" / "floe-iceberg" / "src",
    ]
    offenders: list[str] = []

    for root in searched_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "def get_pyiceberg_catalog_config" in text:
                continue
            if "get_pyiceberg_catalog_config(" in text:
                offenders.append(str(path.relative_to(repo_root)))

    assert offenders == []
