# Specwright Patterns

Reusable patterns discovered during work units. Promoted by `/sw-learn`.

---

## P1: Autouse Fixture Scoping (WU-6)

**Context**: Module-level `autouse=True` fixtures silently run for ALL tests in a file, even those that don't need mocking.

**Pattern**: Scope `autouse=True` to the narrowest applicable level. Use class-level `_apply_mocks` fixtures:

```python
# Module level: NOT autouse
@pytest.fixture
def mock_compute_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock compute plugin discovery."""
    ...

# Class level: autouse scoped to class
class TestCompilePipeline:
    @pytest.fixture(autouse=True)
    def _apply_mocks(self, mock_compute_plugin: Any) -> None:
        """Apply plugin mocks for this class only."""

class TestCompilationStage:
    # No _apply_mocks — this class tests enums, no mocking needed
    ...
```

**Hierarchy**: class > module > session. Always pick the narrowest scope.

---

## P2: Circular Import Management for Plugin ABCs (WU-6)

**Context**: Adding a plugin ABC that imports from a module that also imports from `plugins/` creates circular imports.

**Pattern**:
1. Add `from __future__ import annotations` to the module importing the plugin ABC
2. Guard the import with `if TYPE_CHECKING:`
3. Exclude the plugin from `plugins/__init__.py` with an explanatory comment
4. Document the direct import path for consumers

```python
# alert_router.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from floe_core.plugins.alert_channel import AlertChannelPlugin

# plugins/__init__.py
# AlertChannelPlugin: imported directly from floe_core.plugins.alert_channel
# (omitted from __all__ to avoid circular import with alert_router)
```

**When to apply**: Any plugin ABC whose module has bidirectional imports with `plugins/`.

---

## P3: Verify-Fix-Reverify Cycle (WU-6)

**Context**: First verification of WU-6 found 27 findings (4B/17W/6I). Fixing them ad-hoc would be error-prone.

**Pattern**: When gate findings exceed 5 WARN:
1. Create a structured cleanup plan grouping fixes by commit scope
2. Commit order: source hardening first (adds exports tests may reference), then test tiers independently
3. Re-verify after all fixes to confirm resolution

**Commit grouping**:
| # | Scope | Contains |
|---|-------|----------|
| 1 | Source hardening | Validation, logging, re-exports |
| 2 | Unit test cleanup | Fixture extraction, assertion strengthening |
| 3 | Contract test hardening | Exception narrowing, redundancy removal |
| 4-5 | E2E test cleanup | One commit per E2E test file |

**Why**: Structured plans prevent fix-introduces-new-finding loops and make re-verification tractable.

---

## P4: Re-export Public API Functions (WU-6)

**Context**: `compile_pipeline` was importable from `floe_core.compilation` but `run_enforce_stage` required the deep path `floe_core.compilation.stages`.

**Pattern**: Primary public API functions MUST be re-exported from the package `__init__.py` and listed in `__all__`.

```python
# compilation/__init__.py
from floe_core.compilation.stages import (
    CompilationStage,
    compile_pipeline,
    run_enforce_stage,
)

__all__ = [
    "CompilationStage",
    "compile_pipeline",
    "run_enforce_stage",
]
```

**Test**: If a function is called by code outside its package, it should be importable from the package root. Gate-wiring checks for this.

---

## P5: Health Check Strict Status Validation (WU-8)

**Context**: `wait_for_service` treated any `status_code < 500` as healthy. A 401 or 404 from a misconfigured endpoint would pass the health check.

**Pattern**: Default to lenient (`< 500`) for general service liveness, but use `strict_status=True` for health-readiness endpoints that return well-defined status codes.

```python
def wait_for_service(
    url: str,
    timeout: float = 60.0,
    *,
    strict_status: bool = False,  # Default: any non-5xx
) -> None:
    def check_http() -> bool:
        response = httpx.get(url, timeout=5.0)
        if strict_status:
            return response.status_code == 200  # Exact match
        return response.status_code < 500  # Lenient

# Usage:
wait_for_service(mgmt_url, strict_status=True)   # Health endpoint: exact 200
wait_for_service(api_url)                          # General liveness: any non-5xx
```

**When to apply**: Quarkus `/q/health/ready`, K8s `/healthz`, any endpoint with defined ready/not-ready semantics.

---

## P6: Test Migration Must Preserve Coverage (WU-8)

**Context**: Migrating Polaris test from port 8181 to 8182 deleted HTTP validation of the catalog API port. The old coverage disappeared silently.

**Pattern**: When migrating a test assertion to a new endpoint/target, always verify the old target is still tested elsewhere. If not, test BOTH.

```python
# WRONG: Replace old with new (coverage subtracted)
core_services = [
    ("http://localhost:8182/q/health/ready", "Polaris health"),  # New
]

# RIGHT: Test both (coverage preserved)
core_services = [
    ("http://localhost:8181/api/catalog/v1/config", "Polaris catalog API"),  # Old
    ("http://localhost:8182/q/health/ready", "Polaris management health"),   # New
]
```

**Audit question**: "What did the old test catch that the new one doesn't?"

---

## P7: Single-PID Multi-Port kubectl Port-Forward (WU-8)

**Context**: Two separate `kubectl port-forward` processes targeting the same service created a race condition and required managing two PIDs in cleanup.

**Pattern**: Use a single `kubectl port-forward` command with multiple port pairs. One process, one PID, no race.

```bash
# WRONG: Two processes, two PIDs, race condition
kubectl port-forward svc/polaris 8181:8181 &
PID1=$!
kubectl port-forward svc/polaris 8182:8182 &
PID2=$!

# RIGHT: Single process, single PID, atomic
kubectl port-forward svc/polaris 8181:8181 8182:8182 &
PID=$!
```

**When to apply**: Any service exposing multiple ports (API + management, primary + metrics, etc.).

---

## P8: 5-Gate Verification Effectiveness (WU-1 through WU-8)

**Context**: Across Epic 15's 8 work units, the 5-gate verification system found actionable findings in 7 of 8 WUs (WU-7 was config-only and passed clean).

**Epic-level gate effectiveness**:

| WU | BLOCKs Found | WARNs Found | Resolution |
|----|-------------|-------------|------------|
| WU-1 | 0 | 6 | Shipped with advisories |
| WU-2 | 2 | 7 | BLOCKs fixed in 0c5e8c5 |
| WU-3 | 2 | 8 | BLOCKs fixed in 3e81fc6 |
| WU-4 | 0 | 5 | All resolved in da7415f |
| WU-5 | 0 | 10 | Shipped with advisories |
| WU-6 | 4 | 17 | All 27 resolved across 5 commits |
| WU-7 | 0 | 0 | Clean pass |
| WU-8 | 0 | 8 | All 8 resolved in 34f76c2 |

**Key insight**: gate-tests (adversarial test auditor) found the most issues. gate-wiring caught layer violations early. gate-spec ensured ACs were met. The system works — never skip it, even for "simple" changes.

---

## P9: Golden Fixture Cascade After Version Bumps (WU-9)

**Context**: Bumping `COMPILED_ARTIFACTS_VERSION` from 0.7.0 to 0.8.0 required regenerating all 8 OCI golden fixture files. The version string appears in every serialized artifact. This wasn't planned — it consumed 2 fix-up commits.

**Pattern**: When a CompiledArtifacts version bump is planned, include "Regenerate golden fixtures" as an explicit subtask:

1. Bump version in `schemas/versions.py`
2. Run golden fixture tests with `--update-golden` or regenerate manually
3. Commit version bump + all fixture updates atomically
4. Update `.secrets.baseline` (see P10)

**Fixture locations**: `testing/fixtures/golden/oci_pull/*.json` (8 files as of WU-9)

**Why**: Missing even one golden fixture creates a test failure that looks unrelated to the version change. Plan it, don't discover it.

---

## P10: detect-secrets Baseline After Fixture Changes (WU-9)

**Context**: Regenerated golden fixtures contain hex checksums (SHA256 source hashes) that trigger detect-secrets' "Hex High Entropy String" heuristic as false positives. First `git push` failed on the pre-push hook.

**Pattern**: After modifying golden fixture files, always run:

```bash
.venv/bin/detect-secrets scan --baseline .secrets.baseline
```

Then commit the updated `.secrets.baseline` alongside the fixture changes.

**When to apply**: Any commit that modifies files in `testing/fixtures/golden/` or introduces new hex content in JSON/YAML fixtures.

**Why**: Pre-push hook failures after all tasks are complete and verified is frustrating and predictable. Build baseline maintenance into the fixture update step.

---

## P11: Gate-Security + CI Security Review Are Complementary (WU-9)

**Context**: WU-9 gate-security found 0 BLOCK, 0 WARN, 4 INFO. CI security review (Greptile + Claude Code bot) found 1 CRITICAL + 2 HIGH + 4 MEDIUM on the same code.

**What each catches**:

| Layer | Focus | Example Findings |
|-------|-------|------------------|
| **gate-security** | Code patterns — token validation, exception handling, logging, eval/exec | "Token/principal accepted without length check" |
| **CI security review** | Attack surface — CWE mapping, SSRF, injection vectors, data flow | "Endpoint field is SSRF vector (CWE-918)" |

