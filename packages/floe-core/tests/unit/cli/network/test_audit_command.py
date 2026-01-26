"""Unit tests for the network audit command.

Task ID: T075
Phase: 7C - Network and Pod Security
Requirements: FR-082 (Audit cluster NetworkPolicy state),
              FR-092 (Warn if namespace lacks default-deny policy)

Tests cover:
- Command accepts --namespace option (FR-082)
- Command accepts --all-namespaces flag (FR-082)
- Command accepts --output-format option (FR-082)
- Command accepts --kubeconfig option (FR-082)
- Command accepts --context option (FR-082)
- Input validation (namespace vs all-namespaces)
- Namespace resolution logic
- Kubernetes client setup
- Default-deny policy detection (FR-092)
- Permissive rule detection
- Output formatting (text and JSON)
- Exit code handling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestAuditCommandOptions:
    """Tests for audit command CLI options."""

    @pytest.mark.requirement("FR-082")
    def test_accepts_namespace_option(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command accepts --namespace option.

        Validates that the --namespace option is recognized.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "network",
                "audit",
                "--namespace",
                "floe-jobs",
            ],
        )

        assert "Error: No such option: --namespace" not in (result.output or "")

    @pytest.mark.requirement("FR-082")
    def test_accepts_all_namespaces_flag(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command accepts --all-namespaces flag.

        Validates that the --all-namespaces flag is recognized.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "network",
                "audit",
                "--all-namespaces",
            ],
        )

        assert "Error: No such option: --all-namespaces" not in (result.output or "")

    @pytest.mark.requirement("FR-082")
    def test_accepts_output_format_option(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command accepts --output-format option.

        Validates that the --output-format option is recognized.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "network",
                "audit",
                "--namespace",
                "default",
                "--output-format",
                "json",
            ],
        )

        assert "Error: No such option: --output-format" not in (result.output or "")

    @pytest.mark.requirement("FR-082")
    def test_accepts_kubeconfig_option(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that audit command accepts --kubeconfig option.

        Validates that the --kubeconfig option is recognized.
        """
        from floe_core.cli.main import cli

        kubeconfig = temp_dir / "kubeconfig"
        kubeconfig.write_text("# placeholder kubeconfig")

        result = cli_runner.invoke(
            cli,
            [
                "network",
                "audit",
                "--namespace",
                "default",
                "--kubeconfig",
                str(kubeconfig),
            ],
        )

        assert "Error: No such option: --kubeconfig" not in (result.output or "")

    @pytest.mark.requirement("FR-082")
    def test_accepts_context_option(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command accepts --context option.

        Validates that the --context option is recognized.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "network",
                "audit",
                "--namespace",
                "default",
                "--context",
                "minikube",
            ],
        )

        assert "Error: No such option: --context" not in (result.output or "")

    @pytest.mark.requirement("FR-082")
    def test_shows_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["network", "audit", "--help"],
        )

        assert result.exit_code == 0
        assert "audit" in result.output.lower()
        assert "--namespace" in result.output
        assert "--all-namespaces" in result.output


