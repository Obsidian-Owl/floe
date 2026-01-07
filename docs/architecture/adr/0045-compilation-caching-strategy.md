# ADR-0045: Compilation Caching Strategy

## Status

Accepted

## Context

The `floe compile` command executes multiple stages:
1. **Stage 1**: Load platform manifest from OCI registry
2. **Stage 2**: Resolve profiles (credentials, compute config)
3. **Stage 3**: Parse dbt manifest.json
4. **Stage 4**: Enforce policies (SQL linting, quality gates)

Repeated compilations with unchanged inputs are wasteful. For large dbt projects, parsing `manifest.json` can take 10+ seconds.

### Performance Target (REQ-148)

**Requirement**: Repeat compilation MUST be 10x faster than initial compilation when inputs are unchanged.

### The Caching Decision

Should caching be:
1. **Implementation detail**: Internal optimization, no ADR needed
2. **Architecture concern**: Affects observability, debugging, correctness

**Decision**: Architecture concern because caching affects:
- **Observability**: Cache hit/miss metrics, OTel spans
- **Debugging**: "Why is my change not applied?" → stale cache
- **Correctness**: Policy enforcement MUST NOT be cached

## Decision

Implement **content-addressable caching** for compilation stages 1-3 with strict invalidation rules. **NEVER cache Stage 4 (Policy Enforcement)**.

### Key Principles

1. **Content-Addressable**: Cache keys are SHA256 hashes of inputs (not timestamps)
2. **Cascade Invalidation**: Upstream cache miss invalidates all downstream caches
3. **Observability-First**: All cache operations emit OTel spans and metrics
4. **Correctness > Speed**: Policy enforcement ALWAYS executes (no caching)

## Cache Types

### Stage 1: OCI Artifact Cache

**What**: Platform manifest pulled from OCI registry
**Status**: Already cached by OCI registry (24-hour TTL by convention)
**Cache Key**: `{registry_url}/{manifest_name}:{digest}`
**Invalidation**: Digest change (IMMUTABLE artifacts)
**Location**: OCI registry's built-in cache

**No additional caching needed** - OCI registries handle this.

### Stage 2: Resolved Profiles Cache

**What**: Resolved dbt profiles.yml with credentials and compute config
**Cache Key**: `sha256(platform_manifest_digest + floe_spec_hash + env_vars_hash)`
**Invalidation**:
- Platform manifest version change
- floe.yaml content change
- Environment variable change (DB_HOST, DB_USER, etc.)

**Cache Location**: `~/.cache/floe/profiles/{cache_key}.json`
**TTL**: No TTL (invalidated by content changes only)

**Structure**:
```json
{
  "cache_key": "sha256_hash",
  "created_at": "2025-01-06T12:00:00Z",
  "inputs": {
    "platform_manifest_digest": "sha256:abc123...",
    "floe_spec_hash": "sha256:def456...",
    "env_vars_hash": "sha256:ghi789..."
  },
  "profiles": {
    "floe": {
      "target": "dev",
      "outputs": {
        "dev": {
          "type": "duckdb",
          "path": "dev.duckdb"
        }
      }
    }
  }
}
```

### Stage 3: dbt Manifest Cache

**What**: Parsed `manifest.json` from dbt compilation
**Cache Key**: `sha256(dbt_project_yml_hash + models_hash + macros_hash + profiles_hash)`
**Invalidation**:
- dbt_project.yml change
- Any model file change (*.sql)
- Any macro change
- profiles.yml change (from Stage 2)

**Cache Location**: `~/.cache/floe/manifests/{cache_key}.json`
**TTL**: No TTL (invalidated by content changes only)

**Structure**:
```json
{
  "cache_key": "sha256_hash",
  "created_at": "2025-01-06T12:00:00Z",
  "inputs": {
    "dbt_project_yml_hash": "sha256:abc123...",
    "models_hash": "sha256:def456...",
    "macros_hash": "sha256:ghi789...",
    "profiles_hash": "sha256:jkl012..."
  },
  "manifest": {
    "nodes": { ... },
    "sources": { ... },
    "tests": { ... }
  }
}
```

