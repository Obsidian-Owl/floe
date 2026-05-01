# Enterprise Operating Model Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish enterprise-grade Floe documentation that shows Platform Engineers and Data Engineers how to configure, deploy, package, approve, run, and validate a Floe platform and a first data product without coupling the product path to DevPod, Hetzner, or unsupported lifecycle commands.

**Architecture:** Treat docs as tested product surface. Add concrete source examples for a Platform Environment Contract and a minimal `hello-orders` data product, then rewrite persona guides around those examples. Extend `docs-site` source checks so unsupported defaults, wrong compute guidance, unsupported commands, and Customer 360-as-first-product drift are caught before CI.

**Tech Stack:** Starlight, Astro, Node 24 `node:test`, Markdown docs, YAML examples, dbt project files, Floe platform compiler, `docs-site` sync/build scripts.

---

## File Structure

- Modify `docs-site/scripts/check-source-docs.mjs`: add guardrails for unsupported defaults, unsupported root data-team commands, wrong compute anti-patterns, and first-data-product Customer 360 drift.
- Modify `docs-site/scripts/check-source-docs.test.mjs`: add fixture tests for the new guardrails.
- Modify `docs-site/docs-manifest.json`: add Operating Model and Platform Environment Contract pages to Starlight navigation.
- Create `examples/platform-environment-contracts/dev.yaml`: concrete reference Platform Environment Contract used by docs.
- Create `examples/hello-orders/floe.yaml`: minimal Data Engineer product configuration.
- Create `examples/hello-orders/dbt_project.yml`: minimal dbt project metadata.
- Create `examples/hello-orders/seeds/orders.csv`: small seed dataset.
- Create `examples/hello-orders/models/staging/stg_orders.sql`: staging model.
- Create `examples/hello-orders/models/marts/mart_daily_orders.sql`: business output model.
- Create `examples/hello-orders/models/schema.yml`: dbt tests and descriptions.
- Create `docs/guides/operating-model.md`: recommended enterprise operating model.
- Create `docs/platform-engineers/platform-environment-contract.md`: Platform Environment Contract guide.
- Create `docs/guides/deployment/data-product-runtime-artifacts.md`: runtime artifact and deployment handoff patterns.
- Modify `docs/index.md`: make the docs landing page point at operating-model, first-platform, and first-data-product journeys.
- Modify `docs/platform-engineers/index.md`: clarify Platform Engineer responsibilities and recommended path.
- Modify `docs/platform-engineers/first-platform.md`: teach building a minimal platform and publishing the environment contract.
- Modify `docs/platform-engineers/validate-platform.md`: replace manual endpoint handoff with environment-contract evidence.
- Modify `docs/data-engineers/index.md`: clarify Data Engineer responsibilities and recommended path.
- Modify `docs/data-engineers/first-data-product.md`: teach `hello-orders` from scratch, not Customer 360.
- Modify `docs/data-engineers/validate-data-product.md`: validate `hello-orders` outputs, lineage, telemetry, and escalation boundaries.
- Modify `docs/demo/customer-360.md`: position Customer 360 as advanced proof after first-use guides.
- Modify `docs/architecture/opinionation-boundaries.md`: correct current defaults, capability labels, and compute policy.
- Modify `docs/reference/plugin-catalog.md`: tighten current alpha plugin wording to implementation truth.
- Modify `docs/architecture/capability-status.md`: add Dagster runtime artifact, `floe-jobs`, Platform Environment Contract, and hello-orders status.
- Modify `README.md`: align quick-start claims with current alpha docs and approved per-transform compute.

## Task 1: Add Docs Drift Guardrails

**Files:**
- Modify: `docs-site/scripts/check-source-docs.mjs`
- Test: `docs-site/scripts/check-source-docs.test.mjs`

- [ ] **Step 1: Add failing tests for unsupported defaults and compute anti-patterns**

Append these tests to `docs-site/scripts/check-source-docs.test.mjs`:

```js
test('collectSourceDocsErrors rejects unsupported current default integrations', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/opinionation-boundaries.md'),
      [
        '# Opinionation Boundaries',
        '',
        '| Component | Default | Alternatives |',
        '| --- | --- | --- |',
        '| Telemetry Backend | Jaeger (local), Datadog (production) | Grafana Cloud |',
        '| Lineage Backend | Marquez (local), Atlan (production) | OpenMetadata |',
        '| Storage | MinIO (local), S3 (production) | GCS |',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/architecture/opinionation-boundaries.md: labels Datadog as a current default integration',
      'docs/architecture/opinionation-boundaries.md: labels Atlan as a current default integration',
      'docs/architecture/opinionation-boundaries.md: labels S3 as a current production default',
    ]);
  });
});

test('collectSourceDocsErrors checks README as public product surface', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.writeFile(
      path.join(repoRoot, 'README.md'),
      '# Floe\n\nDatadog is the production default telemetry backend.\n',
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'README.md: labels Datadog as a current default integration',
    ]);
  });
});

test('collectSourceDocsErrors rejects wrong compute ownership guidance', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/architecture'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/architecture/opinionation-boundaries.md'),
      [
        '# Opinionation Boundaries',
        '',
        "### DON'T: Allow Data Engineers to select compute",
        '',
        'Data engineers inherit compute - they do not select it.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/architecture/opinionation-boundaries.md: forbids approved per-transform compute selection',
      'docs/architecture/opinionation-boundaries.md: says Data Engineers cannot select approved compute',
    ]);
  });
});
```

