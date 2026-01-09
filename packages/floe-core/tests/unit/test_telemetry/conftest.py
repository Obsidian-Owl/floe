"""Telemetry unit test fixtures.

Provides fixtures specific to telemetry module unit tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.telemetry import ResourceAttributes, SamplingConfig


@pytest.fixture
def valid_resource_attributes() -> dict[str, str]:
    """Return valid ResourceAttributes constructor kwargs.

    Returns:
        Dictionary with all required fields for ResourceAttributes.
    """
    return {
        "service_name": "test-service",
        "service_version": "1.0.0",
        "deployment_environment": "dev",
        "floe_namespace": "analytics",
        "floe_product_name": "customer-360",
        "floe_product_version": "2.1.0",
        "floe_mode": "dev",
    }


@pytest.fixture
def sample_resource_attributes(
    valid_resource_attributes: dict[str, str],
) -> ResourceAttributes:
    """Create a sample ResourceAttributes instance.

    Args:
        valid_resource_attributes: Valid constructor kwargs.

    Returns:
        ResourceAttributes instance for testing.
    """
    from floe_core.telemetry import ResourceAttributes

    return ResourceAttributes(**valid_resource_attributes)  # type: ignore[arg-type]


@pytest.fixture
def default_sampling_config() -> SamplingConfig:
    """Create SamplingConfig with default values.

    Returns:
        SamplingConfig with dev=1.0, staging=0.5, prod=0.1.
    """
    from floe_core.telemetry import SamplingConfig

    return SamplingConfig()
