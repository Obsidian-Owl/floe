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
