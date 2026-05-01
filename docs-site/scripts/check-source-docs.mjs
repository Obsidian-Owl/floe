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
  { pattern: /charts\/floe-domain/u, message: 'references missing chart charts/floe-domain' },
  { pattern: /make\s+kind-create/u, message: 'references missing Makefile target make kind-create' },
  { pattern: /make\s+kind-delete/u, message: 'references missing Makefile target make kind-delete' },
  { pattern: /\.claude\//u, message: 'links internal .claude path' },
  { pattern: /\bfloe\s+schema\s+export\b/u, message: "references unsupported CLI command 'floe schema export'" },
  { pattern: /\bfloe-storage-minio\b/u, message: 'references non-existent package floe-storage-minio' },
  { pattern: /\bDBTTestsPlugin\b/u, message: 'references stale DBTTestsPlugin name' },
];

const negativeOrPlannedContextPatterns = [
  /\bnot supported\b/iu,
  /\bunsupported\b/iu,
  /\bnot alpha-supported\b/iu,
  /\bnot implemented\b/iu,
  /\bplanned\b/iu,
  /\bhistorical\b/iu,
  /\bdeprecated\b/iu,
  /\brejected\b/iu,
  /\bwas rejected\b/iu,
  /\balternative\b/iu,
  /\bnot a current\b/iu,
  /\bnot the (?:current )?(?:production )?default\b/iu,
  /\bdo not run\b/iu,
  /\bno Docker Compose\b/iu,
  /\bcreates testing parity issues\b/iu,
  /\bparity issues\b/iu,
  /\bfailure mode\b/iu,
  /\bstubs?\b/iu,
  /\badvanced proof after\b/iu,
];

function hasNegativeOrPlannedContext(line) {
  // Negative-context gating exempts planned, rejected, or explicitly non-current
  // references from product-surface checks while keeping current-path claims strict.
  return negativeOrPlannedContextPatterns.some((pattern) => pattern.test(line));
}

const productSurfaceSources = new Set([
  'README.md',
  'docs/index.md',
  'docs/architecture/ARCHITECTURE-SUMMARY.md',
  'docs/architecture/DBT-ARCHITECTURE-CLARIFICATION.md',
  'docs/architecture/adr/0007-openlineage-from-start.md',
  'docs/architecture/adr/0010-target-agnostic-compute.md',
  'docs/architecture/adr/0016-platform-enforcement-architecture.md',
  'docs/architecture/adr/0018-opinionation-boundaries.md',
  'docs/architecture/adr/0020-ingestion-plugins.md',
  'docs/architecture/adr/0032-cube-compute-integration.md',
  'docs/architecture/adr/0035-observability-plugin-interface.md',
  'docs/architecture/adr/0036-storage-plugin-interface.md',
  'docs/architecture/adr/0047-cli-architecture.md',
  'docs/architecture/opinionation-boundaries.md',
  'docs/architecture/capability-status.md',
  'docs/architecture/platform-services.md',
  'docs/architecture/storage-integration.md',
  'docs/reference/plugin-catalog.md',
  'docs/guides/data-product-lifecycle.md',
]);

const productSurfacePrefixes = [
  'docs/start-here/',
  'docs/get-started/',
  'docs/architecture/interfaces/',
  'docs/architecture/plugin-system/',
  'docs/contracts/',
  'docs/platform-engineers/',
  'docs/data-engineers/',
  'docs/guides/deployment/',
];

function isCurrentProductSurfaceSource(source) {
  return productSurfaceSources.has(source) || productSurfacePrefixes.some((prefix) => source.startsWith(prefix));
}

