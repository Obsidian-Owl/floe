# floe-lineage-marquez

Marquez lineage backend plugin for floe - OpenLineage reference implementation for data lineage.

## Overview

This plugin provides a `MarquezLineageBackendPlugin` that configures OpenLineage HTTP transport to send lineage events to a Marquez deployment. This is recommended for:

- Self-hosted data lineage tracking
- OpenLineage reference implementation
- Integration with existing Marquez infrastructure

## Installation

```bash
pip install floe-lineage-marquez
```

## Usage

### Via manifest.yaml (Recommended)

```yaml
# manifest.yaml
plugins:
  lineage_backend: marquez
```

### Programmatic Usage

```python
from floe_lineage_marquez import MarquezLineageBackendPlugin

plugin = MarquezLineageBackendPlugin(
    url="https://marquez:5000",
    api_key="optional-api-key"  # pragma: allowlist secret
)
# Plugin will be loaded automatically by LineageProvider
```

## Configuration

The Marquez plugin configures OpenLineage HTTP transport:

- **Default endpoint**: `marquez:5000` (HTTPS)
- **Protocol**: HTTPS/REST (HTTP for localhost development only)
- **API endpoint**: `/api/v1/lineage`

For production, configure:
- `url`: Marquez API base URL (use HTTPS)
- `api_key`: Optional authentication

## Helm Deployment

The plugin provides Helm values for self-hosted deployment:

```python
plugin = MarquezLineageBackendPlugin()
helm_values = plugin.get_helm_values()
# Returns Marquez + PostgreSQL chart values
```

## Requirements

- Python 3.10+
- floe-core >= 0.1.0

## Related

- [Marquez](https://marquezproject.ai/) - OpenLineage reference implementation
- [OpenLineage](https://openlineage.io/) - Open standard for data lineage

## License

Apache-2.0
