# Gate: Wiring
**Status**: PASS
**Timestamp**: 2026-04-15T15:15:00Z

## Checks

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | `@pytest.fixture(scope="module")` on `flux_suspended` | PASS | `testing/fixtures/flux.py:174` |
| 2 | Import in `test_helm_upgrade_e2e.py` | PASS | Line 25: `from testing.fixtures.flux import flux_suspended` |
| 3 | `flux_suspended` parameter on `test_helm_upgrade_succeeds` | PASS | Line 69: `def test_helm_upgrade_succeeds(self, flux_suspended: None)` |
| 4 | `_recover_suspended_flux_session` is session/autouse | PASS | `conftest.py:356-357` |
| 5 | `helm_release_health` depends on recovery fixture | PASS | `conftest.py:368`: parameter `_recover_suspended_flux_session: None` |
| 6 | `helm.py` Flux delegation path | PASS | `helm.py:115-136`: kubectl check + flux reconcile + fallback |
| 7 | No circular imports | PASS | flux.py imports only stdlib+pytest; helm.py imports only stdlib; conftest.py lazy-imports helm.py |

## Findings
None.