**Pattern**: Both layers must be green before merge. Gate-security is fast (pre-ship); CI review is thorough (post-push). Do not treat one as redundant with the other.

**Why**: WU-6 gate-security found token validation was needed. WU-9 CI review found the validation was incomplete (missing character set regex). Different perspectives catch different classes of vulnerabilities.

---

## P12: Schema Change Ripple Checklist (WU-9)

**Context**: WU-9 had 7 task commits but 5 fix-up commits. The fix-ups were all predictable: golden fixtures, secrets baseline, `__init__.py` exports, trailing newlines. Almost 1:1 task-to-fixup ratio.

**Recurring theme** (WU-6, WU-8, WU-9): Core schema/config changes create predictable downstream work that isn't planned as a task.

**Pattern**: When planning work that touches CompiledArtifacts schema or adds new Pydantic models, include this checklist as explicit subtasks:

| Trigger | Required Step | Reference |
|---------|--------------|-----------|
| New Pydantic models added | Add re-exports to `schemas/__init__.py` or `plugins/__init__.py` | P4 |
| CompiledArtifacts version bump | Regenerate all golden fixtures | P9 |
| Golden fixtures changed | Update `.secrets.baseline` | P10 |
| New fields on existing models | Update contract tests with new field assertions | Constitution IV |
| Test target migration | Verify old target still tested elsewhere | P6 |

**Why**: Planning downstream steps as first-class tasks eliminates the fix-up commit churn that accumulates after verification.

---

## P13: Explicit dbt --profiles-dir (WU-11)

**Context**: `dbt compile --project-dir demo/customer-360` failed because dbt defaulted `--profiles-dir` to `~/.dbt` instead of looking in the project directory. Each demo product has a local `profiles.yml` alongside `dbt_project.yml`.

**Pattern**: When using `dbt compile --project-dir`, ALWAYS pass `--profiles-dir` explicitly. dbt does NOT infer profiles location from the project directory.

```bash
# WRONG: profiles-dir defaults to ~/.dbt
dbt compile --project-dir demo/customer-360

# RIGHT: explicit profiles-dir
dbt compile --project-dir demo/customer-360 --profiles-dir demo/customer-360
```

**When to apply**: Any `dbt` command that uses `--project-dir` and expects a local `profiles.yml`.

---

## P14: Layered Docker --no-deps Requires Dependency Matrix (WU-11)

**Context**: `pip install --no-deps` + `pip check` in Dockerfile failed with 17 missing dependencies and 3 version conflicts. The base image (`dagster-celery-k8s:1.9.6`) didn't contain our packages' transitive deps (dagster-dbt, dbt-core, httpx, opentelemetry-api, etc.).

**Pattern**: Layered Docker builds using `--no-deps` require an explicit dependency compatibility matrix:

| Layer | Image | Provides | Pinned Version |
|-------|-------|----------|----------------|
| Base | dagster-celery-k8s | dagster, pydantic, grpcio | 1.9.6 |
| Install | floe packages | floe-core, orchestrator, compute, dbt | current |

Before adding `--no-deps`, enumerate:
1. What transitive deps the base image provides
2. What transitive deps the installed packages need
3. Version compatibility across both layers

**When to apply**: Any Dockerfile that installs packages with `--no-deps` on top of a vendor base image.

**Why**: `--no-deps` is correct to avoid version conflicts, but shifts the burden to design-time dependency analysis. `pip check` catches the failure, but only at build time — too late.

---

## P15: Base Image Version Pinning Coordination (WU-11)

**Context**: Base image has dagster 1.9.6, but floe packages require `>=1.10.0`. Also pydantic 2.10.4 vs `>=2.12.5` and kubernetes 31.0.0 vs `>=35.0.0`. Three hard version conflicts discovered at Docker build time.

**Pattern**: Base image version pinning MUST be coordinated with package `pyproject.toml` constraints. Track as an explicit version matrix:

```
# docker/dagster-demo/VERSION-MATRIX.md (or Dockerfile comment)
Base: dagster-celery-k8s:1.9.6
  dagster==1.9.6     (floe requires >=1.10.0 — CONFLICT)
  pydantic==2.10.4   (floe requires >=2.12.5 — CONFLICT)
  kubernetes==31.0.0  (floe requires >=35.0.0 — CONFLICT)
```

When bumping base image OR package constraints, check the matrix.

**When to apply**: Any vendor base image with pre-installed Python packages that overlap with your requirements.

---

## P16: Selective Dockerfile COPY (WU-11)

**Context**: PR reviewer caught that `COPY packages/` and `COPY plugins/` copied 23+ packages into the image but only 4 were installed. Wasted build context, bloated image, and leaked source code.

**Pattern**: Dockerfile COPY instructions MUST be selective — copy only what's installed or used.

```dockerfile
# WRONG: Copies entire directory trees
COPY packages/ /build/packages/
COPY plugins/ /build/plugins/

# RIGHT: Copy only what's installed
COPY packages/floe-core /build/packages/floe-core
COPY plugins/floe-orchestrator-dagster /build/plugins/floe-orchestrator-dagster
COPY plugins/floe-compute-duckdb /build/plugins/floe-compute-duckdb
COPY plugins/floe-dbt-core /build/plugins/floe-dbt-core
```

**Audit**: Count COPY lines vs RUN pip install lines. They should match (1:1 or documented otherwise).

---

## P17: No Redundant Makefile Compilation (WU-11)

**Context**: The `demo` Makefile target had an inline `floe compile` block that duplicated work already done by the `compile-demo` prerequisite. The two code paths used different flags and drifted.

**Pattern**: Makefile targets MUST rely on prerequisite dependencies for ordering. Never duplicate compilation or build steps inline.

```makefile
# WRONG: Inline duplication of prerequisite work
demo: kind-up compile-demo build-demo-image
	# This block re-runs compilation with different flags!
	@for product in ...; do floe compile ...; done
	helm upgrade ...

# RIGHT: Trust prerequisites, only do unique work
demo: kind-up compile-demo build-demo-image
	helm upgrade ...
```

**Audit question**: "Does this target body do anything already done by its prerequisites?"

**Why**: Duplicate work slows builds. Worse, the two code paths can drift (different flags, different error handling). Make's dependency graph should be the single source of build ordering.

---

## P18: uv Export as Vendor Image Replacement (WU-12)

**Context**: WU-11 discovered that layered Docker builds on vendor base images (dagster-celery-k8s) create version conflicts (P14, P15). WU-12 replaced the vendor image entirely with a 3-stage build using `uv export`.

**Pattern**: When packaging Python monorepo packages for Docker, prefer `uv export --frozen --require-hashes` over vendor base images:

```dockerfile
# Stage 1: EXPORT — uv produces requirements.txt with SHA256 hashes
FROM ghcr.io/astral-sh/uv:0.6 AS export
COPY uv.lock pyproject.toml ./
COPY packages/*/pyproject.toml ...   # All workspace member metadata
RUN uv export --frozen --no-dev --no-editable --package $PKG > requirements.txt

# Stage 2: BUILD — pip installs from hash-verified requirements
FROM python:3.11-slim AS build
COPY --from=export /build/requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY packages/floe-core /build/packages/floe-core  # Selective COPY (P16)
RUN pip install --no-deps --no-cache-dir /build/packages/floe-core

# Stage 3: RUNTIME — minimal image with site-packages only
FROM python:3.11-slim AS runtime
COPY --from=build /usr/local/lib/python3.11/site-packages ...
```

**Benefits over vendor base images**:
- No version matrix coordination (P14/P15 eliminated)
- `--frozen` ensures lockfile is authoritative (no re-resolution)
- `--require-hashes` provides supply chain verification
- `pip check` validates dependency tree consistency
- No vendor image update lag

**When to apply**: Any Docker image for Python monorepo packages where vendor images create version conflicts.

---

## P19: Python stdlib Version Guards (WU-12)

**Context**: Tests used `import tomllib` (Python 3.11+ only). CI runs Python 3.10/3.11/3.12. mypy flagged `# type: ignore[no-redef]` as unnecessary on 3.11, but removing the try/except broke 3.10.

**Pattern**: For stdlib modules that differ across supported Python versions, use `sys.version_info` guards at module level:

```python
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # backport for 3.10
```

**Why not try/except?**
- mypy doesn't understand try/except for version branching — it sees a redefinition
- `# type: ignore[no-redef]` becomes "unused ignore" on versions where the except branch is dead
- `sys.version_info` guards are natively understood by mypy — it evaluates the branch statically

**When to apply**: Any module that needs stdlib features added after the minimum supported Python version (e.g., `tomllib` 3.11+, `StrEnum` 3.11+, `ExceptionGroup` 3.11+).

---

## P20: Non-root USER Placement in Dockerfiles (WU-12)

**Context**: Gate-security flagged the runtime container as running as root. Adding `USER dagster` before `COPY` and `touch` commands would have broken the build since those operations need root.

**Pattern**: In Dockerfile runtime stages, place the `USER` directive after ALL file operations:

