# Design: Audit Structural Fixes

## Problem

Recurring E2E failures across 20+ shipped work units. The audit (AUDIT.md) identified
4 reinforcing structural root causes — not random bugs but design gaps that make every
fix fragile. Each fix targets a specific, located problem.

## Approach

Four focused fixes, ordered by dependency. No architectural rewrites — make the existing
abstractions work correctly.

---

## Fix 1: Plugin Lifecycle — Add `configure()` to ABC

### What

Add a `configure(config: BaseModel | None)` method to the `PluginMetadata` ABC with a
default implementation. Replace the reflection-based config push in `plugin_registry.py`
with a method call. Add a guard in plugin `connect()` methods.

### Where

| File | Change |
|------|--------|
| `packages/floe-core/src/floe_core/plugin_metadata.py` | Add `configure()` method to ABC |
| `packages/floe-core/src/floe_core/plugin_registry.py:330-334` | Replace `hasattr` + `_config` mutation with `plugin.configure(validated_config)` |
| `packages/floe-core/src/floe_core/plugins/loader.py:160-176` | After instantiation, plugin starts in unconfigured state (no change needed — already passes None) |
| `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | Add guard in `connect()`: raise if `_config is None` |
| `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py` | Same guard in storage access methods |

### How

```python
# plugin_metadata.py — initialize _config in ABC __init__
class PluginMetadata(ABC):
    def __init__(self) -> None:
        self._config: BaseModel | None = None  # Unconfigured state

    def configure(self, config: BaseModel | None) -> None:
        """Accept validated configuration.

        Called by the registry after config validation. Subclasses may override
        for custom config handling.

        Args:
            config: Validated Pydantic model, or None to clear config.
        """
        self._config = config

    @property
    def is_configured(self) -> bool:
        """Whether this plugin has been configured."""
        return self._config is not None

# plugin_registry.py — replace lines 330-334
# Before:
#   if hasattr(plugin, "_config"):
#       plugin._config = validated_config
# After:
plugin.configure(validated_config)

# polaris plugin.py — guard in connect()
def connect(self, config: dict[str, Any] | None = None) -> RestCatalog:
    if self._config is None:
        raise PluginConfigurationError(
            self.name,
            [{"field": "_config", "message": "Plugin not configured. Call registry.configure() before connect().", "type": "missing"}],
        )
    # ... existing connect logic
```

**Critical detail**: The ABC initializes `self._config = None` in `__init__`. This means:
- Plugins that currently accept `config` in `__init__` must call `super().__init__()` first,
  then set `self._config = config` (or defer to `configure()`).
- The `loader.py:164-170` fallback (`plugin_class(config=None)`) continues to work — the
  plugin's `__init__` calls `super().__init__()`, which sets `_config = None`. The registry
  later calls `plugin.configure(validated_config)` to push real config.
- `self._config` is always a declared instance attribute, never a dynamically created one.
  The `connect()` guard checks `self._config is None` — this is an attribute check, not
  reflection, and will never raise `AttributeError`.

### Why this fixes ARC-001

The unsafe config window existed because:
1. No ABC contract for config acceptance (reflection-based)
2. No guard preventing `connect()` before configuration
3. `_config` was a dynamically created attribute, not an ABC-declared one
4. Any new consumer path that skips `registry.configure()` gets garbage

After this fix: `_config` is declared by the ABC `__init__`. `configure()` is an explicit
method. `connect()` raises immediately if called before configuration. `is_configured`
property provides a safe check without reflection.

---

## Fix 2: Config Source of Truth — Manifest-Driven Test Infrastructure

### What

Create a manifest config extractor that test infrastructure reads instead of hardcoding
values. `test-e2e.sh` and `conftest.py` derive ALL configurable values from `demo/manifest.yaml`.

### Where

| File | Change |
|------|--------|
| `testing/ci/extract-manifest-config.py` | New — reads manifest.yaml, outputs shell-evaluable vars |
| `testing/ci/test-e2e.sh:388,416-418,455-489` | Replace hardcoded values with extracted vars |
| `tests/e2e/conftest.py` | Replace hardcoded credential defaults with manifest-derived values |

### How

```python
# testing/ci/extract-manifest-config.py
"""Extract config from manifest.yaml for test infrastructure.

Usage: eval "$(python3 testing/ci/extract-manifest-config.py demo/manifest.yaml)"

Outputs shell variables:
  MANIFEST_BUCKET, MANIFEST_REGION, MANIFEST_PATH_STYLE_ACCESS,
  MANIFEST_WAREHOUSE, MANIFEST_OAUTH_CLIENT_ID, MANIFEST_OAUTH_SCOPE,
  MANIFEST_S3_ENDPOINT, MANIFEST_POLARIS_URI
"""
import sys
import yaml
from pathlib import Path

