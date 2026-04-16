# Plan: Unit 1 — Config Fixes

## Tasks

1. Add `GHSA-gc5v-m9x4-r6x2` to `.vuln-ignore` with rationale comment
2. Change `path` to `:memory:` in `demo/customer-360/profiles.yml`
3. Change `path` to `:memory:` in `demo/iot-telemetry/profiles.yml`
4. Change `path` to `:memory:` in `demo/financial-risk/profiles.yml`
5. Verify with grep that no `demo.duckdb` references remain

## File change map

| File | Action | Lines |
|------|--------|-------|
| `.vuln-ignore` | EDIT — append CVE entry with comment | +3-4 lines at end |
| `demo/customer-360/profiles.yml` | EDIT — change path value | line 6 |
| `demo/iot-telemetry/profiles.yml` | EDIT — change path value | line 6 |
| `demo/financial-risk/profiles.yml` | EDIT — change path value | line 6 |

## Verification

```bash
# AC-1
grep GHSA-gc5v-m9x4-r6x2 .vuln-ignore

# AC-2
grep -r 'path:.*demo.duckdb' demo/  # expect: no output
grep -r 'path:.*:memory:' demo/     # expect: 3 matches

# AC-3
git diff --stat  # expect: 4 files changed
```
