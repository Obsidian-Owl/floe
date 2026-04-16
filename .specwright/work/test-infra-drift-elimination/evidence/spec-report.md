# Gate: Spec Compliance

**Status**: PASS (with INFO on deferred ACs)
**Timestamp**: 2026-04-08

## AC-by-AC evidence

| AC | Tier | Status | Evidence |
|----|------|--------|----------|
| AC-1 | contract | **PASS** | `test_test_jobs_reference_only_chart_rendered_identifiers` — walks every test Job, resolves serviceAccountName + secretKeyRef + configMapKeyRef + envFrom[secretRef/configMapRef] against rendered resource names |
| AC-2 | contract | **PASS** | `test_tests_disabled_render_has_no_test_resources` — default render has zero `test-type`-labelled resources |
| AC-3 | contract | **PASS** | `test_warehouse_name_single_source_of_truth` — sentinel-flip pattern proves bootstrap Job catalog name and test Job `POLARIS_WAREHOUSE` env track `polaris.bootstrap.catalogName` in lockstep |
| AC-4 | contract | **PASS** | `test_test_runner_rbac_rendered_from_chart` — verifies 2 ServiceAccounts from helpers, matching Role/RoleBinding, AC-8 security carry-forward (`secrets: ["get"]`) |
| AC-5 | contract | **PASS** | 4 tests covering `common.sh` existence, every script sources it, no `floe-platform-` literals, no legacy `KIND_CLUSTER=` assignments |
| AC-6 | integration | **DEFERRED** (per AC-11) | `common.sh` lifts identifiers via helpers; sh-tier integration test intentionally out of scope for contract gate. `common.sh` syntax validated (`bash -n`), used by live scripts. |
| AC-7 | contract | **PASS** | `test_raw_test_manifest_dirs_deleted` + `test_no_references_to_deleted_test_manifest_dirs` — raw dirs gone, no file references remain |
| AC-8 | integration | **DEFERRED** (per AC-11) | `test-integration.sh` path not touched by this unit per spec note "out of scope (deferred)". Grep confirms no `testing/k8s/jobs/test-runner.yaml` references remain. |
| AC-9 | contract | **PASS** | `test_values_test_pins_fullname_override` — asserts `fullnameOverride: floe-platform` in values-test.yaml |
| AC-10 | e2e | **DEFERRED** (per AC-11) | E2E deployment readiness is out of scope for contract gate; validated post-ship on Hetzner DevPod. |
| AC-11 | contract | **PASS** | Contract file exists, 11 tests with `@pytest.mark.requirement` markers, `make test-unit` (and contract tier) invokes and passes them. |

## Traceability
`python -m testing.traceability --report` → **226/226 requirements (100.0%)**, PASS.

## Out-of-scope items (per spec §186)
Per spec, these are explicitly deferred:
- Rego/conftest alternative
- POLARIS_HOST/MINIO_HOST workaround list trimming
- fullnameOverride rename
- Dagster subchart migration
- Polaris bootstrap logic changes

None of these are touched.

## Verdict
PASS for contract-tier ACs (7 of 11). The 3 non-contract ACs (AC-6 integration,
AC-8 integration, AC-10 e2e) are explicitly deferred per AC-11's wording and
should be validated on live infrastructure post-ship. INFO note on the handoff.
