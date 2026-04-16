# Assumptions: In-Cluster E2E Test Execution

## A1: Kind cluster networking permits pod-to-pod DNS resolution without NetworkPolicy restrictions
- **Category**: environmental
- **Impact**: HIGH — if wrong, in-cluster test runner gets connection refused despite correct DNS
- **Resolution**: ACCEPTED — Kind clusters have no NetworkPolicies by default; floe Helm chart does not deploy any
- **Evidence**: `charts/floe-platform/templates/` contains no NetworkPolicy resources; `testing/k8s/kind-config.yaml` uses default Calico/kindnet CNI without policy enforcement

## A2: Existing test-integration.sh can be parameterized for E2E without breaking integration path
- **Category**: technical
- **Impact**: MEDIUM — if wrong, need a separate script
- **Resolution**: ACCEPTED — script already supports `TEST_PATH` and `TEST_ARGS` env vars (test-runner.yaml lines 39-42)
- **Evidence**: Job definition has `TEST_PATH: "tests/"` and `TEST_ARGS: ""` as configurable env vars

## A3: PVC-based artifact storage works in Kind clusters
- **Category**: technical
- **Impact**: MEDIUM — if wrong, need alternative extraction
- **Resolution**: ACCEPTED — Kind uses local-path-provisioner which supports ReadWriteOnce PVCs
- **Evidence**: Kind docs confirm local-path-provisioner is the default StorageClass

## A4: Tests that set OTEL_EXPORTER_OTLP_ENDPOINT can use ServiceEndpoint for the URL value
- **Category**: technical
- **Impact**: LOW — if wrong, need conditional logic per execution mode
- **Resolution**: ACCEPTED — the tests set this env var to configure OTel SDK; the URL just needs to point to the collector regardless of mode. ServiceEndpoint resolves correctly in both modes.

## A5: Destructive tests (helm upgrade, pod kill) can run in-cluster with elevated RBAC
- **Category**: integration
- **Impact**: HIGH — if wrong, destructive tests only run in host-based mode (constitutional violation)
- **Resolution**: ACCEPTED — K8s Jobs can have any RBAC via dedicated ServiceAccount. Helm CLI works from inside pods with appropriate ServiceAccount token and kubeconfig.
- **Evidence**: Helm 3 uses K8s API directly (Secrets-based release storage); a pod with secrets access can run `helm upgrade`

## A6: The Dockerfile does not currently include Helm CLI
- **Category**: technical
- **Impact**: MEDIUM — destructive test Job needs Helm installed
- **Resolution**: ACCEPTED — will add `helm` installation to Dockerfile (or use a separate Dockerfile for destructive tests)
- **Evidence**: `testing/Dockerfile` installs kubectl and dbt but not helm
