# Gate: Wiring

**Status**: PASS
**Timestamp**: 2026-04-08

## Scope
This work unit does not add or modify any plugin registrations, entry points,
or cross-package imports. The scope is pure test infrastructure:
- Helm chart templates moved under `charts/floe-platform/templates/tests/`
- Shell script helpers in `testing/ci/common.sh`
- One new contract test file under `tests/contract/`

## Plugin wiring
- No changes to `pyproject.toml` entry points
- No changes to `CompiledArtifacts` schema
- No changes to `floe-core`, `floe-dbt`, `floe-dagster`, or any plugin package
  `src/` trees

## Chart wiring (cross-template references)
AC-1 contract test verifies that every identifier referenced by test Jobs
(`serviceAccountName`, `valueFrom.secretKeyRef.name`, `valueFrom.configMapKeyRef.name`,
`envFrom[].secretRef.name`, `envFrom[].configMapRef.name`) resolves to a
resource produced by the same chart render. **11/11 wiring-related assertions
pass.**

## Single-source-of-truth wiring (AC-3)
`floe-platform.polaris.warehouse` helper reads `.Values.polaris.bootstrap.catalogName`
and is consumed by both:
1. Polaris bootstrap Job (catalog-create payload)
2. Test Jobs (`POLARIS_WAREHOUSE` env)

Sentinel-flip contract test proves both sites change in lockstep when the
values key is overridden.

## Verdict
PASS. No plugin or cross-package wiring changes; intra-chart wiring verified
by tripwire.
