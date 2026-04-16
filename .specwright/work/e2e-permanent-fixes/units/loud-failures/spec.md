# Spec: Loud Failures (Unit 6)

## Acceptance Criteria

### AC-1: All 4 `try_create_*` functions re-raise on configured-but-broken plugins

When a plugin IS configured in `compiled_artifacts.json` but fails to initialize (connection error, auth failure, missing dependency), ALL 4 resource factory functions MUST propagate the exception. No exception swallowing.

**How to verify:** For each factory (`try_create_iceberg_resources`, `try_create_ingestion_resources`, `try_create_semantic_resources`, `try_create_lineage_resource`): configure the plugin, mock the underlying `create_*` function to raise `ConnectionError`. Assert the exception propagates through the `try_create_*` wrapper. Specifically: `try_create_ingestion_resources` MUST no longer return `{}` on exception.

### AC-2: All 4 `try_create_*` functions log at WARNING (not DEBUG) for unconfigured plugins

When a plugin is NOT configured (`plugins.catalog is None`, etc.), the factory MUST log at WARNING level with a structured message, not DEBUG.

**How to verify:** For each factory: pass `plugins=None` or `plugins.X=None`. Capture log output. Assert log level is WARNING. Assert no DEBUG-level "skipping" messages remain.

### AC-3: Consistent log message format across all factories

All factories MUST use the format:
- Unconfigured: `"{resource}_not_configured"` (e.g., `"iceberg_not_configured"`)
- Configured but failed: `"{resource}_creation_failed"` (e.g., `"ingestion_creation_failed"`)

**How to verify:** Grep all 4 factory functions for log messages. Assert format matches convention. No free-form sentences like "Failed to create Iceberg resources."

### AC-4: Ingestion factory exception swallowing removed (CON-001 fix)

`try_create_ingestion_resources()` MUST re-raise exceptions when ingestion IS configured but `create_ingestion_resources()` raises. The `except Exception: return {}` pattern at `ingestion.py:126-130` MUST be replaced with `except Exception: raise` (matching iceberg/semantic pattern).

**How to verify:** Configure ingestion plugin. Mock `create_ingestion_resources` to raise `RuntimeError("connection refused")`. Call `try_create_ingestion_resources()`. Assert `RuntimeError` is raised (not swallowed). Assert log message `"ingestion_creation_failed"` is emitted before re-raise.

### AC-5: Pipeline FAILS (not succeeds) when configured Iceberg is unreachable

When Polaris IS configured in `compiled_artifacts.json` but is unreachable, `load_product_definitions()` (from unit 5) MUST produce a `Definitions` whose resource initialization raises an error. The pipeline MUST NOT report success with zero data.

**How to verify:** Integration test: create `Definitions` via `load_product_definitions()` with Iceberg configured but Polaris mocked as unreachable. Attempt to initialize resources. Assert exception is raised with message containing `"iceberg_creation_failed"`.

### AC-6: Contract test enforces factory semantics for all current and future factories

A parametrized contract test MUST exist at `tests/contract/test_resource_factory_semantics.py` that asserts:
- All `try_create_*` functions return `dict` for "not configured"
- All `try_create_*` functions propagate exceptions for "configured but broken"
- All `try_create_*` functions log at WARNING level

**How to verify:** Run `pytest tests/contract/test_resource_factory_semantics.py`. All parametrized cases pass. Adding a 5th factory without following the pattern would cause the test to fail.
