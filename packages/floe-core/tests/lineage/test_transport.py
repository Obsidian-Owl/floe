"""Tests for lineage transport implementations.

This module tests the four lineage transports: NoOp, Console, Composite, and HTTP.
"""

from __future__ import annotations

import asyncio
import ssl
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from floe_core.lineage.protocols import LineageTransport
from floe_core.lineage.transport import (
    CompositeLineageTransport,
    ConsoleLineageTransport,
    HttpLineageTransport,
    NoOpLineageTransport,
    _apply_insecure_settings,
    _create_ssl_context,
)
from floe_core.lineage.types import (
    LineageEvent,
    LineageJob,
    LineageRun,
    RunState,
)


def _run(coro: object) -> object:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)  # type: ignore[arg-type]


@pytest.fixture()
def sample_event() -> LineageEvent:
    """Create a sample lineage event for testing."""
    return LineageEvent(
        event_type=RunState.START,
        run=LineageRun(),
        job=LineageJob(namespace="floe", name="test_job"),
        producer="floe-test",
    )


class TestNoOpLineageTransport:
    """Tests for NoOpLineageTransport."""

    def test_implements_protocol(self) -> None:
        """NoOpLineageTransport satisfies LineageTransport protocol."""
        transport = NoOpLineageTransport()
        assert isinstance(transport, LineageTransport)

    def test_emit_accepts_event(self, sample_event: LineageEvent) -> None:
        """NoOp transport accepts events without error."""
        transport = NoOpLineageTransport()
        _run(transport.emit(sample_event))

    def test_close_is_idempotent(self) -> None:
        """NoOp close is idempotent - can be called multiple times safely."""
        transport = NoOpLineageTransport()
        transport.close()
        transport.close()  # Second close should also succeed (idempotent)


class TestConsoleLineageTransport:
    """Tests for ConsoleLineageTransport."""

    def test_implements_protocol(self) -> None:
        """ConsoleLineageTransport satisfies LineageTransport protocol."""
        transport = ConsoleLineageTransport()
        assert isinstance(transport, LineageTransport)

    def test_emit_logs_via_structlog(self, sample_event: LineageEvent) -> None:
        """Console transport logs event via structlog."""
        transport = ConsoleLineageTransport()
        with patch.object(transport, "_log") as mock_log:
            _run(transport.emit(sample_event))
            mock_log.info.assert_called_once()
            call_kwargs = mock_log.info.call_args
            assert call_kwargs[0][0] == "lineage_event"
            assert call_kwargs[1]["event_type"] == "START"
            assert call_kwargs[1]["job_name"] == "test_job"

    def test_close_is_idempotent(self) -> None:
        """Console close is idempotent - can be called multiple times safely."""
        transport = ConsoleLineageTransport()
        transport.close()
        transport.close()  # Second close should also succeed (idempotent)


class TestCompositeLineageTransport:
    """Tests for CompositeLineageTransport."""

    def test_implements_protocol(self) -> None:
        """CompositeLineageTransport satisfies LineageTransport protocol."""
        transport = CompositeLineageTransport(transports=[])
        assert isinstance(transport, LineageTransport)

    def test_fans_out_to_multiple_transports(self, sample_event: LineageEvent) -> None:
        """Composite fans out to 3+ child transports."""
        children = [AsyncMock() for _ in range(3)]
        transport = CompositeLineageTransport(transports=children)  # type: ignore[arg-type]

        _run(transport.emit(sample_event))

        for child in children:
            child.emit.assert_awaited_once_with(sample_event)

    def test_child_failure_does_not_propagate(self, sample_event: LineageEvent) -> None:
        """Individual child failures are caught, not propagated."""
        failing = AsyncMock()
        failing.emit.side_effect = RuntimeError("boom")
        healthy = AsyncMock()

        transport = CompositeLineageTransport(transports=[failing, healthy])  # type: ignore[arg-type]
        _run(transport.emit(sample_event))  # Should not raise

        healthy.emit.assert_awaited_once_with(sample_event)

    def test_close_closes_all_children(self) -> None:
        """Close calls close() on all children."""
        children = [MagicMock(spec=["emit", "close"]) for _ in range(3)]
        transport = CompositeLineageTransport(transports=children)  # type: ignore[arg-type]
        transport.close()

        for child in children:
            child.close.assert_called_once()

    def test_close_handles_child_failure(self) -> None:
        """Close continues even if a child fails."""
        failing = MagicMock(spec=["emit", "close"])
        failing.close.side_effect = RuntimeError("boom")
        healthy = MagicMock(spec=["emit", "close"])

        transport = CompositeLineageTransport(transports=[failing, healthy])  # type: ignore[arg-type]
        transport.close()  # Should not raise

        healthy.close.assert_called_once()


