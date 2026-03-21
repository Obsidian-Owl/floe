"""Unit tests for port resolution utilities.

Tests for SERVICE_DEFAULT_PORTS, _get_effective_port(), and get_effective_port()
in testing.fixtures.services module.

These tests verify the port resolution precedence chain:
  1. Environment variable {SERVICE_NAME}_PORT
  2. Explicit default parameter
  3. SERVICE_DEFAULT_PORTS lookup
  4. ValueError if none found
"""

from __future__ import annotations

import pytest

from testing.fixtures.services import (
    SERVICE_DEFAULT_PORTS,
    _get_effective_port,
    get_effective_port,
)

# ---------------------------------------------------------------------------
# AC-1: SERVICE_DEFAULT_PORTS dict exists with specific entries
# ---------------------------------------------------------------------------


class TestServiceDefaultPorts:
    """Tests for the SERVICE_DEFAULT_PORTS constant."""

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_dagster_webserver_port(self) -> None:
        """Test dagster-webserver defaults to port 3000."""
        assert SERVICE_DEFAULT_PORTS["dagster-webserver"] == 3000

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_dagster_port(self) -> None:
        """Test dagster defaults to port 3000."""
        assert SERVICE_DEFAULT_PORTS["dagster"] == 3000

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_polaris_port(self) -> None:
        """Test polaris defaults to port 8181."""
        assert SERVICE_DEFAULT_PORTS["polaris"] == 8181

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_polaris_management_port(self) -> None:
        """Test polaris-management defaults to port 8182."""
        assert SERVICE_DEFAULT_PORTS["polaris-management"] == 8182

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_minio_port(self) -> None:
        """Test minio defaults to port 9000."""
        assert SERVICE_DEFAULT_PORTS["minio"] == 9000

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_minio_console_port(self) -> None:
        """Test minio-console defaults to port 9001."""
        assert SERVICE_DEFAULT_PORTS["minio-console"] == 9001

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_postgres_port(self) -> None:
        """Test postgres defaults to port 5432."""
        assert SERVICE_DEFAULT_PORTS["postgres"] == 5432

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_jaeger_query_port(self) -> None:
        """Test jaeger-query defaults to port 16686."""
        assert SERVICE_DEFAULT_PORTS["jaeger-query"] == 16686

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_otel_collector_grpc_port(self) -> None:
        """Test otel-collector-grpc defaults to port 4317."""
        assert SERVICE_DEFAULT_PORTS["otel-collector-grpc"] == 4317

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_otel_collector_http_port(self) -> None:
        """Test otel-collector-http defaults to port 4318."""
        assert SERVICE_DEFAULT_PORTS["otel-collector-http"] == 4318

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_marquez_port_is_5100_not_5000(self) -> None:
        """Test marquez defaults to port 5100, NOT 5000.

        This is a critical correctness check. Port 5000 is used by
        oci-registry and registry. Marquez historically used 5000 but
        the spec requires 5100. A sloppy implementation that defaults
        marquez to 5000 would silently collide with the OCI registry.
        """
        assert SERVICE_DEFAULT_PORTS["marquez"] == 5100
        assert SERVICE_DEFAULT_PORTS["marquez"] != 5000

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_oci_registry_port(self) -> None:
        """Test oci-registry defaults to port 5000."""
        assert SERVICE_DEFAULT_PORTS["oci-registry"] == 5000

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_registry_port(self) -> None:
        """Test registry defaults to port 5000."""
        assert SERVICE_DEFAULT_PORTS["registry"] == 5000

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_all_expected_services_present(self) -> None:
        """Test that all 13 required services are present in the dict.

        Guards against partial implementations that include only a subset.
        """
        expected_services = {
            "dagster-webserver",
            "dagster",
            "polaris",
            "polaris-management",
            "minio",
            "minio-console",
            "postgres",
            "jaeger-query",
            "otel-collector-grpc",
            "otel-collector-http",
            "marquez",
            "oci-registry",
            "registry",
        }
        assert expected_services.issubset(set(SERVICE_DEFAULT_PORTS.keys()))

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_all_ports_are_integers(self) -> None:
        """Test that all port values are integers, not strings or floats."""
        for service_name, port in SERVICE_DEFAULT_PORTS.items():
            assert isinstance(port, int), (
                f"Port for {service_name} is {type(port).__name__}, expected int"
            )

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_all_ports_in_valid_range(self) -> None:
        """Test that all port values are in the valid TCP range 1-65535."""
        for service_name, port in SERVICE_DEFAULT_PORTS.items():
            assert 1 <= port <= 65535, f"Port {port} for {service_name} is outside valid range"


# ---------------------------------------------------------------------------
# AC-2: _get_effective_port() precedence
# ---------------------------------------------------------------------------


