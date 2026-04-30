export const docsSite = 'https://obsidian-owl.github.io/floe';
export const docsBase = new URL(docsSite).pathname.replace(/\/$/u, '');

export function withDocsBase(route, base = docsBase) {
  if (!base) {
    return route;
  }

  if (route === '/') {
    return `${base}/`;
  }

  return `${base}${route}`;
}
