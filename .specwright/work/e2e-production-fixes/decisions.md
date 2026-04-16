# Decisions: E2E Production Fixes

## D1: Commit manifests rather than generate at build time
- **Choice**: Commit `demo/*/target/manifest.json` with `.gitignore` exception
- **Alternatives**: (A) `dbt parse` in Dockerfile, (B) `dbt compile` in Dockerfile
- **Resolution**: DISAMBIGUATION -- follows existing pattern (definitions.py is committed for same reason). Alternatives require live infrastructure at build time.
- **Reversibility**: Type 2 (easily reversible -- delete committed files, update .gitignore)

## D2: Adjust test assertions rather than change emission timing
- **Choice**: Check Marquez for job existence + event types, not intermediate run states
- **Alternatives**: (A) Add delay between per-model START and COMPLETE, (B) Accept only pipeline-level START check
- **Resolution**: DISAMBIGUATION -- production code emission is correct per OpenLineage spec. Test should validate what Marquez exposes, not assume implementation details of state transitions.
- **Reversibility**: Type 2 (test-only change)

## D3: Simple constraint bump for requests CVE
- **Choice**: `requests>=2.33.0` in root pyproject.toml
- **Alternatives**: (A) Add to vulnerability ignore list, (B) Remove requests dependency
- **Resolution**: Direct -- CVE has a fix version, no breaking changes. Security policy requires update within 7 days.
- **Reversibility**: Type 2 (revert constraint)

## D4: Make hook deadline configurable with higher CI default
- **Choice**: Parameterize `activeDeadlineSeconds` via values, default 600s in test
- **Alternatives**: (A) Just increase hardcoded value, (B) Remove deadline entirely
- **Resolution**: DISAMBIGUATION -- parameterization follows Helm best practices (P50: values must be configurable). Removing deadline risks hung upgrades.
- **Reversibility**: Type 2 (values change)

## D5: Values-driven args construction for dbt jobs (Option A)
- **Choice**: Template constructs args from `profilesDir`, `projectDir` etc.
- **Alternatives**: (B) Passthrough `dbt.args` with callers overriding fully
- **Resolution**: DISAMBIGUATION -- `values-test.yaml` was clearly written for Option A. The unconsumed keys are the bug.
- **Reversibility**: Type 2 (template change, keep `dbt.args` as override escape hatch)
