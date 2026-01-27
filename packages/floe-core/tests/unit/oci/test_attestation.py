"""Unit tests for OCI attestation module.

Task ID: T049, T050
Phase: 5 - User Story 3 (SBOM Generation and Attestation)
Requirements: FR-014, FR-016, FR-017
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.oci.attestation import (
    IN_TOTO_STATEMENT_TYPE,
    SPDX_PREDICATE_TYPE,
    AttestationAttachError,
    AttestationError,
    CosignNotFoundError,
    SBOMGenerationError,
    SyftNotFoundError,
    attach_attestation,
    check_cosign_available,
    check_syft_available,
    create_in_toto_statement,
    generate_sbom,
    generate_sbom_for_python_project,
    retrieve_attestations,
    retrieve_sbom,
)
from floe_core.schemas.signing import AttestationManifest, Subject

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_sbom() -> dict[str, Any]:
    """Sample SPDX SBOM for testing."""
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "test-project",
        "packages": [
            {
                "SPDXID": "SPDXRef-Package-1",
                "name": "click",
                "versionInfo": "8.1.0",
            },
            {
                "SPDXID": "SPDXRef-Package-2",
                "name": "pydantic",
                "versionInfo": "2.5.0",
            },
        ],
    }


@pytest.fixture
def mock_attestation_envelope() -> dict[str, Any]:
    """Sample attestation envelope from cosign verify-attestation."""
    statement = {
        "predicateType": SPDX_PREDICATE_TYPE,
        "predicate": {
            "spdxVersion": "SPDX-2.3",
            "packages": [{"name": "click", "versionInfo": "8.1.0"}],
        },
        "subject": [
            {
                "name": "harbor.example.com/floe:v1.0.0",
                "digest": {"sha256": "abc123def456"},
            }
        ],
    }
    payload_b64 = base64.b64encode(json.dumps(statement).encode()).decode()
    return {"payload": payload_b64}


class TestCheckToolsAvailable:
    """Tests for CLI tool availability checks."""

    @patch("shutil.which")
    def test_check_syft_available_found(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        assert check_syft_available() is True
        mock_which.assert_called_once_with("syft")

    @patch("shutil.which")
    def test_check_syft_available_not_found(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        assert check_syft_available() is False

    @patch("shutil.which")
    def test_check_cosign_available_found(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        assert check_cosign_available() is True
        mock_which.assert_called_once_with("cosign")

    @patch("shutil.which")
    def test_check_cosign_available_not_found(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        assert check_cosign_available() is False


class TestGenerateSBOM:
    """Tests for SBOM generation with mocked syft CLI (T049)."""

    @patch("shutil.which")
    def test_generate_sbom_syft_not_found(self, mock_which: MagicMock, tmp_path: Path) -> None:
        mock_which.return_value = None

        with pytest.raises(SyftNotFoundError) as exc_info:
            generate_sbom(tmp_path)

        assert "syft CLI not found" in str(exc_info.value)
        assert "brew install syft" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_generate_sbom_project_not_exists(
        self, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        nonexistent = Path("/nonexistent/project")

        with pytest.raises(SBOMGenerationError) as exc_info:
            generate_sbom(nonexistent)

        assert "does not exist" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_generate_sbom_success(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
        mock_sbom: dict[str, Any],
    ) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_sbom),
            stderr="",
        )

        result = generate_sbom(tmp_path)

        assert result["spdxVersion"] == "SPDX-2.3"
        assert len(result["packages"]) == 2
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "syft" in call_args[0][0]
        assert f"dir:{tmp_path}" in call_args[0][0]

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_generate_sbom_custom_format(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"bomFormat": "CycloneDX"}',
            stderr="",
        )

        result = generate_sbom(tmp_path, output_format="cyclonedx-json")

        call_args = mock_run.call_args
        assert "cyclonedx-json" in call_args[0][0]

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_generate_sbom_syft_error(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["syft"],
            stderr="Error scanning directory",
        )

        with pytest.raises(SBOMGenerationError) as exc_info:
            generate_sbom(tmp_path)

        assert "exited with code 1" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_generate_sbom_timeout(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["syft"], timeout=300)

        with pytest.raises(SBOMGenerationError) as exc_info:
            generate_sbom(tmp_path)

        assert "timed out" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_generate_sbom_invalid_json(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json",
            stderr="",
        )

        with pytest.raises(SBOMGenerationError) as exc_info:
            generate_sbom(tmp_path)

        assert "Invalid JSON" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_generate_sbom_for_python_project(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
        mock_sbom: dict[str, Any],
    ) -> None:
        mock_which.return_value = "/usr/local/bin/syft"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_sbom),
            stderr="",
        )

        result = generate_sbom_for_python_project(tmp_path)

        assert result["spdxVersion"] == "SPDX-2.3"
        call_args = mock_run.call_args
        assert "spdx-json" in call_args[0][0]


class TestAttachAttestation:
    """Tests for attestation attachment with mocked cosign CLI (T050)."""

    @patch("shutil.which")
    def test_attach_attestation_cosign_not_found(
        self, mock_which: MagicMock, tmp_path: Path
    ) -> None:
        mock_which.return_value = None
        predicate_file = tmp_path / "sbom.json"
        predicate_file.write_text("{}")

        with pytest.raises(CosignNotFoundError) as exc_info:
            attach_attestation("harbor.example.com/floe:v1.0.0", predicate_file)

        assert "cosign CLI not found" in str(exc_info.value)

    @patch("shutil.which")
    def test_attach_attestation_predicate_not_found(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        nonexistent = Path("/nonexistent/sbom.json")

        with pytest.raises(AttestationAttachError) as exc_info:
            attach_attestation("harbor.example.com/floe:v1.0.0", nonexistent)

        assert "not found" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_attach_attestation_success_keyless(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        predicate_file = tmp_path / "sbom.json"
        predicate_file.write_text('{"packages": []}')

        attach_attestation(
            "harbor.example.com/floe:v1.0.0",
            predicate_file,
            keyless=True,
        )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "cosign" in call_args
        assert "attest" in call_args
        assert "--yes" in call_args
        assert "harbor.example.com/floe:v1.0.0" in call_args

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_attach_attestation_custom_predicate_type(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        predicate_file = tmp_path / "sbom.json"
        predicate_file.write_text("{}")

        attach_attestation(
            "harbor.example.com/floe:v1.0.0",
            predicate_file,
            predicate_type="https://cyclonedx.org/bom",
        )

        call_args = mock_run.call_args[0][0]
        assert "cyclonedx" in call_args

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_attach_attestation_cosign_error(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["cosign"],
            stderr="Error attaching attestation",
        )

        predicate_file = tmp_path / "sbom.json"
        predicate_file.write_text("{}")

        with pytest.raises(AttestationAttachError) as exc_info:
            attach_attestation("harbor.example.com/floe:v1.0.0", predicate_file)

        assert "exited with code 1" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_attach_attestation_timeout(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cosign"], timeout=120)

        predicate_file = tmp_path / "sbom.json"
        predicate_file.write_text("{}")

        with pytest.raises(AttestationAttachError) as exc_info:
            attach_attestation("harbor.example.com/floe:v1.0.0", predicate_file)

        assert "timed out" in str(exc_info.value)


class TestRetrieveAttestations:
    """Tests for attestation retrieval."""

    @patch("shutil.which")
    def test_retrieve_attestations_cosign_not_found(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None

        with pytest.raises(CosignNotFoundError):
            retrieve_attestations("harbor.example.com/floe:v1.0.0")

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_retrieve_attestations_no_attestations(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="no matching attestations found",
        )

        result = retrieve_attestations("harbor.example.com/floe:v1.0.0")

        assert result == []

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_retrieve_attestations_success(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        mock_attestation_envelope: dict[str, Any],
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_attestation_envelope),
            stderr="",
        )

        result = retrieve_attestations("harbor.example.com/floe:v1.0.0")

        assert len(result) == 1
        assert result[0].predicate_type == SPDX_PREDICATE_TYPE
        assert len(result[0].subject) == 1

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_retrieve_attestations_timeout(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cosign"], timeout=60)

        with pytest.raises(AttestationError) as exc_info:
            retrieve_attestations("harbor.example.com/floe:v1.0.0")

        assert "timed out" in str(exc_info.value)


class TestRetrieveSBOM:
    """Tests for SBOM retrieval convenience function."""

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_retrieve_sbom_found(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        mock_attestation_envelope: dict[str, Any],
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_attestation_envelope),
            stderr="",
        )

        result = retrieve_sbom("harbor.example.com/floe:v1.0.0")

        assert result is not None
        assert "spdxVersion" in result

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_retrieve_sbom_not_found(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/local/bin/cosign"
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="no matching attestations found",
        )

        result = retrieve_sbom("harbor.example.com/floe:v1.0.0")

        assert result is None


class TestCreateInTotoStatement:
    """Tests for in-toto statement creation."""

    def test_create_in_toto_statement_basic(self, mock_sbom: dict[str, Any]) -> None:
        statement = create_in_toto_statement(
            artifact_ref="harbor.example.com/floe:v1.0.0",
            artifact_digest="sha256:abc123def456",
            predicate_type=SPDX_PREDICATE_TYPE,
            predicate=mock_sbom,
        )

        assert statement["_type"] == IN_TOTO_STATEMENT_TYPE
        assert statement["predicateType"] == SPDX_PREDICATE_TYPE
        assert len(statement["subject"]) == 1
        assert statement["subject"][0]["name"] == "harbor.example.com/floe:v1.0.0"
        assert statement["subject"][0]["digest"]["sha256"] == "abc123def456"
        assert statement["predicate"] == mock_sbom

    def test_create_in_toto_statement_strips_sha256_prefix(self) -> None:
        statement = create_in_toto_statement(
            artifact_ref="test",
            artifact_digest="sha256:abc123",
            predicate_type=SPDX_PREDICATE_TYPE,
            predicate={},
        )

        assert statement["subject"][0]["digest"]["sha256"] == "abc123"


class TestErrorClasses:
    """Tests for custom error classes."""

    def test_syft_not_found_error_message(self) -> None:
        error = SyftNotFoundError()
        assert "syft CLI not found" in str(error)
        assert "brew install syft" in str(error)

    def test_cosign_not_found_error_message(self) -> None:
        error = CosignNotFoundError()
        assert "cosign CLI not found" in str(error)
        assert "brew install cosign" in str(error)

    def test_sbom_generation_error_with_stderr(self) -> None:
        error = SBOMGenerationError(
            reason="command failed",
            stderr="detailed error output",
        )
        assert "command failed" in str(error)
        assert "detailed error output" in str(error)
        assert error.reason == "command failed"
        assert error.stderr == "detailed error output"

    def test_attestation_attach_error_without_stderr(self) -> None:
        error = AttestationAttachError(reason="auth failed")
        assert "auth failed" in str(error)
        assert error.stderr is None
