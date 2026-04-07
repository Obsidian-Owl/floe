# Floe Developer Experience Audit

Snapshot: 2026-04-06T12:00:00Z
Scope: Full (architecture + consistency + debt), DX-focused
Trigger: Weeks of circular E2E failures; user suspects architectural drift from original vision
Prior audit: 2026-04-04 (findings carried forward where still relevant)

## Verdict: REJECTED

The platform has drifted significantly from its "two YAML files, just write SQL" vision. The E2E failures are symptoms of three reinforcing structural problems:

1. **Two divergent integration paths** — `create_definitions()` and `generate_entry_point_code()` produce structurally different Dagster integrations. The system has never been tested as a unified whole.
2. **Silent failure as a design pattern** — resource factories report success when critical subsystems are absent, making E2E tests non-deterministic.
3. **Premature scope** — 71K lines in floe-core, 22 plugin packages, 13K lines of OCI code, while the core use case ("YAML compiles to working pipeline") hasn't been proven end-to-end.

The core compilation logic — floe's actual value — is ~2,500 lines (3.5% of floe-core).

---

## Dimension: Architecture (DX Impact)

### DX-001 [BLOCKER] Generated definitions.py is a full program, not a thin shim

**Location**: `demo/customer-360/definitions.py:1-187`, `plugin.py:1100-1406`
**Vision drift**: Constitution Principle I (Technology Ownership). The generated code manually reads DuckDB tables, iterates schemas, calls PyIceberg APIs, handles Polaris namespace creation, and manages catalog connections. The orchestrator is doing storage's job.
**DX impact**: When Iceberg export fails (S3 endpoint mismatch, catalog auth, schema mismatch), the data engineer must debug a generated Python file they were told not to edit, spanning three systems simultaneously. 96% of the generated file is identical boilerplate across all products.
**Cascading**: YES — root cause of E2E instability. The export function re-reads `compiled_artifacts.json` at runtime (line 69), re-instantiates plugins via registry (line 78-89), duplicating what the plugin system already does.

### DX-002 [BLOCKER] Two divergent Dagster integration paths

**Location**: `plugin.py:183-287` (`create_definitions`) vs `plugin.py:1100-1406` (`generate_entry_point_code`)
**Vision drift**: Constitution Principle IV (Contract-Driven Integration). Two completely different code paths for the same outcome.
**DX impact**: `create_definitions()` creates per-model `@asset` with `dbt.run_models(select=name)`. `generate_entry_point_code()` creates a single `@dbt_assets` with `dbt.cli(["build"]).stream()`. These are NOT equivalent — different asset granularity, different execution model, different lineage emission. A data engineer debugging "works locally, fails in K8s" may not realize they're running different code.
**Cascading**: YES — the generated code does NOT use `create_definitions()`. They evolve independently.

### DX-003 [BLOCKER] Silent failure in resource creation — false success

**Location**: `resources/iceberg.py:177-185`, `resources/ingestion.py:116-130`, `resources/semantic.py:118-131`
**Vision drift**: Constitution Principle VIII (Observability By Default).
**DX impact**: When Polaris is unreachable, the resource factory returns `{}`. Dagster loads without Iceberg. dbt runs successfully. The Iceberg export silently does nothing. **The data engineer sees "pipeline succeeded" in Dagster UI with zero data in Iceberg.** No alert, no error, no warning in the UI. Only a DEBUG-level log message.
**Cascading**: YES — E2E tests are non-deterministic because resources may or may not be present depending on timing. Security gap: data bypasses governance controls when Iceberg is silently absent.

*Previously: ARC-004 (2026-04-04). Still present.*

### DX-004 [BLOCKER] PyIceberg 6-layer config merge — S3 endpoint corruption

**Location**: `floe_catalog_polaris/plugin.py:244-273`, `floe_iceberg/manager.py:206-213`
**DX impact**: Config passes through manifest.yaml → FloeSpec → CompiledArtifacts → PluginRegistry → PolarisCatalogPlugin.connect() → PyIceberg `_fetch_config` → Polaris server `table-default.*` overrides. Server overrides ALWAYS WIN. Client-side `s3.endpoint` silently replaced with K8s-internal hostnames. Root cause of the most time-consuming debugging sessions.

*Previously: ARC-003 (2026-04-04). Still present.*

### DX-005 [WARN] Plugin lifecycle — unsafe config=None window

**Location**: `packages/floe-core/src/floe_core/plugins/loader.py:160-172`, `plugin_registry.py:330-334`
**DX impact**: Plugins exist in an uninitialized state between load and configure. No `configure()` on the ABC, no state machine, no guard preventing `connect()` before configuration.

*Previously: ARC-001 (2026-04-04). Still present.*

### DX-006 [WARN] compiled_artifacts.json read 3 times per pipeline run

**Location**: `definitions.py:48` (_load_iceberg_resources), `definitions.py:69` (_export_dbt_to_iceberg), plus resource init
**Vision drift**: Principle IV — CompiledArtifacts should be read once and threaded through.
**DX impact**: If anything modifies the file between reads, the pipeline sees inconsistent configuration.

