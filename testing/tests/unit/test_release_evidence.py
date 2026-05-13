from __future__ import annotations

from pathlib import Path

import pytest

from testing.release.cli import main
from testing.release.evidence import (
    EvidenceSummaryError,
    classify_live_validation_failure,
    write_evidence_summary,
)


def test_classifies_product_validation_failure() -> None:
    assert classify_live_validation_failure("pytest failed: assertion error") == "product"


def test_classifies_infrastructure_validation_failure() -> None:
    assert classify_live_validation_failure("resource_unavailable") == "infrastructure"


def test_classifies_credential_setup_validation_failure() -> None:
    assert classify_live_validation_failure("AWS_ACCESS_KEY_ID is required") == "credential-setup"
    assert classify_live_validation_failure("AccessDenied from sts:GetCallerIdentity") == (
        "credential-setup"
    )
    assert classify_live_validation_failure("ExpiredToken while creating client") == (
        "credential-setup"
    )
    assert classify_live_validation_failure("UnrecognizedClientException") == "credential-setup"
    assert classify_live_validation_failure("InvalidClientTokenId") == "credential-setup"
    assert classify_live_validation_failure("missing AWS region for profile alpha") == (
        "credential-setup"
    )


def test_classifies_cleanup_validation_failure() -> None:
    assert classify_live_validation_failure("Glue database still exists") == "cleanup"


def test_write_evidence_summary_records_release_evidence_without_secrets(tmp_path: Path) -> None:
    output_path = tmp_path / "release-evidence.md"

    write_evidence_summary(
        output_path=output_path,
        release_sha="release-sha-example",
        manifest_path=Path("release/floe-release.yaml"),
        package_count=15,
        devpod_artifact="test-artifacts/devpod-run-20260513",
        aws_live_result="passed",
        cleanup_result="passed",
    )

    summary = output_path.read_text(encoding="utf-8")

    assert "release-sha-example" in summary
    assert "release/floe-release.yaml" in summary
    assert "15" in summary
    assert "test-artifacts/devpod-run-20260513" in summary
    assert "passed" in summary


