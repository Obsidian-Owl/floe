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

test('collectSourceDocsErrors rejects uncaveated Data Mesh migration claims', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/summary.md'),
      '# Architecture\n\nScale to Data Mesh seamlessly without rewrites.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      "docs/architecture/summary.md: uses uncaveated Data Mesh migration language 'without rewrites'",
      "docs/architecture/summary.md: uses uncaveated Data Mesh migration language 'Data Mesh seamlessly'",
    ]);
  });
});

test('collectSourceDocsErrors rejects Docker Compose and floe dev product paths', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/guides/deployment'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/guides/deployment/local.md'),
      '# Local\n\nUse Docker Compose setup for evaluation.\nRun `docker compose up`.\nRun `floe dev`.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/guides/deployment/local.md: presents Docker Compose setup as a product path',
      'docs/guides/deployment/local.md: presents Docker Compose as a development or evaluation product path',
      "docs/guides/deployment/local.md: presents 'docker compose up' as a product path",
      "docs/guides/deployment/local.md: presents unsupported CLI command 'floe dev' as a product path",
    ]);
  });
});

test('collectSourceDocsErrors allows negative or planned Docker Compose and floe dev context', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/guides/deployment'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/guides/deployment/local-development.md'),
      '# Local\n\nDocker Compose is not supported for Floe product evaluation.\n`floe dev` is planned and not implemented.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, []);
  });
});

test('collectSourceDocsErrors rejects unsupported current default integrations', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/opinionation-boundaries.md'),
      [
        '# Opinionation Boundaries',
        '',
        '| Component | Default | Alternatives |',
        '| --- | --- | --- |',
        '| Telemetry Backend | Jaeger (local), Datadog (production) | Grafana Cloud |',
        '| Lineage Backend | Marquez (local), Atlan (production) | OpenMetadata |',
        '| Storage | MinIO (local), S3 (production) | GCS |',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/architecture/opinionation-boundaries.md: labels Datadog as a current default integration',
      'docs/architecture/opinionation-boundaries.md: labels Atlan as a current default integration',
      'docs/architecture/opinionation-boundaries.md: labels S3 as a current production default',
    ]);
  });
});

test('collectSourceDocsErrors rejects prod shorthand in architecture plugin docs', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture/plugin-system'), { recursive: true });
    await fs.mkdir(path.join(repoRoot, 'docs/architecture/interfaces'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/plugin-system/index.md'),
      [
        '# Plugin Architecture',
        '',
        '| Plugin Type | Default |',
        '| --- | --- |',
        '| Storage | S3 (prod) |',
        '| TelemetryBackend | Datadog (prod) |',
        '| LineageBackend | Atlan (prod) |',
        '',
      ].join('\n'),
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/interfaces/storage-plugin.md'),
      '# Storage Plugin\n\n`S3Plugin` is AWS S3 storage (production default).\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/architecture/interfaces/storage-plugin.md: labels S3 as a current production default',
      'docs/architecture/plugin-system/index.md: labels S3 as a current production default',
      'docs/architecture/plugin-system/index.md: labels Datadog as a current default integration',
      'docs/architecture/plugin-system/index.md: labels Atlan as a current default integration',
    ]);
  });
});

