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
  return /\b(not supported|unsupported|not alpha-supported|not implemented|planned|historical|deprecated|rejected|was rejected|alternative|not a current|do not run|no Docker Compose|creates testing parity issues|parity issues|failure mode)\b/iu.test(
    line,
  );
}

function collectLineLevelErrors(line) {
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

  for (const item of manifestItems(manifest)) {
    if (!isIncludedByPrefix(item.source, excludePrefixes)) {
      sources.add(item.source);
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
    for (const rule of disallowedSnippets) {
      if (rule.pattern.test(markdown)) {
        errors.push(`${source}: ${rule.message}`);
      }
    }
    for (const line of markdown.split(/\r?\n/u)) {
      for (const error of collectLineLevelErrors(line)) {
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