### Stage 4: Policy Enforcement (NEVER CACHED)

**What**: SQL linting, quality gate validation, governance checks
**Cache**: **FORBIDDEN** ❌
**Rationale**: Correctness > speed

**Why NEVER cache**:
- Policy rules may change in platform manifest
- SQL linting tools may be upgraded (new rules)
- Quality gate thresholds may change
- Caching policy enforcement creates false confidence ("It compiled before!")

**Performance**: Policy enforcement is fast (<1s) - caching gain is negligible

## Cache Invalidation Rules

### Rule 1: Content-Addressable Keys

Cache keys are SHA256 hashes of ALL inputs. ANY input change invalidates the cache.

```python
def compute_cache_key(inputs: dict[str, str]) -> str:
    """Compute cache key from inputs."""
    content = json.dumps(inputs, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()
```

### Rule 2: Cascade Invalidation

If Stage N cache is invalid, ALL downstream stages (N+1, N+2, ...) are invalid.

```
Stage 1 MISS → Stage 2 MISS → Stage 3 MISS → Stage 4 ALWAYS EXECUTES
Stage 1 HIT  → Stage 2 MISS → Stage 3 MISS → Stage 4 ALWAYS EXECUTES
Stage 1 HIT  → Stage 2 HIT  → Stage 3 MISS → Stage 4 ALWAYS EXECUTES
Stage 1 HIT  → Stage 2 HIT  → Stage 3 HIT  → Stage 4 ALWAYS EXECUTES
```

### Rule 3: Explicit Cache Clear

Users can force cache invalidation:

```bash
floe compile --no-cache  # Ignore all caches
floe cache clear         # Delete all cached data
floe cache clear --type profiles  # Delete only profile caches
```

### Rule 4: Cache Validation

On cache load, validate that:
1. Cache file exists
2. Cache file is valid JSON
3. Input hashes match current state
4. created_at is within last 30 days (staleness check)

If validation fails → treat as cache miss.

## Observability Integration

### OpenTelemetry Spans

Every cache operation emits spans:

```python
with tracer.start_as_current_span("cache.load") as span:
    span.set_attribute("cache.type", "profiles")
    span.set_attribute("cache.key", cache_key[:16])  # Truncated for logging

    result = load_from_cache(cache_key)

    span.set_attribute("cache.hit", result is not None)
    if result:
        span.set_attribute("cache.age_seconds", time.time() - result.created_at)
```

### Metrics

```python
# Cache hit/miss counters
cache_hit_counter = meter.create_counter("floe.compile.cache.hits")
cache_miss_counter = meter.create_counter("floe.compile.cache.misses")

# Cache hit rate (percentage)
cache_hit_rate = meter.create_histogram("floe.compile.cache.hit_rate")

# Cache age distribution
cache_age_histogram = meter.create_histogram("floe.compile.cache.age_seconds")
```

### Logs

```python
logger.info(
    "cache_hit",
    cache_type="profiles",
    cache_key=cache_key[:16],
    age_seconds=cache_age
)

logger.warning(
    "cache_miss",
    cache_type="manifest",
    cache_key=cache_key[:16],
    reason="model_file_changed",
    changed_file="models/staging/customers.sql"
)
```

## Performance Characteristics

### Target (REQ-148)

**Initial compilation**: 30 seconds (example for large dbt project)
**Repeat compilation (full cache hit)**: 3 seconds (10x faster)

### Breakdown

| Stage | Initial | Cached | Speedup |
|-------|---------|--------|---------|
| Stage 1: Load manifest | 2s | 0.1s (OCI cache) | 20x |
| Stage 2: Resolve profiles | 5s | 0.5s | 10x |
| Stage 3: Parse dbt manifest | 20s | 1s | 20x |
| Stage 4: Policy enforcement | 3s | 3s (NEVER CACHED) | 1x |
| **Total** | **30s** | **4.6s** | **6.5x** |

**Note**: Stage 4 ALWAYS executes (correctness > speed).

## Cache Management

### Cache Location

