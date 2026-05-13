from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from testing.release import cli
from testing.release.manifest import (
    ReleaseManifestError,
    load_release_manifest,
    normalize_tag_to_helm_version,
    normalize_tag_to_python_version,
    validate_release_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "release" / "floe-release.yaml"

ALPHA_PUBLISH = {
    "floe-core",
    "floe-iceberg",
    "floe-orchestrator-dagster",
    "floe-catalog-polaris",
    "floe-storage-minio",
    "floe-compute-duckdb",
    "floe-dbt-core",
    "floe-ingestion-dlt",
    "floe-telemetry-jaeger",
    "floe-rbac-k8s",
    "floe-network-security-k8s",
    "floe-lineage-marquez",
    "floe-quality-gx",
    "floe-storage-aws-s3",
    "floe-catalog-glue",
}

ALPHA_EXCLUDED = {
    "floe-alert-slack",
    "floe-alert-email",
    "floe-alert-alertmanager",
    "floe-alert-webhook",
    "floe-identity-keycloak",
    "floe-secrets-infisical",
    "floe-secrets-k8s",
    "floe-semantic-cube",
    "floe-dbt-fusion",
    "floe-telemetry-console",
    "floe-quality-dbt",
}


def test_normalizes_alpha_git_tag_to_pep440() -> None:
    assert normalize_tag_to_python_version("v0.1.0-alpha.1") == "0.1.0a1"
    assert normalize_tag_to_helm_version("v0.1.0-alpha.1") == "0.1.0-alpha.1"


def test_normalizes_non_alpha_git_tag_to_release_versions() -> None:
    assert normalize_tag_to_python_version("v0.1.1") == "0.1.1"
    assert normalize_tag_to_helm_version("v0.1.1") == "0.1.1"


def test_release_manifest_exists_and_matches_cutline() -> None:
    manifest = load_release_manifest(MANIFEST)

    publish_names = {pkg.name for pkg in manifest.python_packages.publish}
    excluded_names = {pkg.name for pkg in manifest.python_packages.exclude}

    assert publish_names == ALPHA_PUBLISH
    assert excluded_names == ALPHA_EXCLUDED
    assert publish_names.isdisjoint(excluded_names)


def test_release_manifest_validates_alpha_release_cutline() -> None:
    manifest = load_release_manifest(MANIFEST)

    result = validate_release_manifest(
        manifest,
        repo_root=REPO_ROOT,
        tag="v0.1.0-alpha.1",
    )

    assert result.publish_count == 15
    assert result.exclude_count == 11
    assert result.python_version == "0.1.0a1"
    assert result.git_tag == "v0.1.0-alpha.1"


def test_release_manifest_validates_non_alpha_release_tag(tmp_path: Path) -> None:
    _write_chart(tmp_path / "charts" / "floe-platform")
    _write_chart(tmp_path / "charts" / "floe-jobs")
    manifest_path = _write_manifest(
        tmp_path,
        release={
            "git_tag": "v0.1.1",
            "python_version": "0.1.1",
            "helm_version": "0.1.1",
        },
    )

    result = validate_release_manifest(
        load_release_manifest(manifest_path),
        repo_root=tmp_path,
        tag="v0.1.1",
    )

    assert result.python_version == "0.1.1"
    assert result.helm_version == "0.1.1"
    assert result.git_tag == "v0.1.1"


def test_manifest_declares_helm_alpha_publish_policy() -> None:
    manifest = load_release_manifest(MANIFEST)

    assert manifest.helm.alpha_policy == "publish"
    assert manifest.helm.charts == ("charts/floe-platform", "charts/floe-jobs")
    assert manifest.release.helm_version == "0.1.0-alpha.1"


def test_release_manifest_rejects_secret_like_values(tmp_path: Path) -> None:
    manifest_path = tmp_path / "floe-release.yaml"
    manifest_path.write_text(
        """
release:
  train: alpha
  git_tag: v0.1.0-alpha.1
  python_version: 0.1.0a1
  helm_version: 0.1.0-alpha.1
python_packages:
  publish:
    - path: packages/floe-core
      name: floe-core
      evidence: current-main
  exclude: []
helm:
  alpha_policy: publish
  charts: []
validation:
  require_current_main_ci: true
  require_package_build_dry_run: true
  require_full_devpod_e2e: true
  require_aws_provider_live: true
  allow_accepted_historical_evidence: true
aws_secret_access_key: not-allowed
""",
        encoding="utf-8",
    )

    with pytest.raises(ReleaseManifestError, match="secret-like key"):
        load_release_manifest(manifest_path)


def test_release_manifest_rejects_duplicate_publish_name(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        publish=[
            {"path": "packages/floe-core", "name": "floe-core", "evidence": "current-main"},
            {"path": "packages/floe-iceberg", "name": "floe-core", "evidence": "current-main"},
        ],
        exclude=[],
    )

    with pytest.raises(ReleaseManifestError, match="duplicate package name"):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_duplicate_package_path(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        publish=[
            {"path": "packages/floe-core", "name": "floe-core", "evidence": "current-main"},
            {
                "path": "packages/floe-core",
                "name": "floe-core-duplicate",
                "evidence": "current-main",
            },
        ],
        exclude=[],
    )

    with pytest.raises(ReleaseManifestError, match="duplicate package path"):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_unclassified_workspace_package(tmp_path: Path) -> None:
    _write_pyproject(tmp_path / "packages" / "unclassified-package", "unclassified-package")
    manifest_path = _write_manifest(
        tmp_path,
        publish=[
            {"path": "packages/floe-core", "name": "floe-core", "evidence": "current-main"},
        ],
        exclude=[],
    )

    with pytest.raises(ReleaseManifestError, match="unclassified workspace package"):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_invalid_helm_policy(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        helm={"alpha_policy": "skip", "charts": []},
    )

    with pytest.raises(ReleaseManifestError, match="unsupported helm.alpha_policy"):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_empty_alpha_helm_chart_set(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        helm={"alpha_policy": "publish", "charts": []},
    )

    with pytest.raises(ReleaseManifestError, match="missing alpha Helm publish chart"):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_partial_alpha_helm_chart_set(tmp_path: Path) -> None:
    _write_chart(tmp_path / "charts" / "floe-platform")
    manifest_path = _write_manifest(
        tmp_path,
        helm={"alpha_policy": "publish", "charts": ["charts/floe-platform"]},
    )

    with pytest.raises(ReleaseManifestError, match="missing alpha Helm publish chart"):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_duplicate_alpha_helm_chart_entries(
    tmp_path: Path,
) -> None:
    _write_chart(tmp_path / "charts" / "floe-platform")
    manifest_path = _write_manifest(
        tmp_path,
        helm={
            "alpha_policy": "publish",
            "charts": ["charts/floe-platform", "charts/floe-platform"],
        },
    )

    with pytest.raises(ReleaseManifestError, match="duplicate alpha Helm publish chart"):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_helm_version_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        release={"helm_version": "0.1.0-alpha.2"},
    )

    with pytest.raises(
        ReleaseManifestError,
        match="helm_version does not match normalized git tag",
    ):
        validate_release_manifest(
            load_release_manifest(manifest_path),
            repo_root=tmp_path,
            tag="v0.1.0-alpha.1",
        )


