# Spec: test-infra-drift-elimination

**Goal**: make K8s identifier drift between chart, test manifests, and shell
scripts structurally impossible. Delete dead `test-runner.yaml`. Add a
contract test as a tripwire against regression.

**Design**: `.specwright/work/test-infra-drift-elimination/design.md`

---

## Acceptance Criteria

### AC-1 — Test Job manifests live only in the chart

Every Kubernetes Job used by test infrastructure is rendered from a template
under `charts/floe-platform/templates/tests/`. Every `Service`, `Secret`, and
`ServiceAccount` name referenced by those Jobs comes from a
`floe-platform.*` helper (`include "floe-platform.fullname"`,
`include "floe-platform.polaris.fullname"`, etc.) or a values key — never a
literal string.

**Falsifying test** [tier: contract]: render the chart with
`helm template floe-platform charts/floe-platform -f charts/floe-platform/values-test.yaml --set tests.enabled=true`.
For every rendered `Job` doc, parse every `serviceAccountName`, every
`envFrom[].secretRef.name`, every `env[].valueFrom.secretKeyRef.name`, every
`env[].value` whose value matches `^[a-z][a-z0-9-]*$` and starts with the
rendered fullname prefix. Assert each such identifier appears as a rendered
Service, Secret, ConfigMap, or ServiceAccount in the same render. Fails if
any referenced name is not produced by the chart.

### AC-2 — Test Jobs gated by `tests.enabled`

A render with `tests.enabled=false` (the default, set in `values.yaml`)
produces zero resources whose template path starts with `templates/tests/`
and zero resources with the label `test-type`.

**Falsifying test** [tier: contract]: render
`helm template floe-platform charts/floe-platform -f charts/floe-platform/values.yaml`
and assert no document has `metadata.labels["test-type"]` set and no document
was sourced from a template path under `tests/` (check via
`metadata.annotations` Helm source annotation or by diffing against the
`tests.enabled=true` render).

### AC-3 — Single source of truth for warehouse name

The Polaris catalog name consumed by the bootstrap Job and the warehouse name
consumed by the test Job env (`POLARIS_WAREHOUSE`) resolve to the same string
in the rendered chart. Changing one values key changes both.

