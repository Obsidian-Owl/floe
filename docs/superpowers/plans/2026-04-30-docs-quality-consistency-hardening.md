# Documentation Quality And Consistency Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Starlight documentation platform into release-quality user documentation that accurately explains Floe, guides first use, proves Customer 360 outcomes, and prevents future consistency drift.

**Architecture:** Keep Starlight as the site generator and keep Markdown in `docs/` as the source of truth. Fix content against the implemented system, then add deterministic docs-quality checks so stale release claims, wrong plugin counts, stub-command claims, and internal agent runbooks cannot silently ship as public docs.

**Tech Stack:** Astro Starlight, Node 24, Python 3.10+, pytest, Make, GitHub Actions, DevPod + Hetzner, Helm, Kubernetes, Dagster, MinIO, Marquez, Jaeger, Polaris, dbt, Apache Iceberg.

---

## Current Baseline

- Synced trunk: `main@098d6f0a`.
- `make docs-validate` passes mechanically.
- Primary gaps are content quality, implementation truth, public/private information architecture, and demo proof.
- The previous alpha docs plan targeted MkDocs and is superseded by Starlight for this follow-up.

## File Map

- Modify `docs/start-here/index.md`: real entry point, personas, alpha status, mental model, user journeys.
- Modify `docs/get-started/index.md`: choose-path hub with prerequisites and expected outcomes.
- Modify `docs/get-started/first-platform.md`: DevPod + Hetzner platform tutorial with expected output and cleanup.
- Modify `docs/get-started/first-data-product.md`: Customer 360 product walkthrough, artifact inspection, and next steps.
- Modify `docs/demo/customer-360.md`: complete runbook from deploy to trigger to validation.
- Modify `docs/demo/customer-360-validation.md`: UI/API proof guide with expected states and evidence examples.
- Modify `docs/operations/devpod-hetzner.md`: remote workflow details, prerequisites, status interpretation, cleanup.
- Modify `docs/operations/troubleshooting.md`: known failure classes and exact diagnostics.
- Modify `docs/reference/index.md`: user-facing reference hub only.
- Modify `docs/reference/floe-yaml-schema.md`: align examples with current schema truth.
- Create `docs/reference/plugin-catalog.md`: canonical plugin category reference generated from implementation truth.
- Modify `docs/architecture/ARCHITECTURE-SUMMARY.md`: mark implemented vs planned commands and remove stale implementation-phase framing.
- Modify `docs/architecture/plugin-system/index.md`: reconcile plugin category count and link canonical reference.
- Modify `docs/architecture/interfaces/index.md`: reconcile interface count and distinguish plugin category from public ABC.
- Modify `docs/contracts/glossary.md`: align terminology with canonical plugin catalog.
- Modify `README.md`: align product pitch, plugin count, docs site commands, and alpha caveats.
- Move or exclude `docs/reference/arch-review.md`, `docs/reference/cube-skill.md`, `docs/reference/polaris-skill.md`, and `docs/reference/pyiceberg-skill.md`: keep internal agent runbooks out of public docs.
- Modify `docs-site/docs-manifest.json`: add `plugin-catalog.md` and prevent internal runbooks from publishing.
- Modify `docs-site/scripts/sync-docs.test.mjs`: test internal runbook exclusion.
- Create `testing/ci/validate-docs-content.py`: semantic docs-quality checks.
- Create `testing/ci/tests/test_validate_docs_content.py`: unit tests for docs-quality checks.
- Create `testing/ci/tests/test_plugin_docs_consistency.py`: implementation-to-docs plugin consistency checks.
- Modify `testing/ci/validate-docs-navigation.py`: enforce required tutorial sections on alpha-critical pages.
- Modify `testing/ci/tests/test_validate_docs_navigation.py`: cover new page-section requirements.
- Modify `Makefile`: run docs content validation in `docs-validate`; add Customer 360 run target if missing.
- Modify `.github/workflows/docs.yml`: run the new docs-quality tests.
- Modify `demo/customer-360/validation.yaml`: add manifest-driven Dagster trigger metadata.
- Create `testing/demo/customer360_runner.py`: trigger Customer 360 through Dagster using manifest-configured values.
- Create `testing/ci/run_customer_360_demo.py`: CLI wrapper for the runner.
- Create `testing/tests/unit/test_customer360_runner.py`: fake HTTP tests for trigger behavior.
- Modify `docs/releases/v0.1.0-alpha.1-checklist.md`: convert stale evidence into a current release gate checklist.
- Modify `docs/validation/2026-04-29-alpha-customer-360-release-validation.md`: mark old evidence as historical or superseded.
- Create `docs/validation/2026-04-30-alpha-docs-quality-review.md`: record this docs hardening validation result.