```dockerfile
# Stage: RUNTIME
COPY --from=build /usr/local/lib/python3.11/site-packages ...
COPY demo/customer-360/ /app/demo/customer_360/

# Create files that need root
RUN touch /app/demo/customer_360/__init__.py

# THEN switch to non-root (after all COPY/RUN that need root)
RUN useradd --create-home --shell /bin/false appuser
USER appuser

# WORKDIR and CMD run as non-root
WORKDIR /app/demo
CMD ["dagster-webserver"]
```

**Order**: `COPY` → `RUN` (file creation) → `USER` → `WORKDIR` → `CMD`

**Why**: `COPY` uses root by default. Placing `USER` before `COPY` causes permission errors that are silent during build but break at runtime.

---

## P21: Docker Extras for Runtime-Only Dependencies (WU-12)

**Context**: WU-12 needed `dagster-webserver`, `dagster-daemon`, and `dagster-k8s` in Docker but not in the development environment. Adding them as top-level dependencies would pollute `uv sync`.

**Pattern**: Use `[project.optional-dependencies]` extras for runtime-only packages:

```toml
# plugins/floe-orchestrator-dagster/pyproject.toml
[project.optional-dependencies]
docker = [
    "dagster-webserver>=1.9.0,<2.0.0",
    "dagster-daemon>=1.9.0,<2.0.0",
    "dagster-k8s>=1.9.0,<2.0.0",
]
```

```dockerfile
# Dockerfile: include extras in export
RUN uv export --frozen --package floe-orchestrator-dagster --extra docker > requirements.txt
```

```bash
# Development: no extras, no server bloat
uv sync  # Only installs core deps
```

**When to apply**: Packages that need different dependencies for development vs Docker runtime (web servers, daemons, admin tools, monitoring agents).

---

## P22: Validate ALL Interpolated Values in Templates (U2)

**Context**: Shell-side input validation was added for `catalogRole`, `catalogName`, and `principalRole` but missed privilege strings rendered via `{{ range }}` into curl JSON bodies. Three independent PR reviewers (claude[bot], greptile, github-actions) all caught the same gap.

**Pattern**: When adding input validation to a Helm template (or any template engine), enumerate every interpolation site — not just named variables. Range loops, nested templates, and conditional blocks all produce interpolated values that need validation.

**Checklist**:
1. List every `{{ . }}`, `{{ .Values.* }}`, and `{{ include ... }}` in the template
2. For each: is it used in a URL path, JSON body, shell command, or log message?
3. If yes: add validation (shell `case` pattern, JSON schema, or Helm `fail`)
4. Add a test asserting the validation block renders for each interpolation class

**When to apply**: Any Helm template that interpolates values into shell scripts, curl commands, or API payloads.

---

## P23: Child Feature Flags Default to Restrictive (U2)

**Context**: `grants.enabled: true` with parent `bootstrap.enabled: false` meant enabling bootstrap silently inherited privilege escalation (CATALOG_MANAGE_CONTENT on principal role ALL). Caught by gate-wiring.

**Pattern**: When a child feature flag controls security-sensitive behavior (privilege grants, credential creation, network exposure), default to `false` (opt-in) regardless of the parent's default.

```yaml
# WRONG: Child more permissive than parent
bootstrap:
  enabled: false
  grants:
    enabled: true  # Silent privilege escalation when bootstrap enabled

# RIGHT: Child defaults to restrictive
bootstrap:
  enabled: false
  grants:
    enabled: false  # Explicit opt-in required
```

**Corollary**: Environment-specific values files (values-test.yaml) should explicitly set security-sensitive child flags rather than inheriting defaults.

**When to apply**: Any nested feature flag that controls privilege escalation, credential provisioning, or network exposure.

---

## P24: Dynamic Step Counting from ALL Conditionals (U2)

**Context**: `$totalSteps := 4` was hardcoded, then changed to `7` when grants were added. But step 2 (MinIO verification) is conditional on `s3.enabled`, so `s3=false + grants=true` logged `Step 1/7 → 3/7 → ...` (claiming 7 but only running 6).

**Pattern**: When a shell script has conditional steps, compute the total dynamically from all conditionals:

```yaml
{{- $totalSteps := 3 }}
{{- if .Values.polaris.storage.s3.enabled }}
{{- $totalSteps = add $totalSteps 1 }}
{{- end }}
{{- if .Values.polaris.bootstrap.grants.enabled }}
{{- $totalSteps = add $totalSteps 3 }}
{{- end }}
```

**When to apply**: Any Helm template with conditional shell script steps that log progress (Step N/M).

**Why**: Hardcoded totals only work for the combination the developer tested. Dynamic computation handles all 2^N combinations correctly.

---

## P25: Venv Binary Resolution for CLI Tools (U3)

**Context**: System-installed `dbt-fusion` at `~/.local/bin/dbt` shadowed the venv's `dbt-core+dbt-duckdb`. Error message (`unknown variant 'duckdb'`) didn't indicate a PATH conflict. Took significant debugging to trace.

**Pattern**: When test fixtures invoke CLI tools (dbt, dagster, alembic, etc.), resolve the binary from the active venv, never from PATH:

```python
import sys
from pathlib import Path

venv_bin = Path(sys.executable).parent
dbt_bin = str(venv_bin / "dbt")

subprocess.run([dbt_bin, *args], ...)
```

**When to apply**: Any test fixture or helper that invokes a CLI tool via `subprocess`. Especially when the tool has multiple distributions (dbt-core vs dbt-fusion, python vs python3).

**Why**: PATH resolution is environment-dependent. CI, local dev, and IDE terminals may have different PATH orders. Venv resolution is deterministic.

---

## P26: Iceberg Table Purge Before dbt Seed/Run (U3)

**Context**: `dbt seed --full-refresh` failed with 404s because PyIceberg metadata referenced data files from a prior test session that no longer existed. Required 3 iterative commits to get right (--full-refresh → catalog purge → separate seed vs model purge).

**Pattern**: When dbt targets Iceberg tables in E2E tests, purge stale tables via PyIceberg catalog API before seed/run:

```python
def purge_namespace(catalog: Any, namespace: str) -> None:
    """Drop all tables in namespace via catalog API."""
    try:
        tables = catalog.list_tables(namespace)
        for table_id in tables:
            catalog.drop_table(f"{table_id[0]}.{table_id[1]}")
    except Exception:
        logger.warning("Namespace purge skipped for %s", namespace)
```

**Why**: dbt's `--full-refresh` only manages dbt-controlled state. Iceberg metadata (snapshots, manifest lists, data file references) persists independently. Stale metadata from prior sessions causes 404s that dbt cannot recover from.

**When to apply**: Any E2E test that runs dbt against Iceberg tables and needs idempotent re-runs.

---

## P27: Content Landmarks in Structure-Inspecting Tests (U3)

**Context**: `test_try_block_still_contains_backup_creation` used regex to find the "first try/except block" in a fixture. Adding a macro import try block before the backup try block broke the test — regex matched the wrong block.

**Pattern**: Tests that inspect source code structure must search for content landmarks, not ordinal position:

```python
# WRONG: Assumes first try block is the one we care about
try_match = re.search(r"try:\s*\n(.*?)except\s+", source, re.DOTALL)

# RIGHT: Find the try block containing the specific logic
for match in re.finditer(r"try:\s*\n(.*?)except\s+", source, re.DOTALL):
    if "_DBT_DEMO_PRODUCTS" in match.group(1):
        try_body = match.group(1)
        break
```

**When to apply**: Any test that uses AST parsing or regex to validate source code structure. Especially when the inspected function may gain new blocks over time.

**Why**: Ordinal position is fragile — any structural addition to the function breaks the test even when the tested logic is unchanged.

---

## P28: Never Log Auth Response Bodies (U3)

**Context**: OAuth and management API error responses may include request credentials in their error body (reflected `client_secret`, tokens in error messages). Logging `response.text` on error creates CWE-532 (sensitive info in logs) exposure.

**Pattern**: When logging HTTP error responses from authentication or management APIs, log only the status code:

```python
# WRONG: Response body may contain reflected credentials
logger.warning("Auth failed: %s", response.text)

# RIGHT: Status code only
logger.warning("Auth failed: HTTP %s", response.status_code)
```

**When to apply**: Any error handling for OAuth token endpoints, credential management APIs, or admin APIs that accept secrets in request bodies.

**Why**: Error responses commonly reflect request parameters. If the request contained `client_secret=abc123`, the error body may include `"invalid client_secret: abc123"`. Logging this leaks credentials to log aggregators.

---

## P29: mktemp for CI Temporary Files (U3)

**Context**: Hardcoded `/tmp/polaris-create.txt` was world-readable and never cleaned up. On shared CI runners (GitHub Actions, Jenkins agents), other processes or jobs can read or race the file.

**Pattern**: Use `mktemp` for all temporary files in shell scripts, with explicit cleanup:

```bash
# WRONG: Predictable path, no cleanup
curl -s -o /tmp/polaris-create.txt ...
cat /tmp/polaris-create.txt

# RIGHT: Unique path, explicit cleanup
POLARIS_TMP=$(mktemp)
curl -s -o "${POLARIS_TMP}" ...
cat "${POLARIS_TMP}"
rm -f "${POLARIS_TMP}"
```

