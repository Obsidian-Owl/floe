# Identity And Secret Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement PCU-005 by making identity and secret credential delivery a typed, resolver-validated plugin composition contract.

**Architecture:** Extend compiled plugin references with selected `secrets` and `identity` providers, then add typed secret projection and workload identity capability fields to the composition model. Provider plugins declare side-effect-free capabilities, and `CompositionResolver` validates storage/catalog credential requirements against selected secrets and identity providers while preserving the current MinIO plus Polaris Kubernetes Secret path.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, Floe plugin registry, Floe composition resolver, existing `floe-core` compilation pipeline.

---

## File Structure

- Modify `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
  - Add `secrets` and `identity` optional `PluginRef` fields to `ResolvedPlugins`.
  - Keep the contract secret-free and backward-compatible for artifacts that omit these fields.
- Modify `packages/floe-core/src/floe_core/compilation/resolver.py`
  - Pass through `manifest.plugins.secrets` and `manifest.plugins.identity` into `ResolvedPlugins`.
- Modify `packages/floe-core/src/floe_core/composition/models.py`
  - Add typed aliases for credential, secret projection, and identity modes.
  - Add `secret_projection_modes`, `identity_modes`, and `providers` to `CapabilitySet` and `RequirementSet`.
- Modify `packages/floe-core/src/floe_core/composition/__init__.py`
  - Export new mode aliases if the implementation exports them from `models.py`.
- Modify `packages/floe-core/src/floe_core/plugins/secrets.py`
  - Add default `get_secret_capabilities()` method returning an empty secrets capability.
- Modify `packages/floe-core/src/floe_core/plugins/identity.py`
  - Add default `get_identity_capabilities()` method returning an empty identity capability.
- Modify `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py`
  - Declare `kubernetes-secret` projection support and `kubernetes` provider.
- Modify `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py`
  - Declare `external-secret-sync` and `kubernetes-secret` projection support with `infisical` provider.
- Modify `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py`
  - Declare `oidc-federation` identity support with `oidc` provider.
- Modify `packages/floe-core/src/floe_core/composition/resolver.py`
  - Validate secret projection and identity requirements in addition to current storage/catalog compatibility checks.
- Modify `packages/floe-core/src/floe_core/compilation/stages.py`
  - Collect selected secrets and identity capabilities and pass them to `CompositionResolver`.
- Modify `docs/architecture/plugin-composition-uplift-tracker.md`
  - Update PCU-005 status after implementation lands.
- Modify `docs/architecture/interfaces/secrets-plugin.md`
  - Document `get_secret_capabilities()` and projection vocabulary.
- Modify `docs/architecture/interfaces/identity-plugin.md`
  - Document `get_identity_capabilities()` and identity-mode vocabulary.
- Modify `docs/architecture/interfaces/storage-plugin.md`
  - Reference the new credential vocabulary from storage capabilities.
- Modify `docs/architecture/interfaces/catalog-plugin.md`
  - Reference the new credential vocabulary from catalog requirements.
- Test files:
  - `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
  - `packages/floe-core/tests/unit/compilation/test_resolver.py` if present; otherwise use `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`
  - `packages/floe-core/tests/unit/composition/test_resolver.py`
  - `plugins/floe-secrets-k8s/tests/unit/test_plugin.py`
  - `plugins/floe-secrets-infisical/tests/unit/test_plugin.py`
  - `plugins/floe-identity-keycloak/tests/unit/test_init.py`
  - `tests/contract/test_storage_binding_security.py`

## Task 1: Add Secrets And Identity To Resolved Plugins

**Files:**
- Modify: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Modify: `packages/floe-core/src/floe_core/compilation/resolver.py`

- [ ] **Step 1: Write the failing `ResolvedPlugins` schema test**

Add this test to `class TestResolvedPlugins` in `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`:

```python
    @pytest.mark.requirement("PCU-005")
    def test_valid_resolved_plugins_includes_secrets_and_identity(self) -> None:
        """ResolvedPlugins should expose selected security providers."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            secrets=PluginRef(
                type="k8s",
                version="0.1.0",
                config={"namespace": "floe-system"},
            ),
            identity=PluginRef(
                type="keycloak",
                version="0.1.0",
                config={"realm": "floe"},
            ),
        )

        assert plugins.secrets is not None
        assert plugins.secrets.type == "k8s"
        assert plugins.secrets.config == {"namespace": "floe-system"}
        assert plugins.identity is not None
        assert plugins.identity.type == "keycloak"
        assert plugins.identity.config == {"realm": "floe"}
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestResolvedPlugins::test_valid_resolved_plugins_includes_secrets_and_identity -q
```

Expected: FAIL with Pydantic extra-field validation errors for `secrets` and `identity`.

- [ ] **Step 3: Add fields to `ResolvedPlugins`**

In `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`, add the two fields after `lineage_backend`:

```python
    secrets: PluginRef | None = Field(
        default=None,
        description="Resolved secrets plugin (optional)",
    )
    identity: PluginRef | None = Field(
        default=None,
        description="Resolved identity plugin (optional)",
    )
```

Update the `ResolvedPlugins` docstring attribute list so it names `secrets` and `identity`.

- [ ] **Step 4: Run the schema test and verify it passes**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestResolvedPlugins::test_valid_resolved_plugins_includes_secrets_and_identity -q
```

Expected: PASS.

- [ ] **Step 5: Write the failing resolver pass-through test**

Add this test to `packages/floe-core/tests/unit/compilation/test_resolver.py` if that file exists. If it does not exist, create it with the imports shown here:

```python
"""Unit tests for platform plugin resolution."""

from __future__ import annotations

