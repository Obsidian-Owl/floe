"""Contract tests for Cognee Cloud API field names.

These tests validate that CogneeClient sends the correct camelCase field names
to the Cognee Cloud REST API. This prevents the "dad jokes" bug where using
wrong field names (snake_case instead of camelCase) causes the API to use
default values instead of our content.

Implementation: T007-T014 (FLO-662 to FLO-655)

Requirements Covered:
- FR-001: add_content MUST use textData (not data)
- FR-002: add_content MUST use datasetName (not dataset_name)
- FR-003: search MUST use searchType (not search_type)
- FR-004: search MUST use topK (not top_k)
- FR-005: cognify MUST use datasets (already correct)

Test Strategy:
- Use PayloadCapture fixture to intercept API payloads
- Assert correct field names are present
- Assert wrong field names are absent
- No network calls - pure contract validation

Example Bug This Prevents:
    # WRONG: Using "data" instead of "textData"
    json_data = {"data": content_list}  # API ignores this!
    # API uses default: ["Warning: long-term memory may contain dad jokes!"]

    # CORRECT: Using "textData" (camelCase)
    json_data = {"textData": content_list}  # API processes our content
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from agent_memory.cognee_client import CogneeClient
    from tests.contract.conftest import PayloadCapture


class TestAddContentContract:
    """Contract tests for add_content API endpoint.

    Validates that add_content sends correct field names to /api/v1/add.
    """

    @pytest.mark.requirement("FR-001")
    async def test_add_content_uses_textData_field(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test add_content sends textData field (not data).

        The Cognee Cloud API expects textData (camelCase). Using "data"
        causes the API to ignore our content and use its default value.

        Requirement: FR-001
        """
        # Act
        await cognee_client.add_content("test content", "test_dataset")

        # Assert - correct field name is used
        json_data = payload_capture.last_json_data
        assert "textData" in json_data, (
            "add_content MUST use 'textData' field (camelCase). "
            "Using 'data' causes API to use default values."
        )
        assert json_data["textData"] == ["test content"]

    @pytest.mark.requirement("FR-001")
    async def test_add_content_does_not_use_wrong_field_data(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test add_content does NOT use wrong field name 'data'.

        This is the field name that caused the "dad jokes" bug.
        Ensure we never regress to using this field name.

        Requirement: FR-001
        """
        # Act
        await cognee_client.add_content("test content", "test_dataset")

        # Assert - wrong field name is NOT used
        json_data = payload_capture.last_json_data
        assert "data" not in json_data, (
            "add_content MUST NOT use 'data' field. "
            "This causes the 'dad jokes' bug where API ignores our content."
        )

    @pytest.mark.requirement("FR-002")
    async def test_add_content_uses_datasetName_field(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test add_content sends datasetName field (not dataset_name).

        The Cognee Cloud API expects datasetName (camelCase).

        Requirement: FR-002
        """
        # Act
        await cognee_client.add_content("test content", "my_dataset")

        # Assert - correct field name is used
        json_data = payload_capture.last_json_data
        assert (
            "datasetName" in json_data
        ), "add_content MUST use 'datasetName' field (camelCase). "
        assert json_data["datasetName"] == "my_dataset"

    @pytest.mark.requirement("FR-002")
    async def test_add_content_does_not_use_wrong_field_dataset_name(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test add_content does NOT use wrong field name 'dataset_name'.

        Requirement: FR-002
        """
        # Act
        await cognee_client.add_content("test content", "my_dataset")

        # Assert - wrong field name is NOT used
        json_data = payload_capture.last_json_data
        assert "dataset_name" not in json_data, (
            "add_content MUST NOT use 'dataset_name' (snake_case). "
            "Use 'datasetName' (camelCase) instead."
        )


class TestSearchContract:
    """Contract tests for search API endpoint.

    Validates that search sends correct field names to /api/v1/search.
    """

    @pytest.mark.requirement("FR-003")
    async def test_search_uses_searchType_field(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test search sends searchType field (not search_type).

        The Cognee Cloud API expects searchType (camelCase).

        Requirement: FR-003
        """
        # Act
        await cognee_client.search("test query", search_type="GRAPH_COMPLETION")

        # Assert - correct field name is used
        json_data = payload_capture.last_json_data
        assert (
            "searchType" in json_data
        ), "search MUST use 'searchType' field (camelCase). "
        assert json_data["searchType"] == "GRAPH_COMPLETION"

    @pytest.mark.requirement("FR-003")
    async def test_search_does_not_use_wrong_field_search_type(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test search does NOT use wrong field name 'search_type'.

        Requirement: FR-003
        """
        # Act
        await cognee_client.search("test query")

        # Assert - wrong field name is NOT used
        json_data = payload_capture.last_json_data
        assert (
            "search_type" not in json_data
        ), "search MUST NOT use 'search_type' (snake_case). Use 'searchType' (camelCase) instead."

    @pytest.mark.requirement("FR-004")
    async def test_search_uses_topK_field(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test search sends topK field (not top_k).

        The Cognee Cloud API expects topK (camelCase).

        Requirement: FR-004
        """
        # Act
        await cognee_client.search("test query", top_k=10)

        # Assert - correct field name is used
        json_data = payload_capture.last_json_data
        assert "topK" in json_data, "search MUST use 'topK' field (camelCase). "
        assert json_data["topK"] == 10

    @pytest.mark.requirement("FR-004")
    async def test_search_does_not_use_wrong_field_top_k(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test search does NOT use wrong field name 'top_k'.

        Requirement: FR-004
        """
        # Act
        await cognee_client.search("test query")

        # Assert - wrong field name is NOT used
        json_data = payload_capture.last_json_data
        assert (
            "top_k" not in json_data
        ), "search MUST NOT use 'top_k' (snake_case). Use 'topK' (camelCase) instead."


class TestCognifyContract:
    """Contract tests for cognify API endpoint.

    Validates that cognify sends correct field names to /api/v1/cognify.
    """

    @pytest.mark.requirement("FR-005")
    async def test_cognify_uses_datasets_field(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test cognify sends datasets field for dataset scoping.

        The Cognee Cloud API expects datasets as a list.

        Requirement: FR-005
        """
        # Act
        await cognee_client.cognify(dataset_name="test_dataset")

        # Assert - correct field name is used
        json_data = payload_capture.last_json_data
        assert (
            "datasets" in json_data
        ), "cognify MUST use 'datasets' field when dataset is specified."
        assert json_data["datasets"] == ["test_dataset"]

    @pytest.mark.requirement("FR-005")
    async def test_cognify_without_dataset_sends_empty_payload(
        self,
        mock_request: AsyncMock,
        payload_capture: PayloadCapture,
        cognee_client: CogneeClient,
    ) -> None:
        """Test cognify without dataset_name sends empty payload.

        When no dataset is specified, cognify processes all datasets.
        The implementation sends an empty JSON object {} (no datasets field).

        Requirement: FR-005
        """
        # Act
        await cognee_client.cognify()

        # Assert - datasets field should NOT be present (empty payload)
        # Implementation sends {} when no dataset specified (see cognee_client.py:622-624)
        json_data = payload_capture.last_json_data
        assert "datasets" not in json_data, (
            f"cognify without dataset should send empty payload (no 'datasets' field). "
            f"Got: {json_data!r}"
        )
