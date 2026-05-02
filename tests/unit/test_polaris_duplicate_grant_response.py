"""Unit tests for Polaris duplicate grant response handling in E2E fixtures."""

from __future__ import annotations

import httpx


def test_duplicate_polaris_grant_500_matches_helm_bootstrap_signature() -> None:
    """The E2E fixture should treat duplicate grant records like Helm bootstrap."""
    from tests.e2e.conftest import _is_duplicate_polaris_grant_response

    response = httpx.Response(
        500,
        text="duplicate key value violates unique constraint grant_records_pkey; sql-state '23505'",
    )

    assert _is_duplicate_polaris_grant_response(response) is True


def test_duplicate_polaris_grant_helper_rejects_unexpected_500() -> None:
    """Unexpected Polaris HTTP 500 responses must remain visible."""
    from tests.e2e.conftest import _is_duplicate_polaris_grant_response

    response = httpx.Response(500, text="database unavailable")

    assert _is_duplicate_polaris_grant_response(response) is False
