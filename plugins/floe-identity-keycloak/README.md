# floe-identity-keycloak

Keycloak identity provider plugin for the floe data platform.

## Installation

```bash
pip install floe-identity-keycloak
```

## Usage

```python
from floe_identity_keycloak import KeycloakIdentityPlugin, KeycloakIdentityConfig
from pydantic import SecretStr
import os

config = KeycloakIdentityConfig(
    server_url="https://keycloak.example.com",
    realm="floe",
    client_id=os.environ["KEYCLOAK_CLIENT_ID"],
    client_secret=SecretStr(os.environ["KEYCLOAK_CLIENT_SECRET"]),
)
plugin = KeycloakIdentityPlugin(config)
plugin.startup()

token = plugin.authenticate({"username": "user", "password": "pass"})
result = plugin.validate_token(token)
plugin.shutdown()
```

## Features

- OIDC/OAuth2 authentication
- JWT validation with JWKS
- Realm-based multi-tenancy
- OpenTelemetry tracing

## License

Apache-2.0
