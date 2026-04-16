# Spec Compliance Gate — loud-failures
**Status**: PASS
**Timestamp**: 2026-04-06T15:14:00Z

| AC | Status | Evidence |
|----|--------|----------|
| AC-1: All 4 try_create_* re-raise on configured-but-broken | PASS | All 4 use `except Exception: logger.exception(...); raise` |
| AC-2: WARNING (not DEBUG) for unconfigured | PASS | All 4 use `logger.warning("{resource}_not_configured")` |
| AC-3: Consistent structured log keys | PASS | `{resource}_not_configured`, `{resource}_creation_failed` in all 4 |
| AC-4: Ingestion exception swallowing removed | PASS | `return {}` replaced with `raise` in ingestion.py:125-127 |
| AC-5: Pipeline FAILS on unreachable Iceberg | PASS | Integration test at test_loud_failure_integration.py |
| AC-6: Contract test enforces factory semantics | PASS | 16 parametrized tests at test_resource_factory_semantics.py |
