# Composition Error Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace generic plugin composition `E201` and plain renderer `ValueError` failures with actionable `COMPOSITION_*` error codes.

**Architecture:** Keep `CompilationException` and `CompilationError` as the structured error surface. Add named `COMPOSITION_*` constants and map storage/catalog resolver, deployment-binding, and Helm renderer precondition failures to operator-action classes. Do not introduce a new plugin resolver or change successful MinIO/Polaris artifacts.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, Click CLI, existing Floe plugin registry and composition resolver.

---

## File Map

- Modify `packages/floe-core/src/floe_core/compilation/errors.py`: add public composition code constants and document them in `ERROR_CODES`.
- Modify `packages/floe-core/src/floe_core/compilation/stages.py`: remap storage/catalog composition failures from `E201` to specific `COMPOSITION_*` codes.
- Modify `packages/floe-core/src/floe_core/cli/helm/generate.py`: raise structured renderer precondition errors for artifact shapes Helm cannot render.
- Modify `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`: add regression tests for missing plugin, wrong interface, invalid config, and missing binding hooks.
- Modify `packages/floe-core/tests/unit/helm/test_generate_cli.py`: add regression tests for renderer precondition code.
- Modify `docs/contracts/compiled-artifacts.md`: document public composition codes and operator actions.

## Task 1: Add Public Composition Error Codes

**Files:**
- Modify: `packages/floe-core/src/floe_core/compilation/errors.py`
- Test: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`

- [ ] **Step 1: Write the failing taxonomy test**

Add this test near the top of `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`, after `pytestmark`:

```python
def test_composition_error_codes_are_documented() -> None:
    """Public composition failures must be listed for stable operator diagnostics."""
    from floe_core.compilation.errors import ERROR_CODES

    expected_codes = {
        "COMPOSITION_PLUGIN_MISSING",
        "COMPOSITION_PLUGIN_INTERFACE_INVALID",
        "COMPOSITION_PLUGIN_CONFIG_INVALID",
        "COMPOSITION_STORAGE_MISSING",
        "COMPOSITION_PROTOCOL_UNSUPPORTED",
        "COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
        "COMPOSITION_DEPLOYMENT_BINDING_MISSING",
        "COMPOSITION_RENDERER_PRECONDITION_FAILED",
    }

    assert expected_codes.issubset(ERROR_CODES)
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_composition_error_codes_are_documented -q
```

Expected: FAIL because the new `COMPOSITION_*` codes are not all in `ERROR_CODES`.

- [ ] **Step 3: Add constants and `ERROR_CODES` entries**

In `packages/floe-core/src/floe_core/compilation/errors.py`, add these constants above `ERROR_CODES`:

```python
# COMPOSITION_*: plugin resolution, compatibility, deployment binding, and renderer errors
COMPOSITION_PLUGIN_MISSING = "COMPOSITION_PLUGIN_MISSING"
COMPOSITION_PLUGIN_INTERFACE_INVALID = "COMPOSITION_PLUGIN_INTERFACE_INVALID"
COMPOSITION_PLUGIN_CONFIG_INVALID = "COMPOSITION_PLUGIN_CONFIG_INVALID"
COMPOSITION_STORAGE_MISSING = "COMPOSITION_STORAGE_MISSING"
COMPOSITION_PROTOCOL_UNSUPPORTED = "COMPOSITION_PROTOCOL_UNSUPPORTED"
COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED = "COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED"
COMPOSITION_DEPLOYMENT_BINDING_MISSING = "COMPOSITION_DEPLOYMENT_BINDING_MISSING"
COMPOSITION_RENDERER_PRECONDITION_FAILED = "COMPOSITION_RENDERER_PRECONDITION_FAILED"
```

Add these entries inside `ERROR_CODES` after the `E5xx` entries:

```python
    # COMPOSITION errors
    COMPOSITION_PLUGIN_MISSING: "Selected plugin could not be found or loaded",
    COMPOSITION_PLUGIN_INTERFACE_INVALID: "Selected plugin does not implement the required interface",
    COMPOSITION_PLUGIN_CONFIG_INVALID: "Selected plugin configuration or provider-owned binding is invalid",
    COMPOSITION_STORAGE_MISSING: "Storage-dependent plugin selected without storage plugin",
    COMPOSITION_PROTOCOL_UNSUPPORTED: "Selected plugins do not share a required protocol",
    COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED: "Selected plugins do not share a required credential mode",
    COMPOSITION_DEPLOYMENT_BINDING_MISSING: "Selected plugin does not provide the required deployment binding",
    COMPOSITION_RENDERER_PRECONDITION_FAILED: "Renderer cannot render the compiled artifact shape",
