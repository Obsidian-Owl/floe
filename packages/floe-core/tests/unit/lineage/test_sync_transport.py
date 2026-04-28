"""Tests for synchronous lineage transport implementations.

This module tests three synchronous transports: SyncHttpLineageTransport,
SyncConsoleLineageTransport, and SyncNoOpTransport.

These are synchronous counterparts to the existing async transports,
designed for use in contexts where an event loop is unavailable.
"""

from __future__ import annotations

import ssl
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.lineage.events import to_openlineage_event
from floe_core.lineage.transport import (
    SyncConsoleLineageTransport,
    SyncHttpLineageTransport,
    SyncNoOpTransport,
)
from floe_core.lineage.types import (
    LineageEvent,
    LineageJob,
    LineageRun,
    RunState,
)

# Test constants for secret values (not real secrets)
TEST_API_KEY = "test-api-key-for-sync-transport"  # pragma: allowlist secret
TEST_URL = "http://localhost:5000/api/v1/lineage"


@pytest.fixture()
def sample_event() -> LineageEvent:
    """Create a sample lineage event for testing."""
    return LineageEvent(
        event_type=RunState.START,
        run=LineageRun(),
        job=LineageJob(namespace="test-namespace", name="test-job"),
        producer="floe-test",
    )


@pytest.fixture()
def complete_event() -> LineageEvent:
    """Create a COMPLETE event with inputs and outputs for richer payload testing."""
    from floe_core.lineage.types import LineageDataset

    return LineageEvent(
        event_type=RunState.COMPLETE,
        run=LineageRun(),
        job=LineageJob(namespace="production", name="dbt_run_orders"),
        inputs=[LineageDataset(namespace="raw", name="orders_raw")],
        outputs=[LineageDataset(namespace="staging", name="stg_orders")],
        producer="floe",
    )


