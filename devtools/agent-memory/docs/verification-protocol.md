# Agent Memory Verification Protocol

**Purpose**: Verify content integrity after sync operations with Cognee Cloud API.
**Epic**: 10B (Agent Memory Validation & Quality)
**Requirements**: FR-019 (Verification Protocol), FR-010 (Verify Flag)

---

## Overview

This protocol ensures that content synced to Cognee Cloud is:
1. **Correctly stored** (using camelCase field names)
2. **Searchable** (appears in search results after cognify)
3. **Isolated** (datasets don't cross-contaminate)

---

## Quick Start

```bash
# Basic verification (after initial sync)
cd devtools/agent-memory
agent-memory sync --all --verify

# Full verification protocol
agent-memory reset --confirm
agent-memory sync --all --verify
agent-memory cognify --wait
agent-memory search "unique test phrase"
```

---

## 1. Reset Procedure (T042)

**When to use**: Before running verification or after suspected data corruption.

### Full Reset

```bash
# Clear all datasets from Cognee Cloud
agent-memory reset --confirm

# Verify reset succeeded
agent-memory status
# Expected: No datasets found
```

### Dataset-Specific Reset

```bash
# Clear only a specific dataset
agent-memory reset --dataset floe --confirm
```

### Post-Reset Verification

After reset, verify the state is clean:

```bash
agent-memory search "any content"
# Expected: No results (empty)
```

---

## 2. Re-Sync Procedure with --verify Flag (T043)

The `--verify` flag enables read-after-write verification for each file synced.

### How --verify Works

1. Content is added via `/api/add` endpoint
2. Search is issued to find the content
3. If content not found within timeout, `VerificationError` is raised

### Sync with Verification

```bash
# Sync all markdown files with verification
agent-memory sync --all --verify

# Sync specific files with verification
agent-memory sync --paths docs/architecture/ARCHITECTURE-SUMMARY.md --verify

# Verbose output to see verification status
agent-memory sync --all --verify --verbose
```

### Expected Output

```
Syncing 42 files to dataset: floe
  [1/42] docs/architecture/ARCHITECTURE-SUMMARY.md ... verified
  [2/42] docs/guides/getting-started.md ... verified
  ...
Sync completed: 42 files synced, 42 verified
```

### Handling Verification Failures

If verification fails:

```
VerificationError: Content not found in search after 30s timeout
  File: docs/architecture/ARCHITECTURE-SUMMARY.md
  Dataset: floe

Troubleshooting:
1. Check API field names (use camelCase: textData, datasetName)
2. Ensure cognify was run on the dataset
3. Wait for indexing (Cognee Cloud may have processing delay)
4. Re-run: agent-memory sync --paths <file> --verify
```

---

## 3. Search Validation Criteria (T044)

### What Constitutes Valid Search Results

A search result is valid if:

| Criterion | Check | Pass Condition |
|-----------|-------|----------------|
| **Presence** | Content appears in results | At least 1 matching result |
| **Relevance** | Correct file is returned | Source metadata matches expected file |
| **No Corruption** | Content is not "dad jokes" default | Result does NOT contain "Warning: long-term memory may contain dad jokes" |
| **Dataset Scoping** | Results from correct dataset | `dataset_id` matches requested dataset |

### Search Validation Commands

```bash
# Basic search
agent-memory search "architecture four layer model"

# Dataset-scoped search
agent-memory search "plugin interface" --dataset floe

# Verbose search (shows full result details)
agent-memory search "CompiledArtifacts" --verbose
```

### Detecting the "Dad Jokes" Bug

The Cognee API uses default content if field names are wrong:

```bash
agent-memory search "anything"
# BAD: Returns "Warning: long-term memory may contain dad jokes!"
# GOOD: Returns actual content from synced files
```

If you see the "dad jokes" message:
1. Check `cognee_client.py` uses `textData` not `data`
2. Check contract tests pass: `pytest tests/contract/`
3. Reset and re-sync: `agent-memory reset --confirm && agent-memory sync --all --verify`

---

## 4. Full Verification Protocol Execution (T045)

### Pre-Requisites

- Cognee Cloud API key configured (`COGNEE_API_KEY` env var)
- agent-memory CLI installed (`uv pip install -e devtools/agent-memory`)

### Step-by-Step Protocol

#### Phase 1: Clean State

```bash
# 1. Reset to clean state
agent-memory reset --confirm
echo "Reset complete: $(date)"

# 2. Verify clean state
result=$(agent-memory search "test query" 2>&1)
if [[ "$result" == *"No results"* ]]; then
    echo "PASS: Clean state verified"
else
    echo "FAIL: Unexpected content found after reset"
    exit 1
fi
```

#### Phase 2: Sync with Verification

```bash
# 3. Sync content with verification
agent-memory sync --all --verify
echo "Sync complete: $(date)"

# 4. Run cognify to build knowledge graph
agent-memory cognify --wait --timeout 300
echo "Cognify complete: $(date)"
```

#### Phase 3: Search Validation

```bash
# 5. Search for known content
result=$(agent-memory search "floe four layer architecture")

# 6. Validate result is NOT the "dad jokes" default
if [[ "$result" == *"dad jokes"* ]]; then
    echo "FAIL: Dad jokes bug detected!"
    exit 1
fi

# 7. Validate result contains expected content
if [[ "$result" == *"Layer 1: FOUNDATION"* ]]; then
    echo "PASS: Content verified"
else
    echo "WARN: Expected content not found in search results"
fi
```

#### Phase 4: Dataset Isolation

```bash
# 8. Create content in test dataset
agent-memory sync --paths test-file.md --dataset test_isolation

# 9. Search in different dataset - should NOT find it
result=$(agent-memory search "test isolation content" --dataset floe)
if [[ "$result" == *"test-file.md"* ]]; then
    echo "FAIL: Dataset isolation broken!"
    exit 1
else
    echo "PASS: Dataset isolation verified"
fi
```

### Verification Report Template

```markdown
# Agent Memory Verification Report

**Date**: YYYY-MM-DD
**Operator**: [Name]
**Epic**: 10B

## Results

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Clean State | PASS/FAIL | |
| 2. Sync with Verify | PASS/FAIL | X files synced, Y verified |
| 3. Search Validation | PASS/FAIL | |
| 4. Dataset Isolation | PASS/FAIL | |

## Issues Found

[Document any issues here]

## Sign-off

- [ ] All phases passed
- [ ] No "dad jokes" bug detected
- [ ] Contract tests pass
```

---

## Troubleshooting

### Issue: Verification Times Out

```
VerificationError: Content not found in search after 30s timeout
```

**Causes**:
1. Cognify not run (knowledge graph not built)
2. API processing delay
3. Wrong field names in API payload

**Solutions**:
```bash
# Run cognify first
agent-memory cognify --wait

# Increase timeout
agent-memory sync --all --verify --timeout 60

# Check contract tests
pytest tests/contract/
```

### Issue: Dad Jokes Content

**Cause**: API payload using `data` instead of `textData`

**Solution**:
```bash
# 1. Verify contract tests pass
pytest tests/contract/test_cognee_api_contract.py -v

# 2. Reset and re-sync
agent-memory reset --confirm
agent-memory sync --all --verify
```

### Issue: Dataset Cross-Contamination

**Cause**: Search not scoped to dataset

**Solution**: Always use `--dataset` flag:
```bash
agent-memory search "query" --dataset floe
```

---

## Related Documentation

- [CLAUDE.md](../../../CLAUDE.md) - Cognee Cloud API Quirks section
- [Epic 10B Spec](../../../specs/10b-agent-memory-quality/spec.md) - Requirements
- [Contract Tests](../tests/contract/) - API field validation