test('collectSourceDocsErrors rejects stale plugin default wording in published docs', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture/adr'), { recursive: true });
    await fs.mkdir(path.join(repoRoot, 'docs/architecture/plugin-system'), { recursive: true });
    await fs.mkdir(path.join(repoRoot, 'docs/contracts'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/ARCHITECTURE-SUMMARY.md'),
      '# Architecture Summary\n\n3. Create default plugins (DuckDB, Dagster, Polaris, Cube, dlt)\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/DBT-ARCHITECTURE-CLARIFICATION.md'),
      [
        '# dbt Architecture Clarification',
        '',
        '- **Orchestrator**: Dagster (default), Airflow 3.x',
        '**Total Plugin Types**: 12',
        '',
      ].join('\n'),
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/adr/0020-ingestion-plugins.md'),
      '# ADR-0020\n\n### dlt Plugin (Default)\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/adr/0035-observability-plugin-interface.md'),
      '# ADR-0035\n\n- **Default plugins** - Jaeger and Marquez ship together.\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/adr/0036-storage-plugin-interface.md'),
      '# ADR-0036\n\n- **Default plugin** - `floe-storage-minio` ships with Floe.\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/adr/0032-cube-compute-integration.md'),
      [
        '# ADR-0032',
        '',
        '- **DuckDB-first**: Default compute engine should work with semantic layer',
        '- **DuckDB-first**: Works with default open-source stack',
        '',
      ].join('\n'),
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/opinionation-boundaries.md'),
      '# Opinionation Boundaries\n\n| Component | Alpha-Supported Default |\n',
    );
    await fs.mkdir(path.join(repoRoot, 'docs/architecture/interfaces'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/interfaces/telemetry-backend-plugin.md'),
      '# Telemetry\n\n| `JaegerTelemetryPlugin` | Local observability (default) |\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/interfaces/lineage-backend-plugin.md'),
      '# Lineage\n\n| `MarquezLineagePlugin` | Local lineage (default) |\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/interfaces/data-quality-plugin.md'),
      '# Quality\n\n| `DBTTestsPlugin` | Native dbt tests (default) |\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/storage-integration.md'),
      '# Storage\n\n| **MinIO** (default) | Local development |\n\n### MinIO (Default for Development)\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/plugin-system/configuration.md'),
      '# Plugin Configuration\n\n- dagster (1.0.0) [default]\n',
    );
    await fs.writeFile(
      path.join(repoRoot, 'docs/contracts/glossary.md'),
      [
        '# Glossary',
        '',
        'Uses only a `floe.yaml` file with system defaults (DuckDB, Dagster, Polaris, Cube, dlt).',
        'Where dbt transforms execute. Default: **DuckDB**.',
        'compute: duckdb # Analytics (or uses default if omitted)',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/architecture/adr/0020-ingestion-plugins.md: labels a plugin reference implementation as a current default selection',
      'docs/architecture/adr/0032-cube-compute-integration.md: labels DuckDB-first behavior as a current default',
      'docs/architecture/adr/0032-cube-compute-integration.md: labels DuckDB-first behavior as a current default',
      'docs/architecture/adr/0032-cube-compute-integration.md: labels an open-source stack as a current default',
      'docs/architecture/adr/0035-observability-plugin-interface.md: uses default plugin bundle wording',
      'docs/architecture/adr/0036-storage-plugin-interface.md: references non-existent package floe-storage-minio',
      'docs/architecture/adr/0036-storage-plugin-interface.md: uses default plugin bundle wording',
      'docs/architecture/adr/0036-storage-plugin-interface.md: labels MinIO as a current default storage integration',
      'docs/architecture/ARCHITECTURE-SUMMARY.md: uses default plugin bundle wording',
      'docs/architecture/ARCHITECTURE-SUMMARY.md: presents bundled provider plugins as current defaults',
      'docs/architecture/DBT-ARCHITECTURE-CLARIFICATION.md: labels a plugin reference implementation as a current default selection',
      'docs/architecture/DBT-ARCHITECTURE-CLARIFICATION.md: references stale plugin category count 12',
      'docs/architecture/interfaces/data-quality-plugin.md: references stale DBTTestsPlugin name',
      'docs/architecture/interfaces/lineage-backend-plugin.md: labels a plugin reference implementation as a current default selection',
      'docs/architecture/interfaces/telemetry-backend-plugin.md: labels a plugin reference implementation as a current default selection',
      'docs/architecture/opinionation-boundaries.md: uses alpha-supported default provider wording',
      'docs/architecture/plugin-system/configuration.md: labels a plugin reference implementation as a current default selection',
      'docs/architecture/storage-integration.md: labels MinIO as a current default storage integration',
      'docs/architecture/storage-integration.md: labels MinIO as a current default storage integration',
      'docs/contracts/glossary.md: presents implicit platform system defaults as a current user path',
      'docs/contracts/glossary.md: labels a plugin reference implementation as a current default selection',
      'docs/contracts/glossary.md: presents implicit defaults instead of manifest-approved fallbacks',
    ]);
  });
});

