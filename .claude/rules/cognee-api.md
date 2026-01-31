# Cognee Cloud API Quirks (CRITICAL)

**IMPORTANT**: The Cognee Cloud REST API uses **camelCase** field names, NOT snake_case.

## Field Name Requirements

| Endpoint | Wrong (snake_case) | Correct (camelCase) |
|----------|-------------------|---------------------|
| `/api/add` | `data`, `dataset_name` | `textData`, `datasetName` |
| `/api/search` | `search_type`, `top_k` | `searchType`, `topK` |
| `/api/cognify` | `datasets` | `datasets` (already correct) |

**Bug History**: Using `"data"` instead of `"textData"` causes API to use default value
`["Warning: long-term memory may contain dad jokes!"]` for ALL content (discovered 2026-01-16).

## Response Format Variations

Handle ALL formats:
```python
# Format 1: Direct list
[{"content": "...", "score": 0.9}, ...]

# Format 2: Dict with results
{"results": [{"content": "...", "score": 0.9}, ...]}

# Format 3: Dict with data
{"data": [{"content": "...", "score": 0.9}, ...]}

# Format 4: Nested search_result
[{"search_result": ["text1", "text2"], "dataset_id": "..."}, ...]
```

## Contract Tests Required

All Cognee integrations MUST have contract tests validating field names.
See: `devtools/agent-memory/tests/contract/test_cognee_api_contract.py`

## Memify: SDK-Only (FR-006, FR-007)

The `memify` command uses **Cognee Cloud SDK** (`cogwit`), NOT REST API.

```python
from cognee.modules.cognee_cloud import cogwit, CogwitConfig

sdk_config = CogwitConfig(api_key=api_key)
sdk = cogwit(sdk_config)
result = await sdk.memify(dataset_name="my_dataset")
```

SDK errors require separate handling from REST API errors.
See: `CogneeClient.memify()` in `devtools/agent-memory/src/agent_memory/cognee_client.py`