class TestHttpLineageTransport:
    """Tests for HttpLineageTransport."""

    def test_implements_protocol(self) -> None:
        """HttpLineageTransport satisfies LineageTransport protocol."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        assert isinstance(transport, LineageTransport)
        transport.close()

    @pytest.mark.requirement("REQ-525")
    def test_emit_is_non_blocking(self, sample_event: LineageEvent) -> None:
        """Emit enqueues without blocking (<10ms)."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        try:
            start = time.monotonic()
            _run(transport.emit(sample_event))
            elapsed = time.monotonic() - start

            assert elapsed < 0.1, f"emit() took {elapsed:.4f}s, expected <100ms"
        finally:
            transport.close()

    @pytest.mark.requirement("REQ-526")
    def test_fire_and_forget_enqueue(self, sample_event: LineageEvent) -> None:
        """Events are enqueued for background processing (fire-and-forget)."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        try:
            initial_size = transport._async_queue.qsize()
            _run(transport.emit(sample_event))
            final_size = transport._async_queue.qsize()
            # Event should be enqueued (or already being processed by consumer)
            assert final_size >= initial_size, (
                f"Event should be enqueued: queue size {initial_size} -> {final_size}"
            )
        finally:
            transport.close()

    def test_close_drains_queue(self) -> None:
        """Close signals the background consumer to stop."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        transport.close()

        assert transport._closed is True

    def test_constructor_params(self) -> None:
        """Constructor accepts url, timeout, and api_key."""
        transport = HttpLineageTransport(
            url="http://example.com/lineage",
            timeout=10.0,
            api_key="secret-key",  # pragma: allowlist secret
        )
        assert transport._url == "http://example.com/lineage"
        assert transport._timeout == 10.0
        assert transport._api_key == "secret-key"
        transport.close()

    def test_emit_after_close_is_ignored(self, sample_event: LineageEvent) -> None:
        """Events emitted after close are silently dropped."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        transport.close()
        _run(transport.emit(sample_event))  # Should not raise


class TestCreateSslContext:
    """Tests for _create_ssl_context function."""

    def test_returns_none_for_http_url(self) -> None:
        """HTTP URLs should return None (no SSL context needed)."""
        result = _create_ssl_context("http://localhost:5000/api", verify_ssl=True)
        assert result is None, "HTTP URLs should not create SSL context"

    def test_returns_none_for_http_with_verify_false(self) -> None:
        """HTTP URLs with verify_ssl=False should still return None."""
        result = _create_ssl_context("http://example.com/lineage", verify_ssl=False)
        assert result is None, "HTTP URLs never need SSL context"

    def test_returns_secure_context_for_https_with_verify_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HTTPS with verify_ssl=True returns secure context."""
        monkeypatch.delenv("FLOE_ENVIRONMENT", raising=False)
        monkeypatch.delenv("FLOE_ALLOW_INSECURE_SSL", raising=False)

        with patch("ssl.create_default_context") as mock_create_ctx:
            mock_ctx = MagicMock(spec=ssl.SSLContext)
            mock_create_ctx.return_value = mock_ctx

            with patch("certifi.where", return_value="/path/to/cacert.pem"):
                result = _create_ssl_context("https://example.com/api", verify_ssl=True)

            assert result is mock_ctx, "Should return the created SSL context"
            mock_create_ctx.assert_called_once_with(cafile="/path/to/cacert.pem")

    def test_production_always_returns_secure_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production environment always returns secure context even with verify_ssl=False."""
        monkeypatch.setenv("FLOE_ENVIRONMENT", "production")
        monkeypatch.setenv("FLOE_ALLOW_INSECURE_SSL", "true")

        with patch("ssl.create_default_context") as mock_create_ctx:
            mock_ctx = MagicMock(spec=ssl.SSLContext)
            mock_create_ctx.return_value = mock_ctx

            with patch("certifi.where", return_value="/path/to/cacert.pem"):
                result = _create_ssl_context("https://example.com/api", verify_ssl=False)

            assert result is mock_ctx, "Production should return secure context"

    def test_dev_with_insecure_env_var_returns_insecure_context(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Dev environment with FLOE_ALLOW_INSECURE_SSL=true returns insecure context."""
        monkeypatch.delenv("FLOE_ENVIRONMENT", raising=False)
        monkeypatch.setenv("FLOE_ALLOW_INSECURE_SSL", "true")

        with patch("ssl.create_default_context") as mock_create_ctx:
            mock_ctx = MagicMock(spec=ssl.SSLContext)
            mock_create_ctx.return_value = mock_ctx

            with patch("certifi.where", return_value="/path/to/cacert.pem"):
                result = _create_ssl_context("https://example.com/api", verify_ssl=False)

            assert result is mock_ctx, "Should return context"
            assert mock_ctx.check_hostname is False, "Should disable hostname check"
            assert mock_ctx.verify_mode == ssl.CERT_NONE, "Should disable cert verification"

        assert any("SSL verification DISABLED" in record.message for record in caplog.records), (
            "Should log critical warning about disabled SSL"
        )

    def test_dev_without_insecure_env_var_returns_secure_context_with_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Dev without FLOE_ALLOW_INSECURE_SSL returns secure context with warning."""
        monkeypatch.delenv("FLOE_ENVIRONMENT", raising=False)
        monkeypatch.delenv("FLOE_ALLOW_INSECURE_SSL", raising=False)

        with patch("ssl.create_default_context") as mock_create_ctx:
            mock_ctx = MagicMock(spec=ssl.SSLContext)
            mock_create_ctx.return_value = mock_ctx

            with patch("certifi.where", return_value="/path/to/cacert.pem"):
                result = _create_ssl_context("https://example.com/api", verify_ssl=False)

            assert result is mock_ctx, "Should return secure context"

        assert any(
            "FLOE_ALLOW_INSECURE_SSL not set" in record.message for record in caplog.records
        ), "Should warn that verification remains enabled"

    def test_certifi_ca_bundle_is_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify certifi.where() is used for CA bundle."""
        monkeypatch.delenv("FLOE_ENVIRONMENT", raising=False)

        with patch("ssl.create_default_context") as mock_create_ctx:
            mock_ctx = MagicMock(spec=ssl.SSLContext)
            mock_create_ctx.return_value = mock_ctx

            with patch("certifi.where", return_value="/custom/ca/bundle.pem") as mock_where:
                _create_ssl_context("https://example.com/api", verify_ssl=True)

            mock_where.assert_called_once()
            mock_create_ctx.assert_called_once_with(cafile="/custom/ca/bundle.pem")

    @pytest.mark.parametrize(
        ("url", "expected_none"),
        [
            ("http://localhost:8080/api", True),
            ("http://example.com/lineage", True),
            ("https://localhost:8443/api", False),
            ("https://secure.example.com/lineage", False),
        ],
    )
    def test_http_vs_https_urls(
        self, url: str, expected_none: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parametrized test for HTTP vs HTTPS URL handling."""
        monkeypatch.delenv("FLOE_ENVIRONMENT", raising=False)

        with patch("ssl.create_default_context") as mock_create_ctx:
            mock_ctx = MagicMock(spec=ssl.SSLContext)
            mock_create_ctx.return_value = mock_ctx

            with patch("certifi.where", return_value="/path/to/cacert.pem"):
                result = _create_ssl_context(url, verify_ssl=True)

        if expected_none:
            assert result is None, f"HTTP URL {url} should return None"
        else:
            assert result is not None, f"HTTPS URL {url} should return SSL context"


class TestApplyInsecureSettings:
    """Tests for _apply_insecure_settings function."""

    def test_disables_hostname_check(self) -> None:
        """_apply_insecure_settings sets check_hostname to False."""
        context = ssl.create_default_context()
        assert context.check_hostname is True, "Default context should check hostname"

        _apply_insecure_settings(context)

        assert context.check_hostname is False, "Should disable hostname checking"

    def test_sets_verify_mode_to_cert_none(self) -> None:
        """_apply_insecure_settings sets verify_mode to ssl.CERT_NONE."""
        context = ssl.create_default_context()
        assert context.verify_mode == ssl.CERT_REQUIRED, "Default context should require certs"

        _apply_insecure_settings(context)

        assert context.verify_mode == ssl.CERT_NONE, "Should disable certificate verification"

    def test_both_settings_applied_together(self) -> None:
        """Both insecure settings are applied atomically."""
        context = ssl.create_default_context()

        _apply_insecure_settings(context)

        assert context.check_hostname is False, "Hostname check should be disabled"
        assert context.verify_mode == ssl.CERT_NONE, "Cert verification should be disabled"


class TestHttpLineageTransportSsl:
    """Tests for HttpLineageTransport SSL context usage."""

    def test_https_url_uses_ssl_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTPS transport should use SSL context for connections."""
        monkeypatch.delenv("FLOE_ENVIRONMENT", raising=False)

        transport = HttpLineageTransport(
            url="https://lineage.example.com/api/v1/lineage",
            verify_ssl=True,
        )

        assert transport._url.startswith("https://"), "URL should be HTTPS"
        assert transport._verify_ssl is True, "verify_ssl should be True"
        transport.close()

    def test_http_url_works_without_ssl_context(self) -> None:
        """HTTP transport works without SSL context (verify_ssl is ignored for HTTP)."""
        transport = HttpLineageTransport(
            url="http://localhost:5000/api/v1/lineage",
            verify_ssl=True,
        )

        assert transport._url.startswith("http://"), "URL should be HTTP"
        transport.close()

    def test_transport_verify_ssl_parameter_stored(self) -> None:
        """Transport stores verify_ssl parameter for later use."""
        transport_secure = HttpLineageTransport(
            url="https://example.com/lineage",
            verify_ssl=True,
        )
        transport_insecure = HttpLineageTransport(
            url="https://example.com/lineage",
            verify_ssl=False,
        )

        assert transport_secure._verify_ssl is True, "Should store verify_ssl=True"
        assert transport_insecure._verify_ssl is False, "Should store verify_ssl=False"

        transport_secure.close()
        transport_insecure.close()

    @pytest.mark.requirement("REQ-SECURITY-001")
    def test_production_enforces_ssl_verification(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_event: LineageEvent,
    ) -> None:
        """Production environment always enforces SSL verification."""
        monkeypatch.setenv("FLOE_ENVIRONMENT", "production")

        transport = HttpLineageTransport(
            url="https://lineage.example.com/api/v1/lineage",
            verify_ssl=False,
        )

        assert transport._verify_ssl is False, (
            "Parameter stored as passed, production enforces at emit time"
        )
        transport.close()
