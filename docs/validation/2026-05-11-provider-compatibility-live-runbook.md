# Provider Compatibility Live Validation Runbook

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Executable live-service validation plan for the provider compatibility spike.

## Preconditions

- Run from `main`.
- Worktree is clean before validation.
- DevPod is installed and has the Hetzner provider initialized.
- `.env` contains `DEVPOD_HETZNER_TOKEN` or the environment contains `HCLOUD_TOKEN`.
- AWS live proof requires explicit user approval that AWS credentials are available and scoped for the test.
- Do not run live AWS cleanup commands against shared resources unless the resource names match the current run prefix.

## Failure Classification

| Classification | Meaning |
| --- | --- |
| Product failure | Floe resolver, binding, runtime translation, renderer, or plugin behavior is wrong |
| Provider failure | AWS, Glue, S3, Nessie, or catalog provider rejects auth, permissions, region, endpoint, warehouse, or API usage |
| Infrastructure failure | DevPod, Hetzner, Kind, Flux, network, or provisioning fails before product validation |
| Cleanup failure | Billable or test resources remain after the run |
| Tooling warning | Non-fatal wrapper or tunnel behavior occurs after artifacts and cleanup prove the result |

## Preferred Lane: AWS S3 Plus AWS Glue

### Resource Naming

Use a unique run prefix:

```bash
export FLOE_PROVIDER_SPIKE_RUN="floe-provider-$(date -u +%Y%m%dT%H%M%SZ)"
```

All AWS resources created for the proof must include `${FLOE_PROVIDER_SPIKE_RUN}` in the name or tags.

### Readiness Checks

```bash
git status --short --branch
devpod list
aws sts get-caller-identity
aws s3api list-buckets --query 'Buckets[].Name' --output text
aws glue get-databases --max-results 1
```

Expected:

- Git branch is `main`.
- DevPod list is empty or has no current-run workspace.
- AWS caller identity succeeds.
- S3 and Glue list commands succeed with the intended test account.

### Product Validation Shape

The live proof should preserve these artifacts:

- Compiled artifact JSON.
- Resolver decision output.
- Runtime catalog connection projection.
- PyIceberg or runtime config derived from bindings.
- Live create/list/read/write output.
- Secret scan output for artifacts and logs.

### AWS Cleanup

Cleanup must verify these resource classes:

```bash
aws glue get-databases
aws glue get-tables --database-name "${FLOE_PROVIDER_SPIKE_RUN}"
aws s3api list-objects-v2 --bucket "${FLOE_PROVIDER_SPIKE_RUN}" --max-items 10
aws s3api head-bucket --bucket "${FLOE_PROVIDER_SPIKE_RUN}"
aws iam list-roles --query "Roles[?contains(RoleName, '${FLOE_PROVIDER_SPIKE_RUN}')].RoleName"
aws iam list-policies --scope Local --query "Policies[?contains(PolicyName, '${FLOE_PROVIDER_SPIKE_RUN}')].Arn"
```

Expected after cleanup:

- Glue database and tables created for the run are absent.
- S3 bucket or prefix created for the run is absent or empty and retained only if explicitly approved.
- IAM roles and policies created for the run are absent.
- Any external reusable credential or role is named in the final evidence and not deleted by the runbook.

## Fallback Lane: Nessie Plus MinIO

Use this lane when AWS access is unavailable or not safe for the first proof.

Expected proof:

- Nessie catalog service is deployed in the remote validation environment.
- MinIO remains the storage provider.
- Resolver accepts MinIO plus Nessie only when catalog requirements match storage capabilities.
- Runtime catalog connection is derived from deployment bindings.
- Iceberg table create/list/read/write succeeds.
- DevPod and Hetzner resources are directly inventoried after cleanup.

## DevPod And Hetzner Cleanup

Use the existing remote lane shape:

```bash
DEVPOD_WORKSPACE="${FLOE_PROVIDER_SPIKE_RUN}" DEVPOD_REMOTE_E2E_MAKE_TARGET=test-e2e-full make devpod-test
devpod list
```

Direct Hetzner inventory must check these resource classes for the current run prefix:

```bash
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

HCLOUD_INVENTORY_TOKEN="${DEVPOD_HETZNER_TOKEN:-${HCLOUD_TOKEN:-}}"
if [ -z "${HCLOUD_INVENTORY_TOKEN}" ]; then
  echo "ERROR: set DEVPOD_HETZNER_TOKEN or HCLOUD_TOKEN before Hetzner inventory" >&2
  exit 1
fi

if [ -z "${FLOE_PROVIDER_SPIKE_RUN:-}" ]; then
  echo "ERROR: set FLOE_PROVIDER_SPIKE_RUN before Hetzner inventory" >&2
  exit 1
fi

for resource_class in servers volumes ssh_keys load_balancers floating_ips; do
  echo "== ${resource_class} matching ${FLOE_PROVIDER_SPIKE_RUN} =="
  curl -fsS \
    -H "Authorization: Bearer ${HCLOUD_INVENTORY_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://api.hetzner.cloud/v1/${resource_class}" \
    | jq -r --arg class "${resource_class}" --arg run "${FLOE_PROVIDER_SPIKE_RUN}" '
        .[$class]
        | map(select((.name // "") | contains($run)))
        | if length == 0 then
            "no matches"
          else
            (["id", "name", "status"] | @tsv),
            (.[] | [.id, (.name // "-"), (.status // "-")] | @tsv)
          end
      '
done
```

Final evidence must state whether each class has no current-run resources remaining. Delete only current-run matches in a later cleanup step using the provider API or `devpod delete`.

## DevPod Evidence Source

The existing remote lane wrapper documents `DEVPOD_WORKSPACE`, `DEVPOD_REMOTE_E2E_MAKE_TARGET`, and `DEVPOD_REMOTE_E2E_TIMEOUT` as the controls for workspace naming, remote make target selection, and remote timeout. The 2026-05-09 post-composition validation record shows prior use of `DEVPOD_WORKSPACE=floe-postcomp-audit make devpod-test`, `devpod list`, and direct Hetzner inventory for current-run servers, volumes, and SSH keys.