**When to apply**: Any shell script that creates temporary files, especially in CI/CD pipelines or shared environments.

**Why**: Predictable paths enable symlink attacks (CWE-377) and information disclosure on multi-tenant CI runners.

---

## P30: No Pipe Buffering on Background Tasks (U3)

**Context**: `make test-e2e 2>&1 | tail -80` as a background task appeared stuck (0 output for 14+ minutes). Root cause: `tail` buffers ALL input until stdin closes (EOF), so no incremental output is visible. Wasted significant debugging time investigating false leads (AirPlay port conflicts, OTel connectivity).

**Pattern**: Never pipe background task output through `tail`, `head`, or `grep` — redirect to a file directly:

```bash
# WRONG: Pipe buffering hides all output until EOF
make test-e2e 2>&1 | tail -80 &

# RIGHT: File redirect, then read the file
make test-e2e > /tmp/test-output.log 2>&1 &
# Later:
tail -80 /tmp/test-output.log
```

**When to apply**: Any command run in the background where you need to monitor progress or check output before the command completes.

**Why**: Pipe buffering is a POSIX behavior — when stdout is not a TTY, output is block-buffered (typically 4KB or 8KB). `tail -N` additionally waits for EOF before emitting. The combination makes background pipes appear completely silent.

---

## P31: No eval in Helm Shell Scripts (polaris-rbac-keycloak)

**Context**: Bootstrap job used `eval "GRANT_VAR_VAL=\$$GRANT_VAR_NAME"` for variable indirection. Three independent PR reviewers flagged CWE-78 (OS command injection) — if a Helm value contained shell metacharacters, `eval` would execute them.

**Pattern**: Replace `eval` with explicit `case` dispatch for variable indirection in shell scripts:

```bash
# WRONG: eval for variable indirection (CWE-78)
eval "VAL=\$$VAR_NAME"

# RIGHT: case dispatch — no interpretation of values
case "$VAR_NAME" in
  CATALOG_ROLE) VAL="$CATALOG_ROLE" ;;
  CATALOG_NAME) VAL="$CATALOG_NAME" ;;
  *) echo "ERROR: Unknown variable: $VAR_NAME" >&2; exit 42 ;;
esac
```

**When to apply**: Any Helm template or shell script that needs to look up a variable by name. Never use `eval` for this.

**Why**: Helm values are user-controlled. `eval` interprets the entire string, not just the variable reference. A value like `; rm -rf /` would be executed.

---

## P32: Chart Unit Tests Must Track Template Changes (polaris-rbac-keycloak)

**Context**: Bootstrap template was rewritten (5 new grant steps, step counts changed from 6 to 8, `principalRole: ALL` → `principalRole: floe-pipeline`) but `bootstrap_grants_test.yaml` was not updated. CI failed on `helm unittest` — a completely independent pipeline from Python tests.

**Pattern**: When modifying a Helm template, always check for and update corresponding chart unit tests:

1. Find tests: `ls charts/*/tests/` matching the template name
2. Update all `set:` values to match new defaults
3. Update all `matchRegex`/`notMatchRegex` assertions for changed output
4. Add new test cases for new functionality
5. Run `helm unittest charts/<chart>/` locally before committing

**When to apply**: Any Helm template modification. Chart tests are a parallel test pipeline that's easy to forget.

---

## P33: Full Polaris REST Idempotency Codes (polaris-rbac-keycloak)

**Context**: Initial implementation only handled 201 (created) and 409 (conflict) for catalog role creation. PR reviewer caught that grant PUT returns 204 (not 201), and principal role assignment returns 200 or 204 depending on Polaris version.

**Pattern**: Polaris REST API idempotency codes by operation:

| Operation | Method | Success Codes | Idempotent Code |
|-----------|--------|---------------|-----------------|
| Create catalog role | POST | 201 | 409 |
| Grant privilege | PUT | 200, 201, 204 | 409 |
| Create principal role | POST | 201 | 409 |
| Assign principal role | PUT | 200, 201, 204 | 409 |

Always handle the full set. Don't assume all creates return 201 or all updates return 200.

---

## P34: Policy Comments on PR Review Declinations (polaris-rbac-keycloak)

**Context**: PR reviewer suggested adding response body logging to error paths. The suggestion contradicted P28 (never log auth response bodies). The initial instinct was to just decline, but adding a comment explaining P28 and linking the CWE-532 rationale made the review more productive.

**Pattern**: When declining a PR suggestion because it contradicts a project policy:

1. Name the policy (e.g., "P28: Never Log Auth Response Bodies")
2. Explain the security rationale (e.g., CWE-532, reflected credentials)
3. Offer an alternative that satisfies both the reviewer's intent and the policy

```markdown
> This contradicts our P28 policy (never log auth/management API response
> bodies — CWE-532). Error responses from OAuth endpoints may reflect
> `client_secret` values. We log status codes only. See `.specwright/patterns.md` P28.
>
> For debugging, check Polaris server logs directly (they redact credentials).
```

**When to apply**: Any PR review where a suggestion conflicts with an established project security or quality policy.

---

## P35: No Cross-Tier Text-Parsing Tests (polaris-rbac-keycloak)

**Context**: Unit tests in `tests/unit/test_conftest_rbac.py` read E2E fixture source (`tests/e2e/conftest.py`) as raw text and parsed it with regex. This creates a fragile cross-tier dependency — any refactoring of the E2E conftest (extract to module, rename function, restructure) breaks unit tests that should be independent.

**Pattern**: Tests that validate code structure should live in the same tier as the code they inspect:

| Code Location | Structural Test Location | Why |
|---------------|--------------------------|-----|
| `tests/e2e/conftest.py` | `tests/e2e/test_conftest_structure.py` | Same tier, co-evolves |
| `charts/*/templates/*.yaml` | `charts/*/tests/*.yaml` | Helm unittest, same tier |
| `src/**/*.py` | `tests/unit/test_*.py` | Tests the module's public API |

**Anti-pattern**: `tests/unit/test_*.py` reading `tests/e2e/**` source files as text.

**When to apply**: Any test that imports, reads, or parses source files from a different test tier.

---

## P40: Daemon Thread Resource Tests MUST Call close() (lineage-resource)

**Context**: 14 unit tests constructed `LineageResource` (which spawns a daemon thread running `asyncio.run_forever()`) without calling `close()`. Tests passed locally but caused segfaults on CI during Python interpreter shutdown — orphaned daemon threads accessing freed memory.

**Pattern**: Any test that constructs a resource spawning daemon threads MUST ensure cleanup via `try/finally` or yield fixtures:

```python
# Direct construction — try/finally
resource = LineageResource(emitter=mock_emitter)
try:
    assert resource.namespace == "test"
finally:
    resource.close()

# Fixture — yield with teardown
@pytest.fixture
def lineage_resource(mock_emitter: MagicMock) -> Any:
    resource = LineageResource(emitter=mock_emitter)
    yield resource
    resource.close()
```

**When to apply**: Any test constructing objects that spawn threads, open event loops, or hold OS-level resources. Especially critical for daemon threads — they survive test teardown and crash during interpreter shutdown.

**Why**: Python 3.10+ segfaults when daemon threads running `asyncio.run_forever()` access the event loop after the interpreter begins cleanup. This is silent locally (fast shutdown) but fatal on CI (parallel test collection, slower cleanup).

---

## P41: Dagster Resource Creation Inside Generator (lineage-resource)

**Context**: `create_lineage_resource()` created `LineageResource(emitter=emitter)` in the factory scope, then yielded it from the inner `_resource_fn` generator. This meant the daemon thread started at definition-load time (when Dagster collects resources), not at resource-init time (when a run starts).

**Pattern**: Dagster `ResourceDefinition` generators MUST construct the resource inside the generator function, not in the enclosing factory:

```python
# WRONG: Resource created eagerly in factory scope
def create_lineage_resource(ref):
    emitter = create_emitter(config, namespace)
    resource = LineageResource(emitter=emitter)  # Thread starts NOW

    def _resource_fn(_init_context):
        yield resource  # Thread started too early
    return {"lineage": ResourceDefinition(resource_fn=_resource_fn)}

# RIGHT: Resource created lazily inside generator
def create_lineage_resource(ref):
    emitter = create_emitter(config, namespace)

    def _resource_fn(_init_context):
        resource = LineageResource(emitter=emitter)  # Thread starts at init
        try:
            yield resource
        finally:
            resource.close()  # Thread cleaned up at teardown
    return {"lineage": ResourceDefinition(resource_fn=_resource_fn)}
```

**When to apply**: Any Dagster `ResourceDefinition` wrapping an object that holds connections, threads, or other OS resources.

---

## P42: Event Loop Lifecycle — close() After stop()+join(), Guard with is_alive() (lineage-resource)

**Context**: `LineageResource.close()` called `loop.close()` unconditionally after `loop.call_soon_threadsafe(loop.stop)` + `thread.join(timeout)`. When the thread didn't stop in time (timeout expired), `loop.close()` raised `RuntimeError("Cannot close a running event loop")`.

