from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from testing.release.manifest import ReleaseManifest

_PROTECTED_REPO_PATHS = frozenset(
    {
        ".git",
        ".github",
        "packages",
        "plugins",
        "tests",
        "testing",
        "docs",
        "charts",
        "release",
        "scripts",
    },
)


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

    if resolved_dist_dir == resolved_repo_root:
        raise ReleaseBuildError("dist dir cannot be repository root")

    if resolved_dist_dir in resolved_repo_root.parents:
        raise ReleaseBuildError("dist dir cannot be a parent of repository root")

    if not _is_relative_to(resolved_dist_dir, resolved_repo_root):
        raise ReleaseBuildError("dist dir must be inside repository root")

    if _has_symlink_path_component(dist_dir):
        raise ReleaseBuildError("dist dir cannot be a symlink or contain symlink components")

    package_dirs = {
        (resolved_repo_root / package_path).resolve()
        for package_path in package_paths_from_manifest(manifest)
    }
    if any(
        resolved_dist_dir == package_dir or _is_relative_to(resolved_dist_dir, package_dir)
        for package_dir in package_dirs
    ):
        raise ReleaseBuildError("dist dir cannot be a manifest package directory or descendant")

    protected_paths = {
        (resolved_repo_root / protected_path).resolve() for protected_path in _PROTECTED_REPO_PATHS
    }
    if any(
        resolved_dist_dir == protected_path or _is_relative_to(resolved_dist_dir, protected_path)
        for protected_path in protected_paths
    ):
        raise ReleaseBuildError("dist dir cannot be a source/control directory or descendant")

    if dist_dir.exists() and not dist_dir.is_dir():
        raise ReleaseBuildError("dist dir exists and is not a directory")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _has_symlink_path_component(path: Path) -> bool:
    if path.is_symlink():
        return True

    for parent in path.parents:
        if parent.is_symlink():
            return True
        if parent.exists():
            break

    return False
