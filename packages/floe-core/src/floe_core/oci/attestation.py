"""SBOM generation and attestation management.

Implements:
    - FR-014: SBOM generation using syft CLI
    - FR-016: In-toto attestation attachment using cosign
    - FR-017: SBOM retrieval from artifact attestations

This module provides SBOM (Software Bill of Materials) generation and
attestation capabilities for OCI artifacts. Uses syft CLI for SPDX SBOM
generation and cosign CLI for attestation attachment.

External Dependencies:
    - syft: SBOM generation (https://github.com/anchore/syft)
    - cosign: Attestation attachment (https://github.com/sigstore/cosign)
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from opentelemetry import trace

from floe_core.schemas.signing import AttestationManifest, Subject

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

SPDX_PREDICATE_TYPE = "https://spdx.dev/Document"
IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v0.1"


class AttestationError(Exception):
    """Base exception for attestation operations."""

    pass


class SyftNotFoundError(AttestationError):
    """Raised when syft CLI is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "syft CLI not found. Install with: brew install syft (macOS) "
            "or see https://github.com/anchore/syft#installation"
        )


class CosignNotFoundError(AttestationError):
    """Raised when cosign CLI is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "cosign CLI not found. Install with: brew install cosign (macOS) "
            "or see https://github.com/sigstore/cosign#installation"
        )


class SBOMGenerationError(AttestationError):
    """Raised when SBOM generation fails."""

    def __init__(self, reason: str, stderr: str | None = None) -> None:
        self.reason = reason
        self.stderr = stderr
        msg = f"SBOM generation failed: {reason}"
        if stderr:
            msg += f"\n{stderr}"
        super().__init__(msg)


class AttestationAttachError(AttestationError):
    """Raised when attestation attachment fails."""

    def __init__(self, reason: str, stderr: str | None = None) -> None:
        self.reason = reason
        self.stderr = stderr
        msg = f"Attestation attachment failed: {reason}"
        if stderr:
            msg += f"\n{stderr}"
        super().__init__(msg)


def check_syft_available() -> bool:
    """Check if syft CLI is available on PATH."""
    return shutil.which("syft") is not None


def check_cosign_available() -> bool:
    """Check if cosign CLI is available on PATH."""
    return shutil.which("cosign") is not None


def generate_sbom(
    project_path: Path,
    output_format: str = "spdx-json",
) -> dict[str, Any]:
    """Generate SPDX SBOM for a project using syft CLI.

    Args:
        project_path: Path to project directory to scan
        output_format: Output format (spdx-json, cyclonedx-json, etc.)

    Returns:
        SBOM as dictionary (SPDX JSON format)

    Raises:
        SyftNotFoundError: If syft CLI is not installed
        SBOMGenerationError: If SBOM generation fails
    """
    with tracer.start_as_current_span("floe.oci.sbom.generate") as span:
        span.set_attribute("floe.sbom.project_path", str(project_path))
        span.set_attribute("floe.sbom.format", output_format)

        if not check_syft_available():
            raise SyftNotFoundError()

        if not project_path.exists():
            raise SBOMGenerationError(f"Project path does not exist: {project_path}")

        try:
            result = subprocess.run(
                ["syft", "packages", f"dir:{project_path}", "-o", output_format],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )

            sbom = json.loads(result.stdout)
            span.set_attribute("floe.sbom.package_count", len(sbom.get("packages", [])))
            logger.info(
                "SBOM generated: %s (%d packages)",
                project_path,
                len(sbom.get("packages", [])),
            )
            return sbom

        except subprocess.CalledProcessError as e:
            span.record_exception(e)
            raise SBOMGenerationError(
                f"syft exited with code {e.returncode}",
                stderr=e.stderr,
            ) from e
        except subprocess.TimeoutExpired as e:
            span.record_exception(e)
            raise SBOMGenerationError("syft timed out after 300 seconds") from e
        except json.JSONDecodeError as e:
            span.record_exception(e)
            raise SBOMGenerationError(f"Invalid JSON output from syft: {e}") from e


def generate_sbom_for_python_project(project_path: Path) -> dict[str, Any]:
    """Generate SBOM specifically for Python project with pyproject.toml/requirements.txt.

    This is a convenience wrapper that ensures Python-specific scanning.

    Args:
        project_path: Path to Python project root

    Returns:
        SBOM as dictionary (SPDX JSON format)
    """
    return generate_sbom(project_path, output_format="spdx-json")


def attach_attestation(
    artifact_ref: str,
    predicate_path: Path,
    predicate_type: str = SPDX_PREDICATE_TYPE,
    keyless: bool = True,
) -> None:
    """Attach attestation to OCI artifact using cosign.

    Args:
        artifact_ref: Full OCI artifact reference (e.g., registry/repo:tag)
        predicate_path: Path to predicate file (e.g., SBOM JSON)
        predicate_type: Predicate type URL (default: SPDX)
        keyless: Use keyless signing for attestation

    Raises:
        CosignNotFoundError: If cosign CLI is not installed
        AttestationAttachError: If attachment fails
    """
    with tracer.start_as_current_span("floe.oci.attestation.attach") as span:
        span.set_attribute("floe.artifact.ref", artifact_ref)
        span.set_attribute("floe.attestation.predicate_type", predicate_type)
        span.set_attribute("floe.attestation.keyless", keyless)

        if not check_cosign_available():
            raise CosignNotFoundError()

        if not predicate_path.exists():
            raise AttestationAttachError(f"Predicate file not found: {predicate_path}")

        cmd = [
            "cosign",
            "attest",
            "--predicate",
            str(predicate_path),
            "--type",
            _predicate_type_short(predicate_type),
        ]

        if keyless:
            cmd.append("--yes")

        cmd.append(artifact_ref)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )

            logger.info(
                "Attestation attached: %s (type: %s)",
                artifact_ref,
                predicate_type,
            )

        except subprocess.CalledProcessError as e:
            span.record_exception(e)
            raise AttestationAttachError(
                f"cosign exited with code {e.returncode}",
                stderr=e.stderr,
            ) from e
        except subprocess.TimeoutExpired as e:
            span.record_exception(e)
            raise AttestationAttachError("cosign timed out after 120 seconds") from e


def _predicate_type_short(predicate_type: str) -> str:
    """Convert predicate type URL to cosign short form."""
    type_map = {
        SPDX_PREDICATE_TYPE: "spdx",
        "https://cyclonedx.org/bom": "cyclonedx",
        "https://slsa.dev/provenance/v0.2": "slsaprovenance",
    }
    return type_map.get(predicate_type, "custom")


def retrieve_attestations(
    artifact_ref: str,
) -> list[AttestationManifest]:
    """Retrieve attestations attached to an OCI artifact.

    Args:
        artifact_ref: Full OCI artifact reference

    Returns:
        List of AttestationManifest objects

    Raises:
        CosignNotFoundError: If cosign CLI is not installed
        AttestationError: If retrieval fails
    """
    with tracer.start_as_current_span("floe.oci.attestation.retrieve") as span:
        span.set_attribute("floe.artifact.ref", artifact_ref)

        if not check_cosign_available():
            raise CosignNotFoundError()

        try:
            result = subprocess.run(
                [
                    "cosign",
                    "verify-attestation",
                    "--insecure-ignore-tlog",
                    "--insecure-ignore-sct",
                    artifact_ref,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                if "no matching attestations" in result.stderr.lower():
                    return []
                raise AttestationError(f"cosign verify-attestation failed: {result.stderr}")

            attestations = _parse_attestation_output(result.stdout, artifact_ref)
            span.set_attribute("floe.attestation.count", len(attestations))
            return attestations

        except subprocess.TimeoutExpired as e:
            span.record_exception(e)
            raise AttestationError("cosign timed out after 60 seconds") from e


def _parse_attestation_output(
    output: str,
    artifact_ref: str,
) -> list[AttestationManifest]:
    """Parse cosign verify-attestation output into AttestationManifest objects."""
    attestations = []

    for line in output.strip().split("\n"):
        if not line:
            continue

        try:
            envelope = json.loads(line)
            payload_b64 = envelope.get("payload", "")

            if payload_b64:
                import base64

                payload_bytes = base64.b64decode(payload_b64)
                statement = json.loads(payload_bytes)

                predicate_type = statement.get("predicateType", "")
                predicate = statement.get("predicate", {})
                subjects_data = statement.get("subject", [])

                subjects = [
                    Subject(
                        name=s.get("name", artifact_ref),
                        digest=s.get("digest", {}),
                    )
                    for s in subjects_data
                ]

                attestation = AttestationManifest(
                    predicate_type=predicate_type,
                    predicate=predicate,
                    subject=subjects,
                )
                attestations.append(attestation)

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse attestation: %s", e)
            continue

    return attestations


def retrieve_sbom(artifact_ref: str) -> dict[str, Any] | None:
    """Retrieve SBOM attestation from an OCI artifact.

    Convenience function that retrieves attestations and returns the SPDX SBOM.

    Args:
        artifact_ref: Full OCI artifact reference

    Returns:
        SBOM as dictionary, or None if no SBOM attestation found
    """
    attestations = retrieve_attestations(artifact_ref)

    for attestation in attestations:
        if attestation.predicate_type == SPDX_PREDICATE_TYPE:
            return dict(attestation.predicate)

    return None


def create_in_toto_statement(
    artifact_ref: str,
    artifact_digest: str,
    predicate_type: str,
    predicate: dict[str, Any],
) -> dict[str, Any]:
    """Create an in-toto statement for attestation.

    Args:
        artifact_ref: Artifact reference (name)
        artifact_digest: SHA256 digest of artifact
        predicate_type: Type URL for the predicate
        predicate: Predicate content (e.g., SBOM)

    Returns:
        In-toto statement dictionary
    """
    return {
        "_type": IN_TOTO_STATEMENT_TYPE,
        "predicateType": predicate_type,
        "subject": [
            {
                "name": artifact_ref,
                "digest": {"sha256": artifact_digest.replace("sha256:", "")},
            }
        ],
        "predicate": predicate,
    }


__all__ = [
    "AttestationError",
    "SyftNotFoundError",
    "CosignNotFoundError",
    "SBOMGenerationError",
    "AttestationAttachError",
    "check_syft_available",
    "check_cosign_available",
    "generate_sbom",
    "generate_sbom_for_python_project",
    "attach_attestation",
    "retrieve_attestations",
    "retrieve_sbom",
    "create_in_toto_statement",
    "SPDX_PREDICATE_TYPE",
    "IN_TOTO_STATEMENT_TYPE",
]