**Pattern**: Guard `loop.close()` with a thread liveness check:

```python
def close(self) -> None:
    self._emitter.close()
    self._loop.call_soon_threadsafe(self._loop.stop)
    self._thread.join(timeout=TIMEOUT)
    if self._thread.is_alive():
        logger.warning("background_thread_did_not_stop")
        # Do NOT close the loop — it's still running
    else:
        self._loop.close()  # Safe — thread stopped, loop idle
```

**When to apply**: Any resource managing an asyncio event loop in a background thread. The `stop → join → close` sequence must account for join timeout.

---

## P43: Cancel Timed-Out Futures (lineage-resource)

**Context**: `run_coroutine_threadsafe` submits coroutines to a background loop. On timeout, `future.result(timeout=N)` raises `TimeoutError`, but the coroutine continues running in the background loop, accumulating work and potentially leaking resources.

**Pattern**: Always cancel the future after a timeout:

```python
future = asyncio.run_coroutine_threadsafe(coro, self._loop)
try:
    return future.result(timeout=TIMEOUT)
except TimeoutError:
    future.cancel()  # Prevent coroutine accumulation
    logger.warning("emit_timeout", extra={"timeout": TIMEOUT})
    return default
```

**When to apply**: Any use of `run_coroutine_threadsafe` with a timeout. Without cancellation, timed-out coroutines accumulate in the loop and may delay shutdown.

---

## P44: NoOp Implementations Must Match Real Signatures (lineage-resource)

**Context**: `NoOpLineageResource` used `**kwargs` for all methods while `LineageResource` had explicit keyword-only parameters (`inputs`, `outputs`, `run_facets`, `job_facets`). Code using `isinstance` duck-typing or structural subtyping broke when callers passed keyword arguments that `**kwargs` silently absorbed without validation.

**Pattern**: NoOp/stub implementations must mirror the real class's explicit parameter signatures:

```python
# WRONG: **kwargs hides signature mismatches
class NoOpLineageResource:
    def emit_start(self, job_name: str, **kwargs: Any) -> UUID:
        return uuid4()

# RIGHT: Explicit signatures match the real class
class NoOpLineageResource:
    def emit_start(
        self,
        job_name: str,
        *,
        inputs: list[Any] | None = None,
        outputs: list[Any] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
    ) -> UUID:
        return uuid4()
```

**When to apply**: Any NoOp, stub, or mock class intended as a drop-in replacement for a real implementation. Especially when duck-typing (no shared ABC) is used for substitution.

**Why**: `**kwargs` defeats IDE autocomplete, type checking, and caller validation. A typo like `run_facet=` (missing 's') is silently absorbed by `**kwargs` but caught by explicit signatures.

---

## P36: Cleanup at Setup AND Teardown (e2e-test-infra-fixes)

**Context**: Stale K8s jobs from crashed E2E runs left pods in `ContainerCreating` that poisoned health assertions. Teardown cleanup is unreliable because crashes skip it. But skipping teardown entirely leaves resources that accumulate.

**Pattern**: E2E test fixtures should clean stale state at setup time (defensive) AND teardown (courteous):

```python
@pytest.fixture(scope="module")
def e2e_namespace():
    namespace = "floe-e2e-helm"

    # SETUP: Clean up stale state from crashed previous runs
    recover_stuck_helm_release(release_name, namespace, ...)
    result = _kubectl(["get", "namespace", namespace, ...])
    if result.returncode == 0 and phase == "Terminating":
        _kubectl(["wait", "--for=delete", ...])
    ...

    yield namespace

    # TEARDOWN: Best-effort cleanup for the next run
    _helm(["uninstall", release_name, "-n", namespace])
    _kubectl(["delete", "namespace", namespace, "--ignore-not-found"])
```

**Why**: Setup cleanup is the reliable path (always runs). Teardown cleanup is a courtesy (reduces work for the next run but may be skipped on crash).

---

## P37: Guard kubectl/helm Return Codes in Fixtures (e2e-test-infra-fixes)

**Context**: `kubectl wait --for=delete` timeout was silently discarded, causing `kubectl create namespace` to also fail silently. Tests ran against a namespace that was never created, producing confusing downstream failures. Two independent PR reviewers (claude[bot] P1, greptile P1) caught this.

**Pattern**: Every `kubectl`/`helm` call in a test fixture whose failure would invalidate the test MUST have its return code checked:

```python
# WRONG: Silent failure propagates as mystery downstream error
_kubectl(["wait", "--for=delete", f"namespace/{ns}", "--timeout=30s"])
_kubectl(["create", "namespace", ns])

# RIGHT: Fail fast with actionable message
wait_result = _kubectl(["wait", "--for=delete", f"namespace/{ns}", "--timeout=30s"])
if wait_result.returncode != 0:
    pytest.fail(
        f"Namespace {ns!r} stuck in Terminating after 30s. "
        "Check for blocking finalizers: kubectl get namespace {ns} -o yaml"
    )
_kubectl(["create", "namespace", ns])
```

**When to apply**: Any test fixture that calls `kubectl` or `helm` where failure means "the test environment is not set up correctly".

---

## P38: Conditional CLI Flag Expansion (e2e-test-infra-fixes)

**Context**: Empty `.vuln-ignore` file (only comments) produced `--ignore-vulns ""` which caused `uv-secure` to fail with an unhelpful parsing error. Both PR reviewers flagged this.

**Pattern**: When building CLI commands from file-derived values, use conditional expansion to omit the flag entirely when empty:

**Shell (bash)**:
```bash
# WRONG: passes --ignore-vulns "" when IGNORES is empty
--ignore-vulns "$(grep -v '^#' .vuln-ignore | grep -v '^$' | paste -sd ',' -)"

# RIGHT: omits --ignore-vulns entirely when empty
IGNORES=$(grep -v "^#" .vuln-ignore 2>/dev/null | grep -v "^$" | paste -sd "," -)
${IGNORES:+--ignore-vulns "$IGNORES"}
```

**Python**:
```python
# WRONG: passes empty string as argument
cmd = ["tool", "--ignore-vulns", ignore_ids, ...]

# RIGHT: conditionally include flag
cmd = ["tool"]
if ignore_ids_list:
    cmd += ["--ignore-vulns", ",".join(ignore_ids_list)]
cmd += remaining_args
```

**When to apply**: Any CLI command built from a file or variable that may be empty.

---

## P39: Single-File Ignore/Allow Lists (e2e-test-infra-fixes)

**Context**: Vulnerability ignore list was duplicated between `.pre-commit-config.yaml` (9 GHSAs) and `test_governance.py` (7 GHSAs — missing 2 pyOpenSSL entries). The drift caused `test_pip_audit_clean` to fail while pre-commit passed.

**Pattern**: Configuration that must be identical across multiple consumers should live in a single file read by all:

```
# .vuln-ignore — single source of truth
# PyOpenSSL 25.3.0 — fix in 26.0.0, transitive via pyiceberg
GHSA-vp96-hxj8-p424
GHSA-5pwr-322w-8jr4
```

Consumers:
- `.pre-commit-config.yaml`: `bash -c '... $(grep -v "^#" .vuln-ignore | ...) ...'`
- `test_governance.py`: `Path(".vuln-ignore").read_text()` → filter → join

**When to apply**: Any config value that appears in 2+ places and must stay in sync (ignore lists, feature flags, version constraints). If you find yourself copying a value, extract it.

---

## P45: CWE-532 Trust Boundary Clarity (otel-init-unification)

**Context**: Security fix replaced `click.echo(f"Error: {e}")` with structured logging + `exc_info=True`. PR reviewer flagged that `exc_info=True` still writes full exception messages (including credential-bearing URLs) to logs, contradicting the comment "log exception type only".

**Pattern**: When logging exceptions near credential-bearing code paths, comments MUST specify the exact trust boundary being defended:
- **Operator logs** (`exc_info=True`): acceptable — operator-controlled, not user-visible
- **User stderr** (`click.echo`): must never contain `str(exc)` from transport errors
- **Structured log fields** (`exc_type=...`): safe — type name only, no URLs

```python
# ✅ CORRECT — boundary is explicit
except Exception as exc:
    # Log traceback for operator diagnostics only. Never expose
    # str(exc) to users — transport errors may contain credential-
    # bearing URLs (CWE-532). exc_info=True writes to operator-
    # controlled log files; user sees generic message below.
    structlog.get_logger(__name__).error(
        "cli_unexpected_error",
        exc_type=type(exc).__name__,
        exc_info=True,
    )
    click.echo("An unexpected error occurred.", err=True)

# ❌ WRONG — comment is vague
except Exception:
    # Log exception type only — never str(exc) (CWE-532)
    logger.error("error", exc_info=True)  # <-- contradicts comment!
```

**When to apply**: Any `except` block that logs exceptions where transport/HTTP errors could carry credentials in their message string.

---

## P46: DRY OTel Private API Reset (otel-init-unification)

**Context**: MeterProvider reset logic (`hasattr` + private attr manipulation) was duplicated 5× across 3 files. PR reviewers immediately flagged the maintenance risk.

