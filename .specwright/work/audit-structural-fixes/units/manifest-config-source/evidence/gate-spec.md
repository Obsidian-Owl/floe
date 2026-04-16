# Gate: Spec Compliance
**Status**: PASS
**Ran**: 2026-04-04T21:05:00Z

## AC-1: Manifest extractor outputs shell-evaluable config

| # | Condition | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Script accepts manifest path as argument | PASS | `main()` reads `sys.argv[1]`, tested by `test_cli_with_valid_manifest` |
| 2 | Output is valid shell | PASS | `test_cli_output_sets_env_vars_via_shell` runs actual bash eval |
| 3 | Exports 6 required variables | PASS | `test_returns_all_six_required_keys` checks exact key set |
| 4 | Values match manifest exactly | PASS | `TestExtractConfigMatchesRealManifest` cross-checks + parameterized anti-hardcoding |
| 5 | Fails if plugins.storage missing | PASS | `test_error_missing_storage` |
| 6 | Fails if manifest not found | PASS | `test_error_file_not_found` + `test_error_directory_instead_of_file` |
| 7 | Single-quoted prevents injection | PASS | `test_injection_output_is_safe_under_bash` |

## AC-2: test-e2e.sh reads config from manifest

| # | Condition | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Calls eval with extractor early | PASS | `test_eval_line_present` + ordering tests |
| 2 | MINIO_BUCKET defaults to MANIFEST_BUCKET | PASS | `test_minio_bucket_uses_manifest_default` |
| 3 | POLARIS_CATALOG defaults to MANIFEST_WAREHOUSE | PASS | `test_polaris_catalog_uses_manifest_default` |
| 4 | POLARIS_CLIENT_ID defaults to MANIFEST_OAUTH_CLIENT_ID | PASS | `test_polaris_client_id_uses_manifest_default` |
| 5 | Catalog JSON uses MANIFEST_REGION/PATH_STYLE | PASS | `TestCatalogJsonRegion` + `TestCatalogJsonPathStyleAccess` |
| 6 | Env var overrides still work | PASS | `TestEnvVarOverridePreserved` |
| 7 | Changing manifest bucket changes behavior | PASS | Transitive: extractor reads real values + shell uses extractor output |

## AC-3: conftest.py derives credential defaults from manifest

| # | Condition | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `_read_manifest_config()` helper exists | PASS | AST check + static verification |
| 2 | Default credential from manifest oauth2 | PASS | No hardcoded `demo-admin:demo-secret` assignments |
| 3 | Default scope from manifest | PASS | No bare `PRINCIPAL_ROLE:ALL` scope literals |
| 4 | Env var overrides take precedence | PASS | `os.environ.get` patterns preserved |
| 5 | Fallback with warning on missing manifest | PASS | `test_missing_manifest_returns_defaults_with_warning` |

## Summary
- 19/19 acceptance criteria conditions: PASS
- 82 tests across 3 test files
- Post-build review: APPROVED (2 non-blocking WARNs documented in as-built notes)
