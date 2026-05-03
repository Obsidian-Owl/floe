"""Tests for non-deprecated Dagster GraphQL request execution helpers."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from gql import Client, GraphQLRequest
from gql.transport.local_schema import LocalSchemaTransport
from graphql import build_schema

from testing.fixtures.dagster_graphql import execute_dagster_graphql_request


class _FakeGraphQLClient:
    """Capture raw gql client calls made through the Dagster wrapper."""

    def __init__(self) -> None:
        self.calls: list[tuple[GraphQLRequest, dict[str, Any]]] = []

    def execute(self, request: GraphQLRequest, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((request, kwargs))
        return {"ok": True}


class _FakeDagsterClient:
    """Minimal shape of DagsterGraphQLClient needed by the helper."""

    def __init__(self) -> None:
        self._client: Any
        self._client = _FakeGraphQLClient()


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


def test_data_pipeline_sensor_query_uses_graphql_request_helper() -> None:
    """The E2E sensor query must not call Dagster's deprecated private wrapper."""
    source = Path("tests/e2e/test_data_pipeline.py").read_text()

    assert "execute_dagster_graphql_request(dagster_client, sensor_query, variables)" in source
    assert "dagster_client._execute(sensor_query, variables)" not in source
