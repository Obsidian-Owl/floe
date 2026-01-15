# Epic 10B: Agent Memory Validation & Quality

> **Purpose**: Address the quality issues discovered in Epic 10A. Validate API contracts,
> improve test coverage, and establish regression prevention.
>
> **Context**: A critical bug was discovered where the wrong API field name (`"data"` vs `"textData"`)
> caused all synced content to be replaced with Cognee's default value ("dad jokes"). This epic
> ensures such bugs are caught by testing in the future.

## Summary

This Epic addresses the testing gaps that allowed a critical API contract bug to reach production
in Epic 10A. The bug caused all content to be replaced with default values because integration
tests checked "does it return results?" rather than "does it return the correct results?".

**Root Cause**: The Cognee Cloud API uses camelCase field names (`textData`, `searchType`, `topK`)
but our implementation used snake_case (`data`, `search_type`, `top_k`). Since `textData` was never
sent, the API used its default value for every document we synced.

**Solution**: Add contract tests that validate exact field names, unit tests that verify payload
construction, and integration tests that verify content searchability.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: TBD (to be created via /speckit.taskstolinear)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| 10B-FR-001 | Contract tests for all Cognee API endpoints | CRITICAL |
| 10B-FR-002 | CogneeClient unit tests with payload validation | CRITICAL |
| 10B-FR-003 | Integration tests verify content searchability | HIGH |
| 10B-FR-004 | Verify fix: reset + re-sync + search validation | HIGH |
| 10B-FR-005 | Document Cognee API quirks in CLAUDE.md | MEDIUM |
| 10B-FR-006 | Pin Cognee SDK versions in pyproject.toml | MEDIUM |
| 10B-FR-007 | Add CI check for API contract stability | LOW |
| 10B-FR-008 | Self-hosted Cognee documentation (optional fallback) | DEFERRED |

---

## Architecture References

### ADRs
- [ADR-0046](../../../architecture/adr/0046-agent-memory-architecture.md) - Agent Memory Architecture
- Related: Epic 10A implementation

### Bug Analysis
- **Commit with bug**: f23f392 (EP10A merge)
- **Field name issue**: `"data"` sent instead of `"textData"` to `/api/add`
- **API default triggered**: `["Warning: long-term memory may contain dad jokes!"]`
- **Bug fix commits**: See current branch `10b-agent-memory-test-isolation`

### Infrastructure Decision

**Decision**: Stay with Cognee Cloud (SaaS)

**Rationale**:
1. Self-hosted Cognee uses the **same REST API** - switching doesn't fix contract issues
2. Self-hosted adds PostgreSQL maintenance burden (~$30/month + ops time)
3. Alternatives (Neo4j, LlamaIndex) require 40-70% rewrite and lose graph relationships
4. **The fix is testing, not deployment model**

**Fallback**: If Cognee Cloud stability degrades significantly, self-hosted is a 2-3 day migration.

---

## File Ownership (Exclusive)

```text
devtools/agent-memory/
├── tests/
│   ├── contract/                          # NEW: API contract tests
│   │   ├── conftest.py
│   │   └── test_cognee_api_contract.py    # Validates field names
│   ├── unit/
│   │   └── test_cognee_client.py          # NEW: CogneeClient unit tests
│   └── integration/
│       └── test_sync_cycle.py             # UPDATE: Content validation
├── src/agent_memory/
│   ├── cognee_client.py                   # FIXED: Field names (10A bug)
│   └── config.py                          # FIXED: API version default
└── pyproject.toml                         # UPDATE: Pin SDK versions

CLAUDE.md                                  # UPDATE: Add Cognee API quirks section
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | 10A | Builds on existing implementation |
| Blocks | None | Quality improvement, non-blocking |

---

## User Stories (for SpecKit)

### US1: Contract Test Coverage (P0)
**As a** developer
**I want** contract tests that validate API field names
**So that** field name mismatches are caught before merge

**Acceptance Criteria**:
- [ ] Contract test for `add_content()` validates `textData` field
- [ ] Contract test for `search()` validates `searchType`, `topK` fields
- [ ] Contract test for `cognify()` validates `datasets` field
- [ ] Tests run in CI on every PR
- [ ] Tests fail fast with clear error messages

**Implementation Notes**:
```python
# tests/contract/test_cognee_api_contract.py
@pytest.mark.requirement("10B-FR-001")
async def test_add_content_uses_textData_field():
    """Verify add_content sends 'textData', not 'data'."""
    with patch.object(client, '_make_request') as mock:
        mock.return_value = AsyncMock(status_code=200, json=lambda: {})
        await client.add_content("test", "dataset")

        json_data = mock.call_args.kwargs['json_data']
        assert 'textData' in json_data
        assert json_data['textData'] == ['test']
        assert 'data' not in json_data, "Bug regression: sent 'data' instead of 'textData'"
