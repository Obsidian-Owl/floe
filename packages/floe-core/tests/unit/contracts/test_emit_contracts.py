"""Tests for generated contract emitters."""

from __future__ import annotations

import subprocess

from pytest import MonkeyPatch


def test_shell_exports_include_canonical_defaults() -> None:
    """Shell emit output provides defaults owned by topology contracts."""
    from floe_core.contracts.emit import render_shell_defaults

    output = render_shell_defaults()

    assert "FLOE_DEFAULT_RELEASE_NAME=floe-platform" in output
    assert "FLOE_DEFAULT_NAMESPACE=floe-test" in output


def test_shell_exports_quote_metacharacter_defaults(monkeypatch: MonkeyPatch) -> None:
    """Shell emit output is safe to eval when defaults contain metacharacters."""
    import floe_core.contracts.emit as emit

    monkeypatch.setattr(emit, "DEFAULT_RELEASE_NAME", "demo; echo unsafe")
    monkeypatch.setattr(emit, "DEFAULT_NAMESPACE", "name with spaces")

    output = emit.render_shell_defaults()

    assert "FLOE_DEFAULT_RELEASE_NAME='demo; echo unsafe'" in output
    assert "FLOE_DEFAULT_NAMESPACE='name with spaces'" in output

    result = subprocess.run(
        [
            "bash",
            "-c",
            "eval \"$1\"; printf '%s\\n%s\\n' "
            '"$FLOE_DEFAULT_RELEASE_NAME" "$FLOE_DEFAULT_NAMESPACE"',
            "_",
            output,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == "demo; echo unsafe\nname with spaces\n"


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