- [ ] **Step 2: Add failing tests for unsupported lifecycle commands and Customer 360 first-product drift**

Append these tests to `docs-site/scripts/check-source-docs.test.mjs`:

```js
test('collectSourceDocsErrors rejects unsupported root data-team lifecycle commands', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/data-engineers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/data-engineers/first-data-product.md'),
      [
        '# Build Your First Data Product',
        '',
        'Run `floe compile`.',
        'Run `floe run`.',
        'Run `floe product deploy`.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, [
      'docs/data-engineers/first-data-product.md: first data product guide must teach hello-orders before Customer 360',
      "docs/data-engineers/first-data-product.md: presents unsupported root command 'floe compile' as current",
      "docs/data-engineers/first-data-product.md: presents unsupported root command 'floe run' as current",
      "docs/data-engineers/first-data-product.md: presents unsupported CLI command 'floe product deploy' as current",
    ]);
  });
});

test('collectSourceDocsErrors allows planned root commands and Customer 360 as advanced proof', async () => {
  await withSourceDocsFixture(async ({ repoRoot, manifestPath }) => {
    await fs.mkdir(path.join(repoRoot, 'docs/data-engineers'), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, 'docs/data-engineers/first-data-product.md'),
      [
        '# Build Your First Data Product',
        '',
        'Build `hello-orders` first.',
        '`floe compile` is planned and not implemented as the current alpha product command.',
        'Customer 360 is the advanced proof after the hello-orders path.',
        '',
      ].join('\n'),
    );

    const { errors } = await collectSourceDocsErrors({ repoRoot, manifestPath });

    assert.deepEqual(errors, []);
  });
});
```

- [ ] **Step 3: Run source-doc tests and verify they fail**

Run:

```bash
cd docs-site
node --test scripts/check-source-docs.test.mjs
```

Expected: the new tests fail because the source checker does not yet enforce these rules.

- [ ] **Step 4: Implement the new source-doc checks**

In `docs-site/scripts/check-source-docs.mjs`, add these helpers after `hasNegativeOrPlannedContext()`:

```js
function isCurrentProductSurface(source) {
  return (
    source === 'README.md' ||
    source === 'docs/index.md' ||
    source === 'docs/architecture/opinionation-boundaries.md' ||
    source === 'docs/architecture/capability-status.md' ||
    source === 'docs/reference/plugin-catalog.md' ||
    source === 'docs/guides/data-product-lifecycle.md' ||
    source.startsWith('docs/start-here/') ||
    source.startsWith('docs/get-started/') ||
    source.startsWith('docs/platform-engineers/') ||
    source.startsWith('docs/data-engineers/') ||
    source.startsWith('docs/guides/deployment/')
  );
}

function collectSourceLevelErrors(source, markdown) {
  const errors = [];
  if (source === 'docs/data-engineers/first-data-product.md' && !/\bhello-orders\b/iu.test(markdown)) {
    errors.push('first data product guide must teach hello-orders before Customer 360');
  }
  return errors;
}
```

Then update `publishedMarkdownSources()` so README is checked as public product surface:

```js
  const readmePath = path.join(repoRoot, 'README.md');
  try {
    await fs.access(readmePath);
    sources.add('README.md');
  } catch {
    // Fixtures and downstream consumers may not have a README.
  }
```

Then extend `hasNegativeOrPlannedContext()` with alpha caveat words:

```js
function hasNegativeOrPlannedContext(line) {
  return /\b(not supported|unsupported|not alpha-supported|not implemented|planned|stub|stubs|historical|deprecated|rejected|was rejected|alternative|not a current|do not run|no Docker Compose|creates testing parity issues|parity issues|failure mode|advanced proof)\b/iu.test(
    line,
  );
}
```

Then add these checks inside `collectLineLevelErrors(line)`:

```js
  if (
    /\bDatadog\b.*\b(default|production)\b|\b(default|production)\b.*\bDatadog\b/iu.test(line) &&
    !hasNegativeOrPlannedContext(line)
  ) {
    errors.push('labels Datadog as a current default integration');
  }
  if (
    /\bAtlan\b.*\b(default|production)\b|\b(default|production)\b.*\bAtlan\b/iu.test(line) &&
    !hasNegativeOrPlannedContext(line)
  ) {
    errors.push('labels Atlan as a current default integration');
  }
  if (
    /\bS3\b.*\b(production default|default production|current production default|production\))/iu.test(
      line,
    ) &&
    !hasNegativeOrPlannedContext(line)
  ) {
    errors.push('labels S3 as a current production default');
  }
  if (/DON'?T:\s*Allow Data Engineers to select compute/iu.test(line)) {
    errors.push('forbids approved per-transform compute selection');
  }
  if (/Data Engineers?\s+inherit\s+compute.*do not select it/iu.test(line)) {
    errors.push('says Data Engineers cannot select approved compute');
  }
  for (const command of ['compile', 'run', 'validate']) {
    const pattern = new RegExp(String.raw`\bfloe\s+${command}\b`, 'iu');
    if (pattern.test(line) && !hasNegativeOrPlannedContext(line)) {
      errors.push(`presents unsupported root command 'floe ${command}' as current`);
    }
  }
  if (/\bfloe\s+product\s+deploy\b/iu.test(line) && !hasNegativeOrPlannedContext(line)) {
    errors.push("presents unsupported CLI command 'floe product deploy' as current");
  }
```