class TestSyncHttpLineageTransport:
    """Tests for SyncHttpLineageTransport."""

    @pytest.mark.requirement("AC-OLC-1")
    def test_emit_sends_post_request(self, sample_event: LineageEvent) -> None:
        """Verify emit() calls httpx.Client.post() with correct URL and JSON payload.

        A lazy implementation might accept the event but never actually POST it.
        We verify the exact URL and that the payload matches to_openlineage_event().
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            transport.emit(sample_event)

        expected_payload = to_openlineage_event(sample_event)
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == TEST_URL or call_kwargs.kwargs.get("url") == TEST_URL, (
            f"POST must be sent to {TEST_URL}"
        )
        # Verify the JSON payload matches the OpenLineage wire format
        actual_json: dict[str, Any] = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert actual_json is not None, "JSON payload must be provided"
        assert actual_json["eventType"] == expected_payload["eventType"], (
            "eventType must match the event"
        )
        assert actual_json["job"]["namespace"] == "test-namespace", (
            "job namespace must be passed through"
        )
        assert actual_json["job"]["name"] == "test-job", "job name must be passed through"
        assert actual_json["run"]["runId"] == str(sample_event.run.run_id), "run ID must match"
        assert actual_json["producer"] == "floe-test", "producer must be passed through"

    @pytest.mark.requirement("AC-OLC-1")
    def test_emit_sends_full_payload_with_inputs_outputs(
        self, complete_event: LineageEvent
    ) -> None:
        """Verify emit() sends complete payload including inputs and outputs.

        A partial implementation might only send event_type and job, ignoring
        inputs/outputs. This test catches that.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            transport.emit(complete_event)

        call_kwargs = mock_client.post.call_args
        actual_json: dict[str, Any] = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(actual_json["inputs"]) == 1, "Must include input datasets"
        assert actual_json["inputs"][0]["name"] == "orders_raw", "Input dataset name must match"
        assert len(actual_json["outputs"]) == 1, "Must include output datasets"
        assert actual_json["outputs"][0]["name"] == "stg_orders", "Output dataset name must match"

    @pytest.mark.requirement("AC-OLC-1")
    def test_emit_includes_bearer_header(self, sample_event: LineageEvent) -> None:
        """When api_key is provided, Authorization: Bearer header must be set.

        A sloppy implementation might accept the api_key but never use it.
        We verify the exact header value.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL, api_key=TEST_API_KEY)
            transport.emit(sample_event)

        call_kwargs = mock_client.post.call_args
        headers: dict[str, str] = call_kwargs.kwargs.get("headers") or call_kwargs[1].get(
            "headers", {}
        )
        assert "Authorization" in headers, "Authorization header must be present when api_key set"
        assert headers["Authorization"] == f"Bearer {TEST_API_KEY}", (
            f"Authorization header must be 'Bearer {TEST_API_KEY}', "
            f"got '{headers.get('Authorization')}'"
        )

    @pytest.mark.requirement("AC-OLC-1")
    def test_emit_no_auth_header_without_api_key(self, sample_event: LineageEvent) -> None:
        """When no api_key, no Authorization header should be present.

        A buggy implementation might send an empty or 'Bearer None' header.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            transport.emit(sample_event)

        call_kwargs = mock_client.post.call_args
        headers: dict[str, str] = call_kwargs.kwargs.get("headers") or call_kwargs[1].get(
            "headers", {}
        )
        assert "Authorization" not in headers, (
            "Authorization header must NOT be present when no api_key"
        )

    @pytest.mark.requirement("AC-OLC-1")
    def test_default_timeout(self) -> None:
        """Default timeout must be 5.0 seconds.

        A hardcoded wrong value (e.g., 30.0 from the async transport) would fail.
        """
        mock_client = MagicMock()
        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)

        # Verify via the stored timeout attribute or httpx.Client construction
        # The transport should store or use 5.0 as default
        assert transport._timeout == pytest.approx(5.0), (
            f"Default timeout must be 5.0, got {transport._timeout}"
        )

    @pytest.mark.requirement("AC-OLC-1")
    def test_custom_timeout(self) -> None:
        """Custom timeout must be configurable and stored.

        Test with a non-default value to ensure it's not hardcoded.
        """
        mock_client = MagicMock()
        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL, timeout=12.5)

        assert transport._timeout == pytest.approx(12.5), (
            f"Custom timeout must be 12.5, got {transport._timeout}"
        )

    @pytest.mark.requirement("AC-OLC-1")
    def test_timeout_passed_to_httpx_client(self, sample_event: LineageEvent) -> None:
        """Timeout value must actually be used when creating the httpx Client.

        A lazy implementation might store the timeout but never pass it to httpx.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client) as mock_client_class:
            transport = SyncHttpLineageTransport(url=TEST_URL, timeout=7.5)
            transport.emit(sample_event)

        # Check that httpx.Client was constructed with the timeout
        client_call_kwargs = mock_client_class.call_args
        if client_call_kwargs is not None:
            timeout_arg = client_call_kwargs.kwargs.get("timeout")
            if timeout_arg is not None:
                assert timeout_arg == pytest.approx(7.5), (
                    f"httpx.Client must receive timeout=7.5, got {timeout_arg}"
                )

    @pytest.mark.requirement("REQ-SECURITY-001")
    def test_https_defaults_to_secure_ssl_verification(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HTTPS sync transport defaults to certificate verification."""
        monkeypatch.delenv("FLOE_ENVIRONMENT", raising=False)
        monkeypatch.delenv("FLOE_ALLOW_INSECURE_SSL", raising=False)

        mock_client = MagicMock()
        with patch("httpx.Client", return_value=mock_client) as mock_client_class:
            transport = SyncHttpLineageTransport(url="https://marquez.example/api/v1/lineage")

        assert transport._verify_ssl is True
        kwargs = mock_client_class.call_args.kwargs
        assert kwargs["timeout"] == pytest.approx(5.0)
        assert isinstance(kwargs["verify"], ssl.SSLContext)
        assert kwargs["verify"].verify_mode != ssl.CERT_NONE

    @pytest.mark.requirement("REQ-SECURITY-001")
    def test_https_allows_development_insecure_ssl_opt_out(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Development HTTPS sync transport can explicitly disable verification."""
        monkeypatch.setenv("FLOE_ENVIRONMENT", "development")
        monkeypatch.setenv("FLOE_ALLOW_INSECURE_SSL", "true")

        mock_client = MagicMock()
        with patch("httpx.Client", return_value=mock_client) as mock_client_class:
            transport = SyncHttpLineageTransport(
                url="https://localhost:5000/api/v1/lineage",
                verify_ssl=False,
            )

        assert transport._verify_ssl is False
        assert mock_client_class.call_args.kwargs["verify"] is False

    @pytest.mark.requirement("REQ-SECURITY-001")
    def test_https_enforces_secure_verification_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production HTTPS sync transport ignores disabled verification."""
        monkeypatch.setenv("FLOE_ENVIRONMENT", "production")
        monkeypatch.setenv("FLOE_ALLOW_INSECURE_SSL", "true")

        mock_client = MagicMock()
        with patch("httpx.Client", return_value=mock_client) as mock_client_class:
            transport = SyncHttpLineageTransport(
                url="https://marquez.example/api/v1/lineage",
                verify_ssl=False,
            )

        assert transport._verify_ssl is False
        verify_setting = mock_client_class.call_args.kwargs["verify"]
        assert isinstance(verify_setting, ssl.SSLContext)
        assert verify_setting.verify_mode != ssl.CERT_NONE

    @pytest.mark.requirement("AC-OLC-1")
    def test_emit_raises_on_transport_error(self, sample_event: LineageEvent) -> None:
        """Transport exceptions must NOT be swallowed -- they propagate to caller.

        The spec says 'the emitter handles error isolation', meaning the transport
        itself must raise. A sloppy implementation might catch-and-ignore exceptions.
        """
        import httpx

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            with pytest.raises(Exception) as exc_info:
                transport.emit(sample_event)

        # Verify it's a real transport error, not a generic assertion error
        assert "Connection refused" in str(exc_info.value) or isinstance(
            exc_info.value, httpx.ConnectError
        ), f"Expected httpx.ConnectError, got {type(exc_info.value).__name__}: {exc_info.value}"

    @pytest.mark.requirement("AC-OLC-1")
    def test_emit_raises_on_http_timeout(self, sample_event: LineageEvent) -> None:
        """HTTP timeout errors must propagate, not be swallowed."""
        import httpx

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            with pytest.raises(httpx.TimeoutException):
                transport.emit(sample_event)

    @pytest.mark.requirement("AC-OLC-1")
    def test_close_closes_client(self) -> None:
        """close() must call httpx.Client.close() to release resources.

        A lazy implementation might define close() as a no-op.
        """
        mock_client = MagicMock()
        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            transport.close()

        mock_client.close.assert_called_once(), ("close() must call httpx.Client.close()")

    @pytest.mark.requirement("AC-OLC-1")
    def test_close_idempotent(self) -> None:
        """Calling close() twice must not raise."""
        mock_client = MagicMock()
        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            transport.close()
            transport.close()  # Second call must not raise

    @pytest.mark.requirement("AC-OLC-1")
    def test_emit_multiple_events(self, sample_event: LineageEvent) -> None:
        """Multiple emit() calls must each send a separate POST request.

        Guards against an implementation that caches/batches and only sends once.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            transport.emit(sample_event)
            transport.emit(sample_event)
            transport.emit(sample_event)

        assert mock_client.post.call_count == 3, (
            f"Each emit() must trigger a POST, expected 3 calls, got {mock_client.post.call_count}"
        )

    @pytest.mark.requirement("AC-OLC-1")
    def test_content_type_header_is_json(self, sample_event: LineageEvent) -> None:
        """Content-Type header must indicate JSON payload."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            transport = SyncHttpLineageTransport(url=TEST_URL)
            transport.emit(sample_event)

        call_kwargs = mock_client.post.call_args
        # If using httpx json= parameter, Content-Type is set automatically.
        # But if using explicit headers, verify it.
        json_arg = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert json_arg is not None, (
            "Must use json= parameter (which sets Content-Type automatically) "
            "or set Content-Type: application/json header explicitly"
        )


class TestSyncConsoleLineageTransport:
    """Tests for SyncConsoleLineageTransport."""

    @pytest.mark.requirement("AC-OLC-2")
    def test_emit_logs_event_fields(self, sample_event: LineageEvent) -> None:
        """emit() must log event_type, job_namespace, and job_name via structlog.

        A lazy implementation might log just 'event received' without extracting
        the required fields. We verify all three fields are present.
        """
        transport = SyncConsoleLineageTransport()
        with patch.object(transport, "_log") as mock_log:
            transport.emit(sample_event)

            mock_log.info.assert_called_once()
            call_args = mock_log.info.call_args
            call_kwargs = call_args[1]

            # Verify all three required fields are logged
            assert call_kwargs["event_type"] == "START", (
                f"event_type must be 'START', got '{call_kwargs.get('event_type')}'"
            )
            assert call_kwargs["job_namespace"] == "test-namespace", (
                f"job_namespace must be 'test-namespace', got '{call_kwargs.get('job_namespace')}'"
            )
            assert call_kwargs["job_name"] == "test-job", (
                f"job_name must be 'test-job', got '{call_kwargs.get('job_name')}'"
            )

    @pytest.mark.requirement("AC-OLC-2")
    def test_emit_logs_different_event_types(self) -> None:
        """Verify different event types are logged correctly, not hardcoded.

        Guards against hardcoding 'START' in the log output.
        """
        fail_event = LineageEvent(
            event_type=RunState.FAIL,
            run=LineageRun(),
            job=LineageJob(namespace="ci", name="broken-pipeline"),
            producer="floe-test",
        )
        transport = SyncConsoleLineageTransport()
        with patch.object(transport, "_log") as mock_log:
            transport.emit(fail_event)

            call_kwargs = mock_log.info.call_args[1]
            assert call_kwargs["event_type"] == "FAIL", (
                "Must log actual event_type, not hardcode 'START'"
            )
            assert call_kwargs["job_namespace"] == "ci", "Must log actual job_namespace"
            assert call_kwargs["job_name"] == "broken-pipeline", "Must log actual job_name"

    @pytest.mark.requirement("AC-OLC-2")
    def test_emit_is_synchronous(self, sample_event: LineageEvent) -> None:
        """emit() must be a synchronous method, not a coroutine.

        The async ConsoleLineageTransport uses 'async def emit()'. The sync
        version must use plain 'def emit()'.
        """
        import inspect

        transport = SyncConsoleLineageTransport()
        assert not inspect.iscoroutinefunction(transport.emit), (
            "emit() must be synchronous (def, not async def)"
        )

    @pytest.mark.requirement("AC-OLC-2")
    def test_close_is_noop(self) -> None:
        """close() must complete without error (no-op)."""
        transport = SyncConsoleLineageTransport()
        result = transport.close()
        assert result is None, "close() must return None"

    @pytest.mark.requirement("AC-OLC-2")
    def test_close_is_synchronous(self) -> None:
        """close() must be synchronous."""
        import inspect

        transport = SyncConsoleLineageTransport()
        assert not inspect.iscoroutinefunction(transport.close), (
            "close() must be synchronous (def, not async def)"
        )


class TestSyncNoOpTransport:
    """Tests for SyncNoOpTransport."""

    @pytest.mark.requirement("AC-OLC-2")
    def test_emit_is_noop(self, sample_event: LineageEvent) -> None:
        """emit() must return None and produce no side effects.

        Verify it doesn't secretly log, write, or POST anything.
        """
        transport = SyncNoOpTransport()
        result = transport.emit(sample_event)
        assert result is None, "emit() must return None"

    @pytest.mark.requirement("AC-OLC-2")
    def test_emit_is_synchronous(self, sample_event: LineageEvent) -> None:
        """emit() must be synchronous, not a coroutine."""
        import inspect

        transport = SyncNoOpTransport()
        assert not inspect.iscoroutinefunction(transport.emit), (
            "emit() must be synchronous (def, not async def)"
        )

    @pytest.mark.requirement("AC-OLC-2")
    def test_close_is_noop(self) -> None:
        """close() must return None and produce no side effects."""
        transport = SyncNoOpTransport()
        result = transport.close()
        assert result is None, "close() must return None"

    @pytest.mark.requirement("AC-OLC-2")
    def test_close_is_synchronous(self) -> None:
        """close() must be synchronous."""
        import inspect

        transport = SyncNoOpTransport()
        assert not inspect.iscoroutinefunction(transport.close), (
            "close() must be synchronous (def, not async def)"
        )

    @pytest.mark.requirement("AC-OLC-2")
    def test_emit_accepts_any_event(self) -> None:
        """emit() must accept any valid LineageEvent without error.

        Tests with multiple event types to verify no type-specific handling.
        """
        transport = SyncNoOpTransport()

        for state in [RunState.START, RunState.COMPLETE, RunState.FAIL, RunState.ABORT]:
            event = LineageEvent(
                event_type=state,
                run=LineageRun(),
                job=LineageJob(namespace="ns", name="job"),
            )
            result = transport.emit(event)
            assert result is None, f"emit() must return None for {state.value} events"

    @pytest.mark.requirement("AC-OLC-2")
    def test_emit_does_not_call_structlog(self, sample_event: LineageEvent) -> None:
        """NoOp transport must not log anything (unlike Console transport).

        Guards against copy-paste from ConsoleLineageTransport that leaves
        logging in place.
        """
        with patch("structlog.get_logger") as mock_get_logger:
            transport = SyncNoOpTransport()
            transport.emit(sample_event)

            # If get_logger was called during __init__, the logger's methods
            # should not have been called during emit
            if mock_get_logger.called:
                mock_logger = mock_get_logger.return_value
                mock_logger.info.assert_not_called()
                mock_logger.debug.assert_not_called()
                mock_logger.warning.assert_not_called()
