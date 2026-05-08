# Composition Error Taxonomy Design

Status: Approved for planning
Date: 2026-05-07
Author: Codex

## Summary

Floe should make plugin resolution and composition failures actionable by using
specific `COMPOSITION_*` error codes for public plugin-composition failure
modes. The implementation should keep the existing `CompilationException` and
`CompilationError` surfaces, but stop collapsing storage/catalog composition
failures into generic `E201` errors.

The immediate scope is the current storage/catalog composition path and Helm
storage renderer preconditions. Legacy numeric `E*` codes remain valid for
general compilation pipeline failures outside the plugin-composition boundary.

## Current Problem

The storage composition work already introduced a typed resolver and a few
composition issue codes:

- `COMPOSITION_STORAGE_MISSING`
- `COMPOSITION_PROTOCOL_UNSUPPORTED`
- `COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED`

However, `_build_storage_deployment_binding()` still reports several distinct
operator actions as `E201`, including missing plugin packages, wrong plugin
interfaces, invalid plugin configuration, deployment binding construction
failures, and catalog translation failures. Helm storage rendering also raises
plain `ValueError` for missing deployment binding facts.

That means an operator cannot reliably tell whether they need to install a
plugin, fix manifest config, choose compatible plugins, add a deployment
binding, or fix an artifact/rendering precondition.

## Goals

- Use `COMPOSITION_*` for public plugin-composition and deployment-binding
  failures.
- Preserve existing exception types unless a narrow new type becomes necessary.
- Map each public code to a distinct operator action.
- Avoid noisy codes for internal helper branches.
- Keep `CompiledArtifacts` secret-free and do not add raw config values to
  error contexts.
- Add regression tests for each public failure class.
- Document public codes where users and operators already look for composition
  contracts.

## Non-Goals

- Do not redesign the full compilation error model.
- Do not convert every existing `E201` in the repository.
- Do not add a new plugin resolver architecture.
- Do not introduce provider-specific compatibility aliases.
- Do not make Helm decide plugin compatibility.

## Error Code Taxonomy

The following public codes should be supported by this work:

| Code | Failure class | Operator action |
| --- | --- | --- |
| `COMPOSITION_PLUGIN_MISSING` | A selected plugin cannot be found or loaded from the registry. | Install the plugin package or fix the manifest plugin type. |
| `COMPOSITION_PLUGIN_INTERFACE_INVALID` | A registry entry does not implement the required plugin ABC. | Register the plugin under the correct entry point group or fix the plugin implementation. |
| `COMPOSITION_PLUGIN_CONFIG_INVALID` | A selected plugin exists but its config or provider-owned binding construction is invalid. | Fix `manifest.yaml` plugin config or provider-specific required fields. |
| `COMPOSITION_STORAGE_MISSING` | A consumer declares storage requirements but no storage plugin is selected. | Select a storage plugin or remove the storage-dependent consumer. |
| `COMPOSITION_PROTOCOL_UNSUPPORTED` | Selected plugins do not share a required storage protocol. | Choose compatible providers or adjust provider configuration. |
| `COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED` | Selected plugins do not share a required credential mode. | Choose compatible identity/secret/storage modes or update provider config. |
| `COMPOSITION_DEPLOYMENT_BINDING_MISSING` | A selected plugin cannot provide the typed deployment binding needed by composition. | Upgrade/fix the plugin so it emits the binding required by the composition contract. |
| `COMPOSITION_RENDERER_PRECONDITION_FAILED` | A renderer receives a compiled artifact shape it cannot render. | Recompile with required deployment bindings or fix the artifact before rendering. |

These are intentionally operator-action classes, not implementation-detail
classes. For example, a Pydantic validation failure inside a plugin's config
schema and a provider-owned binding validation failure both map to
`COMPOSITION_PLUGIN_CONFIG_INVALID`, because the operator action is to fix the
selected plugin's manifest/configuration.

## Implementation Shape

Keep `CompilationError` as the user-facing structured error model. Extend its
documented code examples and `ERROR_CODES` map with the public `COMPOSITION_*`
taxonomy.

Update the storage/catalog composition path in
`packages/floe-core/src/floe_core/compilation/stages.py`:

- Registry lookup/configuration failures for selected storage/catalog plugins
  raise `COMPOSITION_PLUGIN_MISSING` when the plugin cannot be found or loaded.
- Wrong ABC checks raise `COMPOSITION_PLUGIN_INTERFACE_INVALID`.
- Storage deployment binding construction failures caused by plugin config or
  provider-owned binding validation raise `COMPOSITION_PLUGIN_CONFIG_INVALID`.
- A plugin that does not implement the required deployment binding hook raises
  `COMPOSITION_DEPLOYMENT_BINDING_MISSING`.
- Resolver findings keep their existing issue code and are passed through the
  `CompilationError` context as `composition_issues`.
- Catalog deployment translation failures caused by invalid config or binding
  translation raise `COMPOSITION_PLUGIN_CONFIG_INVALID` unless the plugin lacks
  the required binding hook, in which case they raise
  `COMPOSITION_DEPLOYMENT_BINDING_MISSING`.

Update the Helm storage renderer in
`packages/floe-core/src/floe_core/cli/helm/generate.py` so storage-renderer
precondition failures use a structured composition renderer error instead of
plain `ValueError`. The CLI can still display a normal command error, but unit
tests should assert the public code or wrapped message where the local API is
called directly.

## Testing

Add or update focused tests:

- Composition resolver tests continue to assert protocol, credential mode, and
  missing-storage codes.
- Compilation storage binding tests assert distinct codes for missing storage
  plugin, wrong storage interface, invalid storage config, missing catalog
  plugin, wrong catalog interface, invalid catalog translation, and missing
  deployment binding hook.
- Helm generation tests assert
  `COMPOSITION_RENDERER_PRECONDITION_FAILED` for missing catalog binding,
  wrong catalog provider, missing bucket requirements, and missing Kubernetes
  Secret refs.
- Existing behavior tests should continue to prove successful MinIO plus Polaris
  composition emits secret-free deployment bindings and Helm values.

Run the narrow unit suites first:

```bash
uv run pytest packages/floe-core/tests/unit/composition packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py packages/floe-core/tests/unit/helm/test_generate_cli.py -q
```

Before PR, run the repo-standard checks required by the touched Python surface:

```bash
make lint
make typecheck
make test-unit
```

## Documentation

Update `docs/contracts/compiled-artifacts.md` or the plugin composition
architecture docs with the public taxonomy table. The docs should state that
`COMPOSITION_*` codes are user-facing plugin-composition diagnostics and that
legacy numeric `E*` codes remain for broader compilation stages.

## Acceptance Criteria

- Each failure class named in issue #319 has a distinct public code.
- No raw secrets are introduced into errors, contexts, tests, or generated
  artifacts.
- Existing exception types remain compatible for callers that catch
  `CompilationException`.
- Tests cover the public taxonomy and continue to cover the successful
  MinIO/Polaris path.
- Documentation lists the codes and their operator actions.