Change the source loop so line-level checks only apply the new product-surface rules to current product docs:

```js
    for (const error of collectSourceLevelErrors(source, proseMarkdown)) {
      errors.push(`${source}: ${error}`);
    }
    for (const line of markdown.split(/\r?\n/u)) {
      for (const error of collectLineLevelErrors(line)) {
        if (isCurrentProductSurface(source) || !/Datadog|Atlan|S3|compute|floe /iu.test(error)) {
          errors.push(`${source}: ${error}`);
        }
      }
    }
```

- [ ] **Step 5: Run source-doc tests**

Run:

```bash
cd docs-site
node --test scripts/check-source-docs.test.mjs
```

Expected: all `check-source-docs` tests pass.

- [ ] **Step 6: Commit**

```bash
git add docs-site/scripts/check-source-docs.mjs docs-site/scripts/check-source-docs.test.mjs
git commit -m "test: guard enterprise docs claims"
```

## Task 2: Add Concrete Reference Examples

**Files:**
- Create: `examples/platform-environment-contracts/dev.yaml`
- Create: `examples/hello-orders/floe.yaml`
- Create: `examples/hello-orders/dbt_project.yml`
- Create: `examples/hello-orders/seeds/orders.csv`
- Create: `examples/hello-orders/models/staging/stg_orders.sql`
- Create: `examples/hello-orders/models/marts/mart_daily_orders.sql`
- Create: `examples/hello-orders/models/schema.yml`

- [ ] **Step 1: Create the Platform Environment Contract example**

Create `examples/platform-environment-contracts/dev.yaml`:

```yaml
apiVersion: floe.dev/v1alpha1
kind: PlatformEnvironmentContract
metadata:
  name: floe-dev
  owner: platform-team@example.com
  description: Development Floe environment for first data products.
environment:
  name: dev
  kubernetes:
    namespace: floe-dev
    releaseName: floe
  platformManifest:
    source: git
    path: demo/manifest.yaml
    ociRef: oci://registry.example.com/floe/platform/dev:0.1.0
plugins:
  orchestrator:
    default: dagster
    alphaSupported: [dagster]
  catalog:
    default: polaris
    alphaSupported: [polaris]
  storage:
    default: s3-compatible
    alphaSupported: [s3-compatible]
  telemetryBackend:
    default: jaeger
    alphaSupported: [jaeger, console]
  lineageBackend:
    default: marquez
    alphaSupported: [marquez]
  compute:
    default: duckdb
    approved:
      - name: duckdb
        use: Small and medium dbt transformations in the alpha path.
runtime:
  recommendedAlphaSpine: dagster
  artifactRegistry: registry.example.com/data-products
  imageTagPolicy: git-sha
access:
  serviceAccount: floe-data-product-runner
  secrets:
    convention: Kubernetes Secret references only; do not put raw secrets in floe.yaml.
observability:
  dagsterUrl: http://localhost:3100
  marquezUrl: http://localhost:5100
  jaegerUrl: http://localhost:16686
  minioConsoleUrl: http://localhost:9001
promotion:
  requiredEvidence:
    - floe platform compile succeeds
    - dbt tests pass
    - runtime artifact image is published
    - Dagster run succeeds
    - OpenLineage event appears in Marquez
    - OpenTelemetry trace appears in Jaeger
support:
  escalation: platform-team@example.com
```

- [ ] **Step 2: Create the hello-orders Floe spec**

Create `examples/hello-orders/floe.yaml`:

```yaml
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: hello-orders
  version: 0.1.0
  description: Minimal orders data product for learning Floe.
  owner: data-engineering@example.com
  labels:
    domain: sales
    tier: gold
platform:
  manifest: "../../demo/manifest.yaml"
transforms:
  - name: stg_orders
    tags: [staging]
    tier: bronze
  - name: mart_daily_orders
    tags: [marts]
    tier: gold
    dependsOn: [stg_orders]
schedule:
  cron: "0 8 * * *"
  timezone: UTC
  enabled: false
```

- [ ] **Step 3: Create the dbt project and seed**

Create `examples/hello-orders/dbt_project.yml`:

```yaml
name: hello_orders
version: "0.1.0"
config-version: 2
profile: hello_orders

model-paths: ["models"]
seed-paths: ["seeds"]

models:
  hello_orders:
    staging:
      +materialized: view
    marts:
      +materialized: table
```

Create `examples/hello-orders/seeds/orders.csv`:

```csv
order_id,customer_id,order_date,order_total
1001,C001,2026-04-01,42.50
1002,C002,2026-04-01,18.25
1003,C001,2026-04-02,64.00
```

- [ ] **Step 4: Create the dbt models and tests**

Create `examples/hello-orders/models/staging/stg_orders.sql`:

```sql
select
    cast(order_id as integer) as order_id,
    cast(customer_id as varchar) as customer_id,
    cast(order_date as date) as order_date,
    cast(order_total as decimal(18, 2)) as order_total
from {{ ref('orders') }}
```

