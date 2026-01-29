# floe-core

Core plugin registry and interfaces for the floe data platform.

## Installation

```bash
uv pip install floe-core
```

## Features

- Plugin discovery via entry points
- Type-safe plugin registration
- Version compatibility checking
- Configuration validation with Pydantic
- Health check support
- Artifact signing and verification (Epic 8B)

## External Dependencies

The following external CLI tools are required for artifact signing features:

### cosign (>= 2.0.0)

Required for key-based signing, KMS integration, and attestations.

```bash
# macOS
brew install cosign

# Linux (Debian/Ubuntu)
COSIGN_VERSION=2.4.1
curl -LO https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64
sudo install cosign-linux-amd64 /usr/local/bin/cosign

# Verify installation
cosign version
```

### syft (for SBOM generation)

Required for generating Software Bill of Materials (SBOM) in SPDX format.

```bash
# macOS
brew install syft

# Linux
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

# Verify installation
syft version
```

> **Note**: Keyless signing (OIDC-based) uses the `sigstore` Python library and does not require cosign CLI.

## Environment Variables

Configuration environment variables for signing and testing:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLOE_DISABLE_BROWSER_OAUTH` | `false` | Set to `true` to prevent interactive browser OAuth. Use in CI/CD where OIDC ambient credentials should be available. |
| `FLOE_OIDC_TOKEN_MAX_RETRIES` | `3` | Maximum retries for OIDC token acquisition (1-10). |

### CI/CD Configuration

In GitHub Actions, ensure OIDC is enabled:

```yaml
permissions:
  id-token: write  # Required for keyless signing
```

Then disable browser OAuth fallback:

```yaml
env:
  FLOE_DISABLE_BROWSER_OAUTH: "true"
```

This ensures tests fail fast if OIDC credentials are unavailable rather than hanging on browser auth.

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/floe_core

# Linting
ruff check src/floe_core
```
