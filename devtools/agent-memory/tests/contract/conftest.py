"""Contract test fixtures for Cognee API field validation.

Provides fixtures that mock HTTP requests and capture payloads sent to the
Cognee Cloud API. This enables contract tests to validate that our client
sends the correct field names (camelCase) without making actual API calls.

Implementation: T002 (FLO-664), T004 (FLO-694)

Key fixtures:
- mock_request: Mocks CogneeClient._make_request and captures payloads
- payload_capture: Stores captured request payloads for assertion

Why camelCase matters:
The Cognee Cloud REST API uses camelCase field names. Using snake_case
(e.g., "data" instead of "textData") causes the API to use default values,
resulting in the "dad jokes" bug where all content was replaced with
"Warning: long-term memory may contain dad jokes!"

See CLAUDE.md section "Cognee Cloud API Quirks" for details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from agent_memory.cognee_client import CogneeClient


@dataclass
class PayloadCapture:
    """Captures request payloads sent to Cognee Cloud API.

    Used by contract tests to validate that CogneeClient sends correct
    field names (camelCase) in API requests.

    Attributes:
        requests: List of captured requests, each containing method, endpoint, and json_data.

    Example:
        >>> capture = PayloadCapture()
        >>> # After mocked client call...
        >>> assert capture.last_json_data["textData"] == ["content"]
        >>> assert "data" not in capture.last_json_data  # Wrong field name
    """

    requests: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> None:
        """Record a request for later assertion.

        Args:
            method: HTTP method (GET, POST, DELETE).
            endpoint: API endpoint path.
            json_data: Request body as dict.
        """
        self.requests.append({
            "method": method,
            "endpoint": endpoint,
            "json_data": json_data or {},
        })

    @property
    def last_request(self) -> dict[str, Any]:
        """Get the most recent captured request.

        Returns:
            Dict with method, endpoint, and json_data.

        Raises:
            IndexError: If no requests have been captured.
        """
        return self.requests[-1]

    @property
    def last_json_data(self) -> dict[str, Any]:
        """Get the json_data from the most recent request.

        Returns:
            The json_data dict from the last request.

        Raises:
            IndexError: If no requests have been captured.
        """
        return self.last_request["json_data"]

    def get_requests_for_endpoint(self, endpoint_suffix: str) -> list[dict[str, Any]]:
        """Get all requests to an endpoint.

        Args:
            endpoint_suffix: Endpoint path suffix (e.g., "/add", "/search").

        Returns:
            List of requests matching the endpoint.
        """
        return [r for r in self.requests if r["endpoint"].endswith(endpoint_suffix)]

    def clear(self) -> None:
        """Clear all captured requests."""
        self.requests.clear()


@pytest.fixture
def payload_capture() -> PayloadCapture:
    """Create a fresh PayloadCapture for each test.

    Returns:
        Empty PayloadCapture instance.

    Example:
        >>> def test_add_content_uses_textData(payload_capture, mock_cognee_client):
        ...     await mock_cognee_client.add_content("test", "dataset")
        ...     assert "textData" in payload_capture.last_json_data
    """
    return PayloadCapture()


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Create a mock httpx.Response for successful requests.

    Returns:
        MagicMock configured to behave like httpx.Response(200).
    """
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = "{}"
    response.json.return_value = []
    return response


@pytest.fixture
def mock_request(
    payload_capture: PayloadCapture,
    mock_http_response: MagicMock,
) -> Generator[AsyncMock, None, None]:
    """Mock CogneeClient._make_request to capture payloads without network calls.

    This fixture patches the internal _make_request method to:
    1. Capture all request payloads in payload_capture
    2. Return a mock successful response
    3. Never make actual network calls

    Args:
        payload_capture: PayloadCapture fixture to record requests.
        mock_http_response: Mock response to return.

    Yields:
        AsyncMock of _make_request method.

    Example:
        >>> @pytest.mark.requirement("FR-001")
        >>> async def test_add_content_uses_textData(mock_request, payload_capture):
        ...     client = CogneeClient(mock_config)
        ...     await client.add_content("test content", "test_dataset")
        ...     assert "textData" in payload_capture.last_json_data
        ...     assert payload_capture.last_json_data["textData"] == ["test content"]
    """
    async def capture_request(
        method: str,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        timeout: float = 300.0,  # noqa: ARG001  # Required to match signature
    ) -> MagicMock:
        """Capture request and return mock response."""
        payload_capture.record(method, endpoint, json_data)
        return mock_http_response

    with patch(
        "agent_memory.cognee_client.CogneeClient._make_request",
        new=AsyncMock(side_effect=capture_request),
    ) as mock:
        yield mock


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock AgentMemoryConfig for contract tests.

    Returns:
        MagicMock configured with minimal required config values.
    """
    config = MagicMock()
    config.cognee_api_url = "https://api.cognee.ai"
    config.cognee_api_key.get_secret_value.return_value = "test-api-key"
    config.cognee_api_version = "v1"
    config.search_top_k = 5
    return config


@pytest.fixture
def cognee_client(mock_config: MagicMock) -> CogneeClient:
    """Create a CogneeClient instance for contract tests.

    Uses mock_config to avoid needing real credentials.

    Args:
        mock_config: Mock configuration fixture.

    Returns:
        CogneeClient instance with mock config.
    """
    from agent_memory.cognee_client import CogneeClient

    return CogneeClient(mock_config)
