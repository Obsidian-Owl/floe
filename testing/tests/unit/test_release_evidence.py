from __future__ import annotations

from pathlib import Path

from testing.release.evidence import (
    classify_live_validation_failure,
    write_evidence_summary,
)


def test_classifies_product_validation_failure() -> None:
    assert classify_live_validation_failure("pytest failed: assertion error") == "product"


def test_classifies_infrastructure_validation_failure() -> None:
    assert classify_live_validation_failure("resource_unavailable") == "infrastructure"


def test_classifies_credential_setup_validation_failure() -> None:
    assert classify_live_validation_failure("AWS_ACCESS_KEY_ID is required") == "credential-setup"


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
        aws_live_result="failed: AWS_SECRET_ACCESS_KEY is required",
        cleanup_result="passed",
    )

    summary = output_path.read_text(encoding="utf-8")

    assert "release-sha-example" in summary
    assert "release/floe-release.yaml" in summary
    assert "15" in summary
    assert "test-artifacts/devpod-run-20260513" in summary
    assert "credential-setup" in summary
    assert "passed" in summary
    assert "AWS_SECRET_ACCESS_KEY" not in summary
