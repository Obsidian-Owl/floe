# Post-Composition Strict MinIO Cleanup Validation

Date: 2026-05-09
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `main`

## Scope

This note records the local Wave 1 validation baseline after removing stale Floe storage plugin `s3` identity references and preserving protocol-level S3-compatible configuration for MinIO-backed Polaris/Iceberg runtime behavior.

## Command Ledger

| Command | Result |
| --- | --- |
| `uv run pytest packages/floe-core/tests/unit/plugins/test_plugin_system.py -q` | Passed: `9 passed, 1 xfailed in 1.75s`. No failure output referenced `floe_storage_s3.plugin`. |
| `make test-unit` | Passed: `10487 passed, 1 skipped, 1 xfailed, 6 warnings in 194.30s`; coverage `87.44%`. |
| `uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py -q` | Passed: `45 passed in 0.25s`. |
| `helm unittest charts/floe-platform` | Passed: `17 passed` test suites, `184 passed` tests. |
| `make lint` | Passed: Ruff reported all checks passed and `1256 files already formatted`. |
| `make typecheck` | Passed: `Success: no issues found in 358 source files`. |

## Result

Local unit, Helm renderer, lint, and typecheck gates are green on `main` for the strict MinIO cleanup baseline.

The stale Floe storage plugin identity `s3` is no longer required by the plugin-system path that previously failed during audit; the focused plugin-system test passes without attempting to load `floe_storage_s3.plugin`.

S3-compatible protocol configuration remains intentionally preserved where it belongs: Polaris and Iceberg still use S3 protocol fields such as endpoint, region, path-style access, and bucket settings for MinIO-compatible object storage. Those fields are storage protocol configuration, not Floe plugin identity.
