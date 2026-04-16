# Gate: Wiring

**Status**: PASS (with 1 WARN)

## Integration Criteria Verification

From `.specwright/work/test-infra-convergence/integration-criteria.md`:

| IC | Assertion | Result |
|----|-----------|--------|
| IC-1 | `test-e2e` invokes `test-e2e-cluster.sh` | PASS — `Makefile:132` |
| IC-2 | `test-e2e-full` invokes `test-e2e-full.sh` | PASS — `Makefile:137` |
| IC-3 | `test-e2e-full.sh` calls `test-e2e-cluster.sh` for both suites | PASS — lines 35, 74 |
| IC-4 | `test-e2e-cluster.sh` extracts HTML report | PASS — `${TEST_SUITE}-report.html` extracted at line 237 (stable variable form rather than literal `e2e-report.html`) |
| IC-5 | `test-e2e-cluster.sh` calls `extract_pod_logs()` on Job failure | PASS — lines 260, 266 |
| IC-6 | `test-e2e.yaml` includes `OTEL_EXPORTER_OTLP_ENDPOINT` | PASS — line 106 |
| IC-7 | `test-e2e.yaml` includes `--html=/artifacts/e2e-report.html` | PASS — line 36 |
| IC-8 | `values.yaml` uses anchors referenced by subchart keys | PASS — anchor name is `&podSecurityContextPSS` (not `&podSecCtx`); referenced at lines 150, 186, 237, 449, 744 |
| IC-9 | `test_helm_security_contexts.py` imports subprocess and runs `helm template` | PASS — `import subprocess` at line 21, `helm template` shell-out verified |
| IC-10 | Makefile helm targets use `docker run` | PASS — `helm-validate`, `helm-security`, `helm-test-unit` all wrap kubeconform/kubesec/helm-unittest in `docker run --rm` with pinned tags |

## WARN

- **IC-8 naming drift**: the integration criteria named the anchors
  `&podSecCtx` / `&containerSecCtx`, but the implementation uses
  `&podSecurityContextPSS` / `&containerSecurityContextPSS`. The
  structural intent (shared anchor referenced by multiple subchart keys)
  is satisfied. The IC text is out of date and should be refreshed in a
  future plan iteration.

## Cross-Unit Integration

This is the final work unit of `test-infra-convergence`. Prior units
(`unit-test-consolidation`, `test-infra-tooling`) are already shipped.
The security-hardening unit layers PSS contexts onto the Helm chart
structure that those earlier units established; no cross-unit contract
regressions were observed.
