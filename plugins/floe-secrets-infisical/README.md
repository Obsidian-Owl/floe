# floe-secrets-infisical

Infisical secrets backend plugin for the floe data platform.

## Installation

```bash
pip install floe-secrets-infisical
```

## Usage

```python
from floe_secrets_infisical import InfisicalSecretsPlugin, InfisicalSecretsConfig
from pydantic import SecretStr
import os

config = InfisicalSecretsConfig(
    client_id=os.environ["INFISICAL_CLIENT_ID"],
    client_secret=SecretStr(os.environ["INFISICAL_CLIENT_SECRET"]),
    project_id=os.environ["INFISICAL_PROJECT_ID"],
)
plugin = InfisicalSecretsPlugin(config=config)
plugin.startup()

secret = plugin.get_secret("database-password")
plugin.shutdown()
```

## Features

- Universal Auth authentication
- Path-based secret organization
- InfisicalSecret CRD integration
- Structured audit logging

## License

Apache-2.0