class TestGetEffectivePortPrecedence:
    """Tests for _get_effective_port() precedence chain."""

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_env_var_takes_highest_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env var overrides both explicit default and dict default.

        Precedence level 1: {SERVICE_NAME}_PORT env var wins over everything.
        """
        monkeypatch.setenv("POLARIS_PORT", "9999")
        result = _get_effective_port("polaris", default=1111)
        assert result == 9999

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_explicit_default_overrides_dict(self) -> None:
        """Test that explicit default parameter overrides SERVICE_DEFAULT_PORTS.

        Precedence level 2: explicit default beats dict lookup.
        Polaris has dict default 8181, but explicit default=7777 should win.
        """
        result = _get_effective_port("polaris", default=7777)
        assert result == 7777

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_dict_default_used_when_no_env_or_explicit(self) -> None:
        """Test that SERVICE_DEFAULT_PORTS is used as last resort before error.

        Precedence level 3: dict lookup when no env var and no explicit default.
        """
        result = _get_effective_port("polaris")
        assert result == 8181

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_raises_valueerror_when_no_port_found(self) -> None:
        """Test ValueError when service has no env var, no default, no dict entry.

        Precedence level 4: ValueError with helpful message.
        """
        with pytest.raises(ValueError, match="UNKNOWN_THING_PORT"):
            _get_effective_port("unknown-thing")

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_error_message_contains_known_services(self) -> None:
        """Test that ValueError message lists known services to help the user."""
        with pytest.raises(ValueError, match="polaris") as exc_info:
            _get_effective_port("nonexistent-service")
        # Should mention at least some known services
        error_msg = str(exc_info.value)
        assert "dagster" in error_msg or "SERVICE_DEFAULT_PORTS" in error_msg

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_empty_env_var_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that empty string env var is treated as not set.

        Setting POLARIS_PORT="" should NOT use the empty string; it should
        fall through to the next precedence level.
        """
        monkeypatch.setenv("POLARIS_PORT", "")
        result = _get_effective_port("polaris")
        assert result == 8181

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_empty_env_var_falls_to_explicit_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test empty env var falls through to explicit default, not dict."""
        monkeypatch.setenv("POLARIS_PORT", "")
        result = _get_effective_port("polaris", default=7777)
        assert result == 7777

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_env_var_name_uses_uppercase_and_underscores(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that hyphenated service names map to underscore env vars.

        'otel-collector-grpc' should check OTEL_COLLECTOR_GRPC_PORT.
        """
        monkeypatch.setenv("OTEL_COLLECTOR_GRPC_PORT", "5555")
        result = _get_effective_port("otel-collector-grpc")
        assert result == 5555

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_dagster_checks_dagster_port_not_dagster_webserver_port(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'dagster' checks DAGSTER_PORT, not DAGSTER_WEBSERVER_PORT.

        This catches a bug where the implementation might confuse 'dagster'
        with 'dagster-webserver'. Each service name maps to its OWN env var
        only. 'dagster' -> DAGSTER_PORT, 'dagster-webserver' -> DAGSTER_WEBSERVER_PORT.
        """
        # Set DAGSTER_WEBSERVER_PORT but NOT DAGSTER_PORT
        monkeypatch.setenv("DAGSTER_WEBSERVER_PORT", "8888")
        # Ensure DAGSTER_PORT is not set
        monkeypatch.delenv("DAGSTER_PORT", raising=False)

        # 'dagster' should NOT pick up DAGSTER_WEBSERVER_PORT
        result = _get_effective_port("dagster")
        assert result == 3000  # Falls to dict default, not 8888

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_dagster_webserver_checks_own_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that 'dagster-webserver' checks DAGSTER_WEBSERVER_PORT."""
        monkeypatch.setenv("DAGSTER_WEBSERVER_PORT", "8888")
        monkeypatch.delenv("DAGSTER_PORT", raising=False)
        result = _get_effective_port("dagster-webserver")
        assert result == 8888

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_env_var_returns_integer_not_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that port from env var is returned as int, not str."""
        monkeypatch.setenv("MINIO_PORT", "9999")
        result = _get_effective_port("minio")
        assert result == 9999
        assert isinstance(result, int)

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_explicit_default_none_falls_to_dict(self) -> None:
        """Test that passing default=None explicitly falls through to dict.

        Ensures None is treated the same as not passing a default.
        """
        result = _get_effective_port("postgres", default=None)
        assert result == 5432

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_each_service_resolves_to_own_dict_default(self) -> None:
        """Test multiple services resolve to their own dict defaults.

        Guards against a hardcoded return value implementation.
        """
        assert _get_effective_port("polaris") == 8181
        assert _get_effective_port("minio") == 9000
        assert _get_effective_port("postgres") == 5432
        assert _get_effective_port("marquez") == 5100
        assert _get_effective_port("jaeger-query") == 16686

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_env_var_not_leaked_across_services(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that setting one service's env var doesn't affect another.

        Setting POLARIS_PORT should not change minio's resolution.
        """
        monkeypatch.setenv("POLARIS_PORT", "9999")
        monkeypatch.delenv("MINIO_PORT", raising=False)
        assert _get_effective_port("minio") == 9000


# ---------------------------------------------------------------------------
# AC-9: Invalid env var raises ValueError
# ---------------------------------------------------------------------------


class TestInvalidEnvVar:
    """Tests for invalid (non-integer) env var values."""

    @pytest.mark.requirement("env-resilient-AC-9")
    def test_non_integer_env_var_raises_valueerror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a non-integer env var raises ValueError."""
        monkeypatch.setenv("POLARIS_PORT", "not-a-number")
        with pytest.raises(ValueError):
            _get_effective_port("polaris")

    @pytest.mark.requirement("env-resilient-AC-9")
    def test_error_contains_env_var_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that error message includes the env var name for debugging."""
        monkeypatch.setenv("MINIO_PORT", "abc")
        with pytest.raises(ValueError, match="MINIO_PORT"):
            _get_effective_port("minio")

    @pytest.mark.requirement("env-resilient-AC-9")
    def test_error_contains_invalid_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that error message includes the invalid value that was set."""
        monkeypatch.setenv("POSTGRES_PORT", "xyz123")
        with pytest.raises(ValueError, match="xyz123"):
            _get_effective_port("postgres")

    @pytest.mark.requirement("env-resilient-AC-9")
    def test_error_contains_integer_keyword(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that error message mentions 'integer' for clarity."""
        monkeypatch.setenv("POLARIS_PORT", "eight-thousand")
        with pytest.raises(ValueError, match="integer"):
            _get_effective_port("polaris")

    @pytest.mark.requirement("env-resilient-AC-9")
    def test_float_env_var_is_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a float string like '8181.5' is rejected as non-integer."""
        monkeypatch.setenv("POLARIS_PORT", "8181.5")
        with pytest.raises(ValueError):
            _get_effective_port("polaris")

    @pytest.mark.requirement("env-resilient-AC-9")
    def test_whitespace_only_env_var_treated_as_unset_or_invalid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that whitespace-only env var does not silently become port 0.

        Whitespace should either be treated as unset (falling through to
        defaults) or raise a clear error. It must NOT silently resolve.
        """
        monkeypatch.setenv("POLARIS_PORT", "   ")
        # Either falls through to dict default (8181) or raises ValueError
        # It must NOT return 0 or some garbage value
        try:
            result = _get_effective_port("polaris")
            # If it didn't raise, it must have fallen through to default
            assert result == 8181
        except ValueError:
            pass  # Also acceptable - whitespace is not a valid integer


# ---------------------------------------------------------------------------
# AC-3: get_effective_port() public API and __all__ exports
# ---------------------------------------------------------------------------


class TestPublicApi:
    """Tests for get_effective_port() public function and __all__ exports."""

    @pytest.mark.requirement("env-resilient-AC-3")
    def test_get_effective_port_delegates_to_private(self) -> None:
        """Test that public get_effective_port produces same result as private.

        The public function should delegate to _get_effective_port.
        """
        assert get_effective_port("polaris") == _get_effective_port("polaris")

    @pytest.mark.requirement("env-resilient-AC-3")
    def test_get_effective_port_passes_default(self) -> None:
        """Test that public function forwards the default parameter."""
        result = get_effective_port("unknown-service", default=4444)
        assert result == 4444

    @pytest.mark.requirement("env-resilient-AC-3")
    def test_get_effective_port_passes_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that public function respects env vars like the private one."""
        monkeypatch.setenv("MINIO_PORT", "7777")
        assert get_effective_port("minio") == 7777

    @pytest.mark.requirement("env-resilient-AC-3")
    def test_get_effective_port_in_all(self) -> None:
        """Test that get_effective_port is exported in __all__."""
        import testing.fixtures.services as mod

        assert "get_effective_port" in mod.__all__

    @pytest.mark.requirement("env-resilient-AC-3")
    def test_service_default_ports_in_all(self) -> None:
        """Test that SERVICE_DEFAULT_PORTS is exported in __all__."""
        import testing.fixtures.services as mod

        assert "SERVICE_DEFAULT_PORTS" in mod.__all__

    @pytest.mark.requirement("env-resilient-AC-3")
    def test_get_effective_port_raises_for_unknown(self) -> None:
        """Test that public function also raises ValueError for unknown services."""
        with pytest.raises(ValueError):
            get_effective_port("completely-unknown-service")
