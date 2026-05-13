from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

from testing.release.manifest import (
    ReleaseManifestError,
    load_release_manifest,
    validate_release_manifest,
)


def main() -> None:
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

    args = parser.parse_args()
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
    except ReleaseManifestError as exc:
        _fail(str(exc))

    _fail(f"unknown command: {args.command}")


def _resolve_manifest_path(repo_root: Path, manifest_path: str) -> Path:
    path = Path(manifest_path)
    if path.is_absolute():
        return path
    return repo_root / path


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
