import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const docsSiteRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const distRoot = path.join(docsSiteRoot, 'dist');
const manifestPath = path.join(docsSiteRoot, 'docs-manifest.json');
const hrefPattern = /href=["']([^"']+)["']/gu;
const daemonStatusPath = '/api/daemon/status';

async function walkHtmlFiles(directory) {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkHtmlFiles(absolutePath)));
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      files.push(absolutePath);
    }
  }

  return files;
}

function withoutHashOrQuery(href) {
  return href.split('#', 1)[0].split('?', 1)[0];
}

function routePrefixForDocsPrefix(prefix) {
  const withoutDocsPrefix = prefix.replace(/^docs\//u, '');
  if (withoutDocsPrefix === '') {
    return '/';
  }
  return `/${withoutDocsPrefix}`;
}

function isExcludedDocsRoute(href, excludedRoutePrefixes) {
  const target = withoutHashOrQuery(href);
  if (
    target === '' ||
    target.startsWith('#') ||
    /^[a-z][a-z0-9+.-]*:/iu.test(target)
  ) {
    return false;
  }

  return excludedRoutePrefixes.some((prefix) => target.startsWith(prefix));
}

async function checkBuiltDocs() {
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  const excludedRoutePrefixes = (manifest.excludePrefixes ?? []).map(
    routePrefixForDocsPrefix,
  );
  const htmlFiles = await walkHtmlFiles(distRoot);
  const errors = [];

  for (const htmlFile of htmlFiles) {
    const html = await fs.readFile(htmlFile, 'utf8');
    const relativePath = path.relative(docsSiteRoot, htmlFile);
    for (const match of html.matchAll(hrefPattern)) {
      const href = match[1];
      if (/^[a-z][a-z0-9+.-]*:/iu.test(href)) {
        continue;
      }
      if (/\.md(?:[#?].*)?$/u.test(href)) {
        errors.push(`${relativePath}: contains local href to Markdown source: ${href}`);
      }
      if (isExcludedDocsRoute(href, excludedRoutePrefixes)) {
        errors.push(`${relativePath}: contains site href to excluded docs content: ${href}`);
      }
    }
    if (html.includes(daemonStatusPath)) {
      errors.push(`${relativePath}: references ${daemonStatusPath}`);
    }
  }

  if (errors.length > 0) {
    for (const error of errors) {
      console.error(error);
    }
    process.exitCode = 1;
    return;
  }

  console.log(`Checked ${htmlFiles.length} built docs pages.`);
}

checkBuiltDocs().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
