# Integration Criteria: Test Infrastructure Convergence

After all units are built, these structural connections MUST exist:

- [ ] IC-1: `Makefile` target `test-e2e` invokes `testing/ci/test-e2e-cluster.sh` (not `test-e2e.sh`)
- [ ] IC-2: `Makefile` target `test-e2e-full` invokes `testing/ci/test-e2e-full.sh`
- [ ] IC-3: `testing/ci/test-e2e-full.sh` calls `testing/ci/test-e2e-cluster.sh` for both standard and destructive suites
- [ ] IC-4: `testing/ci/test-e2e-cluster.sh` extracts HTML report (`e2e-report.html`) from PVC alongside JUnit XML
- [ ] IC-5: `testing/ci/test-e2e-cluster.sh` calls `extract_pod_logs()` on Job failure
- [ ] IC-6: `testing/k8s/jobs/test-e2e.yaml` includes `OTEL_EXPORTER_OTLP_ENDPOINT` env var
- [ ] IC-7: `testing/k8s/jobs/test-e2e.yaml` includes `--html=/artifacts/e2e-report.html` arg
- [ ] IC-8: `charts/floe-platform/values.yaml` uses YAML anchors `&podSecCtx` and `&containerSecCtx` referenced by subchart keys
- [ ] IC-9: `tests/contract/test_helm_security_contexts.py` imports `subprocess` and runs `helm template`
- [ ] IC-10: `Makefile` targets `helm-validate`, `helm-security`, `helm-test-unit` use `docker run` (not host binaries)