class TestValidateAuditInputs:
    """Tests for _validate_audit_inputs function."""

    @pytest.mark.requirement("FR-082")
    def test_neither_namespace_nor_all_namespaces_fails(
        self,
    ) -> None:
        """Test that validation fails when neither namespace nor all-namespaces provided.

        Validates proper error handling for missing required input.
        """
        from floe_core.cli.network.audit import _validate_audit_inputs

        with pytest.raises(SystemExit) as exc_info:
            _validate_audit_inputs(namespace=(), all_namespaces=False)

        assert exc_info.value.code == 2  # ExitCode.USAGE_ERROR

    @pytest.mark.requirement("FR-082")
    def test_namespace_provided_passes(
        self,
    ) -> None:
        """Test that validation passes when namespace is provided.

        Validates that providing a valid namespace succeeds.
        """
        from floe_core.cli.network.audit import _validate_audit_inputs

        # Should not raise
        _validate_audit_inputs(namespace=("floe-jobs",), all_namespaces=False)

    @pytest.mark.requirement("FR-082")
    def test_all_namespaces_provided_passes(
        self,
    ) -> None:
        """Test that validation passes when all-namespaces flag is set.

        Validates that setting all-namespaces flag succeeds.
        """
        from floe_core.cli.network.audit import _validate_audit_inputs

        # Should not raise
        _validate_audit_inputs(namespace=(), all_namespaces=True)

    @pytest.mark.requirement("FR-082")
    def test_both_provided_passes(
        self,
    ) -> None:
        """Test that validation passes when both namespace and all-namespaces provided.

        Validates that providing both is allowed (all-namespaces takes precedence).
        """
        from floe_core.cli.network.audit import _validate_audit_inputs

        # Should not raise (all-namespaces wins)
        _validate_audit_inputs(namespace=("floe-jobs",), all_namespaces=True)

    @pytest.mark.requirement("FR-082")
    def test_invalid_namespace_fails(
        self,
    ) -> None:
        """Test that validation fails with invalid namespace name.

        Validates that invalid namespace names are rejected.
        """
        from floe_core.cli.network.audit import _validate_audit_inputs

        with pytest.raises(SystemExit) as exc_info:
            _validate_audit_inputs(namespace=("Invalid_Namespace",), all_namespaces=False)

        assert exc_info.value.code == 2  # ExitCode.USAGE_ERROR


class TestResolveNamespaces:
    """Tests for _resolve_namespaces function."""

    @pytest.mark.requirement("FR-082")
    def test_returns_specified_namespaces(
        self,
    ) -> None:
        """Test that specified namespaces are returned as list.

        Validates that explicit namespace list is preserved.
        """
        from floe_core.cli.network.audit import _resolve_namespaces

        result = _resolve_namespaces(
            namespace=("floe-jobs", "floe-services"),
            all_namespaces=False,
        )

        assert result == ["floe-jobs", "floe-services"]

    @pytest.mark.requirement("FR-082")
    def test_returns_wildcard_when_all_namespaces_set(
        self,
    ) -> None:
        """Test that wildcard marker is returned when all-namespaces flag set.

        Validates that all-namespaces flag returns special marker.
        """
        from floe_core.cli.network.audit import _resolve_namespaces

        result = _resolve_namespaces(
            namespace=(),
            all_namespaces=True,
        )

        assert result == ["*"]

    @pytest.mark.requirement("FR-082")
    def test_all_namespaces_overrides_explicit_namespaces(
        self,
    ) -> None:
        """Test that all-namespaces flag overrides explicit namespace list.

        Validates precedence of all-namespaces over explicit namespaces.
        """
        from floe_core.cli.network.audit import _resolve_namespaces

        result = _resolve_namespaces(
            namespace=("floe-jobs",),
            all_namespaces=True,
        )

        assert result == ["*"]


class TestSetupKubernetesClient:
    """Tests for _setup_kubernetes_client function."""

    @pytest.mark.requirement("FR-082")
    def test_loads_incluster_config(
        self,
    ) -> None:
        """Test that in-cluster config is loaded when available.

        Validates that in-cluster config is attempted first.
        """
        from floe_core.cli.network.audit import _load_kubeconfig

        mock_k8s_config = MagicMock()
        mock_k8s_config.load_incluster_config.return_value = None

        _load_kubeconfig(mock_k8s_config, kubeconfig=None, context=None)

        mock_k8s_config.load_incluster_config.assert_called_once()

    @pytest.mark.requirement("FR-082")
    def test_falls_back_to_kubeconfig(
        self,
    ) -> None:
        """Test that kubeconfig is loaded when in-cluster config fails.

        Validates fallback to kubeconfig when not running in cluster.
        """
        from floe_core.cli.network.audit import _load_kubeconfig

        mock_k8s_config = MagicMock()
        # Simulate in-cluster config failure
        mock_k8s_config.ConfigException = Exception
        mock_k8s_config.load_incluster_config.side_effect = Exception("Not in cluster")

        _load_kubeconfig(mock_k8s_config, kubeconfig=None, context=None)

        mock_k8s_config.load_kube_config.assert_called_once_with(context=None)

    @pytest.mark.requirement("FR-082")
    def test_uses_explicit_kubeconfig_path(
        self,
        temp_dir: Path,
    ) -> None:
        """Test that explicit kubeconfig path is used when provided.

        Validates that kubeconfig parameter is respected.
        """
        from floe_core.cli.network.audit import _load_kubeconfig

        kubeconfig = temp_dir / "kubeconfig"
        kubeconfig.write_text("# test kubeconfig")

        mock_k8s_config = MagicMock()

        _load_kubeconfig(mock_k8s_config, kubeconfig=kubeconfig, context=None)

        mock_k8s_config.load_kube_config.assert_called_once_with(
            config_file=str(kubeconfig),
            context=None,
        )

    @pytest.mark.requirement("FR-082")
    def test_uses_context_parameter(
        self,
    ) -> None:
        """Test that context parameter is passed to kubeconfig loader.

        Validates that context parameter is respected.
        """
        from floe_core.cli.network.audit import _load_kubeconfig

        mock_k8s_config = MagicMock()
        mock_k8s_config.ConfigException = Exception
        mock_k8s_config.load_incluster_config.side_effect = Exception("Not in cluster")

        _load_kubeconfig(mock_k8s_config, kubeconfig=None, context="minikube")

        mock_k8s_config.load_kube_config.assert_called_once_with(context="minikube")


