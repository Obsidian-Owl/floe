# Gate: Tests

**Status**: PASS
**Timestamp**: 2026-04-08

## Contract tier (AC-1..AC-9 tripwire)
`pytest tests/contract/test_test_infra_chart_integrity.py -v` → **11 passed in 1.39s**

| Test | AC | Result |
|------|----|----|
| test_test_jobs_reference_only_chart_rendered_identifiers | AC-1 | PASS |
| test_tests_disabled_render_has_no_test_resources | AC-2 | PASS |
| test_warehouse_name_single_source_of_truth | AC-3 | PASS |
| test_test_runner_rbac_rendered_from_chart | AC-4 + AC-8 carry-forward | PASS |
| test_common_sh_exists | AC-5 | PASS |
| test_every_test_script_sources_common_sh | AC-5 | PASS |
| test_no_hardcoded_floe_platform_in_test_scripts | AC-5 | PASS |
| test_no_kind_cluster_legacy_assignments_outside_common_sh | AC-5 | PASS |
| test_raw_test_manifest_dirs_deleted | AC-7 | PASS |
| test_no_references_to_deleted_test_manifest_dirs | AC-7 | PASS |
| test_values_test_pins_fullname_override | AC-9 | PASS |

## Unit tier (chart-rendering observability tests)
`pytest tests/unit/test_observability_manifests.py` → **24 passed**

## Full regression (post-build)
940 passed, 1 xfailed. No new failures introduced.

## Requirement traceability
`python -m testing.traceability --report` → **226/226 (100.0%)**

## Coverage gaps / notes
- AC-6 (`common.sh` fixture integration), AC-8 (`test-integration.sh` behavior),
  AC-10 (`make test-e2e` deployment readiness) are integration/E2E tier per spec.
  Not contract-tier; excluded from this gate by design per AC-11.

## Verdict
PASS.
