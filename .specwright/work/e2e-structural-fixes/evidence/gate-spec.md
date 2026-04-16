# Gate: Spec Compliance

**Status**: PASS
**Timestamp**: 2026-03-30T14:20:00Z

## Results

- **Total criteria**: 23
- **Verified PASS**: 23
- **FAIL**: 0
- **WARN**: 0
- **Unit tests**: 8840 passed, 1 skipped, 87.44% coverage
- **Shellcheck**: Clean (no warnings)

## Criterion Summary

| # | Criterion | Status |
|---|-----------|--------|
| AC-1.1 | ServiceEndpoint for marquez URL | PASS |
| AC-1.2 | ServiceEndpoint for OTLP endpoint | PASS |
| AC-1.3 | K8s DNS resolution | PASS |
| AC-1.4 | Localhost fallback | PASS |
| AC-1.5 | Error messages use resolved endpoints | PASS |
| AC-2.1 | Script builds image | PASS |
| AC-2.2 | Script loads into Kind | PASS |
| AC-2.3 | Script deletes previous Job | PASS |
| AC-2.4 | Script submits Job | PASS |
| AC-2.5 | Script waits for completion | PASS |
| AC-2.6 | Script extracts results | PASS |
| AC-2.7 | Script exits non-zero on failure | PASS |
| AC-2.8 | Distinguishes failure from timeout | PASS |
| AC-2.9 | stderr for errors, [[ for conditionals | PASS |
| AC-2.10 | Makefile target exists | PASS |
| AC-3.1 | Dockerfile copies charts/ | PASS |
| AC-3.2 | _find_chart_root() resolves correctly | PASS |
| AC-3.3 | _find_repo_root() finds pyproject.toml | PASS |
| AC-3.4 | No absolute host paths | PASS |
| AC-4.1 | Fixture does not write profiles.yml | PASS |
| AC-4.2 | Compilation is in-memory | PASS |
| AC-4.3 | Demo profiles.yml unchanged after compilation | PASS |
| AC-4.4 | Write target is generated_profiles (if any) | PASS |

## Observation (non-blocking)

ServiceEndpoint constructs K8s DNS as `{service_name}.{namespace}.svc.cluster.local`
but Helm generates service names with release prefix (e.g., `floe-platform-marquez`).
Pre-existing design concern, not introduced by this spec's changes. Mitigated by
`{SERVICE}_HOST` env var overrides in the Job manifest.

## Findings

None.