**Pattern**: Consolidate OTel private API workarounds to a single function. Test fixtures should call the production reset function rather than duplicating the private API manipulation.

```python
# ✅ CORRECT — single source of truth
# initialization.py
def reset_telemetry() -> None:
    """Handles ALL private API reset (TracerProvider + MeterProvider)."""
    ...

# test fixtures
@pytest.fixture(autouse=True)
def _reset_otel_state():
    reset_telemetry()
    yield
    reset_telemetry()

# ❌ WRONG — duplicated private API manipulation in fixtures
@pytest.fixture(autouse=True)
def _reset_otel_state():
    # 8 lines of hasattr + private attr reset (copy-pasted from reset_telemetry)
    ...
```

**When to apply**: Any OTel SDK state reset in test fixtures. Always prefer calling `reset_telemetry()` over manual private API manipulation.

---

## P47: OTel ProxyMeterProvider Restoration Asymmetry (otel-init-unification)

**Context**: After resetting OTel global state, TracerProvider uses `None` to avoid infinite recursion (`ProxyTracerProvider.get_tracer()` reads `_TRACER_PROVIDER` — when it IS the provider, it recurses). MeterProvider needs a fresh `_ProxyMeterProvider()` instance to restore the auto-upgrade mechanism.

**Pattern**: When extending OTel reset patterns to new provider types, verify the proxy restoration behavior independently:

```python
# TracerProvider: None (avoids recursion)
trace._TRACER_PROVIDER = None

# MeterProvider: fresh proxy (restores auto-upgrade)
metrics._internal._PROXY_METER_PROVIDER = metrics._internal._ProxyMeterProvider()
```

**Why the asymmetry**: `ProxyTracerProvider.get_tracer()` checks `_TRACER_PROVIDER` to find the "real" provider. When `_TRACER_PROVIDER` is itself the proxy, it recurses infinitely. `None` causes a safe NoOp fallback. `_ProxyMeterProvider` doesn't have this recursion issue, and needs a live proxy to auto-upgrade when `set_meter_provider()` is next called.

**When to apply**: Any time you add a new OTel provider type to `reset_telemetry()`. Don't assume the same null-safety semantics as existing providers.

---

## P48: Go YAML Last-Key-Wins Silently Drops Duplicate Keys (fix-postgresql-volumes)

**Context**: Helm template rendered two `volumes:` keys at the same YAML mapping level inside a StatefulSet spec. Go YAML v2/v3 (used by Helm) silently uses last-key-wins, dropping the first `volumes:` block containing `init-scripts`. The pod then fails because the `volumeMount` references a volume that doesn't exist.

**Pattern**: When Helm template conditionals produce structural YAML keys (like `volumes:`, `containers:`, `env:`), verify rendered output with `helm template` to ensure no duplicate keys at the same mapping level:

```bash
# Check for duplicate keys in rendered output
helm template my-chart ./charts/my-chart \
  --set some.flag=false \
  | python3 -c "
import sys, yaml
for doc in yaml.safe_load_all(sys.stdin):
    pass  # Python's yaml.safe_load also uses last-key-wins silently
"
# Better: use a YAML linter that detects duplicate keys
helm template my-chart ./charts/my-chart | yamllint -d '{rules: {key-duplicates: enable}}' -
```

**When to apply**: Any Helm template where conditional branches produce top-level YAML keys (`volumes:`, `env:`, `ports:`, `containers:`). Especially when branches are added incrementally — the second branch may accidentally re-declare a key from the first.

**Why**: Duplicate YAML keys are valid YAML (not a parse error). Linters don't catch them by default. `helm lint` doesn't catch them. The bug is completely silent until a pod fails at runtime.

---

## P49: helm-unittest Assertion Gotchas (fix-postgresql-volumes)

**Context**: Three separate assertion issues discovered during helm-unittest test development for the PostgreSQL StatefulSet volume fix.

**Pattern**: Reference for helm-unittest assertion edge cases:

| Scenario | Wrong Assertion | Right Assertion | Why |
|----------|----------------|-----------------|-----|
| Path doesn't exist in rendered output | `isNullOrEmpty` | `notExists` | `isNullOrEmpty` expects the path to exist with null/empty value; `notExists` handles paths that aren't rendered at all |
| Complex object with helper-injected labels | `contains` with partial content | `equal` on a specific sub-path | `contains` tries to match the full object; labels from helpers add unexpected fields |
| Template uses `include` for other templates | Omit dependency from `templates:` | List all referenced templates in `templates:` array | `include` fails at render time if the referenced template isn't loaded |

```yaml
# Example: asserting volumeClaimTemplates name without matching all labels
# WRONG: contains fails because metadata has extra labels from helpers
- contains:
    path: spec.volumeClaimTemplates
    content:
      metadata:
        name: data

# RIGHT: target a specific sub-path
- equal:
    path: spec.volumeClaimTemplates[0].metadata.name
    value: data
```

**When to apply**: Any helm-unittest test, especially for StatefulSets, Deployments, or other complex K8s resources that use Helm helpers.

---

## P50: Explicit Test Values Over Default Reliance (fix-postgresql-volumes)

**Context**: Helm unit tests 1 and 2 relied on `values.yaml` defaults for `persistence.enabled` and `initdb.scripts`. PR reviewers (greptile) flagged that if someone later changed the defaults, these tests would fail with confusing errors unrelated to the test's actual intent.

**Pattern**: Helm unit tests should explicitly set ALL values they assert on, even when the current defaults happen to produce the desired state:

```yaml
# WRONG: relies on defaults (fragile)
- it: should render volumeClaimTemplates when persistence=true
  template: templates/statefulset-postgresql.yaml
  # No set: block — depends on values.yaml defaults
  asserts:
    - exists:
        path: spec.volumeClaimTemplates

# RIGHT: explicitly sets all relevant values (self-documenting)
- it: should render volumeClaimTemplates when persistence=true
  template: templates/statefulset-postgresql.yaml
  set:
    postgresql.persistence.enabled: true
    postgresql.primary.initdb.scripts:
      init-databases.sql: "CREATE DATABASE dagster;"
  asserts:
    - exists:
        path: spec.volumeClaimTemplates
```

**When to apply**: All helm-unittest tests. The `set:` block should make the test self-documenting — a reader should understand the test's preconditions without cross-referencing `values.yaml`.

---

## P51: Dead Key Detection in Values Files (fix-postgresql-volumes)

**Context**: `values-test.yaml` set `postgresql.primary.persistence.enabled: false` but the template reads `postgresql.persistence.enabled`. The dead key masked the duplicate-volumes bug for months. E2E tests thought persistence was disabled but it was actually enabled (using the default `true`).

**Pattern**: When adding or modifying values in `values.yaml` or variant files (`values-test.yaml`, `values-prod.yaml`), verify the key path is actually consumed by a template:

```bash
# Check if a values path is consumed by any template
grep -r "\.Values\.postgresql\.primary\.persistence" charts/floe-platform/templates/
# Empty output = dead key!

# Check what path the template actually reads
grep -r "\.Values\.postgresql\.persistence" charts/floe-platform/templates/
# This is the real path
```

**Audit checklist for values files**:
1. For every key in the values file, verify at least one template references it via `.Values.<path>`
2. Pay special attention to keys under `primary`, `secondary`, `worker` — these are commonly confused with the top-level key
3. After fixing a dead key, check all variant values files for the same mistake

**When to apply**: Any PR that modifies `values.yaml` or variant values files. Especially when the Helm chart wraps a subchart (like Bitnami PostgreSQL) where the values path hierarchy may differ from the subchart's documentation.

---

## P52: Guard Post-Loop Actions Against Empty Iteration (devpod-remote-e2e)

**Context**: `devpod-tunnels.sh` looped over port mappings, skipping ports already in use via `continue`. If ALL ports were skipped, the post-loop SSH command ran with zero `-L` flags, creating a no-op background SSH connection and reporting "tunnels established" — silently wrong.

**Pattern**: After any loop that can skip/continue all items, guard the post-loop action against the empty case:

```bash
FORWARDED=()
for MAPPING in "${PORTS[@]}"; do
    if port_in_use "${LOCAL_PORT}"; then
        continue
    fi
    SSH_ARGS+=(-L "${LOCAL_PORT}:localhost:${REMOTE_PORT}")
    FORWARDED+=("${MAPPING}")
done

# Guard: no tunnels to establish if all ports were skipped
if [[ ${#FORWARDED[@]} -eq 0 ]]; then
    log "WARNING: All ports already in use — no tunnels to establish"
    exit 0
fi

ssh "${SSH_ARGS[@]}" "${SSH_TARGET}"
```

**When to apply**: Any loop where items can be conditionally skipped and the post-loop action depends on at least one item being processed. Common in: port-forwarding, batch operations, retry loops with skip conditions.

---

## P53: Pin npx-Invoked CLI Tools (devpod-remote-e2e)

**Context**: `.mcp.json` used `npx -y kubernetes-mcp-server@latest`, which auto-installs whatever version is current. Combined with `-y` (auto-confirm), this is a supply-chain risk — a compromised package version gets installed without review.

