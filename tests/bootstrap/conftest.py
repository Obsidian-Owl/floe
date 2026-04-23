"""Bootstrap validation fixtures.

Bootstrap tests validate environment bring-up before product E2E tests run.
They may use Kubernetes and Helm readiness checks, but they should not assert
data-platform product behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from testing.fixtures.polling import wait_for_condition


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark all bootstrap tests with the bootstrap boundary marker."""
    bootstrap_dir = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(bootstrap_dir):
            item.add_marker(pytest.mark.bootstrap)


@pytest.fixture(scope="session")
def wait_for_service() -> Callable[..., None]:
    """Create helper fixture for waiting on HTTP service readiness."""

    def _wait_for_service(
        url: str,
        timeout: float = 60.0,
        description: str | None = None,
        *,
        strict_status: bool = False,
    ) -> None:
        """Wait for an HTTP service to become available."""
        effective_description = description or f"service at {url}"

        def check_http() -> bool:
            try:
                response = httpx.get(url, timeout=5.0)
                if strict_status:
                    return response.status_code == 200
                return response.status_code < 500
            except (httpx.HTTPError, OSError):
                return False

        wait_for_condition(
            check_http,
            timeout=timeout,
            description=effective_description,
        )

    return _wait_for_service
