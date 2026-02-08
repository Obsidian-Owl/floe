"""Unit tests for CogneeClient.

Tests for:
- Search response parsing (FR-015): All 5 response format variations
- Payload construction: add_content, cognify, search
- Error handling: Retryable and non-retryable status codes

Implementation: T015-T026 (FLO-654 to FLO-643)

Requirements Covered:
- FR-015: Handle all response format variations
- FR-008: SDK error handling
- SC-002: 80%+ unit test coverage
- SC-007: Unit tests execute in < 30 seconds
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

if TYPE_CHECKING:
    pass


class TestSearchResponseParsing:
    """Unit tests for search response parsing.

    Tests all 5 response format variations that Cognee Cloud API can return.
    Each test mocks the HTTP response and verifies correct parsing.
    """

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock configuration."""
        config = MagicMock()
        config.cognee_api_url = "https://api.cognee.ai"
        config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        config.cognee_api_version = "v1"
        config.search_top_k = 5
        return config

    @pytest.fixture
    def cognee_client(self, mock_config: MagicMock) -> Any:
        """Create CogneeClient with mock config."""
        from agent_memory.cognee_client import CogneeClient

        return CogneeClient(mock_config)

    def _create_mock_response(
        self,
        json_data: Any,
        status_code: int = 200,
    ) -> MagicMock:
        """Create mock httpx.Response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = json_data
        response.text = str(json_data)
        return response

    @pytest.mark.requirement("FR-015")
    async def test_parse_direct_list_format(
        self,
        cognee_client: Any,
    ) -> None:
        """Test parsing direct list response format.

        Format 1: [{"content": "...", "score": 0.9}, ...]

        Requirement: FR-015
        """
        # Arrange
        response_data = [
            {"content": "First result", "score": 0.9},
            {"content": "Second result", "score": 0.8},
        ]
        mock_response = self._create_mock_response(response_data)

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            # Act
            result = await cognee_client.search("test query")

            # Assert
            assert len(result.results) == 2
            assert result.results[0].content == "First result"
            assert result.results[0].relevance_score == pytest.approx(0.9)
            assert result.results[1].content == "Second result"
            assert result.results[1].relevance_score == pytest.approx(0.8)

    @pytest.mark.requirement("FR-015")
    async def test_parse_dict_with_results_format(
        self,
        cognee_client: Any,
    ) -> None:
        """Test parsing dict with 'results' key format.

        Format 2: {"results": [{"content": "...", "score": 0.9}, ...]}

        Requirement: FR-015
        """
        # Arrange
        response_data = {
            "results": [
                {"content": "Result from results key", "score": 0.85},
            ],
        }
        mock_response = self._create_mock_response(response_data)

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            # Act
            result = await cognee_client.search("test query")

            # Assert
            assert len(result.results) == 1
            assert result.results[0].content == "Result from results key"
            assert result.results[0].relevance_score == pytest.approx(0.85)

    @pytest.mark.requirement("FR-015")
    async def test_parse_dict_with_data_format(
        self,
        cognee_client: Any,
    ) -> None:
        """Test parsing dict with 'data' key format.

        Format 3: {"data": [{"content": "...", "score": 0.9}, ...]}

        Requirement: FR-015
        """
        # Arrange
        response_data = {
            "data": [
                {"content": "Result from data key", "score": 0.75},
            ],
        }
        mock_response = self._create_mock_response(response_data)

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            # Act
            result = await cognee_client.search("test query")

            # Assert
            assert len(result.results) == 1
            assert result.results[0].content == "Result from data key"
            assert result.results[0].relevance_score == pytest.approx(0.75)

    @pytest.mark.requirement("FR-015")
    async def test_parse_nested_search_result_format(
        self,
        cognee_client: Any,
    ) -> None:
        """Test parsing nested search_result format.

        Format 4: [{"search_result": ["text1", "text2"], "dataset_id": "..."}, ...]

        Requirement: FR-015
        """
        # Arrange
        response_data = [
            {
                "search_result": ["First line", "Second line"],
                "dataset_id": "ds-123",
                "score": 0.95,
            },
        ]
        mock_response = self._create_mock_response(response_data)

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            # Act
            result = await cognee_client.search("test query")

            # Assert
            assert len(result.results) == 1
            # search_result items are joined with newlines
            assert result.results[0].content == "First line\nSecond line"
            assert result.results[0].relevance_score == pytest.approx(0.95)

    @pytest.mark.requirement("FR-015")
    async def test_parse_empty_response(
        self,
        cognee_client: Any,
    ) -> None:
        """Test parsing empty response.

        Format 5: [] or {} or {"results": []}

        Requirement: FR-015
        """
        # Test empty list
        mock_response = self._create_mock_response([])

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await cognee_client.search("test query")
            assert len(result.results) == 0
            assert result.total_count == 0

        # Test empty dict with results key
        mock_response = self._create_mock_response({"results": []})

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await cognee_client.search("another query")
            assert len(result.results) == 0

    @pytest.mark.requirement("FR-015")
    async def test_parse_text_field_fallback(
        self,
        cognee_client: Any,
    ) -> None:
        """Test parsing falls back to 'text' field when 'content' is missing.

        Requirement: FR-015
        """
        # Arrange
        response_data = [
            {"text": "Text field content", "score": 0.7},
        ]
        mock_response = self._create_mock_response(response_data)

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            # Act
            result = await cognee_client.search("test query")

            # Assert
            assert len(result.results) == 1
            assert result.results[0].content == "Text field content"

    @pytest.mark.requirement("FR-015")
    async def test_parse_string_items(
        self,
        cognee_client: Any,
    ) -> None:
        """Test parsing when items are plain strings instead of dicts.

        Requirement: FR-015
        """
        # Arrange
        response_data = ["Plain string result 1", "Plain string result 2"]
        mock_response = self._create_mock_response(response_data)

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            # Act
            result = await cognee_client.search("test query")

            # Assert
            assert len(result.results) == 2
            assert result.results[0].content == "Plain string result 1"
            assert result.results[0].relevance_score == pytest.approx(0.0)


class TestPayloadConstruction:
    """Unit tests for API payload construction."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock configuration."""
        config = MagicMock()
        config.cognee_api_url = "https://api.cognee.ai"
        config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        config.cognee_api_version = "v1"
        config.search_top_k = 5
        return config

    @pytest.fixture
    def cognee_client(self, mock_config: MagicMock) -> Any:
        """Create CogneeClient with mock config."""
        from agent_memory.cognee_client import CogneeClient

        return CogneeClient(mock_config)

    @pytest.mark.requirement("FR-001")
    async def test_add_content_payload_structure(
        self,
        cognee_client: Any,
    ) -> None:
        """Test add_content constructs correct payload.

        Requirement: FR-001 (textData field)
        """
        captured_payload: dict[str, Any] = {}

        async def capture_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            captured_payload.update(json_data or {})
            response = MagicMock()
            response.status_code = 200
            return response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=capture_request),
        ):
            await cognee_client.add_content("test content", "test_dataset")

            assert "textData" in captured_payload
            assert "datasetName" in captured_payload
            assert captured_payload["textData"] == ["test content"]
            assert captured_payload["datasetName"] == "test_dataset"

    @pytest.mark.requirement("FR-001")
    async def test_add_content_list_payload(
        self,
        cognee_client: Any,
    ) -> None:
        """Test add_content with list of content items.

        Requirement: FR-001
        """
        captured_payload: dict[str, Any] = {}

        async def capture_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            captured_payload.update(json_data or {})
            response = MagicMock()
            response.status_code = 200
            return response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=capture_request),
        ):
            content_list = ["item 1", "item 2", "item 3"]
            await cognee_client.add_content(content_list, "test_dataset")

            assert captured_payload["textData"] == content_list

    @pytest.mark.requirement("FR-005")
    async def test_cognify_payload_with_dataset(
        self,
        cognee_client: Any,
    ) -> None:
        """Test cognify constructs correct payload with dataset.

        Requirement: FR-005 (datasets field)
        """
        captured_payload: dict[str, Any] = {}

        async def capture_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            captured_payload.update(json_data or {})
            response = MagicMock()
            response.status_code = 200
            return response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=capture_request),
        ):
            await cognee_client.cognify(dataset_name="my_dataset")

            assert "datasets" in captured_payload
            assert captured_payload["datasets"] == ["my_dataset"]

    @pytest.mark.requirement("FR-005")
    async def test_cognify_payload_without_dataset(
        self,
        cognee_client: Any,
    ) -> None:
        """Test cognify without dataset sends minimal payload.

        Requirement: FR-005
        """
        captured_payload: dict[str, Any] = {}

        async def capture_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            captured_payload.update(json_data or {})
            response = MagicMock()
            response.status_code = 200
            return response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=capture_request),
        ):
            await cognee_client.cognify()

            # Should not include datasets when not specified
            assert "datasets" not in captured_payload