**Pattern**: Always pin exact versions for npx-invoked tools. Never use `@latest` with the `-y` flag:

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "npx",
      "args": ["-y", "kubernetes-mcp-server@0.0.59"]
    }
  }
}
```

**Version discovery**: `npm view <package> version` returns the current latest. Pin to that, then update deliberately.

**When to apply**: Any `npx -y <package>@latest` in config files, scripts, or CI. The `-y` flag bypasses confirmation, so the version pin is the only supply-chain control.

---

## P63: MagicMock Auto-Attributes Bypass Type Constructors (e2e-alpha-stability)

**Context**: Production code changed `dagster_parent_id = UUID(context.run.run_id)` but the mock fixture left `context.run.run_id` as a MagicMock auto-attribute. `UUID(MagicMock())` raises `ValueError`, but a broad `except Exception` silently swallowed it — 9 tests appeared green while exercising only the error path.

**Pattern**: When production code applies type constructors (`UUID()`, `int()`, `Path()`, `float()`) to context/resource attributes, mock fixtures MUST set those attributes to values of the correct type:

```python
# ❌ MagicMock auto-attribute — UUID() will raise ValueError
context = MagicMock()
# context.run.run_id is a MagicMock object

# ✅ Explicit typed value
context = MagicMock()
context.run.run_id = str(uuid4())  # UUID() will succeed
```

**Detection**: After any production code change that adds a type constructor call on a mocked attribute, grep the test fixtures for that attribute name. If no explicit assignment exists, the mock will return a MagicMock and the constructor will fail.

**When to apply**: Any mock fixture where the production code path applies `UUID()`, `int()`, `float()`, `Path()`, `datetime.fromisoformat()`, or similar type constructors to the mocked value. Especially dangerous when the call site has broad exception handling.

---

## P64: Never Grant NOPASSWD to Shells or File-Writing Utilities (e2e-alpha-stability)

**Context**: The devcontainer Dockerfile granted `NOPASSWD` to `/bin/sh`, `/usr/bin/tee`, and `/bin/rm`. Since the container has Docker socket access (`dockerd` is also in the sudoers list), root-in-container escalates to root-on-host.

**Pattern**: Never grant passwordless sudo to general-purpose binaries. Wrap each privileged operation in a dedicated script with a fixed purpose:

```dockerfile
# ❌ Grants unrestricted root shell
echo "node ALL=(root) NOPASSWD: /bin/sh, /usr/bin/tee, /bin/rm"

# ✅ Scoped wrapper scripts
COPY fix-docker-group.sh /usr/local/bin/
RUN chmod 0555 /usr/local/bin/fix-docker-group.sh
# sudoers: node ALL=(root) NOPASSWD: /usr/local/bin/fix-docker-group.sh
```

**Dangerous binaries** (never NOPASSWD): `/bin/sh`, `/bin/bash`, `/usr/bin/tee` (can write to any file), `/bin/rm` (can delete any file), `/usr/bin/env` (arbitrary command execution).

**When to apply**: Any Dockerfile or sudoers configuration where non-root users need specific privileged operations. Always prefer dedicated wrapper scripts over granting access to general-purpose binaries.

---

## P65: Never Interpolate Credential Values into Assertion Messages (e2e-alpha-stability)

**Context**: Test assertions included credential values in failure messages: `f"Expected to match AWS_SECRET_ACCESS_KEY env var ('{env_secret_key}')"`. When tests fail in CI, pytest prints the full message to stdout, test report artifacts, and GitHub Actions summaries — leaking secrets.

**Pattern**: Assertion messages must describe what was expected without including the actual credential value:

```python
# ❌ Leaks credential to CI logs on failure
assert actual == env_secret_key, (
    f"Expected to match AWS_SECRET_ACCESS_KEY "
    f"('{env_secret_key}') or use env_var() template."
)

# ✅ Describes expectation without revealing value
assert actual == env_secret_key, (
    f"Expected to match AWS_SECRET_ACCESS_KEY env var "
    f"or use env_var() template."
)
```

**Extends**: Constitution S-VI (CWE-532 boundary clarity). This pattern applies the same principle to test assertion messages, not just exception logging.

**When to apply**: Any test assertion that compares against a value sourced from an environment variable containing credentials (`AWS_SECRET_ACCESS_KEY`, `AWS_ACCESS_KEY_ID`, API keys, passwords, tokens).

---

## P66: Kind Cluster Taint-Recovery in Docker-outside-of-Docker (e2e-alpha-stability)

**Context**: In DooD environments (devcontainer accessing host Docker daemon via mounted socket), Kind's internal taint-removal step races the API server startup. The API server needs ~8 more seconds than Kind allows, causing `kind create cluster` to fail and (without `--retain`) delete the control plane container.

**Pattern**: Use `--retain` flag and manual taint recovery:

```bash
# --retain keeps control plane container on failure
if ! kind create cluster --name "${CLUSTER_NAME}" --retain --wait "${TIMEOUT}s"; then
    # Wait for API server, then remove taint manually
    while ! docker exec "${cp_container}" \
        kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes >/dev/null 2>&1; do
        sleep 2
    done
    docker exec "${cp_container}" \
        kubectl --kubeconfig=/etc/kubernetes/admin.conf \
        taint nodes --all node-role.kubernetes.io/control-plane- 2>/dev/null || true
fi
```

**Note**: `docker exec` does NOT need `--privileged` — kubectl only makes API calls to the in-container API server. Also: the devcontainer must be connected to the `kind` Docker network to reach the control plane at its Docker IP.

**When to apply**: Any CI or development setup that creates Kind clusters inside Docker containers (DooD pattern). Not needed on bare metal or VMs where Docker runs natively.

---

## P67: dbt manifest.json Embeds Absolute Host Paths (e2e-materialization-fix)

**Context**: `dbt parse` and `dbt compile` embed the build host's absolute `root_path` into every node in `manifest.json`. `partial_parse.msgpack` caches these paths. When the manifest is generated on a host (or in a CI step) and then copied into a Docker image at a different path, dbt operations fail with "file not found" because the embedded paths point to the original host filesystem.

**Pattern**: Regenerate manifests inside the container after COPY:

```dockerfile
# Delete stale partial_parse cache, then regenerate manifest at container paths
RUN rm -f /app/demo/project_a/target/partial_parse.msgpack \
          /app/demo/project_b/target/partial_parse.msgpack \
 && cd /app/demo/project_a && dbt parse --profiles-dir . \
 && cd /app/demo/project_b && dbt parse --profiles-dir .
```

**When to apply**: Any Dockerfile that COPYs a dbt project with a pre-built `target/manifest.json`. Also relevant for CI pipelines that build manifests in one stage and consume them in another with different working directories.

---

## P68: GitHub Action Version != Tool Binary Version (e2e-materialization-fix)

**Context**: `azure/setup-helm@v4` is the GitHub Action's own semantic version (v4 of the action), NOT the Helm binary version it installs. The actual Helm binary version is controlled by the `version:` input parameter. Confusing the two led to a real bug where we believed CI was running Helm v4 when it was actually installing v3.14.0.

**Pattern**: Always distinguish action version from tool version in CI configuration:

```yaml
# The @v4 is the ACTION version, not the Helm version
- uses: azure/setup-helm@v4    # Action v4
  with:
    version: v4.1.3             # Helm binary v4.1.3 — THIS is what matters
```

**When to apply**: Any CI workflow using `setup-*` actions (setup-helm, setup-node, setup-python, setup-go). The `@vN` tag on the action is independent of the tool version installed. Always verify the `version:` input parameter matches the intended tool version.

---

## P69: Helm v4 --rollback-on-failure Does NOT Imply --wait (e2e-materialization-fix)

**Context**: In Helm v3, `--atomic` implied `--wait` (it would wait for resources to become ready before considering the release successful, and roll back on failure). In Helm v4, `--atomic` was renamed to `--rollback-on-failure`, but the new flag does NOT imply `--wait`. Without explicit `--wait`, Helm returns immediately after submitting resources, so rollback-on-failure may not detect failures that manifest during pod startup.

**Pattern**: Always pair `--rollback-on-failure` with `--wait`:

```bash
helm upgrade --install my-release chart/ \
  --rollback-on-failure \
  --wait \                  # MUST be explicit in Helm v4
  --timeout 8m
```

**When to apply**: Any Helm v4 upgrade/install command that previously used `--atomic` in v3. The migration is not just a flag rename — `--wait` must be added explicitly.

---

## P70: Docker Build Cache Bypasses New COPY Directives (e2e-test-stability)

**Context**: When adding a new `COPY` line to a Dockerfile (e.g., adding `floe-iceberg` to the demo image), Docker layer cache can silently skip the new directive if the preceding layers haven't changed. The build appears to succeed but the new package is never installed.

**Pattern**: Use `docker build --no-cache` when adding new COPY or ARG lines to a Dockerfile:

```bash
# After adding new COPY/ARG lines, first build MUST use --no-cache
docker build --no-cache -f docker/dagster-demo/Dockerfile .

