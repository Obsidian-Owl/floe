from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from testing.release.manifest import ReleaseManifest


class ReleaseBuildError(Exception):
    """Raised when release package build setup or execution fails."""


def package_paths_from_manifest(manifest: ReleaseManifest) -> list[str]:
    return [package.path for package in manifest.python_packages.publish]


def artifact_counts(dist_dir: Path) -> dict[str, int]:
    return {
        "wheels": len(list(dist_dir.glob("*.whl"))),
        "sdists": len(list(dist_dir.glob("*.tar.gz"))),
    }


def build_packages(manifest: ReleaseManifest, repo_root: Path, dist_dir: Path) -> None:
    _prepare_dist_dir(manifest, repo_root=repo_root, dist_dir=dist_dir)

    for package_path in package_paths_from_manifest(manifest):
        package_dir = repo_root / package_path
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "build",
                    package_dir.as_posix(),
                    "--outdir",
                    dist_dir.as_posix(),
                ],
                check=True,
                cwd=repo_root,
            )
        except subprocess.CalledProcessError as exc:
            raise ReleaseBuildError(
                f"package build failed for {package_path} with exit code {exc.returncode}",
            ) from exc


def _prepare_dist_dir(manifest: ReleaseManifest, *, repo_root: Path, dist_dir: Path) -> None:
    _validate_dist_dir(manifest, repo_root=repo_root, dist_dir=dist_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)


def _validate_dist_dir(manifest: ReleaseManifest, *, repo_root: Path, dist_dir: Path) -> None:
    resolved_repo_root = repo_root.resolve()
    resolved_dist_dir = dist_dir.resolve()

    if resolved_dist_dir == Path("/"):
        raise ReleaseBuildError("dist dir cannot be filesystem root")

    if resolved_dist_dir == resolved_repo_root:
        raise ReleaseBuildError("dist dir cannot be repository root")

    if resolved_dist_dir in resolved_repo_root.parents:
        raise ReleaseBuildError("dist dir cannot be a parent of repository root")

    package_dirs = {
        (resolved_repo_root / package_path).resolve()
        for package_path in package_paths_from_manifest(manifest)
    }
    if resolved_dist_dir in package_dirs:
        raise ReleaseBuildError("dist dir cannot be a manifest package directory")

    if dist_dir.exists() and (not dist_dir.is_dir() or dist_dir.is_symlink()):
        raise ReleaseBuildError("dist dir exists and is not a directory")

    if (
        dist_dir.exists()
        and any(dist_dir.iterdir())
        and not _is_relative_to(resolved_dist_dir, resolved_repo_root)
        and not _is_relative_to(resolved_dist_dir, Path("/tmp").resolve())
        and not (resolved_dist_dir.name == "dist" or resolved_dist_dir.name.startswith("floe-"))
    ):
        raise ReleaseBuildError(
            "refusing to delete non-empty external dist dir; use a repo dist dir, "
            "/tmp path, basename 'dist', or basename starting with 'floe-'",
        )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
