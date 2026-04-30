import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const docsSiteRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const repoRoot = path.resolve(docsSiteRoot, '..');
const sourceRoot = path.join(repoRoot, 'docs');
const targetRoot = path.join(docsSiteRoot, 'src', 'content', 'docs');
const manifestPath = path.join(docsSiteRoot, 'docs-manifest.json');
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

function uniqueSorted(values) {
  return [...new Set(values)].sort();
}

function isIncludedByPrefix(source, prefixes) {
  return prefixes.some((prefix) => source === prefix || source.startsWith(prefix));
}

async function publishedSources(manifest) {
  const manifestSources = manifest.sections.flatMap((section) =>
    section.items.map((item) => item.source),
  );
  const includePrefixes = manifest.includePrefixes ?? [];
  const excludePrefixes = manifest.excludePrefixes ?? [];
  const sourceFiles = await walkMarkdownFiles(sourceRoot);
  const generatedSources = [];

  for (const sourceFile of sourceFiles) {
    const source = path.posix.join('docs', toPosixPath(path.relative(sourceRoot, sourceFile)));
    if (
      isIncludedByPrefix(source, includePrefixes) &&
      !isIncludedByPrefix(source, excludePrefixes)
    ) {
      generatedSources.push(source);
    }
  }

  return uniqueSorted([...manifestSources, ...generatedSources]);
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

function repositoryUrlForPath(repositoryPath, query, anchor) {
  return `${repositoryBlobBaseUrl}/${repositoryPath}${query ? `?${query}` : ''}${
    anchor ? `#${anchor}` : ''
  }`;
}

function repositoryPathForResolvedSource(resolvedSource) {
  return resolvedSource.replace(/^(\.\.\/)+/u, '');
}

function rewriteMarkdownLinks(markdown, source, publishedSourceSet) {
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
      if (!targetPath.endsWith('.md')) {
        return fullMatch;
      }

      const resolvedSource = targetPath.startsWith('docs/')
        ? path.posix.normalize(targetPath)
        : path.posix.normalize(path.posix.join(sourceParent, targetPath));
      if (!resolvedSource.startsWith('docs/')) {
        const repositoryPath = repositoryPathForResolvedSource(resolvedSource);
        const absoluteRepositoryPath = path.join(repoRoot, repositoryPath);
        if (repositoryPath.endsWith('.md') && existsSync(absoluteRepositoryPath)) {
          return `[${label}](${repositoryUrlForPath(repositoryPath, query, anchor)})`;
        }
        return fullMatch;
      }

      if (!publishedSourceSet.has(resolvedSource)) {
        const absoluteRepositoryPath = path.join(repoRoot, resolvedSource);
        if (existsSync(absoluteRepositoryPath)) {
          return `[${label}](${repositoryUrlForPath(resolvedSource, query, anchor)})`;
        }
      }

      const route = routeForDocsSource(resolvedSource);
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

async function syncDocs() {
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  for (const section of manifest.sections) {
    for (const item of section.items) {
      const sourcePath = path.join(repoRoot, item.source);
      try {
        await fs.access(sourcePath);
      } catch {
        throw new Error(`Manifest source not found: ${item.source}`);
      }
    }
  }

  await fs.rm(targetRoot, { recursive: true, force: true });
  await fs.mkdir(targetRoot, { recursive: true });
  await fs.writeFile(path.join(targetRoot, '.gitignore'), '*\n!.gitignore\n');

  const sources = await publishedSources(manifest);
  const publishedSourceSet = new Set(sources);
  for (const source of sources) {
    const sourceFile = path.join(repoRoot, source);
    const relativePath = toPosixPath(path.relative(sourceRoot, sourceFile));
    const targetPath = path.join(targetRoot, relativePath);
    const markdown = await fs.readFile(sourceFile, 'utf8');

    await fs.mkdir(path.dirname(targetPath), { recursive: true });
    await fs.writeFile(
      targetPath,
      normalizeGeneratedMarkdown(
        withStarlightFrontmatter(
          rewriteMarkdownLinks(markdown, source, publishedSourceSet),
          relativePath,
        ),
      ),
    );
  }

  console.log(`Synced ${sources.length} docs pages into Starlight content.`);
}

syncDocs().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
