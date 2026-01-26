"""Unit tests for network check-cni CLI command.

Task ID: FR-084
Phase: Network and Pod Security
Requirements: FR-084 - Verify CNI plugin supports NetworkPolicies

This module tests the `floe network check-cni` command which:
- Detects the CNI plugin running in the cluster
- Verifies NetworkPolicy support
- Reports compatibility status

Test Coverage:
- Command option parsing (--kubeconfig, --context, --verbose, --output-format)
- CNI support matrix (supported and unsupported plugins)
- Kubernetes client loading (in-cluster, kubeconfig, context)
- CNI detection from DaemonSets
- Output formatting (text and JSON)
- Exit codes (success, unsupported, not detected, connection error)
- Command execution with various CNI plugins
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.network.check_cni import (
    CNI_SUPPORT,
    _detect_cni,
    _format_json_output,
    _format_text_output,
    _load_kubernetes_client,
    check_cni_command,
)
from floe_core.cli.utils import ExitCode

if TYPE_CHECKING:
    pass


# =============================================================================
# TestCheckCniCommandOptions - Test command option parsing
# =============================================================================


class TestCheckCniCommandOptions:
    """Test check-cni command option parsing."""

    @pytest.mark.requirement("FR-084")
    def test_accepts_kubeconfig_option(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that --kubeconfig option is accepted."""
        kubeconfig = tmp_path / "kubeconfig"
        kubeconfig.write_text("fake-kubeconfig")

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.side_effect = SystemExit(ExitCode.NETWORK_ERROR)

            cli_runner.invoke(
                check_cni_command,
                ["--kubeconfig", str(kubeconfig)],
            )

            # Should attempt to load with kubeconfig path
            mock_load.assert_called_once()
            args = mock_load.call_args[0]
            assert args[0] == kubeconfig

    @pytest.mark.requirement("FR-084")
    def test_accepts_context_option(self, cli_runner: CliRunner) -> None:
        """Test that --context option is accepted."""
        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.side_effect = SystemExit(ExitCode.NETWORK_ERROR)

            cli_runner.invoke(
                check_cni_command,
                ["--context", "prod-cluster"],
            )

            # Should attempt to load with context
            mock_load.assert_called_once()
            args = mock_load.call_args[0]
            assert args[1] == "prod-cluster"

    @pytest.mark.requirement("FR-084")
    def test_accepts_verbose_flag(self, cli_runner: CliRunner) -> None:
        """Test that --verbose flag is accepted."""
        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.side_effect = SystemExit(ExitCode.NETWORK_ERROR)

            result = cli_runner.invoke(
                check_cni_command,
                ["--verbose"],
            )

            # Verbose flag should be processed (check output contains verbose messages)
            assert result.exit_code == ExitCode.NETWORK_ERROR

    @pytest.mark.requirement("FR-084")
    def test_accepts_output_format_option(self, cli_runner: CliRunner) -> None:
        """Test that --output-format option is accepted."""
        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.side_effect = SystemExit(ExitCode.NETWORK_ERROR)

            result = cli_runner.invoke(
                check_cni_command,
                ["--output-format", "json"],
            )

            # Should accept json format
            assert result.exit_code == ExitCode.NETWORK_ERROR

    @pytest.mark.requirement("FR-084")
    def test_shows_help(self, cli_runner: CliRunner) -> None:
        """Test that --help shows command help."""
        result = cli_runner.invoke(check_cni_command, ["--help"])

        assert result.exit_code == ExitCode.SUCCESS
        assert "check-cni" in result.output
        assert "Verify CNI plugin supports NetworkPolicies" in result.output
        assert "--kubeconfig" in result.output
        assert "--context" in result.output
        assert "--verbose" in result.output
        assert "--output-format" in result.output


# =============================================================================
# TestCniSupportMatrix - Test CNI support matrix
# =============================================================================


