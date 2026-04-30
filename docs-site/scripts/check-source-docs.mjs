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
];

function hasNegativeOrPlannedContext(line) {
  return /\b(not supported|unsupported|not alpha-supported|not implemented|planned|historical|deprecated|rejected|was rejected|alternative|not a current|not the (?:current )?(?:production )?default|do not run|no Docker Compose|creates testing parity issues|parity issues|failure mode|stub|stubs|advanced proof)\b/iu.test(
    line,
  );
}

const productSurfaceSources = new Set([
  'README.md',
  'docs/index.md',
  'docs/architecture/opinionation-boundaries.md',
  'docs/architecture/capability-status.md',
  'docs/reference/plugin-catalog.md',
  'docs/guides/data-product-lifecycle.md',
]);

const productSurfacePrefixes = [
  'docs/start-here/',
  'docs/get-started/',
  'docs/architecture/interfaces/',
  'docs/architecture/plugin-system/',
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
  if (/\bS3\b.*\b(production|default|prod)\b|\b(production|default|prod)\b.*\bS3\b/u.test(line)) {
    errors.push('labels S3 as a current production default');
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
  if (/\bfloe\s+run\b/iu.test(line)) {
    errors.push("presents unsupported root command 'floe run' as current");
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