from floe_core.compilation.resolver import resolve_plugins
from floe_core.schemas.manifest import PlatformManifest
from floe_core.schemas.metadata import ManifestMetadata
from floe_core.schemas.plugins import PluginSelection, PluginsConfig
```

Then add:

```python
def test_resolve_plugins_preserves_secrets_and_identity_selections() -> None:
    """Compilation should expose selected security providers in artifacts."""
    manifest = PlatformManifest(
        metadata=ManifestMetadata(name="platform", version="1.0.0"),
        plugins=PluginsConfig(
            compute=PluginSelection(type="duckdb", version="0.9.0"),
            orchestrator=PluginSelection(type="dagster", version="1.5.0"),
            secrets=PluginSelection(
                type="k8s",
                version="0.1.0",
                config={"namespace": "floe-system"},
            ),
            identity=PluginSelection(
                type="keycloak",
                version="0.1.0",
                config={"realm": "floe"},
            ),
        ),
    )

    resolved = resolve_plugins(manifest)

    assert resolved.secrets is not None
    assert resolved.secrets.type == "k8s"
    assert resolved.secrets.config == {"namespace": "floe-system"}
    assert resolved.identity is not None
    assert resolved.identity.type == "keycloak"
    assert resolved.identity.config == {"realm": "floe"}
```

- [ ] **Step 6: Run the resolver test and verify it fails**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_resolver.py::test_resolve_plugins_preserves_secrets_and_identity_selections -q
```

Expected: FAIL because `resolve_plugins()` does not set `secrets` or `identity`.

- [ ] **Step 7: Pass through secrets and identity selections**

In `packages/floe-core/src/floe_core/compilation/resolver.py`, update `resolve_plugins()`:

```python
    return ResolvedPlugins(
        compute=_to_plugin_ref(plugins.compute),  # type: ignore[arg-type]
        orchestrator=_to_plugin_ref(plugins.orchestrator),  # type: ignore[arg-type]
        catalog=_to_plugin_ref(plugins.catalog),
        storage=_to_plugin_ref(plugins.storage),
        ingestion=_to_plugin_ref(plugins.ingestion),
        semantic=_to_plugin_ref(plugins.semantic_layer),
        lineage_backend=_to_plugin_ref(plugins.lineage_backend),
        secrets=_to_plugin_ref(plugins.secrets),
        identity=_to_plugin_ref(plugins.identity),
    )
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestResolvedPlugins::test_valid_resolved_plugins_includes_secrets_and_identity \
  packages/floe-core/tests/unit/compilation/test_resolver.py::test_resolve_plugins_preserves_secrets_and_identity_selections \
  -q
```

Expected: both tests PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add \
  packages/floe-core/src/floe_core/schemas/compiled_artifacts.py \
  packages/floe-core/src/floe_core/compilation/resolver.py \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py \
  packages/floe-core/tests/unit/compilation/test_resolver.py
git commit -m "feat: expose resolved identity and secrets plugins"
```

## Task 2: Add Typed Credential Composition Vocabulary

**Files:**
- Modify: `packages/floe-core/tests/unit/composition/test_resolver.py`
- Modify: `packages/floe-core/src/floe_core/composition/models.py`
- Modify: `packages/floe-core/src/floe_core/composition/__init__.py`

- [ ] **Step 1: Write failing model tests**

Append these tests to `packages/floe-core/tests/unit/composition/test_resolver.py`:

```python
def test_capability_set_accepts_security_composition_modes() -> None:
    """CapabilitySet should carry secret projection and identity capabilities."""
    capabilities = CapabilitySet(
        credential_modes=["kubernetes-secret", "workload-identity"],
        secret_projection_modes=["kubernetes-secret", "external-secret-sync"],
        identity_modes=["aws-irsa", "oidc-federation"],
        providers=["kubernetes", "aws", "oidc"],
    )

    assert capabilities.secret_projection_modes == [
        "kubernetes-secret",
        "external-secret-sync",
    ]
    assert capabilities.identity_modes == ["aws-irsa", "oidc-federation"]
    assert capabilities.providers == ["kubernetes", "aws", "oidc"]


def test_requirement_set_accepts_security_composition_modes() -> None:
    """RequirementSet should describe required secret and identity modes."""
    requirements = RequirementSet(
        credential_modes=["external-secret-sync"],
        secret_projection_modes=["external-secret-sync"],
        identity_modes=["gcp-workload-identity"],
        providers=["gcp"],
    )

    assert requirements.credential_modes == ["external-secret-sync"]
    assert requirements.secret_projection_modes == ["external-secret-sync"]
    assert requirements.identity_modes == ["gcp-workload-identity"]
    assert requirements.providers == ["gcp"]
```

- [ ] **Step 2: Run the model tests and verify they fail**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/composition/test_resolver.py::test_capability_set_accepts_security_composition_modes \
  packages/floe-core/tests/unit/composition/test_resolver.py::test_requirement_set_accepts_security_composition_modes \
  -q
```

Expected: FAIL because `CapabilitySet` and `RequirementSet` reject the new fields.

- [ ] **Step 3: Add mode aliases and fields**

In `packages/floe-core/src/floe_core/composition/models.py`, replace the current import section with:

```python
from typing import Literal, TypeAlias
```

Then add these aliases after the imports:

```python
CredentialMode: TypeAlias = Literal[
    "kubernetes-secret",
    "external-secret-sync",
    "csi-secret-volume",
    "environment",
    "workload-identity",
    "none",
]
SecretProjectionMode: TypeAlias = Literal[
    "kubernetes-secret",
    "external-secret-sync",
    "csi-secret-volume",
    "environment",
]
IdentityMode: TypeAlias = Literal[
    "aws-irsa",
    "aws-pod-identity",
    "gcp-workload-identity",
    "azure-workload-identity",
    "azure-managed-identity",
    "oidc-federation",
]
```

