"""Dagster GraphQL helper utilities for tests."""

from __future__ import annotations

from typing import Any

from gql import GraphQLRequest, gql


def execute_dagster_graphql_request(
    dagster_client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute an arbitrary Dagster GraphQL query without deprecated gql kwargs.

    DagsterGraphQLClient exposes arbitrary query execution through its private
    ``_execute`` helper, but that path passes ``variable_values`` to
    ``gql.Client.execute`` as deprecated kwargs. Constructing ``GraphQLRequest``
    directly keeps variable values on the request object, matching gql's current
    API while preserving the existing Dagster test fixture.
    """
    request = GraphQLRequest(gql(query), variable_values=variables)
    result = dagster_client._client.execute(request)
    assert isinstance(result, dict), f"Dagster GraphQL returned non-dict result: {type(result)}"
    return result
