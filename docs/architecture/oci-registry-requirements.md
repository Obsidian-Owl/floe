# OCI Registry Requirements

This document describes the requirements and configuration for OCI registries used to store floe platform artifacts.

## Overview

floe stores platform configuration as OCI artifacts in container registries:

```
oci://registry.example.com/
├── floe-platform:v1.2.3           # Platform configuration artifacts
├── floe-platform-chart:v1.2.3     # Helm chart for platform deployment
└── plugins/
    ├── floe-dagster-chart:v1.0.0  # Plugin charts
    └── floe-cube-chart:v1.0.0
```

**Why OCI Registry?**
- Immutable, versioned storage (same as container images)
- Universal availability (every cloud has a registry)
- Native support in Helm 3.8+ for chart storage
- Content-addressable (SHA256 digests ensure integrity)
- Supports signing (cosign/sigstore)

## Supported Registries

| Registry | OCI Artifacts | Cosign Signing | Auth Method | Notes |
|----------|---------------|----------------|-------------|-------|
| **Amazon ECR** | Yes | Yes | IRSA / IAM | Recommended for AWS |
| **Azure Container Registry** | Yes | Yes | Managed Identity / SP | Recommended for Azure |
| **Google Artifact Registry** | Yes | Yes | Workload Identity / SA | Recommended for GCP |
| **GitHub Container Registry** | Yes | Yes | PAT / GITHUB_TOKEN | Good for open source |
| **Harbor** | Yes | Yes | LDAP / OIDC / Basic | Air-gapped ready |
| **Docker Hub** | Limited | Yes | PAT | Rate limits, not recommended |

### Amazon ECR

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe
    auth:
      type: aws-irsa  # Uses pod service account
```

**ECR Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:us-east-1:123456789:repository/floe/*"
    },
    {
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    }
  ]
}
```

### Azure Container Registry

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://myregistry.azurecr.io/floe
    auth:
      type: azure-managed-identity
```

### Google Artifact Registry

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://us-central1-docker.pkg.dev/my-project/floe
    auth:
      type: gcp-workload-identity
```

### GitHub Container Registry

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://ghcr.io/my-org/floe
    auth:
      type: token
      token_ref: ghcr-token  # K8s Secret reference
```

### Harbor (Air-Gapped)

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://harbor.internal.company.com/floe
    auth:
      type: basic
      username_ref: harbor-credentials
      password_ref: harbor-credentials
    tls:
      insecure_skip_verify: false
      ca_cert_ref: harbor-ca-cert  # Custom CA certificate
```

## Image Signing