manifest_path = Path(sys.argv[1])
manifest = yaml.safe_load(manifest_path.read_text())

plugins = manifest.get("plugins", {})
storage = plugins.get("storage", {}).get("config", {})
catalog = plugins.get("catalog", {}).get("config", {})
oauth = catalog.get("oauth2", {})

pairs = {
    "MANIFEST_BUCKET": storage.get("bucket", "floe-data"),
    "MANIFEST_REGION": storage.get("region", "us-east-1"),
    "MANIFEST_PATH_STYLE_ACCESS": str(storage.get("path_style_access", True)).lower(),
    "MANIFEST_S3_ENDPOINT": storage.get("endpoint", ""),
    "MANIFEST_WAREHOUSE": catalog.get("warehouse", ""),
    "MANIFEST_POLARIS_URI": catalog.get("uri", ""),
    "MANIFEST_OAUTH_CLIENT_ID": oauth.get("client_id", ""),
    "MANIFEST_OAUTH_SCOPE": oauth.get("scope", ""),
}

for key, value in pairs.items():
    # Shell-safe: single-quote values, escape embedded single quotes
    safe = str(value).replace("'", "'\\''")
    print(f"export {key}='{safe}'")
```

In `test-e2e.sh`:
```bash
# Near top, after SCRIPT_DIR detection:
eval "$(python3 "${SCRIPT_DIR}/extract-manifest-config.py" "${REPO_ROOT}/demo/manifest.yaml")"

# Replace hardcoded defaults:
MINIO_BUCKET="${MINIO_BUCKET:-${MANIFEST_BUCKET}}"       # was: floe-iceberg
POLARIS_CATALOG="${POLARIS_CATALOG:-${MANIFEST_WAREHOUSE}}"  # was: floe-e2e
POLARIS_CLIENT_ID="${POLARIS_CLIENT_ID:-${MANIFEST_OAUTH_CLIENT_ID}}"  # was: demo-admin
```

In catalog creation JSON (lines 455-489), replace hardcoded `'us-east-1'` and `'true'`
with `MANIFEST_REGION` and `MANIFEST_PATH_STYLE_ACCESS`.

In `conftest.py`, add manifest reading to derive defaults:
```python
def _read_manifest_config() -> dict[str, Any]:
    """Read config from demo/manifest.yaml for E2E fixture defaults."""
    manifest_path = Path(__file__).parent.parent.parent / "demo" / "manifest.yaml"
    if manifest_path.exists():
        import yaml
        return yaml.safe_load(manifest_path.read_text())
    return {}
```

### Why this fixes ARC-002

Config values are defined in ONE place (manifest.yaml) and consumed by both the
production pipeline (via compilation) and the test infrastructure (via extraction).
No more divergence. When someone changes the bucket name in manifest.yaml, tests
automatically use the new name.

**Legitimate divergences** remain intentional: S3 endpoint and Polaris URI differ
between K8s-internal and port-forwarded access. These are TRANSPORT differences,
not config differences. The manifest has K8s-internal hostnames; test scripts
translate to localhost:port for port-forwarded access.

---

## Fix 3: E2E Test Optimization — Module-Scoped dbt Fixtures

### What

Replace per-test `dbt seed` + `dbt run` calls with module-scoped pytest fixtures.
Move 48 non-E2E tests out of `tests/e2e/` to appropriate unit directories.

### Where

| File | Change |
|------|--------|
| `tests/e2e/test_data_pipeline.py` | Replace inline dbt calls with `dbt_pipeline_result` fixture |
| `tests/e2e/conftest.py` | Add `dbt_seeded_product` and `dbt_pipeline_result` module-scoped fixtures |
| `tests/e2e/test_profile_isolation.py` | Move to `packages/floe-dbt/tests/unit/` |
| `tests/e2e/test_dbt_e2e_profile.py` | Move to `packages/floe-dbt/tests/unit/` |
| `tests/e2e/test_plugin_system.py` | Move to `packages/floe-core/tests/unit/` |

### How

New fixtures in `tests/e2e/conftest.py`:
```python
@pytest.fixture(scope="module")
def dbt_seeded_product(
    request: pytest.FixtureRequest,
    dbt_e2e_profile: Path,
) -> tuple[str, Path]:
    """Seed a demo product's data once per test module.

    Returns (product_name, project_dir) after successful dbt seed.
    """
    product = request.param  # parametrized by test module
    project_dir = Path("demo") / product
    result = run_dbt(["seed"], project_dir)
    assert result.returncode == 0, f"dbt seed failed for {product}"
    return product, project_dir


