from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from testing.release.manifest import ReleaseManifest, ReleaseManifestError


def package_paths_from_manifest(manifest: ReleaseManifest) -> list[str]:
    return [package.path for package in manifest.python_packages.publish]


def artifact_counts(dist_dir: Path) -> dict[str, int]:
    return {
        "wheels": len(list(dist_dir.glob("*.whl"))),
        "sdists": len(list(dist_dir.glob("*.tar.gz"))),
    }


def build_packages(manifest: ReleaseManifest, repo_root: Path, dist_dir: Path) -> None:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

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
            raise ReleaseManifestError(
                f"package build failed for {package_path} with exit code {exc.returncode}",
            ) from exc