## Task 1: Add Docs Content Quality Gates

**Files:**
- Create: `testing/ci/validate-docs-content.py`
- Create: `testing/ci/tests/test_validate_docs_content.py`
- Modify: `Makefile`
- Modify: `.github/workflows/docs.yml`

- [ ] **Step 1: Write failing tests for stale and inconsistent docs**

Create `testing/ci/tests/test_validate_docs_content.py` with tests covering:

```python
from pathlib import Path

from testing.ci.validate_docs_content import validate_docs_content


def test_rejects_stale_release_patch_claim(tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "releases"
    docs.mkdir(parents=True)
    (docs / "v0.1.0-alpha.1-checklist.md").write_text(
        "# Release\nCustomer 360 passed on an unmerged release-hardening patch.\n",
    )

    errors = validate_docs_content(tmp_path)

    assert any("unmerged release-hardening patch" in error for error in errors)


def test_rejects_internal_agent_runbook_in_public_reference(tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "reference"
    docs.mkdir(parents=True)
    (docs / "cube-skill.md").write_text(
        "---\nname: cube-semantic-layer\n---\n"
        "ALWAYS USE when building semantic layer.\n"
        "When this skill is invoked, you should verify runtime state.\n",
    )

    errors = validate_docs_content(tmp_path)

    assert any("internal agent runbook" in error for error in errors)


def test_rejects_wrong_plugin_count(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("Floe lets teams choose from 12 plugin types.\n")

    errors = validate_docs_content(tmp_path, plugin_category_count=14)

    assert any("plugin count" in error for error in errors)
```

Run:

```bash
uv run pytest testing/ci/tests/test_validate_docs_content.py -q
```

Expected: FAIL because the validator does not exist.

- [ ] **Step 2: Implement docs content validator**

Create `testing/ci/validate-docs-content.py` with these checks:

- Scan `README.md` and included public docs under `docs/`.
- Fail on stale release phrases: `unmerged release-hardening patch`, `blocked until the release-hardening patch`, `main@c1f26a1`.
- Fail on internal agent runbook phrases in public docs: `ALWAYS USE when`, `When this skill is invoked`, `$ARGUMENTS`, `Context Injection (For Future Claude Instances)`.
- Import `floe_core.plugin_types.PluginType` and require every `N plugin type`, `N plugin types`, `N plugin category`, and `N plugin categories` phrase in public docs to match `len(list(PluginType))`, unless the line is explicitly in a historical ADR section containing `Version` or `History`.
- Emit one deterministic error per offending file and line.

Run:

```bash
uv run pytest testing/ci/tests/test_validate_docs_content.py -q
```

Expected: PASS for synthetic tests.

- [ ] **Step 3: Wire validator into docs validation**

Modify `Makefile`:

```makefile
docs-validate: ## Validate docs navigation and build
	@uv run python testing/ci/validate-docs-navigation.py
	@uv run python testing/ci/validate-docs-content.py
	@npm --prefix docs-site ci
	@npm --prefix docs-site run validate
```

