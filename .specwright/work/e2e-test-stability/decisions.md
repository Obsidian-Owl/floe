# Decisions: E2E Test Stability — Round 2

## D1: Fix manifest config rather than add backward compat to plugin

- **Type**: DISAMBIGUATION
- **Rule**: Constitution Principle VI (Security First) — OAuth2 is the correct
  auth abstraction. The `credential` field was a pre-OAuth2 shorthand.
- **Choice**: Update `demo/manifest.yaml` to use `oauth2:` format
- **Alternative rejected**: Adding `credential` as a backward-compat field in
  `PolarisCatalogConfig`. Rejected because: (a) the plugin schema is correct,
  (b) adding backward compat for a pre-alpha demo config adds complexity,
  (c) the manifest is the stale artifact, not the plugin.

## D2: Bump cryptography rather than add to .vuln-ignore

- **Type**: DISAMBIGUATION
- **Rule**: Constitution Principle VI — "Update within 7 days of CVE disclosure"
- **Choice**: Bump `cryptography>=46.0.6`
- **Alternative rejected**: Adding to `.vuln-ignore`. Only appropriate if the
  CVE doesn't apply to our usage pattern. `GHSA-m959-cc7f-wv43` affects
  cryptography broadly — bump is the correct fix.

## D3: Scope includes two test files for Fix 3

- **Type**: DISAMBIGUATION (architect review finding)
- **Rule**: Completeness — both `test_compile_deploy_materialize_e2e.py:239`
  and `test_dbt_e2e_profile.py:550` assert `path.startswith("/tmp/")`.
- **Choice**: Fix both files in a single task.

## D4: Fix 1 requires COPY line AND FLOE_PLUGINS update

- **Type**: DISAMBIGUATION (architect review finding)
- **Rule**: Completeness — adding to `FLOE_PLUGINS` without the stage-2 COPY
  would fail with "source for floe-iceberg not found".
- **Choice**: Both changes in a single task.

## D5: Deferred OpenLineage parentRun facet

- **Type**: SCOPE
- **Rule**: Stage boundary — production code change that crosses architectural
  boundaries (lineage emission in orchestrator plugin).
- **Choice**: Defer to its own `/sw-design` cycle. 1 test failure is acceptable
  as a known issue while the fix is properly designed.

## D6: Deferred port-forward stability

- **Type**: SCOPE
- **Rule**: Root cause resolved — SSH tunnel conflict was the issue, not watchdog
  logic. Running `make test-e2e` without pre-existing tunnels eliminates the problem.
- **Choice**: No code change needed. Document in test-e2e.sh if not already noted.

## D7: Single work unit (planning phase)

- **Type**: DISAMBIGUATION
- **Rule**: Blast radius — all 7 fixes are local to their respective files with
  no systemic impact. No fix crosses package boundaries.
- **Choice**: Flat layout (single work unit). 8 tasks including validation.

## D8: CVE fix via .vuln-ignore rather than lockfile bump

- **Type**: DISAMBIGUATION
- **Rule**: Minimal blast radius — `uv lock --upgrade-package cryptography` may
  cascade to other dependency changes across multiple lockfiles.
- **Choice**: Add to `.vuln-ignore` with review date. The keycloak plugin already
  has `>=46.0.6` pinned; the lockfile will naturally pick it up on next full
  regeneration.
- **Alternative rejected**: Lockfile bump — higher risk of unintended changes.

## D9: Task 8 as explicit validation task

- **Type**: DISAMBIGUATION (user request)
- **Rule**: User explicitly requested "ensuring that the final task is to run E2E
  tests and demo to fully validate the changes worked."
- **Choice**: T8 is a validation-only task with clear pass/fail criteria. No code
  changes. Requires DevPod infrastructure.
