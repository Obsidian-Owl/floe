# Decisions: In-Cluster E2E Test Execution

## D1: In-cluster execution over tunnel hardening
- **Type**: DISAMBIGUATION (>1 valid approach)
- **Rule applied**: User directive — "I want the long term solutions - no tactical fixes"
- **Alternatives**: autossh + keepalive (tactical), kubefwd (still uses K8s API tunnel), Docker network join (Linux-only)
- **Choice**: In-cluster K8s Job execution
- **Rationale**: Eliminates the entire tunnel/port-forward transport layer. Aligns with Constitution Principle V (K8s-native). Infrastructure already 80% built.

## D2: Two separate Jobs (standard + destructive) over single Job with full RBAC
- **Type**: DISAMBIGUATION (security vs simplicity)
- **Rule applied**: Constitution Principle VI (Security First) + blast radius minimization
- **Choice**: Separate Jobs with separate ServiceAccounts
- **Rationale**: Standard E2E tests don't need secrets/deployment RBAC. Granting it creates unnecessary blast radius. Destructive tests are a small subset (~6 tests) that genuinely need elevated access.

## D3: PVC-primary artifact extraction over kubectl-cp-primary
- **Type**: Architect BLOCK resolution
- **Rule applied**: Reliability requirement — architect flagged kubectl cp as fragile
- **Choice**: PVC-backed /artifacts volume with helper pod extraction
- **Rationale**: PVC survives pod eviction/OOM. kubectl cp requires pod to exist in terminal state. PVC is more reliable for CI artifact pipelines.

## D4: Do not extend test-e2e.sh for CI
- **Type**: DISAMBIGUATION (extend existing vs new path)
- **Rule applied**: Architect INFO — "adding features to it contradicts the stated goal"
- **Choice**: No new features to test-e2e.sh. It remains as-is for dev convenience.
- **Rationale**: The user wants long-term solutions. Investing in a mode being deprecated for CI is counter-productive.

## D5: Destructive tests run in CI (separate Job) rather than dev-only
- **Type**: Architect pre-mortem resolution
- **Rule applied**: Constitution Principle V — "All E2E tests MUST run in Kubernetes"
- **Choice**: Destructive tests get their own in-cluster Job with elevated RBAC
- **Rationale**: Excluding destructive tests from CI creates a coverage gap. The architect's pre-mortem correctly identified this risk. Separate Job with elevated SA is the constitutional path.

## D6: Add Helm CLI to testing Dockerfile
- **Type**: Technical requirement from A6
- **Rule applied**: Destructive tests need helm; single Dockerfile is simpler than two
- **Choice**: Add `helm` installation alongside existing kubectl in Dockerfile
- **Rationale**: Helm 3 is a single binary (~50MB). Adding it to the existing Dockerfile is simpler than maintaining a separate destructive-tests Dockerfile.

## D7: New work unit (not continuing e2e-tunnel-resilience)
- **Type**: State management
- **Rule applied**: Previous work is `shipped`; new scope warrants new ID
- **Choice**: Work ID `e2e-in-cluster-ci`

## D8: Two work units (test-portability + in-cluster-infra)
- **Type**: DISAMBIGUATION (decomposition granularity)
- **Rule applied**: Blast radius boundaries — test code changes (local) vs infrastructure (adjacent)
- **Alternatives**: Single unit (simpler but mixes concerns), 6 units (one per design area, too granular)
- **Choice**: 2 units with dependency: test-portability → in-cluster-infra
- **Rationale**: Unit 1 (test-portability) is independently valuable — makes tests portable without any infra changes. Unit 2 (in-cluster-infra) depends on Unit 1 and groups tightly coupled infrastructure (Jobs, RBAC, Dockerfile, CI script, workflow). 6 units would be over-decomposed since the infra pieces can't be tested independently.

## D9: Design correction — conftest.py:349 is docstring, not functional
- **Type**: Late discovery during planning
- **Rule applied**: Verified actual code before writing spec
- **Choice**: 4 functional localhost changes (not 5 as design stated)
- **Rationale**: `conftest.py:349` is a docstring example inside `wait_for_service` fixture definition. The smoke check fixture already uses `ServiceEndpoint`. No functional change needed.

## D10: RBAC manifests in testing/k8s/rbac/ (not Helm chart templates/)
- **Type**: DISAMBIGUATION (placement)
- **Rule applied**: Design said "charts/floe-platform/templates/" but E2E RBAC is test infrastructure, not production
- **Choice**: `testing/k8s/rbac/` directory alongside existing `testing/k8s/jobs/`
- **Rationale**: E2E test RBAC is applied by the CI script (`kubectl apply -f`), not by Helm. Putting it in the Helm chart would deploy test infrastructure to production. Test-scoped resources belong in `testing/`.
