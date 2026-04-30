# Contributing

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Validate documentation before submitting alpha-facing changes.
- Keep user journeys, reference pages, and troubleshooting notes in sync.
- Run the docs validator and strict Starlight build locally.
- Link release-impacting work to the alpha checklist when needed.

## Commands

```bash
make docs-validate
uv run pytest testing/ci/tests/test_validate_docs_navigation.py -q
```

## Contributor Workflows

- <a href="devpod-&#104;etzner/">Remote DevPod workspace</a> for heavyweight validation.
- [Contributor testing](testing.md) for unit, integration, E2E, docs, and release-validation checks.
- [Contributor troubleshooting](troubleshooting.md) for remote validation, tunnel, demo, lineage, trace, and stale-image failures.
- [Documentation standards](documentation-standards.md) for keeping docs aligned with behavior.

Contributor workflows can use repo-local `make` targets and DevPod. Platform Engineer and Data Engineer docs should describe product workflows that do not require contributor infrastructure.

## Success Criteria

- Alpha-critical documentation pages exist and are included in the docs manifest.
- Local relative Markdown links in required pages resolve.
- Validator tests pass after docs navigation changes.
- Pull requests explain which documentation surface changed.

## Next Step

- [Documentation standards](documentation-standards.md)