```
~/.cache/floe/
├── profiles/
│   ├── {sha256_hash}.json
│   └── ...
└── manifests/
    ├── {sha256_hash}.json
    └── ...
```

### Cache Cleanup

```bash
# Automatic cleanup (daily cron job)
floe cache clean --older-than 30d  # Delete caches older than 30 days

# Manual cleanup
floe cache clear                    # Delete all caches
floe cache clear --type profiles    # Delete only profile caches
floe cache clear --type manifests   # Delete only manifest caches

# Cache statistics
floe cache stats
# Output:
# Profiles cache: 15 entries, 2.3 MB, oldest: 5 days ago
# Manifests cache: 8 entries, 45 MB, oldest: 12 days ago
# Total cache size: 47.3 MB
```

### Cache Debugging

```bash
# Verbose compilation shows cache hits/misses
floe compile --verbose

# Output:
# Stage 1: Load manifest [CACHE HIT] (0.1s)
# Stage 2: Resolve profiles [CACHE HIT] (0.5s)
# Stage 3: Parse dbt manifest [CACHE MISS - model changed: models/staging/customers.sql] (20s)
# Stage 4: Policy enforcement [EXECUTED] (3s)
# Total: 23.6s
```

## Security Considerations

### Cache Poisoning Prevention

1. **Immutable OCI artifacts**: Platform manifests are IMMUTABLE (cannot be modified after push)
2. **Content hashing**: Cache keys include input hashes (tampering invalidates cache)
3. **File permissions**: Cache files are user-readable only (`0600`)

### Credential Handling

**NEVER cache raw credentials**:
- Profiles cache stores connection config structure ONLY
- Credentials are resolved at RUNTIME (not compile-time)
- Environment variables are HASHED (not stored in cache)

```json
// ✅ CORRECT - No credentials in cache
{
  "profiles": {
    "floe": {
      "outputs": {
        "dev": {
          "type": "snowflake",
          "account": "xy12345",
          "user": "${SNOWFLAKE_USER}",  // Environment variable reference
          "password": "${SNOWFLAKE_PASSWORD}"
        }
      }
    }
  }
}
```

## Consequences

### Positive

- **10x faster repeat compilations** (REQ-148 satisfied)
- **Content-addressable keys** prevent stale cache issues
- **Observability-first** design aids debugging
- **Correctness guaranteed** by never caching policy enforcement

### Negative

- **Cache storage overhead**: ~50 MB per project for typical usage
- **Cache invalidation complexity**: Must track ALL input file changes
- **Debugging effort**: "Why is my change not applied?" → must understand cache invalidation

### Neutral

- OCI registry caching already exists (no change needed)
- Cache cleanup required (automatic + manual)
- Cache statistics available for monitoring

## Implementation Roadmap

### Epic 3: Foundation
- Define cache file formats (profiles, manifests)
- Implement cache key computation (SHA256 hashing)
- Implement cache validation logic

### Epic 4: Cache Integration
- Integrate Stage 2 caching (profiles)
- Integrate Stage 3 caching (dbt manifest)
- Add cache clear commands

### Epic 5: Observability
- Add OTel spans for cache operations
- Add metrics (hit/miss counters, hit rate, age histogram)
- Add structured logging

### Epic 6: Cache Management
- Implement cache cleanup (automatic + manual)
- Implement cache statistics
- Add cache debugging (--verbose flag)

## Related ADRs

- [ADR-0016: Environment-Agnostic Compute](0016-environment-agnostic-compute.md) - No per-environment caching
- [ADR-0020: OCI Artifact Distribution](0020-oci-artifact-distribution.md) - OCI registry caching
- [ADR-0044: Unified Data Quality Plugin](0044-unified-data-quality-plugin.md) - Quality gates never cached

## References

- REQ-148: Incremental Compilation and Caching
- [Content-Addressable Storage](https://en.wikipedia.org/wiki/Content-addressable_storage)
- [OpenTelemetry Tracing](https://opentelemetry.io/docs/concepts/signals/traces/)
- [dbt Manifest Documentation](https://docs.getdbt.com/reference/artifacts/manifest-json)
