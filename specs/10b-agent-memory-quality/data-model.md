# Data Model: Agent Memory Validation & Quality

**Feature**: Epic 10B - Agent Memory Validation & Quality
**Date**: 2026-01-16
**Status**: Design Complete

---

## Overview

This document defines the data entities for API contract validation and testing quality improvements. Entities are organized into three categories:
1. **API Contract Schemas** - Expected Cognee REST API payload structures
2. **Test Entities** - Models for test fixtures and verification
3. **Extended Operations** - New fields for existing models (verify, status polling)

All entities use Pydantic v2 models with `ConfigDict(frozen=True, extra="forbid")` for immutability and strict validation.

---

## Entity Definitions

### 1. API Contract Schemas

These models represent the **expected** payload structure for Cognee REST API calls. They are used in contract tests to validate that CogneeClient sends correct field names.

#### AddContentPayload

**Purpose**: Expected payload for `POST /api/v1/add`.

```python
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class AddContentPayload(BaseModel):
    """Expected payload for Cognee add_content API.

    CRITICAL: All fields use camelCase to match Cognee REST API.
    Using snake_case triggers API default values (the 'dad jokes' bug).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    textData: list[str] = Field(
        ...,
        alias="textData",
        description="List of text content to add (camelCase REQUIRED)"
    )
    datasetName: str | None = Field(
        default=None,
        alias="datasetName",
        description="Target dataset name (camelCase REQUIRED)"
    )
    datasetId: UUID | None = Field(
        default=None,
        alias="datasetId",
        description="Target dataset UUID (camelCase REQUIRED)"
    )
    nodeSet: list[str] | None = Field(
        default=None,
        alias="nodeSet",
        description="Node set labels (camelCase REQUIRED)"
    )
```

**Validation Rules**:
- `textData` MUST be present (not `data`)
- `datasetName` MUST use camelCase (not `dataset_name`)
- All field names MUST match OpenAPI spec exactly

**Contract Test Pattern**:
```python
def test_add_content_payload_uses_camelCase():
    """Verify payload uses camelCase field names."""
    payload = capture_request_payload()
    assert "textData" in payload
    assert "data" not in payload  # Bug regression check
```

---

#### SearchPayload

**Purpose**: Expected payload for `POST /api/v1/search`.

```python
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Literal

SearchType = Literal[
    "SUMMARIES",
    "CHUNKS",
    "RAG_COMPLETION",
    "GRAPH_COMPLETION",
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

class SearchPayload(BaseModel):
    """Expected payload for Cognee search API.

    CRITICAL: Field names use camelCase (searchType, topK).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search query string"
    )
    searchType: SearchType = Field(
        default="GRAPH_COMPLETION",
        alias="searchType",
        description="Type of search (camelCase REQUIRED, not search_type)"
    )
    topK: int = Field(
        default=10,
        alias="topK",
        ge=1,
        le=100,
        description="Number of results (camelCase REQUIRED, not top_k)"
    )
    datasets: list[str] | None = Field(
        default=None,
        description="Dataset names to search"
    )
    datasetIds: list[UUID] | None = Field(
        default=None,
        alias="datasetIds",
        description="Dataset UUIDs to search"
    )
    systemPrompt: str | None = Field(
        default=None,
        alias="systemPrompt",
        description="Custom system prompt"
    )
    nodeName: list[str] | None = Field(
        default=None,
        alias="nodeName",
        description="Node names to filter"
    )
    onlyContext: bool = Field(
        default=False,
        alias="onlyContext",
        description="Return only context, no completion"
    )
    useCombinedContext: bool = Field(
        default=False,
        alias="useCombinedContext",
        description="Use combined context mode"
    )
```

**Validation Rules**:
- `searchType` MUST use camelCase (not `search_type`)
- `topK` MUST use camelCase (not `top_k`)

---

#### CognifyPayload

**Purpose**: Expected payload for `POST /api/v1/cognify`.

```python
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class CognifyPayload(BaseModel):
    """Expected payload for Cognee cognify API."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    datasets: list[str] | None = Field(
        default=None,
        description="Dataset names to cognify"
    )
    dataset_ids: list[UUID] | None = Field(
        default=None,
        description="Dataset UUIDs to cognify"
    )
    run_in_background: bool | None = Field(
        default=None,
        description="Run cognify in background"
    )
```