Update `CapabilitySet`:

```python
class CapabilitySet(BaseModel):
    """Structured capabilities emitted by a plugin for composition checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[CredentialMode] = Field(default_factory=list)
    secret_projection_modes: list[SecretProjectionMode] = Field(default_factory=list)
    identity_modes: list[IdentityMode] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    path_style_access: bool | None = None
    sts: bool | None = None
```

Update `RequirementSet`:

```python
class RequirementSet(BaseModel):
    """Structured peer requirements consumed by the composition resolver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[CredentialMode] = Field(default_factory=list)
    secret_projection_modes: list[SecretProjectionMode] = Field(default_factory=list)
    identity_modes: list[IdentityMode] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    requires_server_side_storage_access: bool | None = None
    supports_no_sts: bool | None = None
    supports_path_style_access: bool | None = None
```

- [ ] **Step 4: Export the aliases**

In `packages/floe-core/src/floe_core/composition/__init__.py`, include these imports:

```python
from floe_core.composition.models import (
    CapabilitySet,
    CompositionIssue,
    CompositionValidationResult,
    CredentialMode,
    IdentityMode,
    PluginCapabilities,
    PluginRequirements,
    RequirementSet,
    SecretProjectionMode,
)
```

Update `__all__` to include:

```python
    "CredentialMode",
    "IdentityMode",
    "SecretProjectionMode",
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
```

Expected: existing resolver tests and the new model tests PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add \
  packages/floe-core/src/floe_core/composition/models.py \
  packages/floe-core/src/floe_core/composition/__init__.py \
  packages/floe-core/tests/unit/composition/test_resolver.py
git commit -m "feat: add credential composition mode vocabulary"
```

## Task 3: Add Provider Capability Methods

**Files:**
- Modify: `packages/floe-core/src/floe_core/plugins/secrets.py`
- Modify: `packages/floe-core/src/floe_core/plugins/identity.py`
- Modify: `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py`
- Modify: `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py`
- Modify: `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py`
- Modify: `plugins/floe-secrets-k8s/tests/unit/test_plugin.py`
- Modify: `plugins/floe-secrets-infisical/tests/unit/test_plugin.py`
- Modify: `plugins/floe-identity-keycloak/tests/unit/test_init.py`

- [ ] **Step 1: Write failing K8s secrets capability test**

Add to `plugins/floe-secrets-k8s/tests/unit/test_plugin.py` in `class TestK8sSecretsPluginMetadata`:

```python
    @pytest.mark.requirement("PCU-005")
    def test_secret_capabilities(self) -> None:
        """K8s secrets plugin should declare Kubernetes Secret projection."""
        plugin = K8sSecretsPlugin()

        capabilities = plugin.get_secret_capabilities()

        assert capabilities.plugin_type == "secrets"
        assert capabilities.plugin_name == "k8s"
        assert capabilities.capabilities.secret_projection_modes == ["kubernetes-secret"]
        assert capabilities.capabilities.providers == ["kubernetes"]
```

- [ ] **Step 2: Write failing Infisical secrets capability test**

Add to `plugins/floe-secrets-infisical/tests/unit/test_plugin.py` in `class TestInfisicalSecretsPluginMetadata`:

```python
    @pytest.mark.requirement("PCU-005")
    def test_secret_capabilities(
        self,
        plugin: InfisicalSecretsPlugin,
    ) -> None:
        """Infisical plugin should declare external secret sync support."""
        capabilities = plugin.get_secret_capabilities()

        assert capabilities.plugin_type == "secrets"
        assert capabilities.plugin_name == "infisical"
        assert capabilities.capabilities.secret_projection_modes == [
            "external-secret-sync",
            "kubernetes-secret",
        ]
        assert capabilities.capabilities.providers == ["infisical", "kubernetes"]
```

- [ ] **Step 3: Write failing Keycloak identity capability test**

Add to `plugins/floe-identity-keycloak/tests/unit/test_init.py` in `class TestLazyImports`:

```python
    @pytest.mark.requirement("PCU-005")
    def test_keycloak_identity_capabilities(self) -> None:
        """Keycloak plugin should declare OIDC federation support."""
        from pydantic import SecretStr

        from floe_identity_keycloak import KeycloakIdentityConfig, KeycloakIdentityPlugin

        plugin = KeycloakIdentityPlugin(
            KeycloakIdentityConfig(
                server_url="https://keycloak.example.com",
                realm="floe",
                client_id="floe-client",
                client_secret=SecretStr("not-a-real-secret"),
            )
        )

        capabilities = plugin.get_identity_capabilities()

        assert capabilities.plugin_type == "identity"
        assert capabilities.plugin_name == "keycloak"
        assert capabilities.capabilities.identity_modes == ["oidc-federation"]
        assert capabilities.capabilities.providers == ["oidc"]
```

- [ ] **Step 4: Run capability tests and verify they fail**

Run:

```bash
uv run pytest \
  plugins/floe-secrets-k8s/tests/unit/test_plugin.py::TestK8sSecretsPluginMetadata::test_secret_capabilities \
  plugins/floe-secrets-infisical/tests/unit/test_plugin.py::TestInfisicalSecretsPluginMetadata::test_secret_capabilities \
  plugins/floe-identity-keycloak/tests/unit/test_init.py::TestLazyImports::test_keycloak_identity_capabilities \
  -q
