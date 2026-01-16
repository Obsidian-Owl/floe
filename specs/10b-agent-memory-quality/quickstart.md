# Quickstart: Agent Memory Validation & Quality

**Time to complete**: ~10 minutes
**Prerequisites**: Working agent-memory installation (Epic 10A)

---

## Overview

This guide walks through running the new contract tests, unit tests, and verification procedures added in Epic 10B to prevent API field name bugs like the "dad jokes" incident.

---

## 1. Prerequisites

### Working Agent Memory Installation

Epic 10B builds on Epic 10A. Ensure agent-memory is installed and working:

```bash
# From floe project root
cd devtools/agent-memory

# Verify installation
uv run agent-memory health

# Expected output:
# HealthStatus: healthy
# - Cognee Cloud: healthy
# - LLM Provider: healthy
# - Local State: healthy
```

If health check fails, see `specs/10a-agent-memory/quickstart.md` for setup instructions.

---

## 2. Running Contract Tests

Contract tests validate that CogneeClient sends correct camelCase field names to the Cognee API. They run without network access.

### Run All Contract Tests

```bash
cd devtools/agent-memory

# Run contract tests only
uv run pytest tests/contract/ -v

# Expected: All tests pass in < 5 seconds
# test_add_content_uses_textData_field PASSED
# test_add_content_uses_datasetName_field PASSED
# test_search_uses_searchType_field PASSED
# test_search_uses_topK_field PASSED
# test_cognify_uses_datasets_field PASSED
```

### Run Single Contract Test

```bash
# Test specific field
uv run pytest tests/contract/test_cognee_api_contract.py::test_add_content_uses_textData_field -v
```

### What Contract Tests Verify

| Test | What It Checks | Bug It Prevents |
|------|---------------|-----------------|
| `test_add_content_uses_textData_field` | `textData` not `data` | "dad jokes" bug |
| `test_add_content_uses_datasetName_field` | `datasetName` not `dataset_name` | Silent failures |
| `test_search_uses_searchType_field` | `searchType` not `search_type` | Wrong search type |
| `test_search_uses_topK_field` | `topK` not `top_k` | Wrong result count |
| `test_cognify_uses_datasets_field` | `datasets` format correct | Cognify failures |

---

## 3. Running Unit Tests

Unit tests verify CogneeClient logic without requiring Cognee Cloud access.

### Run All Unit Tests

```bash
cd devtools/agent-memory

# Run unit tests with coverage
uv run pytest tests/unit/ -v --cov=agent_memory.cognee_client --cov-report=term-missing

# Expected: 80%+ coverage (SC-002)
```

### Response Parsing Tests

Unit tests cover all response format variations:

```bash
# Test specific response parsing
uv run pytest tests/unit/test_cognee_client.py -k "response" -v

# Tests cover:
# - test_parse_response_direct_list
# - test_parse_response_dict_with_results
# - test_parse_response_dict_with_data
# - test_parse_response_nested_search_result
# - test_parse_response_empty
```

---

## 4. Running Integration Tests

Integration tests verify content searchability against real Cognee Cloud.

### Prerequisites

```bash
# Ensure environment variables are set
echo $COGNEE_API_KEY | head -c 10
echo $OPENAI_API_KEY | head -c 10
```

### Run Integration Tests

```bash
cd devtools/agent-memory

# Run integration tests (requires Cognee Cloud access)
uv run pytest tests/integration/ -v

# Expected: All tests pass
# test_sync_and_search_returns_actual_content PASSED
# test_dataset_isolation_prevents_cross_pollution PASSED
```

### What Integration Tests Verify

| Test | What It Checks |
|------|---------------|
| Content searchability | Search returns actual indexed content, not defaults |
| Dataset isolation | Test datasets don't affect production data |
| Cleanup | Test datasets are removed after tests |

---

## 5. Verify Bug Fix

Verify the "dad jokes" bug fix by resetting and re-syncing.

### Step 1: Reset (if needed)

```bash
# From project root
cd /path/to/floe

# Reset Cognee Cloud data (DESTRUCTIVE)
uv run agent-memory reset --confirm

# Clear local checksums
rm -f .cognee/checksums.json
```

### Step 2: Re-sync Content

```bash
# Sync architecture docs
uv run agent-memory sync --all --dataset floe

# Wait for cognify to complete
uv run agent-memory status --wait
```

### Step 3: Verify No "Dad Jokes"

