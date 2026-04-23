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


def test_polaris_readiness_uses_management_service() -> None:
    """Polaris readiness belongs to the management endpoint, not the catalog port."""
    from floe_core.contracts.topology import ComponentId, service_contract

    assert service_contract(ComponentId.POLARIS).readiness_path is None
    assert (
        service_contract(ComponentId.POLARIS_MANAGEMENT).readiness_path
        == "/q/health/ready"
    )


def test_local_ports_encode_forwarded_service_ports() -> None:
    """Local ports capture explicit port-forward contracts for host-style contexts."""
    from floe_core.contracts.topology import ComponentId, service_contract

    assert service_contract(ComponentId.DAGSTER_WEBSERVER).host_port == 3100
    assert service_contract(ComponentId.MARQUEZ).host_port == 5100
    assert service_contract(ComponentId.MINIO).host_port == 9000
    assert service_contract(ComponentId.POLARIS).host_port == 8181
    assert service_contract(ComponentId.JAEGER_QUERY).host_port == 16686
    assert service_contract(ComponentId.OTEL_COLLECTOR_GRPC).host_port == 4317
    assert service_contract(ComponentId.POSTGRESQL).host_port == 5432
