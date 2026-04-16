# Context: Loud Failures (Unit 6)

## Key File Paths

### Resource Factories (the 4 try_create_* functions)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:151-198` — returns `{}` on missing config, RE-RAISES on exception
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py:114-130` — returns `{}` on missing config, **SWALLOWS exception** (returns `{}`)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/semantic.py:98-133` — returns `{}` on missing config, RE-RAISES on exception
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py:387-419` — returns `{"lineage": NoOp}` on missing config, RE-RAISES on exception

### Current Failure Semantics (CON-001)

| Factory | On missing config | On exception |
|---------|-------------------|--------------|
| `try_create_iceberg_resources()` | Returns `{}` | **Re-raises** |
| `try_create_lineage_resource()` | Returns `{"lineage": NoOp}` | **Re-raises** |
| `try_create_ingestion_resources()` | Returns `{}` | **Swallows, returns `{}`** |
| `try_create_semantic_resources()` | Returns `{}` | **Re-raises** |

### Target Semantics (after fix)

| Factory | On missing config | On exception |
|---------|-------------------|--------------|
| All 4 | Returns `{}` or NoOp + WARNING log | **Re-raises** + `"{resource}_creation_failed"` log |

### Existing Unit Tests
- `plugins/floe-orchestrator-dagster/tests/unit/` — existing tests for resource factories
- `tests/contract/` — 48 existing contract tests (no factory semantics test)

## Gotchas
- Lineage factory returns `{"lineage": NoOp}` (not `{}`) — this is correct, lineage always provides a resource
- Changing ingestion from swallow to re-raise may surface latent bugs in ingestion plugin init
- Existing E2E tests may implicitly depend on ingestion swallowing errors — survey before changing
- Log level change (DEBUG → WARNING) will increase log volume in test environments
