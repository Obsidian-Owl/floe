import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { collectSourceDocsErrors } from './check-source-docs.mjs';

async function withSourceDocsFixture(callback, manifestOverrides = {}) {
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
      ...manifestOverrides,
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

test('collectSourceDocsErrors checks manifest-section-only sources outside include prefixes', async () => {
  await withSourceDocsFixture(
    async ({ repoRoot, manifestPath }) => {
      await fs.mkdir(path.join(repoRoot, 'docs/personas'), { recursive: true });
      await fs.writeFile(
        path.join(repoRoot, 'docs/personas/kubernetes-platform.md'),
        '# Kubernetes Platform\n\nValidate on hetzner.\n',
      );

      const { checkedCount, errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

      assert.equal(checkedCount, 1);
      assert.deepEqual(errors, [
        'docs/personas/kubernetes-platform.md: references Hetzner outside Floe Contributor docs',
      ]);
    },
    {
      includePrefixes: ['docs/published/'],
      sections: [
        {
          title: 'Personas',
          items: [
            {
              title: 'Kubernetes Platform',
              source: 'docs/personas/kubernetes-platform.md',
              slug: 'personas/kubernetes-platform',
            },
          ],
        },
      ],
    },
  );
});

test('collectSourceDocsErrors skips excluded docs discovered through include prefixes', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/superpowers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/superpowers/internal.md'),
      '# Internal\n\nRequires Hetzner credentials.\n',
    );

    const { checkedCount, errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.equal(checkedCount, 0);
    assert.deepEqual(errors, []);
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

test('collectSourceDocsErrors allows links to contributor DevPod docs outside contributor docs', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/demo'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/demo/customer-360-validation.md'),
      '# Validation\n\nSee [DevPod contributor workspace](../contributing/devpod-hetzner.md).\n',
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

test('collectSourceDocsErrors rejects unsupported public CLI snippets', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/reference'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/reference/floe-yaml-schema.md'),
      '# Schema\n\nRun `floe schema export --format json`.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      "docs/reference/floe-yaml-schema.md: references unsupported CLI command 'floe schema export'",
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