```

Update `__all__` to export the constants:

```python
    "COMPOSITION_PLUGIN_MISSING",
    "COMPOSITION_PLUGIN_INTERFACE_INVALID",
    "COMPOSITION_PLUGIN_CONFIG_INVALID",
    "COMPOSITION_STORAGE_MISSING",
    "COMPOSITION_PROTOCOL_UNSUPPORTED",
    "COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
    "COMPOSITION_DEPLOYMENT_BINDING_MISSING",
    "COMPOSITION_RENDERER_PRECONDITION_FAILED",
```

- [ ] **Step 4: Run the taxonomy test**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_composition_error_codes_are_documented -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add packages/floe-core/src/floe_core/compilation/errors.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py
git commit -m "feat: document composition error codes"
```

## Task 2: Remap Storage Plugin Composition Failures

**Files:**
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Modify: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`

- [ ] **Step 1: Update missing storage plugin test expectation**

In `test_missing_storage_plugin_raises_structured_compilation_error`, change:

```python
assert error.code == "E201"
```

to:

```python
assert error.code == "COMPOSITION_PLUGIN_MISSING"
```

- [ ] **Step 2: Update invalid storage config test expectation**

In `test_storage_plugin_binding_failure_raises_structured_compilation_error`, change:

```python
assert error.code == "E201"
```

to:

```python
assert error.code == "COMPOSITION_PLUGIN_CONFIG_INVALID"
```

- [ ] **Step 3: Add a wrong storage interface regression test**

Add this test after `test_missing_storage_plugin_raises_structured_compilation_error`:

```python
def test_wrong_storage_plugin_interface_raises_composition_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plugin loaded from storage selection must implement StoragePlugin."""

    class NotStoragePlugin:
        name = "minio"

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class WrongInterfaceRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> NotStoragePlugin:
            return NotStoragePlugin()

    monkeypatch.setattr(plugin_registry, "PluginRegistry", WrongInterfaceRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_PLUGIN_INTERFACE_INVALID"
    assert error.context == {"storage_plugin": "minio"}
```

- [ ] **Step 4: Add a missing storage deployment binding regression test**

Add this test after `test_storage_plugin_binding_failure_raises_structured_compilation_error`:

```python
def test_storage_plugin_missing_deployment_binding_raises_composition_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage plugins without deployment bindings must produce a specific code."""

    class LegacyStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "minio"

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
            return f"s3://unused/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class LegacyStorageRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> LegacyStoragePlugin:
            return LegacyStoragePlugin()

    monkeypatch.setattr(plugin_registry, "PluginRegistry", LegacyStorageRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_DEPLOYMENT_BINDING_MISSING"
    assert error.context == {"storage_plugin": "minio"}
```

- [ ] **Step 5: Run storage composition tests and verify failures**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py -q
```

Expected: FAIL on the updated/new error-code assertions.

- [ ] **Step 6: Implement storage plugin error mapping**

In `packages/floe-core/src/floe_core/compilation/stages.py`, change the local imports inside `_build_storage_deployment_binding()` to include constants and specific plugin errors:

```python
    from floe_core.compilation.errors import (
        COMPOSITION_DEPLOYMENT_BINDING_MISSING,
        COMPOSITION_PLUGIN_CONFIG_INVALID,
        COMPOSITION_PLUGIN_INTERFACE_INVALID,
        COMPOSITION_PLUGIN_MISSING,
        CompilationError,
        CompilationException,
    )
    from floe_core.plugin_errors import (
        PluginConfigurationError,
        PluginError,
        PluginNotFoundError,
    )
```

Replace the storage configure/get `except PluginError as exc:` block with:

```python
    except PluginConfigurationError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_CONFIG_INVALID,
                message=f"Storage plugin {plugins.storage.type!r} configuration is invalid",
                suggestion="Fix plugins.storage.config in the platform manifest",
                context={"storage_plugin": plugins.storage.type},
            )
        ) from exc
    except PluginNotFoundError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_MISSING,
                message=f"Storage plugin {plugins.storage.type!r} could not be resolved",
                suggestion=(
                    "Install the storage plugin package and verify "
                    "plugins.storage.type in the platform manifest"
                ),
                context={"storage_plugin": plugins.storage.type},
            )
        ) from exc
    except PluginError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_MISSING,
                message=f"Storage plugin {plugins.storage.type!r} could not be loaded",
                suggestion=(
                    "Install a compatible storage plugin package and verify "
                    "its entry point registration"
                ),
                context={"storage_plugin": plugins.storage.type},
            )
        ) from exc
```

Change the wrong interface branch to:

```python
                code=COMPOSITION_PLUGIN_INTERFACE_INVALID,
```

Replace the storage binding exception block with:

```python
    except NotImplementedError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_DEPLOYMENT_BINDING_MISSING,
                message=f"Storage plugin {plugins.storage.type!r} does not provide deployment binding",
                suggestion=(
                    "Upgrade or fix the storage plugin so it implements "
                    "get_deployment_binding()"
                ),
                context={"storage_plugin": plugins.storage.type},
            )
        ) from exc
    except PluginError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_CONFIG_INVALID,
                message=(
                    f"Storage plugin {plugins.storage.type!r} could not build deployment binding"
                ),
                suggestion=(
                    "Verify plugins.storage.config in the platform manifest and "
                    "ensure the storage plugin can build its deployment binding"
                ),
                context={"storage_plugin": plugins.storage.type},
            )
        ) from exc
```

- [ ] **Step 7: Run storage composition tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py -q
```

Expected: storage plugin code assertions PASS; catalog-specific assertions may still fail until Task 3.

- [ ] **Step 8: Commit Task 2**

```bash
git add packages/floe-core/src/floe_core/compilation/stages.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py
git commit -m "feat: classify storage composition failures"
```

## Task 3: Remap Catalog Composition Failures

**Files:**
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Modify: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`

- [ ] **Step 1: Add a missing catalog plugin regression test**

Add this test before `test_incompatible_storage_catalog_composition_raises_structured_error`:

```python
def test_missing_catalog_plugin_raises_composition_code(tmp_path: Path) -> None:
    """Catalog plugin resolution failures must identify missing catalog plugins."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"]["catalog"]["type"] = "missing-catalog"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_PLUGIN_MISSING"
    assert error.context == {"catalog_plugin": "missing-catalog"}
```

- [ ] **Step 2: Add a wrong catalog interface regression test**

Add this test after the missing catalog test:

```python
def test_wrong_catalog_plugin_interface_raises_composition_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plugin loaded from catalog selection must implement CatalogPlugin."""

    class MinimalStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "minio"

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
            return f"s3://unused/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> StorageDeploymentBinding:
            return _minimal_storage_binding()

    class NotCatalogPlugin:
        name = "polaris"

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class WrongCatalogRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> object:
            if plugin_type == PluginType.STORAGE:
                return MinimalStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return NotCatalogPlugin()
            raise AssertionError(f"unexpected plugin request: {plugin_type}:{name}")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", WrongCatalogRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_PLUGIN_INTERFACE_INVALID"
    assert error.context == {"catalog_plugin": "polaris"}
```

Add this helper near the top-level tests if it does not already exist:

```python
def _minimal_storage_binding() -> StorageDeploymentBinding:
    """Return a valid MinIO-like storage binding for catalog composition tests."""
    return StorageDeploymentBinding(
        provider="minio",
        protocol="s3-compatible",
        endpoint=StorageServiceEndpoint(
            internal_url="http://floe-platform-minio:9000",
            external_url="http://localhost:9000",
            region="us-east-1",
            warehouse_path="s3://floe-iceberg",
            path_style_access=True,
        ),
        credentials=StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name="floe-platform-minio-credentials",
                namespace="floe-system",
                keys={
                    "accessKeyId": "accesskey",
                    "secretAccessKey": "secretkey",  # pragma: allowlist secret
                },
            ),
        ),
        capabilities=StorageCapabilities(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            path_style_access=True,
        ),
        dbt=DbtStorageBinding(
            profile_name="floe",
            target_name="dev",
            schema_name="analytics",
        ),
        dagster=DagsterStorageBinding(
            resource_key="storage",
            asset_io_manager_key="io_manager",
        ),
    )
```

- [ ] **Step 3: Add missing catalog deployment binding regression test**

Add this test after the wrong catalog interface test:

```python
def test_catalog_plugin_missing_deployment_binding_raises_composition_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catalog plugins without deployment translators must produce a specific code."""

    class MinimalStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "minio"

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
            return f"s3://unused/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> StorageDeploymentBinding:
            return _minimal_storage_binding()

    class LegacyCatalogPlugin(CatalogPlugin):
        @property
        def name(self) -> str:
            return "polaris"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def connect(self, config: dict[str, Any]) -> Any:
            raise NotImplementedError

        def create_namespace(
            self,
            namespace: str,
            properties: dict[str, str] | None = None,
        ) -> None:
            raise NotImplementedError

        def vend_credentials(self, table_path: str, operations: list[str]) -> dict[str, Any]:
            raise NotImplementedError

        def list_namespaces(self, parent: str | None = None) -> list[str]:
            raise NotImplementedError

        def delete_namespace(self, namespace: str) -> None:
            raise NotImplementedError

        def create_table(
            self,
            identifier: str,
            schema: dict[str, Any],
            location: str | None = None,
            properties: dict[str, str] | None = None,
        ) -> None:
            raise NotImplementedError

        def list_tables(self, namespace: str) -> list[str]:
            raise NotImplementedError

        def drop_table(self, identifier: str, purge: bool = False) -> None:
            raise NotImplementedError

        def get_storage_requirements(self) -> PluginRequirements:
            return PluginRequirements(
                plugin_type="catalog",
                plugin_name="polaris",
                requirements=RequirementSet(
                    protocols=["s3-compatible"],
                    credential_modes=["kubernetes-secret"],
                ),
            )

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class LegacyCatalogRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> StoragePlugin | CatalogPlugin:
            if plugin_type == PluginType.STORAGE:
                return MinimalStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return LegacyCatalogPlugin()
            raise AssertionError(f"unexpected plugin request: {plugin_type}:{name}")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", LegacyCatalogRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_DEPLOYMENT_BINDING_MISSING"
    assert error.context == {"storage_plugin": "minio", "catalog_plugin": "polaris"}
```

- [ ] **Step 4: Run catalog tests and verify failures**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py -q
```

Expected: FAIL on catalog missing/interface/binding code assertions.

- [ ] **Step 5: Implement catalog plugin error mapping**

In `packages/floe-core/src/floe_core/compilation/stages.py`, replace the catalog configure/get `except PluginError as exc:` block with the same three-way classification used for storage, changing messages and contexts to catalog:

```python
    except PluginConfigurationError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_CONFIG_INVALID,
                message=f"Catalog plugin {plugins.catalog.type!r} configuration is invalid",
                suggestion="Fix plugins.catalog.config in the platform manifest",
                context={"catalog_plugin": plugins.catalog.type},
            )
        ) from exc
    except PluginNotFoundError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_MISSING,
                message=f"Catalog plugin {plugins.catalog.type!r} could not be resolved",
                suggestion=(
                    "Install the catalog plugin package and verify "
                    "plugins.catalog.type in the platform manifest"
                ),
                context={"catalog_plugin": plugins.catalog.type},
            )
        ) from exc
    except PluginError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_MISSING,
                message=f"Catalog plugin {plugins.catalog.type!r} could not be loaded",
                suggestion=(
                    "Install a compatible catalog plugin package and verify "
                    "its entry point registration"
                ),
                context={"catalog_plugin": plugins.catalog.type},
            )
        ) from exc