def test_release_manifest_rejects_stale_manifest_git_tag(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        release={"git_tag": "v0.1.0-alpha.2"},
    )

    with pytest.raises(
        ReleaseManifestError,
        match="manifest git_tag does not match release tag",
    ):
        validate_release_manifest(
            load_release_manifest(manifest_path),
            repo_root=tmp_path,
            tag="v0.1.0-alpha.1",
        )


@pytest.mark.parametrize(
    ("chart_path", "expected_error"),
    [
        ("/outside-chart", "must be relative"),
        ("../outside-chart", "must not traverse parents"),
        ("outside-chart", "must be under charts/"),
        ("charts/not-alpha", "not in the alpha allowlist"),
    ],
)
def test_release_manifest_rejects_unapproved_alpha_helm_chart_paths(
    tmp_path: Path,
    chart_path: str,
    expected_error: str,
) -> None:
    if chart_path.startswith("/"):
        chart_path = str(tmp_path / chart_path.removeprefix("/"))
    chart_directory = Path(chart_path)
    if not chart_directory.is_absolute():
        chart_directory = tmp_path / chart_directory
    _write_chart(chart_directory)
    manifest_path = _write_manifest(
        tmp_path,
        helm={"alpha_policy": "publish", "charts": [chart_path]},
    )

    with pytest.raises(ReleaseManifestError, match=expected_error):
        validate_release_manifest(load_release_manifest(manifest_path), repo_root=tmp_path)


