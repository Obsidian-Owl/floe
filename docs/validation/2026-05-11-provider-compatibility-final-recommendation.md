# Provider Compatibility Final Recommendation

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Closeout recommendation for the provider compatibility spike.

## Evidence Artifacts

| Artifact | Role |
| --- | --- |
| `docs/validation/2026-05-11-provider-compatibility-system-map.md` | Implemented model and source map |
| `docs/validation/2026-05-11-provider-compatibility-matrix.md` | Provider matrix and Level decisions |
| `docs/validation/2026-05-11-provider-compatibility-gap-ledger.md` | Gap classification and next action |
| `docs/validation/2026-05-11-provider-compatibility-live-runbook.md` | Live AWS/Glue and Nessie/MinIO validation plan |

## Recommendation

Proceed with AWS S3 plus AWS Glue as the first provider compatibility
implementation design if AWS credentials and cleanup controls are available.
Otherwise proceed with Nessie plus MinIO as the first live proof while keeping
AWS S3 plus AWS Glue as the primary provider matrix target.

AWS S3 plus Glue is the stronger first target because it stresses the full
composition model: native cloud storage, managed catalog semantics, IAM,
credential and identity modes, PyIceberg runtime translation, and external
provider cleanup. Nessie plus MinIO is the safer fallback because it validates
catalog variation without adding cloud-provider billing and IAM surface area.

## First Implementation Unit

Recommended first implementation unit:

- Design native AWS S3 storage binding and AWS Glue catalog binding against the
  current composition model.
- Add resolver tests for AWS credential and identity modes.
- Add secret-free compiled artifact tests.
- Add runtime translator proof for PyIceberg Glue config derived from typed
  bindings.
- Keep live AWS validation behind the runbook readiness gate.

The first implementation unit should remain design/test-led. It should not add
literal AWS credential values to `CompiledArtifacts`, should not introduce a
compatibility shim around deprecated helper APIs, and should not let runtime
code rediscover provider config outside typed bindings.

## Fallback Implementation Unit

Recommended fallback implementation unit:

- Design Nessie catalog binding that composes with existing MinIO storage
  binding.
- Add resolver tests for MinIO plus Nessie compatibility.
- Add runtime translator proof for Nessie Iceberg catalog config.
- Use the fallback live lane to validate catalog variation without AWS
  resources.

The fallback is appropriate if AWS credentials, IAM scope, or cleanup controls
are not ready. It should not be treated as proof that native cloud storage is
complete.

## Explicit Deferrals

- GCS and Azure remain design pressure tests until a concrete provider path
  exists.
- Hive remains deferred until a concrete deployment path exists.
- Deprecated compatibility helpers are not new provider contracts.
- Raw credentials in `CompiledArtifacts` remain forbidden.
- Live AWS or DevPod validation has not been run as part of this spike
  artifact set.

## Closeout Status

The provider compatibility spike artifacts are complete when this document is
committed after the system map, matrix, gap ledger, and live runbook, and the
worktree is clean after the final commit.
