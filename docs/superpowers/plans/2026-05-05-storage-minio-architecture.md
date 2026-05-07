# Storage MinIO Architecture Plan

Status: Superseded by `docs/superpowers/plans/2026-05-07-storage-composition-closeout.md`

This early plan captured the initial strict MinIO rename and storage-binding
direction. It is retained only as a historical pointer because the target
architecture changed during the composition review.

Use the closeout plan and current architecture documents as the source of
truth:

- `docs/superpowers/plans/2026-05-07-storage-composition-closeout.md`
- `docs/superpowers/specs/2026-05-05-storage-minio-architecture-design.md`
- `docs/architecture/adr/0036-storage-plugin-interface.md`
- `docs/architecture/interfaces/storage-plugin.md`
- `docs/architecture/interfaces/catalog-plugin.md`
- `docs/contracts/compiled-artifacts.md`
- `docs/architecture/plugin-composition-uplift-tracker.md`

Current contract:

- Storage plugins emit neutral, secret-free storage deployment bindings.
- `floe-core` validates storage/catalog compatibility through the composition
  resolver and records typed deployment bindings in `CompiledArtifacts`.
- Catalog plugins own catalog-specific storage translation. Polaris owns its
  `storageConfigInfo` inputs, endpoint fields, STS semantics, allowed
  locations, and storage Secret references.
- Helm renders generated deployment bindings. It must not reconstruct storage
  semantics from legacy plugin config or literal chart credentials.
- Broader plugin-family uplift is tracked outside the storage PR in
  `docs/architecture/plugin-composition-uplift-tracker.md`.