floe supports artifact signing via [cosign](https://github.com/sigstore/cosign) for supply chain security.

### Signing Configuration

Signature verification is **configurable per environment**:

```yaml
# manifest.yaml
artifacts:
  signing:
    enabled: true
    enforcement: warn | enforce | off
    # warn: Log warning but allow unsigned artifacts
    # enforce: Reject unsigned artifacts
    # off: No verification (development only)
```

### Keyless Signing (Recommended for CI/CD)

Use OIDC-based keyless signing in GitHub Actions:

```yaml
# .github/workflows/publish.yml
- name: Install cosign
  uses: sigstore/cosign-installer@v3

- name: Login to registry
  run: echo "${{ secrets.REGISTRY_TOKEN }}" | helm registry login ghcr.io -u ${{ github.actor }} --password-stdin

- name: Publish and sign
  env:
    COSIGN_EXPERIMENTAL: "true"  # Enable keyless signing
  run: |
    floe platform compile
    floe platform publish v${{ github.run_number }}
    # Automatic signing with GitHub OIDC identity
```

### Key-Based Signing

For environments without OIDC, use key-based signing:

```bash
# Generate key pair (one-time)
cosign generate-key-pair

# Sign during publish
floe platform publish v1.2.3 --sign --key cosign.key

# Verify during pull
floe init --platform=v1.2.3 --verify --key cosign.pub
```

### Verification Workflow

```
┌─────────────────┐     1. Pull artifact     ┌─────────────────┐
│   floe init     │ ◄────────────────────────│   OCI Registry  │
└────────┬────────┘                          └─────────────────┘
         │
         │ 2. Check signature (if enforcement enabled)
         ▼
┌─────────────────┐     3. Verify signature  ┌─────────────────┐
│  Local verify   │ ◄────────────────────────│   Rekor (log)   │
└────────┬────────┘                          └─────────────────┘
         │
         │ 4. Signature valid? Continue or reject
         ▼
┌─────────────────┐
│ Deploy platform │
└─────────────────┘
```

## Air-Gapped Deployments

For environments without internet access, use bundle export/import:

### Export (Connected Environment)

```bash
# Export platform artifacts to tarball
floe platform export \
  --version=v1.2.3 \
  --output=platform-v1.2.3.tar \
  --include-charts \
  --include-signatures
```

### Transfer

Transfer `platform-v1.2.3.tar` to air-gapped environment via approved media.

### Import (Air-Gapped Environment)

```bash
# Import to internal Harbor registry
floe platform import \
  --bundle=platform-v1.2.3.tar \
  --registry=oci://harbor.internal/floe

# Verify import
floe platform list --registry=oci://harbor.internal/floe
```

### Use Imported Artifacts

```yaml
# floe.yaml (in air-gapped environment)
platform:
  ref: oci://harbor.internal/floe/platform:v1.2.3
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Publish Platform
on:
  push:
    tags: ['v*']

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write  # For keyless signing
    steps:
      - uses: actions/checkout@v4

      - name: Install floe CLI
        run: pip install floe-cli

      - name: Login to GHCR
        run: echo "${{ secrets.GITHUB_TOKEN }}" | helm registry login ghcr.io -u ${{ github.actor }} --password-stdin

      - name: Compile and publish
        env:
          COSIGN_EXPERIMENTAL: "true"
        run: |
          floe platform compile
          floe platform publish ${{ github.ref_name }}
```

### GitLab CI

```yaml
publish:
  stage: deploy
  image: python:3.11
  script:
    - pip install floe-cli
    - echo "$CI_REGISTRY_PASSWORD" | helm registry login $CI_REGISTRY -u $CI_REGISTRY_USER --password-stdin
    - floe platform compile
    - floe platform publish $CI_COMMIT_TAG
  only:
    - tags
```

## Resilience and Retry Strategy

Registry unavailability can block platform deployments and compilations. This section defines the resilience strategy.

### Retry Policy

All OCI operations use exponential backoff with jitter:

```yaml
# manifest.yaml
artifacts:
  registry:
    uri: oci://ghcr.io/my-org/floe
    resilience:
      retry:
        max_attempts: 3
        initial_delay_ms: 1000
        max_delay_ms: 30000
        backoff_multiplier: 2.0
        jitter: 0.1  # 10% jitter
```

**Retry Behavior:**

| Attempt | Delay (with jitter) | Total Wait |
|---------|---------------------|------------|
| 1 | ~1s | 1s |
| 2 | ~2s | 3s |
| 3 | ~4s | 7s |
| Fail | - | 7s total |

### Timeout Configuration

```yaml
artifacts:
  registry:
    resilience:
      timeouts:
        connect_ms: 5000      # TCP connection timeout
        read_ms: 30000        # Read timeout per chunk
        total_ms: 300000      # Total operation timeout (5 min)
```

### Circuit Breaker

Prevents cascading failures when registry is unavailable:

```yaml
artifacts:
  registry:
    resilience:
      circuit_breaker:
        enabled: true
        failure_threshold: 5         # Open after 5 consecutive failures
        success_threshold: 2         # Close after 2 consecutive successes
        half_open_timeout_ms: 60000  # Try again after 60s
```

**Circuit Breaker States:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CIRCUIT BREAKER STATES                               │
│                                                                              │
│    ┌──────────┐    5 failures     ┌──────────┐    60s timeout   ┌─────────┐│
│    │  CLOSED  │ ────────────────► │   OPEN   │ ───────────────► │HALF-OPEN││
│    │ (normal) │                   │ (reject) │                  │ (probe) ││
│    └────┬─────┘                   └──────────┘                  └────┬────┘│
│         │                              ▲                             │      │
│         │                              │ failure                     │      │
│         │                              └─────────────────────────────┘      │
│         │                                                            │      │
│         │ 2 successes                                     success    │      │
│         └◄───────────────────────────────────────────────────────────┘      │
│                                                                              │
│  CLOSED: All requests pass through, failures counted                        │
│  OPEN: All requests fail-fast with cached error                             │
│  HALF-OPEN: One request allowed to probe, result determines next state     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Failure Handling for Multi-Artifact Pulls

When pulling multiple artifacts (e.g., platform manifest + charts), failures are handled as follows:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MULTI-ARTIFACT PULL FLOW                                                    │
│                                                                              │
│  ┌────────────┐                                                             │
│  │ Pull Start │                                                             │
│  └─────┬──────┘                                                             │
│        │                                                                    │
│        ▼                                                                    │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐            │
│  │ 1. Pull        │───►│ 2. Pull        │───►│ 3. Pull        │            │
│  │    Manifest    │    │    Chart       │    │    Plugins     │            │
│  └───────┬────────┘    └───────┬────────┘    └───────┬────────┘            │
│          │                     │                     │                      │
│          ▼                     ▼                     ▼                      │
│      ┌───────┐             ┌───────┐             ┌───────┐                 │
│      │Success│             │ Fail  │             │  N/A  │                 │
│      └───────┘             └───┬───┘             └───────┘                 │
│                                │                                            │
│                                ▼                                            │
│                          ┌──────────┐                                       │
│                          │  Retry   │                                       │
│                          │ (3 tries)│                                       │
│                          └────┬─────┘                                       │
│                               │                                             │
│              ┌────────────────┼────────────────┐                           │
│              ▼                                 ▼                            │
│         ┌─────────┐                       ┌─────────┐                       │
│         │ Success │                       │  Fail   │                       │
│         │Continue │                       │ Rollback│                       │
│         └─────────┘                       └────┬────┘                       │
│                                                │                            │
│                                                ▼                            │
│                                          ┌──────────────┐                   │
│                                          │Clean up Step 1│                   │
│                                          │(remove pulled)│                   │
│                                          └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Partial Failure Behavior:**
- If any artifact fails after retries, rollback all previously pulled artifacts
- No partial state left behind
- User sees consolidated error with all attempted operations

### Caching Strategy

To reduce registry load and improve resilience:

```yaml
artifacts:
  registry:
    cache:
      enabled: true
      local_path: /var/cache/floe/oci
      ttl_hours: 24          # Time-to-live for cached artifacts
      max_size_gb: 10        # Max cache size
      immutable_tags: true   # v1.2.3 tags never re-fetched
```

**Cache Behavior:**

| Tag Type | Cache Behavior | Rationale |
|----------|----------------|-----------|
| Semver (`v1.2.3`) | Immutable, never re-fetch | Semantic versions are immutable |
| Latest (`latest`) | TTL-based, re-fetch after expiry | Mutable tags |
| SHA (`sha256:abc`) | Immutable, never re-fetch | Content-addressable |

### Rate Limit Handling

For registries with rate limits (Docker Hub, some GCR tiers):

```yaml
artifacts:
  registry:
    rate_limiting:
      respect_retry_after: true   # Honor Retry-After header
      max_requests_per_minute: 50 # Self-imposed limit
      quota_buffer_percent: 20    # Reserve 20% of quota
```

**Rate Limit Response:**

| HTTP Status | Action |
|-------------|--------|
| 429 Too Many Requests | Wait for Retry-After, then retry |
| 503 Service Unavailable | Exponential backoff retry |
| Quota exceeded | Fail with clear error, log quota state |

### Monitoring

OCI registry operations emit the following metrics:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `floe_oci_pull_duration_seconds` | Histogram | registry, artifact | Pull operation duration |
| `floe_oci_pull_total` | Counter | registry, status | Total pull attempts |
| `floe_oci_circuit_breaker_state` | Gauge | registry | 0=closed, 1=open, 2=half-open |
| `floe_oci_cache_hits_total` | Counter | registry | Cache hit count |
| `floe_oci_cache_misses_total` | Counter | registry | Cache miss count |

**Alert Rules:**

```yaml
groups:
  - name: oci-registry
    rules:
      - alert: OCIRegistryUnavailable
        expr: floe_oci_circuit_breaker_state == 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "OCI registry circuit breaker is open"

      - alert: OCIRegistrySlowPulls
        expr: histogram_quantile(0.99, floe_oci_pull_duration_seconds) > 30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "OCI registry pulls are slow (p99 > 30s)"
```

---

## Rate Limiting and Caching

### Docker Hub Limits

Docker Hub has rate limits (100 pulls/6 hours for anonymous). **Not recommended for production.**

### Pull-Through Cache

Configure registry mirror for rate-limited or slow registries:

```yaml
# manifest.yaml (optional)
artifacts:
  registry:
    uri: oci://ghcr.io/my-org/floe
    cache:
      enabled: true
      mirror: oci://harbor.internal/cache/ghcr.io
```

### Helm OCI Cache

Helm 3.8+ caches OCI artifacts locally:

```bash
# Cache location
~/.cache/helm/registry/

# Clear cache
helm registry logout ghcr.io
rm -rf ~/.cache/helm/registry/ghcr.io
```

## Configuration Schema

```yaml
# Full artifacts configuration schema
artifacts:
  registry:
    uri: string  # OCI registry URI (oci://...)
    auth:
      type: aws-irsa | azure-managed-identity | gcp-workload-identity | token | basic
      # Token-based
      token_ref: string  # K8s Secret reference
      # Basic auth
      username_ref: string
      password_ref: string
    tls:
      insecure_skip_verify: boolean  # Skip TLS verification (not recommended)
      ca_cert_ref: string  # Custom CA certificate Secret reference
    cache:
      enabled: boolean
      mirror: string  # Pull-through cache registry

  signing:
    enabled: boolean
    enforcement: warn | enforce | off
    public_key_ref: string  # For key-based verification
```

## References

- [OCI Distribution Spec](https://github.com/opencontainers/distribution-spec)
- [Helm OCI Support](https://helm.sh/docs/topics/registries/)
- [ORAS (OCI Registry As Storage)](https://oras.land/)
- [Cosign](https://github.com/sigstore/cosign)
- [Sigstore](https://www.sigstore.dev/)
- [ADR-0016: Platform Enforcement Architecture](adr/0016-platform-enforcement-architecture.md) - OCI decision rationale
- [Platform Artifacts](platform-artifacts.md) - Artifact structure details