class TestCniSupportMatrix:
    """Test CNI_SUPPORT matrix contains expected plugins."""

    @pytest.mark.requirement("FR-084")
    def test_calico_supported(self) -> None:
        """Test that Calico is marked as supported."""
        assert "calico" in CNI_SUPPORT
        assert CNI_SUPPORT["calico"]["supported"] is True
        assert "Full NetworkPolicy support" in CNI_SUPPORT["calico"]["notes"]

    @pytest.mark.requirement("FR-084")
    def test_cilium_supported(self) -> None:
        """Test that Cilium is marked as supported."""
        assert "cilium" in CNI_SUPPORT
        assert CNI_SUPPORT["cilium"]["supported"] is True
        assert "Full support with extensions" in CNI_SUPPORT["cilium"]["notes"]

    @pytest.mark.requirement("FR-084")
    def test_weave_supported(self) -> None:
        """Test that Weave is marked as supported."""
        assert "weave" in CNI_SUPPORT
        assert CNI_SUPPORT["weave"]["supported"] is True
        assert "Full NetworkPolicy support" in CNI_SUPPORT["weave"]["notes"]

    @pytest.mark.requirement("FR-084")
    def test_aws_node_supported(self) -> None:
        """Test that AWS VPC CNI is marked as supported."""
        assert "aws-node" in CNI_SUPPORT
        assert CNI_SUPPORT["aws-node"]["supported"] is True
        assert "Support on EKS 1.25+" in CNI_SUPPORT["aws-node"]["notes"]

    @pytest.mark.requirement("FR-084")
    def test_azure_cni_supported(self) -> None:
        """Test that Azure CNI is marked as supported."""
        assert "azure-cni" in CNI_SUPPORT
        assert CNI_SUPPORT["azure-cni"]["supported"] is True
        assert "Support with Network Policy Manager" in CNI_SUPPORT["azure-cni"]["notes"]

    @pytest.mark.requirement("FR-084")
    def test_gce_supported(self) -> None:
        """Test that GCE is marked as supported."""
        assert "gce" in CNI_SUPPORT
        assert CNI_SUPPORT["gce"]["supported"] is True
        assert "Support on GKE" in CNI_SUPPORT["gce"]["notes"]

    @pytest.mark.requirement("FR-084")
    def test_flannel_not_supported(self) -> None:
        """Test that Flannel is marked as NOT supported."""
        assert "flannel" in CNI_SUPPORT
        assert CNI_SUPPORT["flannel"]["supported"] is False
        assert "NOT supported" in CNI_SUPPORT["flannel"]["notes"]

    @pytest.mark.requirement("FR-084")
    def test_kindnet_not_supported(self) -> None:
        """Test that KindNet is marked as NOT supported."""
        assert "kindnet" in CNI_SUPPORT
        assert CNI_SUPPORT["kindnet"]["supported"] is False
        assert "NOT supported" in CNI_SUPPORT["kindnet"]["notes"]


# =============================================================================
# TestLoadKubernetesClient - Test Kubernetes client loading
# =============================================================================


