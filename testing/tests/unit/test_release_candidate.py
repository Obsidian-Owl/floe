from __future__ import annotations

from pathlib import Path

import pytest

from testing.release.candidate import (
    ReleaseCandidateError,
    validate_release_candidate,
)


def _write_manifest(tmp_path: Path, tag: str = "v0.1.0-alpha.1") -> Path:
    manifest = tmp_path / "release" / "floe-release.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        f"""
release:
  train: alpha
  git_tag: {tag}
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
  charts:
    - charts/floe-platform
    - charts/floe-jobs
validation:
  require_current_main_ci: true
  require_package_build_dry_run: true
  require_full_devpod_e2e: true
  require_aws_provider_live: true
  allow_accepted_historical_evidence: false
""",
        encoding="utf-8",
    )
    return manifest


def _write_package_and_charts(tmp_path: Path) -> None:
    package = tmp_path / "packages" / "floe-core"
    package.mkdir(parents=True)
    package.joinpath("pyproject.toml").write_text(
        """
[project]
name = "floe-core"
version = "0.1.0a1"
""",
        encoding="utf-8",
    )
    for chart in ("floe-platform", "floe-jobs"):
        chart_dir = tmp_path / "charts" / chart
        chart_dir.mkdir(parents=True)
        chart_dir.joinpath("Chart.yaml").write_text(
            f"name: {chart}\nversion: 0.1.0-alpha.1\n",
            encoding="utf-8",
        )


def test_validate_release_candidate_accepts_matching_manifest_and_sha(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    result = validate_release_candidate(
        requested_version="v0.1.0-alpha.1",
        release_sha="0000000000000000000000000000000000000000",
        manifest_path=manifest,
        repo_root=tmp_path,
        existing_tags=(),
    )

    assert result.version == "v0.1.0-alpha.1"
    assert result.release_sha == "0000000000000000000000000000000000000000"
    assert result.python_version == "0.1.0a1"
    assert result.helm_version == "0.1.0-alpha.1"
    assert result.publish_count == 1


def test_validate_release_candidate_rejects_manifest_version_mismatch(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    with pytest.raises(ReleaseCandidateError, match="does not match manifest git_tag"):
        validate_release_candidate(
            requested_version="v0.1.0-alpha.2",
            release_sha="0000000000000000000000000000000000000000",
            manifest_path=manifest,
            repo_root=tmp_path,
            existing_tags=(),
        )


def test_validate_release_candidate_rejects_existing_tag(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    with pytest.raises(ReleaseCandidateError, match="release tag already exists"):
        validate_release_candidate(
            requested_version="v0.1.0-alpha.1",
            release_sha="0000000000000000000000000000000000000000",
            manifest_path=manifest,
            repo_root=tmp_path,
            existing_tags=("v0.1.0-alpha.1",),
        )


def test_validate_release_candidate_rejects_non_sha_release_ref(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    with pytest.raises(
        ReleaseCandidateError,
        match="release_sha must be a 40-character commit SHA",
    ):
        validate_release_candidate(
            requested_version="v0.1.0-alpha.1",
            release_sha="main",
            manifest_path=manifest,
            repo_root=tmp_path,
            existing_tags=(),
        )
