# Persona-Aligned Docs And Kubernetes Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the alpha docs so Platform Engineers and Data Engineers get provider-neutral Kubernetes onboarding, while DevPod + Hetzner is clearly scoped to Floe Contributors and release validation.

**Architecture:** Keep source Markdown readable in GitHub and generate Starlight-compatible content during docs sync. Split navigation by Floe personas, add source-doc quality gates for provider/persona/capability drift, and correct deployment/testing guides so public claims match implemented alpha behavior.

**Tech Stack:** Starlight, Astro, Node 24 `node:test`, Markdown docs, `docs-site` sync/build scripts, Makefile docs targets.

---

## File Structure

- Modify `docs-site/scripts/sync-docs.mjs`: derive Starlight titles from source docs and strip duplicated generated H1s.
- Modify `docs-site/scripts/sync-docs.test.mjs`: add regression tests for generated heading behavior.
- Create `docs-site/scripts/check-source-docs.mjs`: validate source Markdown against provider/persona/capability rules before build.
- Create or modify `docs-site/scripts/check-source-docs.test.mjs`: unit tests for source-doc validation rules.
- Modify `docs-site/package.json`: add `check:source` and include it in `validate`.
- Modify `docs-site/docs-manifest.json`: replace generic Get Started/Operations navigation with Platform Engineers, Data Engineers, and Floe Contributors.
- Modify `docs/index.md`: describe the persona model and current alpha status.
- Modify `docs/start-here/index.md`: route readers by persona and remove DevPod as the product-first path.
- Create `docs/platform-engineers/index.md`: Platform Engineer landing page.
- Create `docs/platform-engineers/first-platform.md`: provider-neutral Kubernetes deployment guide.
- Create `docs/platform-engineers/validate-platform.md`: platform validation guide for service UIs and Customer 360 platform evidence.
- Create `docs/data-engineers/index.md`: Data Engineer landing page.
- Create `docs/data-engineers/first-data-product.md`: Data Engineer first product guide using Customer 360.
- Create `docs/data-engineers/validate-data-product.md`: Data Engineer validation guide.
- Modify `docs/get-started/index.md`: persona router, not contributor command checklist.
- Modify `docs/get-started/first-platform.md`: short bridge to Platform Engineer first-platform guide.
- Modify `docs/get-started/first-data-product.md`: short bridge to Data Engineer first-data-product guide.
- Move `docs/operations/devpod-hetzner.md` to `docs/contributing/devpod-hetzner.md`: contributor remote validation guide.
- Create `docs/contributing/testing.md`: contributor test strategy landing page.
- Modify `docs/contributing/index.md`: link contributor environment, testing, docs authoring, and release validation.
- Modify `docs/demo/customer-360.md` and `docs/demo/customer-360-validation.md`: keep Customer 360 as the golden demo, but avoid saying DevPod is the product requirement.
- Modify `docs/demo/index.md`: describe Customer 360 without making DevPod the product path.
- Modify `docs/guides/deployment/index.md`: accurate deployment overview with capability statuses.
- Modify `docs/guides/deployment/local-development.md`: use actual `make kind-up` and `make kind-down`, and keep this contributor/evaluation scoped.
- Modify `docs/guides/deployment/kubernetes-helm.md`: align Helm commands with current chart names and avoid unvalidated production claims.
- Modify `docs/guides/deployment/data-mesh.md`: mark Data Mesh as architecture and implemented primitives, not alpha-supported operations.
- Modify `docs/guides/testing/index.md`: bridge to Platform/Data Engineer validation and Contributor testing.
- Modify `Makefile`: update DevPod help text so it is contributor/release-validation scoped.

## Task 1: Fix Starlight Generated Heading Duplication

**Files:**
- Modify: `docs-site/scripts/sync-docs.mjs`
- Test: `docs-site/scripts/sync-docs.test.mjs`

- [ ] **Step 1: Add failing tests for duplicate H1 stripping**

Append these tests to `docs-site/scripts/sync-docs.test.mjs`:

```js
test('syncDocs removes the source H1 from generated Starlight content', async () => {
  await withDocsFixture(async ({ repoRoot, docsSiteRoot }) => {
    await fs.writeFile(
      path.join(repoRoot, 'docs/source-page.md'),
      '# Source Page\n\nIntro paragraph.\n\n## Next Section\n',
    );
    await writeManifest(docsSiteRoot, [
      {
        title: 'Source Page',
        source: 'docs/source-page.md',
        slug: 'source-page',
      },
    ]);

    await syncDocs({ repoRoot, docsSiteRoot });

    const generatedSource = await fs.readFile(
      path.join(docsSiteRoot, 'src/content/docs/source-page.md'),
      'utf8',
    );

    assert.match(generatedSource, /^---\ntitle: "Source Page"\n---\n\nIntro paragraph/u);
    assert.doesNotMatch(generatedSource, /^# Source Page$/mu);
    assert.match(generatedSource, /^## Next Section$/mu);
  });
});

test('syncDocs preserves a non-title H1 that appears later in the body', async () => {
  await withDocsFixture(async ({ repoRoot, docsSiteRoot }) => {
    await fs.writeFile(
      path.join(repoRoot, 'docs/source-page.md'),
      'Intro paragraph.\n\n# Deliberate Later Heading\n',
    );
    await writeManifest(docsSiteRoot, [
      {
        title: 'Source Page',
        source: 'docs/source-page.md',
        slug: 'source-page',
      },
    ]);

    await syncDocs({ repoRoot, docsSiteRoot });

    const generatedSource = await fs.readFile(
      path.join(docsSiteRoot, 'src/content/docs/source-page.md'),
      'utf8',
    );

    assert.match(generatedSource, /^---\ntitle: "Deliberate Later Heading"\n---/u);
    assert.match(generatedSource, /^Intro paragraph\.\n\n# Deliberate Later Heading$/mu);
  });
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd docs-site
node --test scripts/sync-docs.test.mjs
```

Expected: first new test fails because generated content still contains `# Source Page`.

- [ ] **Step 3: Implement generated-title H1 stripping**

