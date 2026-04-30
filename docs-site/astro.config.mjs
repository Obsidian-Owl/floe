import fs from 'node:fs';

import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

const manifest = JSON.parse(
  fs.readFileSync(new URL('./docs-manifest.json', import.meta.url), 'utf8'),
);

function itemToSidebarLink(item) {
  return {
    label: item.title,
    link: item.slug === 'index' ? '/' : `/${item.slug}/`,
  };
}

const sidebar = manifest.sections.map((section) => {
  if (section.items.length === 1 && section.items[0].slug === 'index') {
    return itemToSidebarLink(section.items[0]);
  }

  return {
    label: section.label,
    items: section.items.map(itemToSidebarLink),
  };
});

export default defineConfig({
  site: 'https://obsidian-owl.github.io/floe',
  integrations: [
    starlight({
      title: 'Floe',
      description: 'Open platform for building internal data platforms.',
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/Obsidian-Owl/floe',
        },
      ],
      sidebar,
    }),
  ],
});
