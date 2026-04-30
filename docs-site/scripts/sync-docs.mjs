import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { withDocsBase } from '../site-config.mjs';

const defaultDocsSiteRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const defaultRepoRoot = path.resolve(defaultDocsSiteRoot, '..');
const repositoryBlobBaseUrl = 'https://github.com/Obsidian-Owl/floe/blob/main';
const unsupportedFenceLanguages = new Set(['gotemplate', 'promql', 'tpl']);

function toPosixPath(value) {
  return value.split(path.sep).join(path.posix.sep);
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

function isIncludedByPrefix(source, prefixes) {
  return prefixes.some((prefix) => source === prefix || source.startsWith(prefix));
}

function titleFromMarkdown(markdown, relativePath) {
  const heading = markdown.match(/^#\s+(.+)$/m);
  if (heading) {
    return heading[1].replace(/`/g, '').trim();
  }

  return path.basename(relativePath, '.md').replace(/[-_]/g, ' ');
}

function withStarlightFrontmatter(markdown, relativePath) {
  const title = JSON.stringify(titleFromMarkdown(markdown, relativePath));
  const frontmatter = markdown.match(/^---\n([\s\S]*?)\n---\n?/);

  if (!frontmatter) {
    return `---\ntitle: ${title}\n---\n\n${markdown}`;
  }

  if (/^title:/m.test(frontmatter[1])) {
    return markdown;
  }

  return markdown.replace(/^---\n/, `---\ntitle: ${title}\n`);
}

function routeForDocsSource(source) {
  const withoutDocsPrefix = source.slice('docs/'.length);
  const withoutExtension = withoutDocsPrefix.replace(/\.md$/u, '');
  if (withoutExtension === 'index') {
    return '/';
  }
  if (withoutExtension.endsWith('/index')) {
    return `/${withoutExtension.slice(0, -'/index'.length)}/`;
  }
  return `/${withoutExtension}/`;
}

function routeForManifestSlug(slug) {
  return slug === 'index' ? '/' : `/${slug}/`;
}

function targetPathForManifestItem(item) {
  if (item.slug === 'index') {
    return 'index.md';
  }

  if (item.source.endsWith('/index.md')) {
    return `${item.slug}/index.md`;
  }

  return `${item.slug}.md`;
}

function manifestItems(manifest) {
  return manifest.sections.flatMap((section) => section.items);
}

function repositoryUrlForPath(repositoryPath, query, anchor) {
  return `${repositoryBlobBaseUrl}/${repositoryPath}${query ? `?${query}` : ''}${
    anchor ? `#${anchor}` : ''
  }`;
}

function repositoryPathForResolvedSource(resolvedSource) {
  return resolvedSource.replace(/^(\.\.\/)+/u, '');
}

function docsSourceCandidates(sourceParent, targetPath) {
  const candidateTargets = [];
  const extension = path.posix.extname(targetPath);

  if (targetPath.endsWith('.md')) {
    candidateTargets.push(targetPath);
  } else if (extension === '') {
    if (targetPath.endsWith('/')) {
      candidateTargets.push(`${targetPath}index.md`);
    } else {
      candidateTargets.push(`${targetPath}.md`, `${targetPath}/index.md`);
    }
  }

  return candidateTargets.map((candidate) =>
    candidate.startsWith('docs/')
      ? path.posix.normalize(candidate)
      : path.posix.normalize(path.posix.join(sourceParent, candidate)),
  );
}

function rewriteMarkdownLinks(markdown, source, publishedSourceRoutes, repoRoot) {
  const sourceParent = path.posix.dirname(source);
  return markdown.replace(
    /(?<!!)\[([^\]]+)\]\(([^)]+)\)/g,
    (fullMatch, label, rawTarget) => {
      const trimmedTarget = rawTarget.trim();
      if (
        trimmedTarget === '' ||
        trimmedTarget.startsWith('#') ||
        trimmedTarget.startsWith('/') ||
        /^[a-z][a-z0-9+.-]*:/iu.test(trimmedTarget)
      ) {
        return fullMatch;
      }

      const [pathAndQuery, anchor = ''] = trimmedTarget.split('#', 2);
      const [targetPath, query = ''] = pathAndQuery.split('?', 2);
      const candidates = docsSourceCandidates(sourceParent, targetPath);
      if (candidates.length === 0) {
        return fullMatch;
      }

      const resolvedSource =
        candidates.find((candidate) => existsSync(path.join(repoRoot, candidate))) ??
        candidates[0];
      if (!resolvedSource.startsWith('docs/')) {
        const repositoryPath = repositoryPathForResolvedSource(resolvedSource);
        const absoluteRepositoryPath = path.join(repoRoot, repositoryPath);
        if (repositoryPath.endsWith('.md') && existsSync(absoluteRepositoryPath)) {
          return `[${label}](${repositoryUrlForPath(repositoryPath, query, anchor)})`;
        }
        return fullMatch;
      }

      const publishedRoute = publishedSourceRoutes.get(resolvedSource);
      if (!publishedRoute) {
        const absoluteRepositoryPath = path.join(repoRoot, resolvedSource);
        if (existsSync(absoluteRepositoryPath)) {
          return `[${label}](${repositoryUrlForPath(resolvedSource, query, anchor)})`;
        }
        throw new Error(`Broken docs link in ${source}: ${targetPath} -> ${resolvedSource}`);
      }

      const route = withDocsBase(publishedRoute ?? routeForDocsSource(resolvedSource));
      const rewrittenTarget = `${route}${query ? `?${query}` : ''}${anchor ? `#${anchor}` : ''}`;
      return `[${label}](${rewrittenTarget})`;
    },
  );
}

function normalizeGeneratedMarkdown(markdown) {
  return markdown.replace(/^```([A-Za-z0-9_-]+)([^\n]*)$/gm, (line, language, suffix) => {
    if (!unsupportedFenceLanguages.has(language)) {
      return line;
    }
    return `\`\`\`text${suffix}`;
  });
}

async function publishedSourceEntries(manifest, sourceRoot) {
  const includePrefixes = manifest.includePrefixes ?? [];
  const excludePrefixes = manifest.excludePrefixes ?? [];
  const entriesBySource = new Map();

  for (const item of manifestItems(manifest)) {
    if (isIncludedByPrefix(item.source, excludePrefixes)) {
      continue;
    }
    entriesBySource.set(item.source, {
      source: item.source,
      route: routeForManifestSlug(item.slug),
      targetRelativePath: targetPathForManifestItem(item),
    });
  }

  const sourceFiles = await walkMarkdownFiles(sourceRoot);
  for (const sourceFile of sourceFiles) {
    const source = path.posix.join('docs', toPosixPath(path.relative(sourceRoot, sourceFile)));
    if (
      isIncludedByPrefix(source, includePrefixes) &&
      !isIncludedByPrefix(source, excludePrefixes) &&
      !entriesBySource.has(source)
    ) {
      entriesBySource.set(source, {
        source,
        route: routeForDocsSource(source),
        targetRelativePath: toPosixPath(path.relative(sourceRoot, sourceFile)),
      });
    }
  }

  return [...entriesBySource.values()].sort((left, right) =>
    left.source.localeCompare(right.source),
  );
}

export async function syncDocs({
  repoRoot = defaultRepoRoot,
  docsSiteRoot = defaultDocsSiteRoot,
} = {}) {
  const sourceRoot = path.join(repoRoot, 'docs');
  const targetRoot = path.join(docsSiteRoot, 'src', 'content', 'docs');
  const manifestPath = path.join(docsSiteRoot, 'docs-manifest.json');
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  const excludePrefixes = manifest.excludePrefixes ?? [];
  const manifestSources = new Set();
  for (const item of manifestItems(manifest)) {
    if (!item.source.endsWith('.md')) {
      throw new Error(`Manifest source must be Markdown: ${item.source}`);
    }
    if (isIncludedByPrefix(item.source, excludePrefixes)) {
      throw new Error(`Manifest source is excluded by docs manifest: ${item.source}`);
    }
    if (manifestSources.has(item.source)) {
      throw new Error(`Duplicate manifest source: ${item.source}`);
    }
    manifestSources.add(item.source);

    const sourcePath = path.join(repoRoot, item.source);
    try {
      await fs.access(sourcePath);
    } catch {
      throw new Error(`Manifest source not found: ${item.source}`);
    }
  }

  await fs.rm(targetRoot, { recursive: true, force: true });
  await fs.mkdir(targetRoot, { recursive: true });
  await fs.writeFile(path.join(targetRoot, '.gitignore'), '*\n!.gitignore\n');

  const entries = await publishedSourceEntries(manifest, sourceRoot);
  const publishedSourceRoutes = new Map(entries.map((entry) => [entry.source, entry.route]));
  for (const entry of entries) {
    const sourceFile = path.join(repoRoot, entry.source);
    const targetPath = path.join(targetRoot, entry.targetRelativePath);
    const markdown = await fs.readFile(sourceFile, 'utf8');

    await fs.mkdir(path.dirname(targetPath), { recursive: true });
    await fs.writeFile(
      targetPath,
      normalizeGeneratedMarkdown(
        withStarlightFrontmatter(
          rewriteMarkdownLinks(markdown, entry.source, publishedSourceRoutes, repoRoot),
          entry.targetRelativePath,
        ),
      ),
    );
  }

  console.log(`Synced ${entries.length} docs pages into Starlight content.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  syncDocs().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