```bash
# Search for floe content
uv run agent-memory search "What is floe?" --dataset floe

# EXPECTED: Results about the floe platform
# ✅ "floe is an open platform for building internal data platforms"
# ✅ "Plugin-based architecture with 11 plugin types"

# BAD (bug still present):
# ❌ "Warning: long-term memory may contain dad jokes!"
```

---

## 6. Using --verify Flag

The new `--verify` flag provides read-after-write verification.

### CLI Usage

```bash
# Sync with verification (slower but safer)
uv run agent-memory sync --file docs/architecture/adr/0001-plugin-registry.md --verify

# Sync all with verification
uv run agent-memory sync --all --dataset floe --verify
```

### What --verify Does

1. Adds content via `POST /api/v1/add`
2. Lists datasets to confirm dataset was created
3. Fails if dataset doesn't appear (catches indexing failures)

---

## 7. Status Polling

The `cognify()` method now waits for completion by default.

### CLI Usage

```bash
# Cognify with status polling (default)
uv run agent-memory cognify --dataset floe

# Cognify without waiting (background)
uv run agent-memory cognify --dataset floe --no-wait

# Check status manually
uv run agent-memory status --dataset floe
```

### Status Values

| Status | Meaning |
|--------|---------|
| `INITIATED` | Queued for processing |
| `STARTED` | Currently processing |
| `COMPLETED` | Successfully finished |
| `ERRORED` | Processing failed |

---

## 8. Full Test Suite

Run all tests (contract + unit + integration):

```bash
cd devtools/agent-memory

# Full test suite
uv run pytest tests/ -v

# With coverage report
uv run pytest tests/ -v --cov=agent_memory --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Expected Results

| Test Category | Expected Time | Expected Result |
|---------------|---------------|-----------------|
| Contract tests | < 5 seconds | All pass |
| Unit tests | < 30 seconds | 80%+ coverage |
| Integration tests | < 5 minutes | All pass |

---

## 9. CI Integration

Contract and unit tests run automatically on every PR.

### GitHub Actions

```yaml
# Runs automatically via .github/workflows/agent-memory.yml
- name: Run contract tests
  run: |
    cd devtools/agent-memory
    uv run pytest tests/contract/ -v

- name: Run unit tests
  run: |
    cd devtools/agent-memory
    uv run pytest tests/unit/ -v --cov=agent_memory
```

### Local Pre-commit Check

```bash
# Run before committing changes to CogneeClient
cd devtools/agent-memory
uv run pytest tests/contract/ tests/unit/ -v

# Should complete in < 35 seconds
```

---

## 10. Troubleshooting

### Contract Test Fails

```bash
# If test_add_content_uses_textData_field fails:
# Check cognee_client.py around line 408

# The payload should look like:
# json_data = {
#     "textData": content_list,     # camelCase (CORRECT)
#     "datasetName": dataset_name,  # camelCase (CORRECT)
# }

# NOT:
# json_data = {
#     "data": content_list,         # snake_case (BUG!)
#     "dataset_name": dataset_name, # snake_case (BUG!)
# }
```

### Unit Test Coverage < 80%

```bash
# Find uncovered lines
uv run pytest tests/unit/ --cov=agent_memory.cognee_client --cov-report=term-missing

# Add tests for uncovered paths
# Common gaps:
# - Error handling paths
# - Response parsing edge cases
# - Timeout handling
```

### Integration Test Flaky

```bash
# If tests pass sometimes, fail other times:
# 1. Check if cognify completed before search
uv run agent-memory status --dataset test_*

# 2. Increase timeout
# In tests/integration/conftest.py:
# COGNIFY_TIMEOUT = 600  # 10 minutes instead of 5

# 3. Check for test dataset pollution
uv run agent-memory list | grep test_
```

### "Dad Jokes" Still Appearing

```bash
# If search still returns default values:

# 1. Verify code fix is applied
grep -n "textData" devtools/agent-memory/src/agent_memory/cognee_client.py
# Should show: "textData": content_list

# 2. Full reset and re-sync
uv run agent-memory reset --confirm
rm -f .cognee/checksums.json
uv run agent-memory sync --all --dataset floe
uv run agent-memory status --wait

# 3. Verify with fresh search
uv run agent-memory search "What is floe?"
```

---

## 11. Next Steps

1. **Review contract tests**: `tests/contract/test_cognee_api_contract.py`
2. **Review unit tests**: `tests/unit/test_cognee_client.py`
3. **Read the API contract**: `specs/10b-agent-memory-quality/contracts/cognee-rest-api.md`
4. **Check CLAUDE.md**: API quirks documented in project root
