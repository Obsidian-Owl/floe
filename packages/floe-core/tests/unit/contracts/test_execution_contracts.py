"""Tests for execution context contracts."""

from __future__ import annotations

import pytest


def test_in_cluster_bindings_use_service_names() -> None:
    """In-cluster bindings use Kubernetes service DNS names."""
    from floe_core.contracts.execution import ExecutionContext, service_binding
    from floe_core.contracts.topology import ComponentId

    binding = service_binding(
        ComponentId.POLARIS,
        ExecutionContext.IN_CLUSTER,
        release_name="floe-platform",
        namespace="floe-test",
    )

    assert binding.host == "floe-platform-polaris"
    assert binding.port == 8181
    assert binding.env == {
        "POLARIS_HOST": "floe-platform-polaris",
        "POLARIS_PORT": "8181",
    }


def test_host_bindings_use_localhost_explicitly() -> None:
    """Host execution is explicit and does not rely on DNS probing."""
    from floe_core.contracts.execution import ExecutionContext, service_binding
    from floe_core.contracts.topology import ComponentId

    binding = service_binding(ComponentId.MINIO, ExecutionContext.HOST)

    assert binding.host == "localhost"
    assert binding.env == {"MINIO_HOST": "localhost", "MINIO_PORT": "9000"}


def test_unknown_execution_context_fails_as_contract_violation() -> None:
    """Invalid execution contexts fail before service helpers run."""
    from floe_core.contracts.errors import ExecutionContextMismatch
    from floe_core.contracts.execution import parse_execution_context

    with pytest.raises(ExecutionContextMismatch, match="Unknown execution context"):
        parse_execution_context("k8s")
