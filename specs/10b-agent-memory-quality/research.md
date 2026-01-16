# Research: Agent Memory Validation & Quality

**Feature**: Epic 10B - Agent Memory Validation & Quality
**Date**: 2026-01-16
**Status**: Complete

---

## Executive Summary

This research addresses the testing gaps discovered in Epic 10A where a critical API field name bug (`"data"` vs `"textData"`) caused all synced content to be replaced with Cognee's default value. The solution is comprehensive testing at three tiers: contract tests (validate API payloads), unit tests (verify CogneeClient logic), and integration tests (verify content searchability).

**Key Decisions**:
1. **Memify**: Refactor to REST API (`POST /api/v1/memify` not found in OpenAPI - investigate alternatives)
2. **Load Assurance**: Add optional `verify` parameter for read-after-write verification
3. **Status Polling**: Poll `/api/v1/datasets/status` until cognify completes

---

## Research Questions Resolved

### Q1: What are the exact Cognee REST API field names?

**Decision**: All API payloads MUST use camelCase field names.

**Validated from OpenAPI spec (https://api.cognee.ai/openapi.json)**:

| Endpoint | Field | Wrong (snake_case) | Correct (camelCase) |
|----------|-------|-------------------|---------------------|
| `POST /api/v1/add` | content | `data` | `textData` |
| `POST /api/v1/add` | dataset | `dataset_name` | `datasetName` |
| `POST /api/v1/add` | dataset ID | `dataset_id` | `datasetId` |
| `POST /api/v1/add` | node set | `node_set` | `nodeSet` |
| `POST /api/v1/search` | type | `search_type` | `searchType` |
| `POST /api/v1/search` | limit | `top_k` | `topK` |
| `POST /api/v1/cognify` | datasets | `datasets` | `datasets` (correct) |

**Critical Finding**: The `textData` field has a default value of `["Warning: long-term memory may contain dad jokes!"]`. This is why the bug caused "dad jokes" contamination - missing fields trigger this default.

**Rationale**: Contract tests must validate exact field names in JSON payloads before any HTTP call is made.

---

### Q2: How does the dataset status endpoint work?

**Decision**: Poll `GET /api/v1/datasets/status` with dataset UUIDs until processing completes.

**Endpoint**: `GET /api/v1/datasets/status`

**Request**: Query parameter `dataset` (List[UUID]) - dataset UUIDs to check

**Response Values**:
| Status | Meaning |
|--------|---------|
| `DATASET_PROCESSING_INITIATED` | Queued for processing |
| `DATASET_PROCESSING_STARTED` | Currently processing |
| `DATASET_PROCESSING_COMPLETED` | Successfully finished |
| `DATASET_PROCESSING_ERRORED` | Encountered error |

**Polling Pattern**:
```python
async def wait_for_cognify_completion(
    client: CogneeClient,
    dataset_id: str,
    timeout_seconds: float = 300.0,
    poll_interval_seconds: float = 2.0,
) -> bool:
    """Poll until cognify completes or times out."""
    start = time.monotonic()
    while (time.monotonic() - start) < timeout_seconds:
        status = await client.get_dataset_status([dataset_id])
        if status.get(dataset_id) == "DATASET_PROCESSING_COMPLETED":
            return True
        if status.get(dataset_id) == "DATASET_PROCESSING_ERRORED":
            raise CogneeClientError(f"Cognify failed for dataset {dataset_id}")
        await asyncio.sleep(poll_interval_seconds)
    raise TimeoutError(f"Cognify did not complete within {timeout_seconds}s")
```

**Rationale**: Integration tests must wait for cognify completion before searching, eliminating timing-related flakiness.

---

### Q3: Does memify have a REST API endpoint?

**Decision**: Memify does NOT have a documented REST API endpoint. Evaluate alternatives.

**Research Findings**:
1. **OpenAPI spec**: No `/api/v1/memify` endpoint exists
2. **HTTP API docs**: No memify endpoint listed among 30+ documented endpoints
3. **SDK only**: Memify is available via Python SDK (`cognee.memify()`) and CLI
4. **cogwit_sdk**: Current implementation uses cogwit_sdk for memify

**Options for Epic 10B**:

| Option | Pros | Cons |
|--------|------|------|
| **A: Keep cogwit_sdk** | Already works, no refactor needed | Inconsistent with REST pattern, adds dependency |
| **B: Remove memify** | Simpler, removes dependency | Loses semantic enrichment capability |
| **C: Request API from Cognee** | Consistent REST pattern | Depends on external team, timeline unknown |

**Recommendation**: **Option A** - Keep cogwit_sdk for memify until REST endpoint becomes available. Document this inconsistency. The original FR-006 (refactor memify to REST) cannot be fulfilled as the endpoint doesn't exist.

**Update to Spec**: FR-006 through FR-008 need revision - memify cannot be refactored to REST API.

---

### Q4: What contract testing patterns work for HTTP APIs?

**Decision**: Mock at the `_make_request()` level to capture JSON payloads without network calls.

**Pattern**:
```python
@pytest.mark.requirement("10B-FR-001")
async def test_add_content_uses_textData_field():
    """Verify add_content sends 'textData', not 'data'."""
    with patch.object(client, '_make_request') as mock:
        mock.return_value = AsyncMock(status_code=200, json=lambda: {})
        await client.add_content("test", "dataset")

        json_data = mock.call_args.kwargs['json_data']
        assert 'textData' in json_data, "Must use camelCase 'textData'"
        assert json_data['textData'] == ['test']
        assert 'data' not in json_data, "Bug regression: sent 'data' instead of 'textData'"
```

**Key Benefits**:
1. Zero network calls (fast, deterministic)
2. Captures exact JSON payload structure
3. Runs on every PR without external dependencies
4. Clear failure messages for regressions

**Alternative Considered**: Mock at httpx level - more integration-like but harder to inspect payloads.

---

### Q5: What are the response format variations?

**Decision**: CogneeClient must handle multiple response formats defensively.

**Observed Formats from Cognee Cloud**:

```python
# Format 1: Direct list (most common)
[{"content": "...", "score": 0.9}, ...]

# Format 2: Dict with 'results' key
{"results": [{"content": "...", "score": 0.9}, ...]}

# Format 3: Dict with 'data' key
{"data": [{"content": "...", "score": 0.9}, ...]}

# Format 4: Nested search_result (GRAPH_COMPLETION)
[{"search_result": ["text1", "text2"], "dataset_id": "..."}, ...]
```

**Current Implementation** (cognee_client.py:598-605):
```python
raw_results: list[Any]
if isinstance(results_data, list):
    raw_results = results_data
elif isinstance(results_data, dict):
    raw_results = results_data.get("results") or results_data.get("data") or []
else:
    raw_results = []
```

**Unit Test Coverage Required**:
- `test_search_response_direct_list()`
- `test_search_response_dict_with_results()`
- `test_search_response_dict_with_data()`
- `test_search_response_nested_search_result()`
- `test_search_response_empty()`
- `test_search_response_invalid_format()`

---

### Q6: What is the verify (read-after-write) pattern?

**Decision**: Add optional `verify=True` to `add_content()` that confirms content exists in dataset.

**Implementation Pattern**:
```python
async def add_content(
    self,
    content: str | list[str],
    dataset_name: str,
    *,
    verify: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Add content to dataset.

    Args:
        content: Text content to add.
        dataset_name: Target dataset.
        verify: If True, confirms content is retrievable before returning.
    """
    # Add content via REST API
    await self._add_content_impl(content, dataset_name, metadata)

    if verify:
        # Verify content is in dataset
        datasets = await self.list_datasets()
        if dataset_name not in datasets:
            raise CogneeClientError(f"Dataset '{dataset_name}' not found after add")

        # Optionally search for unique term from content
        # to confirm it's indexed (before cognify)
```

**CLI Integration**:
```bash
# sync command with verification
agent-memory sync --all --dataset floe --verify
```

**Rationale**: Catches indexing failures early before cognify runs.

---

### Q7: What are the Cognee Cloud rate limits?

**Decision**: Implement retry logic and respect rate limits.

**Current Implementation** (cognee_client.py:40-41):
```python
DEFAULT_MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
```

**Rate Limit Handling**:
- HTTP 429 triggers exponential backoff
- Already implemented in `_make_request()` with 3 retries
- Poll interval for status checks: 2 seconds default

**Rationale**: Existing retry logic is sufficient; contract tests validate payload structure without hitting rate limits.

---

## Technology Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Contract Test Level | Mock `_make_request()` | Captures JSON payloads, no network |
| Memify Approach | Keep cogwit_sdk | No REST endpoint available |
| Status Polling | Poll with timeout | Wait for cognify completion |
| Verify Pattern | Optional flag | Catch indexing failures early |
| Response Parsing | Defensive multi-format | Handle API inconsistency |
| Field Validation | camelCase only | Match OpenAPI spec |

---

## Specification Updates Required

Based on research findings, the following spec changes are needed:

### FR-006, FR-007, FR-008: Memify REST Refactor
**Original**: Refactor memify to REST API, add contract tests, remove cogwit_sdk
**Updated**: Cannot fulfill - no REST endpoint exists. Options:
1. Remove these requirements (simplest)
2. Keep cogwit_sdk with SDK-level tests (not contract tests)
3. Defer until Cognee provides REST endpoint

**Recommendation**: Remove FR-006/FR-007/FR-008; add FR-006-ALT: "Document memify uses cogwit_sdk (not REST API) due to missing endpoint"

### FR-012: Status Polling
**Addition Needed**: Specify dataset UUID requirement (must get UUID from list_datasets first)

### Success Criteria SC-008
**Original**: "All CogneeClient methods use REST API consistently"
**Updated**: "All CogneeClient methods except memify use REST API consistently; memify documented as SDK-only"

---

## Implementation Implications

### What We Build

1. **Contract Tests** (`tests/contract/test_cognee_api_contract.py`)
   - Validate camelCase field names in all payloads
   - Mock at `_make_request()` level
   - Zero network calls, fast execution
   - ~10 test cases covering all endpoints

2. **CogneeClient Unit Tests** (`tests/unit/test_cognee_client.py`)
   - Test all response parsing paths
   - Test error handling paths
   - Test payload construction
   - Target 80% coverage

3. **Status Polling** (`cognee_client.py`)
   - Add `wait_for_cognify()` method
   - Poll `GET /api/v1/datasets/status`
   - Configurable timeout (default 5 min)

4. **Verify Flag** (`cognee_client.py`, `cli.py`)
   - Optional `verify=True` parameter
   - CLI `--verify` flag on sync command

5. **Integration Test Updates** (`tests/integration/`)
   - Verify content searchability (not just count)
   - Use unique identifiers in test content
   - Wait for cognify completion before search

### What We DON'T Build

1. **Memify REST Refactor** - Endpoint doesn't exist
2. **Custom Rate Limiting** - Existing retry logic sufficient
3. **Response Format Unification** - Handle multiple formats defensively

---

## References

- Cognee OpenAPI Spec: https://api.cognee.ai/openapi.json
- Cognee HTTP API Docs: https://docs.cognee.ai/http_api
- Cognee Memify Blog: https://www.cognee.ai/blog/cognee-news/product-update-memify
- Cognee REST Server Deploy: https://docs.cognee.ai/guides/deploy-rest-api-server
- Epic 10A Research: `/specs/10a-agent-memory/research.md`