@pytest.fixture(scope="module")
def dbt_pipeline_result(
    dbt_seeded_product: tuple[str, Path],
) -> tuple[str, Path]:
    """Run dbt models once per test module, after seeding.

    Returns (product_name, project_dir) after successful dbt run.
    """
    product, project_dir = dbt_seeded_product
    result = run_dbt(["run"], project_dir)
    assert result.returncode == 0, f"dbt run failed for {product}"
    return product, project_dir
```

In `test_data_pipeline.py`, tests that currently call `dbt seed` + `dbt run` inline
switch to requesting `dbt_pipeline_result` fixture:

```python
# Before (repeated in each test):
# seed_result = run_dbt(["seed"], project_dir)
# assert seed_result.returncode == 0
# result = run_dbt(["run"], project_dir)
# assert result.returncode == 0

# After:
@pytest.mark.parametrize("dbt_seeded_product", ALL_PRODUCTS, indirect=True)
class TestDataPipelineExecution:
    def test_seed_creates_tables(self, dbt_pipeline_result):
        product, project_dir = dbt_pipeline_result
        # ... verify tables exist (seed already happened)

    def test_medallion_transforms(self, dbt_pipeline_result):
        product, project_dir = dbt_pipeline_result
        # ... verify bronze/silver/gold (run already happened)
```

**Isolation guarantees**:
- Each product writes to its own Iceberg namespace (`customer_360`, `iot_telemetry`,
  `financial_risk`) — no cross-product contamination.
- The `dbt_seeded_product` fixture uses a module-unique namespace suffix
  (`{product}_{module_hash[:8]}`) to prevent contamination between test files
  that parametrize the same product.
- Tests within a module are read-only consumers of seed+run output. Tests that MUTATE
  table state (e.g., incremental merge tests, schema evolution tests) get their own
  function-scoped fixture that creates a throwaway namespace, not the shared one.
- Fixture teardown (via `yield` + `finally`) purges the module namespace via
  `_purge_iceberg_namespace()` from `dbt_utils.py`, ensuring no state leaks between
  test modules.

```python
@pytest.fixture(scope="module")
def dbt_pipeline_result(
    request: pytest.FixtureRequest,
    dbt_e2e_profile: Path,
) -> Generator[tuple[str, Path], None, None]:
    product = request.param
    # Unique namespace per module to avoid cross-module pollution
    module_hash = hashlib.md5(request.module.__name__.encode()).hexdigest()[:8]
    namespace = f"{product.replace('-', '_')}_{module_hash}"
    project_dir = Path("demo") / product

    # Seed + Run
    os.environ["FLOE_ICEBERG_NAMESPACE"] = namespace
    assert run_dbt(["seed"], project_dir).returncode == 0
    assert run_dbt(["run"], project_dir).returncode == 0

    yield product, project_dir

    # Cleanup: purge namespace
    try:
        _purge_iceberg_namespace(namespace)
    except Exception:
        logger.warning("namespace_cleanup_failed", namespace=namespace)
```

**Runtime impact**: ~24 dbt cycles → ~3 (one per product). At 2-5 minutes per cycle,
this saves 40-100 minutes. Target suite time: under 15 minutes.

**Test relocation**: The 3 non-E2E files move to package-level unit directories with
minimal changes (update imports, remove K8s fixtures). Saves ~15-20 minutes of E2E time.

### Why this fixes E2E-002

Redundant dbt invocations are the primary driver of the 73-minute suite. The long
runtime is what makes port-forward failures inevitable (E2E-001). By reducing to 3
cycles, the suite fits within the port-forward reliability window.

---

## Fix 4: Fail-Fast on Startup

### What

Make `try_create_iceberg_resources()` re-raise exceptions when plugins are configured
but fail, instead of catching everything and returning `{}`.

### Where

| File | Change |
|------|--------|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:187-197` | Re-raise when configured |

### How

```python
# Before:
def try_create_iceberg_resources(...) -> dict[str, Any]:
    # ... None guards (these stay — legitimate "not configured" cases) ...
    try:
        return create_iceberg_resources(...)
    except Exception:
        logger.exception("Failed to create Iceberg resources")
        return {}

# After:
def try_create_iceberg_resources(...) -> dict[str, Any]:
    # ... None guards stay (catalog/storage not configured = no Iceberg, OK) ...
    try:
        return create_iceberg_resources(
            catalog_ref=plugins.catalog,
            storage_ref=plugins.storage,
            governance=governance,
        )
    except Exception:
        logger.exception(
            "Failed to create Iceberg resources — catalog and storage ARE configured "
            "but resource creation failed. This is a startup error, not a missing feature."
        )
        raise  # Fail fast — configured plugins MUST work
```