**Note**: The `datasets` field already uses correct naming.

---

#### DatasetStatusResponse

**Purpose**: Expected response from `GET /api/v1/datasets/status`.

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from uuid import UUID

DatasetProcessingStatus = Literal[
    "DATASET_PROCESSING_INITIATED",
    "DATASET_PROCESSING_STARTED",
    "DATASET_PROCESSING_COMPLETED",
    "DATASET_PROCESSING_ERRORED",
]

class DatasetStatusResponse(BaseModel):
    """Response from dataset status endpoint.

    The response is a dict mapping dataset UUIDs to their status.
    """
    model_config = ConfigDict(frozen=True, extra="allow")  # Allow dynamic keys

    # Response format: {dataset_uuid: status_string}
    # Example: {"123e4567-...": "DATASET_PROCESSING_COMPLETED"}
```

**Status Transitions**:
```
INITIATED → STARTED → COMPLETED
                    → ERRORED
```

---

### 2. Test Entities

#### ContractTestResult

**Purpose**: Result of a contract test validation.

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class ContractTestResult(BaseModel):
    """Result of validating an API payload against contract."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    test_name: str = Field(
        ...,
        description="Contract test identifier"
    )
    endpoint: str = Field(
        ...,
        description="API endpoint being tested"
    )
    passed: bool = Field(
        ...,
        description="Whether contract was satisfied"
    )
    expected_fields: list[str] = Field(
        default_factory=list,
        description="Fields that should be present"
    )
    actual_fields: list[str] = Field(
        default_factory=list,
        description="Fields actually sent"
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Expected fields not found"
    )
    extra_fields: list[str] = Field(
        default_factory=list,
        description="Unexpected fields found"
    )
    violations: list[str] = Field(
        default_factory=list,
        description="Contract violation messages"
    )
    captured_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Actual JSON payload captured"
    )
```

**Usage in Tests**:
```python
@pytest.mark.requirement("10B-FR-001")
def test_add_content_contract():
    result = validate_contract(AddContentPayload, captured_payload)
    assert result.passed, f"Contract violations: {result.violations}"
```

---

#### TestDatasetFixture

**Purpose**: Fixture for isolated test datasets.

```python
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID, uuid4

class TestDatasetFixture(BaseModel):
    """Isolated test dataset with unique identifier.

    Used to prevent cross-test pollution in integration tests.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str = Field(
        ...,
        description="Unique dataset name (prefixed with test_)"
    )
    unique_content: str = Field(
        ...,
        description="Unique searchable content for verification"
    )
    test_id: UUID = Field(
        default_factory=uuid4,
        description="Unique test run identifier"
    )

    @classmethod
    def create(cls, prefix: str = "test") -> "TestDatasetFixture":
        """Create fixture with unique values."""
        test_id = uuid4()
        return cls(
            dataset_name=f"{prefix}_{test_id.hex[:8]}",
            unique_content=f"UNIQUE_MARKER_{test_id.hex}",
            test_id=test_id,
        )
```

**Usage in Integration Tests**:
```python
@pytest.fixture
def test_dataset():
    """Create isolated test dataset."""
    fixture = TestDatasetFixture.create("integration")
    yield fixture
    # Cleanup in teardown
    await client.delete_dataset(fixture.dataset_name)
```

---

#### VerificationResult

**Purpose**: Result of read-after-write verification.

```python
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

class VerificationResult(BaseModel):
    """Result of verify=True verification."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    verified: bool = Field(
        ...,
        description="Whether content was verified in dataset"
    )
    dataset_name: str = Field(
        ...,
        description="Dataset that was checked"
    )
    dataset_exists: bool = Field(
        ...,
        description="Whether dataset exists after add"
    )
    content_searchable: bool = Field(
        default=False,
        description="Whether content is retrievable"
    )
    verification_time_ms: int = Field(
        default=0,
        ge=0,
        description="Time spent verifying"
    )
    checked_at: datetime = Field(
        ...,
        description="When verification ran"
    )
    error_message: str | None = Field(
        default=None,
        description="Error if verification failed"
    )
```

---

### 3. Extended Operations Models

#### Extended CogneeClient Methods

These are not new models but document new parameters for existing methods.

