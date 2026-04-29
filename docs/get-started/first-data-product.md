# Build Your First Data Product

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

- Inspect the bundled demo data products.
- Compile the demo dbt projects and Floe artifacts.
- Verify generated artifacts are current before demo deployment.
- Use the Customer 360 demo as the alpha reference product.

## Commands

```bash
ls demo/customer-360
make compile-demo
git diff -- demo/customer-360/target/manifest.json demo/customer-360/compiled_artifacts.json
```

## Success Criteria

- `make compile-demo` compiles the demo dbt projects.
- `demo/customer-360/target/manifest.json` exists after compilation.
- `demo/customer-360/compiled_artifacts.json` exists after compilation.
- Any generated diffs are reviewed before committing.

## Next Step

- [Run the Customer 360 demo](../demo/customer-360.md)