test('collectSourceDocsErrors checks README as public product surface', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.writeFile(
      path.join(repoRoot, 'README.md'),
      '# Floe\n\nDatadog is the production default telemetry backend.\nJaeger alpha default telemetry path.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'README.md: labels Datadog as a current default integration',
      'README.md: uses alpha default provider wording',
    ]);
  });
});

test('collectSourceDocsErrors does not let README inclusion override manifest exclusions', async () => {
  await withSourceDocsFixture(
    async ({ repoRoot, manifestPath }) => {
      await fs.writeFile(
        path.join(repoRoot, 'README.md'),
        '# Floe\n\nDatadog is the production default telemetry backend.\n',
      );

      const { checkedCount, errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

      assert.equal(checkedCount, 0);
      assert.deepEqual(errors, []);
    },
    {
      excludePrefixes: ['README.md'],
    },
  );
});

test('collectSourceDocsErrors allows explicitly negated product-surface default claims', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/opinionation-boundaries.md'),
      [
        '# Opinionation Boundaries',
        '',
        'Datadog is not the production default telemetry backend.',
        'Atlan is not the current default lineage backend.',
        'S3 is not the production default storage backend.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, []);
  });
});

test('collectSourceDocsErrors rejects wrong compute ownership guidance', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/opinionation-boundaries.md'),
      [
        '# Opinionation Boundaries',
        '',
        "### DON'T: Allow Data Engineers to select compute",
        '',
        'Data engineers inherit compute - they do not select it.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/architecture/opinionation-boundaries.md: forbids approved per-transform compute selection',
      'docs/architecture/opinionation-boundaries.md: says Data Engineers cannot select approved compute',
    ]);
  });
});

test('collectSourceDocsErrors rejects unsupported root data-team lifecycle commands', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/data-engineers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/data-engineers/first-data-product.md'),
      [
        '# Build Your First Data Product',
        '',
        'Run `floe compile`.',
        'Run `floe init --platform=v1.0.0`.',
        'Run `floe run`.',
        'Run `floe test`.',
        'Run `floe product deploy`.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/data-engineers/first-data-product.md: first data product guide must teach hello-orders before Customer 360',
      "docs/data-engineers/first-data-product.md: presents unsupported root command 'floe compile' as current",
      "docs/data-engineers/first-data-product.md: presents unsupported root command 'floe init' as current",
      "docs/data-engineers/first-data-product.md: presents unsupported root command 'floe run' as current",
      "docs/data-engineers/first-data-product.md: presents unsupported root command 'floe test' as current",
      "docs/data-engineers/first-data-product.md: presents unsupported CLI command 'floe product deploy' as current",
    ]);
  });
});

test('collectSourceDocsErrors allows planned root commands and Customer 360 as advanced proof', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/data-engineers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/data-engineers/first-data-product.md'),
      [
        '# Build Your First Data Product',
        '',
        'Build `hello-orders` first.',
        '`floe compile` is planned and not implemented as the current alpha product command.',
        'Customer 360 is the advanced proof after the hello-orders path.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, []);
  });
});

test('collectSourceDocsErrors rejects broad advanced proof wording as negative context', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/data-engineers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/data-engineers/first-data-product.md'),
      [
        '# Build Your First Data Product',
        '',
        'Build `hello-orders` first.',
        'This provides advanced proof-of-concept coverage for `floe compile`.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      "docs/data-engineers/first-data-product.md: presents unsupported root command 'floe compile' as current",
    ]);
  });
});
