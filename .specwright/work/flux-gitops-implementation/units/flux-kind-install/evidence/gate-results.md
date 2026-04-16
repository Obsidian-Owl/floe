# Gate Results: flux-kind-install

**Date**: 2026-04-15
**Unit**: flux-kind-install (1 of 3)

## Gate-Build: PASS
- Ruff lint: 0 issues on 3 test files
- Ruff format: all files formatted
- YAML parse: 3/3 CRD files parse successfully
- Shell syntax: common.sh and setup-cluster.sh pass bash -n

## Gate-Tests: PASS
- 38/38 flux-specific tests pass (0.05s)
- 312/312 full unit suite pass (13.9s)
- Pre-existing test_iceberg_purge failure excluded (unrelated working-tree changes)

## Gate-Security: PASS (3 WARNs, pre-existing or by-design)
- WARN-1: print_info echoes test passwords (pre-existing, not from this unit)
- WARN-2: GitRepository polls branch HEAD without integrity pinning (by-design for test infra; Cosign verification addressed in Unit 3 AC-2)
- WARN-3: insecure-skip-tls-verify in DooD probe (pre-existing)
- No hardcoded secrets in new code
- No command injection risks

## Gate-Wiring: PASS (0 findings)
- common.sh exports FLUX_VERSION, setup-cluster.sh sources it correctly
- HelmRelease cross-references verified (jobs dependsOn platform, both reference GitRepository)
- GitRepository name/namespace match sourceRef in both HelmReleases
- kubectl apply path matches CRD directory
- FLOE_NO_FLUX gates all Flux operations correctly

## Gate-Spec: PASS (1 WARN)
- AC-1 through AC-10: PASS
- AC-11: WARN -- structural test is trivially true (matches string anywhere in script). Full e2e validation deferred per tier annotation.
- Minor: setup-cluster.sh uses local NAMESPACE instead of FLOE_NAMESPACE from common.sh (both resolve to floe-test)