```

Expected: FAIL because the capability methods do not exist.

- [ ] **Step 5: Add default `SecretsPlugin.get_secret_capabilities()`**

In `packages/floe-core/src/floe_core/plugins/secrets.py`, add this import:

```python
from floe_core.composition.models import CapabilitySet, PluginCapabilities
```

Add this method to `SecretsPlugin`:

```python
    def get_secret_capabilities(self) -> PluginCapabilities:
        """Return secret projection capabilities for composition validation.

        The default is intentionally empty so existing secrets plugins remain
        discoverable until they adopt composition explicitly.
        """
        return PluginCapabilities(
            plugin_type="secrets",
            plugin_name=self.name,
            capabilities=CapabilitySet(),
        )
```

- [ ] **Step 6: Add default `IdentityPlugin.get_identity_capabilities()`**

In `packages/floe-core/src/floe_core/plugins/identity.py`, add this import:

```python
from floe_core.composition.models import CapabilitySet, PluginCapabilities
```

Add this method to `IdentityPlugin`:

```python
    def get_identity_capabilities(self) -> PluginCapabilities:
        """Return workload identity capabilities for composition validation.

        The default is intentionally empty so existing identity plugins remain
        discoverable until they adopt composition explicitly.
        """
        return PluginCapabilities(
            plugin_type="identity",
            plugin_name=self.name,
            capabilities=CapabilitySet(),
        )
```

- [ ] **Step 7: Add K8s capability declaration**

In `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py`, add:

```python
from floe_core.composition.models import CapabilitySet, PluginCapabilities
```

Add this method to `K8sSecretsPlugin` near the metadata methods:

```python
    def get_secret_capabilities(self) -> PluginCapabilities:
        """Return Kubernetes Secret projection capabilities."""
        return PluginCapabilities(
            plugin_type="secrets",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["kubernetes-secret"],
                secret_projection_modes=["kubernetes-secret"],
                providers=["kubernetes"],
            ),
        )
```

- [ ] **Step 8: Add Infisical capability declaration**

In `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py`, add:

```python
from floe_core.composition.models import CapabilitySet, PluginCapabilities
```

Add this method to `InfisicalSecretsPlugin` near the metadata methods:

```python
    def get_secret_capabilities(self) -> PluginCapabilities:
        """Return Infisical external secret sync capabilities."""
        return PluginCapabilities(
            plugin_type="secrets",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["external-secret-sync", "kubernetes-secret"],
                secret_projection_modes=["external-secret-sync", "kubernetes-secret"],
                providers=["infisical", "kubernetes"],
            ),
        )
```

- [ ] **Step 9: Add Keycloak capability declaration**

In `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py`, add:

```python
from floe_core.composition.models import CapabilitySet, PluginCapabilities
```

Add this method to `KeycloakIdentityPlugin` near the metadata properties:

```python
    def get_identity_capabilities(self) -> PluginCapabilities:
        """Return OIDC federation capabilities for workload identity checks."""
        return PluginCapabilities(
            plugin_type="identity",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["workload-identity"],
                identity_modes=["oidc-federation"],
                providers=["oidc"],
            ),
        )
```

- [ ] **Step 10: Run focused provider tests**

Run:

```bash
uv run pytest \
  plugins/floe-secrets-k8s/tests/unit/test_plugin.py::TestK8sSecretsPluginMetadata::test_secret_capabilities \
  plugins/floe-secrets-infisical/tests/unit/test_plugin.py::TestInfisicalSecretsPluginMetadata::test_secret_capabilities \
  plugins/floe-identity-keycloak/tests/unit/test_init.py::TestLazyImports::test_keycloak_identity_capabilities \
  -q
```

Expected: all three tests PASS.

- [ ] **Step 11: Commit Task 3**

```bash
git add \
  packages/floe-core/src/floe_core/plugins/secrets.py \
  packages/floe-core/src/floe_core/plugins/identity.py \
  plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py \
  plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py \
  plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py \
  plugins/floe-secrets-k8s/tests/unit/test_plugin.py \
  plugins/floe-secrets-infisical/tests/unit/test_plugin.py \
  plugins/floe-identity-keycloak/tests/unit/test_init.py
git commit -m "feat: declare identity and secret plugin capabilities"
```

## Task 4: Validate Secret Projection And Identity Modes In The Resolver

**Files:**
- Modify: `packages/floe-core/tests/unit/composition/test_resolver.py`
- Modify: `packages/floe-core/src/floe_core/composition/resolver.py`

- [ ] **Step 1: Write failing resolver tests**

Append these tests to `packages/floe-core/tests/unit/composition/test_resolver.py`:

```python
def test_resolver_accepts_kubernetes_secret_with_implicit_baseline() -> None:
    """Existing MinIO and Polaris path must stay valid without secrets plugin."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            secret_projection_modes=["kubernetes-secret"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="polaris",
        requirements=RequirementSet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            secret_projection_modes=["kubernetes-secret"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is True
    assert result.issues == []


def test_resolver_rejects_external_secret_sync_without_secrets_plugin() -> None:
    """External secret sync requires an explicit secrets provider."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_SECRET_PROVIDER_MISSING",
            message=(
                "catalog glue requires secret projection mode external-secret-sync "
                "but no secrets plugin was selected"
            ),
            plugins=["catalog:glue"],
        )
    ]


