# Spec: Config Merge Fix (Unit 7)

## Acceptance Criteria

### AC-1: Polaris bootstrap MUST NOT set `table-default.s3.endpoint`

The Helm bootstrap job (`job-polaris-bootstrap.yaml`) MUST NOT set `table-default.s3.endpoint` in catalog properties. Only `s3.endpoint` (catalog-level) should be set. The `table-default.*` prefix causes PyIceberg to override client-side S3 endpoint config at the table level, which is the root cause of DX-004.

**How to verify:** `helm template` the chart. Assert rendered bootstrap job does NOT contain `table-default.s3.endpoint`. Assert `s3.endpoint` IS present (for Polaris server-side S3 access). Assert `storageConfigInfo.endpoint` IS present (for Polaris storage config).

### AC-2: PyIceberg client S3 endpoint MUST survive table load

After loading a table from Polaris, the `FileIO` used for data operations MUST use the client-provided `s3.endpoint`, not a server-provided override. The floe catalog plugin MUST ensure client endpoint takes precedence.

**How to verify:** Integration test: connect to Polaris catalog with `s3.endpoint=http://test-endpoint:9000`. Load a table. Assert `table.io.properties["s3.endpoint"]` equals the client-provided endpoint, not a K8s-internal hostname.

### AC-3: S3 endpoint flows from manifest.yaml through to PyIceberg FileIO without corruption

The endpoint defined in `manifest.yaml` `plugins.storage.config.endpoint` MUST be the endpoint used by PyIceberg for all S3 operations. No intermediate layer may silently replace it.

**How to verify:** Contract test: trace endpoint from `CompiledArtifacts.plugins.storage.config.endpoint` through `PolarisCatalogPlugin.connect()` config dict. Assert endpoint value is preserved. No `table-default.*` keys appear in the config dict passed to PyIceberg.

### AC-4: Helm unit tests validate no `table-default.s3.endpoint` in bootstrap

Helm unit tests (`helm unittest`) MUST assert that the bootstrap job does NOT set `table-default.s3.endpoint`. This is a regression gate.

**How to verify:** Run `helm unittest`. Assert test for bootstrap job validates absence of `table-default.s3.endpoint`. Test MUST fail if someone re-adds the property.

### AC-5: Polaris catalog plugin applies client endpoint override after table load

The `floe_catalog_polaris` plugin MUST ensure that after PyIceberg loads table metadata from the Polaris server, the client-side `s3.endpoint` is re-applied to the table's `FileIO` properties. This guards against any remaining server-side overrides.

**How to verify:** Unit test: mock PyIceberg catalog. Set table metadata to include server-provided `s3.endpoint=http://k8s-internal:9000`. Call plugin method that loads table. Assert resulting FileIO uses client endpoint, not server endpoint.
