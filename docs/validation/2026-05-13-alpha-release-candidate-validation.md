# Alpha Release Candidate Validation

Date: 2026-05-13
Repo: `/Users/dmccarthy/Projects/floe/.worktrees/alpha-manifest-validator`
Branch: `release/alpha-manifest-validator`
Commit: `d3a30c43b78e4778b85e69d0989810b0358c0fc5`
Remote source used by DevPod wrapper: `git:https://github.com/Obsidian-Owl/floe@release/alpha-manifest-validator`

This record captures observed release-candidate validation for `v0.1.0-alpha.1`.
It does not record a tag cut and does not claim PyPI or Helm publication.

## Failure Taxonomy

| Classification | Meaning |
| --- | --- |
| Product | Floe product code or product test assertion failed after the lane reached product validation. |
| Release tooling | A required release gate, Make target, script, or automation entry point is missing or miswired before product validation can run. |
| Infrastructure | DevPod, Hetzner, Kind, Flux, network, or provider capacity failed before product validation. |
| Credential/setup | Required AWS, DevPod, Hetzner, or local setup was missing or invalid. |
| Cleanup | A cleanup command or inventory check failed after a lane attempted to create resources. |

## Local Release Checks

| Command | Result | Evidence | Classification |
| --- | --- | --- | --- |
| `git rev-parse HEAD` | Exit `0` | `d3a30c43b78e4778b85e69d0989810b0358c0fc5` | Evidence |
| `uv run python -m testing.release.cli validate --manifest release/floe-release.yaml --tag v0.1.0-alpha.1` | Exit `0` | `publish_count: 15`; `exclude_count: 11`; `git_tag: v0.1.0-alpha.1`; `python_version: 0.1.0a1`; `helm_version: 0.1.0-alpha.1` | Product pass |
| `uv run python -m testing.release.cli build --manifest release/floe-release.yaml --dist-dir .release-build/alpha-dist` | Exit `0` | Built `15` wheels and `15` sdists | Product pass |
| Count and remove `.release-build/alpha-dist` | Exit `0` | `wheels=15`; `sdists=15`; `.release-build/alpha-dist` removed before documentation commit | Cleanup pass |
| `uv run pytest testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py -q` | Exit `0` | `53 passed in 0.15s` | Product pass |
| `uv run ruff check testing/release testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py` | Exit `0` | `All checks passed!` | Product pass |
| `uv run mypy --strict testing/release` | Exit `0` | `Success: no issues found in 6 source files` | Product pass |

## Full Repo Validation

| Command | Result | Evidence | Classification |
| --- | --- | --- | --- |
| `make test-unit` | Exit `0` | `10657 passed, 1 skipped, 1 xfailed, 6 warnings in 184.34s (0:03:04)`; coverage `87.65%`, required coverage `80%` reached | Product pass |
| `make test-contract` | Exit `2` | `make: *** No rule to make target \`test-contract'. Stop.` | Release tooling failure: requested product gate target is absent from this branch's `Makefile` |
| `make lint` | Exit `0` after rerun with a Bash wrapper for exit-code capture | `All checks passed!`; `1284 files already formatted` | Product pass |
| `make typecheck` | Exit `0` | `Success: no issues found in 371 source files` | Product pass |

## DevPod And Hetzner Full E2E

| Field | Observed value |
| --- | --- |
| Requested lane | `DEVPOD_WORKSPACE=floe-alpha-rc-$(date -u +%Y%m%dT%H%M%SZ) DEVPOD_REMOTE_E2E_MAKE_TARGET=test-e2e-full make devpod-test` |
| Accepted workspace used for live attempt | `floe-alpha-rc-20260513-123857` |
| Reason workspace differs from requested example | DevPod rejected uppercase `T` and `Z` with `workspace name can only include smaller case letters, numbers or dashes`; rerun used lowercase-compatible timestamp separators. |
| Remote source | `git:https://github.com/Obsidian-Owl/floe@release/alpha-manifest-validator` |
| Machine name created before failure | `floe-alpha-4b60f` |
| Result | Failed before product tests ran |
| Exit code captured by wrapper | `0`; this was not treated as a pass because the log shows provisioning failure and no product test execution |
| Artifact path | None created; failure occurred during `devpod up` before remote E2E artifact collection |
| Final pytest summary | None; `test-e2e-full` never started |
| Failure taxonomy | Infrastructure failure |

Observed failure:

```text
Error in server creation action: action timeout
fatal prepare workspace client: exit status 1
```

Cleanup evidence:

| Check | Result |
| --- | --- |
| `devpod delete floe-alpha-rc-20260513-123857 --force` | DevPod reported `couldn't find workspace floe-alpha-rc-20260513-123857`; provider resources still existed in Hetzner inventory. |
| Direct Hetzner inventory after failure | Found server `130796337` / `floe-alpha-4b60f`, volume `105700551` / `floe-alpha-4b60f`, and SSH key `112236187` / `floe-alpha-4b60f-be10e08b`. |
| Direct Hetzner cleanup | Deleted server `130796337`, then volume `105700551`, then SSH key `112236187`. |
| Final direct Hetzner inventory | No `floe-alpha*` servers, volumes, SSH keys, load balancers, or floating IPs remained. |
| Final DevPod inventory | `devpod list` and `devpod machine list` showed no entries. |

Additional cleanup note: an interrupted local probe briefly created default
workspace resources for `floe` / `floe-734a5`. A direct Hetzner inventory after
review found server `130795698` / `floe-734a5` and volume `105700530` /
`floe-734a5`; both were deleted directly through the Hetzner API. The final
direct inventory showed no `floe-734a5`, `floe-alpha*`, or `floe-provi*`
servers, volumes, SSH keys, load balancers, or floating IPs, and `devpod list`
plus `devpod machine list` remained empty.

## AWS S3 And Glue Live Validation Through DevPod

AWS readiness input was the existing bootstrap profile and non-secret Terraform
state outputs:

| Field | Observed value |
| --- | --- |
| AWS profile used for credential export | `floe-aws-bootstrap` |
| AWS account | `278833447053` |
| AWS region | `ap-southeast-2` |
| S3 bucket | `floe-provider-tests-278833447053-ap-southeast-2` |
| S3 prefix for run | `runs/floe-provider-20260513T125105Z/` |
| Glue database prefix | `floe_provider_` |
| Glue database for run | `floe_provider_floe_provider_20260513T125105Z` |

| Field | Observed value |
| --- | --- |
| Command | `FLOE_PROVIDER_SPIKE_RUN=floe-provider-20260513T125105Z DEVPOD_WORKSPACE=floe-provider-20260513-125105 make devpod-test-aws-provider` with AWS credentials exported from `floe-aws-bootstrap` and non-secret Floe AWS env exported from `/Users/dmccarthy/Projects/floe/infra/aws-provider-tests/terraform.tfstate` |
| DevPod workspace | `floe-provider-20260513-125105` |
| Remote source | `git:https://github.com/Obsidian-Owl/floe@release/alpha-manifest-validator` |
| Machine name created before failure | `floe-provi-bdbf5` |
| Result | Failed before AWS product tests ran |
| Exit code | `2` |
| Artifact path | None created; failure occurred during `devpod up` before remote AWS test artifact collection |
| Pytest result for `tests/integration/test_aws_provider_live.py` | None; the test never started |
| Failure taxonomy | Infrastructure failure |

Observed failure:

```text
Error in server creation action: action timeout
fatal prepare workspace client: exit status 1
make: *** [devpod-test-aws-provider] Error 1
```

Cleanup evidence:

| Check | Result |
| --- | --- |
| Direct Hetzner inventory after AWS DevPod failure | Found server `130797909` / `floe-provi-bdbf5`, volume `105700674` / `floe-provi-bdbf5`, and SSH key `112236634` / `floe-provi-bdbf5-f194c46c`. |
| Direct Hetzner cleanup | Deleted server `130797909`, then volume `105700674`, then SSH key `112236634`. |
| `scripts/aws-provider-test-cleanup.sh` | Exit `0`; cleaned `s3://floe-provider-tests-278833447053-ap-southeast-2/runs/floe-provider-20260513T125105Z/`; checked Glue database `floe_provider_floe_provider_20260513T125105Z`; reported `Cleanup checks passed`. |
| Final direct Hetzner inventory | No `floe-provi*` servers, volumes, SSH keys, load balancers, or floating IPs remained. |
| Final DevPod inventory | `devpod list` and `devpod machine list` showed no entries. |

## Overall Result

Status: `DONE_WITH_CONCERNS`

Local release-package checks passed, and cleanup completed. The release
candidate is not fully validated because:

- Release tooling gap: `make test-contract` is not available in this branch's `Makefile`, so the contract-test product gate could not run.
- Full DevPod+Hetzner E2E failed during Hetzner server creation before product tests ran.
- AWS S3+Glue live validation failed during Hetzner server creation before `tests/integration/test_aws_provider_live.py` ran.

No tag was cut, no packages were published, and no credentials or remote env
files were archived.