class TestLoadKubernetesClient:
    """Test _load_kubernetes_client function."""

    @pytest.mark.requirement("FR-084")
    def test_loads_incluster_config(self, mock_k8s_config: MagicMock) -> None:
        """Test loading in-cluster config when no kubeconfig provided."""
        with patch("kubernetes.config", mock_k8s_config):
            with patch("kubernetes.client") as mock_client:
                mock_core_api = MagicMock()
                mock_apps_api = MagicMock()
                mock_client.CoreV1Api.return_value = mock_core_api
                mock_client.AppsV1Api.return_value = mock_apps_api

                core_api, apps_api = _load_kubernetes_client(None, None)

                # Should try in-cluster config first
                mock_k8s_config.load_incluster_config.assert_called_once()
                assert core_api == mock_core_api
                assert apps_api == mock_apps_api

    @pytest.mark.requirement("FR-084")
    def test_falls_back_to_kubeconfig(self, mock_k8s_config: MagicMock) -> None:
        """Test falling back to kubeconfig when in-cluster fails."""
        # Simulate in-cluster config failure
        mock_k8s_config.load_incluster_config.side_effect = mock_k8s_config.ConfigException(
            "Not in cluster"
        )

        with patch("kubernetes.config", mock_k8s_config):
            with patch("kubernetes.client") as mock_client:
                mock_core_api = MagicMock()
                mock_apps_api = MagicMock()
                mock_client.CoreV1Api.return_value = mock_core_api
                mock_client.AppsV1Api.return_value = mock_apps_api

                core_api, apps_api = _load_kubernetes_client(None, None)

                # Should fall back to kubeconfig
                mock_k8s_config.load_kube_config.assert_called_once_with(context=None)
                assert core_api == mock_core_api
                assert apps_api == mock_apps_api

    @pytest.mark.requirement("FR-084")
    def test_uses_context_parameter(self, mock_k8s_config: MagicMock, tmp_path: Path) -> None:
        """Test that context parameter is passed to load_kube_config."""
        kubeconfig = tmp_path / "kubeconfig"

        with patch("kubernetes.config", mock_k8s_config):
            with patch("kubernetes.client") as mock_client:
                mock_core_api = MagicMock()
                mock_apps_api = MagicMock()
                mock_client.CoreV1Api.return_value = mock_core_api
                mock_client.AppsV1Api.return_value = mock_apps_api

                core_api, apps_api = _load_kubernetes_client(kubeconfig, "prod-cluster")

                # Should use kubeconfig with context
                mock_k8s_config.load_kube_config.assert_called_once_with(
                    config_file=str(kubeconfig),
                    context="prod-cluster",
                )

    @pytest.mark.requirement("FR-084")
    def test_handles_connection_error(self, mock_k8s_config: MagicMock) -> None:
        """Test that connection errors exit with NETWORK_ERROR code."""
        mock_k8s_config.load_incluster_config.side_effect = Exception("Connection refused")
        mock_k8s_config.load_kube_config.side_effect = Exception("Connection refused")

        with patch("kubernetes.config", mock_k8s_config):
            with patch("kubernetes.client"):
                with pytest.raises(SystemExit) as exc_info:
                    _load_kubernetes_client(None, None)

                assert exc_info.value.code == ExitCode.NETWORK_ERROR


# =============================================================================
# TestDetectCni - Test CNI detection from DaemonSets
# =============================================================================