class TestCheckDefaultDenyPolicy:
    """Tests for _check_default_deny_policy function."""

    @pytest.mark.requirement("FR-092")
    def test_detects_missing_default_deny(
        self,
    ) -> None:
        """Test that missing default-deny policy is detected.

        Validates FR-092: Warn if namespace lacks default-deny policy.
        """
        from floe_core.cli.network.audit import _check_default_deny_policy

        # Mock NetworkPolicyList with no default-deny policy
        mock_policies = MagicMock()
        mock_policy = MagicMock()
        mock_policy.metadata.name = "allow-web"
        mock_policy.spec.ingress_rules = [MagicMock()]  # Has rules (not default-deny)
        mock_policy.spec.egress_rules = [MagicMock()]
        mock_policies.items = [mock_policy]

        result = _check_default_deny_policy(mock_policies)

        assert result is False

    @pytest.mark.requirement("FR-092")
    def test_recognizes_default_deny_by_empty_rules(
        self,
    ) -> None:
        """Test that default-deny policy is recognized by empty rules.

        Validates that policy with no ingress/egress rules is default-deny.
        """
        from floe_core.cli.network.audit import _check_default_deny_policy

        # Mock NetworkPolicyList with default-deny policy (empty rules)
        mock_policies = MagicMock()
        mock_policy = MagicMock()
        mock_policy.metadata.name = "deny-all"
        mock_policy.spec.ingress_rules = None
        mock_policy.spec.egress_rules = None
        mock_policies.items = [mock_policy]

        result = _check_default_deny_policy(mock_policies)

        assert result is True

    @pytest.mark.requirement("FR-092")
    def test_recognizes_default_deny_by_name(
        self,
    ) -> None:
        """Test that default-deny policy is recognized by name pattern.

        Validates that policies with 'default-deny' in name are recognized.
        """
        from floe_core.cli.network.audit import _check_default_deny_policy

        # Mock NetworkPolicyList with default-deny in name
        mock_policies = MagicMock()
        mock_policy = MagicMock()
        mock_policy.metadata.name = "default-deny-all"
        mock_policy.spec.ingress_rules = [MagicMock()]  # Has rules but name indicates default-deny
        mock_policy.spec.egress_rules = [MagicMock()]
        mock_policies.items = [mock_policy]

        result = _check_default_deny_policy(mock_policies)

        assert result is True

    @pytest.mark.requirement("FR-092")
    def test_recognizes_default_deny_with_empty_list_rules(
        self,
    ) -> None:
        """Test that default-deny policy is recognized with empty list rules.

        Validates that policy with empty list (not None) for rules is default-deny.
        """
        from floe_core.cli.network.audit import _check_default_deny_policy

        # Mock NetworkPolicyList with default-deny policy (empty lists)
        mock_policies = MagicMock()
        mock_policy = MagicMock()
        mock_policy.metadata.name = "deny-all"
        mock_policy.spec.ingress_rules = []
        mock_policy.spec.egress_rules = []
        mock_policies.items = [mock_policy]

        result = _check_default_deny_policy(mock_policies)

        assert result is True


