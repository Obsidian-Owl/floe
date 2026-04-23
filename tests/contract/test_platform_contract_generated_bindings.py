"""Cross-consumer contract tests for generated platform bindings."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_shell_and_python_render_same_polaris_service_name() -> None:
    """Shell bindings and Python contracts render the same service name."""
    from floe_core.contracts.topology import ComponentId, render_service_name

    expected = render_service_name(
        ComponentId.POLARIS,
        release_name="floe-platform",
    ).strip()
    result = subprocess.run(
        [
            "bash",
            "-lc",
            "source testing/ci/common.sh && floe_service_name polaris",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_chart_generated_env_helper_is_emitter_output() -> None:
    """The committed Helm helper is generated from the contract emitter."""
    from floe_core.contracts.emit import render_helm_test_env_template

    path = Path("charts/floe-platform/templates/tests/_contract-env.generated.tpl")

    assert path.read_text() == render_helm_test_env_template()


def test_service_fixture_uses_contract_owned_port_table() -> None:
    """Python service fixture defaults are generated from topology contracts."""
    from floe_core.contracts.topology import service_contracts

    from testing.fixtures.services import SERVICE_DEFAULT_PORTS

    assert SERVICE_DEFAULT_PORTS == {
        service.short_name: service.default_port for service in service_contracts()
    }
