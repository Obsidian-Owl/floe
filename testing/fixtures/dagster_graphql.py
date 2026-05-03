"""Dagster GraphQL helper utilities for tests."""

from __future__ import annotations

from typing import Any, Protocol

from gql import GraphQLRequest, gql


class _GqlClient(Protocol):
    """Subset of ``gql.Client`` required by Dagster GraphQL tests."""

    def execute(self, request: GraphQLRequest) -> dict[str, Any]:
        """Execute a prepared GraphQL request."""


class _DagsterGraphQLClient(Protocol):
    """Subset of ``DagsterGraphQLClient`` required by this helper."""

    _client: _GqlClient


def execute_dagster_graphql_request(
    dagster_client: _DagsterGraphQLClient,
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
    if not isinstance(result, dict):
        msg = f"Dagster GraphQL returned non-dict result: {type(result)}"
        raise TypeError(msg)
    return result
