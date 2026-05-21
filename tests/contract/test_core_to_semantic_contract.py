"""Contract tests for CompiledArtifacts.plugins.semantic round-trip.

These tests validate that the semantic plugin reference in CompiledArtifacts
can be serialized and deserialized correctly, ensuring cross-package
compatibility between floe-core and floe-semantic-cube.

This is a contract test (tests/contract/) because it validates the
CompiledArtifacts schema stability for the semantic field.

Requirements Covered:
    - SC-006: CompiledArtifacts.plugins.semantic round-trip integrity
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from floe_core.schemas.compiled_artifacts import (
    CompiledArtifacts,
    DeploymentConfig,
    PluginRef,
    ResolvedPlugins,
    SemanticDeploymentBinding,
    SemanticPublicationBinding,
)
from pydantic import ValidationError

GOLDEN_SEMANTIC_FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "golden"
    / "v0.5_compiled_artifacts_with_semantic.json"
)


class TestSemanticPluginRefRoundTrip:
    """Contract tests for PluginRef with type='cube'."""

    @pytest.mark.requirement("SC-006")
    def test_plugin_ref_cube_type_accepted(self) -> None:
        """Test that PluginRef accepts type='cube' for semantic layer."""
        ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={"server_url": "http://cube:4000"},
        )
        assert ref.type == "cube"
        assert ref.version == "0.1.0"
        assert ref.config == {"server_url": "http://cube:4000"}

    @pytest.mark.requirement("SC-006")
    def test_serialize_deserialize_preserves_fields(self) -> None:
        """Test that JSON round-trip preserves all PluginRef fields."""
        ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={
                "server_url": "http://cube:4000",
                "database_name": "analytics",
                "health_check_timeout": 5.0,
            },
        )
        json_str = ref.model_dump_json()
        restored = PluginRef.model_validate_json(json_str)

        assert restored.type == ref.type
        assert restored.version == ref.version
        assert restored.config == ref.config

    @pytest.mark.requirement("SC-006")
    def test_cube_specific_config_round_trips(self) -> None:
        """Test that Cube-specific configuration survives round-trip."""
        cube_config: dict[str, Any] = {
            "server_url": "https://cube.prod.example.com",
            "database_name": "warehouse",
            "health_check_timeout": 10.0,
            "model_filter_tags": ["analytics", "cube"],
            "model_filter_schemas": ["gold"],
        }
        ref = PluginRef(type="cube", version="0.1.0", config=cube_config)
        data = ref.model_dump()
        restored = PluginRef.model_validate(data)
        assert restored.config == cube_config


class TestResolvedPluginsSemanticField:
    """Contract tests for ResolvedPlugins.semantic field."""

    @pytest.mark.requirement("SC-006")
    def test_semantic_none_by_default(self) -> None:
        """Test that semantic field defaults to None."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
        )
        assert plugins.semantic is None

    @pytest.mark.requirement("SC-006")
    def test_semantic_none_serializes_correctly(self) -> None:
        """Test that None semantic field serializes and deserializes."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=None,
        )
        data = plugins.model_dump()
        restored = ResolvedPlugins.model_validate(data)
        assert restored.semantic is None

    @pytest.mark.requirement("SC-006")
    def test_semantic_with_cube_ref(self) -> None:
        """Test that semantic field accepts a Cube PluginRef."""
        cube_ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={"server_url": "http://cube:4000"},
        )
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=cube_ref,
        )
        assert plugins.semantic is not None
        assert plugins.semantic.type == "cube"

    @pytest.mark.requirement("SC-006")
    def test_semantic_round_trip_in_resolved_plugins(self) -> None:
        """Test full round-trip of ResolvedPlugins with semantic set."""
        cube_ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={"database_name": "analytics"},
        )
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=cube_ref,
        )
        json_str = plugins.model_dump_json()
        restored = ResolvedPlugins.model_validate_json(json_str)
        assert restored.semantic is not None
        assert restored.semantic.type == "cube"
        assert restored.semantic.config == {"database_name": "analytics"}


class TestSemanticDeploymentDesiredStateContract:
    """Contract tests for provider-neutral deployment.semantic desired state."""

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    def test_semantic_env_refs_reject_raw_secret_values(self) -> None:
        """Contract: env maps carry environment variable names, not raw secrets."""
        with pytest.raises(ValidationError) as exc_info:
            SemanticDeploymentBinding(
                provider="semantic-provider",
                datasources=[
                    {
                        "name": "warehouse",
                        "driver": "duckdb",
                        "env_refs": {"api_token": "raw-secret-value"},  # pragma: allowlist secret
                    }
                ],
            )

        assert "environment variable name" in str(exc_info.value)

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    def test_semantic_config_maps_reject_raw_secret_values(self) -> None:
        """Contract: config maps carry desired configuration, not raw credentials."""
        with pytest.raises(ValidationError) as exc_info:
            SemanticDeploymentBinding(
                provider="semantic-provider",
                service_endpoints=[
                    {
                        "name": "internal",
                        "url": "https://semantic.internal",
                        "config": {"api_secret": "raw-secret-value"},  # pragma: allowlist secret
                    }
                ],
            )

        assert "raw credential material" in str(exc_info.value)

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    @pytest.mark.parametrize(
        "publication",
        [
            SemanticPublicationBinding(enabled=False, policy="disabled"),
            SemanticPublicationBinding(enabled=False, policy="manual"),
            SemanticPublicationBinding(enabled=True, policy="manual"),
            SemanticPublicationBinding(enabled=True, policy="publish-on-change"),
            SemanticPublicationBinding(enabled=True, policy="publish-on-deploy"),
        ],
    )
    def test_semantic_publication_accepts_consistent_policy(
        self,
        publication: SemanticPublicationBinding,
    ) -> None:
        """Contract: publication enabled flag and policy agree."""
        binding = SemanticDeploymentBinding(
            provider="semantic-provider",
            publication=publication,
        )

        assert binding.publication == publication

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    @pytest.mark.parametrize(
        ("enabled", "policy"),
        [
            (False, "publish-on-change"),
            (False, "publish-on-deploy"),
            (True, "disabled"),
        ],
    )
    def test_semantic_publication_rejects_contradictory_policy(
        self,
        enabled: bool,
        policy: str,
    ) -> None:
        """Contract: disabled publication cannot request active publication."""
        with pytest.raises(ValidationError) as exc_info:
            SemanticPublicationBinding(enabled=enabled, policy=policy)  # type: ignore[arg-type]

        assert "semantic publication policy contradicts enabled" in str(exc_info.value)

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    def test_semantic_api_endpoint_name_must_reference_service_endpoint(self) -> None:
        """Contract: API bindings reference declared service endpoints."""
        with pytest.raises(ValidationError) as exc_info:
            SemanticDeploymentBinding(
                provider="semantic-provider",
                service_endpoints=[
                    {"name": "internal", "url": "https://semantic.internal"},
                ],
                apis=[
                    {"family": "sql", "endpoint_name": "missing"},
                ],
            )

        assert "semantic.api.endpoint_name" in str(exc_info.value)
        assert "unknown service endpoint" in str(exc_info.value)

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    def test_semantic_api_endpoint_name_accepts_declared_service_endpoint(self) -> None:
        """Contract: API bindings accept known service endpoint names."""
        binding = SemanticDeploymentBinding(
            provider="semantic-provider",
            service_endpoints=[
                {"name": "internal", "url": "https://semantic.internal"},
            ],
            apis=[
                {"family": "sql", "endpoint_name": "internal"},
            ],
        )

        assert binding.apis[0].endpoint_name == "internal"

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    def test_semantic_publication_artifact_names_must_reference_artifacts(self) -> None:
        """Contract: publication artifact names reference declared artifacts."""
        with pytest.raises(ValidationError) as exc_info:
            SemanticDeploymentBinding(
                provider="semantic-provider",
                artifacts=[
                    {
                        "name": "semantic-models",
                        "mount_path": "/var/lib/floe/semantic",
                        "format": "semantic-model",
                    }
                ],
                publication=SemanticPublicationBinding(
                    enabled=True,
                    policy="publish-on-change",
                    artifact_names=["missing"],
                ),
            )

        assert "semantic.publication.artifact_names" in str(exc_info.value)
        assert "unknown semantic artifact" in str(exc_info.value)

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    def test_semantic_publication_artifact_names_accept_declared_artifacts(self) -> None:
        """Contract: publication artifact names accept known artifact names."""
        binding = SemanticDeploymentBinding(
            provider="semantic-provider",
            artifacts=[
                {
                    "name": "semantic-models",
                    "mount_path": "/var/lib/floe/semantic",
                    "format": "semantic-model",
                }
            ],
            publication=SemanticPublicationBinding(
                enabled=True,
                policy="publish-on-change",
                artifact_names=["semantic-models"],
            ),
        )

        assert binding.publication is not None
        assert binding.publication.artifact_names == ["semantic-models"]

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    @pytest.mark.parametrize(
        ("runtime_key", "semantic_payload"),
        [
            ("schema_artifacts", {"config": {"schema_artifacts": []}}),
            ("query_results", {"config": {"query_results": []}}),
            ("health_status", {"config": {"health_status": "ok"}}),
            ("generated_files", {"config": {"generated_files": []}}),
            ("schemaArtifacts", {"config": {"schemaArtifacts": []}}),
            ("query-results", {"config": {"query-results": []}}),
        ],
    )
    def test_semantic_deployment_rejects_runtime_evidence_fields(
        self,
        runtime_key: str,
        semantic_payload: dict[str, Any],
    ) -> None:
        """Contract: deployment.semantic config maps reject runtime evidence fields."""
        with pytest.raises(ValidationError) as exc_info:
            DeploymentConfig(
                semantic=SemanticDeploymentBinding(
                    provider="semantic-provider",
                    **semantic_payload,
                )
            )

        assert runtime_key in str(exc_info.value)
        assert "runtime evidence" in str(exc_info.value)

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    @pytest.mark.parametrize(
        ("expected_path", "semantic_payload"),
        [
            ("semantic.config.health_status", {"config": {"health_status": "ok"}}),
            (
                "semantic.datasource.config.query_results",
                {
                    "datasources": [
                        {
                            "name": "warehouse",
                            "driver": "duckdb",
                            "config": {"query_results": []},
                        }
                    ]
                },
            ),
            (
                "semantic.artifact.config.schema_artifacts",
                {
                    "artifacts": [
                        {
                            "name": "semantic-models",
                            "mount_path": "/var/lib/floe/semantic",
                            "format": "semantic-model",
                            "config": {"schema_artifacts": []},
                        }
                    ]
                },
            ),
        ],
    )
    def test_semantic_config_maps_reject_runtime_evidence_keys(
        self,
        expected_path: str,
        semantic_payload: dict[str, Any],
    ) -> None:
        """Contract: semantic config maps cannot smuggle runtime evidence."""
        with pytest.raises(ValidationError) as exc_info:
            SemanticDeploymentBinding(provider="semantic-provider", **semantic_payload)

        assert expected_path in str(exc_info.value)
        assert "runtime evidence" in str(exc_info.value)

    @pytest.mark.requirement("SEMANTIC-CONTRACT-002")
    def test_golden_fixture_uses_provider_neutral_semantic_desired_state(self) -> None:
        """Contract: golden semantic fixture validates without provider endpoint leakage."""
        raw_fixture = GOLDEN_SEMANTIC_FIXTURE.read_text(encoding="utf-8")

        assert "cubejs-api" not in raw_fixture
        assert "http://cube" not in raw_fixture
        assert "CUBEJS_" not in raw_fixture

        fixture = json.loads(raw_fixture)
        fixture_without_comment = {
            key: value for key, value in fixture.items() if key != "$comment"
        }
        artifacts = CompiledArtifacts.model_validate(fixture_without_comment)

        assert artifacts.deployment is not None
        assert artifacts.deployment.semantic is not None
        assert artifacts.deployment.semantic.provider == "semantic-provider"