class TestAuditPolicy:
    """Tests for _audit_policy function."""

    @pytest.mark.requirement("FR-082")
    def test_checks_ingress_rules(
        self,
    ) -> None:
        """Test that ingress rules are checked for permissiveness.

        Validates that overly permissive ingress rules are detected.
        """
        from floe_core.cli.network.audit import _audit_policy

        # Mock policy with permissive ingress rule
        mock_policy = MagicMock()
        mock_policy.metadata.name = "test-policy"
        mock_policy.spec.ingress_rules = [MagicMock()]
        mock_policy.spec.ingress_rules[0].from_ = None  # No selector (permissive)
        mock_policy.spec.ingress_rules[0].ports = None  # No ports (permissive)
        mock_policy.spec.egress_rules = None

        findings = _audit_policy(mock_policy, "test-namespace")

        assert len(findings) == 1
        assert findings[0]["type"] == "overly_permissive_ingress"
        assert findings[0]["severity"] == "warning"

    @pytest.mark.requirement("FR-082")
    def test_checks_egress_rules(
        self,
    ) -> None:
        """Test that egress rules are checked for permissiveness.

        Validates that overly permissive egress rules are detected.
        """
        from floe_core.cli.network.audit import _audit_policy

        # Mock policy with permissive egress rule
        mock_policy = MagicMock()
        mock_policy.metadata.name = "test-policy"
        mock_policy.spec.ingress_rules = None
        mock_policy.spec.egress_rules = [MagicMock()]
        mock_policy.spec.egress_rules[0].to = None  # No selector (permissive)
        mock_policy.spec.egress_rules[0].ports = None  # No ports (permissive)

        findings = _audit_policy(mock_policy, "test-namespace")

        assert len(findings) == 1
        assert findings[0]["type"] == "overly_permissive_egress"
        assert findings[0]["severity"] == "warning"

    @pytest.mark.requirement("FR-082")
    def test_reports_multiple_permissive_rules(
        self,
    ) -> None:
        """Test that multiple permissive rules are all reported.

        Validates that all permissive rules are detected, not just the first.
        """
        from floe_core.cli.network.audit import _audit_policy

        # Mock policy with multiple permissive rules
        mock_policy = MagicMock()
        mock_policy.metadata.name = "test-policy"
        mock_policy.spec.ingress_rules = [MagicMock(), MagicMock()]
        mock_policy.spec.ingress_rules[0].from_ = None
        mock_policy.spec.ingress_rules[0].ports = None
        mock_policy.spec.ingress_rules[1].from_ = None
        mock_policy.spec.ingress_rules[1].ports = None
        mock_policy.spec.egress_rules = None

        findings = _audit_policy(mock_policy, "test-namespace")

        assert len(findings) == 2
        assert all(f["type"] == "overly_permissive_ingress" for f in findings)