class TestDetectCni:
    """Test _detect_cni function."""

    @pytest.mark.requirement("FR-084")
    def test_detects_calico_from_daemonset(
        self,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_calico: MagicMock,
    ) -> None:
        """Test detecting Calico CNI from DaemonSet."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_calico
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        result = _detect_cni(mock_core_api, mock_apps_api, verbose=False)

        assert result["detected"] == "calico"
        assert result["supported"] is True
        assert "Full NetworkPolicy support" in result["notes"]
        assert "calico-node" in result["daemonsets"]

    @pytest.mark.requirement("FR-084")
    def test_detects_cilium_from_daemonset(
        self,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_cilium: MagicMock,
    ) -> None:
        """Test detecting Cilium CNI from DaemonSet."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_cilium
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        result = _detect_cni(mock_core_api, mock_apps_api, verbose=False)

        assert result["detected"] == "cilium"
        assert result["supported"] is True
        assert "Full support with extensions" in result["notes"]
        assert "cilium" in result["daemonsets"]

    @pytest.mark.requirement("FR-084")
    def test_detects_flannel_from_daemonset(
        self,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_flannel: MagicMock,
    ) -> None:
        """Test detecting Flannel CNI (unsupported) from DaemonSet."""
        ds_list = MagicMock()
        ds_list.items = [mock_daemonset_flannel]
        mock_apps_api.list_namespaced_daemon_set.return_value = ds_list
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        result = _detect_cni(mock_core_api, mock_apps_api, verbose=False)

        assert result["detected"] == "flannel"
        assert result["supported"] is False
        assert "NOT supported" in result["notes"]

    @pytest.mark.requirement("FR-084")
    def test_detects_aws_node_from_daemonset(
        self,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_aws_node: MagicMock,
    ) -> None:
        """Test detecting AWS VPC CNI from DaemonSet."""
        ds_list = MagicMock()
        ds_list.items = [mock_daemonset_aws_node]
        mock_apps_api.list_namespaced_daemon_set.return_value = ds_list
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        result = _detect_cni(mock_core_api, mock_apps_api, verbose=False)

        assert result["detected"] == "aws-node"
        assert result["supported"] is True
        assert "Support on EKS 1.25+" in result["notes"]

    @pytest.mark.requirement("FR-084")
    def test_no_cni_detected_empty_list(
        self,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_empty: MagicMock,
    ) -> None:
        """Test when no CNI DaemonSets are found."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_empty
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        result = _detect_cni(mock_core_api, mock_apps_api, verbose=False)

        assert result["detected"] is None
        assert result["supported"] is False
        assert result["notes"] == ""
        assert result["daemonsets"] == []

    @pytest.mark.requirement("FR-084")
    def test_handles_api_error(
        self,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
    ) -> None:
        """Test handling API errors during CNI detection."""
        mock_apps_api.list_namespaced_daemon_set.side_effect = Exception("API error")

        result = _detect_cni(mock_core_api, mock_apps_api, verbose=False)

        # Should return empty result on error
        assert result["detected"] is None
        assert result["supported"] is False


# =============================================================================
# TestFormatOutput - Test output formatting
# =============================================================================


class TestFormatOutput:
    """Test output formatting functions."""

    @pytest.mark.requirement("FR-084")
    def test_text_format_supported(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test text format output for supported CNI."""
        result: dict[str, Any] = {
            "detected": "calico",
            "supported": True,
            "notes": "Full NetworkPolicy support",
            "daemonsets": ["calico-node"],
            "configmaps": [],
        }

        _format_text_output(result)

        captured = capsys.readouterr()
        assert "✓ CNI Plugin: CALICO" in captured.out
        assert "Status: SUPPORTED" in captured.out
        assert "Full NetworkPolicy support" in captured.out

    @pytest.mark.requirement("FR-084")
    def test_text_format_unsupported(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test text format output for unsupported CNI."""
        result: dict[str, Any] = {
            "detected": "flannel",
            "supported": False,
            "notes": "NOT supported - needs Calico overlay",
            "daemonsets": ["kube-flannel-ds"],
            "configmaps": [],
        }

        _format_text_output(result)

        captured = capsys.readouterr()
        assert "✗ CNI Plugin: FLANNEL" in captured.err
        assert "Status: NOT SUPPORTED" in captured.err
        assert "NOT supported - needs Calico overlay" in captured.err

    @pytest.mark.requirement("FR-084")
    def test_json_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test JSON format output."""
        result: dict[str, Any] = {
            "detected": "cilium",
            "supported": True,
            "notes": "Full support with extensions",
            "daemonsets": ["cilium"],
            "configmaps": ["cilium-config"],
        }

        _format_json_output(result)

        captured = capsys.readouterr()
        import json

        output = json.loads(captured.out)
        assert output["cni"] == "cilium"
        assert output["supported"] is True
        assert output["notes"] == "Full support with extensions"
        assert output["detected_daemonsets"] == ["cilium"]
        assert output["detected_configmaps"] == ["cilium-config"]

    @pytest.mark.requirement("FR-084")
    def test_verbose_includes_details(
        self,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_calico: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that verbose mode includes detection details."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_calico
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        _detect_cni(mock_core_api, mock_apps_api, verbose=True)

        captured = capsys.readouterr()
        assert "Found DaemonSets:" in captured.err
        assert "Detected CNI: calico" in captured.err


# =============================================================================
# TestExitCodes - Test command exit codes
# =============================================================================


class TestExitCodes:
    """Test command exit codes for different scenarios."""

    @pytest.mark.requirement("FR-084")
    def test_supported_cni_exits_0(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_calico: MagicMock,
    ) -> None:
        """Test that supported CNI exits with code 0."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_calico
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, [])

            assert result.exit_code == ExitCode.SUCCESS

    @pytest.mark.requirement("FR-084")
    def test_unsupported_cni_exits_5(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_flannel: MagicMock,
    ) -> None:
        """Test that unsupported CNI exits with code 5 (VALIDATION_ERROR)."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_flannel
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, [])

            assert result.exit_code == ExitCode.VALIDATION_ERROR

    @pytest.mark.requirement("FR-084")
    def test_no_cni_detected_exits_1(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_empty: MagicMock,
    ) -> None:
        """Test that no CNI detected exits with code 1 (GENERAL_ERROR)."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_empty
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, [])

            assert result.exit_code == ExitCode.GENERAL_ERROR

    @pytest.mark.requirement("FR-084")
    def test_connection_error_exits_7(self, cli_runner: CliRunner) -> None:
        """Test that connection error exits with code 7 (NETWORK_ERROR)."""
        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.side_effect = SystemExit(ExitCode.NETWORK_ERROR)

            result = cli_runner.invoke(check_cni_command, [])

            assert result.exit_code == ExitCode.NETWORK_ERROR


# =============================================================================
# TestCheckCniCommandExecution - Test full command execution
# =============================================================================


class TestCheckCniCommandExecution:
    """Test full command execution with various CNI plugins."""

    @pytest.mark.requirement("FR-084")
    def test_calico_detection_success(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_calico: MagicMock,
    ) -> None:
        """Test successful Calico detection and output."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_calico
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, [])

            assert result.exit_code == ExitCode.SUCCESS
            assert "✓ CNI Plugin: CALICO" in result.output
            assert "Status: SUPPORTED" in result.output

    @pytest.mark.requirement("FR-084")
    def test_flannel_detection_warns(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_flannel: MagicMock,
    ) -> None:
        """Test Flannel detection shows unsupported warning."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_flannel
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, [])

            assert result.exit_code == ExitCode.VALIDATION_ERROR
            assert "✗ CNI Plugin: FLANNEL" in result.output
            assert "Status: NOT SUPPORTED" in result.output

    @pytest.mark.requirement("FR-084")
    def test_no_cni_detected_error(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_empty: MagicMock,
    ) -> None:
        """Test error when no CNI is detected."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_empty
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, [])

            assert result.exit_code == ExitCode.GENERAL_ERROR
            assert "✗ Could not detect CNI plugin" in result.output

    @pytest.mark.requirement("FR-084")
    def test_json_output_format(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_cilium: MagicMock,
    ) -> None:
        """Test JSON output format."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_cilium
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, ["--output-format", "json"])

            assert result.exit_code == ExitCode.SUCCESS
            import json

            output = json.loads(result.output)
            assert output["cni"] == "cilium"
            assert output["supported"] is True

    @pytest.mark.requirement("FR-084")
    def test_verbose_output(
        self,
        cli_runner: CliRunner,
        mock_core_api: MagicMock,
        mock_apps_api: MagicMock,
        mock_daemonset_list_calico: MagicMock,
    ) -> None:
        """Test verbose output includes detection details."""
        mock_apps_api.list_namespaced_daemon_set.return_value = mock_daemonset_list_calico
        mock_core_api.list_namespaced_config_map.return_value = MagicMock(items=[])

        with patch("floe_core.cli.network.check_cni._load_kubernetes_client") as mock_load:
            mock_load.return_value = (mock_core_api, mock_apps_api)

            result = cli_runner.invoke(check_cni_command, ["--verbose"])

            assert result.exit_code == ExitCode.SUCCESS
            assert "Connecting to Kubernetes cluster..." in result.output
            assert "Connected successfully" in result.output
            assert "Detecting CNI plugin..." in result.output


__all__: list[str] = [
    "TestCheckCniCommandOptions",
    "TestCniSupportMatrix",
    "TestLoadKubernetesClient",
    "TestDetectCni",
    "TestFormatOutput",
    "TestExitCodes",
    "TestCheckCniCommandExecution",
]