---

## Dimension: Consistency

### CON-001 [BLOCKER] try_create_* functions have 3 different failure semantics

**Location**: `resources/iceberg.py`, `lineage.py`, `ingestion.py`, `semantic.py`
**DX impact**: A developer cannot predict whether a misconfigured plugin will crash, silently degrade, or provide a NoOp fallback.

| Factory | On missing config | On exception |
|---------|-------------------|--------------|
| `try_create_iceberg_resources()` | Returns `{}` | **Re-raises** |
| `try_create_lineage_resource()` | Returns `{"lineage": NoOp}` | **Re-raises** |
| `try_create_ingestion_resources()` | Returns `{}` | **Swallows, returns `{}`** |
| `try_create_semantic_resources()` | Returns `{}` | **Re-raises** |

The `try_` prefix conventionally signals "safe, won't throw." Two of four violate this. Ingestion swallows all errors — data disappears silently.

### CON-002 [WARN] 4 distinct logging patterns in one package

**Location**: `plugins/floe-orchestrator-dagster/src/`
**DX impact**: Log output is inconsistent. A data engineer sees `lineage_emit_fail_failed` (tag-only, opaque) interleaved with `"Failed to create Iceberg resources"` (human-readable).
- Tag-only: `logger.warning("lineage_emit_start_failed", exc_info=True)` (6 occurrences)
- Full sentence: `logger.warning("No transforms found in artifacts, returning empty Definitions")` (3 occurrences)
- Structured: `logger.warning("lineage_emit_timeout", extra={"timeout": _EMIT_TIMEOUT})` (2 occurrences)
- Exception: `logger.exception("Failed to create Iceberg resources...")` (3 occurrences)

### CON-003 [WARN] Generated code tracked in git with no ownership clarity

**Location**: `demo/*/definitions.py`, no `demo/.gitignore`
**DX impact**: New developer sees `definitions.py` alongside `floe.yaml` and cannot tell which files to edit. The only signal is line 3: "AUTO-GENERATED — DO NOT EDIT." There is no `demo/AUTHORING.md` explaining authored vs generated files.

---

## Dimension: Configuration Debt

### DBT-001 [BLOCKER] Credentials hardcoded in 31 files

**Location**: 31 files containing `minioadmin` or `demo-secret`
**DX impact**: Rotating credentials (even for local dev) requires touching 31 files. Contradicts the project's own security standards. Trains developers to hardcode secrets.
**Evidence**: Spans `Makefile`, `charts/*/values*.yaml`, `testing/ci/*.sh`, `testing/k8s/secrets/`, `tests/e2e/*.py`, `testing/fixtures/minio.py`, plugin test files.

### DBT-002 [WARN] `floe-e2e` warehouse name hardcoded in 21 files

**Location**: 21 files across `charts/`, `tests/e2e/`, `demo/manifest.yaml`, `testing/ci/`, `.github/workflows/`
**DX impact**: Should be defined once in manifest.yaml and extracted by all consumers.

### DBT-003 [WARN] K8s service names hardcoded in 16 files

**Location**: 16 files containing `floe-platform-polaris` or `floe-platform-minio`
**DX impact**: Derived from Helm release name — should be computed, not copied.

### DBT-004 [WARN] Port numbers in 80+ files

**Location**: 81 files for `8181`, 50 files for `9000`
**DX impact**: Port conflicts on developer laptops require touching dozens of files.

---

## Dimension: Scope and Viability

### SCP-001 [BLOCKER] 71K-line floe-core — compilation is 3.5% of the package

**Location**: `packages/floe-core/src/floe_core/` (229 files, 71,181 lines)
**Vision drift**: Constitution says floe-core = "Schemas, validation, compilation." Actual contents:
- Compilation (the core function): ~2,500 lines (3.5%)
- Schemas: 11,491 lines (26 files)
- OCI registry: 13,217 lines (signing, verification, attestation, promotion, webhooks)
- Governance: 1,606 lines
- Enforcement: 6,359 lines
- RBAC: 2,853 lines
- Contracts/monitoring: 3,282 lines
- CLI: 8,505 lines
- Telemetry: 2,446 lines

**DX impact**: Any dependency change triggers a full rebuild. Import time is non-trivial. A data engineer debugging a compilation error navigates 229 files for 2,500 relevant lines.

### SCP-002 [WARN] 22 plugin packages for zero external users

**Location**: `plugins/` (22 packages)
**DX impact**: Docker build must COPY 24 individual `pyproject.toml` files. Adding a plugin requires editing Dockerfile, FLOE_PLUGINS arg, Makefile. 9 of 14 plugin categories have exactly 1 implementation — the abstraction has no current consumer.

### SCP-003 [WARN] dbt compiled 3 times for a single deployment

**Location**: `Makefile:338` (host), `Dockerfile:177-179` (container), runtime `dbt build`
**DX impact**: Step 2 exists solely because step 1 embeds host-absolute paths in manifest.json (P67). Not obvious from docs — appears as `make build-demo-image` which hides the prerequisite.