### Why this fixes ARC-004

The current catch converts startup failures to runtime mysteries. When catalog and
storage plugins ARE configured in the manifest, a failure to create resources means
something is broken (wrong credentials, unreachable endpoint, schema mismatch). That
should fail loudly at startup, not silently degrade into "resource 'iceberg' not found"
errors minutes later during asset materialization.

The `None` guards remain for the legitimate case where Iceberg isn't configured at all.

---

## Blast Radius

### Modules/files the design touches

| File | Change Type | Propagation |
|------|-------------|-------------|
| `plugin_metadata.py` | Add method to ABC | **Systemic** — all plugins inherit, but default impl means no breakage |
| `plugin_registry.py:330-334` | Replace 3 lines | **Adjacent** — all config push goes through here |
| `loader.py` | No change needed | N/A |
| `polaris/plugin.py` | Add guard in connect() | **Local** — only affects Polaris connect path |
| `s3/plugin.py` | Add guard in storage methods | **Local** — only affects S3 access path |
| `iceberg.py:187-197` | Change catch to raise | **Adjacent** — Dagster startup behavior changes |
| `test-e2e.sh:388,416-489` | Replace hardcoded with vars | **Local** — test infrastructure only |
| `extract-manifest-config.py` | New file | **Local** — additive |
| `conftest.py` | Add module-scoped fixtures | **Adjacent** — E2E tests must adopt new fixtures |
| `test_data_pipeline.py` | Refactor to use fixtures | **Local** — internal to test file |
| 3 test files | Move directories | **Local** — test organization only |

### What this design does NOT change

- Plugin discovery or entry point mechanism
- CompiledArtifacts schema or compilation pipeline
- Helm charts or K8s deployment
- Dagster asset definitions or IO managers
- Production configuration or manifest schema
- Port-forward management or SSH tunnels
- CI pipeline (GitHub Actions)
- Any existing test assertions (only where dbt calls are invoked)

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| `configure()` default impl breaks a plugin that does custom `__init__` config handling | Low | Default impl just sets `_config` — same as current reflection. Plugin-specific overrides possible. |
| Fail-fast raise breaks Dagster startup in non-Iceberg deployments | Low | `None` guards handle "not configured". Only raises when configured-but-broken. |
| Module-scoped fixtures hide test isolation bugs | Medium | Each product writes to its own namespace. Add explicit namespace isolation check in fixture teardown. |
| Manifest extractor breaks on schema changes | Low | Extractor reads well-known paths (`plugins.storage.config.bucket`). Schema changes are rare and intentional. |
| Moved tests have different conftest.py available | Medium | Review imports before moving. Create appropriate conftest.py in destination if needed. |

## WARNs

1. **Module-scoped fixture teardown**: Resolved — fixture uses `yield` + `finally` block
   with `_purge_iceberg_namespace()`. Cleanup runs even on test failure.
2. **Manifest extractor validation**: The extractor MUST validate that required keys exist.
   If `plugins.storage` or `plugins.catalog` is missing, fail with a clear error rather
   than emitting empty defaults. Add: `assert storage, f"manifest.yaml missing plugins.storage.config"`.
3. **Backward compatibility**: `configure()` on ABC changes the interface for ALL plugins.
   Since floe is pre-alpha with no external plugins, this is acceptable. Document in
   CHANGELOG when shipped.
4. **Partial configuration** (WARN from critic): If `plugins.catalog` is set but
   `plugins.storage` is `None`, `try_create_iceberg_resources()` returns `{}` via the
   existing None guard. This is intentional — catalog-only or storage-only configs are
   incomplete for Iceberg, and the function is correctly named "try". The fail-fast raise
   only applies when BOTH are configured and the creation fails.
5. **Error propagation order** (WARN from critic): If `registry.configure()` raises
   `PluginConfigurationError` for a catalog plugin, that exception propagates through
   `create_iceberg_resources()` and is now re-raised by `try_create_iceberg_resources()`.
   The error message will correctly indicate a configuration failure, not a "not configured"
   guard. The `connect()` guard is a second line of defense for cases where configure
   succeeds but another code path calls connect on a different, unconfigured plugin.