class TestErrorHandling:
    """Unit tests for error handling."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock configuration."""
        config = MagicMock()
        config.cognee_api_url = "https://api.cognee.ai"
        config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        config.cognee_api_version = "v1"
        config.search_top_k = 5
        return config

    @pytest.fixture
    def cognee_client(self, mock_config: MagicMock) -> Any:
        """Create CogneeClient with mock config."""
        from agent_memory.cognee_client import CogneeClient

        return CogneeClient(mock_config)

    @pytest.mark.requirement("FR-008")
    async def test_retryable_status_codes(
        self,
        cognee_client: Any,
    ) -> None:
        """Test that retryable status codes trigger retries.

        Retryable codes: 408, 409, 429, 500, 502, 503, 504

        Requirement: FR-008
        """
        from agent_memory.cognee_client import RETRYABLE_STATUS_CODES

        # Verify retryable codes are defined correctly
        expected_codes = {408, 409, 429, 500, 502, 503, 504}
        assert RETRYABLE_STATUS_CODES == expected_codes

    @pytest.mark.requirement("FR-008")
    async def test_non_retryable_status_code_400(
        self,
        cognee_client: Any,
    ) -> None:
        """Test 400 Bad Request is not retried.

        Requirement: FR-008
        """
        from agent_memory.cognee_client import CogneeClientError

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            with pytest.raises(CogneeClientError, match="failed with status 400"):
                await cognee_client.add_content("test", "dataset")

    @pytest.mark.requirement("FR-008")
    async def test_non_retryable_status_code_401(
        self,
        cognee_client: Any,
    ) -> None:
        """Test 401 Unauthorized is not retried.

        Requirement: FR-008
        """
        from agent_memory.cognee_client import CogneeClientError

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            with pytest.raises(CogneeClientError, match="failed with status 401"):
                await cognee_client.add_content("test", "dataset")

    @pytest.mark.requirement("FR-008")
    async def test_non_retryable_status_code_404(
        self,
        cognee_client: Any,
    ) -> None:
        """Test 404 Not Found is not retried.

        Requirement: FR-008
        """
        from agent_memory.cognee_client import CogneeClientError

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            with pytest.raises(CogneeClientError, match="failed with status 404"):
                await cognee_client.add_content("test", "dataset")

    @pytest.mark.requirement("FR-008")
    async def test_ssl_error_triggers_retry(
        self,
        mock_config: MagicMock,
    ) -> None:
        """Test that SSL errors trigger retries.

        SSL "record layer failure" and similar transient TLS errors should
        be retried like other connection errors.

        Requirement: FR-008
        """
        import ssl

        from agent_memory.cognee_client import CogneeClient, CogneeClientError
        from agent_memory.resilience import RetryConfig

        # Use a config with fewer retries for faster tests
        retry_config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        client = CogneeClient(mock_config, retry_config=retry_config)

        # Create an SSL error to simulate transient TLS failure
        ssl_error = ssl.SSLError(1, "[SSL] record layer failure (_ssl.c:2580)")

        # Track call count to verify retries
        call_count = 0

        async def mock_request(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            raise ssl_error

        with (patch("httpx.AsyncClient") as mock_async_client,):
            mock_client_instance = AsyncMock()
            mock_client_instance.request.side_effect = mock_request
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_async_client.return_value = mock_client_instance

            with pytest.raises(CogneeClientError, match="Request failed after"):
                await client._make_request(
                    "POST", "/api/add", json_data={"data": "test"}
                )

            # Should have retried max_retries times
            assert call_count == 3

    @pytest.mark.requirement("FR-008")
    async def test_proxy_error_triggers_retry(
        self,
        mock_config: MagicMock,
    ) -> None:
        """Test that ProxyError (502 Bad Gateway) triggers retries.

        httpx.ProxyError is raised when a proxy returns an error like 502.
        This was a critical bug - 502s were coming as ProxyError exceptions
        rather than status codes, bypassing retry logic.

        Requirement: FR-008
        """
        from agent_memory.cognee_client import CogneeClient, CogneeClientError
        from agent_memory.resilience import RetryConfig

        # Use a config with fewer retries for faster tests
        retry_config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        client = CogneeClient(mock_config, retry_config=retry_config)

        # Create a ProxyError to simulate 502 Bad Gateway
        proxy_error = httpx.ProxyError("502 Bad Gateway")

        # Track call count to verify retries
        call_count = 0

        async def mock_request(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            raise proxy_error

        with (patch("httpx.AsyncClient") as mock_async_client,):
            mock_client_instance = AsyncMock()
            mock_client_instance.request.side_effect = mock_request
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_async_client.return_value = mock_client_instance

            with pytest.raises(CogneeClientError, match="Request failed after"):
                await client._make_request(
                    "POST", "/api/add", json_data={"data": "test"}
                )

            # Should have retried max_retries times
            assert call_count == 3


class TestSearchResultMetadata:
    """Unit tests for search result metadata extraction."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock configuration."""
        config = MagicMock()
        config.cognee_api_url = "https://api.cognee.ai"
        config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        config.cognee_api_version = "v1"
        config.search_top_k = 5
        return config

    @pytest.fixture
    def cognee_client(self, mock_config: MagicMock) -> Any:
        """Create CogneeClient with mock config."""
        from agent_memory.cognee_client import CogneeClient

        return CogneeClient(mock_config)

    @pytest.mark.requirement("FR-015")
    async def test_metadata_extraction(
        self,
        cognee_client: Any,
    ) -> None:
        """Test metadata is correctly extracted from response.

        Requirement: FR-015
        """
        response_data = [
            {
                "content": "Test content",
                "score": 0.9,
                "source": "/path/to/file.md",
                "dataset_name": "test_dataset",
                "dataset_id": "ds-123",
                "metadata": {"custom_key": "custom_value"},
            },
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await cognee_client.search("test query")

            assert len(result.results) == 1
            item = result.results[0]
            assert item.source_path == "/path/to/file.md"
            assert item.metadata["dataset_name"] == "test_dataset"
            assert item.metadata["dataset_id"] == "ds-123"
            assert item.metadata["custom_key"] == "custom_value"

    @pytest.mark.requirement("FR-015")
    async def test_source_path_fallback(
        self,
        cognee_client: Any,
    ) -> None:
        """Test source_path falls back to source_path field.

        Requirement: FR-015
        """
        response_data = [
            {
                "content": "Test content",
                "score": 0.9,
                "source_path": "/fallback/path.md",
            },
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await cognee_client.search("test query")

            assert result.results[0].source_path == "/fallback/path.md"


class TestVerifyParameter:
    """Unit tests for verify parameter in add_content.

    Tests that the verify parameter triggers read-after-write verification.

    Implementation: T030, T030a (FLO-687, FLO-688)
    Requirements: FR-009, FR-010
    """

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock configuration."""
        config = MagicMock()
        config.cognee_api_url = "https://api.cognee.ai"
        config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        config.cognee_api_version = "v1"
        config.search_top_k = 5
        return config

    @pytest.fixture
    def cognee_client(self, mock_config: MagicMock) -> Any:
        """Create CogneeClient with mock config."""
        from agent_memory.cognee_client import CogneeClient

        return CogneeClient(mock_config)

    @pytest.mark.requirement("FR-009")
    async def test_verify_true_triggers_verification(
        self,
        cognee_client: Any,
    ) -> None:
        """Test verify=True triggers read-after-write verification.

        When verify=True, add_content should:
        1. Add the content via POST /add
        2. Search for the content to verify it was stored
        3. Raise VerificationError if content not found

        Requirement: FR-009
        """
        add_response = MagicMock()
        add_response.status_code = 200
        add_response.text = "{}"

        # Search response includes the added content (verification passes)
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.json.return_value = [
            {"content": "test verification content", "score": 0.95}
        ]

        call_count = 0

        async def mock_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if "/add" in endpoint:
                return add_response
            if "/search" in endpoint:
                return search_response
            return add_response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=mock_request),
        ):
            # Call with verify=True
            await cognee_client.add_content(
                "test verification content",
                "test_dataset",
                verify=True,
            )

            # Should have made 2 requests: add + search
            assert call_count == 2

    @pytest.mark.requirement("FR-009")
    async def test_verify_false_skips_verification(
        self,
        cognee_client: Any,
    ) -> None:
        """Test verify=False (default) skips verification.

        When verify=False (the default), add_content should:
        1. Add the content via POST /add
        2. NOT search for verification

        Requirement: FR-009
        """
        add_response = MagicMock()
        add_response.status_code = 200
        add_response.text = "{}"

        call_count = 0
        endpoints_called: list[str] = []

        async def mock_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            nonlocal call_count
            call_count += 1
            endpoints_called.append(endpoint)
            return add_response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=mock_request),
        ):
            # Call with default verify=False
            await cognee_client.add_content(
                "test content",
                "test_dataset",
            )

            # Should have made only 1 request: add (no search)
            assert call_count == 1
            assert "/search" not in endpoints_called[0]

    @pytest.mark.requirement("FR-010")
    async def test_verify_raises_on_content_not_found(
        self,
        cognee_client: Any,
    ) -> None:
        """Test verify=True raises VerificationError if content not found.

        When verification search doesn't find the added content,
        a VerificationError should be raised.

        Requirement: FR-010
        """
        from agent_memory.cognee_client import VerificationError

        add_response = MagicMock()
        add_response.status_code = 200
        add_response.text = "{}"

        # Search response is empty (verification fails)
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.json.return_value = []

        async def mock_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            if "/add" in endpoint:
                return add_response
            if "/search" in endpoint:
                return search_response
            return add_response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=mock_request),
        ):
            with pytest.raises(VerificationError, match="No search results"):
                await cognee_client.add_content(
                    "content that wont be found",
                    "test_dataset",
                    verify=True,
                )


class TestCognifyStatusPolling:
    """Unit tests for status polling in cognify.

    Tests the wait_for_completion parameter that enables status polling.

    Implementation: T031 (FLO-686)
    Requirements: FR-012, FR-013
    """

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock configuration."""
        config = MagicMock()
        config.cognee_api_url = "https://api.cognee.ai"
        config.cognee_api_key.get_secret_value.return_value = "test-api-key"
        config.cognee_api_version = "v1"
        config.search_top_k = 5
        return config

    @pytest.fixture
    def cognee_client(self, mock_config: MagicMock) -> Any:
        """Create CogneeClient with mock config."""
        from agent_memory.cognee_client import CogneeClient

        return CogneeClient(mock_config)

    @pytest.mark.requirement("FR-012")
    async def test_wait_for_completion_polls_status(
        self,
        cognee_client: Any,
    ) -> None:
        """Test wait_for_completion=True polls status endpoint.

        When wait_for_completion=True, cognify should:
        1. Start cognify via POST /cognify
        2. Poll GET /datasets/{name}/status until complete
        3. Return when status is "COMPLETED"

        Requirement: FR-012
        """
        cognify_response = MagicMock()
        cognify_response.status_code = 202  # Accepted (async processing)
        cognify_response.text = "{}"

        # First status check: processing, second: completed
        status_responses = [
            {"status": "PROCESSING"},
            {"status": "COMPLETED"},
        ]
        status_index = 0

        async def mock_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            nonlocal status_index
            if "/cognify" in endpoint:
                return cognify_response
            if "/status" in endpoint:
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = status_responses[
                    min(status_index, len(status_responses) - 1)
                ]
                status_index += 1
                return response
            return cognify_response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=mock_request),
        ):
            # Use short polling interval for test speed
            await cognee_client.cognify(
                dataset_name="test_dataset",
                wait_for_completion=True,
                poll_interval=0.01,  # 10ms for fast test
            )

            # Should have polled status at least once
            assert status_index >= 1

    @pytest.mark.requirement("FR-012")
    async def test_wait_for_completion_false_skips_polling(
        self,
        cognee_client: Any,
    ) -> None:
        """Test wait_for_completion=False (default) skips polling.

        When wait_for_completion=False (the default), cognify should:
        1. Start cognify via POST /cognify
        2. Return immediately without polling

        Requirement: FR-012
        """
        cognify_response = MagicMock()
        cognify_response.status_code = 202
        cognify_response.text = "{}"

        endpoints_called: list[str] = []

        async def mock_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            endpoints_called.append(endpoint)
            return cognify_response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=mock_request),
        ):
            await cognee_client.cognify(dataset_name="test_dataset")

            # Should only call cognify, not status
            assert len(endpoints_called) == 1
            assert "/cognify" in endpoints_called[0]
            assert not any("/status" in ep for ep in endpoints_called)

    @pytest.mark.requirement("FR-013")
    async def test_status_polling_timeout(
        self,
        cognee_client: Any,
    ) -> None:
        """Test status polling respects timeout.

        If status polling exceeds the timeout, a TimeoutError should be raised.

        Requirement: FR-013
        """
        from agent_memory.cognee_client import CognifyTimeoutError

        cognify_response = MagicMock()
        cognify_response.status_code = 202
        cognify_response.text = "{}"

        # Status always returns "PROCESSING" (never completes)
        async def mock_request(
            method: str,
            endpoint: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: float = 300.0,
        ) -> MagicMock:
            if "/cognify" in endpoint:
                return cognify_response
            if "/status" in endpoint:
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {"status": "PROCESSING"}
                return response
            return cognify_response

        with patch.object(
            cognee_client,
            "_make_request",
            new=AsyncMock(side_effect=mock_request),
        ):
            with pytest.raises(CognifyTimeoutError, match="timed out"):
                await cognee_client.cognify(
                    dataset_name="test_dataset",
                    wait_for_completion=True,
                    poll_interval=0.01,
                    timeout=0.05,  # 50ms timeout for fast test
                )
