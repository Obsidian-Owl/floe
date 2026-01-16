# Cognee REST API Contract

**Date**: 2026-01-16
**Feature**: 10b-agent-memory-quality
**Type**: External REST API (Cognee Cloud)

## Overview

This contract documents the Cognee Cloud REST API field names and response formats that CogneeClient depends on. Contract tests validate that CogneeClient sends correct payloads.

**Base URL**: `https://api.cognee.ai`
**API Version**: `/api/v1` or `/api` (configurable)
**Authentication**: `X-Api-Key` header

---

## Critical Contract: Field Names (camelCase)

**CRITICAL**: All request payloads MUST use camelCase field names. Using snake_case causes the API to use default values.

**Bug History**: The "dad jokes" incident (2026-01-16) was caused by sending `"data"` instead of `"textData"`. The API's default value for missing `textData` is `["Warning: long-term memory may contain dad jokes!"]`.

---

## Endpoint: POST /api/v1/add

**Purpose**: Add text content to a dataset.

### Request

```json
{
    "textData": ["content1", "content2"],
    "datasetName": "my_dataset",
    "datasetId": "uuid-optional",
    "nodeSet": ["label1", "label2"]
}
```

### Field Contract

| Field | Type | Required | Correct Name | Wrong Name (triggers bug) |
|-------|------|----------|--------------|---------------------------|
| textData | `list[str]` | YES | `textData` | `data`, `text_data` |
| datasetName | `str` | NO | `datasetName` | `dataset_name` |
| datasetId | `UUID` | NO | `datasetId` | `dataset_id` |
| nodeSet | `list[str]` | NO | `nodeSet` | `node_set` |

### Response

**Success (200/201/202)**:
```json
{}
```

**Error (4xx/5xx)**:
```json
{
    "detail": "error message"
}
```

### Contract Test

```python
@pytest.mark.requirement("10B-FR-001")
async def test_add_content_uses_textData_field(client, mock_request):
    """Verify add_content sends 'textData', not 'data'."""
    await client.add_content("test content", "dataset")

    payload = mock_request.call_args.kwargs['json_data']
    assert 'textData' in payload, "MUST use 'textData'"
    assert 'data' not in payload, "Bug regression: sent 'data'"
    assert payload['textData'] == ['test content']
```

---

## Endpoint: POST /api/v1/search

**Purpose**: Query the knowledge graph.

### Request

```json
{
    "query": "search text",
    "searchType": "GRAPH_COMPLETION",
    "topK": 10,
    "datasets": ["dataset1"],
    "datasetIds": ["uuid1"],
    "systemPrompt": "custom prompt",
    "nodeName": ["filter"],
    "onlyContext": false,
    "useCombinedContext": false
}
```

### Field Contract

| Field | Type | Required | Correct Name | Wrong Name (triggers bug) |
|-------|------|----------|--------------|---------------------------|
| query | `str` | YES | `query` | - |
| searchType | `str` | NO | `searchType` | `search_type` |
| topK | `int` | NO | `topK` | `top_k` |
| datasets | `list[str]` | NO | `datasets` | - |
| datasetIds | `list[UUID]` | NO | `datasetIds` | `dataset_ids` |
| systemPrompt | `str` | NO | `systemPrompt` | `system_prompt` |
| nodeName | `list[str]` | NO | `nodeName` | `node_name` |
| onlyContext | `bool` | NO | `onlyContext` | `only_context` |
| useCombinedContext | `bool` | NO | `useCombinedContext` | `use_combined_context` |

### SearchType Enum

```python
SearchType = Literal[
    "SUMMARIES",
    "CHUNKS",
    "RAG_COMPLETION",
    "GRAPH_COMPLETION",  # Default
    "GRAPH_SUMMARY_COMPLETION",
    "CODE",
    "CYPHER",
    "NATURAL_LANGUAGE",
    "GRAPH_COMPLETION_COT",
    "GRAPH_COMPLETION_CONTEXT_EXTENSION",
    "FEELING_LUCKY",
    "FEEDBACK",
    "TEMPORAL",
    "CODING_RULES",
    "CHUNKS_LEXICAL",
]
```

### Response Formats (ALL must be handled)

**Format 1: Direct list**
```json
[
    {"content": "result text", "score": 0.95},
    {"content": "another result", "score": 0.87}
]
```

**Format 2: Dict with results**
```json
{
    "results": [
        {"content": "result text", "score": 0.95}
    ]
}
```

**Format 3: Dict with data**
```json
{
    "data": [
        {"content": "result text", "score": 0.95}
    ]
}
```

**Format 4: Nested search_result (GRAPH_COMPLETION)**
```json
[
    {
        "search_result": ["text line 1", "text line 2"],
        "dataset_id": "uuid"
    }
]
```

### Contract Test

```python
@pytest.mark.requirement("10B-FR-003")
async def test_search_uses_searchType_field(client, mock_request):
    """Verify search sends 'searchType', not 'search_type'."""
    await client.search("query")

    payload = mock_request.call_args.kwargs['json_data']
    assert 'searchType' in payload, "MUST use 'searchType'"
    assert 'search_type' not in payload, "Bug regression"

@pytest.mark.requirement("10B-FR-004")
async def test_search_uses_topK_field(client, mock_request):
    """Verify search sends 'topK', not 'top_k'."""
    await client.search("query", top_k=5)

    payload = mock_request.call_args.kwargs['json_data']
    assert 'topK' in payload, "MUST use 'topK'"
    assert 'top_k' not in payload, "Bug regression"
```

