# DevPod Remote E2E Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make full DevPod lifecycle validation execute E2E tests inside the Hetzner workspace and avoid local test-runner image streaming by default.

**Architecture:** `scripts/devpod-test.sh` remains the lifecycle owner. It provisions, health-checks, tunnels, then runs `make test-e2e` remotely with `IMAGE_LOAD_METHOD=kind`; the existing local DevPod image transport path remains available only through an explicit fallback variable.

**Tech Stack:** Bash, DevPod CLI, Kind, Helm-rendered Kubernetes Jobs, pytest structural tests.

---

### Task 1: Lock The Remote Execution Contract

**Files:**
- Modify: `tests/unit/test_devpod_source_selection.py`
- Modify: `scripts/devpod-test.sh`

- [ ] **Step 1: Write the failing structural tests**

Add tests that assert `devpod-test.sh` runs E2E remotely by default, uses the configured remote workdir, selects `IMAGE_LOAD_METHOD=kind`, and keeps local execution behind `DEVPOD_E2E_EXECUTION=local`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `uv run pytest tests/unit/test_devpod_source_selection.py -q`

Expected: the new tests fail because `scripts/devpod-test.sh` still invokes local `make -C "${PROJECT_ROOT}" test-e2e KUBECONFIG="${KUBECONFIG_PATH}"`.

- [ ] **Step 3: Implement the remote E2E command**

Update Step 4 in `scripts/devpod-test.sh` so the default path calls:

```bash
devpod ssh "${WORKSPACE}" \
    --start-services=false \
    --workdir "${DEVPOD_REMOTE_WORKDIR}" \
    --command "IMAGE_LOAD_METHOD=kind make test-e2e"
```

Add `DEVPOD_E2E_EXECUTION="${DEVPOD_E2E_EXECUTION:-remote}"` near the script configuration and support `DEVPOD_E2E_EXECUTION=local` as the old fallback path.

- [ ] **Step 4: Verify the focused tests pass**

Run: `uv run pytest tests/unit/test_devpod_source_selection.py -q`

Expected: all tests pass.

### Task 2: Fix Health Gate Numeric Counting

**Files:**
- Modify: `tests/unit/test_devpod_source_selection.py`
- Modify: `scripts/devpod-test.sh`

- [ ] **Step 1: Write the failing structural test**

Add a test that asserts the health loop captures pod rows once in a variable and computes `TOTAL` through a single numeric command substitution rather than `wc -l | tr -d ' ' || echo "0"`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `uv run pytest tests/unit/test_devpod_source_selection.py -q`

Expected: the new test fails against the existing health loop.

- [ ] **Step 3: Implement captured pod counting**

Change the loop to:

```bash
POD_ROWS="$(kubectl --kubeconfig="${KUBECONFIG_PATH}" get pods -n "${NAMESPACE}" --no-headers 2>/dev/null || true)"
if [[ -z "${POD_ROWS}" ]]; then
    TOTAL=0
    UNHEALTHY=0
else
    TOTAL="$(printf '%s\n' "${POD_ROWS}" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')"
    UNHEALTHY="$(printf '%s\n' "${POD_ROWS}" | grep -Ecv " Running | Completed " || true)"
fi
```

- [ ] **Step 4: Verify the focused tests pass**

Run: `uv run pytest tests/unit/test_devpod_source_selection.py -q`

Expected: all tests pass.

### Task 3: Validate Shell And Affected Contracts

**Files:**
- Validate: `scripts/devpod-test.sh`
- Validate: `testing/ci/test-e2e-cluster.sh`
- Validate: `tests/unit/test_devpod_source_selection.py`

- [ ] **Step 1: Run shell syntax validation**

Run: `bash -n scripts/devpod-test.sh testing/ci/test-e2e-cluster.sh`

Expected: exit code 0.

- [ ] **Step 2: Run affected unit tests**

Run: `uv run pytest tests/unit/test_devpod_source_selection.py tests/unit/test_e2e_runner_devpod_path.py -q`

Expected: all tests pass.

- [ ] **Step 3: Run remote lifecycle validation**

Run:

```bash
FLOE_REQUIRED_FLUX_GIT_BRANCH=feat/alpha-reliability-closure \
DEVPOD_GIT_REF=feat/alpha-reliability-closure \
DEVPOD_HEALTH_TIMEOUT=900 \
make devpod-test
```

Expected: platform bootstrap completes on Hetzner, E2E tests build/load the test runner on the DevPod VM, and no local `docker save floe-test-runner:latest | devpod ssh ... docker load` appears in Step 4.
