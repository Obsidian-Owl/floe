from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

import yaml

from testing.release.build_packages import ReleaseBuildError, artifact_counts, build_packages
from testing.release.candidate import ReleaseCandidateError, validate_release_candidate
from testing.release.cleanup import CleanupEvidence, cleanup_status, cleanup_summary
from testing.release.evidence import EvidenceSummaryError, write_evidence_summary
from testing.release.failure_issue import FailureIssue, issue_comment_body, issue_title
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

    candidate_parser = subparsers.add_parser("candidate")
    candidate_parser.add_argument("--manifest", default="release/floe-release.yaml")
    candidate_parser.add_argument("--version", required=True)
    candidate_parser.add_argument("--release-sha", required=True)
    candidate_parser.add_argument("--existing-tag", action="append", default=[])

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

    evidence_parser = subparsers.add_parser("evidence-summary")
    evidence_parser.add_argument("--release-sha", required=True)
    evidence_parser.add_argument("--manifest", required=True)
    evidence_parser.add_argument("--devpod-artifact", required=True)
    evidence_parser.add_argument("--aws-live-result", required=True)
    evidence_parser.add_argument("--cleanup-result", required=True)
    evidence_parser.add_argument("--output", required=True)
    evidence_parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow pre-tag placeholder evidence for planning runs only.",
    )

    cleanup_parser = subparsers.add_parser("cleanup-summary")
    cleanup_parser.add_argument("--devpod", required=True)
    cleanup_parser.add_argument("--hetzner", required=True)
    cleanup_parser.add_argument("--aws", required=True)

    issue_parser = subparsers.add_parser("failure-issue")
    issue_parser.add_argument("--lane", required=True)
    issue_parser.add_argument("--version", default=None)
    issue_parser.add_argument("--gate", required=True)
    issue_parser.add_argument("--classification", required=True)
    issue_parser.add_argument("--sha", required=True)
    issue_parser.add_argument("--run-url", required=True)
    issue_parser.add_argument("--log-excerpt", default="")
    issue_parser.add_argument("--cleanup-status", default="not-run")
    issue_parser.add_argument("--skipped-output", action="append", default=[])
    issue_parser.add_argument("--output", required=True)

    args = parser.parse_args(argv)
    repo_root = Path.cwd()

    if args.command == "cleanup-summary":
        evidence = CleanupEvidence(devpod=args.devpod, hetzner=args.hetzner, aws=args.aws)
        print(
            json.dumps(
                {
                    "status": cleanup_status(evidence),
                    "summary": cleanup_summary(evidence),
                },
                indent=2,
                sort_keys=True,
            ),
        )
        return

    if args.command == "failure-issue":
        issue = FailureIssue(
            lane=args.lane,
            version=args.version,
            gate=args.gate,
            classification=args.classification,
            sha=args.sha,
            run_url=args.run_url,
            log_excerpt=args.log_excerpt,
            cleanup_status=args.cleanup_status,
            skipped_outputs=tuple(args.skipped_output),
        )
        output = {
            "title": issue_title(issue),
            "body": issue_comment_body(issue),
        }
        Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        return

    manifest_path = _resolve_manifest_path(repo_root, args.manifest)

    try:
        manifest = load_release_manifest(manifest_path)
        if args.command == "candidate":
            result = validate_release_candidate(
                requested_version=args.version,
                release_sha=args.release_sha,
                manifest_path=manifest_path,
                repo_root=repo_root,
                existing_tags=tuple(args.existing_tag),
            )
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
            return

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

        if args.command == "evidence-summary":
            result = validate_release_manifest(manifest, repo_root=repo_root)
            write_evidence_summary(
                output_path=_resolve_path(repo_root, args.output),
                release_sha=args.release_sha,
                manifest_path=manifest_path.relative_to(repo_root),
                package_count=result.publish_count,
                devpod_artifact=args.devpod_artifact,
                aws_live_result=args.aws_live_result,
                cleanup_result=args.cleanup_result,
                publish_packages=tuple(
                    (package.name, package.evidence or "")
                    for package in manifest.python_packages.publish
                ),
                exclude_packages=tuple(
                    (package.name, package.reason or "")
                    for package in manifest.python_packages.exclude
                ),
                allow_placeholders=args.allow_placeholders,
            )
            return
    except (
        EvidenceSummaryError,
        OSError,
        ReleaseCandidateError,
        ReleaseBuildError,
        ReleaseManifestError,
        yaml.YAMLError,
    ) as exc:
        _fail(str(exc))

    _fail(f"unknown command: {args.command}")


def _resolve_manifest_path(repo_root: Path, manifest_path: str) -> Path:
    return _resolve_path(repo_root, manifest_path)


def _resolve_path(repo_root: Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        # Command handlers own path-safety validation because read and write
        # targets have different repository-boundary requirements.
        return path
    return repo_root / path


def _fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
