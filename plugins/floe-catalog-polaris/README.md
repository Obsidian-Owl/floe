# floe-catalog-polaris

Apache Polaris Catalog Plugin for the floe data platform.

## Overview

This plugin provides Iceberg catalog management via [Apache Polaris](https://polaris.apache.org/),
implementing the `CatalogPlugin` ABC from floe-core.

## Features

- OAuth2 authentication with automatic token refresh
- Namespace management (create, list, delete)
- Table operations (create, list, drop)
- Credential vending (X-Iceberg-Access-Delegation)
- Health monitoring with response time tracking
- OpenTelemetry trace instrumentation

## Installation

```bash
pip install floe-catalog-polaris
```

## Quick Start

```python
from floe_core.plugins import get_plugin

# Get the Polaris catalog plugin
catalog = get_plugin("catalog", "polaris")

# Configure and connect
config = {
    "uri": "https://polaris.example.com/api/catalog",
    "warehouse": "default_warehouse",
    "oauth2": {
        "client_id": "${POLARIS_CLIENT_ID}",
        "client_secret": "${POLARIS_CLIENT_SECRET}",
        "token_url": "https://polaris.example.com/oauth/token",
    },
}
iceberg_catalog = catalog.connect(config)

# List namespaces
namespaces = catalog.list_namespaces()
```

## Configuration

See [quickstart.md](../../specs/001-catalog-plugin/quickstart.md) for detailed configuration options.

## Development

```bash
# Install in development mode
cd plugins/floe-catalog-polaris
pip install -e ".[dev]"

# Run tests
pytest tests/unit/
pytest tests/integration/  # Requires Polaris in Kind cluster
```

## License

Apache 2.0
