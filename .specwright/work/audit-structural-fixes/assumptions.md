# Assumptions — Audit Structural Fixes

## A1: All plugins that require config accept it via __init__(config=...)

- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: Grep of all plugin `__init__` signatures shows Polaris, S3, DuckDB all take
  `config` parameter. The loader already handles the `config=None` fallback at `loader.py:168-170`.
  Adding `configure()` to ABC doesn't change how plugins receive config — it formalizes the
  second-phase push that `plugin_registry.py:330-334` already does.

## A2: manifest.yaml is always present at demo/manifest.yaml in test contexts

- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: `demo/manifest.yaml` is checked into git, present in all environments
  (local dev, DevPod, Kind in-cluster via Docker COPY). The testing/Dockerfile already
  copies the full workspace. The CI test-e2e.sh script runs from the repo root.

## A3: Module-scoped dbt fixtures provide sufficient test isolation

- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: Each product writes to its own Iceberg namespace (e.g., `customer_360`,
  `iot_telemetry`, `financial_risk`). Module scope means seed+run happens once per product
  per test file. Tests within the same file read from the same tables — they don't mutate
  them (seed is write-once, run is idempotent for non-incremental models).

## A4: PyYAML is available in test environments

- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: PyYAML is a transitive dependency of dbt-core, Dagster, and structlog.
  It's in the uv lockfile. Used by multiple test fixtures already.

## A5: The 48 non-E2E tests have no hidden K8s dependencies

- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: Research agent classified each file by analyzing imports and test bodies.
  `test_profile_isolation.py` tests file I/O on profiles.yml. `test_dbt_e2e_profile.py`
  tests dbt profile generation. `test_plugin_system.py` tests plugin discovery. None
  import K8s clients, make HTTP calls, or use ServiceEndpoint.

## A6: connect() is the only method that requires configured state

- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: Plugin methods that need config: `connect()` builds catalog connections,
  `get_pyiceberg_fileio()` reads S3 config. Both are called after `create_iceberg_resources()`
  which calls `registry.configure()` first. `health_check()` and `startup()` don't need config.
  The guard in `connect()` covers the critical path.