```

Change the wrong catalog interface branch to:

```python
                code=COMPOSITION_PLUGIN_INTERFACE_INVALID,
```

Replace the final catalog deployment `except (PluginError, NotImplementedError, ValueError) as exc:` block with:

```python
    except NotImplementedError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_DEPLOYMENT_BINDING_MISSING,
                message=(
                    f"Catalog plugin {plugins.catalog.type!r} does not provide deployment binding"
                ),
                suggestion=(
                    "Upgrade or fix the catalog plugin so it implements "
                    "get_storage_requirements() and build_catalog_deployment()"
                ),
                context={
                    "storage_plugin": plugins.storage.type,
                    "catalog_plugin": plugins.catalog.type,
                },
            )
        ) from exc
    except (PluginError, ValueError) as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code=COMPOSITION_PLUGIN_CONFIG_INVALID,
                message=(
                    f"Catalog plugin {plugins.catalog.type!r} could not build deployment binding"
                ),
                suggestion=(
                    "Verify plugins.catalog.config and ensure the catalog plugin can "
                    "translate the selected storage deployment binding"
                ),
                context={
                    "storage_plugin": plugins.storage.type,
                    "catalog_plugin": plugins.catalog.type,
                    "error": str(exc),
                },
            )
        ) from exc
```

- [ ] **Step 6: Run compilation and resolver tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add packages/floe-core/src/floe_core/compilation/stages.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py
git commit -m "feat: classify catalog composition failures"
```