Create `examples/hello-orders/models/marts/mart_daily_orders.sql`:

```sql
select
    order_date,
    count(*) as order_count,
    sum(order_total) as total_order_value
from {{ ref('stg_orders') }}
group by order_date
```

Create `examples/hello-orders/models/schema.yml`:

```yaml
version: 2

seeds:
  - name: orders
    description: Small source dataset for the hello-orders data product.
    columns:
      - name: order_id
        tests:
          - not_null
          - unique
      - name: customer_id
        tests:
          - not_null
      - name: order_total
        tests:
          - not_null

models:
  - name: stg_orders
    description: Typed order records.
    columns:
      - name: order_id
        tests:
          - not_null
          - unique
      - name: customer_id
        tests:
          - not_null
  - name: mart_daily_orders
    description: Daily order metrics for the hello-orders data product.
    columns:
      - name: order_date
        tests:
          - not_null
          - unique
      - name: order_count
        tests:
          - not_null
      - name: total_order_value
        tests:
          - not_null
```

- [ ] **Step 5: Validate example files are parseable**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
import csv
import yaml

for path in [
    Path("examples/platform-environment-contracts/dev.yaml"),
    Path("examples/hello-orders/floe.yaml"),
    Path("examples/hello-orders/dbt_project.yml"),
    Path("examples/hello-orders/models/schema.yml"),
]:
    yaml.safe_load(path.read_text())

with Path("examples/hello-orders/seeds/orders.csv").open(newline="") as handle:
    rows = list(csv.DictReader(handle))
assert len(rows) == 3
assert rows[0]["order_id"] == "1001"
PY
```

Expected: command exits with status `0`.

- [ ] **Step 6: Commit**

```bash
git add examples/platform-environment-contracts examples/hello-orders
git commit -m "docs: add enterprise onboarding examples"
```

## Task 3: Publish Operating Model And Runtime Artifact Docs

**Files:**
- Create: `docs/guides/operating-model.md`
- Create: `docs/platform-engineers/platform-environment-contract.md`
- Create: `docs/guides/deployment/data-product-runtime-artifacts.md`
- Modify: `docs-site/docs-manifest.json`
- Modify: `docs/index.md`

- [ ] **Step 1: Add the operating model page**

Create `docs/guides/operating-model.md` with these sections:

```markdown
# Recommended Enterprise Operating Model

Floe fits into an enterprise delivery system. It does not replace your source control, CI/CD, artifact registry, release approvals, identity provider, service catalog, or GitOps controller.

## Roles

| Role | Owns | Does Not Own |
| --- | --- | --- |
| Platform Engineer | Platform environments, manifests, plugin defaults, service health, access boundaries, environment contracts | Product SQL logic and product business tests |
| Data Engineer | `floe.yaml`, dbt models, product tests, product contracts, product run validation | Platform service credentials, cluster-wide policy, production access bypasses |
| Governance, Security, Release | Approval rules, exception handling, evidence requirements, production controls | Day-to-day product modeling |

## Recommended Flow

1. Platform Engineer publishes a Platform Environment Contract.
2. Data Engineer creates a product repo and targets that contract.
3. Pull request runs dbt checks, Floe compilation, policy checks, and docs/artifact validation.
4. CI builds a runtime artifact, usually a container image for the alpha Dagster path.
5. CI publishes the artifact to the organization registry.
6. Approval happens through the organization's release process.
7. Deployment happens through GitOps, CI deployment, service catalog, or a release train.
8. Dagster or the selected runtime launches Kubernetes work.
9. OpenLineage and OpenTelemetry evidence proves what ran.
10. Data Engineer validates business outputs and escalates platform failures with evidence.

## What Floe Standardizes

- Platform and data product configuration contracts.
- Compile-time validation.
- Runtime artifact contract.
- Policy and data contract evidence.
- OpenLineage and OpenTelemetry expectations.
- Kubernetes-native execution model.

## What Your Organization Supplies

- Git provider and repository rules.
- CI/CD runner and approval gates.
- Container and artifact registry.
- Production deployment mechanism.
- Identity, secrets, ingress, TLS, backup, and audit controls.

## Alpha Posture

The recommended alpha runtime spine is Dagster because the Customer 360 release-validation path proves that shape today. `floe-jobs` is an implemented lower-level Helm primitive for Kubernetes Jobs and CronJobs, but it is not yet the primary self-service product deployment workflow.
```

- [ ] **Step 2: Add the Platform Environment Contract page**

Create `docs/platform-engineers/platform-environment-contract.md` with these sections:

```markdown
# Platform Environment Contract

A Platform Environment Contract is the stable handoff between Platform Engineers, Data Engineers, CI, and release workflows.

It replaces informal endpoint sharing. Data Engineers should not need a Slack message with service URLs and hidden assumptions. They need a documented contract that says which environment exists, which platform manifest it uses, what is approved, how artifacts are named, which evidence is required, and where to escalate.

## Reference Example

