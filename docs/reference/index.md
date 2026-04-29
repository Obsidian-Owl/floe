# Reference

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Find stable contracts and schemas behind the alpha journeys.
- Use architecture references when a guide omits implementation detail.
- Check plugin interface documentation before changing extension points.
- Return to contributing guidance before opening a docs or behavior PR.

## Commands

```bash
make docs-build
uv run python testing/ci/validate-docs-navigation.py
```

## Success Criteria

- Reference pages are reachable from the MkDocs navigation.
- Alpha-critical pages remain present in the custom docs validator.
- Schema and contract links resolve to existing repository files.

## Next Step

- [floe.yaml schema](floe-yaml-schema.md)
- [Data contract reference](../contracts/datacontract-yaml-reference.md)
- [Plugin interfaces](../architecture/interfaces/index.md)
- [Contributing](../contributing/index.md)