def test_resolver_accepts_external_secret_sync_with_matching_secrets_plugin() -> None:
    """External secret sync succeeds when selected secrets plugin supports it."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
        ),
    )
    secrets = PluginCapabilities(
        plugin_type="secrets",
        plugin_name="infisical",
        capabilities=CapabilitySet(
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
            providers=["infisical"],
        ),
    )

    result = resolver.validate([storage, secrets], [catalog])

    assert result.valid is True
    assert result.issues == []


def test_resolver_rejects_unsupported_secret_projection_mode() -> None:
    """Selected secrets provider must support the requested projection mode."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="azure-blob",
        capabilities=CapabilitySet(
            protocols=["azure-blob"],
            credential_modes=["csi-secret-volume"],
            secret_projection_modes=["csi-secret-volume"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="rest",
        requirements=RequirementSet(
            protocols=["azure-blob"],
            credential_modes=["csi-secret-volume"],
            secret_projection_modes=["csi-secret-volume"],
        ),
    )
    secrets = PluginCapabilities(
        plugin_type="secrets",
        plugin_name="infisical",
        capabilities=CapabilitySet(
            credential_modes=["external-secret-sync"],
            secret_projection_modes=["external-secret-sync"],
            providers=["infisical"],
        ),
    )

    result = resolver.validate([storage, secrets], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_SECRET_PROJECTION_UNSUPPORTED",
            message=(
                "catalog rest requires secret projection mode csi-secret-volume; "
                "secrets infisical provides ['external-secret-sync']"
            ),
            plugins=["secrets:infisical", "catalog:rest"],
        )
    ]


