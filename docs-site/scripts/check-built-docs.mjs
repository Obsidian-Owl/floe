import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { docsBase } from '../site-config.mjs';

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

function stripDocsBase(target) {
  if (!docsBase) {
    return target;
  }
  if (target === docsBase) {
    return '/';
  }
  if (target.startsWith(`${docsBase}/`)) {
    return target.slice(docsBase.length);
  }
  return target;
}

function routeForHtmlFile(htmlFile, root = distRoot) {
  const relativePath = path.relative(root, htmlFile).split(path.sep).join(path.posix.sep);
  if (relativePath === 'index.html') {
    return '/';
  }
  if (relativePath.endsWith('/index.html')) {
    return `/${relativePath.slice(0, -'index.html'.length)}`;
  }
  return `/${relativePath.replace(/\.html$/u, '')}`;
}

function routeForHref(href, currentRoute) {
  const target = withoutHashOrQuery(href);
  if (
    target === '' ||
    target.startsWith('#') ||
    target.startsWith('//') ||
    /^[a-z][a-z0-9+.-]*:/iu.test(target)
  ) {
    return null;
  }

  if (target.startsWith('/')) {
    return stripDocsBase(target);
  }

  return path.posix.normalize(path.posix.join(currentRoute, target));
}

function routePrefixForDocsPrefix(prefix) {
  const withoutDocsPrefix = prefix.replace(/^docs\//u, '');
  if (withoutDocsPrefix === '') {
    return '/';
  }
  return `/${withoutDocsPrefix}`;
}

function isExcludedDocsRoute(href, excludedRoutePrefixes, currentRoute) {
  const route = routeForHref(href, currentRoute);
  if (!route) {
    return false;
  }

  return excludedRoutePrefixes.some((prefix) => route.startsWith(prefix));
}

function isRootLocalHrefWithoutBase(href) {
  const target = withoutHashOrQuery(href);
  if (
    !docsBase ||
    target === '' ||
    target.startsWith('#') ||
    target.startsWith('//') ||
    !target.startsWith('/') ||
    target.startsWith(`${docsBase}/`) ||
    target === docsBase ||
    /^[a-z][a-z0-9+.-]*:/iu.test(target)
  ) {
    return false;
  }

  return true;
}

export async function collectBuiltDocsErrors({
  docsSiteRoot: siteRoot = docsSiteRoot,
  distRoot: htmlRoot = distRoot,
  manifestPath: docsManifestPath = manifestPath,
} = {}) {
  const manifest = JSON.parse(await fs.readFile(docsManifestPath, 'utf8'));
  const excludedRoutePrefixes = (manifest.excludePrefixes ?? []).map(
    routePrefixForDocsPrefix,
  );
  const htmlFiles = await walkHtmlFiles(htmlRoot);
  const errors = [];

  for (const htmlFile of htmlFiles) {
    const html = await fs.readFile(htmlFile, 'utf8');
    const relativePath = path.relative(siteRoot, htmlFile);
    const currentRoute = routeForHtmlFile(htmlFile, htmlRoot);
    for (const match of html.matchAll(hrefPattern)) {
      const href = match[1];
      if (/^[a-z][a-z0-9+.-]*:/iu.test(href)) {
        continue;
      }
      if (/\.md(?:[#?].*)?$/u.test(href)) {
        errors.push(`${relativePath}: contains local href to Markdown source: ${href}`);
      }
      if (isRootLocalHrefWithoutBase(href)) {
        errors.push(`${relativePath}: contains root-local href without ${docsBase}: ${href}`);
      }
      if (isExcludedDocsRoute(href, excludedRoutePrefixes, currentRoute)) {
        errors.push(`${relativePath}: contains site href to excluded docs content: ${href}`);
      }
    }
    if (html.includes(daemonStatusPath)) {
      errors.push(`${relativePath}: references ${daemonStatusPath}`);
    }
  }

  return { checkedCount: htmlFiles.length, errors };
}

async function checkBuiltDocs() {
  const { checkedCount, errors } = await collectBuiltDocsErrors();

  if (errors.length > 0) {
    for (const error of errors) {
      console.error(error);
    }
    process.exitCode = 1;
    return;
  }

  console.log(`Checked ${checkedCount} built docs pages.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  checkBuiltDocs().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