class TestIsPermissiveRule:
    """Tests for _is_permissive_rule function."""

    @pytest.mark.requirement("FR-082")
    def test_rule_with_no_from_selector_is_permissive(
        self,
    ) -> None:
        """Test that ingress rule with no from selector is permissive.

        Validates that missing from selector indicates permissive rule.
        """
        from floe_core.cli.network.audit import _is_permissive_rule

        mock_rule = MagicMock()
        mock_rule.from_ = None
        mock_rule.ports = [MagicMock()]

        result = _is_permissive_rule(mock_rule)

        assert result is True

    @pytest.mark.requirement("FR-082")
    def test_rule_with_empty_from_selector_is_permissive(
        self,
    ) -> None:
        """Test that ingress rule with empty from selector is permissive.

        Validates that empty from selector list indicates permissive rule.
        """
        from floe_core.cli.network.audit import _is_permissive_rule

        mock_rule = MagicMock()
        mock_rule.from_ = []
        mock_rule.ports = [MagicMock()]

        result = _is_permissive_rule(mock_rule)

        assert result is True

    @pytest.mark.requirement("FR-082")
    def test_rule_with_no_to_selector_is_permissive(
        self,
    ) -> None:
        """Test that egress rule with no to selector is permissive.

        Validates that missing to selector indicates permissive rule.
        """
        from floe_core.cli.network.audit import _is_permissive_rule

        mock_rule = MagicMock()
        mock_rule.to = None
        mock_rule.ports = [MagicMock()]
        # Remove from_ attribute to simulate egress rule
        delattr(mock_rule, "from_")

        result = _is_permissive_rule(mock_rule)

        assert result is True

    @pytest.mark.requirement("FR-082")
    def test_rule_with_no_ports_is_permissive(
        self,
    ) -> None:
        """Test that rule with no ports specified is permissive.

        Validates that missing ports indicates permissive rule.
        """
        from floe_core.cli.network.audit import _is_permissive_rule

        mock_rule = MagicMock()
        mock_rule.from_ = [MagicMock()]
        mock_rule.ports = None

        result = _is_permissive_rule(mock_rule)

        assert result is True

    @pytest.mark.requirement("FR-082")
    def test_rule_with_empty_ports_is_permissive(
        self,
    ) -> None:
        """Test that rule with empty ports list is permissive.

        Validates that empty ports list indicates permissive rule.
        """
        from floe_core.cli.network.audit import _is_permissive_rule

        mock_rule = MagicMock()
        mock_rule.from_ = [MagicMock()]
        mock_rule.ports = []

        result = _is_permissive_rule(mock_rule)

        assert result is True

    @pytest.mark.requirement("FR-082")
    def test_rule_with_selectors_and_ports_not_permissive(
        self,
    ) -> None:
        """Test that rule with selectors and ports is not permissive.

        Validates that properly restricted rule is not flagged as permissive.
        """
        from floe_core.cli.network.audit import _is_permissive_rule

        mock_rule = MagicMock()
        # For ingress rule with both from selector and ports
        mock_rule.from_ = [MagicMock()]
        mock_rule.ports = [MagicMock()]
        # Remove 'to' attribute to simulate ingress rule only
        if hasattr(mock_rule, "to"):
            delattr(mock_rule, "to")

        result = _is_permissive_rule(mock_rule)

        assert result is False


class TestOutputReport:
    """Tests for _output_report function."""

    @pytest.mark.requirement("FR-082")
    def test_json_format(
        self,
        capsys: Any,
    ) -> None:
        """Test that JSON format output is valid JSON.

        Validates that JSON output can be parsed.
        """
        import json

        from floe_core.cli.network.audit import _output_report

        report = {
            "namespaces": ["test"],
            "policies": [],
            "findings": [],
            "summary": {
                "total_namespaces": 1,
                "total_policies": 0,
                "total_findings": 0,
                "critical_findings": 0,
                "warning_findings": 0,
            },
        }

        _output_report(report, "json")

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == report

    @pytest.mark.requirement("FR-082")
    def test_text_format_includes_summary(
        self,
        capsys: Any,
    ) -> None:
        """Test that text format includes summary statistics.

        Validates that text output contains expected summary fields.
        """
        from floe_core.cli.network.audit import _output_report

        report = {
            "namespaces": ["test"],
            "policies": [],
            "findings": [],
            "summary": {
                "total_namespaces": 1,
                "total_policies": 2,
                "total_findings": 0,
                "critical_findings": 0,
                "warning_findings": 0,
            },
        }

        _output_report(report, "text")

        captured = capsys.readouterr()
        assert "Namespaces audited: 1" in captured.out
        assert "Total policies: 2" in captured.out

    @pytest.mark.requirement("FR-082")
    def test_text_format_includes_findings(
        self,
        capsys: Any,
    ) -> None:
        """Test that text format includes findings details.

        Validates that findings are displayed in text output.
        """
        from floe_core.cli.network.audit import _output_report

        report = {
            "namespaces": ["test"],
            "policies": [],
            "findings": [
                {
                    "severity": "warning",
                    "type": "missing_default_deny",
                    "namespace": "test",
                    "message": "Namespace lacks default-deny policy",
                }
            ],
            "summary": {
                "total_namespaces": 1,
                "total_policies": 0,
                "total_findings": 1,
                "critical_findings": 0,
                "warning_findings": 1,
            },
        }

        _output_report(report, "text")

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "test" in captured.out
        assert "default-deny" in captured.out

    @pytest.mark.requirement("FR-082")
    def test_text_format_no_findings_success(
        self,
        capsys: Any,
    ) -> None:
        """Test that text format shows success when no findings.

        Validates that clean audit shows success message.
        """
        from floe_core.cli.network.audit import _output_report

        report = {
            "namespaces": ["test"],
            "policies": [],
            "findings": [],
            "summary": {
                "total_namespaces": 1,
                "total_policies": 0,
                "total_findings": 0,
                "critical_findings": 0,
                "warning_findings": 0,
            },
        }

        _output_report(report, "text")

        captured = capsys.readouterr()
        assert "No network security issues found" in captured.out