function collectGeneralLineLevelErrors(line) {
  const errors = [];
  if (/without rewrites/iu.test(line)) {
    errors.push("uses uncaveated Data Mesh migration language 'without rewrites'");
  }
  if (/Data Mesh seamlessly/iu.test(line)) {
    errors.push("uses uncaveated Data Mesh migration language 'Data Mesh seamlessly'");
  }
  if (/Docker Compose setup/iu.test(line) && !hasNegativeOrPlannedContext(line)) {
    errors.push('presents Docker Compose setup as a product path');
  }
  if (/\bdocker\s+compose\s+up\b/iu.test(line) && !hasNegativeOrPlannedContext(line)) {
    errors.push("presents 'docker compose up' as a product path");
  }
  if (
    (/\bDocker Compose\b.*\b(development|evaluation)\b/iu.test(line) ||
      /\b(development|evaluation)\b.*\bDocker Compose\b/iu.test(line)) &&
    !hasNegativeOrPlannedContext(line)
  ) {
    errors.push('presents Docker Compose as a development or evaluation product path');
  }
  if (/\bfloe\s+dev\b/iu.test(line) && !hasNegativeOrPlannedContext(line)) {
    errors.push("presents unsupported CLI command 'floe dev' as a product path");
  }
  return errors;
}

function collectProductSurfaceLineLevelErrors(line) {
  const errors = [];
  if (hasNegativeOrPlannedContext(line)) {
    return errors;
  }
  if (/\bDatadog\b.*\b(default|production|prod)\b|\b(default|production|prod)\b.*\bDatadog\b/iu.test(line)) {
    errors.push('labels Datadog as a current default integration');
  }
  if (/\bAtlan\b.*\b(default|production|prod)\b|\b(default|production|prod)\b.*\bAtlan\b/iu.test(line)) {
    errors.push('labels Atlan as a current default integration');
  }
  if (/\bS3\b.*\b(production|default|prod)\b|\b(production|default|prod)\b.*\bS3\b/iu.test(line)) {
    errors.push('labels S3 as a current production default');
  }
  if (/\bDefault plugins?\b/iu.test(line)) {
    errors.push('uses default plugin bundle wording');
  }
  if (/\bMinIO\b.*\bdefault\b|\bdefault\b.*\bMinIO\b/iu.test(line)) {
    errors.push('labels MinIO as a current default storage integration');
  }
  if (/\bTotal Plugin Types(?:\*\*)?\s*:?\s*12\b/iu.test(line)) {
    errors.push('references stale plugin category count 12');
  }
  if (/\bAlpha-Supported Default\b/u.test(line)) {
    errors.push('uses alpha-supported default provider wording');
  }
  if (/\balpha default\b/iu.test(line)) {
    errors.push('uses alpha default provider wording');
  }
  if (/\bCreate default plugins\b.*\b(DuckDB|Dagster|Polaris|Cube|dlt)\b/iu.test(line)) {
    errors.push('presents bundled provider plugins as current defaults');
  }
  if (/\bsystem defaults\b.*\b(DuckDB|Dagster|Polaris|Cube|dlt)\b/iu.test(line)) {
    errors.push('presents implicit platform system defaults as a current user path');
  }
  if (/\b(DuckDB|Dagster|Polaris|Cube|dlt|Jaeger|Marquez|MinIO)\s*\(\s*default\s*\)/iu.test(line)) {
    errors.push('labels a plugin reference implementation as a current default selection');
  }
  if (/\b(DuckDB|Dagster|Polaris|Cube|dlt|Jaeger|Marquez|MinIO)\b.*\bPlugin\b.*\(\s*default\s*\)/iu.test(line)) {
    errors.push('labels a plugin reference implementation as a current default selection');
  }
  if (/\b(DuckDB|Dagster|Polaris|Cube|dlt|Jaeger|Marquez|MinIO)[A-Za-z]*Plugin\b.*\(\s*default\s*\)/iu.test(line)) {
    errors.push('labels a plugin reference implementation as a current default selection');
  }
  if (/\bDefault:\s*\*\*(DuckDB|Dagster|Polaris|Cube|dlt)\*\*/iu.test(line)) {
    errors.push('labels a plugin reference implementation as a current default selection');
  }
  if (/\b(dagster|duckdb|polaris|cube|dlt)\b.*\[\s*default\s*\]/iu.test(line)) {
    errors.push('labels a plugin reference implementation as a current default selection');
  }
  if (/\bDuckDB-first\b.*\bdefault\b|\bdefault\b.*\bDuckDB-first\b/iu.test(line)) {
    errors.push('labels DuckDB-first behavior as a current default');
  }
  if (/\bdefault open-source stack\b/iu.test(line)) {
    errors.push('labels an open-source stack as a current default');
  }
  if (/\bdefault if omitted\b/iu.test(line)) {
    errors.push('presents implicit defaults instead of manifest-approved fallbacks');
  }
  if (/DON'T:\s*Allow Data Engineers to select compute/iu.test(line)) {
    errors.push('forbids approved per-transform compute selection');
  }
  if (/Data Engineers inherit compute\s+-\s+they do not select it/iu.test(line)) {
    errors.push('says Data Engineers cannot select approved compute');
  }
  if (/\bfloe\s+compile\b/iu.test(line)) {
    errors.push("presents unsupported root command 'floe compile' as current");
  }
  if (/\bfloe\s+init\b/iu.test(line)) {
    errors.push("presents unsupported root command 'floe init' as current");
  }
  if (/\bfloe\s+run\b/iu.test(line)) {
    errors.push("presents unsupported root command 'floe run' as current");
  }
  if (/\bfloe\s+test\b/iu.test(line)) {
    errors.push("presents unsupported root command 'floe test' as current");
  }
  if (/\bfloe\s+validate\b/iu.test(line)) {
    errors.push("presents unsupported root command 'floe validate' as current");
  }
  if (/\bfloe\s+product\s+deploy\b/iu.test(line)) {
    errors.push("presents unsupported CLI command 'floe product deploy' as current");
  }
  return errors;
}

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

