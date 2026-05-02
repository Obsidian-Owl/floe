# Alpha Docs And Demo Walkthrough - 2026-05-02

## Commit

- Validation baseline commit: `fe526a2f3f3ecc57444e1158064ed82dbb60a04e`
- Branch: `docs/alpha-docs-demo-walkthrough`
- Docs site: https://obsidian-owl.github.io/floe/
- Release gate: https://github.com/Obsidian-Owl/floe/issues/288

## Automated Checks

| Check | Result | Evidence |
| --- | --- | --- |
| `npm --prefix docs-site test` | PASS | 34 tests passed, 0 failed after adding Customer 360 query-boundary guardrails. |
| `make docs-build` | PASS | Starlight synced 132 docs pages and built 133 pages; Pagefind and sitemap generation completed. |
| `uv run python testing/ci/validate-docs-navigation.py` | PASS | Command exited 0 after bytecode compiling 14038 files in the evidence worktree. |

## Published Route Checks

| Page | Result | Evidence |
| --- | --- | --- |
| Platform Engineer first platform | PASS | https://obsidian-owl.github.io/floe/platform-engineers/first-platform/ returned HTTP 200 with one H1: `Deploy Your First Platform`. |
| Platform Engineers | PASS | https://obsidian-owl.github.io/floe/platform-engineers/ returned HTTP 200 with one H1: `Platform Engineers`. |
| Deployment guide | PASS | https://obsidian-owl.github.io/floe/guides/deployment/ returned HTTP 200 with one H1: `Deployment Guides`. |
| Contributor workflows | PASS | https://obsidian-owl.github.io/floe/contributing/ returned HTTP 200 with one H1: `Contributing`. |
| Data Engineers | PASS | https://obsidian-owl.github.io/floe/data-engineers/ returned HTTP 200 with one H1: `Data Engineers`. |
| Demo | PASS | https://obsidian-owl.github.io/floe/demo/ returned HTTP 200 with one H1: `Demo`. |
| First data product | PASS | https://obsidian-owl.github.io/floe/data-engineers/first-data-product/ returned HTTP 200 with one H1: `Build Your First Data Product`. |
| Customer 360 | PASS | https://obsidian-owl.github.io/floe/demo/customer-360/ returned HTTP 200 with one H1: `Customer 360 Golden Demo`. |
| Customer 360 validation | PASS | https://obsidian-owl.github.io/floe/demo/customer-360-validation/ returned HTTP 200 with one H1: `Customer 360 Validation`. |

The previous execution-plan route `https://obsidian-owl.github.io/floe/guides/first-data-product/` returned HTTP 404. It was not linked from the published docs navigation, but the release execution plan now points at the current persona route: `https://obsidian-owl.github.io/floe/data-engineers/first-data-product/`.

## Platform Engineer Walkthrough

| Page | Result | Notes |
| --- | --- | --- |
| First platform | PASS | The guide is provider-neutral: it starts from any Kubernetes cluster, calls out Kind for evaluation, and does not require Hetzner for product deployment. |
| Platform Engineers | PASS | Ownership is clear: Platform Engineers own cluster access, manifests, service access, secrets, and the Platform Environment Contract. |
| Deployment guide | PASS | The deployment model is "bring any conformant Kubernetes cluster"; Data Mesh is presented as implemented primitives and planned operations rather than an alpha deployment promise. |
| Contributor remote validation operations | PASS | Contributor docs keep DevPod + Hetzner scoped to heavyweight validation and release workflows, not product deployment. |

## Data Engineer Walkthrough

| Page | Result | Notes |
| --- | --- | --- |
| Data Engineers | PASS | The path starts from a Platform Environment Contract and separates Data Engineer ownership from platform ownership. |
| First data product | PASS | The guide teaches `hello-orders` before Customer 360 and avoids presenting planned root lifecycle commands as current product commands. |
| Data product runtime artifacts | PASS | The deployment story is accurately framed as CI artifact packaging and organization-approved deployment handoff for alpha. |
| Demo | PASS | Customer 360 is positioned as the advanced proof after the first data product path, not as the only onboarding path. |
| Customer 360 validation | PASS | Validation explains Dagster, storage, Marquez, Jaeger, Polaris, and business metric evidence. The docs now clarify that the current alpha business/query proof is command-based against generated Iceberg outputs, while Cube is optional and disabled by default. |

## Defects Found And Resolved

| Finding | Resolution |
| --- | --- |
| Release execution plan pointed the Data Engineer walkthrough at `/floe/guides/first-data-product/`, which returns HTTP 404. | Updated the plan to `/floe/data-engineers/first-data-product/`. |
| Customer 360 docs used broad `semantic/query layer` wording without clearly stating the current alpha query proof. | Clarified that Customer 360 uses command-based business metric validation against Iceberg outputs; Cube is charted but disabled by default and not part of the Customer 360 alpha gate unless enabled by the platform. |
| No guardrail existed to prevent future Customer 360 docs from implying Cube is required for the alpha query proof. | Added docs-site source validation tests for the Customer 360 query boundary. |

## Decision

- Release decision: PASS for #288 after this evidence branch is merged.
- Blocking follow-up issues: none from this walkthrough.
- Remaining alpha gates: #278, #285, and #289.

This does not replace the final #285 DevPod remote validation lane. The final release-candidate record must still prove the Customer 360 demo, OpenLineage/Marquez, Jaeger, storage, Dagster, and business metric evidence on the merged release-candidate commit.