def test_release_manifest_rejects_publish_entry_without_evidence(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        publish=[
            {"path": "packages/floe-core", "name": "floe-core", "evidence": ""},
        ],
        exclude=[],
    )

    with pytest.raises(ReleaseManifestError, match="evidence must be non-empty"):
        load_release_manifest(manifest_path)


def test_release_manifest_rejects_exclude_entry_without_reason(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        publish=[],
        exclude=[
            {"path": "packages/floe-core", "name": "floe-core", "reason": ""},
        ],
    )

    with pytest.raises(ReleaseManifestError, match="reason must be non-empty"):
        load_release_manifest(manifest_path)


@pytest.mark.parametrize(
    "secret_value",
    [
        "AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
        (
            "-----BEGIN PRIVATE KEY-----\n"  # pragma: allowlist secret
            "not-a-real-key\n"
            "-----END PRIVATE KEY-----"
        ),
    ],
)
def test_release_manifest_rejects_secret_like_scalar_values(
    tmp_path: Path,
    secret_value: str,
) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        publish=[
            {"path": "packages/floe-core", "name": "floe-core", "evidence": secret_value},
        ],
        exclude=[],
    )

    with pytest.raises(ReleaseManifestError, match="secret-like value"):
        load_release_manifest(manifest_path)


def test_release_manifest_allows_normal_release_evidence_values(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        publish=[
            {
                "path": "plugins/floe-storage-aws-s3",
                "name": "floe-storage-aws-s3",
                "evidence": "aws-live-required",
            },
        ],
        exclude=[],
    )

    manifest = load_release_manifest(manifest_path)

    assert manifest.python_packages.publish[0].evidence == "aws-live-required"


def test_release_cli_prints_concise_error_for_missing_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["release-cli", "validate", "--manifest", "missing.yaml"],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err.startswith("error: ")
    assert "missing.yaml" in captured.err
    assert "Traceback" not in captured.err


def test_release_cli_prints_concise_error_for_malformed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "broken.yaml"
    manifest_path.write_text("release: [", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["release-cli", "validate", "--manifest", str(manifest_path)],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err.startswith("error: ")
    assert "broken.yaml" in captured.err
    assert "Traceback" not in captured.err


def _write_manifest(
    repo_root: Path,
    *,
    release: dict[str, str] | None = None,
    publish: list[dict[str, str]] | None = None,
    exclude: list[dict[str, str]] | None = None,
    helm: dict[str, object] | None = None,
) -> Path:
    release_data = {
        "train": "alpha",
        "git_tag": "v0.1.0-alpha.1",
        "python_version": "0.1.0a1",
        "helm_version": "0.1.0-alpha.1",
    }
    if release:
        release_data.update(release)

    publish_entries = (
        publish
        if publish is not None
        else [
            {"path": "packages/floe-core", "name": "floe-core", "evidence": "current-main"},
        ]
    )
    exclude_entries = exclude if exclude is not None else []
    helm_data: dict[str, object] = {
        "alpha_policy": "publish",
        "charts": ["charts/floe-platform", "charts/floe-jobs"],
    }
    if helm:
        helm_data.update(helm)

    for entry in [*publish_entries, *exclude_entries]:
        _write_pyproject(
            repo_root / entry["path"],
            entry["name"],
            version=release_data["python_version"],
        )

    manifest_path = repo_root / "release.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "release": release_data,
                "python_packages": {
                    "publish": publish_entries,
                    "exclude": exclude_entries,
                },
                "helm": helm_data,
                "validation": {
                    "require_current_main_ci": True,
                    "require_package_build_dry_run": True,
                    "require_full_devpod_e2e": True,
                    "require_aws_provider_live": True,
                    "allow_accepted_historical_evidence": True,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


def _write_pyproject(path: Path, name: str, *, version: str = "0.1.0a1") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(
        dedent(
            f"""
            [project]
            name = "{name}"
            version = "{version}"
            """,
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_chart(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "Chart.yaml").write_text(
        dedent(
            f"""
            apiVersion: v2
            name: {path.name}
            version: 0.1.0-alpha.1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
