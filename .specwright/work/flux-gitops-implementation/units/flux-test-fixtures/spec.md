# Spec: flux-test-fixtures

**Unit**: 2 of 3
**Parent**: flux-gitops-implementation
**Purpose**: Integrate Flux awareness into pytest test infrastructure with crash-safe fixtures

## Acceptance Criteria

### AC-1: flux_suspended fixture suspends and resumes HelmRelease [tier: integration]

`testing/fixtures/flux.py` provides a `flux_suspended` module-scoped pytest fixture that:
1. Checks if Flux manages `${FLOE_RELEASE_NAME}` (default `floe-platform`) in the
   configured namespace via `kubectl get helmrelease`. The release name is read from
   `os.environ.get("FLOE_RELEASE_NAME", "floe-platform")` — not hardcoded.
2. If managed: checks that the `flux` CLI is on PATH via `shutil.which("flux")`. If
   `flux` is not found, logs a warning and returns without suspending (graceful degradation).
3. Runs `flux suspend helmrelease {name} -n {namespace}`
4. Registers a finalizer via `request.addfinalizer()` that runs
   `flux resume helmrelease {name} -n {namespace}` with `check=False` (best-effort).
   The finalizer logs on failure per P56.
5. Returns control to the test module (fixture function completes after addfinalizer registration).

After the test module completes (or crashes), the finalizer resumes the HelmRelease.
Verified by: suspending, running a no-op test, then confirming
`kubectl get helmrelease {name} -o jsonpath='{.spec.suspend}'` returns empty string
or `"false"`.

### AC-2: flux_suspended degrades gracefully without Flux [tier: unit]

The `flux_suspended` fixture degrades gracefully in three scenarios:
1. **Flux CRD not installed**: `kubectl get helmrelease` returns non-zero → fixture returns
   without suspending, no finalizer registered, no error raised.
2. **Release not Flux-managed**: `kubectl get helmrelease {name}` returns non-zero for the
   specific release → same behavior as (1).
3. **Flux CLI not on PATH**: `kubectl get helmrelease` succeeds (CRDs exist) but
   `shutil.which("flux")` returns `None` → fixture logs a warning
   ("Flux CRDs found but flux CLI not on PATH — skipping suspend") and returns
   without suspending. No `FileNotFoundError` raised.

Tests using this fixture run normally in all non-Flux environments.

### AC-3: Session startup crash recovery [tier: integration]

`tests/e2e/conftest.py` includes a session-scoped fixture `_recover_suspended_flux()`
that `helm_release_health` depends on via fixture parameter (ensuring ordering).
The fixture:
1. Runs `kubectl get helmrelease {release} -n {ns} -o jsonpath='{.spec.suspend}'`
   for both `floe-platform` and `floe-jobs-test`
2. If the result is `"true"` for either: logs a warning
   ("HelmRelease {name} was suspended from previous crash, resuming...")
   and runs `flux resume helmrelease {name} -n {ns}`
3. If kubectl returns non-zero (no Flux): silently returns (no-op)

This ensures a crashed test session never leaves Flux permanently suspended.
Resume is idempotent — resuming an already-resumed release is a no-op.

### AC-4: Flux controller smoke check [tier: e2e]

`tests/e2e/conftest.py` infrastructure smoke check includes a Flux controller health
verification step. The check uses label selectors matching Flux v2's actual labels:
1. `kubectl get pods -n flux-system -l app.kubernetes.io/component=source-controller -o jsonpath='{.items[0].status.phase}'`
2. `kubectl get pods -n flux-system -l app.kubernetes.io/component=helm-controller -o jsonpath='{.items[0].status.phase}'`
3. If either returns anything other than `"Running"`, the smoke check fails with:
   `"Flux controller {name} is not Running (status: {actual}). Check flux-system namespace."`
4. If `kubectl get namespace flux-system` returns non-zero (no Flux installed), the check
   is a no-op with an INFO log ("Flux not installed — controller check skipped") — supports
   `--no-flux` clusters. This is NOT a `pytest.skip()` — the check function simply returns.

Testability proof: Given a cluster where `helm-controller` pod is in `CrashLoopBackOff`,
when the smoke check runs, `pytest.fail()` is called with the message containing
"helm-controller is not Running (status: CrashLoopBackOff)". This can be tested by
mocking `subprocess.run` to return `CrashLoopBackOff` for the helm-controller query.

### AC-5: test_helm_upgrade_e2e uses flux_suspended [tier: integration]

The following test functions in `tests/e2e/test_helm_upgrade_e2e.py` declare a dependency
on the `flux_suspended` fixture: all test functions whose body contains a `subprocess.run`
call with `"helm"` and either `"upgrade"` or `"install"` in the command list. The fixture
is imported from `testing.fixtures.flux`. The exact set of functions is determined during
implementation by inspecting the file — no guessing required.

### AC-6: recover_stuck_helm_release delegates to Flux when available [tier: integration]

`testing/fixtures/helm.py` `recover_stuck_helm_release()` is modified to:
1. Check if Flux manages the release: `kubectl get helmrelease {name} -n {ns}`
2. If Flux is active AND `shutil.which("flux")` returns a path:
   run `flux reconcile helmrelease {name} -n {ns}` (without `--with-source` — source
   reconciliation is unnecessary when Flux is already tracking the GitRepository).
   If `flux reconcile` fails (non-zero exit), log a warning and fall through to the
   existing Helm rollback/recovery path as a fallback.
3. If Flux is not active: fall through to the existing Helm rollback/recovery path unchanged.

### AC-7: All Flux subprocess calls log on failure [tier: unit]

Every `subprocess.run()` call for `flux` or `kubectl` (Flux-related) in `testing/fixtures/flux.py`
and the conftest additions follows pattern P56: on non-zero returncode, log a warning via
`logging.getLogger(__name__)` (stdlib logging, matching existing `testing/fixtures/` convention)
with the command, returncode, and stderr. No bare `except Exception: pass`.
Best-effort cleanup calls use `check=False` but still log failures.

### AC-8: Flux helpers are importable without Flux installed [tier: unit]

`testing/fixtures/flux.py` does not import any Flux-specific Python packages. All Flux
interactions are via subprocess calls to the `flux` CLI. The module can be imported
on any system regardless of whether Flux is installed — the CLI availability check
happens at fixture runtime via `shutil.which("flux")`, not at import time.

## WARNs from Spec Review (Accepted)

- WARN-4: Release name extracted from env var (AC-1 revised), not hardcoded
- WARN-5: Fixture ordering via dependency parameter (AC-3 revised: `helm_release_health` depends on `_recover_suspended_flux`)
- WARN-6: Label selectors corrected to `app.kubernetes.io/component` (AC-4 revised)
- WARN-7: `flux reconcile` failure falls through to Helm path (AC-6 revised)
- WARN-8: `shutil.which("flux")` check prevents FileNotFoundError (AC-1, AC-2 revised)
- WARN-9: Test functions determined by implementation-time inspection (AC-5 revised)
- INFO-10: Both empty string and "false" handled (AC-1 verification step)
- INFO-11: "no-op" language replaces "skipped" (AC-4 revised)
- INFO-13: `--with-source` removed from AC-6 (unnecessary for test env)