def test_resolver_rejects_identity_mode_without_identity_plugin() -> None:
    """Workload identity requires an explicit identity provider."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_IDENTITY_PROVIDER_MISSING",
            message=(
                "catalog glue requires identity mode aws-irsa "
                "but no identity plugin was selected"
            ),
            plugins=["catalog:glue"],
        )
    ]


def test_resolver_rejects_unsupported_identity_mode() -> None:
    """Selected identity provider must support the requested identity mode."""
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            providers=["aws"],
        ),
    )
    identity = PluginCapabilities(
        plugin_type="identity",
        plugin_name="keycloak",
        capabilities=CapabilitySet(
            credential_modes=["workload-identity"],
            identity_modes=["oidc-federation"],
            providers=["oidc"],
        ),
    )

    result = resolver.validate([storage, identity], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_IDENTITY_MODE_UNSUPPORTED",
            message=(
                "catalog glue requires identity mode aws-irsa; "
                "identity keycloak provides ['oidc-federation']"
            ),
            plugins=["identity:keycloak", "catalog:glue"],
        )
    ]
```

- [ ] **Step 2: Run resolver tests and verify new ones fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
```

Expected: existing tests PASS; new secret/identity resolver tests FAIL.

- [ ] **Step 3: Implement resolver helpers**

In `packages/floe-core/src/floe_core/composition/resolver.py`, update `validate()` and add helper methods. The resulting class should contain these methods:

```python
class CompositionResolver:
    """Validate that selected plugin capabilities satisfy peer requirements."""

    def validate(
        self,
        capabilities: list[PluginCapabilities],
        requirements: list[PluginRequirements],
    ) -> CompositionValidationResult:
        """Return compatibility issues for the selected plugin graph."""
        issues: list[CompositionIssue] = []
        storage = next((item for item in capabilities if item.plugin_type == "storage"), None)
        secrets = next((item for item in capabilities if item.plugin_type == "secrets"), None)
        identity = next((item for item in capabilities if item.plugin_type == "identity"), None)

        for requirement in requirements:
            if requirement.plugin_type != "catalog":
                continue
            if storage is None:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_STORAGE_MISSING",
                        message=(
                            f"catalog {requirement.plugin_name} requires storage "
                            "capabilities but no storage plugin was selected"
                        ),
                        plugins=[requirement.ref],
                    )
                )
                continue
            issues.extend(self._validate_storage_for_catalog(storage, requirement))
            issues.extend(self._validate_secret_projection(secrets, requirement))
            issues.extend(self._validate_identity(identity, requirement))

        return CompositionValidationResult(
            valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )
```

Add these helpers below `_validate_storage_for_catalog()`:

```python
    def _validate_secret_projection(
        self,
        secrets: PluginCapabilities | None,
        requirement: PluginRequirements,
    ) -> list[CompositionIssue]:
        """Validate required secret projection modes against secrets provider."""
        issues: list[CompositionIssue] = []
        for mode in requirement.requirements.secret_projection_modes:
            if mode in ("kubernetes-secret", "environment"):
                if secrets is None:
                    continue
            if secrets is None:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_SECRET_PROVIDER_MISSING",
                        message=(
                            f"catalog {requirement.plugin_name} requires secret projection "
                            f"mode {mode} but no secrets plugin was selected"
                        ),
                        plugins=[requirement.ref],
                    )
                )
                continue
            provided_modes = list(secrets.capabilities.secret_projection_modes)
            if mode not in provided_modes:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_SECRET_PROJECTION_UNSUPPORTED",
                        message=(
                            f"catalog {requirement.plugin_name} requires secret projection "
                            f"mode {mode}; secrets {secrets.plugin_name} provides {provided_modes}"
                        ),
                        plugins=[secrets.ref, requirement.ref],
                    )
                )
        return issues

    def _validate_identity(
        self,
        identity: PluginCapabilities | None,
        requirement: PluginRequirements,
    ) -> list[CompositionIssue]:
        """Validate required workload identity modes against identity provider."""
        issues: list[CompositionIssue] = []
        requires_workload_identity = "workload-identity" in requirement.requirements.credential_modes
        required_modes = list(requirement.requirements.identity_modes)
        if not requires_workload_identity and not required_modes:
            return issues

        if identity is None:
            mode = required_modes[0] if required_modes else "workload-identity"
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_IDENTITY_PROVIDER_MISSING",
                    message=(
                        f"catalog {requirement.plugin_name} requires identity mode {mode} "
                        "but no identity plugin was selected"
                    ),
                    plugins=[requirement.ref],
                )
            )
            return issues

        provided_modes = list(identity.capabilities.identity_modes)
        for mode in required_modes:
            if mode not in provided_modes:
                issues.append(
                    CompositionIssue(
                        severity="error",
                        code="COMPOSITION_IDENTITY_MODE_UNSUPPORTED",
                        message=(
                            f"catalog {requirement.plugin_name} requires identity mode {mode}; "
                            f"identity {identity.plugin_name} provides {provided_modes}"
                        ),
                        plugins=[identity.ref, requirement.ref],
                    )
                )
        return issues
```

- [ ] **Step 4: Run resolver tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
```

Expected: all resolver tests PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add \
  packages/floe-core/src/floe_core/composition/resolver.py \
  packages/floe-core/tests/unit/composition/test_resolver.py
git commit -m "feat: validate identity and secret composition modes"
```

## Task 5: Wire Security Capabilities Into Compilation

**Files:**
- Modify: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Modify: `tests/contract/test_storage_binding_security.py`

- [ ] **Step 1: Add fake provider classes to the compilation test**

In `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`, add imports near the existing plugin imports:

```python
from floe_core.composition.models import CapabilitySet, PluginCapabilities
from floe_core.plugins.identity import IdentityPlugin, TokenValidationResult, UserInfo
from floe_core.plugins.secrets import SecretsPlugin
```

Add these classes above the first test:

```python
class FakeSecretsPlugin(SecretsPlugin):
    """Secrets plugin used to prove compiler composition wiring."""

    @property
    def name(self) -> str:
        return "fake-secrets"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def get_config_schema(self) -> None:
        return None

    def get_secret(self, key: str) -> str | None:
        return None

    def set_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        return None

    def list_secrets(self, prefix: str = "") -> list[str]:
        return []

    def get_secret_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            plugin_type="secrets",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["external-secret-sync"],
                secret_projection_modes=["external-secret-sync"],
                providers=["infisical"],
            ),
        )


class FakeIdentityPlugin(IdentityPlugin):
    """Identity plugin used to prove compiler composition wiring."""

    @property
    def name(self) -> str:
        return "fake-identity"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def get_config_schema(self) -> None:
        return None

    def authenticate(self, credentials: dict[str, Any]) -> str | None:
        return None

    def get_user_info(self, token: str) -> UserInfo | None:
        return None

    def validate_token(self, token: str) -> TokenValidationResult:
        return TokenValidationResult(valid=False)

    def get_identity_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            plugin_type="identity",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["workload-identity"],
                identity_modes=["aws-irsa"],
                providers=["aws"],
            ),
        )
```

- [ ] **Step 2: Write failing compiler wiring test**

Append this test to `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`:

```python
def test_compile_passes_selected_secret_and_identity_capabilities_to_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compilation should validate non-baseline credential modes with providers."""

    class IdentityStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "s3"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_config_schema(self) -> None:
            return None

        def get_pyiceberg_fileio(self) -> FileIO:
            raise NotImplementedError

        def get_warehouse_uri(self, namespace: str) -> str:
            return f"s3://warehouse/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> StorageDeploymentBinding:
            return StorageDeploymentBinding(
                provider="s3",
                protocol="s3",
                endpoint=StorageServiceEndpoint(
                    internal_url="https://s3.us-east-1.amazonaws.com",
                    external_url="https://s3.us-east-1.amazonaws.com",
                    region="us-east-1",
                    warehouse_path="s3://warehouse",
                    path_style_access=False,
                ),
                warehouse=StorageWarehouse(uri="s3://warehouse", bucket="warehouse"),
                credentials=StorageCredentialBinding(
                    mode="workload-identity",
                    service_account_ref="floe-runtime",
                ),
                capabilities=StorageCapabilities(
                    protocols=["s3"],
                    credential_modes=["workload-identity"],
                    sts_supported=True,
                    path_style_access=False,
                ),
                dbt=DbtStorageBinding(
                    profile_name="floe",
                    target_name="dev",
                    schema_name="analytics",
                ),
                dagster=DagsterStorageBinding(
                    resource_key="s3_storage",
                    asset_io_manager_key="iceberg_io_manager",
                ),
            )

    class IdentityCatalogPlugin(CatalogPlugin):
        @property
        def name(self) -> str:
            return "glue"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_config_schema(self) -> None:
            return None

        def connect(self, config: dict[str, Any]) -> Any:
            raise NotImplementedError

        def create_namespace(self, namespace: str, properties: dict[str, str] | None = None) -> None:
            return None

        def vend_credentials(self, table_path: str, operations: list[str]) -> dict[str, Any]:
            return {}

        def list_namespaces(self, parent: str | None = None) -> list[str]:
            return []

        def delete_namespace(self, namespace: str) -> None:
            return None

        def create_table(self, identifier: str, schema: dict[str, Any], **kwargs: Any) -> None:
            return None

        def list_tables(self, namespace: str) -> list[str]:
            return []

        def drop_table(self, identifier: str, purge: bool = False) -> None:
            return None

        def get_storage_requirements(self) -> PluginRequirements:
            return PluginRequirements(
                plugin_type="catalog",
                plugin_name="glue",
                requirements=RequirementSet(
                    protocols=["s3"],
                    credential_modes=["workload-identity"],
                    identity_modes=["aws-irsa"],
                    providers=["aws"],
                ),
            )

        def build_catalog_deployment(
            self,
            storage: StorageDeploymentBinding,
        ) -> CatalogDeploymentBinding:
            return CatalogDeploymentBinding(
                provider="polaris",
                polaris=PolarisCatalogDeploymentBinding(
                    storage_type="S3",
                    default_base_location="s3://warehouse",
                    allowed_locations=["s3://warehouse"],
                    endpoint=storage.endpoint.external_url,
                    endpoint_internal=storage.endpoint.internal_url,
                    path_style_access=False,
                    sts_unavailable=False,
                    credential_refs={
                        "accessKeyId": CredentialRef(source="none", name="none"),
                        "secretAccessKey": CredentialRef(source="none", name="none"),
                    },
                ),
            )

    class IsolatedRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> Any:
            if plugin_type == PluginType.STORAGE:
                return IdentityStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return IdentityCatalogPlugin()
            if plugin_type == PluginType.SECRETS:
                return FakeSecretsPlugin()
            if plugin_type == PluginType.IDENTITY:
                return FakeIdentityPlugin()
            raise AssertionError(f"unexpected plugin lookup: {plugin_type} {name}")

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedRegistry)
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"]["storage"] = {"type": "s3"}
    manifest["plugins"]["catalog"] = {"type": "glue"}
    manifest["plugins"]["secrets"] = {"type": "fake-secrets"}
    manifest["plugins"]["identity"] = {"type": "fake-identity"}
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        manifest_path,
        emit_lineage=False,
    )

    assert artifacts.plugins is not None
    assert artifacts.plugins.secrets is not None
    assert artifacts.plugins.secrets.type == "fake-secrets"
    assert artifacts.plugins.identity is not None
    assert artifacts.plugins.identity.type == "fake-identity"
    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    assert artifacts.deployment.storage.credentials.mode == "workload-identity"
