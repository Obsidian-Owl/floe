"""Unit tests for Polaris duplicate grant response handling in E2E fixtures."""

from __future__ import annotations

import logging

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


def test_duplicate_grant_context_suppresses_expected_httpx_info_noise() -> None:
    """Expected duplicate-grant retries should not print scary httpx 500 lines."""
    from tests.e2e.conftest import _suppress_httpx_info_logs

    httpx_logger = logging.getLogger("httpx")
    original_level = httpx_logger.level
    try:
        httpx_logger.setLevel(logging.INFO)
        with _suppress_httpx_info_logs():
            assert httpx_logger.level == logging.WARNING
        assert httpx_logger.level == logging.INFO
    finally:
        httpx_logger.setLevel(original_level)


def test_duplicate_grant_fixture_log_messages_avoid_http_500_text() -> None:
    """Known duplicate-grant info messages should not contain literal HTTP 500."""
    from pathlib import Path

    source = Path("tests/e2e/conftest.py").read_text(encoding="utf-8")

    assert "duplicate grant record, HTTP 500" not in source
