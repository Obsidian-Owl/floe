import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { collectBuiltDocsErrors } from './check-built-docs.mjs';

async function withBuiltDocsFixture(callback) {
  const docsSiteRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'floe-built-docs-'));
  const distRoot = path.join(docsSiteRoot, 'dist');
  const manifestPath = path.join(docsSiteRoot, 'docs-manifest.json');

  await fs.mkdir(distRoot, { recursive: true });
  await fs.writeFile(
    manifestPath,
    JSON.stringify({
      excludePrefixes: ['docs/plans/'],
      sections: [],
    }),
  );

  try {
    await callback({ docsSiteRoot, distRoot, manifestPath });
  } finally {
    await fs.rm(docsSiteRoot, { recursive: true, force: true });
  }
}

test('checkBuiltDocs resolves relative hrefs before excluded-route detection', async () => {
  await withBuiltDocsFixture(async ({ docsSiteRoot, distRoot, manifestPath }) => {
    const htmlPath = path.join(distRoot, 'guides/testing/index.html');
    await fs.mkdir(path.dirname(htmlPath), { recursive: true });
    await fs.writeFile(htmlPath, '<a href="../../plans/">Internal plan</a>');

    const { errors } = await collectBuiltDocsErrors({
      docsSiteRoot,
      distRoot,
      manifestPath,
    });

    assert.deepEqual(errors, [
      'dist/guides/testing/index.html: contains site href to excluded docs content: ../../plans/',
    ]);
  });
});
