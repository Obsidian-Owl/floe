"""Tests for generated contract emitters."""

from __future__ import annotations


def test_shell_exports_include_canonical_defaults() -> None:
    """Shell emit output provides defaults owned by topology contracts."""
    from floe_core.contracts.emit import render_shell_defaults

    output = render_shell_defaults()

    assert "FLOE_DEFAULT_RELEASE_NAME=floe-platform" in output
    assert "FLOE_DEFAULT_NAMESPACE=floe-test" in output


def test_service_name_command_uses_topology_contract() -> None:
    """Service-name rendering comes from the topology contract."""
    from floe_core.contracts.emit import render_service_name_output

    assert render_service_name_output("polaris", "demo") == "demo-polaris\n"


def test_helm_env_fragment_contains_execution_context() -> None:
    """The Helm env fragment includes explicit execution context binding."""
    from floe_core.contracts.emit import render_helm_test_env_template

    output = render_helm_test_env_template()

    assert "name: FLOE_EXECUTION_CONTEXT" in output
    assert 'value: "in-cluster"' in output
    assert "POLARIS_HOST" in output