Modify `.github/workflows/docs.yml` so Docs CI runs:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
npm --prefix docs-site ci
npm --prefix docs-site run validate
```

- [ ] **Step 4: Verify current docs fail the new gate**

Run:

```bash
make docs-validate
```

Expected: FAIL on current stale docs claims, wrong plugin counts, and internal agent runbook pages. Keep this red state for Tasks 2-5.

## Task 2: Reconcile Canonical Product Concepts With Implementation Truth

**Files:**
- Create: `docs/reference/plugin-catalog.md`
- Create: `testing/ci/tests/test_plugin_docs_consistency.py`
- Modify: `README.md`
- Modify: `docs/architecture/plugin-system/index.md`
- Modify: `docs/architecture/interfaces/index.md`
- Modify: `docs/architecture/ARCHITECTURE-SUMMARY.md`
- Modify: `docs/contracts/glossary.md`
- Modify: `docs-site/docs-manifest.json`

- [ ] **Step 1: Write implementation-to-docs plugin consistency test**

Create `testing/ci/tests/test_plugin_docs_consistency.py`:

```python
from pathlib import Path

from floe_core.plugin_types import PluginType


ROOT = Path(__file__).resolve().parents[3]


def test_plugin_catalog_mentions_current_plugin_category_count() -> None:
    catalog = ROOT / "docs" / "reference" / "plugin-catalog.md"
    text = catalog.read_text()
    count = len(list(PluginType))
    assert f"{count} plugin categories" in text


def test_public_docs_do_not_use_stale_plugin_counts() -> None:
    count = len(list(PluginType))
    stale_phrases = {"11 plugin types", "12 plugin types", "13 plugin types"}
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
        if "docs/architecture/adr/" in path.as_posix():
            continue
        text = path.read_text()
        for phrase in stale_phrases:
            assert phrase not in text, f"{path} uses stale phrase {phrase!r}; use {count} plugin categories or avoid counts"
```

Run:

```bash
uv run pytest testing/ci/tests/test_plugin_docs_consistency.py -q
```

Expected: FAIL because `plugin-catalog.md` is missing and stale counts exist.

- [ ] **Step 2: Add canonical plugin catalog**

Create `docs/reference/plugin-catalog.md` with:

- Current implementation source: `floe_core.plugin_types.PluginType`.
- Current count: `14 plugin categories`.
- Clear distinction between `PluginType` categories and public plugin ABC reference pages.
- Table with category, entry point group, current alpha status, and owner:
  - Compute: `floe.computes`
  - Orchestrator: `floe.orchestrators`
  - Catalog: `floe.catalogs`
  - Storage: `floe.storage`
  - Telemetry backend: `floe.telemetry_backends`
  - Lineage backend: `floe.lineage_backends`
  - dbt runtime: `floe.dbt`
  - Semantic layer: `floe.semantic_layers`
  - Ingestion: `floe.ingestion`
  - Secrets: `floe.secrets` <!-- pragma: allowlist secret -->
  - Identity: `floe.identity`
  - Quality: `floe.quality`
  - RBAC: `floe.rbac`
  - Alert channel: `floe.alert_channels`
- Note that `PluginType.LINEAGE` is a code alias for `LINEAGE_BACKEND` and is not an additional category.

- [ ] **Step 3: Replace stale concept counts**

Update public docs to avoid stale counts or use the canonical phrase `14 plugin categories`:

```bash
rg -n "11 plugin|12 plugin|13 plugin|14 plugin|plugin types|plugin categories" README.md docs
```

Expected after edits:

- `README.md` aligns to `14 plugin categories`.
- `docs/architecture/plugin-system/index.md` links to `docs/reference/plugin-catalog.md`.
- `docs/architecture/interfaces/index.md` says public ABC coverage is a subset/reference surface, not the canonical category count.
- `docs/architecture/ARCHITECTURE-SUMMARY.md` stops claiming stale counts.
- `docs/contracts/glossary.md` points to the plugin catalog.

- [ ] **Step 4: Add plugin catalog to Starlight navigation**

Modify `docs-site/docs-manifest.json` under Reference:

```json
{
  "title": "Plugin Catalog",
  "source": "docs/reference/plugin-catalog.md",
  "slug": "reference/plugin-catalog"
}
```

- [ ] **Step 5: Verify plugin docs consistency**

Run:

```bash
uv run pytest testing/ci/tests/test_plugin_docs_consistency.py -q
uv run python testing/ci/validate-docs-content.py
```

Expected: PASS.

## Task 3: Rewrite The User Onboarding Journey

**Files:**
- Modify: `docs/start-here/index.md`
- Modify: `docs/get-started/index.md`
- Modify: `docs/get-started/first-platform.md`
- Modify: `docs/get-started/first-data-product.md`
- Modify: `docs/operations/devpod-hetzner.md`
- Modify: `docs/operations/troubleshooting.md`
- Modify: `testing/ci/validate-docs-navigation.py`
- Modify: `testing/ci/tests/test_validate_docs_navigation.py`

- [ ] **Step 1: Extend navigation validator with tutorial-section requirements**

Require these headings in alpha-critical tutorial pages:

- `## Prerequisites`
- `## What This Does`
- `## Steps`
- `## Expected Output`
- `## Troubleshooting`
- `## Cleanup` where the page starts infrastructure or port-forwards.

