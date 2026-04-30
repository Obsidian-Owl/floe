# Docs Platform Starlight Migration Design

## Decision

Move Floe documentation off MkDocs before the first alpha tag and adopt Astro Starlight as the documentation renderer.

The MkDocs site was added recently, but the Material for MkDocs warning about the future MkDocs 2.0 direction creates immediate platform risk. Pinning MkDocs would reduce short-term noise but would knowingly ship new release debt. For Floe's alpha posture, documentation should be a release asset, not a fragile sidecar.

## Goals

- Replace MkDocs and Material for MkDocs with a static Starlight docs site.
- Keep `docs/` as the source of truth for authored Markdown.
- Avoid duplicated docs content by generating Starlight content from a manifest.
- Preserve the current alpha-critical docs navigation.
- Keep `make docs-build`, `make docs-serve`, and `make docs-validate` as stable user entry points.
- Make docs validation renderer-neutral so a future docs renderer change does not rewrite the validation contract.

## Non-Goals

- Do not redesign every page.
- Do not migrate historical planning artifacts into the public docs site or navigation.
- Do not build a custom docs framework.
- Do not make final DevPod + Hetzner release validation part of this docs migration.

## Architecture

The repository will have three separate concerns:

1. Authored content remains in `docs/`.
2. A docs-site manifest declares which source pages are part of the user-facing site and how they appear in navigation.
3. Astro Starlight renders generated content under `docs-site/src/content/docs/`.

The manifest is the stable contract. It records source file, generated slug, title, navigation group, and ordering. The sync script reads this manifest, validates source pages, injects Starlight frontmatter where required, and writes generated Markdown into the Starlight content collection.

This design avoids coupling validation to MkDocs YAML and avoids hand-copying Markdown into a second content tree.

## Components

- `docs-site/package.json`: Node package for the docs renderer.
- `docs-site/package-lock.json`: Locked npm dependency graph.
- `docs-site/astro.config.mjs`: Starlight integration and sidebar derived from the manifest.
- `docs-site/docs-manifest.json`: Renderer-neutral navigation and source mapping.
- `docs-site/scripts/sync-docs.mjs`: Generates Starlight content from `docs/`.
- `docs-site/src/content.config.ts`: Starlight content collection config.
- `testing/ci/validate-docs-navigation.py`: Renderer-neutral validation for manifest coverage and Markdown links.
- `testing/ci/tests/test_validate_docs_navigation.py`: Unit tests for manifest validation.
- `Makefile`: Stable docs command entry points backed by npm/Starlight.
- `.github/workflows/docs.yml`: CI build for validation and Starlight static output.

## Validation

The validation flow must catch the warnings seen locally:

- Site-root Markdown links like `/TESTING.md` fail validation.
- Broken relative Markdown links fail validation.
- Alpha-critical docs missing from the manifest fail validation.
- Manifest entries pointing to missing source pages fail validation.
- Generated Starlight pages build successfully.

`/api/daemon/status` 404s are not a docs source issue unless the path appears in repository content or generated output. The migration should still verify this by searching source and generated output.

## Testing

- Unit tests for the Python docs validator.
- `make docs-validate` runs the validator and the Starlight build.
- `make docs-build` produces static output.
- `make docs-serve` starts the Starlight local preview path without MkDocs.
- CI runs the same validation and build on pull requests.

## External References

- Starlight getting started: https://starlight.astro.build/getting-started/
- Starlight configuration reference: https://starlight.astro.build/reference/configuration/
- Starlight sidebar guide: https://starlight.astro.build/guides/sidebar/
- Material for MkDocs MkDocs 2.0 analysis: https://squidfunk.github.io/mkdocs-material/blog/2026/02/18/mkdocs-2.0/

## Approval

Approved in terminal on 2026-04-30.