**Falsifying test** [tier: contract]: render the chart and assert that
(rendered `polaris-bootstrap` Job's catalog-create payload) and (rendered
test-e2e Job's `POLARIS_WAREHOUSE` env value) are equal. Additionally, run
a second render overriding the canonical values key to a different string
(e.g. `floe-test-alt`) and assert *both* sites update in lockstep.

### AC-4 — RBAC manifests live only in the chart

`ServiceAccount`, `Role`, and `RoleBinding` for test runners (standard and
destructive) render from templates under `charts/floe-platform/templates/tests/`.
Helper functions `floe-platform.testRunner.saName` and
`floe-platform.testRunnerDestructive.saName` exist in `_helpers.tpl`. Raw
RBAC YAML under `testing/k8s/rbac/` does not exist.

**Falsifying test** [tier: contract]: assert
`not (Path("testing/k8s/rbac").exists())`. Assert the rendered chart (with
`tests.enabled=true`) contains exactly two `ServiceAccount` resources whose
names come from the two helpers, plus matching `Role` and `RoleBinding`
resources. Assert standard runner Role does not include `list`/`watch` on
`secrets` (carry forward security-hardening AC-8).

### AC-5 — Shell scripts resolve identifiers through `common.sh`

A new file `testing/ci/common.sh` exists. Every script under `testing/ci/test-*.sh`
(except `common.sh` itself) sources `common.sh` as its first non-comment
action. No script under `testing/ci/test-*.sh` contains the literal string
`floe-platform-` or the literal strings `KIND_CLUSTER=` or `KIND_CLUSTER_NAME=`
outside of `common.sh`. Every Kubernetes identifier previously hardcoded
(service names, secret names, namespace, cluster name, image name, job name,
manifest path) is produced by calling a `common.sh` helper or reading a
`FLOE_*` variable exported by `common.sh`.

**Falsifying test** [tier: contract]:
- Assert `Path("testing/ci/common.sh").exists()`.
- For each script in `testing/ci/test-*.sh` (excluding `common.sh`), read the
  first 20 non-comment, non-blank lines and assert one of them is
  `source "$(dirname "$0")/common.sh"` (or equivalent resolvable form).
- Run `grep -nE 'floe-platform-' testing/ci/test-*.sh` excluding `common.sh`
  and assert zero matches. Fail message must cite the offending file:line.
- Run `grep -nE '^(KIND_CLUSTER|KIND_CLUSTER_NAME)=' testing/ci/test-*.sh`
  excluding `common.sh` and assert zero matches.

### AC-6 — `common.sh` provides a tested rendering helper

`common.sh` defines:
- `FLOE_RELEASE_NAME` (default `floe-platform`)
- `FLOE_NAMESPACE` (default `floe-test`)
- `FLOE_KIND_CLUSTER` (default `floe`, absorbs `KIND_CLUSTER` and `KIND_CLUSTER_NAME` if either is already set)
- `FLOE_VALUES_FILE` (default `charts/floe-platform/values-test.yaml`)
- `FLOE_CHART_DIR` (default `charts/floe-platform`)
- `floe_render_test_job <template-subpath>` — echoes a rendered YAML stream for the named template
- `floe_service_name <component>` — echoes `${FLOE_RELEASE_NAME}-<component>`
- `floe_require_cluster` — exits non-zero with an actionable message if the Kind cluster doesn't exist

**Falsifying test** [tier: integration]: in a test fixture, source
`common.sh` in a subshell and assert:
- All six `FLOE_*` variables are exported with the documented defaults when
  no env is pre-set.
- `FLOE_KIND_CLUSTER=floe-custom bash -c 'source common.sh; echo "$FLOE_KIND_CLUSTER"'` prints `floe-custom`.
- `KIND_CLUSTER=legacy bash -c 'source common.sh; echo "$FLOE_KIND_CLUSTER"'` prints `legacy` (legacy absorb).
- `KIND_CLUSTER_NAME=legacy2 bash -c 'source common.sh; echo "$FLOE_KIND_CLUSTER"'` prints `legacy2`.
- `floe_render_test_job tests/job-e2e.yaml` emits a parseable YAML stream
  containing at least one `Job` document whose name is `floe-test-e2e`.
- `floe_service_name polaris` prints `floe-platform-polaris`.
- `floe_require_cluster` exits non-zero with a message containing "Kind cluster"
  when the named cluster does not exist.

### AC-7 — Dead `test-runner.yaml` and directories deleted

`testing/k8s/jobs/test-runner.yaml` does not exist. `testing/k8s/jobs/` does
not exist. `testing/k8s/rbac/` does not exist. No script, Makefile target,
GitHub Actions workflow, pre-commit hook, or Python test references any path
under `testing/k8s/jobs/` or `testing/k8s/rbac/`.

**Falsifying test** [tier: contract]:
- Assert each of the three paths does not exist.
- Run `grep -rnE 'testing/k8s/(jobs|rbac)' .github/ Makefile testing/ tests/ scripts/ charts/ docker/ packages/ plugins/ --include='*.sh' --include='*.yaml' --include='*.yml' --include='*.py' --include='Makefile'` and assert zero matches. Fail message must cite the offending file:line.

### AC-8 — `TEST_SUITE=integration` path in `test-integration.sh` removed or repointed

The default dispatch in `testing/ci/test-integration.sh` does not reference
`testing/k8s/jobs/test-runner.yaml`. If the `TEST_SUITE=integration` branch is
retained, it invokes `floe_render_test_job` pointing at a live chart template.
If removed, running the script without a `TEST_SUITE` env var produces an
actionable error (not a silent fallthrough to a stale manifest).

**Falsifying test** [tier: integration]: run
`TEST_SUITE= bash testing/ci/test-integration.sh --help 2>&1 || true` in a
mocked environment (kubectl + helm stubbed to no-op) and assert either:
- The script calls `floe_render_test_job` with a path that starts with `tests/`, OR
- The script exits non-zero with a message containing `TEST_SUITE`.
Additionally, grep the script for `test-runner.yaml` and assert zero matches.

### AC-9 — `fullnameOverride` preserved and respected by `floe_service_name`

`charts/floe-platform/values-test.yaml` still contains `fullnameOverride: floe-platform`.
`floe_service_name` returns `${FLOE_RELEASE_NAME}-<component>`, so callers get
`floe-platform-<component>` whenever `FLOE_RELEASE_NAME=floe-platform` (the
default). If a future change sets `FLOE_RELEASE_NAME=alt-release` and the
chart is re-deployed with `--name-template alt-release` (or override removed),
the contract test still passes because it renders the chart with the same
values the scripts use.

**Falsifying test** [tier: contract]: parse `values-test.yaml` as YAML and
assert `fullnameOverride == "floe-platform"`. Run the chart render with
`FLOE_RELEASE_NAME=alt-release helm template alt-release charts/floe-platform -f values-test-alt.yaml --set tests.enabled=true --set fullnameOverride=null` (using a synthesized alt values file that drops the override) and assert every rendered test Job's referenced names start with `alt-release-`.

### AC-10 — `make test-e2e` reaches the test-run phase without K8s name-resolution errors

Running `make test-e2e` on a freshly-deployed Hetzner DevPod + Kind cluster
launches the test Job, the Job's pod reaches `Running` state, and no
`ServiceAccount not found`, `Secret not found`, or `Service not found` errors
appear in kubelet events for the Job's pod within 60 seconds of scheduling.

**Falsifying test** [tier: e2e]: in the Hetzner DevPod, invoke
`make test-e2e`. Within the first 120 seconds after the Job is created,
collect events with `kubectl get events -n floe-test --field-selector involvedObject.name=<pod-name> -o json` and assert no event has a `reason` in `{"FailedMount", "FailedCreate"}` or a `message` matching `not found`. (This AC validates the *deployment* reaches readiness; actual test pass/fail is out of scope for this work unit.)

### AC-11 — New contract test runs in gate-build and covers ACs 1-9

A new file `tests/contract/test_test_infra_chart_integrity.py` exists. It
contains pytest functions covering the falsifying tests for AC-1, AC-2, AC-3,
AC-4, AC-5, AC-7, and AC-9. Each function carries a
`@pytest.mark.requirement("test-infra-drift-elimination-AC-{n}")` marker.
The test module runs as part of `make test-unit` (or the equivalent gate-build
invocation) and passes.

**Falsifying test** [tier: contract]: run
`.venv/bin/pytest tests/contract/test_test_infra_chart_integrity.py -v` and
assert all test functions pass. Run
`.venv/bin/python -m testing.traceability --pattern test-infra-drift-elimination`
and assert 100% of spec ACs (except AC-6, AC-8, AC-10 which are integration/e2e)
have at least one covering test.

---

## Out of scope (deferred)

- **Rego / conftest alternative**: D4 chose pytest for repo consistency. A conftest swap is a mechanical rewrite if desired later.
- **Reducing the `POLARIS_HOST`/`MINIO_HOST` env var workaround list** beyond what's incidentally cleaned by chart-helper rendering. Kept minimal: if a host env var is still needed by test code, it stays — but its *value* comes from a helper, not a literal. Further trimming is a follow-up.
- **Rename of `fullnameOverride`**: out of scope. The override stays as-is.
- **Migration of Dagster subchart or other upstream helm dependencies**: out of scope. Only floe-owned templates are moved.
- **Changing the Polaris bootstrap job logic**: only the values-key source is unified. Bootstrap HTTP logic unchanged.

---

## Known edge cases to cover in tests

- `helm template` with no `--set tests.enabled=true` must produce zero test resources (AC-2).
- `helm template -s templates/tests/job-e2e.yaml` with `tests.enabled=false` must produce an *empty* document stream, not an error (AC-2 corollary).
- `common.sh` sourced with `set -u` active (strict mode) must not error on undefined vars — use `:${VAR:=default}` style (AC-6 edge).
- `grep` in contract test must use an excluded-file pattern that ignores `common.sh` without also ignoring a future `common-helpers.sh` (AC-5 edge).
- A comment in a test script containing the literal `floe-platform-something` must still pass AC-5 — the grep must target non-comment lines, or the AC wording is relaxed to "executable lines". Resolution: grep excludes lines whose first non-whitespace char is `#`.