```

### US2: CogneeClient Unit Tests (P0)
**As a** developer
**I want** unit tests for CogneeClient methods
**So that** payload construction bugs are caught without integration tests

**Acceptance Criteria**:
- [ ] `test_cognee_client.py` exists with 80%+ coverage
- [ ] Tests mock at httpx level, not client level
- [ ] Tests verify exact JSON payload structure
- [ ] Tests cover all response parsing paths (list, dict with results, dict with data)

**Implementation Notes**:
- Mock `_make_request()` to inspect `json_data` argument
- Test all defensive parsing paths in `search()` response handling
- Test error handling paths

### US3: Fix Verification (P0)
**As a** developer
**I want** to verify the API fixes work
**So that** the "dad jokes" contamination is eliminated

**Acceptance Criteria**:
- [ ] Reset Cognee Cloud data (`agent-memory reset --confirm`)
- [ ] Re-sync all content with fixed code (`agent-memory sync --all`)
- [ ] Search returns actual floe content (not "dad jokes")
- [ ] Integration tests pass with content validation

**Verification Steps**:
```bash
# 1. Reset contaminated data
uv run agent-memory reset --confirm

# 2. Clear checksums and re-sync
rm -f .cognee/checksums.json
uv run agent-memory sync --all --dataset floe

# 3. Verify no "dad jokes" contamination
uv run agent-memory search 'What is floe?' --dataset floe
# Expected: Results about floe platform, NOT "dad jokes"
```

### US4: API Quirks Documentation (P1)
**As a** future developer
**I want** Cognee API quirks documented
**So that** I don't repeat the same mistakes

**Acceptance Criteria**:
- [ ] CLAUDE.md documents camelCase requirement for Cognee API
- [ ] CLAUDE.md documents response format variations
- [ ] CLAUDE.md documents defensive parsing patterns

---

## Technical Notes

### Cognee API Field Names (camelCase)

| Endpoint | Field | Wrong (snake_case) | Correct (camelCase) |
|----------|-------|-------------------|---------------------|
| `/api/add` | content | `data` | `textData` |
| `/api/add` | dataset | `dataset_name` | `datasetName` |
| `/api/search` | type | `search_type` | `searchType` |
| `/api/search` | limit | `top_k` | `topK` |
| `/api/cognify` | datasets | `datasets` | `datasets` (OK) |

### Response Format Variations

The Cognee API returns different formats depending on endpoint and version:
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

**Implementation must handle all formats defensively.**

### Test Strategy

| Test Type | What to Mock | What to Validate |
|-----------|--------------|------------------|
| **Contract** | `_make_request()` | `json_data` argument field names |
| **Unit** | httpx requests | Payload structure, response parsing |
| **Integration** | Nothing (real API) | Content searchability, not just count |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cognee API changes again | MEDIUM | MEDIUM | Contract tests catch early |
| Self-hosted needed later | LOW | MEDIUM | Document fallback option |
| Integration tests flaky | MEDIUM | LOW | Use unique datasets per test |
| Cognify timeout during sync | MEDIUM | LOW | Increase timeout, retry logic |

---

## Test Strategy

- **Contract Tests** (`tests/contract/`):
  - Mock `_make_request()`, validate `json_data` argument
  - Zero network calls, fast execution
  - Run on every PR

- **Unit Tests** (`tests/unit/test_cognee_client.py`):
  - Mock httpx at request level
  - Test all response parsing paths
  - Test error handling
  - 80%+ coverage target

- **Integration Tests** (`tests/integration/test_sync_cycle.py`):
  - Real Cognee Cloud API
  - Test dataset with unique content
  - Validate content appears in search results (not just count > 0)

- **E2E Verification**:
  - Full reset → sync → search cycle
  - Manual verification that "dad jokes" is eliminated

---

## SpecKit Context

### Relevant Codebase Paths
- `devtools/agent-memory/src/agent_memory/cognee_client.py` - Fixed API calls
- `devtools/agent-memory/tests/` - Test directory structure
- `CLAUDE.md` - Project documentation (add API quirks section)

### Related Existing Code
- `devtools/agent-memory/tests/integration/test_sync_cycle.py` - Update with content validation
- `devtools/agent-memory/tests/unit/test_cli_*.py` - Existing unit test patterns

### External Dependencies
- `cognee` (PyPI) - Pin version to prevent breaking changes
- `cogwit-sdk` (PyPI) - Pin version for memify support
- Cognee Cloud (SaaS) - https://cognee.ai
