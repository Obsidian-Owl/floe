# floe-cli

> **DEPRECATED**: This package is deprecated and will be removed in a future release.
>
> The `floe` CLI has been unified in `floe-core`. Please use `floe-core` instead.
>
> ## Migration
>
> If you have `floe-cli` installed, uninstall it and install `floe-core`:
>
> ```bash
> pip uninstall floe-cli
> pip install floe-core
> ```
>
> All commands are now available through the unified `floe` entry point from `floe-core`:
>
> - `floe platform compile` - Compile FloeSpec and Manifest
> - `floe rbac generate` - Generate RBAC manifests
> - `floe artifact push` - Push artifacts to OCI registry
> - `floe compile` - Data Team compilation (stub)
> - `floe validate` - Data Team validation (stub)
> - `floe run` - Pipeline execution (stub)
> - `floe test` - dbt test execution (stub)

---

*Original package description below for reference:*

## Description

CLI for the floe data platform. This package provided the original RBAC management
commands before the CLI unification.

## Status

**DEPRECATED** - Use `floe-core` instead.