```

- [ ] **Step 3: Run compiler wiring test and verify it fails**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_compile_passes_selected_secret_and_identity_capabilities_to_resolver -q
```

Expected: FAIL because compilation does not collect selected secrets or identity capabilities for resolver validation.

- [ ] **Step 4: Add helper functions in compilation stages**

In `packages/floe-core/src/floe_core/compilation/stages.py`, inside `_build_storage_deployment_binding()`, import:

```python
    from floe_core.plugins.identity import IdentityPlugin
    from floe_core.plugins.secrets import SecretsPlugin
```

Before calling `CompositionResolver().validate(...)`, collect optional capabilities:

```python
        composition_capabilities = [storage_capabilities]

        if plugins.secrets is not None:
            registry.configure(
                PluginType.SECRETS,
                plugins.secrets.type,
                plugins.secrets.config or {},
            )
            secrets_plugin = registry.get(PluginType.SECRETS, plugins.secrets.type)
            if not isinstance(secrets_plugin, SecretsPlugin):
                raise CompilationException(
                    CompilationError(
                        stage=CompilationStage.RESOLVE,
                        code="E201",
                        message=f"Plugin {plugins.secrets.type!r} is not a SecretsPlugin",
                        suggestion="Use a plugin registered under the floe.secrets entry point group",
                        context={"secrets_plugin": plugins.secrets.type},
                    )
                )
            composition_capabilities.append(secrets_plugin.get_secret_capabilities())

        if plugins.identity is not None:
            registry.configure(
                PluginType.IDENTITY,
                plugins.identity.type,
                plugins.identity.config or {},
            )
            identity_plugin = registry.get(PluginType.IDENTITY, plugins.identity.type)
            if not isinstance(identity_plugin, IdentityPlugin):
                raise CompilationException(
                    CompilationError(
                        stage=CompilationStage.RESOLVE,
                        code="E201",
                        message=f"Plugin {plugins.identity.type!r} is not an IdentityPlugin",
                        suggestion="Use a plugin registered under the floe.identity entry point group",
                        context={"identity_plugin": plugins.identity.type},
                    )
                )
            composition_capabilities.append(identity_plugin.get_identity_capabilities())

        composition = CompositionResolver().validate(
            composition_capabilities,
            [catalog_requirements],
        )
```

Replace the previous call that passed only `[storage_capabilities]`.

- [ ] **Step 5: Run compiler wiring test**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_compile_passes_selected_secret_and_identity_capabilities_to_resolver -q
```

Expected: PASS.

- [ ] **Step 6: Add security contract assertion for plugin refs**

In `tests/contract/test_storage_binding_security.py`, extend `test_compiled_artifact_does_not_contain_minio_secret_values()`:

```python
    assert artifacts.plugins is not None
    payload = artifacts.model_dump_json()
    assert "credentialSecretName" not in payload
```

If this assertion fails because chart-only keys are not present but plugin config carries `credential_secret_name`, change the assertion to:

```python
    assert artifacts.plugins is not None
    assert artifacts.plugins.storage is not None
    assert artifacts.plugins.storage.config is not None
    assert "credential_secret_name" in artifacts.plugins.storage.config
```

This keeps the test honest about current behavior: the plugin config may name a Secret, but raw Secret values must remain absent.

- [ ] **Step 7: Run focused compilation and security tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  tests/contract/test_storage_binding_security.py \
  -q
```

Expected: tests PASS.

- [ ] **Step 8: Commit Task 5**

```bash
git add \
  packages/floe-core/src/floe_core/compilation/stages.py \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  tests/contract/test_storage_binding_security.py
git commit -m "feat: validate security provider capabilities during compile"
```

## Task 6: Update Architecture Documentation

**Files:**
- Modify: `docs/architecture/plugin-composition-uplift-tracker.md`
- Modify: `docs/architecture/interfaces/secrets-plugin.md`
- Modify: `docs/architecture/interfaces/identity-plugin.md`
- Modify: `docs/architecture/interfaces/storage-plugin.md`
- Modify: `docs/architecture/interfaces/catalog-plugin.md`

- [ ] **Step 1: Update PCU-005 tracker**

In `docs/architecture/plugin-composition-uplift-tracker.md`, find the
`Secrets / identity` row in the immediate-priority table and replace it with:


```markdown
| Secrets / identity | 2 | PCU-005 implemented | Credential projection and workload identity modes are typed capabilities validated by the resolver |
```