---

## Endpoint: POST /api/v1/cognify

**Purpose**: Transform content into knowledge graph.

### Request

```json
{
    "datasets": ["dataset1", "dataset2"],
    "dataset_ids": ["uuid1"],
    "run_in_background": true
}
```

### Field Contract

| Field | Type | Required | Correct Name | Notes |
|-------|------|----------|--------------|-------|
| datasets | `list[str]` | NO | `datasets` | Already correct |
| dataset_ids | `list[UUID]` | NO | `dataset_ids` | Snake_case is accepted |
| run_in_background | `bool` | NO | `run_in_background` | Snake_case is accepted |

### Response

**Success (200/201/202)**:
```json
{}
```

### Contract Test

```python
@pytest.mark.requirement("10B-FR-005")
async def test_cognify_uses_datasets_field(client, mock_request):
    """Verify cognify sends 'datasets' in correct format."""
    await client.cognify("my_dataset")

    payload = mock_request.call_args.kwargs['json_data']
    assert 'datasets' in payload
    assert isinstance(payload['datasets'], list)
```

---

## Endpoint: GET /api/v1/datasets/status

**Purpose**: Check processing status for datasets.

### Request

**Query Parameters**:
- `dataset`: List of dataset UUIDs (optional)

### Response

```json
{
    "uuid-1": "DATASET_PROCESSING_COMPLETED",
    "uuid-2": "DATASET_PROCESSING_STARTED"
}
```

### Status Values

| Status | Meaning |
|--------|---------|
| `DATASET_PROCESSING_INITIATED` | Queued for processing |
| `DATASET_PROCESSING_STARTED` | Currently processing |
| `DATASET_PROCESSING_COMPLETED` | Successfully finished |
| `DATASET_PROCESSING_ERRORED` | Processing failed |

### Polling Pattern

```python
async def wait_for_completion(dataset_id: str, timeout: float = 300.0):
    """Poll until cognify completes."""
    start = time.monotonic()
    while (time.monotonic() - start) < timeout:
        status = await client.get_dataset_status([dataset_id])
        if status.get(dataset_id) == "DATASET_PROCESSING_COMPLETED":
            return True
        if status.get(dataset_id) == "DATASET_PROCESSING_ERRORED":
            raise CogneeClientError(f"Cognify failed: {dataset_id}")
        await asyncio.sleep(2.0)
    raise TimeoutError(f"Cognify timeout after {timeout}s")
```

---

## Endpoint: GET /api/v1/datasets

**Purpose**: List all datasets.

### Response

**Format 1: Direct list**
```json
[
    {"id": "uuid", "name": "dataset1", "created_at": "..."},
    {"id": "uuid", "name": "dataset2", "created_at": "..."}
]
```

**Format 2: Dict with datasets**
```json
{
    "datasets": [
        {"id": "uuid", "name": "dataset1"}
    ]
}
```

**Format 3: Dict with data**
```json
{
    "data": [
        {"id": "uuid", "name": "dataset1"}
    ]
}
```

---

## Endpoint: DELETE /api/v1/datasets/{dataset_id}

**Purpose**: Delete a dataset and its content.

### Response

**Success (200/204)**:
```json
{}
```

---

## Authentication Contract

**Header**: `X-Api-Key`

```python
def _get_headers(self) -> dict[str, str]:
    return {
        "X-Api-Key": self._config.cognee_api_key.get_secret_value(),
        "Content-Type": "application/json",
    }
```

**Contract**:
- API key MUST be sent in `X-Api-Key` header
- Content-Type MUST be `application/json`
- Invalid/missing key returns HTTP 401

---

## Error Handling Contract

### Retryable Status Codes

```python
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
```

**Behavior**:
- 408: Request Timeout - retry with backoff
- 409: Conflict - retry (resource busy)
- 429: Rate Limited - retry with backoff
- 500-504: Server Error - retry with backoff

### Non-Retryable Errors

- 400: Bad Request - raise immediately (payload error)
- 401: Unauthorized - raise immediately (invalid key)
- 403: Forbidden - raise immediately (permission error)
- 404: Not Found - raise immediately (resource missing)

---

## Contract Test Suite Requirements

### Test Categories

1. **Field Name Tests** (FR-001 to FR-005)
   - Validate camelCase field names in payloads
   - Assert absence of snake_case alternatives

2. **Response Parsing Tests** (FR-015)
   - Handle all 4+ response formats
   - Handle empty responses
   - Handle unexpected formats gracefully

3. **Error Handling Tests**
   - Retry on retryable codes
   - Raise on non-retryable codes
   - Include error details in exceptions

### Test Execution

```bash
# Run contract tests only (fast, no network)
pytest tests/contract/ -v

# Expected: < 5 seconds (SC-006)
```

---

## Version Compatibility

**API Version**: Configurable via `cognee_api_version` config
- Empty string (`""`) → `/api`
- `"v1"` → `/api/v1`

**Contract Tests**: Validate against current API version (v1)

---

## References

- OpenAPI Spec: https://api.cognee.ai/openapi.json
- HTTP API Docs: https://docs.cognee.ai/http_api
- Epic 10A Research: `/specs/10a-agent-memory/research.md`
