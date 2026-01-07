# Plugin Lifecycle and Versioning

This document describes plugin API versioning and compatibility management.

## Plugin API Versioning

```python
# floe_core/plugin_api.py
from typing import Final

FLOE_PLUGIN_API_VERSION: Final[str] = "1.0"
FLOE_PLUGIN_API_MIN_VERSION: Final[str] = "1.0"

@dataclass
class PluginMetadata:
    name: str
    version: str
    floe_api_version: str  # Required
    description: str
    author: str
```

## Compatibility Check

```python
def load_plugin(self, entry_point) -> Plugin:
    plugin_class = entry_point.load()
    metadata = plugin_class.metadata

    if not is_compatible(metadata.floe_api_version, FLOE_PLUGIN_API_MIN_VERSION):
        raise PluginIncompatibleError(
            f"Plugin {metadata.name} requires API v{metadata.floe_api_version}, "
            f"but minimum supported is v{FLOE_PLUGIN_API_MIN_VERSION}"
        )

    return plugin_class()
```

## Related Documents

- [Plugin Architecture Overview](index.md)
- [Discovery and Registry](discovery.md)
- [Plugin Interfaces](interfaces.md)