Update `testing/ci/tests/test_validate_docs_navigation.py` with one failing test where `docs/get-started/first-platform.md` is missing `## Expected Output`.

Run:

```bash
uv run pytest testing/ci/tests/test_validate_docs_navigation.py -q
```

Expected: FAIL until the validator and pages are updated.

- [ ] **Step 2: Rewrite `docs/start-here/index.md`**

The page must answer:

- What Floe is.
- Who uses it: platform engineers, data engineers, contributors.
- What the alpha supports.
- What it does not yet support.
- The four-layer model in one paragraph.
- When to use DevPod + Hetzner instead of local Kind.
- Which journey to choose next.

Required links:

- `../get-started/first-platform.md`
- `../get-started/first-data-product.md`
- `../demo/customer-360.md`
- `../architecture/four-layer-overview.md`
- `../reference/plugin-catalog.md`

- [ ] **Step 3: Rewrite `docs/get-started/first-platform.md` as a real tutorial**

Include:

- Prerequisites: DevPod CLI, Hetzner provider setup, `kubectl`, `helm`, `uv`, `npm`, repo checkout.
- Why local Kind is smoke-only and DevPod + Hetzner is the release validation lane.
- Exact commands:

```bash
make devpod-setup
make devpod-up
make devpod-sync
make devpod-status
make docs-validate
```

- Expected output patterns:

```text
workspace: reachable
kubeconfig: present
cluster: reachable
```

- Cleanup:

```bash
make devpod-stop
make devpod-delete
```

- Troubleshooting links to `../operations/troubleshooting.md`.

- [ ] **Step 4: Rewrite `docs/get-started/first-data-product.md`**

Include:

- A map of `demo/customer-360/floe.yaml`, `demo/manifest.yaml`, `demo/customer-360/dbt_project.yml`, `demo/customer-360/models/`, `demo/customer-360/compiled_artifacts.json`.
- Exact commands:

```bash
ls demo/customer-360
make compile-demo
git diff -- demo/customer-360/target/manifest.json demo/customer-360/compiled_artifacts.json
```

- Explanation of what dbt owns, what Floe compiles, and what Dagster runs.
- Expected artifacts and what they mean.
- Link to `../contracts/compiled-artifacts.md`.

- [ ] **Step 5: Expand operations and troubleshooting**

Update `docs/operations/devpod-hetzner.md` with:

- Workspace lifecycle.
- Kubeconfig sync and how to verify `KUBECONFIG`.
- Port-forward ownership: `make demo` owns automated forwards; `make devpod-tunnels` is for manual inspection.
- Status interpretation table.

Update `docs/operations/troubleshooting.md` with:

- DevPod unreachable.
- Kubeconfig stale or wrong.
- Service tunnel port already in use.
- Dagster reachable but no Customer 360 run.
- Marquez has no final mart lineage.
- Jaeger has no Customer 360 trace.
- Stale demo image symptoms.

- [ ] **Step 6: Verify onboarding docs**

Run:

```bash
uv run pytest testing/ci/tests/test_validate_docs_navigation.py -q
make docs-validate
```

Expected: PASS for navigation and docs build after Tasks 1-3.