Add these helpers after `titleFromMarkdown()` in `docs-site/scripts/sync-docs.mjs`:

```js
function titleFromFrontmatterOrMarkdown(markdown, relativePath) {
  const frontmatter = markdown.match(/^---\n([\s\S]*?)\n---\n?/u);
  const title = frontmatter?.[1].match(/^title:\s*(.+)$/m)?.[1];
  if (title) {
    return title.trim().replace(/^['"]|['"]$/gu, '').replace(/`/gu, '');
  }

  return titleFromMarkdown(markdown, relativePath);
}

function normalizedHeadingText(value) {
  return value.replace(/`/gu, '').trim();
}

function withoutGeneratedTitleHeading(markdown, relativePath) {
  const title = titleFromFrontmatterOrMarkdown(markdown, relativePath);
  const frontmatter = markdown.match(/^---\n([\s\S]*?)\n---\n?/u);
  const prefix = frontmatter ? frontmatter[0] : '';
  const body = markdown.slice(prefix.length);
  const firstHeading = body.match(/^#\s+(.+)\n?/u);

  if (!firstHeading) {
    return markdown;
  }

  if (normalizedHeadingText(firstHeading[1]) !== normalizedHeadingText(title)) {
    return markdown;
  }

  return `${prefix}${body.slice(firstHeading[0].length).replace(/^\n/u, '')}`;
}
```

Then change the write pipeline in `syncDocs()` to call the new helper after frontmatter injection:

```js
const rewrittenMarkdown = rewriteMarkdownLinks(
  markdown,
  entry.source,
  publishedSourceRoutes,
  repoRoot,
);
const withFrontmatter = withStarlightFrontmatter(
  rewrittenMarkdown,
  entry.targetRelativePath,
);
const withoutDuplicateHeading = withoutGeneratedTitleHeading(
  withFrontmatter,
  entry.targetRelativePath,
);

await fs.writeFile(targetPath, normalizeGeneratedMarkdown(withoutDuplicateHeading));
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd docs-site
node --test scripts/sync-docs.test.mjs
```

Expected: all `sync-docs` tests pass.

- [ ] **Step 5: Commit**

```bash
git add docs-site/scripts/sync-docs.mjs docs-site/scripts/sync-docs.test.mjs
git commit -m "fix: remove duplicate Starlight page headings"
```

## Task 2: Add Source Docs Quality Gates

**Files:**
- Create: `docs-site/scripts/check-source-docs.mjs`
- Create: `docs-site/scripts/check-source-docs.test.mjs`
- Modify: `docs-site/package.json`

- [ ] **Step 1: Write failing tests for provider, command, chart, and internal-link drift**

Create `docs-site/scripts/check-source-docs.test.mjs`:

```js
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { collectSourceDocsErrors } from './check-source-docs.mjs';

async function withSourceDocsFixture(callback) {
  const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'floe-source-docs-'));
  const docsSiteRoot = path.join(repoRoot, 'docs-site');
  const manifestPath = path.join(docsSiteRoot, 'docs-manifest.json');

  await fs.mkdir(path.join(repoRoot, 'docs'), { recursive: true });
  await fs.mkdir(docsSiteRoot, { recursive: true });
  await fs.writeFile(
    manifestPath,
    JSON.stringify({
      includePrefixes: ['docs/'],
      excludePrefixes: ['docs/superpowers/'],
      sections: [],
    }),
  );

  try {
    await callback({ repoRoot, manifestPath });
  } finally {
    await fs.rm(repoRoot, { recursive: true, force: true });
  }
}

test('collectSourceDocsErrors rejects Hetzner coupling outside contributor docs', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/platform-engineers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/platform-engineers/first-platform.md'),
      '# First Platform\n\nRequires Hetzner credentials.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/platform-engineers/first-platform.md: references Hetzner outside Floe Contributor docs',
    ]);
  });
});

test('collectSourceDocsErrors allows Hetzner in contributor DevPod docs', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/contributing'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/contributing/devpod-hetzner.md'),
      '# DevPod + Hetzner\n\nUse Hetzner for contributor validation.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, []);
  });
});

test('collectSourceDocsErrors rejects missing chart and Makefile target references', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/guides/deployment'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/guides/deployment/data-mesh.md'),
      '# Data Mesh\n\nRun `helm install sales-domain charts/floe-domain` and `make kind-create`.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/guides/deployment/data-mesh.md: references missing chart charts/floe-domain',
      'docs/guides/deployment/data-mesh.md: references missing Makefile target make kind-create',
    ]);
  });
});

test('collectSourceDocsErrors rejects user-facing links to internal agent rules', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/data-engineers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/data-engineers/validate-data-product.md'),
      '# Validate\n\nSee [testing](../../.claude/rules/testing-standards.md).\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/data-engineers/validate-data-product.md: links internal .claude path',
    ]);
  });
});
```

- [ ] **Step 2: Run tests and verify they fail because the script does not exist**

Run:

```bash
cd docs-site
node --test scripts/check-source-docs.test.mjs
```

Expected: FAIL with module-not-found for `check-source-docs.mjs`.

- [ ] **Step 3: Implement the source docs checker**

Create `docs-site/scripts/check-source-docs.mjs`:

```js
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const defaultDocsSiteRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const defaultRepoRoot = path.resolve(defaultDocsSiteRoot, '..');
const defaultManifestPath = path.join(defaultDocsSiteRoot, 'docs-manifest.json');

const allowedHetznerSources = new Set([
  'docs/contributing/devpod-hetzner.md',
  'docs/contributing/release-validation.md',
]);

const disallowedSnippets = [
  {
    pattern: /charts\/floe-domain/u,
    message: 'references missing chart charts/floe-domain',
  },
  {
    pattern: /make\s+kind-create/u,
    message: 'references missing Makefile target make kind-create',
  },
  {
    pattern: /make\s+kind-delete/u,
    message: 'references missing Makefile target make kind-delete',
  },
  {
    pattern: /\.claude\//u,
    message: 'links internal .claude path',
  },
];

async function walkMarkdownFiles(directory) {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkMarkdownFiles(absolutePath)));
    } else if (entry.isFile() && entry.name.endsWith('.md')) {
      files.push(absolutePath);
    }
  }

  return files;
}

function toPosixPath(value) {
  return value.split(path.sep).join(path.posix.sep);
}

function isIncludedByPrefix(source, prefixes) {
  return prefixes.some((prefix) => source === prefix || source.startsWith(prefix));
}

async function publishedMarkdownSources(repoRoot, manifestPath) {
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  const includePrefixes = manifest.includePrefixes ?? [];
  const excludePrefixes = manifest.excludePrefixes ?? [];
  const docsRoot = path.join(repoRoot, 'docs');
  const markdownFiles = await walkMarkdownFiles(docsRoot);

  return markdownFiles
    .map((file) => path.posix.join('docs', toPosixPath(path.relative(docsRoot, file))))
    .filter((source) => isIncludedByPrefix(source, includePrefixes))
    .filter((source) => !isIncludedByPrefix(source, excludePrefixes))
    .sort((left, right) => left.localeCompare(right));
}

export async function collectSourceDocsErrors({
  repoRoot = defaultRepoRoot,
  manifestPath = defaultManifestPath,
} = {}) {
  const sources = await publishedMarkdownSources(repoRoot, manifestPath);
  const errors = [];

  for (const source of sources) {
    const markdown = await fs.readFile(path.join(repoRoot, source), 'utf8');

    if (/\bHetzner\b/u.test(markdown) && !allowedHetznerSources.has(source)) {
      errors.push(`${source}: references Hetzner outside Floe Contributor docs`);
    }

    for (const rule of disallowedSnippets) {
      if (rule.pattern.test(markdown)) {
        errors.push(`${source}: ${rule.message}`);
      }
    }
  }

  return { checkedCount: sources.length, errors };
}

async function checkSourceDocs() {
  const { checkedCount, errors } = await collectSourceDocsErrors();

  if (errors.length > 0) {
    for (const error of errors) {
      console.error(error);
    }
    process.exitCode = 1;
    return;
  }

  console.log(`Checked ${checkedCount} source docs pages.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  checkSourceDocs().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
```

- [ ] **Step 4: Wire the checker into docs validation**

Modify `docs-site/package.json` scripts:

```json
{
  "scripts": {
    "sync": "node scripts/sync-docs.mjs",
    "test": "node --test scripts/*.test.mjs",
    "build": "npm run sync && ASTRO_TELEMETRY_DISABLED=1 astro build",
    "dev": "npm run sync && ASTRO_TELEMETRY_DISABLED=1 astro dev",
    "check:source": "node scripts/check-source-docs.mjs",
    "check:dist": "node scripts/check-built-docs.mjs",
    "validate": "npm run test && npm run check:source && npm run build && npm run check:dist"
  }
}
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd docs-site
node --test scripts/check-source-docs.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Run the checker against current docs and capture expected failures**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: FAIL before later docs tasks because current published docs still mention Hetzner outside contributor docs and still reference unsupported deployment snippets.

- [ ] **Step 7: Commit**

```bash
git add docs-site/scripts/check-source-docs.mjs docs-site/scripts/check-source-docs.test.mjs docs-site/package.json
git commit -m "test: add docs source quality gates"
```

## Task 3: Restructure Docs Navigation Around Floe Personas

**Files:**
- Modify: `docs-site/docs-manifest.json`
- Modify: `docs/index.md`
- Modify: `docs/start-here/index.md`
- Create: `docs/platform-engineers/index.md`
- Create: `docs/data-engineers/index.md`
- Modify: `docs/contributing/index.md`

- [ ] **Step 1: Update manifest publication prefixes and navigation**

Replace `includePrefixes` in `docs-site/docs-manifest.json` with:

```json
[
  "docs/architecture/",
  "docs/contracts/",
  "docs/contributing/",
  "docs/data-engineers/",
  "docs/demo/",
  "docs/get-started/",
  "docs/guides/",
  "docs/index.md",
  "docs/platform-engineers/",
  "docs/reference/",
  "docs/releases/",
  "docs/start-here/"
]
```

This removes `docs/operations/` from generated-site publication. The DevPod guide moves to `docs/contributing/`, and operation-specific troubleshooting should be rewritten under persona-specific docs before it is republished.

Replace the `sections` array with this structure while preserving the updated `includePrefixes` and existing `excludePrefixes`:

```json
[
  {
    "label": "Home",
    "items": [
      {
        "title": "Home",
        "source": "docs/index.md",
        "slug": "index"
      },
      {
        "title": "Start Here",
        "source": "docs/start-here/index.md",
        "slug": "start-here"
      }
    ]
  },
  {
    "label": "Platform Engineers",
    "items": [
      {
        "title": "Platform Engineers",
        "source": "docs/platform-engineers/index.md",
        "slug": "platform-engineers"
      },
      {
        "title": "Deploy Your First Platform",
        "source": "docs/platform-engineers/first-platform.md",
        "slug": "platform-engineers/first-platform"
      },
      {
        "title": "Validate Your Platform",
        "source": "docs/platform-engineers/validate-platform.md",
        "slug": "platform-engineers/validate-platform"
      },
      {
        "title": "Deployment Guides",
        "source": "docs/guides/deployment/index.md",
        "slug": "guides/deployment"
      }
    ]
  },
  {
    "label": "Data Engineers",
    "items": [
      {
        "title": "Data Engineers",
        "source": "docs/data-engineers/index.md",
        "slug": "data-engineers"
      },
      {
        "title": "Build Your First Data Product",
        "source": "docs/data-engineers/first-data-product.md",
        "slug": "data-engineers/first-data-product"
      },
      {
        "title": "Validate Your Data Product",
        "source": "docs/data-engineers/validate-data-product.md",
        "slug": "data-engineers/validate-data-product"
      },
      {
        "title": "Customer 360 Golden Demo",
        "source": "docs/demo/customer-360.md",
        "slug": "demo/customer-360"
      }
    ]
  },
  {
    "label": "Architecture",
    "items": [
      {
        "title": "Architecture Summary",
        "source": "docs/architecture/ARCHITECTURE-SUMMARY.md",
        "slug": "architecture/ARCHITECTURE-SUMMARY"
      },
      {
        "title": "Four-Layer Model",
        "source": "docs/architecture/four-layer-overview.md",
        "slug": "architecture/four-layer-overview"
      },
      {
        "title": "Plugin System",
        "source": "docs/architecture/plugin-system/index.md",
        "slug": "architecture/plugin-system"
      },
      {
        "title": "Opinionation Boundaries",
        "source": "docs/architecture/opinionation-boundaries.md",
        "slug": "architecture/opinionation-boundaries"
      },
      {
        "title": "Capability Status",
        "source": "docs/architecture/capability-status.md",
        "slug": "architecture/capability-status"
      }
    ]
  },
  {
    "label": "Reference",
    "items": [
      {
        "title": "Reference",
        "source": "docs/reference/index.md",
        "slug": "reference"
      },
      {
        "title": "floe.yaml Schema",
        "source": "docs/reference/floe-yaml-schema.md",
        "slug": "reference/floe-yaml-schema"
      },
      {
        "title": "Compiled Artifacts",
        "source": "docs/contracts/compiled-artifacts.md",
        "slug": "contracts/compiled-artifacts"
      },
      {
        "title": "Plugin Catalog",
        "source": "docs/reference/plugin-catalog.md",
        "slug": "reference/plugin-catalog"
      },
      {
        "title": "Data Contract Reference",
        "source": "docs/contracts/datacontract-yaml-reference.md",
        "slug": "contracts/datacontract-yaml-reference"
      }
    ]
  },
  {
    "label": "Floe Contributors",
    "items": [
      {
        "title": "Contributing",
        "source": "docs/contributing/index.md",
        "slug": "contributing"
      },
      {
        "title": "DevPod + Hetzner",
        "source": "docs/contributing/devpod-hetzner.md",
        "slug": "contributing/devpod-hetzner"
      },
      {
        "title": "Contributor Testing",
        "source": "docs/contributing/testing.md",
        "slug": "contributing/testing"
      },
      {
        "title": "Documentation Standards",
        "source": "docs/contributing/documentation-standards.md",
        "slug": "contributing/documentation-standards"
      },
      {
        "title": "Alpha Checklist",
        "source": "docs/releases/v0.1.0-alpha.1-checklist.md",
        "slug": "releases/v0.1.0-alpha.1-checklist"
      }
    ]
  }
]
```

- [ ] **Step 2: Add persona landing pages**

Create `docs/platform-engineers/index.md`:

```markdown
# Platform Engineers

Platform Engineers use Floe to deploy and operate governed data platform services on Kubernetes.

## What You Own

- Kubernetes cluster access and platform namespace setup.
- Platform manifest choices for compute, catalog, storage, orchestration, lineage, observability, and security.
- Helm installation, upgrades, rollback, service access, and operational validation.
- Secrets, object storage, ingress, TLS, and persistence choices for your environment.

## Start Here

1. [Deploy your first platform](first-platform.md).
2. [Validate your platform](validate-platform.md).
3. [Review deployment guides](../guides/deployment/index.md).
4. [Run Customer 360](../demo/customer-360.md) to prove the platform path end to end.

## What This Path Does Not Require

You do not need DevPod or Hetzner to deploy Floe as a product. DevPod + Hetzner is a contributor and release-validation path for running heavyweight checks outside a laptop.
```

Create `docs/data-engineers/index.md`:

```markdown
# Data Engineers

Data Engineers use Floe to build governed data products on an existing Floe platform.

## What You Own

- `floe.yaml` data product configuration.
- dbt models, tests, and product contracts.
- Product validation, deployment, lineage inspection, and business output checks.

## Start Here

1. [Build your first data product](first-data-product.md).
2. [Validate your data product](validate-data-product.md).
3. [Run the Customer 360 demo](../demo/customer-360.md).
4. [Review the floe.yaml schema](../reference/floe-yaml-schema.md).

## What This Path Does Not Require

You do not need DevPod, Hetzner, or Floe contributor tooling. Start from a Floe platform that a Platform Engineer has deployed and validated.
```

- [ ] **Step 3: Rewrite home and start-here routing**

Modify `docs/index.md` so its "Alpha User Journeys" section becomes:

```markdown
## Alpha Journeys

| Persona | Start Here | Outcome |
| --- | --- | --- |
| Platform Engineer | [Deploy your first platform](./platform-engineers/first-platform.md) | A Floe platform running on a Kubernetes cluster you control |
| Data Engineer | [Build your first data product](./data-engineers/first-data-product.md) | A governed Customer 360 data product running on Floe |
| Floe Contributor | [Contributing](./contributing/index.md) | A local or remote development environment for changing Floe itself |
```

Modify `docs/start-here/index.md` so the "Choose Your Journey" section becomes:

```markdown
## Choose Your Journey

- Choose [Platform Engineers](../platform-engineers/index.md) if you deploy and operate Floe platforms.
- Choose [Data Engineers](../data-engineers/index.md) if you build data products on an existing Floe platform.
- Choose [Floe Contributors](../contributing/index.md) if you change Floe itself or run release validation.

## Deployment Model

Floe's product deployment model is bring any conformant Kubernetes cluster. DevPod + Hetzner is a contributor and release-validation workspace, not a product requirement.
```

- [ ] **Step 4: Run docs sync to find missing files**

Run:

```bash
cd docs-site
npm run sync
```

Expected: FAIL until `docs/platform-engineers/first-platform.md`, `docs/platform-engineers/validate-platform.md`, `docs/data-engineers/first-data-product.md`, `docs/data-engineers/validate-data-product.md`, `docs/contributing/devpod-hetzner.md`, `docs/contributing/testing.md`, and `docs/architecture/capability-status.md` exist.

- [ ] **Step 5: Commit only navigation and landing pages after dependent files exist in later tasks**

Do not commit this task until Tasks 4, 5, 6, 7, and 8 create the files referenced by the manifest. The commit command belongs at the end of Task 8.

## Task 4: Write Platform Engineer Onboarding

**Files:**
- Create: `docs/platform-engineers/first-platform.md`
- Create: `docs/platform-engineers/validate-platform.md`
- Modify: `docs/get-started/index.md`
- Modify: `docs/get-started/first-platform.md`

- [ ] **Step 1: Create provider-neutral first platform guide**

Create `docs/platform-engineers/first-platform.md`:

````markdown
# Deploy Your First Platform

This guide deploys Floe to a Kubernetes cluster you control. Floe does not require a specific cloud provider for the product path.

## Prerequisites

- `kubectl` points at the cluster where you want to deploy Floe.
- `helm` is installed locally.
- You can create namespaces, secrets, services, deployments, jobs, and persistent volume claims.
- You have decided how Floe should access object storage, catalog services, lineage, tracing, and secrets for this environment.

For local evaluation, use Kind. For real deployment, use your organization's Kubernetes platform and durable backing services.

## 1. Confirm Your Cluster Context

```bash
kubectl config current-context
kubectl cluster-info
kubectl auth can-i create namespace
```

Expected outcome:

- `kubectl config current-context` shows the cluster you intend to use.
- `kubectl cluster-info` returns Kubernetes API information.
- `kubectl auth can-i create namespace` returns `yes`.

## 2. Choose The Deployment Mode

| Mode | Use When | Notes |
| --- | --- | --- |
| Evaluation | You want to inspect Floe quickly | Use Kind or another disposable cluster |
| Real Kubernetes deployment | You want Floe on managed or self-hosted Kubernetes | Bring durable storage, secrets, ingress, and backup choices |
| Contributor validation | You are developing Floe itself | Use the Floe Contributor DevPod guide |

## 3. Prepare Platform Configuration

Start with the alpha platform values that match the Customer 360 path, then replace environment-specific settings for your cluster.

```bash
helm dependency update ./charts/floe-platform
helm template floe ./charts/floe-platform --namespace floe-dev --create-namespace >/tmp/floe-platform-rendered.yaml
```

Expected outcome:

- Helm renders Kubernetes resources without schema errors.
- The rendered resources reference your selected namespace and values.

## 4. Install Floe

```bash
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

Expected outcome:

- Helm reports the release as deployed.
- Platform pods begin starting in the `floe-dev` namespace.

## 5. Wait For Platform Services

```bash
kubectl get pods -n floe-dev
kubectl wait --for=condition=Ready pods --all -n floe-dev --timeout=10m
```

Expected outcome:

- Required platform pods reach `Ready`.
- If a pod does not become ready, inspect `kubectl describe pod` and `kubectl logs` for that pod before continuing.

## 6. Validate The Platform

Continue with [Validate Your Platform](validate-platform.md).

## Cloud Provider Examples

Provider-specific guides are examples, not requirements. EKS, GKE, AKS, and Hetzner can all be documented after each path is validated. The alpha product contract remains Kubernetes, Helm, manifests, and Floe artifacts.
````

- [ ] **Step 2: Create Platform Engineer validation guide**

Create `docs/platform-engineers/validate-platform.md`:

````markdown
# Validate Your Platform

Use this guide after installing Floe to confirm that the platform is reachable and ready for a Data Engineer to run a data product.

## Platform Health

```bash
kubectl get pods -n floe-dev
helm status floe -n floe-dev
```

Expected outcome:

- Helm release status is `deployed`.
- Platform pods are `Running` or `Completed` according to their workload type.

## Service Access

Open service access using your normal Kubernetes access pattern. For local evaluation, port-forward the services you want to inspect.

```bash
kubectl port-forward -n floe-dev svc/dagster-webserver 3100:3000
```

Expected outcome:

- Dagster is reachable at `http://localhost:3100`.
- Platform service access uses your cluster access method, not a cloud-provider-specific Floe requirement.

## Customer 360 Platform Evidence

Run the Customer 360 validation path after the data product has been deployed and run:

```bash
make demo-customer-360-validate
```

Expected evidence keys:

- `platform.ready`
- `dagster.customer_360_run`
- `storage.customer_360_outputs`
- `lineage.marquez_customer_360`
- `tracing.jaeger_customer_360`
- `business.customer_count`
- `business.total_lifetime_value`

## What To Hand To Data Engineers

Give Data Engineers:

- The Floe platform endpoint and namespace.
- The data product deployment command for your environment.
- The service URLs they can use for Dagster, lineage, traces, storage, and query validation.
- Any secrets or identities they need through your approved access process.
````

- [ ] **Step 3: Turn legacy get-started pages into persona routing**

Replace `docs/get-started/index.md` with:

```markdown
# Get Started

Choose the path that matches your role.

| Role | Start Here | Outcome |
| --- | --- | --- |
| Platform Engineer | [Deploy your first platform](../platform-engineers/first-platform.md) | A Floe platform running on Kubernetes |
| Data Engineer | [Build your first data product](../data-engineers/first-data-product.md) | A governed data product running on Floe |
| Floe Contributor | [Contributing](../contributing/index.md) | A development or release-validation workspace |
```

Replace `docs/get-started/first-platform.md` with:

```markdown
# Deploy Your First Platform

The current Platform Engineer guide lives at [Deploy Your First Platform](../platform-engineers/first-platform.md).

Floe's product deployment model is bring any conformant Kubernetes cluster. DevPod + Hetzner is documented for Floe Contributors and release validation, not as a product requirement.
```

- [ ] **Step 4: Run source checker and expect remaining failures from later tasks**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: Hetzner failures from `docs/start-here/index.md` and demo docs still remain until later tasks. `docs/operations/` is no longer published after the manifest prefix update.

## Task 5: Write Data Engineer Onboarding

**Files:**
- Create: `docs/data-engineers/first-data-product.md`
- Create: `docs/data-engineers/validate-data-product.md`
- Modify: `docs/get-started/first-data-product.md`

- [ ] **Step 1: Create first data product guide**

Create `docs/data-engineers/first-data-product.md`:

````markdown
# Build Your First Data Product

This guide starts from an existing Floe platform. A Platform Engineer should already have deployed and validated the platform.

## Prerequisites

- Access to the target Floe platform.
- A data product project with `floe.yaml`.
- dbt project files for the product transformations.
- Access to the approved compute, storage, catalog, lineage, and observability integrations for the platform.

## 1. Inspect The Product Configuration

```bash
ls demo/customer-360
sed -n '1,160p' demo/customer-360/floe.yaml
```

Expected outcome:

- The product declares its name, owner, inputs, outputs, and runtime expectations in `floe.yaml`.
- dbt models live with the product source.

## 2. Validate The Product

```bash
uv run floe data validate demo/customer-360/floe.yaml
```

Expected outcome:

- Floe reports schema-valid product configuration.
- Validation errors point to fields in `floe.yaml` that need correction.

## 3. Compile The Product

```bash
uv run floe data compile demo/customer-360/floe.yaml --output target/customer-360
```

Expected outcome:

- Floe writes compiled artifacts under `target/customer-360`.
- The artifacts are the handoff contract for orchestration, dbt, lineage, and platform services.

## 4. Run The Product

Use the run command or deployment command documented by your Platform Engineer for the target platform. For the alpha Customer 360 path, use the Customer 360 demo guide:

```bash
make demo-customer-360-run
```

Expected outcome:

- The Customer 360 run completes successfully.
- The platform records run, lineage, trace, storage, and business output evidence.

## 5. Validate The Product Outputs

Continue with [Validate Your Data Product](validate-data-product.md).
````

- [ ] **Step 2: Create data product validation guide**

Create `docs/data-engineers/validate-data-product.md`:

````markdown
# Validate Your Data Product

Use this guide to prove that a data product produced useful outputs on a Floe platform.

## Validate Business Outputs

```bash
make demo-customer-360-validate
```

Expected outcome:

- `evidence.business.customer_count` is a non-negative integer.
- `evidence.business.total_lifetime_value` is a non-negative decimal.

## Inspect Orchestration

Open Dagster using the service URL provided by your Platform Engineer.

Pass criteria:

- The latest Customer 360 run succeeded.
- The run uses the expected job or asset definitions.

## Inspect Storage

Open the object storage or Iceberg catalog view provided by your Platform Engineer.

Pass criteria:

- Customer 360 output objects or tables exist.
- The final customer mart is available for query.

## Inspect Lineage And Traces

Open Marquez and Jaeger using the service URLs provided by your Platform Engineer.

Pass criteria:

- Marquez shows Customer 360 jobs and datasets.
- Jaeger shows traces for the Customer 360 execution path.

## Troubleshooting

If validation fails:

- Check the product run status in Dagster.
- Check whether compiled artifacts match the platform manifest.
- Check storage outputs before lineage and trace checks.
- Ask the Platform Engineer to confirm platform service health if multiple products fail the same way.
````

- [ ] **Step 3: Bridge legacy first data product page**

Replace `docs/get-started/first-data-product.md` with:

```markdown
# Build Your First Data Product

The current Data Engineer guide lives at [Build Your First Data Product](../data-engineers/first-data-product.md).

Start there if you build product configuration, dbt models, contracts, and validation checks on top of an existing Floe platform.
```

- [ ] **Step 4: Run docs sync and expect missing contributor/deployment files**

Run:

```bash
cd docs-site
npm run sync
```

Expected: manifest errors remain only for files created in later tasks if those files do not exist yet.

## Task 6: Move DevPod + Hetzner To Floe Contributor Documentation

**Files:**
- Move: `docs/operations/devpod-hetzner.md` to `docs/contributing/devpod-hetzner.md`
- Modify: `docs/contributing/index.md`
- Modify: `docs/demo/index.md`
- Modify: `docs/demo/customer-360.md`
- Modify: `docs/demo/customer-360-validation.md`
- Modify: `Makefile`

- [ ] **Step 1: Move the DevPod guide**

Run:

```bash
git mv docs/operations/devpod-hetzner.md docs/contributing/devpod-hetzner.md
```

- [ ] **Step 2: Reframe the moved guide**

Replace the opening of `docs/contributing/devpod-hetzner.md` with:

```markdown
# DevPod + Hetzner Contributor Workspace

Use this guide when you contribute to Floe and need a remote workspace for heavyweight E2E, integration, demo, or release-validation runs.

This is not the primary Floe product deployment model. Platform Engineers deploy Floe to Kubernetes using manifests, Helm, and their chosen cluster provider.

## Prerequisites

- DevPod CLI installed locally.
- Hetzner provider configured with `make devpod-setup`.
- A reachable DevPod workspace from `make devpod-up`.
- `kubectl` installed locally.
```

Keep the existing lifecycle commands, port-forward ownership, troubleshooting, and cleanup sections after the new opening.

- [ ] **Step 3: Update contributor index**

Add this section to `docs/contributing/index.md`:

```markdown
## Contributor Workflows

- [DevPod + Hetzner contributor workspace](devpod-hetzner.md) for remote heavyweight validation.
- [Contributor testing](testing.md) for unit, integration, E2E, docs, and release-validation checks.
- [Documentation standards](documentation-standards.md) for keeping docs aligned with behavior.

Contributor workflows can use repo-local `make` targets and DevPod. Platform Engineer and Data Engineer docs should describe product workflows that do not require contributor infrastructure.
```

- [ ] **Step 4: Remove product-requirement wording from demo docs**

In `docs/demo/index.md`, replace any sentence that says the demo starts against the configured DevPod workspace with:

```markdown
The Customer 360 demo validates Floe's alpha platform and data product path. Platform Engineers can run it on a deployed Floe platform; Floe Contributors can use the DevPod + Hetzner workspace when they need the remote release-validation lane.
```

In `docs/demo/customer-360.md`, replace the prerequisites section with:

```markdown
## Prerequisites

- A Floe platform is deployed and reachable.
- The Customer 360 data product has been compiled or is available in the demo project.
- You can access Dagster, object storage, Marquez, Jaeger, Polaris, and the semantic/query layer through your platform access method.

Floe contributors can use [DevPod + Hetzner](../contributing/devpod-hetzner.md) when they need the remote release-validation lane.
```

In `docs/demo/customer-360-validation.md`, replace the related guide list with:

```markdown
## Related Guides

- [Customer 360 Golden Demo](customer-360.md)
- [Validate your platform](../platform-engineers/validate-platform.md)
- [Validate your data product](../data-engineers/validate-data-product.md)
- [DevPod + Hetzner contributor workspace](../contributing/devpod-hetzner.md)
```

- [ ] **Step 5: Reframe Makefile help text**

Modify the help text in `Makefile`:

```make
	@echo "Contributor Remote Validation (DevPod + Hetzner):"
	@echo "  make devpod-setup    One-time Hetzner provider setup from .env"
	@echo "  make devpod-test     Run contributor E2E validation on DevPod"
	@echo "  make devpod-delete   Delete DevPod workspace (stops billing)"
	@echo "  make devpod-status   Show workspace status, tunnels, and cluster health"
	@echo "  make devpod-up       Create/start contributor DevPod workspace"
```

Update target descriptions:

```make
devpod-up: devpod-check ## Create/start contributor DevPod workspace
devpod-test: devpod-check ## Run contributor E2E validation on DevPod
```

- [ ] **Step 6: Run source checker**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: Hetzner errors are gone. Deployment and testing errors remain until later tasks.

## Task 7: Correct Deployment Capability Truth

**Files:**
- Create: `docs/architecture/capability-status.md`
- Modify: `docs/guides/deployment/index.md`
- Modify: `docs/guides/deployment/local-development.md`
- Modify: `docs/guides/deployment/kubernetes-helm.md`
- Modify: `docs/guides/deployment/data-mesh.md`

- [ ] **Step 1: Create capability status reference**

Create `docs/architecture/capability-status.md`:

```markdown
# Capability Status

Floe docs use capability labels so readers can distinguish alpha-supported workflows from architecture direction.

| Status | Meaning |
| --- | --- |
| Alpha-supported | Implemented, documented, and validated in the release lane |
| Implemented primitive | Code, schema, or contract exists, but no full user workflow is promised |
| Example | Provider-specific illustration, not a requirement |
| Planned | Architecture direction that is not yet a supported workflow |

## Alpha-Supported

- Single-platform Kubernetes deployment with the `floe-platform` Helm chart.
- Customer 360 demo validation path.
- Manifest-driven platform and data product configuration for the documented alpha path.
- OpenLineage and OpenTelemetry evidence in the Customer 360 validation path.

## Implemented Primitives

- Data Mesh schema and contract primitives.
- Manifest inheritance fields and validation.
- Namespace strategies for centralized and data mesh lineage naming.

## Planned Or Not Yet Alpha-Supported

- Multi-cluster Data Mesh deployment operations.
- A dedicated `floe-domain` Helm chart.
- Product registration commands such as `floe product register`.
- Provider-specific managed Kubernetes guides until each path is validated.
```

- [ ] **Step 2: Rewrite deployment overview**

Replace `docs/guides/deployment/index.md` with:

```markdown
# Deployment Guides

Floe's product deployment model is bring any conformant Kubernetes cluster. Platform Engineers deploy Floe with manifests, Helm, and their organization's Kubernetes access model.

## Current Deployment Paths

| Path | Status | Use Case |
| --- | --- | --- |
| Kubernetes with Helm | Alpha-supported | Deploy Floe platform services to a Kubernetes cluster |
| Local Kind evaluation | Alpha-supported for evaluation and contributor smoke checks | Try Floe on a disposable local cluster |
| GitOps with Flux | Implemented example | Deploy public OCI chart releases and compiled values through Flux |
| Data Mesh operations | Implemented primitives and planned operations | Understand the architecture without treating it as an alpha deployment path |

## Start Here

- [Platform Engineer first platform guide](../../platform-engineers/first-platform.md)
- [Kubernetes Helm](kubernetes-helm.md)
- [Local Kind evaluation](local-development.md)
- [GitOps with Flux](gitops-flux.md)
- [Data Mesh status](data-mesh.md)
- [Capability status](../../architecture/capability-status.md)
```

- [ ] **Step 3: Fix local development commands**

In `docs/guides/deployment/local-development.md`, replace `make kind-create` with `make kind-up` and `make kind-delete` with `make kind-down`.

Replace the opening with:

```markdown
# Local Kind Evaluation

Use local Kind when you want a disposable Kubernetes cluster for evaluation or contributor smoke checks. Docker Compose is not supported because Floe's platform behavior depends on Kubernetes service discovery, workload lifecycle, and Helm rendering.
```

- [ ] **Step 4: Correct Helm guide chart commands**

In `docs/guides/deployment/kubernetes-helm.md`, replace the old installation section with:

````markdown
## Quick Start

```bash
helm dependency update ./charts/floe-platform
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

For published chart validation, use the release artifact path documented in the release checklist for the version you are installing.
````

Remove examples that claim `https://charts.floe.dev` or `floe/floe` unless those artifacts exist in the current release process.

- [ ] **Step 5: Reframe Data Mesh page as current-state architecture**

Replace the opening and deployment command section of `docs/guides/deployment/data-mesh.md` with:

```markdown
# Data Mesh Deployment Status

Data Mesh is part of Floe's architecture direction. The current alpha includes schema, contract, inheritance, and lineage namespace primitives, but it does not yet provide a validated multi-cluster Data Mesh deployment path.

## Current Status

| Capability | Status |
| --- | --- |
| Enterprise and domain manifest fields | Implemented primitive |
| Manifest inheritance validation | Implemented primitive |
| Data contract schemas | Implemented primitive |
| Data Mesh lineage namespace strategy | Implemented primitive |
| Dedicated domain Helm chart | Planned |
| Multi-cluster deployment guide | Planned |
| Product registration workflow | Planned |

## Alpha Guidance

Use the single-platform Kubernetes deployment path for alpha. Treat the diagrams below as architecture context, not a supported deployment recipe.
```

Delete command examples that reference `charts/floe-domain`, `floe product init`, or `floe product register`.

- [ ] **Step 6: Run source checker**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: deployment-related source checker errors are gone. Testing-related `.claude` link errors may remain until Task 8.

## Task 8: Split Testing Docs By Persona

**Files:**
- Create: `docs/contributing/testing.md`
- Modify: `docs/guides/testing/index.md`
- Modify: `docs/guides/testing/code-quality.md`
- Modify: `docs/guides/testing/unit-testing.md`
- Modify: `docs/guides/testing/integration-testing.md`
- Modify: `docs/guides/testing/e2e-testing.md`
- Modify: `docs/guides/workflow-quickref.md`

- [ ] **Step 1: Create contributor testing guide**

Create `docs/contributing/testing.md`:

````markdown
# Contributor Testing

This guide is for Floe Contributors changing the Floe repository.

## Primary Commands

```bash
make test-unit
make test
make docs-validate
```

## Test Boundaries

| Tier | Purpose | Typical Command |
| --- | --- | --- |
| Unit | Fast package and function tests | `make test-unit` |
| Integration | Kubernetes-native service integration | `make test-integration` |
| E2E | Full platform workflows | `make demo-customer-360-validate` after setup |
| Docs | Starlight sync, build, and content gates | `make docs-validate` |

## Remote Validation

Use [DevPod + Hetzner](devpod-hetzner.md) when the full validation lane does not fit on a local machine.
````

- [ ] **Step 2: Convert public testing guide to persona router**

Replace `docs/guides/testing/index.md` with:

```markdown
# Testing And Validation

Choose the validation guide that matches your role.

| Persona | Guide | Purpose |
| --- | --- | --- |
| Platform Engineer | [Validate your platform](../../platform-engineers/validate-platform.md) | Prove Floe services are healthy and reachable |
| Data Engineer | [Validate your data product](../../data-engineers/validate-data-product.md) | Prove product outputs, lineage, traces, and business metrics |
| Floe Contributor | [Contributor testing](../../contributing/testing.md) | Run repository unit, integration, E2E, docs, and release checks |

Contributor-only test strategy pages remain available for maintainers, but Platform Engineers and Data Engineers should start from the validation guides above.
```

- [ ] **Step 3: Remove internal `.claude` links from published guide pages**

Run:

```bash
rg -n "\.claude/" docs/guides docs/platform-engineers docs/data-engineers docs/get-started docs/demo docs/contributing
```

Apply these exact rewrites:

- In `docs/guides/testing/index.md`, replace the `.claude/rules/testing-standards.md` link with `../../contributing/testing.md`.
- In `docs/guides/testing/code-quality.md`, replace the `.claude/rules/python-standards.md` link with `../../contributing/documentation-standards.md`.
- In `docs/guides/workflow-quickref.md`, replace the `.claude/settings.json`, `.claude/agents/*.md`, and `.claude/skills/*/SKILL.md` references with a short note: `Contributor agent configuration is internal to repository development and is not part of the Floe product interface.`

Expected after edits:

```bash
rg -n "\.claude/" docs/guides docs/platform-engineers docs/data-engineers docs/get-started docs/demo docs/contributing
```

No output.

- [ ] **Step 4: Run source checker**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: PASS.

- [ ] **Step 5: Commit persona navigation and docs content**

```bash
git add docs-site/docs-manifest.json docs/index.md docs/start-here/index.md docs/platform-engineers docs/data-engineers docs/get-started docs/contributing docs/demo docs/guides/deployment docs/guides/testing docs/architecture/capability-status.md Makefile
git commit -m "docs: align onboarding with Floe personas"
```

## Task 9: Full Docs Validation And Final Cleanup

**Files:**
- Modify only files needed to resolve validation failures found by this task.

- [ ] **Step 1: Run full docs validation**

Run:

```bash
make docs-validate
```

Expected: PASS. This runs `npm run validate` inside `docs-site`, including script tests, source checks, Starlight build, and built-doc link checks.

- [ ] **Step 2: Check generated Starlight content manually for duplicated H1s**

Run:

```bash
rg -n "^# " docs-site/src/content/docs
```

Expected: no source-title H1 appears as the first body heading immediately after Starlight frontmatter. Later deliberate H1s can be reviewed case by case; convert them to `##` if they are normal section headings.

- [ ] **Step 3: Check persona and provider drift**

Run:

```bash
rg -n "Hetzner|DevPod" docs/platform-engineers docs/data-engineers docs/get-started docs/guides docs/demo
```

Expected: no result saying Hetzner or DevPod is required for product deployment. Links that explicitly say "Floe contributors can use DevPod + Hetzner for release validation" are acceptable only in demo-related context.

- [ ] **Step 4: Check unsupported deployment references**

Run:

```bash
rg -n "charts/floe-domain|floe product register|floe product init|make kind-create|make kind-delete|charts.floe.dev|helm install floe floe/floe" docs/guides/deployment docs/platform-engineers docs/data-engineers docs/get-started docs/demo
```

Expected: no unsupported command appears in product deployment guidance. If a planned capability page mentions a future command, it must be labeled `Planned` and must not be presented as executable alpha guidance.

- [ ] **Step 5: Run git diff checks**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. `git status --short` only shows intentional modified files before the final commit.

- [ ] **Step 6: Commit validation fixes**

If Step 1 through Step 5 required any edits:

```bash
git add docs docs-site Makefile
git commit -m "docs: validate persona onboarding reset"
```

If no edits were required, do not create an empty commit.

## Self-Review Checklist

- Spec coverage: Tasks cover heading duplication, persona IA, provider-neutral Kubernetes onboarding, DevPod contributor scoping, Data Mesh truthfulness, testing split, and quality gates.
- Placeholder scan: no task relies on placeholder files, missing commands, or future-only implementations.
- Type and path consistency: new manifest paths match files created in the plan.
- Validation coverage: focused Node tests, source-doc checks, Starlight build, built-doc checks, and final `make docs-validate`.
