# Context: flux-test-fixtures

**Parent work**: flux-gitops-implementation
**Baseline commit**: 412b1c4 (origin/main)

## What This Unit Does

Integrate Flux awareness into the pytest test infrastructure. Provides crash-safe
suspend/resume fixtures for destructive tests, adds Flux controller health checks
to the E2E smoke check, and simplifies the existing Helm recovery fixture to
delegate to Flux when available.

## Key Files

| File | Lines | Role |
|------|-------|------|
| `testing/fixtures/helm.py` | 173 | `recover_stuck_helm_release()` — **modify to add Flux delegation** |
| `tests/e2e/conftest.py` | 1469 | Session fixtures: `helm_release_health()` (264-307), infra smoke check (227-260) — **modify** |
| `tests/e2e/test_helm_upgrade_e2e.py` | exists | Destructive Helm upgrade tests — **add flux_suspended dependency** |
| `testing/fixtures/flux.py` | NEW | `flux_suspended` fixture + Flux CLI helpers |
| `testing/fixtures/__init__.py` | exists | Package init — may need flux export |

## Design Decisions

- D10: Crash-safe `flux suspend`/`resume` via `request.addfinalizer()` (not yield-based try/finally)
- D11: Both Helm releases managed by Flux — fixtures must handle both
- WARN-7: Flux controller monitoring added to infrastructure smoke check

## Fixture Architecture

```
conftest.py (session scope)
  └── helm_release_health()
       ├── Check for suspended HelmRelease (crash recovery)
       ├── Resume if suspended
       └── Verify HelmRelease is Ready

testing/fixtures/flux.py (module scope)
  └── flux_suspended()
       ├── Detect Flux management (kubectl get helmrelease)
       ├── Suspend if managed
       ├── Register addfinalizer(_resume)
       └── Yield

testing/fixtures/helm.py
  └── recover_stuck_helm_release()
       ├── Check for Flux management
       ├── If Flux: flux reconcile (delegate)
       └── If no Flux: existing rollback path
```

## Testing Patterns Required

- Module-scoped fixture with `request.addfinalizer()` for crash-safety (not try/finally)
- Graceful degradation when `flux` CLI is not installed (subprocess returncode check)
- `subprocess.run` with `capture_output=True, text=True` for all kubectl/flux calls
- Best-effort cleanup MUST log (P56) — never bare `except Exception: pass`
- Guard kubectl return codes in fixtures (P37)

## Python Standards

- `from __future__ import annotations` at top
- Type hints on all functions and fixtures
- Google-style docstrings
- `structlog` for logging (not `logging`)

## Dependencies

- Requires Unit 1 (flux-kind-install) to be complete — Flux controllers must be
  installed in the cluster for integration tests to validate fixture behavior