# Subsequent builds can use cache normally
docker build -f docker/dagster-demo/Dockerfile .
```

**When to apply**: Any time you add a new `COPY`, `ARG`, or `RUN` line to an existing Dockerfile. Once the new layer is in the cache, normal caching works correctly.

---

## P71: Always Use 127.0.0.1, Never localhost, in Scripts (e2e-test-stability)

**Context**: macOS resolves `localhost` to `::1` (IPv6) by default, but SSH tunnels and K8s port-forwards bind to `127.0.0.1` (IPv4 only). Using `localhost` in scripts causes silent connection failures — `nc -z localhost 8181` may fail even though the service is reachable at `127.0.0.1:8181`.

**Pattern**: Always use explicit `127.0.0.1` in scripts, kubeconfig rewrites, and hook port checks:

```bash
# WRONG: may resolve to ::1 on macOS
nc -z localhost "${PORT}"
sed "s|server: .*/|server: https://localhost:${PORT}|"

# RIGHT: explicit IPv4
nc -z 127.0.0.1 "${PORT}"
sed "s|server: .*/|server: https://127.0.0.1:${PORT}|"
```

**When to apply**: Any shell script that connects to port-forwarded or tunneled services. Never use `localhost` — always use `127.0.0.1`.

---

## P72: Masking Errors — Fixing One Failure Exposes Downstream Failures (e2e-test-stability)

**Context**: When fixing a root-cause error (e.g., `No module named 'floe_iceberg'`), previously-masked downstream errors may surface (e.g., `Plugin not found: STORAGE:s3`). The import error prevented code from reaching the plugin lookup, so the lookup error was invisible until the import was fixed.

**Pattern**: When writing acceptance criteria for error-fixing work, use relative thresholds ("27 previously failing tests now pass") rather than absolute thresholds ("at most 1 failure remains"). Budget for newly-exposed failures in your success criteria:

```markdown
# FRAGILE: absolute count breaks when masking errors exist
AC: E2E suite has at most 1 failure

# ROBUST: measures improvement, tolerates newly-exposed issues
AC: The 27 previously failing tests now pass. Newly-exposed
    failures (if any) are documented and tracked separately.
```

**When to apply**: Any work unit that fixes errors which could be masking downstream issues — especially import errors, config validation, and service startup failures.

---

## P73: E2E Smoke-Check Blocks Static Tests (e2e-test-optimization)

**Context**: Session-scoped `autouse` infrastructure smoke checks in `tests/e2e/conftest.py` abort the entire pytest session if Dagster/Polaris/MinIO are unreachable. This blocks ALL tests collected under `tests/e2e/`, including tests that only perform static analysis (AST parsing, file existence checks) and need no K8s infrastructure.

**Pattern**: When writing verification tests for E2E code structure, run them via `subprocess.run([sys.executable, "-c", ...])` or as standalone scripts, not via pytest collection under the E2E directory. Alternatively, place structural validation tests in a sibling `tests/e2e/tests/` directory with its own conftest that doesn't inherit the smoke check.

```python
# DON'T: put static analysis test in tests/e2e/ (smoke check blocks it)
# tests/e2e/test_fixture_structure.py  # ← blocked by autouse smoke check

# DO: put in tests/e2e/tests/ with independent conftest
# tests/e2e/tests/test_fixture_structure.py  # ← own conftest, no smoke check

# OR: run validation as subprocess
result = subprocess.run(
    [sys.executable, "-c", "import ast; ..."],
    capture_output=True, text=True
)
assert result.returncode == 0
```

**When to apply**: Any time you need to verify E2E file structure, fixture wiring, or code patterns without running the full E2E infrastructure.

---

## P74: Distinguish dbt test (Read-Only) from dbt seed/run (Mutating) (e2e-test-optimization)

**Context**: `dbt test` validates data quality against existing tables (read-only). `dbt seed` and `dbt run` mutate table state. When optimizing E2E fixtures to share module-scoped setup, only seed/run should move to the fixture — `dbt test` calls should remain in individual test methods because they ARE the test assertion.

**Pattern**: When writing gates or static analysis that checks for "no dbt calls in read-only tests," always exclude `run_dbt(["test"])` from the check. It's validation, not setup.

```python
# These are SETUP (move to fixture):
run_dbt(["seed"], ...)   # Load test data
run_dbt(["run"], ...)    # Execute models

# This is VALIDATION (keep in test method):
run_dbt(["test"], ...)   # Assert data quality — this IS the test
```

**When to apply**: Any refactoring of dbt-based test suites, any gate that counts dbt invocations.

---

## P75: Spec AC Qualifier Consistency (e2e-test-optimization)

**Context**: AC-1 stated "total seed invocations reduced to 0" while AC-2 stated "mutating tests retain their own seed calls." These contradicted each other. The fix was adding "in read-only test methods" qualifier to AC-1.

**Pattern**: When one acceptance criterion makes an absolute claim ("X = 0", "all Y removed") and another carves out exceptions, the absolute claim MUST include the qualifier upfront. Review all ACs as a set for consistency before finalizing specs.

```markdown
# CONTRADICTORY:
AC-1.6: Total seed invocations reduced to 0
AC-2.1: Mutating tests use own seed calls  # ← wait, AC-1 said 0!

# CONSISTENT:
AC-1.6: Total seed invocations in READ-ONLY test methods reduced to 0
AC-2.1: Mutating tests use own seed calls  # ← no conflict
```

**When to apply**: During spec writing (`/sw-plan`) — always cross-check ACs for qualifier consistency before gate handoff.

---

## P76: Helm Nil Pointer on Nested Value Access (salvage-branch-wrap-up)

**Context**: `{{- if .Values.polaris.persistence.jdbc.password }}` panics when `.Values.polaris.persistence.jdbc` is nil (not set in the test case). Go templates do NOT short-circuit nested access — every intermediate key must exist.

**Pattern**: Always wrap nested Helm value access in `{{- with }}` before accessing child keys, or guard each level explicitly:

```yaml
# ❌ PANICS when .jdbc is nil
{{- if .Values.polaris.persistence.jdbc.password }}

# ✅ Safe — with scopes to .jdbc first
{{- with .Values.polaris.persistence.jdbc }}
{{- if .password }}
...
{{- end }}
{{- end }}

# ✅ Also safe — explicit nil guard at each level
{{- if and .Values.polaris.persistence.jdbc .Values.polaris.persistence.jdbc.password }}
```

Note: Inside `{{- with }}`, use `$` for global context (e.g., `{{ include "helper" $ }}`).

**When to apply**: Every Helm template that accesses values more than one level deep where intermediate keys are optional.

---

## P77: Unconditional Env Var Rendering for existingSecret Support (salvage-branch-wrap-up)

**Context**: `QUARKUS_DATASOURCE_PASSWORD` env var was gated on `{{- if .password }}` which only renders when a plaintext password exists in values. Production deployments using `existingSecret` (External Secrets Operator) have no plaintext password — the env var was silently omitted, breaking PostgreSQL auth.

**Pattern**: When a Deployment env var references a Secret key via `secretKeyRef`, render the env var unconditionally for the feature mode (e.g., whenever `persistence.type=relational-jdbc`). The Secret template handles whether to create the key inline or defer to `existingSecret`. Don't gate env var rendering on the presence of the plaintext value.

```yaml
# ❌ Breaks existingSecret pattern
{{- if .Values.polaris.persistence.jdbc.password }}
- name: QUARKUS_DATASOURCE_PASSWORD
  valueFrom:
    secretKeyRef: ...
{{- end }}

# ✅ Renders whenever the feature is enabled
{{- if eq (.Values.polaris.persistence.type | default "in-memory") "relational-jdbc" }}
- name: QUARKUS_DATASOURCE_PASSWORD
  valueFrom:
    secretKeyRef: ...
{{- end }}
```

**When to apply**: Any Helm Deployment template that injects credentials from a Secret — always key on the feature flag, not the plaintext value.

---

## P78: Env Var URI Double-Suffix (salvage-branch-wrap-up)

**Context**: Helm set `POLARIS_URI=http://polaris:8181/api/catalog` but `dbt_utils.py` appended `/api/catalog` again, creating `.../api/catalog/api/catalog`. The `PolarisConfig.uri` convention expects the full URI including path suffix. This is the 3rd env var name/value mismatch in the E2E stabilization cycle (also: `MINIO_URL` vs `MINIO_ENDPOINT`, `POLARIS_URL` vs `POLARIS_URI`).

**Pattern**: When reading env vars that contain URIs, never append path components that may already be present. Establish a single convention: either the env var contains the base URL and code appends the path, OR the env var contains the full URI and code uses it as-is. Document the convention per service.

```python
# ❌ Double-suffix risk
polaris_url = os.environ.get("POLARIS_URI", "http://polaris:8181")
catalog_uri = f"{polaris_url}/api/catalog"  # Duplicates if env already has path

# ✅ Convention: POLARIS_URI includes path, use as-is
polaris_uri = os.environ.get("POLARIS_URI", f"{ServiceEndpoint('polaris').url}/api/catalog")
catalog = load_catalog("polaris", uri=polaris_uri)  # No further appending
```

**When to apply**: Any code reading service URI env vars — verify the Helm template value and match the convention.
