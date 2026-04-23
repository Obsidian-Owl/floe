"""Tests for platform topology contracts."""

from __future__ import annotations


def test_platform_services_include_current_e2e_dependencies() -> None:
    """The topology contract owns service identities used by E2E tests."""
    from floe_core.contracts.topology import ComponentId, service_contract, test_runner_services

    assert service_contract(ComponentId.POLARIS).default_port == 8181
    assert service_contract(ComponentId.POLARIS_MANAGEMENT).default_port == 8182
    assert service_contract(ComponentId.MINIO).default_port == 9000
    assert service_contract(ComponentId.DAGSTER_WEBSERVER).default_port == 3000
    assert service_contract(ComponentId.POSTGRESQL).default_port == 5432
    assert ComponentId.OCI_REGISTRY not in {
        service.component_id for service in test_runner_services()
    }


def test_service_names_are_rendered_from_release_name() -> None:
    """Chart and shell consumers must not hand-author service-name formulas."""
    from floe_core.contracts.topology import ComponentId, render_service_name

    assert render_service_name(ComponentId.POLARIS, release_name="floe-platform") == (
        "floe-platform-polaris"
    )
    assert render_service_name(ComponentId.DAGSTER_WEBSERVER, release_name="demo") == (
        "demo-dagster-webserver"
    )