def test_write_evidence_summary_rejects_failed_aws_result_by_default(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "release-evidence.md"

    with pytest.raises(EvidenceSummaryError, match="aws_live_result must be passed"):
        write_evidence_summary(
            output_path=output_path,
            release_sha="release-sha-example",
            manifest_path=Path("release/floe-release.yaml"),
            package_count=15,
            devpod_artifact="test-artifacts/devpod-run-20260513",
            aws_live_result="failed: AWS_SECRET_ACCESS_KEY is required",
            cleanup_result="passed",
        )

    assert not output_path.exists()


def test_write_evidence_summary_rejects_failed_cleanup_result_by_default(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "release-evidence.md"

    with pytest.raises(EvidenceSummaryError, match="cleanup_result must be passed"):
        write_evidence_summary(
            output_path=output_path,
            release_sha="release-sha-example",
            manifest_path=Path("release/floe-release.yaml"),
            package_count=15,
            devpod_artifact="test-artifacts/devpod-run-20260513",
            aws_live_result="passed",
            cleanup_result="failed: orphan server still exists",
        )

    assert not output_path.exists()


def test_write_evidence_summary_rejects_fake_devpod_artifact_by_default(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "release-evidence.md"

    with pytest.raises(EvidenceSummaryError, match="devpod_artifact"):
        write_evidence_summary(
            output_path=output_path,
            release_sha="release-sha-example",
            manifest_path=Path("release/floe-release.yaml"),
            package_count=15,
            devpod_artifact="test-artifacts/not-real-fake-devpod-run",
            aws_live_result="passed",
            cleanup_result="passed",
        )

    assert not output_path.exists()


def test_write_evidence_summary_rejects_placeholder_evidence_by_default(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "release-evidence.md"

    with pytest.raises(EvidenceSummaryError, match="placeholder release evidence"):
        write_evidence_summary(
            output_path=output_path,
            release_sha="release-sha-example",
            manifest_path=Path("release/floe-release.yaml"),
            package_count=15,
            devpod_artifact="pre-tag-required",
            aws_live_result="passed",
            cleanup_result="passed",
        )

    assert not output_path.exists()


def test_write_evidence_summary_allows_placeholders_when_explicitly_enabled(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "release-evidence.md"

    write_evidence_summary(
        output_path=output_path,
        release_sha="release-sha-example",
        manifest_path=Path("release/floe-release.yaml"),
        package_count=15,
        devpod_artifact="pre-tag-required",
        aws_live_result="pre-tag-required",
        cleanup_result="pre-tag-required",
        allow_placeholders=True,
    )

    summary = output_path.read_text(encoding="utf-8")
    assert "pre-tag-required" in summary


def test_write_evidence_summary_allows_failed_statuses_when_placeholders_enabled(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "release-evidence.md"

    write_evidence_summary(
        output_path=output_path,
        release_sha="release-sha-example",
        manifest_path=Path("release/floe-release.yaml"),
        package_count=15,
        devpod_artifact="not-real-fake-artifact",
        aws_live_result="failed: AWS_SECRET_ACCESS_KEY is required",
        cleanup_result="failed: orphan server still exists",
        allow_placeholders=True,
    )

    summary = output_path.read_text(encoding="utf-8")
    assert "credential-setup" in summary
    assert "cleanup" in summary
    assert "not-real-fake-artifact" in summary


def test_write_evidence_summary_redacts_secret_like_values(tmp_path: Path) -> None:
    output_path = tmp_path / "release-evidence.md"
    github_token = "ghp_" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJ"
    github_pat = "github_pat_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    slack_token = "xoxb-" + "123456789012-abcdefghijkl"

    write_evidence_summary(
        output_path=output_path,
        release_sha="AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
        manifest_path=Path(
            "release/floe-release.yaml?token=abc123&X-Amz-Signature=deadbeef",
        ),
        package_count=15,
        devpod_artifact=(
            "https://ci.example.com/artifacts/devpod.log?"
            f"auth={github_token}&githubPat={github_pat}&slack={slack_token} "
            "https://ci.example.com/artifacts/devpod.log?token=abc123 "
            "Bearer eyJhbGciOiJIUzI1NiJ9.abc.def "
            "password=hunter2 secret=abc access_key="
            "ASIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret
        ),
        aws_live_result="passed",
        cleanup_result="passed",
        allow_placeholders=True,
    )

    summary = output_path.read_text(encoding="utf-8")

    assert "AKIA" not in summary
    assert "ASIA" not in summary
    assert "Bearer" not in summary
    assert "auth=" not in summary
    assert "ghp_" not in summary
    assert "github_pat_" not in summary
    assert "xoxb-" not in summary
    assert "token=" not in summary
    assert "X-Amz-Signature=" not in summary
    assert "password=" not in summary
    assert "secret=" not in summary
    assert "access_key=" not in summary
    assert "AWS_SECRET_ACCESS_KEY" not in summary
    assert "BEGIN " + "PRIVATE KEY" not in summary
    assert "[redacted" in summary


def test_write_evidence_summary_records_manifest_cutline_details(tmp_path: Path) -> None:
    output_path = tmp_path / "release-evidence.md"

    write_evidence_summary(
        output_path=output_path,
        release_sha="release-sha-example",
        manifest_path=Path("release/floe-release.yaml"),
        package_count=2,
        devpod_artifact="test-artifacts/devpod-run-20260513",
        aws_live_result="passed",
        cleanup_result="passed",
        publish_packages=(
            ("floe-core", "current-main"),
            ("floe-catalog-glue", "aws-live-required"),
        ),
        exclude_packages=(("floe-alert-slack", "no-composed-alpha-runtime-path"),),
    )

    summary = output_path.read_text(encoding="utf-8")
    assert "Published package cutline" in summary
    assert "| floe-core | `current-main` |" in summary
    assert "| floe-catalog-glue | `aws-live-required` |" in summary
    assert "Excluded package cutline" in summary
    assert "Excluded package count | `1`" in summary
    assert "| floe-alert-slack | `no-composed-alpha-runtime-path` |" in summary


def test_evidence_summary_requires_manifest_argument(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "evidence-summary",
                "--release-sha",
                "release-sha-example",
                "--devpod-artifact",
                "test-artifacts/devpod-run-20260513",
                "--aws-live-result",
                "passed",
                "--cleanup-result",
                "passed",
                "--output",
                "/tmp/floe-release-evidence.md",
            ],
        )

    assert exc_info.value.code != 0
    assert "--manifest" in capsys.readouterr().err


def test_evidence_summary_cli_writes_summary_after_manifest_validation(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "floe-release-evidence.md"

    main(
        [
            "evidence-summary",
            "--release-sha",
            "release-sha-example",
            "--manifest",
            "release/floe-release.yaml",
            "--devpod-artifact",
            "test-artifacts/devpod-run-20260513",
            "--aws-live-result",
            "passed",
            "--cleanup-result",
            "passed",
            "--output",
            str(output_path),
        ],
    )

    summary = output_path.read_text(encoding="utf-8")
    assert "release-sha-example" in summary
    assert "release/floe-release.yaml" in summary
    assert "Python package publish count | `15`" in summary
    assert "test-artifacts/devpod-run-20260513" in summary
    assert "| floe-core | `current-main` |" in summary
    assert "| floe-alert-slack | `no-composed-alpha-runtime-path` |" in summary