**add_content() Extension**:
```python
async def add_content(
    self,
    content: str | list[str],
    dataset_name: str,
    *,
    verify: bool = False,  # NEW: Read-after-write verification
    verify_timeout: float = 30.0,  # NEW: Verification timeout (30 seconds)
    metadata: dict[str, Any] | None = None,
) -> None:
    """Add content with optional verification.

    Args:
        verify: If True, confirms content exists in dataset before returning.
                Uses list_datasets() to verify dataset was created.
        verify_timeout: Maximum time to wait for verification (default 30 seconds).
    """
```

**cognify() Extension**:
```python
async def cognify(
    self,
    dataset_name: str | None = None,
    *,
    wait_for_completion: bool = True,  # NEW: Status polling
    timeout_seconds: float = 300.0,     # NEW: Polling timeout (5 minutes per FR-013)
) -> None:
    """Process content with optional completion waiting.

    Args:
        wait_for_completion: If True, polls status until processing completes.
        timeout_seconds: Maximum time to wait for completion (default 300 seconds = 5 minutes).
    """
```

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Contract Schemas                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AddContentPayload ─────► textData (camelCase)                  │
│         │                 datasetName (camelCase)               │
│         │                                                        │
│  SearchPayload ─────────► searchType (camelCase)                │
│         │                 topK (camelCase)                       │
│         │                                                        │
│  CognifyPayload ────────► datasets                              │
│         │                                                        │
│  DatasetStatusResponse ─► {uuid: status} mapping                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Test Entities                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ContractTestResult ────► passed, violations, captured_payload  │
│         │                                                        │
│         ▼                                                        │
│  TestDatasetFixture ────► unique dataset_name, unique_content   │
│         │                                                        │
│         ▼                                                        │
│  VerificationResult ────► verified, dataset_exists              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Extended Operations                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  add_content(verify=True) ──► VerificationResult                │
│                                                                  │
│  cognify(wait_for_completion=True) ──► DatasetStatusResponse    │
│                                                                  │
│  CLI: sync --verify ────────► VerificationResult per file       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Field Name Reference

**CRITICAL**: This table is the authoritative reference for API field names.

| Endpoint | Correct (camelCase) | Wrong (snake_case) | Default if Missing |
|----------|---------------------|--------------------|--------------------|
| `/api/v1/add` | `textData` | `data` | `["dad jokes!"]` |
| `/api/v1/add` | `datasetName` | `dataset_name` | None |
| `/api/v1/add` | `datasetId` | `dataset_id` | None |
| `/api/v1/add` | `nodeSet` | `node_set` | None |
| `/api/v1/search` | `searchType` | `search_type` | `GRAPH_COMPLETION` |
| `/api/v1/search` | `topK` | `top_k` | `10` |
| `/api/v1/search` | `datasetIds` | `dataset_ids` | None |
| `/api/v1/search` | `systemPrompt` | `system_prompt` | None |
| `/api/v1/search` | `nodeName` | `node_name` | None |
| `/api/v1/search` | `onlyContext` | `only_context` | `false` |
| `/api/v1/search` | `useCombinedContext` | `use_combined_context` | `false` |

---

## Storage Locations

| Entity | Storage | Format |
|--------|---------|--------|
| `AddContentPayload` | Contract test assertions | Captured JSON |
| `SearchPayload` | Contract test assertions | Captured JSON |
| `ContractTestResult` | Test output | pytest assertions |
| `TestDatasetFixture` | Test fixtures | In-memory |
| `VerificationResult` | CLI output / logs | Structured log |
| `DatasetStatusResponse` | API response | JSON dict |

---

## Response Format Variations

The CogneeClient must handle multiple response formats. Unit tests must cover all paths.

```python
# Format 1: Direct list (most common)
[{"content": "...", "score": 0.9}, ...]

# Format 2: Dict with 'results' key
{"results": [{"content": "...", "score": 0.9}, ...]}

# Format 3: Dict with 'data' key
{"data": [{"content": "...", "score": 0.9}, ...]}

# Format 4: Nested search_result (GRAPH_COMPLETION)
[{"search_result": ["text1", "text2"], "dataset_id": "..."}, ...]

# Format 5: Empty results
[] or {} or {"results": []}
```

**Unit Test Coverage Required**:
- `test_parse_response_direct_list()`
- `test_parse_response_dict_with_results()`
- `test_parse_response_dict_with_data()`
- `test_parse_response_nested_search_result()`
- `test_parse_response_empty()`