## Task 4: Add Structured Helm Renderer Preconditions

**Files:**
- Modify: `packages/floe-core/src/floe_core/cli/helm/generate.py`
- Modify: `packages/floe-core/tests/unit/helm/test_generate_cli.py`

- [ ] **Step 1: Add renderer precondition import in tests**

In `packages/floe-core/tests/unit/helm/test_generate_cli.py`, change:

```python
from floe_core.cli.helm.generate import _storage_helm_values, generate_command
```

to:

```python
from floe_core.cli.helm.generate import _storage_helm_values, generate_command
from floe_core.compilation.errors import CompilationException
```

- [ ] **Step 2: Update existing missing Polaris credential ref test**

In `test_storage_helm_values_reject_missing_polaris_credential_ref`, replace:

```python
with pytest.raises(ValueError, match="secretAccessKey"):
    _storage_helm_values(artifacts)
```

with:

```python
with pytest.raises(CompilationException) as exc_info:
    _storage_helm_values(artifacts)

error = exc_info.value.error
assert error.code == "COMPOSITION_RENDERER_PRECONDITION_FAILED"
assert "secretAccessKey" in error.message
```

- [ ] **Step 3: Add renderer precondition tests**

Add these tests after `test_storage_helm_values_reject_missing_polaris_credential_ref`:

```python
@pytest.mark.requirement("9b-FR-060")
def test_storage_helm_values_reject_missing_catalog_binding(self, tmp_path: Path) -> None:
    """MinIO Helm rendering requires a catalog deployment binding."""
    artifact_file = tmp_path / "compiled_artifacts.json"
    _write_minio_artifact(artifact_file)
    artifacts = CompiledArtifacts.from_json_file(artifact_file)
    assert artifacts.deployment is not None
    artifacts = artifacts.model_copy(
        update={"deployment": artifacts.deployment.model_copy(update={"catalog": None})}
    )

    with pytest.raises(CompilationException) as exc_info:
        _storage_helm_values(artifacts)

    error = exc_info.value.error
    assert error.code == "COMPOSITION_RENDERER_PRECONDITION_FAILED"
    assert "catalog deployment binding" in error.message


@pytest.mark.requirement("9b-FR-060")
def test_storage_helm_values_reject_missing_bucket_requirements(
    self, tmp_path: Path
) -> None:
    """MinIO Helm rendering requires bucket requirements in the storage binding."""
    artifact_file = tmp_path / "compiled_artifacts.json"
    _write_minio_artifact(artifact_file)
    artifacts = CompiledArtifacts.from_json_file(artifact_file)
    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    storage = artifacts.deployment.storage.model_copy(update={"buckets": []})
    artifacts = artifacts.model_copy(
        update={"deployment": artifacts.deployment.model_copy(update={"storage": storage})}
    )

    with pytest.raises(CompilationException) as exc_info:
        _storage_helm_values(artifacts)

    error = exc_info.value.error
    assert error.code == "COMPOSITION_RENDERER_PRECONDITION_FAILED"
    assert "bucket requirements" in error.message
```