In the Future Tracking Items table, update PCU-005 from:

```markdown
| PCU-005 | Security | Connect credential binding to identity/secrets plugins | Workload identity and external secret modes are resolver-validated |
```

to:

```markdown
| PCU-005 | Security | Connect credential binding to identity/secrets plugins | Implemented: workload identity and external secret modes are resolver-validated |
```

- [ ] **Step 2: Update secrets plugin interface docs**

In `docs/architecture/interfaces/secrets-plugin.md`, add this section after the interface introduction:

```markdown
## Composition Capabilities

Secrets plugins declare how they can project sensitive material into runtime
consumers without exposing secret values in compiled artifacts.

```python
def get_secret_capabilities(self) -> PluginCapabilities:
    """Return secret projection capabilities for composition validation."""
```

Supported projection modes:

| Mode | Meaning |
| --- | --- |
| `kubernetes-secret` | Runtime consumers reference existing or managed Kubernetes Secret keys. |
| `external-secret-sync` | A controller syncs external secret manager values into Kubernetes resources. |
| `csi-secret-volume` | Secrets are mounted through the Secrets Store CSI Driver or equivalent. |
| `environment` | Local or development environment variable projection. |

Capabilities are secret-free. Provider-specific fields such as Vault roles,
Infisical identity IDs, AWS Secret ARNs, or Azure Key Vault object names remain
in provider-owned configuration or deployment bindings.
```

- [ ] **Step 3: Update identity plugin interface docs**

In `docs/architecture/interfaces/identity-plugin.md`, add this section after the interface introduction:

```markdown
## Composition Capabilities

Identity plugins declare workload identity modes that selected storage,
catalog, compute, or runtime plugins can require.

```python
def get_identity_capabilities(self) -> PluginCapabilities:
    """Return workload identity capabilities for composition validation."""
```

Supported identity modes:

| Mode | Meaning |
| --- | --- |
| `aws-irsa` | EKS IAM Roles for Service Accounts. |
| `aws-pod-identity` | EKS Pod Identity association. |
| `gcp-workload-identity` | GKE Workload Identity Federation. |
| `azure-workload-identity` | Microsoft Entra Workload ID for AKS workloads. |
| `azure-managed-identity` | Azure managed identity used by AKS or provider integrations. |
| `oidc-federation` | Generic OIDC federation for services such as Keycloak or Snowflake WIF. |

Core validates the named modes and provider labels only. Provider plugins own
cloud-specific translation such as IAM role trust policies, GCP service account
bindings, Azure federated credentials, or OIDC issuer details.
```

- [ ] **Step 4: Update storage and catalog docs**

In `docs/architecture/interfaces/storage-plugin.md`, add a paragraph near the storage deployment binding section:

```markdown
Storage credential capabilities use the shared composition vocabulary.
`credential_modes` preserves broad compatibility (`kubernetes-secret`,
`external-secret-sync`, `csi-secret-volume`, `environment`,
`workload-identity`, `none`), while `secret_projection_modes` and
`identity_modes` describe how the credential mode is realized.
```

In `docs/architecture/interfaces/catalog-plugin.md`, add a paragraph near `get_storage_requirements()`:

```markdown
Catalog storage requirements may name required credential modes, secret
projection modes, identity modes, and provider labels. The composition resolver
validates these requirements against selected storage, secrets, and identity
plugins before deployment bindings are rendered.
```

- [ ] **Step 5: Run documentation checks**

Run:

```bash
uv run pre-commit run --files \
  docs/architecture/plugin-composition-uplift-tracker.md \
  docs/architecture/interfaces/secrets-plugin.md \
  docs/architecture/interfaces/identity-plugin.md \
  docs/architecture/interfaces/storage-plugin.md \
  docs/architecture/interfaces/catalog-plugin.md
```

Expected: hooks PASS.

- [ ] **Step 6: Commit Task 6**

```bash
git add \
  docs/architecture/plugin-composition-uplift-tracker.md \
  docs/architecture/interfaces/secrets-plugin.md \
  docs/architecture/interfaces/identity-plugin.md \
  docs/architecture/interfaces/storage-plugin.md \
  docs/architecture/interfaces/catalog-plugin.md
git commit -m "docs: describe identity and secret composition contract"
```

## Task 7: Final Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestResolvedPlugins \
  packages/floe-core/tests/unit/compilation/test_resolver.py \
  packages/floe-core/tests/unit/composition/test_resolver.py \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  plugins/floe-secrets-k8s/tests/unit/test_plugin.py::TestK8sSecretsPluginMetadata \
  plugins/floe-secrets-infisical/tests/unit/test_plugin.py::TestInfisicalSecretsPluginMetadata \
  plugins/floe-identity-keycloak/tests/unit/test_init.py::TestLazyImports \
  tests/contract/test_storage_binding_security.py \
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 2: Run lint and typecheck**

Run:

```bash
make lint
make typecheck
```

Expected: both commands PASS.

- [ ] **Step 3: Run unit test suite**

Run:

```bash
make test-unit
```

Expected: unit suite PASS.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git status --short
git diff --stat origin/main...HEAD
```

Expected: worktree is clean after commits; diff is limited to core composition, provider capability declarations, tests, and architecture docs.

- [ ] **Step 5: Prepare PR summary evidence**

Collect these facts for the PR body or handoff:

```text
Focused pytest: PASS
make lint: PASS
make typecheck: PASS
make test-unit: PASS
Security invariant: compiled artifacts and Helm values contain credential refs and mode names, not raw secret values
Compatibility invariant: MinIO plus Polaris Kubernetes Secret path remains valid without explicit secrets plugin
```