function manifestItems(manifest) {
  return (manifest.sections ?? []).flatMap((section) => section.items ?? []);
}

function stripMarkdownLinkDestinations(markdown) {
  return markdown.replace(/\]\([^)\n]*\)/gu, ']()');
}

async function publishedMarkdownSources(repoRoot, manifestPath) {
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  const includePrefixes = manifest.includePrefixes ?? [];
  const excludePrefixes = manifest.excludePrefixes ?? [];
  const docsRoot = path.join(repoRoot, 'docs');
  const sources = new Set();
  const readmePath = path.join(repoRoot, 'README.md');

  for (const item of manifestItems(manifest)) {
    if (!isIncludedByPrefix(item.source, excludePrefixes)) {
      sources.add(item.source);
    }
  }

  try {
    const readmeStats = await fs.stat(readmePath);
    if (readmeStats.isFile() && !isIncludedByPrefix('README.md', excludePrefixes)) {
      sources.add('README.md');
    }
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error;
    }
  }

  const markdownFiles = await walkMarkdownFiles(docsRoot);
  for (const file of markdownFiles) {
    const source = path.posix.join('docs', toPosixPath(path.relative(docsRoot, file)));
    if (isIncludedByPrefix(source, includePrefixes) && !isIncludedByPrefix(source, excludePrefixes)) {
      sources.add(source);
    }
  }

  return [...sources].sort((left, right) => left.localeCompare(right));
}

export async function collectSourceDocsErrors({
  repoRoot = defaultRepoRoot,
  manifestPath = defaultManifestPath,
} = {}) {
  const sources = await publishedMarkdownSources(repoRoot, manifestPath);
  const errors = [];
  for (const source of sources) {
    const markdown = await fs.readFile(path.join(repoRoot, source), 'utf8');
    const proseMarkdown = stripMarkdownLinkDestinations(markdown);
    if (/\bhetzner\b/iu.test(proseMarkdown) && !allowedHetznerSources.has(source)) {
      errors.push(`${source}: references Hetzner outside Floe Contributor docs`);
    }
    if (source === 'docs/data-engineers/first-data-product.md' && !/\bhello-orders\b/iu.test(markdown)) {
      errors.push(`${source}: first data product guide must teach hello-orders before Customer 360`);
    }
    for (const rule of disallowedSnippets) {
      if (rule.pattern.test(markdown)) {
        errors.push(`${source}: ${rule.message}`);
      }
    }
    for (const line of markdown.split(/\r?\n/u)) {
      const lineLevelErrors = collectGeneralLineLevelErrors(line);
      if (isCurrentProductSurfaceSource(source)) {
        lineLevelErrors.push(...collectProductSurfaceLineLevelErrors(line));
      }
      for (const error of lineLevelErrors) {
        errors.push(`${source}: ${error}`);
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