class TestAuditCommandExecution:
    """Tests for full audit command execution."""

    @pytest.mark.requirement("FR-082")
    def test_no_findings_success(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit succeeds when no findings are detected.

        Validates successful audit with clean network policies.
        """
        from floe_core.cli.main import cli

        mock_networking_api = MagicMock()

        # Mock clean namespace with default-deny policy
        mock_policies = MagicMock()
        mock_policy = MagicMock()
        mock_policy.metadata.name = "default-deny-all"
        mock_policy.spec.ingress_rules = None
        mock_policy.spec.egress_rules = None
        mock_policy.spec.pod_selector = MagicMock()
        mock_policy.spec.pod_selector.match_labels = {}
        mock_policy.spec.policy_types = ["Ingress", "Egress"]
        mock_policies.items = [mock_policy]

        mock_networking_api.list_namespaced_network_policy.return_value = mock_policies

        # Mock the kubernetes imports inside _setup_kubernetes_client
        mock_k8s_module = MagicMock()
        mock_k8s_module.client.NetworkingV1Api.return_value = mock_networking_api
        mock_k8s_module.config.ConfigException = Exception
        mock_k8s_module.config.load_incluster_config.side_effect = Exception("Not in cluster")

        with patch.dict("sys.modules", {"kubernetes": mock_k8s_module}):
            result = cli_runner.invoke(
                cli,
                [
                    "network",
                    "audit",
                    "--namespace",
                    "test",
                ],
            )

            assert "No network security issues found" in result.output

    @pytest.mark.requirement("FR-092")
    def test_warnings_reported(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that warnings are reported in output.

        Validates that warning-level findings are displayed.
        """
        from floe_core.cli.main import cli

        mock_networking_api = MagicMock()

        # Mock namespace without default-deny policy
        mock_policies = MagicMock()
        mock_policy = MagicMock()
        mock_policy.metadata.name = "allow-web"
        mock_policy.spec.ingress_rules = [MagicMock()]
        mock_policy.spec.egress_rules = None
        mock_policy.spec.pod_selector = MagicMock()
        mock_policy.spec.pod_selector.match_labels = {"app": "web"}
        mock_policy.spec.policy_types = ["Ingress"]
        mock_policies.items = [mock_policy]

        mock_networking_api.list_namespaced_network_policy.return_value = mock_policies

        # Mock the kubernetes imports inside _setup_kubernetes_client
        mock_k8s_module = MagicMock()
        mock_k8s_module.client.NetworkingV1Api.return_value = mock_networking_api
        mock_k8s_module.config.ConfigException = Exception
        mock_k8s_module.config.load_incluster_config.side_effect = Exception("Not in cluster")

        with patch.dict("sys.modules", {"kubernetes": mock_k8s_module}):
            result = cli_runner.invoke(
                cli,
                [
                    "network",
                    "audit",
                    "--namespace",
                    "test",
                ],
            )

            assert "WARNING" in result.output
            assert "default-deny" in result.output.lower()

    @pytest.mark.requirement("FR-082")
    def test_critical_findings_exit_error(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that critical findings cause error exit code.

        Validates that critical severity findings result in non-zero exit.
        """
        from floe_core.cli.main import cli

        mock_networking_api = MagicMock()

        # Mock namespace with critical finding
        mock_policies = MagicMock()
        mock_policies.items = []

        # Simulate critical finding by patching _audit_namespace
        def mock_audit_namespace(ns: str, policies: Any) -> list[dict[str, Any]]:
            return [
                {
                    "severity": "critical",
                    "type": "test_critical",
                    "namespace": ns,
                    "message": "Critical security issue",
                }
            ]

        mock_networking_api.list_namespaced_network_policy.return_value = mock_policies

        # Mock the kubernetes imports inside _setup_kubernetes_client
        mock_k8s_module = MagicMock()
        mock_k8s_module.client.NetworkingV1Api.return_value = mock_networking_api
        mock_k8s_module.config.ConfigException = Exception
        mock_k8s_module.config.load_incluster_config.side_effect = Exception("Not in cluster")

        with (
            patch.dict("sys.modules", {"kubernetes": mock_k8s_module}),
            patch("floe_core.cli.network.audit._audit_namespace", mock_audit_namespace),
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "network",
                    "audit",
                    "--namespace",
                    "test",
                ],
            )

            assert result.exit_code != 0
            assert "CRITICAL" in result.output


class TestPerformAudit:
    """Tests for _perform_audit function."""

    @pytest.mark.requirement("FR-082")
    def test_resolves_wildcard_to_all_namespaces(
        self,
    ) -> None:
        """Test that wildcard namespace marker triggers namespace listing.

        Validates that ["*"] causes all namespaces to be queried.
        """
        mock_networking_api = MagicMock()
        mock_core_api = MagicMock()

        # Mock namespace list
        mock_ns_list = MagicMock()
        mock_ns1 = MagicMock()
        mock_ns1.metadata.name = "ns1"
        mock_ns2 = MagicMock()
        mock_ns2.metadata.name = "ns2"
        mock_ns_list.items = [mock_ns1, mock_ns2]

        # Mock empty policy lists
        mock_policies = MagicMock()
        mock_policies.items = []

        mock_core_api.list_namespace.return_value = mock_ns_list
        mock_networking_api.list_namespaced_network_policy.return_value = mock_policies

        # Mock the kubernetes module that's imported inside _perform_audit
        mock_k8s_module = MagicMock()
        mock_k8s_module.client.CoreV1Api.return_value = mock_core_api
        mock_k8s_module.client.ApiException = Exception

        # Need to import after patching to get the patched version
        with patch.dict(
            "sys.modules",
            {"kubernetes": mock_k8s_module, "kubernetes.client": mock_k8s_module.client},
        ):
            from floe_core.cli.network.audit import _perform_audit

            report = _perform_audit(mock_networking_api, ["*"])

            assert "ns1" in report["namespaces"]
            assert "ns2" in report["namespaces"]
            assert mock_networking_api.list_namespaced_network_policy.call_count == 2

    @pytest.mark.requirement("FR-082")
    def test_handles_namespace_not_found(
        self,
    ) -> None:
        """Test that 404 errors for namespaces are handled gracefully.

        Validates that missing namespaces generate appropriate findings.
        """
        from kubernetes.client import ApiException

        from floe_core.cli.network.audit import _perform_audit

        mock_networking_api = MagicMock()

        # Simulate 404 error
        api_exception = ApiException(status=404)
        mock_networking_api.list_namespaced_network_policy.side_effect = api_exception

        report = _perform_audit(mock_networking_api, ["nonexistent"])

        assert len(report["findings"]) == 1
        assert report["findings"][0]["type"] == "namespace_not_found"
        assert report["findings"][0]["severity"] == "error"

    @pytest.mark.requirement("FR-082")
    def test_includes_summary_statistics(
        self,
    ) -> None:
        """Test that report includes summary statistics.

        Validates that summary section contains expected metrics.
        """
        from floe_core.cli.network.audit import _perform_audit

        mock_networking_api = MagicMock()

        # Mock empty policy list
        mock_policies = MagicMock()
        mock_policies.items = []
        mock_networking_api.list_namespaced_network_policy.return_value = mock_policies

        report = _perform_audit(mock_networking_api, ["test"])

        assert "summary" in report
        assert "total_namespaces" in report["summary"]
        assert "total_policies" in report["summary"]
        assert "total_findings" in report["summary"]
        assert "critical_findings" in report["summary"]
        assert "warning_findings" in report["summary"]
