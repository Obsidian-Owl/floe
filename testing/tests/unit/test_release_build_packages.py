from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from testing.release import cli
from testing.release.build_packages import (
    ReleaseBuildError,
    artifact_counts,
    build_packages,
    package_paths_from_manifest,
)
from testing.release.manifest import load_release_manifest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "release" / "floe-release.yaml"


def test_package_paths_from_manifest_returns_alpha_publish_set() -> None:
    paths = package_paths_from_manifest(load_release_manifest(MANIFEST))

    assert len(paths) == 15
    assert "plugins/floe-storage-aws-s3" in paths
    assert "plugins/floe-catalog-glue" in paths
    assert "plugins/floe-alert-slack" not in paths
    assert "plugins/floe-dbt-fusion" not in paths


def test_artifact_counts_counts_wheels_and_sdists(tmp_path: Path) -> None:
    (tmp_path / "floe_core-0.1.0a1-py3-none-any.whl").write_text("", encoding="utf-8")
    (tmp_path / "floe_core-0.1.0a1.tar.gz").write_text("", encoding="utf-8")
    (tmp_path / "floe_core-0.1.0a1.zip").write_text("", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "ignored-0.1.0a1-py3-none-any.whl").write_text("", encoding="utf-8")

    assert artifact_counts(tmp_path) == {"wheels": 1, "sdists": 1}


def test_build_packages_rejects_repo_root_as_dist_dir_without_deleting_sentinel(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("do-not-delete", encoding="utf-8")

    with pytest.raises(ReleaseBuildError, match="repository root"):
        build_packages(
            load_release_manifest(manifest_path),
            repo_root=tmp_path,
            dist_dir=tmp_path,
        )

    assert sentinel.read_text(encoding="utf-8") == "do-not-delete"


def test_build_packages_rejects_manifest_package_directory_as_dist_dir(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    package_dir = tmp_path / "packages" / "floe-core"

    with pytest.raises(ReleaseBuildError, match="package directory"):
        build_packages(
            load_release_manifest(manifest_path),
            repo_root=tmp_path,
            dist_dir=package_dir,
        )

    assert (package_dir / "pyproject.toml").exists()


def test_build_packages_rejects_external_tmp_dist_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    external_dist = Path("/tmp/floe-alpha-dist-unit-test")

    monkeypatch.setattr(subprocess, "run", _successful_build)
    try:
        with pytest.raises(ReleaseBuildError, match="inside repository root"):
            build_packages(
                load_release_manifest(manifest_path),
                repo_root=tmp_path,
                dist_dir=external_dist,
            )
    finally:
        if external_dist.exists() and external_dist.is_dir() and not external_dist.is_symlink():
            external_dist.rmdir()


def test_build_packages_rejects_external_dist_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    manifest_path = _write_manifest(repo_root)
    external_dist = tmp_path / "dist"

    monkeypatch.setattr(subprocess, "run", _successful_build)

    with pytest.raises(ReleaseBuildError, match="inside repository root"):
        build_packages(
            load_release_manifest(manifest_path),
            repo_root=repo_root,
            dist_dir=external_dist,
        )

    assert not external_dist.exists()


def test_build_packages_rejects_source_control_dist_dir_without_deleting_sentinel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    testing_dir = tmp_path / "testing"
    testing_dir.mkdir()
    sentinel = testing_dir / "sentinel.txt"
    sentinel.write_text("do-not-delete", encoding="utf-8")

    monkeypatch.setattr(subprocess, "run", _successful_build)

    with pytest.raises(ReleaseBuildError, match="source/control directory"):
        build_packages(
            load_release_manifest(manifest_path),
            repo_root=tmp_path,
            dist_dir=testing_dir,
        )

    assert sentinel.read_text(encoding="utf-8") == "do-not-delete"


def test_build_packages_wraps_subprocess_failure_in_release_build_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path)

    def fail_build(
        args: list[str],
        *,
        check: bool,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=7, cmd=args)

    monkeypatch.setattr(subprocess, "run", fail_build)

    with pytest.raises(ReleaseBuildError, match="floe-core.*exit code 7") as exc_info:
        build_packages(
            load_release_manifest(manifest_path),
            repo_root=tmp_path,
            dist_dir=tmp_path / "dist",
        )

    assert isinstance(exc_info.value.__cause__, subprocess.CalledProcessError)


def test_build_packages_removes_stale_files_from_allowed_dist_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    stale = dist_dir / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    monkeypatch.setattr(subprocess, "run", _successful_build)

    build_packages(
        load_release_manifest(manifest_path),
        repo_root=tmp_path,
        dist_dir=dist_dir,
    )

    assert not stale.exists()
    assert dist_dir.is_dir()


def test_build_packages_invokes_subprocess_with_safe_build_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    dist_dir = tmp_path / "dist"
    calls: list[dict[str, object]] = []

    def capture_run(
        args: list[str],
        *,
        check: bool,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, "check": check, "cwd": cwd})
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(subprocess, "run", capture_run)

    build_packages(load_release_manifest(manifest_path), repo_root=tmp_path, dist_dir=dist_dir)

    assert calls == [
        {
            "args": [
                sys.executable,
                "-m",
                "build",
                (tmp_path / "packages" / "floe-core").as_posix(),
                "--outdir",
                dist_dir.as_posix(),
            ],
            "check": True,
            "cwd": tmp_path,
        },
    ]


def test_release_cli_build_prints_concise_error_for_build_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = _write_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "testing.release.cli.build_packages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ReleaseBuildError("unsafe dist dir")),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["build", "--manifest", str(manifest_path), "--dist-dir", "dist"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err == "error: unsafe dist dir\n"
    assert "Traceback" not in captured.err


def _write_manifest(repo_root: Path) -> Path:
    package_dir = repo_root / "packages" / "floe-core"
    package_dir.mkdir(parents=True)
    (package_dir / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "floe-core"
            version = "0.1.0a1"
            """,
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    manifest_path = repo_root / "release.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "release": {
                    "train": "alpha",
                    "git_tag": "v0.1.0-alpha.1",
                    "python_version": "0.1.0a1",
                    "helm_version": "0.1.0-alpha.1",
                },
                "python_packages": {
                    "publish": [
                        {
                            "path": "packages/floe-core",
                            "name": "floe-core",
                            "evidence": "current-main",
                        },
                    ],
                    "exclude": [],
                },
                "helm": {"alpha_policy": "publish", "charts": []},
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


def _successful_build(
    args: list[str],
    *,
    check: bool,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=0)