### SCP-004 [WARN] 22.5K-line testing framework with 14:1 test-to-source file ratio

**Location**: `testing/` (71 files, 22,545 lines)
**DX impact**: The testing framework has its own 26-file test suite. When an E2E test fails, it could be product code, test code, fixture code, port-forwards, or their interaction.

---

## Dimension: Documentation & Onboarding

### DOC-001 [WARN] No getting-started guide for data engineers

**Location**: Repository root, `docs/`
**DX impact**: No quickstart exists. Data engineer must piece together the flow from Makefile targets, demo README, and generated file headers.

### DOC-002 [WARN] 62 Makefile targets with no tiered grouping

**Location**: `Makefile` (671 lines)
**DX impact**: `make help` lists all targets equally. A data engineer needs ~5 of the 62.

### DOC-003 [INFO] Demo README doesn't explain two-file config model

**Location**: `demo/README.md`
**DX impact**: Mentions `floe.yaml` but not `manifest.yaml`. New contributor doesn't understand which file to modify.

---

## Structural Diagnosis

The E2E failures are symptoms of **architectural drift from vision**:

```
Vision: "Two YAML files → working pipeline"

Reality: manifest.yaml → FloeSpec → CompiledArtifacts → plugin.py
         → generate_entry_point_code() → 187-line definitions.py
         → module-load Polaris connection → Dagster loads (maybe)
         → dbt runs → DuckDB export → Iceberg write (silently skipped)
         
         Meanwhile: create_definitions() exists as a SEPARATE path
         that does the same thing differently.
```

The platform confused **extensibility** with **value**. Every abstraction layer taxes every contributor on every change. For alpha, the question isn't "is the plugin architecture elegant?" — it's "can a data engineer go from YAML to working pipeline without debugging generated Python?"

Currently: **no**.

---

## Recommended Path to Alpha

### Priority 1: Collapse the two Dagster paths (DX-001, DX-002)
Replace code generation with a runtime loader. One path, one codebase, one thing to debug. This is already designed (see `design.md` Option B).

### Priority 2: Make failures loud (DX-003, CON-001)
Standardize resource factory error handling. When Polaris is down, the pipeline MUST fail with a clear message, not silently succeed.

### Priority 3: Single source for config values (DBT-001, DBT-002, DBT-003)
Extract credentials, service names, and warehouse names to one location. Test infrastructure reads from manifest.

### Priority 4: Defer non-alpha scope (SCP-001, SCP-002)
The 13K OCI, 6K enforcement, 3K RBAC, and 3K contract monitoring lines are not needed for alpha. They can live in the repo but should not be in the critical path.

### Priority 5: Data engineer onboarding (DOC-001, CON-003)
Quickstart guide. Clear ownership markers for generated vs authored files.

---

## Known Gaps: Accepted

### SEC-001 — Marquez runs as root (UID 0)

**Dimension**: Security
**Severity**: WARN (accepted, not blocking)
**Location**: `charts/floe-platform/charts/marquez/` (subchart)
**Source**: `test-infra-convergence/security-hardening` AC-10

**Finding**: The upstream Marquez container image is built to run as root
(UID 0). Unlike the other platform subcharts (Dagster, OTel collector, Jaeger,
MinIO, PostgreSQL), Marquez cannot be hardened to comply with the Pod Security
Standards (PSS) Restricted profile without upstream changes.

**Upstream tracking**:
- GitHub issue: [MarquezProject/marquez#3060](https://github.com/MarquezProject/marquez/issues/3060)
- Status: Open, no fix timeline.

**Impact**:
- PSS Restricted profile cannot be enforced namespace-wide in `floe-*`
  namespaces while Marquez is present. Enforcement would cause Marquez pods
  to fail admission.
- The `tests/contract/test_helm_security_contexts.py` contract test explicitly
  excludes Marquez pods from security context assertions (see `MARQUEZ_NAME_MARKERS`
  in that file). Any new subchart added without hardening will still fail
  the contract test; only Marquez is exempt.

**Mitigation — accepted for now**:
- Marquez runs in the same namespace as the rest of the platform; we rely on
  PSS `baseline` profile (not `restricted`) at the namespace level.
- All other pods are PSS-restricted compliant, so the attack surface from
  Marquez's root user is contained to the Marquez container itself.
- Network policies (future work) will further scope Marquez's lateral reach.

**Future work**: A separate work unit will migrate Marquez to its own dedicated
namespace with a less-restrictive PSS level, allowing the rest of the platform
namespace to enforce PSS `restricted` uniformly. Not scheduled — depends on
upstream fix progress or an internal custom image build.

---

## Resolved (from prior audit)

### E2E-002 — Resolved by `e2e-test-optimization` (PR #227)
Module-scoped `dbt_pipeline_result` fixture replaces per-test seed/run calls.

### E2E-003 — Partially resolved by `e2e-test-optimization` (PR #227)
`test_plugin_system.py` relocated to unit tests. Two files descoped as E2E-adjacent.
