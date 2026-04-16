# Decisions — Audit Structural Fixes

## D1: Option B — Fix within current architecture (not radical scope reduction)

**Rule**: DISAMBIGUATION — user explicitly chose Option B when presented with audit findings.
**Choice**: Make the abstractions work rather than removing them.
**Why**: User stated "A clear roadmap outlining how we ensure the abstractions work" and "the
abstractions are sound; the wiring has specific bugs." The plugin architecture is the project's
value proposition.

## D2: Plugin lifecycle — add configure() to ABC, not state machine

**Rule**: DISAMBIGUATION — simplest solution that closes the gap.
**Choice**: Add a `configure(config: BaseModel)` method to `PluginMetadata` ABC with a default
implementation that sets `self._config`. This replaces the reflection-based `hasattr(plugin, "_config")`
in `plugin_registry.py:330-334`.
**Why**: A full state machine (loaded→configured→active) adds complexity beyond what's needed.
The concrete problem is that `_config` mutation happens via reflection. Making `configure()` an
ABC method makes the contract explicit. Plugins that need custom config handling override it.
A guard in `connect()` that raises if `_config is None` prevents the unsafe window.
**Alternative rejected**: Full state machine with enum states — overkill for pre-alpha where
there's one consumer path (`create_iceberg_resources`).

## D3: Config source of truth — manifest extraction helper, not full compilation

**Rule**: DISAMBIGUATION — test infrastructure should read from manifest, not redefine.
**Choice**: Create a `testing/ci/manifest-config.py` helper that reads `demo/manifest.yaml`
and exports specific values (bucket, region, path_style_access, oauth scope, credentials) as
environment variables or shell-evaluable output. `test-e2e.sh` sources this instead of
hardcoding values.
**Why**: Full compilation (`floe compile`) is too heavy for bash script infrastructure setup.
The manifest is YAML — a simple Python script with PyYAML reads the values needed. This gives
a single source of truth without coupling test infrastructure to the compilation pipeline.
**Alternative rejected**: Bash-native YAML parsing (fragile), `yq` dependency (not in devcontainer).

## D4: dbt fixture sharing — module-scoped fixtures, not shared utility

**Rule**: DISAMBIGUATION — user said "optimise processing to run at the right time, in the
right order. Not 8 times when it could be 1 time."
**Choice**: Create module-scoped pytest fixtures (`dbt_seeded_product`) that run `dbt seed` +
`dbt run` once per product per test module. Tests within a module share the fixture.
**Why**: Module-scoped is the right granularity — session-scoped is too coarse (test isolation
breaks if one product's run corrupts another's state), function-scoped is the status quo (redundant).
Module scope runs once per file, and the test file is already organized by product via parametrize.
**Alternative rejected**: Session-scoped fixture (cross-product contamination risk), custom
caching utility (framework complexity).

## D5: Fail-fast — raise when plugins are configured but fail, not unconditionally

**Rule**: DISAMBIGUATION — distinguishing "no plugins configured" (graceful) from "plugins
configured but broken" (fail-fast).
**Choice**: `try_create_iceberg_resources()` returns `{}` when `plugins.catalog is None` or
`plugins.storage is None` (no Iceberg configured — legitimate). But when both ARE configured
and `create_iceberg_resources()` raises, re-raise the exception instead of catching it.
**Why**: The current blanket catch masks configuration errors. The function already has
explicit `None` guards for the "not configured" case. When configured plugins fail, that's a
startup error that should surface immediately, not after the first asset run.
**Alternative rejected**: Always raise (breaks deployments without Iceberg), always warn
(status quo — hides real errors).

## D6: Non-E2E test relocation — move to package-level unit tests

**Rule**: DISAMBIGUATION — test organization rules say tests importing from single package
go in package-level directories.
**Choice**: Move `test_profile_isolation.py`, `test_dbt_e2e_profile.py`, `test_plugin_system.py`
out of `tests/e2e/` to appropriate package-level `tests/unit/` directories.
**Why**: These 48 tests don't need K8s, port-forwards, or any infrastructure. Running them
in the E2E suite adds ~15-20 minutes to the runtime and increases the port-forward exposure
window. Moving them to unit tests means they run in `make test-unit` (fast, reliable).

## Planning Phase Decisions

## D7: Decompose into 3 work units (not 1 or 4)

**Rule**: DISAMBIGUATION — design blast radius assessment.
**Choice**: 3 units: (1) plugin-lifecycle-fix (Fix 1 + Fix 4), (2) manifest-config-source
(Fix 2), (3) e2e-test-optimization (Fix 3). Fix 1 and Fix 4 are in the same unit because
the `connect()` guard (Fix 1) is what makes fail-fast (Fix 4) meaningful.
**Why**: Fix 1 has systemic blast radius (touches ABC, 11 plugins, registry, tests). Fixes
2 and 3 are local/adjacent and independent. Each unit is independently buildable and testable.
4 separate units would create unnecessary overhead for Fix 4 (3 lines of change).

## D8: Unit order — lifecycle first, config and optimization parallel

**Rule**: DISAMBIGUATION — dependency analysis.
**Choice**: Unit 1 must be built first (foundational). Units 2 and 3 are independent and
can be built in either order after Unit 1.
**Why**: Unit 1's ABC changes could theoretically affect test expectations in Units 2/3.
Building it first ensures a stable foundation. Units 2 and 3 don't depend on each other.
