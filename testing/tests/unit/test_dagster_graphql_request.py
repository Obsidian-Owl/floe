"""Tests for non-deprecated Dagster GraphQL request execution helpers."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest
from gql import Client, GraphQLRequest
from gql.transport.local_schema import LocalSchemaTransport
from graphql import build_schema

from testing.fixtures import execute_dagster_graphql_request

_REPO_ROOT = Path(__file__).resolve().parents[3]


class _FakeGraphQLClient:
    """Capture raw gql client calls made through the Dagster wrapper."""

    def __init__(self, result: Any = None) -> None:
        self.result = {"ok": True} if result is None else result
        self.calls: list[tuple[GraphQLRequest, dict[str, Any]]] = []

    def execute(self, request: GraphQLRequest, **kwargs: Any) -> Any:
        self.calls.append((request, kwargs))
        return self.result


class _FakeDagsterClient:
    """Minimal shape of DagsterGraphQLClient needed by the helper."""

    def __init__(self, result: Any = None) -> None:
        self._client: Any
        self._client = _FakeGraphQLClient(result)


@pytest.mark.requirement("15-FR-007")
def test_execute_dagster_graphql_request_places_variables_on_request() -> None:
    """Avoid gql's deprecated execute(variable_values=...) call shape."""
    dagster_client = _FakeDagsterClient()

    result = execute_dagster_graphql_request(
        dagster_client,
        "query GetSensors($repoSelector: RepositorySelector!) { __typename }",
        {"repoSelector": {"repositoryName": "repo", "repositoryLocationName": "location"}},
    )

    assert result == {"ok": True}
    [(request, kwargs)] = dagster_client._client.calls
    assert isinstance(request, GraphQLRequest)
    assert request.variable_values == {
        "repoSelector": {"repositoryName": "repo", "repositoryLocationName": "location"}
    }
    assert kwargs == {}


@pytest.mark.requirement("15-FR-007")
def test_execute_dagster_graphql_request_emits_no_gql_deprecation_warning() -> None:
    """Exercise gql.Client.execute with variables using the current request API."""
    dagster_client = _FakeDagsterClient()
    dagster_client._client = Client(
        transport=LocalSchemaTransport(build_schema("type Query { ok: Boolean! }")),
        fetch_schema_from_transport=False,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = execute_dagster_graphql_request(
            dagster_client,
            "query Test($includeTypename: Boolean!) { __typename @include(if: $includeTypename) }",
            {"includeTypename": True},
        )

    assert result == {"__typename": "Query"}
    assert not [
        warning
        for warning in caught
        if "GraphQLRequest" in str(warning.message)
        or "variable_values and operation_name" in str(warning.message)
    ]


@pytest.mark.requirement("15-FR-007")
def test_execute_dagster_graphql_request_rejects_non_dict_results() -> None:
    """Non-object GraphQL responses should fail under optimized Python too."""
    dagster_client = _FakeDagsterClient(result=["not", "a", "dict"])

    with pytest.raises(TypeError, match="Dagster GraphQL returned non-dict result"):
        execute_dagster_graphql_request(dagster_client, "{ __typename }")


@pytest.mark.requirement("15-FR-007")
def test_data_pipeline_sensor_query_uses_graphql_request_helper() -> None:
    """The E2E sensor query must not call Dagster's deprecated private wrapper."""
    source = (_REPO_ROOT / "tests/e2e/test_data_pipeline.py").read_text()

    assert "execute_dagster_graphql_request(dagster_client, sensor_query, variables)" in source
    assert "dagster_client._execute(sensor_query, variables)" not in source