## Task 4: Resolve The Customer 360 Trigger And Proof Gap

**Files:**
- Modify: `demo/customer-360/validation.yaml`
- Create: `testing/demo/customer360_runner.py`
- Create: `testing/ci/run_customer_360_demo.py`
- Create: `testing/tests/unit/test_customer360_runner.py`
- Modify: `Makefile`
- Modify: `docs/demo/customer-360.md`
- Modify: `docs/demo/customer-360-validation.md`

- [ ] **Step 1: Write failing tests for manifest-driven Dagster trigger**

Create `testing/tests/unit/test_customer360_runner.py` with fake HTTP responses that prove:

- Runner loads Dagster URL and expected job name from `demo/customer-360/validation.yaml`.
- Runner discovers repository/location through Dagster GraphQL rather than hardcoding repository internals.
- Runner submits the configured Customer 360 job.
- Runner prints the run id and fails clearly when the configured job is absent.

Run:

```bash
uv run pytest testing/tests/unit/test_customer360_runner.py -q
```

Expected: FAIL because the runner does not exist.

- [ ] **Step 2: Add manifest-driven trigger metadata**

Extend `demo/customer-360/validation.yaml`:

```yaml
validation:
  dagster:
    job_name: customer-360
    run_tags:
      floe.demo: customer-360
      floe.validation: alpha
```

Use the existing service URL fields. Do not hardcode the job name in Python or Make.

- [ ] **Step 3: Implement Customer 360 runner**

Implement `testing/demo/customer360_runner.py` so it:

- Loads `validation.yaml`.
- Calls Dagster GraphQL at the configured Dagster URL.
- Discovers repositories/locations from Dagster.
- Launches the manifest-configured job.
- Polls until terminal state or timeout.
- Prints deterministic output:

```text
status=PASS
dagster.run_id=<run-id>
dagster.job_name=customer-360
```

Failure output must include the missing job name, URL, and next diagnostic command.

- [ ] **Step 4: Add CLI and Make target**

Create `testing/ci/run_customer_360_demo.py` as a thin CLI wrapper.

Modify `Makefile`:

```makefile
demo-customer-360-run: ## Trigger and wait for Customer 360 golden demo run
	@uv run python -m testing.ci.run_customer_360_demo
```

Keep existing `demo-customer-360-validate`.

- [ ] **Step 5: Rewrite Customer 360 docs around actual run flow**

Update `docs/demo/customer-360.md` to make the sequence explicit:

```bash
make demo
make demo-customer-360-run
make demo-customer-360-validate
make demo-stop
```

Explain:

- `make demo` deploys services and port-forwards.
- `make demo-customer-360-run` triggers the Customer 360 Dagster job.
- `make demo-customer-360-validate` checks platform readiness, storage outputs, Marquez lineage, Jaeger traces, and business metrics.

Update `docs/demo/customer-360-validation.md` with expected evidence output:

```text
status=PASS
evidence.business.customer_count=true
evidence.business.total_lifetime_value=true
evidence.dagster.customer_360_run=true
evidence.lineage.marquez_customer_360=true
evidence.storage.customer_360_outputs=true
evidence.tracing.jaeger_customer_360=true
```

- [ ] **Step 6: Verify trigger tooling locally with unit tests**

Run:

```bash
uv run pytest testing/tests/unit/test_customer360_runner.py testing/tests/unit/test_customer360_validator.py -q
make docs-validate
```

Expected: PASS.

## Task 5: Separate Public Docs From Internal Agent Runbooks

**Files:**
- Move: `docs/reference/arch-review.md` to `docs/internal/agent-skills/arch-review.md`
- Move: `docs/reference/cube-skill.md` to `docs/internal/agent-skills/cube-skill.md`
- Move: `docs/reference/polaris-skill.md` to `docs/internal/agent-skills/polaris-skill.md`
- Move: `docs/reference/pyiceberg-skill.md` to `docs/internal/agent-skills/pyiceberg-skill.md`
- Modify: `docs-site/docs-manifest.json`
- Modify: `docs-site/scripts/sync-docs.test.mjs`
- Modify: `docs/reference/index.md`

