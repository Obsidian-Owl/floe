from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

import yaml

from testing.release.build_packages import ReleaseBuildError, artifact_counts, build_packages
from testing.release.manifest import (
    ReleaseManifestError,
    load_release_manifest,
    validate_release_manifest,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate Floe release manifest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--manifest", default="release/floe-release.yaml")
    validate_parser.add_argument("--tag", default=None)

    list_parser = subparsers.add_parser("package-list")
    list_parser.add_argument("--manifest", default="release/floe-release.yaml")
    list_parser.add_argument(
        "--format",
        choices=("json", "lines", "bash"),
        default="lines",
    )

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--manifest", default="release/floe-release.yaml")
    build_parser.add_argument("--dist-dir", default="dist")

    args = parser.parse_args(argv)
    repo_root = Path.cwd()
    manifest_path = _resolve_manifest_path(repo_root, args.manifest)

    try:
        manifest = load_release_manifest(manifest_path)
        if args.command == "validate":
            result = validate_release_manifest(manifest, repo_root=repo_root, tag=args.tag)
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
            return

        if args.command == "package-list":
            packages = [package.path for package in manifest.python_packages.publish]
            if args.format == "json":
                print(json.dumps(packages, indent=2))
            elif args.format == "bash":
                print(" ".join(packages))
            else:
                print("\n".join(packages))
            return

        if args.command == "build":
            validate_release_manifest(manifest, repo_root=repo_root)
            dist_dir = _resolve_path(repo_root, args.dist_dir)
            build_packages(manifest, repo_root=repo_root, dist_dir=dist_dir)
            counts = artifact_counts(dist_dir)
            expected = len(manifest.python_packages.publish)
            if counts["wheels"] != expected or counts["sdists"] != expected:
                raise ReleaseManifestError(
                    "built artifact count mismatch: "
                    f"expected {expected} wheels and {expected} sdists, "
                    f"got {counts['wheels']} wheels and {counts['sdists']} sdists",
                )
            print(json.dumps(counts, indent=2, sort_keys=True))
            return
    except (OSError, ReleaseBuildError, ReleaseManifestError, yaml.YAMLError) as exc:
        _fail(str(exc))

    _fail(f"unknown command: {args.command}")


def _resolve_manifest_path(repo_root: Path, manifest_path: str) -> Path:
    return _resolve_path(repo_root, manifest_path)


def _resolve_path(repo_root: Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repo_root / path


def _fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