See [`examples/platform-environment-contracts/dev.yaml`](https://github.com/Obsidian-Owl/floe/blob/main/examples/platform-environment-contracts/dev.yaml).

## Minimum Contents

- Environment name and Kubernetes namespace.
- Platform manifest path or OCI reference.
- Approved plugin selections and defaults.
- Approved per-transform compute choices.
- Runtime spine and artifact registry convention.
- Service account, RBAC, namespace, and secret-reference rules.
- Dagster, Marquez, Jaeger, storage, and query access URLs where appropriate.
- Required validation and promotion evidence.
- Support and escalation path.

## How Data Engineers Use It

Data Engineers use the contract to configure `platform` references, choose approved compute where allowed, understand validation expectations, and know where CI will publish runtime artifacts. The contract should be versioned with the platform environment or published from the platform repository.

## What Not To Put In It

- Raw secrets.
- Personal access tokens.
- One-off workstation paths.
- Unapproved compute accounts.
- Cloud-provider assumptions that are not true for the environment.
```

- [ ] **Step 3: Add runtime artifact and deployment handoff docs**

Create `docs/guides/deployment/data-product-runtime-artifacts.md` with these sections:

```markdown
# Data Product Runtime Artifacts

Floe's alpha data product deployment path should be understood as an artifact flow.

## Recommended Alpha Shape

1. Data product source lives in a product repository.
2. CI runs dbt checks and `uv run floe platform compile --spec <product>/floe.yaml --manifest <platform>/manifest.yaml --output <target>/compiled_artifacts.json --generate-definitions`.
3. CI builds a product runtime image containing product code, dbt files, compiled artifacts, and Dagster definitions.
4. CI publishes the image to the organization registry.
5. The organization deployment path updates the Dagster code location or release values to use that image.
6. Dagster launches Kubernetes work and emits OpenLineage and OpenTelemetry evidence.

## Handoff Patterns

| Pattern | Use When | Floe Contract |
| --- | --- | --- |
| GitOps PR | Platform changes are deployed from a GitOps repo | CI proposes image tag and values changes |
| CI deploy job | Your release workflow can deploy after approval | CI deploys the image and records evidence |
| Service catalog request | Platform team owns production deployment | CI publishes artifact metadata and requests deployment |
| Release train | Production changes move in scheduled batches | Artifact digest and evidence are promoted together |

## Lower-Level Primitive: floe-jobs

`charts/floe-jobs` can render Kubernetes Jobs and CronJobs for dbt, dlt, and custom workloads. Use it when your Platform Engineer has approved that pattern. Do not treat it as the default self-service alpha story until a complete product workflow is documented and validated.
```

- [ ] **Step 4: Add the pages to Starlight navigation**

Update `docs-site/docs-manifest.json`:

```json
{
  "title": "Operating Model",
  "source": "docs/guides/operating-model.md",
  "slug": "guides/operating-model"
}
```

Add that item under the `Home` or `Platform Engineers` section. Add this item under `Platform Engineers`:

```json
{
  "title": "Platform Environment Contract",
  "source": "docs/platform-engineers/platform-environment-contract.md",
  "slug": "platform-engineers/platform-environment-contract"
}
```

Add this item under `Platform Engineers` or `Data Engineers` deployment references:

```json
{
  "title": "Data Product Runtime Artifacts",
  "source": "docs/guides/deployment/data-product-runtime-artifacts.md",
  "slug": "guides/deployment/data-product-runtime-artifacts"
}
```

- [ ] **Step 5: Update docs landing page**

In `docs/index.md`, change the Data Engineer outcome from Customer 360 to hello-orders:

```markdown
| Data Engineer | [Build your first data product](./data-engineers/first-data-product.md) | A minimal `hello-orders` data product built from source and ready for governed runtime packaging |
```

Add this bullet under Start Here:

```markdown
- [Recommended Enterprise Operating Model](./guides/operating-model.md) explains how Floe fits into source control, CI/CD, artifact registries, approvals, and deployment systems.
```

- [ ] **Step 6: Commit**

```bash
git add docs/guides/operating-model.md docs/platform-engineers/platform-environment-contract.md docs/guides/deployment/data-product-runtime-artifacts.md docs-site/docs-manifest.json docs/index.md
git commit -m "docs: publish enterprise operating model"
```

## Task 4: Rewrite Platform Engineer Journey

**Files:**
- Modify: `docs/platform-engineers/index.md`
- Modify: `docs/platform-engineers/first-platform.md`
- Modify: `docs/platform-engineers/validate-platform.md`

- [ ] **Step 1: Update Platform Engineer landing page**

Replace the `Start Here` list in `docs/platform-engineers/index.md` with:

```markdown
1. [Read the enterprise operating model](../guides/operating-model.md).
2. [Deploy your first platform](first-platform.md).
3. [Publish a Platform Environment Contract](platform-environment-contract.md).
4. [Validate your platform](validate-platform.md).
5. [Run Customer 360](../demo/customer-360.md) as the advanced end-to-end proof.
```

Add this paragraph after `What You Own`:

```markdown
Your primary handoff to Data Engineers is a Platform Environment Contract. It should be versioned, reviewable, and usable by humans and CI. Avoid one-off endpoint handoffs that cannot be audited or reproduced.
```

- [ ] **Step 2: Rewrite the first-platform guide around platform setup and contract publication**

In `docs/platform-engineers/first-platform.md`, keep the provider-neutral Kubernetes prerequisite section and replace the numbered flow with:

````markdown
## 1. Choose Your Environment

Use any Kubernetes cluster where you can install Helm charts and create the Floe namespace. Kind is suitable for evaluation. Managed Kubernetes is suitable when your organization supplies durable storage, ingress, TLS, identity, backup, and operational controls.

## 2. Render The Platform

```bash
helm dependency update ./charts/floe-platform
helm template floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace \
  >/tmp/floe-platform-rendered.yaml
```

## 3. Install The Platform

```bash
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

## 4. Wait For Services

```bash
kubectl get pods -n floe-dev
kubectl wait --for=condition=Ready pods --all -n floe-dev --timeout=10m
```

## 5. Publish The Environment Contract

Start from `examples/platform-environment-contracts/dev.yaml` and replace namespace, release name, registry, access, and URL values for your environment.

## 6. Validate The Platform

Continue with [Validate Your Platform](validate-platform.md).

## 7. Prove The Full Demo

Run [Customer 360](../demo/customer-360.md) after the basic platform and environment contract are validated.
````

- [ ] **Step 3: Replace endpoint handoff with contract-based evidence**

In `docs/platform-engineers/validate-platform.md`, replace `What To Hand To Data Engineers` with:

```markdown
## Publish The Contract, Not A Chat Message

Publish the Platform Environment Contract after validation. At minimum it should include:

- Namespace and release name.
- Platform manifest reference.
- Approved plugins and compute choices.
- Runtime artifact registry convention.
- Dagster, Marquez, Jaeger, storage, and semantic/query service access patterns.
- Required promotion evidence.
- Support path.

Use [`examples/platform-environment-contracts/dev.yaml`](https://github.com/Obsidian-Owl/floe/blob/main/examples/platform-environment-contracts/dev.yaml) as the reference shape.
```

Add this expected evidence list:

```markdown
## Platform Evidence

- Helm release is deployed.
- Dagster UI is reachable.
- Polaris catalog API is reachable.
- MinIO or configured object storage is reachable.
- Marquez API is reachable.
- Jaeger UI or configured trace backend is reachable.
- OTel collector is accepting traces.
- Data product runtime artifact path is defined.
```

- [ ] **Step 4: Run source docs check**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: no source-doc errors from Platform Engineer pages.

- [ ] **Step 5: Commit**

```bash
git add docs/platform-engineers/index.md docs/platform-engineers/first-platform.md docs/platform-engineers/validate-platform.md
git commit -m "docs: rewrite platform engineer onboarding"
```

## Task 5: Rewrite Data Engineer Journey Around hello-orders

**Files:**
- Modify: `docs/data-engineers/index.md`
- Modify: `docs/data-engineers/first-data-product.md`
- Modify: `docs/data-engineers/validate-data-product.md`

- [ ] **Step 1: Update Data Engineer landing page**

In `docs/data-engineers/index.md`, replace the `Start Here` list with:

```markdown
1. [Build your first data product](first-data-product.md) with `hello-orders`.
2. [Validate your data product](validate-data-product.md).
3. [Review runtime artifact and deployment handoff patterns](../guides/deployment/data-product-runtime-artifacts.md).
4. [Run the Customer 360 demo](../demo/customer-360.md) as the advanced proof.
5. [Review the floe.yaml schema](../reference/floe-yaml-schema.md).
```

Add this paragraph:

```markdown
Data Engineers target a Platform Environment Contract from the Platform Engineer. You own product source, tests, schedules, metadata, and validation. Platform Engineers own the platform manifest, service access, secrets, and production deployment boundaries.
```

- [ ] **Step 2: Rewrite first-data-product as a hello-orders build guide**

Replace the body of `docs/data-engineers/first-data-product.md` with a guide that includes these sections in this order:

````markdown
# Build Your First Data Product

This guide builds `hello-orders`, a minimal data product with one seed, one staging model, one mart, and dbt tests. Customer 360 is the advanced demo after you understand this path.

## Prerequisites

- A Platform Environment Contract from your Platform Engineer.
- A Floe platform installed and validated by a Platform Engineer.
- A repository checkout with the `examples/hello-orders` project.
- `uv`, Python, and the repository development dependencies installed for the alpha docs path.

## 1. Inspect The Environment Contract

```bash
sed -n '1,220p' examples/platform-environment-contracts/dev.yaml
```

## 2. Inspect The Data Product

```bash
find examples/hello-orders -maxdepth 3 -type f | sort
sed -n '1,180p' examples/hello-orders/floe.yaml
```

## 3. Review The dbt Models

```bash
sed -n '1,120p' examples/hello-orders/models/staging/stg_orders.sql
sed -n '1,120p' examples/hello-orders/models/marts/mart_daily_orders.sql
sed -n '1,180p' examples/hello-orders/models/schema.yml
```

## 4. Compile The Product For The Alpha Runtime Contract

```bash
uv run floe platform compile \
  --spec examples/hello-orders/floe.yaml \
  --manifest demo/manifest.yaml \
  --output target/hello-orders/compiled_artifacts.json \
  --generate-definitions
```

The root `floe compile`, `floe run`, and `floe product deploy` commands are planned product lifecycle entry points. They are not the current alpha path.

## 5. Package A Runtime Artifact

For the alpha path, CI should build a product runtime image that contains:

- dbt project files.
- `compiled_artifacts.json`.
- generated Dagster definitions.
- runtime dependencies pinned by the repository lockfile or organization base image.

## 6. Deploy Through Your Organization's Approved Path

Use the handoff pattern documented in [Data Product Runtime Artifacts](../guides/deployment/data-product-runtime-artifacts.md). Floe does not mandate GitHub, GitLab, Jenkins, Argo CD, Flux, Backstage, or a specific registry.

## 7. Validate The Product

Continue with [Validate Your Data Product](validate-data-product.md).

## 8. Then Run Customer 360

After `hello-orders`, use [Customer 360](../demo/customer-360.md) to prove the full business demo and release-validation path.
````

- [ ] **Step 3: Rewrite validation around product evidence and escalation**

Replace Customer 360-specific claims in `docs/data-engineers/validate-data-product.md` with:

```markdown
# Validate Your Data Product

Use this guide after your product runtime artifact has been deployed through the organization-approved path.

## Business Output Evidence

For `hello-orders`, pass criteria are:

- The `mart_daily_orders` output exists.
- `order_count` is greater than zero for at least one day.
- `total_order_value` is positive for at least one day.

## Runtime Evidence

- Dagster shows the latest product run succeeded.
- The run used the expected product image or code location.
- The run read the compiled artifacts generated for the product version.

## Lineage And Telemetry Evidence

- Marquez shows the product job and output dataset.
- Jaeger or your configured trace backend shows traces for the product run.
- OpenLineage and OpenTelemetry evidence use the platform namespace and product name from compiled artifacts.

## Escalation Boundary

Escalate to the Platform Engineer when multiple products fail the same platform service, when a service URL in the Platform Environment Contract is unreachable, or when the runtime cannot access approved secrets. Keep product model failures, dbt test failures, and invalid `floe.yaml` changes within the data product team first.
```

- [ ] **Step 4: Run source docs check**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: no source-doc errors from Data Engineer pages.

- [ ] **Step 5: Commit**

```bash
git add docs/data-engineers/index.md docs/data-engineers/first-data-product.md docs/data-engineers/validate-data-product.md
git commit -m "docs: rewrite data engineer onboarding"
```

## Task 6: Correct Architecture, Reference, Demo, And README Claims

**Files:**
- Modify: `docs/architecture/opinionation-boundaries.md`
- Modify: `docs/reference/plugin-catalog.md`
- Modify: `docs/architecture/capability-status.md`
- Modify: `docs/demo/customer-360.md`
- Modify: `README.md`

- [ ] **Step 1: Correct opinionation boundaries**

In `docs/architecture/opinionation-boundaries.md`, replace the pluggable component table with:

```markdown
| Component | Alpha-Supported Default | Implemented Alternatives | Planned Or Ecosystem Examples |
| --- | --- | --- | --- |
| Compute | DuckDB | None validated as an alpha product path | Spark, Snowflake, Databricks, BigQuery, Redshift |
| Orchestration | Dagster | None validated as an alpha product path | Airflow 3.x, Prefect, Argo Workflows |
| Catalog | Polaris | None validated as an alpha product path | AWS Glue, Hive Metastore, Nessie |
| Storage | S3-compatible object storage through the implemented storage plugin; demo uses MinIO | S3-compatible backends where configured and validated by the platform team | GCS, Azure Blob, provider-native object storage |
| Telemetry Backend | Jaeger and console telemetry plugins | OTLP-compatible backends through standard OpenTelemetry configuration | Datadog, Grafana Cloud, AWS X-Ray |
| Lineage Backend | Marquez | None validated as an alpha product path | Atlan, OpenMetadata, Egeria |
| dbt Runtime | dbt Core | dbt Fusion plugin exists as an implementation path requiring explicit validation | dbt Cloud |
| Semantic Layer | Cube reference implementation | None validated as an alpha product path | dbt Semantic Layer |
| Ingestion | dlt plugin primitive | None validated as a full product path | Airbyte-style integrations |
| Data Quality Framework | dbt expectations and Great Expectations plugin primitives | None validated as a full product path | Soda, custom |
| Secrets | Kubernetes Secrets and Infisical plugin primitives | None validated as a full product path | Vault, External Secrets Operator |
```

Replace the compute anti-pattern section with:

````markdown
### DO: Allow Approved Per-Transform Compute Selection

Platform Engineers approve compute targets and choose defaults. Data Engineers may select compute per transform only from that approved list.

```yaml
plugins:
  compute:
    approved:
      - name: duckdb
      - name: spark
    default: duckdb
```

```yaml
transforms:
  - type: dbt
    path: models/staging
    compute: spark
  - type: dbt
    path: models/marts
    compute: duckdb
```

### DON'T: Use Unapproved Compute

```yaml
transforms:
  - type: dbt
    path: models/marts
    compute: unapproved-snowflake-account
```

### DON'T: Create Per-Environment Compute Drift

```yaml
environments:
  development:
    compute: duckdb
  production:
    compute: snowflake
```
````

- [ ] **Step 2: Tighten plugin catalog wording**

In `docs/reference/plugin-catalog.md`, change broad current status phrases:

```markdown
| `STORAGE` | `floe.storage` | S3-compatible storage plugin; demo uses MinIO-compatible object storage. | Platform team selects; storage plugin owns object-store access. |
| `TELEMETRY_BACKEND` | `floe.telemetry_backends` | Jaeger and console telemetry plugins. | Platform team selects; OpenTelemetry owns trace semantics. |
| `LINEAGE_BACKEND` | `floe.lineage_backends` | Marquez lineage backend plugin. | Platform team selects; OpenLineage owns lineage semantics. |
| `INGESTION` | `floe.ingestion` | dlt plugin primitive. | Data product team configures sources within platform-approved plugins. |
| `QUALITY` | `floe.quality` | dbt expectations and Great Expectations plugin primitives. | Platform team sets standards; data products attach checks. |
```

- [ ] **Step 3: Update capability status**

Add these bullets under `Alpha-Supported` in `docs/architecture/capability-status.md`:

```markdown
- Dagster-centered runtime artifact pattern for the documented alpha path.
- Platform Environment Contract as the recommended documentation and CI handoff model.
```

Add these bullets under `Implemented Primitives`:

```markdown
- `charts/floe-jobs` as a lower-level Kubernetes Job and CronJob chart.
- `examples/hello-orders` as a first-use source example.
```

Add these bullets under `Planned Or Not Yet Alpha-Supported`:

```markdown
- Root data-team lifecycle commands as packaged product workflow: `floe compile`, `floe run`, and `floe product deploy`.
- Self-service product deployment through `floe-jobs` without Platform Engineer-approved workflow design.
```

- [ ] **Step 4: Reposition Customer 360 as advanced proof**

In `docs/demo/customer-360.md`, add this note after the opening paragraph:

```markdown
If you are learning Floe for the first time, start with [Build Your First Data Product](../data-engineers/first-data-product.md). Customer 360 is the advanced proof that demonstrates the full platform, runtime, lineage, telemetry, storage, and business-output path.
```

- [ ] **Step 5: Align README claims**

In `README.md`, change unsupported current plugin examples so Datadog and Atlan are described as planned or ecosystem examples, not current defaults. Keep the approved per-transform compute example, but add this caveat immediately before it:

```markdown
The alpha-supported runtime path is documented in the Floe docs. Some plugin examples below describe the target architecture or ecosystem integrations and are labeled as such in the documentation.
```

- [ ] **Step 6: Run source docs check**

Run:

```bash
cd docs-site
npm run check:source
```

Expected: no source-doc errors from architecture, reference, demo, or README pages.

- [ ] **Step 7: Commit**

```bash
git add docs/architecture/opinionation-boundaries.md docs/reference/plugin-catalog.md docs/architecture/capability-status.md docs/demo/customer-360.md README.md
git commit -m "docs: correct product capability claims"
```

## Task 7: Validate Published Docs End To End

**Files:**
- Validate generated docs under `docs-site/src/content/docs/`
- Validate source docs under `docs/`

- [ ] **Step 1: Run full docs validation**

Run:

```bash
cd docs-site
npm run validate
```

Expected:

- `node --test scripts/*.test.mjs` passes.
- `npm run check:source` passes.
- Starlight build completes.
- `npm run check:dist` passes.

- [ ] **Step 2: Inspect generated Starlight pages for first-use flow**

Run:

```bash
rg -n "hello-orders|Platform Environment Contract|Customer 360 is the advanced proof|Datadog \\(production\\)|Atlan \\(production\\)|DON'?T: Allow Data Engineers to select compute|floe product deploy" docs-site/src/content/docs
```

Expected:

- `hello-orders` appears in Data Engineer pages.
- `Platform Environment Contract` appears in Platform Engineer and operating-model pages.
- `Customer 360 is the advanced proof` appears where Customer 360 is referenced from first-use docs.
- No generated page contains `Datadog (production)`, `Atlan (production)`, `DON'T: Allow Data Engineers to select compute`, or uncaveated `floe product deploy`.

- [ ] **Step 3: Run repository docs targets**

Run:

```bash
make docs-check
```

Expected: repository docs target passes. If `make docs-check` is not defined, run `make help | sed -n '1,120p'` and use the documented docs validation target instead.

- [ ] **Step 4: Check final worktree state**

Run:

```bash
git status --short
git log --oneline -n 8
```

Expected: only intentional generated docs artifacts are dirty, or the worktree is clean if generated docs are ignored. Recent commits should show one commit per task.

- [ ] **Step 5: Commit final generated or validation-related changes if required**

If `docs-site/src/content/docs/` contains tracked generated output, commit it:

```bash
git add docs-site/src/content/docs
git commit -m "docs: sync enterprise docs site"
```

If generated output is ignored and no files remain dirty, skip this commit.

## Self-Review Checklist

- Every design-spec goal maps to a task:
  - Enterprise operating model: Task 3.
  - Platform Environment Contract: Tasks 2, 3, and 4.
  - Dagster alpha runtime spine: Tasks 3, 5, and 6.
  - `floe-jobs` as lower-level primitive: Tasks 3 and 6.
  - Correct opinionation boundaries and compute policy: Tasks 1 and 6.
  - First-use guides use hello-orders instead of Customer 360: Tasks 2, 5, and 6.
  - Guardrails against drift: Tasks 1 and 7.
- Public docs do not require DevPod or Hetzner for product users.
- Public docs do not claim packaged `floe compile`, `floe run`, or `floe product deploy` as the current alpha product path.
- Current examples use concrete files, not imaginary snippets.
- Customer 360 remains documented as advanced proof and release validation.