- [ ] **Step 4: Run Helm tests and verify failures**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py::TestHelmGenerateCommand::test_storage_helm_values_reject_missing_polaris_credential_ref packages/floe-core/tests/unit/helm/test_generate_cli.py::TestHelmGenerateCommand::test_storage_helm_values_reject_missing_catalog_binding packages/floe-core/tests/unit/helm/test_generate_cli.py::TestHelmGenerateCommand::test_storage_helm_values_reject_missing_bucket_requirements -q
```

Expected: FAIL because `_storage_helm_values()` still raises `ValueError`.

- [ ] **Step 5: Implement renderer precondition helper**

In `packages/floe-core/src/floe_core/cli/helm/generate.py`, add imports:

```python
from floe_core.compilation.errors import (
    COMPOSITION_RENDERER_PRECONDITION_FAILED,
    CompilationError,
    CompilationException,
)
from floe_core.compilation.stages import CompilationStage
```

Add this helper after `_load_compiled_artifacts()`:

```python
def _renderer_precondition_failed(
    message: str,
    *,
    context: dict[str, Any] | None = None,
) -> CompilationException:
    """Build a structured Helm renderer precondition failure."""
    return CompilationException(
        CompilationError(
            stage=CompilationStage.GENERATE,
            code=COMPOSITION_RENDERER_PRECONDITION_FAILED,
            message=message,
            suggestion="Recompile with required deployment bindings or fix the artifact before rendering.",
            context=context,
        )
    )
```

Replace every `raise ValueError(msg)` in `_storage_helm_values()`, `_require_kubernetes_secret_ref()`, and `_minio_storage_helm_values()` with:

```python
raise _renderer_precondition_failed(msg)
```

For provider-specific branches, include context:

```python
raise _renderer_precondition_failed(
    msg,
    context={"storage_provider": storage.provider, "catalog_provider": catalog.provider},
)
```

- [ ] **Step 6: Run Helm tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add packages/floe-core/src/floe_core/cli/helm/generate.py packages/floe-core/tests/unit/helm/test_generate_cli.py
git commit -m "feat: classify helm renderer preconditions"
```

## Task 5: Document Taxonomy and Run Validation

**Files:**
- Modify: `docs/contracts/compiled-artifacts.md`

- [ ] **Step 1: Add public taxonomy docs**

In `docs/contracts/compiled-artifacts.md`, after the `Rules:` list under `## Deployment Bindings`, add:

```markdown
### Composition Error Codes

Plugin composition diagnostics use `COMPOSITION_*` codes. These codes are
operator-facing and map to the action needed to fix the platform selection or
compiled artifact. Legacy numeric `E*` codes remain valid for broader
compilation stages outside plugin composition.

| Code | Meaning | Operator action |
| --- | --- | --- |
| `COMPOSITION_PLUGIN_MISSING` | A selected plugin cannot be found or loaded. | Install the plugin package or fix the manifest plugin type. |
| `COMPOSITION_PLUGIN_INTERFACE_INVALID` | A registry entry does not implement the required plugin interface. | Register the plugin under the correct entry point group or fix the plugin class. |
| `COMPOSITION_PLUGIN_CONFIG_INVALID` | A plugin exists but its config or provider-owned binding is invalid. | Fix the plugin config in `manifest.yaml`. |
| `COMPOSITION_STORAGE_MISSING` | A storage-dependent plugin was selected without a storage plugin. | Select a storage plugin or remove the storage-dependent consumer. |
| `COMPOSITION_PROTOCOL_UNSUPPORTED` | Selected plugins do not share a required storage protocol. | Choose compatible storage/catalog providers or adjust provider config. |
| `COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED` | Selected plugins do not share a required credential mode. | Choose compatible credential modes or update provider config. |
| `COMPOSITION_DEPLOYMENT_BINDING_MISSING` | A selected plugin does not emit the required typed deployment binding. | Upgrade or fix the plugin implementation. |
| `COMPOSITION_RENDERER_PRECONDITION_FAILED` | A renderer cannot render the compiled artifact shape. | Recompile with required deployment bindings or fix the artifact before rendering. |
```

- [ ] **Step 2: Run focused validation**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py packages/floe-core/tests/unit/helm/test_generate_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run standard touched-surface checks**

Run:

```bash
make lint
make typecheck
make test-unit
```

Expected: PASS for all three commands. If a command fails, inspect the exact failure, fix only failures caused by this branch, and rerun the failed command.

- [ ] **Step 4: Commit Task 5**

```bash
git add docs/contracts/compiled-artifacts.md
git commit -m "docs: list composition error taxonomy"
```

- [ ] **Step 5: Report final state**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: clean working tree except intentionally untracked local artifacts, and recent commits for the design, plan if committed, taxonomy, storage mapping, catalog mapping, renderer preconditions, and docs.
