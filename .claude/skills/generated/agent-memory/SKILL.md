---
name: agent-memory
description: "Skill for the Agent_memory area of floe. 108 symbols across 11 files."
---

# Agent_memory

108 symbols | 11 files | Cohesion: 81%

## When to Use

- Working with code in `devtools/`
- Understanding how can_execute, record_success, record_failure work
- Modifying agent_memory-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `devtools/agent-memory/src/agent_memory/cli.py` | _collect_files_from_source, _compute_file_checksum, _index_content, _sync_python_files, _codify_content (+33) |
| `devtools/agent-memory/src/agent_memory/cognee_client.py` | CogneeClientError, CogneeAuthenticationError, CogneeConnectionError, VerificationError, CognifyTimeoutError (+20) |
| `devtools/agent-memory/src/agent_memory/resilience.py` | can_execute, record_success, record_failure, calculate_backoff, parse_retry_after (+4) |
| `devtools/agent-memory/src/agent_memory/session.py` | retrieve_session_context, DecisionRecord, SessionContext, capture_session_context, save_session_context (+2) |
| `devtools/agent-memory/src/agent_memory/git_diff.py` | GitError, _validate_git_ref, get_repo_root, get_changed_files, get_staged_files (+2) |
| `devtools/agent-memory/src/agent_memory/markdown_parser.py` | ParsedContent, _extract_frontmatter, _extract_title, _extract_headers, parse_markdown_file (+1) |
| `devtools/agent-memory/src/agent_memory/docstring_extractor.py` | DocstringEntry, _parse_google_style_sections, _get_function_signature, _get_base_names, _get_method_names (+1) |
| `devtools/agent-memory/src/agent_memory/models.py` | SearchResultItem, SearchResult, ComponentStatus, HealthStatus |
| `devtools/agent-memory/src/agent_memory/config.py` | AgentMemoryConfig, load_yaml_config, get_config, get_llm_api_key |
| `devtools/agent-memory/scripts/cleanup_test_datasets.py` | main |

## Entry Points

Start here when exploring this area:

- **`can_execute`** (Function) — `devtools/agent-memory/src/agent_memory/resilience.py:122`
- **`record_success`** (Function) — `devtools/agent-memory/src/agent_memory/resilience.py:144`
- **`record_failure`** (Function) — `devtools/agent-memory/src/agent_memory/resilience.py:158`
- **`calculate_backoff`** (Function) — `devtools/agent-memory/src/agent_memory/resilience.py:180`
- **`parse_retry_after`** (Function) — `devtools/agent-memory/src/agent_memory/resilience.py:219`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SearchResultItem` | Class | `devtools/agent-memory/src/agent_memory/models.py` | 152 |
| `SearchResult` | Class | `devtools/agent-memory/src/agent_memory/models.py` | 181 |
| `CogneeClientError` | Class | `devtools/agent-memory/src/agent_memory/cognee_client.py` | 62 |
| `CogneeAuthenticationError` | Class | `devtools/agent-memory/src/agent_memory/cognee_client.py` | 66 |
| `CogneeConnectionError` | Class | `devtools/agent-memory/src/agent_memory/cognee_client.py` | 70 |
| `VerificationError` | Class | `devtools/agent-memory/src/agent_memory/cognee_client.py` | 74 |
| `CognifyTimeoutError` | Class | `devtools/agent-memory/src/agent_memory/cognee_client.py` | 82 |
| `CogneeServiceUnavailableError` | Class | `devtools/agent-memory/src/agent_memory/cognee_client.py` | 90 |
| `AgentMemoryConfig` | Class | `devtools/agent-memory/src/agent_memory/config.py` | 50 |
| `CogneeClient` | Class | `devtools/agent-memory/src/agent_memory/cognee_client.py` | 98 |
| `DecisionRecord` | Class | `devtools/agent-memory/src/agent_memory/session.py` | 20 |
| `SessionContext` | Class | `devtools/agent-memory/src/agent_memory/session.py` | 43 |
| `ParsedContent` | Class | `devtools/agent-memory/src/agent_memory/markdown_parser.py` | 26 |
| `GitError` | Class | `devtools/agent-memory/src/agent_memory/git_diff.py` | 29 |
| `DocstringEntry` | Class | `devtools/agent-memory/src/agent_memory/docstring_extractor.py` | 23 |
| `ComponentStatus` | Class | `devtools/agent-memory/src/agent_memory/models.py` | 269 |
| `HealthStatus` | Class | `devtools/agent-memory/src/agent_memory/models.py` | 289 |
| `RetryConfig` | Class | `devtools/agent-memory/src/agent_memory/resilience.py` | 37 |
| `CircuitBreaker` | Class | `devtools/agent-memory/src/agent_memory/resilience.py` | 80 |
| `CircuitBreakerConfig` | Class | `devtools/agent-memory/src/agent_memory/resilience.py` | 66 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Test → CogneeServiceUnavailableError` | cross_community | 6 |
| `Test → _get_headers` | cross_community | 6 |
| `Test → Parse_retry_after` | cross_community | 6 |
| `Session_save → CogneeServiceUnavailableError` | cross_community | 6 |
| `Session_save → _get_headers` | cross_community | 6 |
| `Session_save → Parse_retry_after` | cross_community | 6 |
| `Session_save → Calculate_backoff` | cross_community | 6 |
| `Coverage → CogneeServiceUnavailableError` | cross_community | 6 |
| `Coverage → _get_headers` | cross_community | 6 |
| `Coverage → Parse_retry_after` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Floe_catalog_polaris | 12 calls |
| Ops | 4 calls |
| Network | 3 calls |
| Schemas | 1 calls |
| Validators | 1 calls |
| Oci | 1 calls |

## How to Explore

1. `gitnexus_context({name: "can_execute"})` — see callers and callees
2. `gitnexus_query({query: "agent_memory"})` — find related execution flows
3. Read key files listed above for implementation details
