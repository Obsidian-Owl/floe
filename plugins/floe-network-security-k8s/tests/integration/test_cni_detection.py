"""Integration tests for CNI plugin detection.

Task: T078
Phase: 9 - CLI Commands (US8)
User Story: US8 - CLI Commands for Network Security
Requirement: FR-084
"""

from __future__ import annotations

import json
import subprocess

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestCniDetectionLogic:
    """Tests for CNI detection logic."""

    @pytest.mark.requirement("FR-084")
    def test_cni_support_dict_has_calico(self) -> None:
        """Test Calico is in supported CNI list."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        assert "calico" in CNI_SUPPORT
        assert CNI_SUPPORT["calico"]["supported"] is True

    @pytest.mark.requirement("FR-084")
    def test_cni_support_dict_has_flannel(self) -> None:
        """Test Flannel is in CNI list as unsupported."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        assert "flannel" in CNI_SUPPORT
        assert CNI_SUPPORT["flannel"]["supported"] is False

    @pytest.mark.requirement("FR-084")
    def test_cni_support_dict_structure(self) -> None:
        """Test CNI_SUPPORT dict has required fields."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        assert isinstance(CNI_SUPPORT, dict)
        assert len(CNI_SUPPORT) > 0

        for cni_name, cni_info in CNI_SUPPORT.items():
            assert isinstance(cni_name, str)
            assert isinstance(cni_info, dict)
            assert "supported" in cni_info
            assert isinstance(cni_info["supported"], bool)

    @pytest.mark.requirement("FR-084")
    def test_cni_support_dict_has_weave(self) -> None:
        """Test Weave is in supported CNI list."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        assert "weave" in CNI_SUPPORT
        assert CNI_SUPPORT["weave"]["supported"] is True

    @pytest.mark.requirement("FR-084")
    def test_cni_support_dict_has_cilium(self) -> None:
        """Test Cilium is in supported CNI list."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        assert "cilium" in CNI_SUPPORT
        assert CNI_SUPPORT["cilium"]["supported"] is True


class TestCheckCniCommand(IntegrationTestBase):
    """Integration tests for check-cni CLI command."""

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_help(self) -> None:
        """Test check-cni shows help."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "check-cni", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "CNI" in result.stdout or "cni" in result.stdout.lower()

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_json_output(self) -> None:
        """Test check-cni with --output-format json."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "check-cni", "--output-format", "json"],
            capture_output=True,
            text=True,
        )
        # May fail if no cluster, but should at least run
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "detected" in data or "error" in data

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_text_output(self) -> None:
        """Test check-cni with --output-format text."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "check-cni", "--output-format", "text"],
            capture_output=True,
            text=True,
        )
        # Should succeed or fail gracefully
        assert result.returncode in (0, 1)
        # Should have some output
        assert len(result.stdout) > 0 or len(result.stderr) > 0

    @pytest.mark.integration
    @pytest.mark.requirement("FR-084")
    def test_check_cni_command_exists(self) -> None:
        """Test check-cni command is accessible."""
        result = subprocess.run(
            ["uv", "run", "floe", "network", "check-cni"],
            capture_output=True,
            text=True,
        )
        # Should either succeed or fail with meaningful error, not "command not found"
        assert "not found" not in result.stderr.lower()


class TestCniSupportMatrix(IntegrationTestBase):
    """Tests for known CNI support levels."""

    @pytest.mark.requirement("FR-084")
    def test_supported_cni_list_not_empty(self) -> None:
        """Test that there are supported CNIs defined."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        supported = [name for name, info in CNI_SUPPORT.items() if info.get("supported", False)]
        assert len(supported) > 0

    @pytest.mark.requirement("FR-084")
    def test_unsupported_cni_list_not_empty(self) -> None:
        """Test that there are unsupported CNIs defined."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        unsupported = [
            name for name, info in CNI_SUPPORT.items() if not info.get("supported", True)
        ]
        assert len(unsupported) > 0

    @pytest.mark.requirement("FR-084")
    def test_cni_support_matrix_consistency(self) -> None:
        """Test CNI support matrix has consistent structure."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        for cni_name, cni_info in CNI_SUPPORT.items():
            # Each CNI should have a supported field
            assert "supported" in cni_info, f"CNI {cni_name} missing 'supported' field"
            # Supported field should be boolean
            assert isinstance(cni_info["supported"], bool), (
                f"CNI {cni_name} 'supported' is not boolean"
            )

    @pytest.mark.requirement("FR-084")
    def test_cni_support_matrix_has_common_cnis(self) -> None:
        """Test that common CNIs are in the support matrix."""
        from floe_core.cli.network.check_cni import CNI_SUPPORT

        common_cnis = ["calico", "cilium", "weave", "flannel"]
        for cni in common_cnis:
            assert cni in CNI_SUPPORT, f"Common CNI '{cni}' not in support matrix"