- [ ] **Step 1: Add sync test proving internal runbooks are not published**

Add a test to `docs-site/scripts/sync-docs.test.mjs`:

```javascript
test('syncDocs does not publish docs/internal pages', async () => {
  const { repoRoot, docsSiteRoot } = await createTempDocsFixture({
    manifest: {
      includePrefixes: ['docs/'],
      excludePrefixes: ['docs/internal/'],
      sections: [{ label: 'Home', items: [{ title: 'Home', source: 'docs/index.md', slug: 'index' }] }],
    },
    files: {
      'docs/index.md': '# Home\n',
      'docs/internal/agent-skills/cube-skill.md': '# Internal\nALWAYS USE when building semantic layer.\n',
    },
  });

  await syncDocs({ repoRoot, docsSiteRoot });

  assert.equal(existsSync(path.join(docsSiteRoot, 'src/content/docs/internal/agent-skills/cube-skill.md')), false);
});
```

Adapt helper names to the current test fixture style in that file.

- [ ] **Step 2: Move internal agent runbooks**

Run:

```bash
mkdir -p docs/internal/agent-skills
git mv docs/reference/arch-review.md docs/internal/agent-skills/arch-review.md
git mv docs/reference/cube-skill.md docs/internal/agent-skills/cube-skill.md
git mv docs/reference/polaris-skill.md docs/internal/agent-skills/polaris-skill.md
git mv docs/reference/pyiceberg-skill.md docs/internal/agent-skills/pyiceberg-skill.md
```

- [ ] **Step 3: Exclude internal docs from public sync**

Modify `docs-site/docs-manifest.json`:

```json
"excludePrefixes": [
  "docs/analysis/",
  "docs/audits/",
  "docs/internal/",
  "docs/plans/",
  "docs/requirements/",
  "docs/security/",
  "docs/superpowers/"
]
```

- [ ] **Step 4: Verify no public links point at moved pages**

Run:

```bash
rg -n "arch-review|cube-skill|polaris-skill|pyiceberg-skill" docs README.md docs-site
```

Expected: no public navigation links point to moved pages. Internal references under `docs/internal/` are acceptable.

- [ ] **Step 5: Verify public/private docs split**

Run:

```bash
npm --prefix docs-site test
make docs-validate
```

Expected: PASS.

## Task 6: Correct Release Checklist And Evidence Semantics

**Files:**
- Modify: `docs/releases/v0.1.0-alpha.1-checklist.md`
- Modify: `docs/validation/2026-04-29-alpha-customer-360-release-validation.md`
- Create: `docs/validation/2026-04-30-alpha-docs-quality-review.md`

- [ ] **Step 1: Convert release checklist from stale evidence to gate checklist**

Update `docs/releases/v0.1.0-alpha.1-checklist.md` so it contains:

- Required gates.
- Command to run.
- Evidence location.
- Current status: `Not run on final merged release candidate` until final validation is complete.
- Known alpha limitations.
- Link to current validation records.

Remove stale claims that validation passed on an unmerged patch or that tagging is blocked until a now-merged patch lands.

- [ ] **Step 2: Mark old validation record as historical**

At the top of `docs/validation/2026-04-29-alpha-customer-360-release-validation.md`, add:

```markdown
> Historical evidence: this record was captured before the Starlight docs migration and before final alpha release candidate validation. Do not use it as the current release tag gate without rerunning the commands against the current merged commit.
```

- [ ] **Step 3: Record docs quality review evidence**

Create `docs/validation/2026-04-30-alpha-docs-quality-review.md` with:

- Review date.
- Current commit.
- Mechanical validation command and result.
- Findings addressed by this hardening plan.
- Remaining validation still required before tag.

- [ ] **Step 4: Verify stale release claims are gone**

Run:

```bash
uv run python testing/ci/validate-docs-content.py
rg -n "unmerged release-hardening patch|blocked until the release-hardening patch|main@c1f26a1" docs README.md
```

