# Docs Platform Starlight Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the newly added MkDocs site with a Starlight docs site that keeps `docs/` as source-of-truth.

**Architecture:** `docs/` remains authored content. `docs-site/docs-manifest.json` declares the public navigation. `docs-site/scripts/sync-docs.mjs` generates Starlight content into `docs-site/src/content/docs/` before build or serve.

**Tech Stack:** Astro 6.1.10, `@astrojs/starlight` 0.38.4, npm lockfile, existing Python validator tests.

---

### Task 1: Add Starlight Site Skeleton

**Files:**
- Create: `docs-site/package.json`
- Create: `docs-site/astro.config.mjs`
- Create: `docs-site/src/content.config.ts`
- Create: `docs-site/src/content/docs/.gitkeep`

- [ ] Add npm scripts: `sync`, `build`, `dev`, and `validate`.
- [ ] Configure Starlight with Floe title, repo link, edit links, and sidebar generated from the manifest.
- [ ] Configure Starlight content collections with `docsLoader()` and `docsSchema()`.
- [ ] Run `npm --prefix docs-site install` and commit `docs-site/package-lock.json`.

### Task 2: Add Manifest-Driven Docs Generation

**Files:**
- Create: `docs-site/docs-manifest.json`
- Create: `docs-site/scripts/sync-docs.mjs`

- [ ] Encode current alpha navigation in the manifest using `section`, `title`, `source`, and `slug`.
- [ ] Copy manifest-selected public Markdown files under `docs/` into generated Starlight content to preserve public relative links without publishing internal planning artifacts.
- [ ] Inject `title` frontmatter when source pages do not already have frontmatter.
- [ ] Clean generated content before each sync so deleted source files cannot become stale pages.

### Task 3: Replace MkDocs Validation

**Files:**
- Modify: `testing/ci/validate-docs-navigation.py`
- Modify: `testing/ci/tests/test_validate_docs_navigation.py`

- [ ] Change validation from `mkdocs.yml` navigation to `docs-site/docs-manifest.json`.
- [ ] Validate all required alpha pages exist and are included in the manifest.
- [ ] Validate manifest entries point to existing `docs/*.md` source files.
- [ ] Keep all-doc Markdown link validation and fail site-root Markdown links like `/TESTING.md`.
- [ ] Run focused validator tests.

### Task 4: Replace User And CI Entrypoints

**Files:**
- Delete: `mkdocs.yml`
- Modify: `Makefile`
- Modify: `.github/workflows/docs.yml`
- Modify: `README.md`
- Modify: `docs/start-here/index.md`
- Modify: `docs/get-started/index.md`
- Modify: `docs/get-started/first-platform.md`
- Modify: `docs/operations/troubleshooting.md`
- Modify: `docs/reference/index.md`
- Modify: `docs/contributing/index.md`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] Keep `make docs-build`, `make docs-serve`, and `make docs-validate` stable.
- [ ] Remove MkDocs and Material for MkDocs from Python dependencies.
- [ ] Update docs workflow paths and steps to install Node 24 with pinned `actions/setup-node`.
- [ ] Replace MkDocs wording in active user-facing docs with Starlight wording.

### Task 5: Verify

**Commands:**
- `uv run pytest testing/ci/tests/test_validate_docs_navigation.py -q`
- `make docs-validate`
- `make docs-build`
- `rg -n "mkdocs|mkdocs-material|Material for MkDocs" README.md docs Makefile pyproject.toml .github testing`
- `rg -n "/api/daemon/status" docs docs-site`

- [ ] Fix any failures.
- [ ] Commit the implementation.
