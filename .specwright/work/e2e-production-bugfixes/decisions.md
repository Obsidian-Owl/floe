# Decisions: E2E Production Bugfixes

## D1: Use plugin connect() instead of manual credential construction

- **Type**: DISAMBIGUATION
- **Rule applied**: Constitution Principle II (Plugin-First Architecture)
- **Options**: (A) Update template to manually extract oauth2 fields and construct credential string, (B) Delegate to plugin system via registry.get + configure + connect
- **Choice**: B
- **Rationale**: Option A duplicates the Polaris plugin's `connect()` logic (credential construction, scope handling, token URL, credential vending). Option B follows the existing pattern in `_load_iceberg_resources()` and `create_iceberg_resources()`. If the auth mechanism changes, only the plugin needs updating.

## D2: Scope of work — fix both bugs in one work unit

- **Type**: DISAMBIGUATION
- **Rule applied**: Blast radius assessment — both are LOCAL scope, both affect same E2E run
- **Choice**: Single work unit with 2 tasks
- **Rationale**: Both bugs are small, local fixes with no interdependency. Shipping separately would mean 2 PR/build/deploy cycles for 2 small changes to the same test suite.

## D3: Design scope interpretation (design phase)

- **Type**: DISAMBIGUATION
- **Rule applied**: User said "the fixes for the production bugs" — meaning the 2 bugs identified in the E2E analysis
- **Choice**: Fix both production bugs (code generator template + S3 tracer_name)
- **Rationale**: Both were explicitly identified in the preceding conversation analysis as "production code issues".

## D4: Single work unit (planning phase)

- **Type**: DISAMBIGUATION
- **Rule applied**: Blast radius — both fixes are LOCAL, 3 files total
- **Choice**: Flat layout (no decomposition into sub-units)
- **Rationale**: Total change is ~30 lines across 2 production files + regenerated demo files. No architectural boundary crossings.

## D5: tracer_name convention (planning phase)

- **Type**: DISAMBIGUATION
- **Rule applied**: Existing convention from Polaris plugin
- **Options**: (A) `"floe_storage_s3"` (underscore), (B) `"floe.storage.s3"` (dot-separated)
- **Choice**: B — dot-separated
- **Rationale**: Polaris plugin uses `TRACER_NAME = "floe.catalog.polaris"` in `tracing.py`. Consistency with existing plugins takes precedence.