Expected: validator passes and `rg` returns no matches except if quoted in a historical warning that the validator explicitly allows.

## Task 7: Final Quality Gate And Remote Validation

**Files:**
- Modify: `docs/validation/2026-04-30-alpha-docs-quality-review.md`
- Modify: `docs/releases/v0.1.0-alpha.1-checklist.md`

- [ ] **Step 1: Run local docs and content gates**

Run:

```bash
make docs-validate
uv run pytest \
  testing/ci/tests/test_validate_docs_navigation.py \
  testing/ci/tests/test_validate_docs_content.py \
  testing/ci/tests/test_plugin_docs_consistency.py \
  testing/tests/unit/test_customer360_runner.py \
  testing/tests/unit/test_customer360_validator.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run broader local checks for docs plus tooling**

Run:

```bash
make lint
make typecheck
```

Expected: PASS. If failures are unrelated existing debt, capture exact output and decide whether to fix or classify before PR.

- [ ] **Step 3: Push PR**

Run:

```bash
git switch -c docs/quality-consistency-hardening
git add README.md Makefile .github/workflows/docs.yml docs docs-site testing
git commit -m "docs: harden release documentation quality"
git push -u origin docs/quality-consistency-hardening
gh pr create --base main --head docs/quality-consistency-hardening --title "Harden alpha documentation quality and consistency" --body-file - <<'EOF'
## Summary
- Rewrites alpha onboarding docs into runnable user journeys.
- Resolves Customer 360 trigger/proof documentation gap.
- Aligns plugin terminology with implementation truth.
- Moves internal agent runbooks out of public docs.
- Adds docs content quality gates to prevent stale release claims and consistency drift.

## Validation
- make docs-validate
- uv run pytest testing/ci/tests/test_validate_docs_navigation.py testing/ci/tests/test_validate_docs_content.py testing/ci/tests/test_plugin_docs_consistency.py testing/tests/unit/test_customer360_runner.py testing/tests/unit/test_customer360_validator.py -q
- make lint
- make typecheck
EOF
```

- [ ] **Step 4: After merge, run final DevPod + Hetzner validation on `main`**

Run:

```bash
git checkout main
git pull --ff-only origin main
make devpod-status
make demo
make demo-customer-360-run
make demo-customer-360-validate
make demo-stop
```

Expected:

```text
status=PASS
evidence.dagster.customer_360_run=true
evidence.storage.customer_360_outputs=true
evidence.lineage.marquez_customer_360=true
evidence.tracing.jaeger_customer_360=true
evidence.business.customer_count=true
evidence.business.total_lifetime_value=true
```

- [ ] **Step 5: Capture final evidence**

Update `docs/releases/v0.1.0-alpha.1-checklist.md` and `docs/validation/2026-04-30-alpha-docs-quality-review.md` with:

- Final merged commit.
- CI URLs.
- Docs validation result.
- Customer 360 run id.
- Customer 360 validation output.
- Any remaining known alpha limitations.

Open a small evidence-only PR if the validation evidence is captured after the main hardening PR merges.

## Completion Criteria

- The docs answer what Floe is, who uses it, how to deploy the first platform, how to build the first data product, and how to prove the Customer 360 business outcome.
- Public docs no longer publish internal agent skill runbooks.
- Docs no longer present stubbed commands as complete user workflows.
- Plugin category terminology is consistent with `PluginType`.
- Release checklist no longer contains stale pre-merge evidence.
- `make docs-validate` catches navigation, link, build, stale-claim, internal-runbook, and plugin-count regressions.
- Customer 360 docs have an explicit deploy, trigger, validate, inspect, and cleanup path.
- Final DevPod + Hetzner validation evidence is captured before alpha tagging.

## Self-Review

- Spec coverage: covers all current review findings: thin onboarding docs, stub command claims, Customer 360 trigger gap, stale release evidence, plugin count drift, internal runbook publication, and missing consistency gates.
- Placeholder scan: no `TBD`, `TODO`, or "fill in later" placeholders are present.
- Type consistency: validator names, Make targets, and Customer 360 runner names are consistent across tasks.
