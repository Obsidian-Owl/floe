import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { syncDocs } from './sync-docs.mjs';

async function withDocsFixture(callback) {
  const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'floe-docs-sync-'));
  const repoRoot = path.join(tempRoot, 'repo');
  const docsSiteRoot = path.join(repoRoot, 'docs-site');

  await fs.mkdir(path.join(repoRoot, 'docs'), { recursive: true });
  await fs.mkdir(docsSiteRoot, { recursive: true });

  try {
    await callback({ repoRoot, docsSiteRoot });
  } finally {
    await fs.rm(tempRoot, { recursive: true, force: true });
  }
}

async function writeManifest(docsSiteRoot, items) {
  await fs.writeFile(
    path.join(docsSiteRoot, 'docs-manifest.json'),
    JSON.stringify({
      includePrefixes: [],
      excludePrefixes: [],
      sections: [
        {
          label: 'Test',
          items,
        },
      ],
    }),
  );
}

test('syncDocs writes explicit manifest pages at their configured slug routes', async () => {
  await withDocsFixture(async ({ repoRoot, docsSiteRoot }) => {
    await fs.writeFile(
      path.join(repoRoot, 'docs/source-page.md'),
      '# Source\n\nSee [linked](linked-page.md).\n',
    );
    await fs.writeFile(path.join(repoRoot, 'docs/linked-page.md'), '# Linked\n');
    await writeManifest(docsSiteRoot, [
      {
        title: 'Renamed Source',
        source: 'docs/source-page.md',
        slug: 'renamed/source',
      },
      {
        title: 'Renamed Linked',
        source: 'docs/linked-page.md',
        slug: 'renamed/linked',
      },
    ]);

    await syncDocs({ repoRoot, docsSiteRoot });

    const generatedSource = await fs.readFile(
      path.join(docsSiteRoot, 'src/content/docs/renamed/source.md'),
      'utf8',
    );

    assert.match(generatedSource, /\[linked\]\(\/floe\/renamed\/linked\/\)/u);
    await assert.rejects(
      fs.access(path.join(docsSiteRoot, 'src/content/docs/source-page.md')),
      /ENOENT/u,
    );
  });
});

test('syncDocs rejects non-Markdown manifest sources before generating nav targets', async () => {
  await withDocsFixture(async ({ repoRoot, docsSiteRoot }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/downloads'), { recursive: true });
    await fs.writeFile(path.join(repoRoot, 'docs/downloads/readme.txt'), 'Not Markdown.\n');
    await writeManifest(docsSiteRoot, [
      {
        title: 'Plain Text',
        source: 'docs/downloads/readme.txt',
        slug: 'downloads/readme',
      },
    ]);

    await assert.rejects(
      syncDocs({ repoRoot, docsSiteRoot }),
      /Manifest source must be Markdown: docs\/downloads\/readme\.txt/u,
    );
  });
});

test('syncDocs rejects duplicate manifest sources before route generation', async () => {
  await withDocsFixture(async ({ repoRoot, docsSiteRoot }) => {
    await fs.writeFile(path.join(repoRoot, 'docs/source-page.md'), '# Source\n');
    await writeManifest(docsSiteRoot, [
      {
        title: 'Primary',
        source: 'docs/source-page.md',
        slug: 'primary',
      },
      {
        title: 'Duplicate',
        source: 'docs/source-page.md',
        slug: 'duplicate',
      },
    ]);

    await assert.rejects(
      syncDocs({ repoRoot, docsSiteRoot }),
      /Duplicate manifest source: docs\/source-page\.md/u,
    );
  });
});

test('syncDocs rejects missing Markdown docs link targets before route generation', async () => {
  await withDocsFixture(async ({ repoRoot, docsSiteRoot }) => {
    await fs.writeFile(
      path.join(repoRoot, 'docs/source-page.md'),
      '# Source\n\nSee [missing](missing-page.md).\n',
    );
    await writeManifest(docsSiteRoot, [
      {
        title: 'Source',
        source: 'docs/source-page.md',
        slug: 'source',
      },
    ]);

    await assert.rejects(
      syncDocs({ repoRoot, docsSiteRoot }),
      /Broken docs link in docs\/source-page\.md: missing-page\.md -> docs\/missing-page\.md/u,
    );
  });
});
