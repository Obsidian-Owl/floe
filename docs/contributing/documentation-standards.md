# Documentation Standards

Every user-facing change must update at least one documentation surface:

- Guide: user workflow changes.
- Reference: schema, CLI, chart, or API changes.
- Troubleshooting: discovered or fixed failure modes.
- Architecture: package boundary, contract, or plugin responsibility changes.
- Release notes: noteworthy behavior that does not need a permanent guide.

Pull requests that change behavior should state which docs surface was updated,
or explicitly state why no documentation update is needed.
