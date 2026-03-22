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
    _PORT_UNSET,
    SERVICE_DEFAULT_PORTS,
    ServiceEndpoint,
    ServiceUnavailableError,
    _get_effective_port,
    check_infrastructure,
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


# ---------------------------------------------------------------------------
# AC-4: ServiceEndpoint resolves port via __post_init__
# ---------------------------------------------------------------------------


class TestServiceEndpointPortResolution:
    """Tests for ServiceEndpoint port resolution via __post_init__.

    ServiceEndpoint must accept name-only construction (port omitted),
    resolving the port from SERVICE_DEFAULT_PORTS or env vars. The sentinel
    value _PORT_UNSET (-1) triggers resolution when passed explicitly.
    """

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_sentinel_value_is_negative_one(self) -> None:
        """Test that _PORT_UNSET sentinel is exactly -1.

        Guards against the sentinel being changed to 0 or None, which
        would break the resolution logic.
        """
        assert _PORT_UNSET == -1
        assert isinstance(_PORT_UNSET, int)

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_name_only_resolves_from_defaults(self) -> None:
        """Test that ServiceEndpoint('dagster') resolves port from defaults.

        When port is omitted, __post_init__ must resolve it from
        SERVICE_DEFAULT_PORTS. Currently this fails because port is a
        required positional argument with no default.
        """
        endpoint = ServiceEndpoint("dagster")
        assert endpoint.port == 3000

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_name_only_resolves_different_services(self) -> None:
        """Test that multiple services each resolve to their own default port.

        Guards against a hardcoded return value that always returns 3000.
        """
        dagster = ServiceEndpoint("dagster")
        polaris = ServiceEndpoint("polaris")
        minio = ServiceEndpoint("minio")
        postgres = ServiceEndpoint("postgres")

        assert dagster.port == 3000
        assert polaris.port == 8181
        assert minio.port == 9000
        assert postgres.port == 5432

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_explicit_port_preserved(self) -> None:
        """Test that ServiceEndpoint('dagster', 3100).port == 3100.

        An explicit port must be used as-is, never overridden by defaults.
        """
        endpoint = ServiceEndpoint("dagster", 3100)
        assert endpoint.port == 3100

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_explicit_port_not_overridden_by_default(self) -> None:
        """Test explicit port differs from default and is preserved.

        A sloppy implementation might always resolve from defaults,
        ignoring the explicit port. Use a port that differs from the
        default (3000) to catch this.
        """
        endpoint = ServiceEndpoint("dagster", 5555)
        assert endpoint.port == 5555
        assert endpoint.port != SERVICE_DEFAULT_PORTS["dagster"]

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_sentinel_triggers_resolution(self) -> None:
        """Test that ServiceEndpoint('dagster', -1).port == 3000.

        Passing the sentinel value _PORT_UNSET (-1) explicitly must trigger
        port resolution, NOT store -1 as the port.
        """
        endpoint = ServiceEndpoint("dagster", _PORT_UNSET)
        assert endpoint.port == 3000
        assert endpoint.port != -1

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_sentinel_minus_one_resolves_multiple_services(self) -> None:
        """Test sentinel resolution works for different services.

        Guards against sentinel resolution being hardcoded for dagster only.
        """
        polaris = ServiceEndpoint("polaris", -1)
        minio = ServiceEndpoint("minio", -1)

        assert polaris.port == 8181
        assert minio.port == 9000

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_env_var_overrides_default_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test env var is respected during name-only construction.

        With DAGSTER_PORT=4000, ServiceEndpoint('dagster') should
        resolve port to 4000, not the default 3000.
        """
        monkeypatch.setenv("DAGSTER_PORT", "4000")
        endpoint = ServiceEndpoint("dagster")
        assert endpoint.port == 4000

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_env_var_overrides_sentinel_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test env var is respected when sentinel is passed explicitly.

        With POLARIS_PORT=9999, ServiceEndpoint('polaris', -1) should
        resolve port to 9999.
        """
        monkeypatch.setenv("POLARIS_PORT", "9999")
        endpoint = ServiceEndpoint("polaris", -1)
        assert endpoint.port == 9999

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_explicit_port_not_overridden_by_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an explicit (non-sentinel) port is NOT overridden by env var.

        When the user provides a real port (not -1), the env var should be
        irrelevant. The explicit port takes absolute priority.
        """
        monkeypatch.setenv("DAGSTER_PORT", "4000")
        endpoint = ServiceEndpoint("dagster", 3100)
        assert endpoint.port == 3100

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_unknown_service_raises_valueerror(self) -> None:
        """Test that ServiceEndpoint('unknown_service') raises ValueError.

        When port is omitted for a service not in SERVICE_DEFAULT_PORTS and
        with no env var, construction must fail with ValueError.
        """
        with pytest.raises(ValueError, match="unknown_service"):
            ServiceEndpoint("unknown_service")

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_unknown_service_with_explicit_port_succeeds(self) -> None:
        """Test that ServiceEndpoint('unknown_service', 8080).port == 8080.

        An unknown service name is fine if port is explicitly provided.
        Resolution is only needed when port is sentinel or omitted.
        """
        endpoint = ServiceEndpoint("unknown_service", 8080)
        assert endpoint.port == 8080
        assert endpoint.name == "unknown_service"

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_frozen_after_construction(self) -> None:
        """Test that the dataclass remains frozen=True after __post_init__.

        The frozen constraint must survive the addition of __post_init__.
        Assigning to .port after construction must raise.
        """
        endpoint = ServiceEndpoint("dagster", 3000)
        with pytest.raises(AttributeError):
            endpoint.port = 9999  # type: ignore[misc]

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_frozen_after_name_only_construction(self) -> None:
        """Test frozen is enforced even when port was resolved via __post_init__.

        A common implementation mistake: using object.__setattr__ in
        __post_init__ but forgetting to re-freeze. Verify that the
        resolved endpoint is truly immutable.
        """
        endpoint = ServiceEndpoint("dagster")
        with pytest.raises(AttributeError):
            endpoint.name = "something_else"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            endpoint.port = 5555  # type: ignore[misc]

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_namespace_default_preserved(self) -> None:
        """Test that namespace still defaults to 'floe-test' with name-only construction."""
        endpoint = ServiceEndpoint("dagster")
        assert endpoint.namespace == "floe-test"

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_namespace_can_be_overridden_with_name_only(self) -> None:
        """Test namespace override works with name-only (port-resolving) construction."""
        endpoint = ServiceEndpoint("dagster", namespace="custom-ns")
        assert endpoint.namespace == "custom-ns"
        assert endpoint.port == 3000

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_port_stored_as_integer(self) -> None:
        """Test that resolved port is stored as int, not string or float."""
        endpoint = ServiceEndpoint("dagster")
        assert isinstance(endpoint.port, int)

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_hyphenated_service_resolves(self) -> None:
        """Test that hyphenated service names resolve correctly.

        'dagster-webserver' and 'otel-collector-grpc' have hyphens that
        must be handled in both dict lookup and env var construction.
        """
        dw = ServiceEndpoint("dagster-webserver")
        assert dw.port == 3000

        otel = ServiceEndpoint("otel-collector-grpc")
        assert otel.port == 4317

    @pytest.mark.requirement("env-resilient-AC-4")
    def test_env_var_for_hyphenated_service(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test env var override for hyphenated service during resolution.

        DAGSTER_WEBSERVER_PORT should override dagster-webserver default.
        """
        monkeypatch.setenv("DAGSTER_WEBSERVER_PORT", "6000")
        endpoint = ServiceEndpoint("dagster-webserver")
        assert endpoint.port == 6000


# ---------------------------------------------------------------------------
# AC-5: ServiceEndpoint.url property
# ---------------------------------------------------------------------------


class TestServiceEndpointUrl:
    """Tests for ServiceEndpoint.url property.

    The url property must return 'http://{host}:{port}' where host
    comes from get_effective_host and port is the resolved port.
    """

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_property_exists(self) -> None:
        """Test that ServiceEndpoint has a url property.

        Currently ServiceEndpoint has no url attribute, so this fails.
        """
        endpoint = ServiceEndpoint("dagster", 3000)
        _ = endpoint.url  # Should not raise AttributeError

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_starts_with_http(self) -> None:
        """Test that url starts with 'http://'."""
        endpoint = ServiceEndpoint("dagster", 3000)
        assert endpoint.url.startswith("http://")

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_contains_port(self) -> None:
        """Test that url contains the correct port number."""
        endpoint = ServiceEndpoint("dagster", 3000)
        assert endpoint.url.endswith(":3000")

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_contains_different_port(self) -> None:
        """Test url with a non-default port to guard against hardcoding.

        If url always returns ':3000' regardless, this catches it.
        """
        endpoint = ServiceEndpoint("polaris", 8181)
        assert ":8181" in endpoint.url
        assert endpoint.url.endswith(":8181")

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_format_matches_spec(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that url returns exactly 'http://{host}:{port}'.

        Forces localhost via env var so we get a deterministic host value.
        """
        monkeypatch.setenv("INTEGRATION_TEST_HOST", "localhost")
        endpoint = ServiceEndpoint("dagster", 3000)
        assert endpoint.url == "http://localhost:3000"

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_uses_get_effective_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that url uses get_effective_host for the host portion.

        Set a service-specific host override and verify it appears in url.
        """
        monkeypatch.setenv("POLARIS_HOST", "my-custom-host")
        endpoint = ServiceEndpoint("polaris", 8181)
        assert endpoint.url == "http://my-custom-host:8181"

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_with_k8s_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test url with K8s DNS hostname.

        When INTEGRATION_TEST_HOST=k8s, host should be the FQDN.
        """
        monkeypatch.setenv("INTEGRATION_TEST_HOST", "k8s")
        endpoint = ServiceEndpoint("dagster", 3000)
        assert endpoint.url == "http://dagster.floe-test.svc.cluster.local:3000"

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_with_resolved_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test url works correctly when port was resolved via __post_init__.

        Combines AC-4 (port resolution) with AC-5 (url property).
        """
        monkeypatch.setenv("INTEGRATION_TEST_HOST", "localhost")
        endpoint = ServiceEndpoint("polaris")
        assert endpoint.url == "http://localhost:8181"

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_is_property_not_method(self) -> None:
        """Test that url is a property (no parentheses needed), not a method.

        Accessing .url should return a string directly, not a callable.
        """
        endpoint = ServiceEndpoint("dagster", 3000)
        result = endpoint.url
        assert isinstance(result, str)

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_with_custom_namespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test url reflects custom namespace in K8s DNS host.

        When using K8s host resolution, the namespace should appear in the FQDN.
        """
        monkeypatch.setenv("INTEGRATION_TEST_HOST", "k8s")
        endpoint = ServiceEndpoint("dagster", 3000, namespace="production")
        assert endpoint.url == "http://dagster.production.svc.cluster.local:3000"

    @pytest.mark.requirement("env-resilient-AC-5")
    def test_url_no_trailing_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test url does not include a trailing slash.

        Consumers will append paths, so a trailing slash would cause
        double-slash issues like 'http://host:port//api/v1'.
        """
        monkeypatch.setenv("INTEGRATION_TEST_HOST", "localhost")
        endpoint = ServiceEndpoint("dagster", 3000)
        assert not endpoint.url.endswith("/")


# ---------------------------------------------------------------------------
# AC-6: check_infrastructure() accepts both tuple and string formats
# ---------------------------------------------------------------------------


class TestCheckInfrastructureMixedFormats:
    """Tests for check_infrastructure() accepting mixed tuple/string service entries.

    The function must accept ``list[tuple[str, int] | str]`` where bare strings
    resolve their port via the standard precedence chain (env var, then
    SERVICE_DEFAULT_PORTS). Currently the implementation destructures with
    ``for service_name, port in services`` which crashes on string entries.
    """

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_string_entry_accepted_without_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a bare string service entry does not raise ValueError/TypeError.

        Current implementation does ``for service_name, port in services``
        which raises ``ValueError: too many values to unpack`` on a string.
        """
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )
        # Must not raise
        result = check_infrastructure(
            ["polaris"],
            raise_on_failure=False,
        )
        assert isinstance(result, dict)

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_string_entry_returns_service_name_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a bare string entry produces a dict key matching the service name."""
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )
        result = check_infrastructure(
            ["polaris"],
            raise_on_failure=False,
        )
        assert "polaris" in result

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_string_entry_resolves_port_from_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a bare string resolves its port via SERVICE_DEFAULT_PORTS.

        Captures the (host, port) passed to _tcp_health_check to verify
        that the resolved port is 8181 for 'polaris', not some garbage value.
        """
        captured_calls: list[tuple[str, int]] = []

        def capturing_health_check(host: str, port: int, timeout: float) -> bool:
            captured_calls.append((host, port))
            return True

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            capturing_health_check,
        )
        check_infrastructure(
            ["polaris"],
            raise_on_failure=False,
        )
        assert len(captured_calls) == 1
        _host, port = captured_calls[0]
        assert port == 8181

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_string_entry_resolves_port_from_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a bare string respects env var override for port.

        POLARIS_PORT=9999 should override the default 8181.
        """
        captured_calls: list[tuple[str, int]] = []

        def capturing_health_check(host: str, port: int, timeout: float) -> bool:
            captured_calls.append((host, port))
            return True

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            capturing_health_check,
        )
        monkeypatch.setenv("POLARIS_PORT", "9999")
        check_infrastructure(
            ["polaris"],
            raise_on_failure=False,
        )
        assert len(captured_calls) == 1
        _host, port = captured_calls[0]
        assert port == 9999

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_tuple_entry_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: tuple entries must continue to work after the change.

        Guards against an implementation that handles strings but breaks tuples.
        """
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )
        result = check_infrastructure([("polaris", 8181)], raise_on_failure=False)
        assert result == {"polaris": True}

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_tuple_entry_uses_explicit_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that tuple entries use the explicitly provided port, not the default.

        Passes port 7777 for polaris (default is 8181). Verifies the explicit
        port reaches _tcp_health_check.
        """
        captured_calls: list[tuple[str, int]] = []

        def capturing_health_check(host: str, port: int, timeout: float) -> bool:
            captured_calls.append((host, port))
            return True

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            capturing_health_check,
        )
        check_infrastructure([("polaris", 7777)], raise_on_failure=False)
        assert len(captured_calls) == 1
        _host, port = captured_calls[0]
        assert port == 7777

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_mixed_list_returns_both_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a mixed list of tuples and strings returns all service keys.

        check_infrastructure([("dagster", 3100), "polaris"]) must return a dict
        with both 'dagster' and 'polaris' keys.
        """
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )
        result = check_infrastructure(
            [("dagster", 3100), "polaris"],
            raise_on_failure=False,
        )
        assert set(result.keys()) == {"dagster", "polaris"}

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_mixed_list_resolves_correct_ports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that mixed entries resolve to correct ports.

        ("dagster", 3100) should use port 3100 (explicit).
        "polaris" should use port 8181 (from SERVICE_DEFAULT_PORTS).
        """
        captured_calls: list[tuple[str, int]] = []

        def capturing_health_check(host: str, port: int, timeout: float) -> bool:
            captured_calls.append((host, port))
            return True

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            capturing_health_check,
        )
        check_infrastructure(
            [("dagster", 3100), "polaris"],
            raise_on_failure=False,
        )
        assert len(captured_calls) == 2
        ports_by_call = {call[1] for call in captured_calls}
        assert 3100 in ports_by_call, "Explicit tuple port 3100 not passed to health check"
        assert 8181 in ports_by_call, "Resolved string port 8181 not passed to health check"

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_empty_list_returns_empty_dict(self) -> None:
        """Test that check_infrastructure([], raise_on_failure=False) returns {}.

        No monkeypatching needed -- empty list should never call health check.
        """
        result = check_infrastructure([], raise_on_failure=False)
        assert result == {}

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_empty_list_returns_dict_type(self) -> None:
        """Test that empty list returns a dict, not None or some other type."""
        result = check_infrastructure([], raise_on_failure=False)
        assert isinstance(result, dict)

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_duplicate_service_later_overwrites_earlier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that duplicate service names: later entry overwrites earlier in result.

        First entry is ("polaris", 8181) with health=False, second is "polaris"
        with health=True. The result dict should have polaris=True (last wins).
        """
        call_count = 0

        def alternating_health_check(host: str, port: int, timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            # First call returns False, second returns True
            return call_count >= 2

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            alternating_health_check,
        )
        result = check_infrastructure(
            [("polaris", 8181), "polaris"],
            raise_on_failure=False,
        )
        # Later entry (True) should overwrite earlier (False)
        assert result["polaris"] is True

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_duplicate_service_only_one_key_in_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that duplicates don't create multiple keys -- dict has one entry."""
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )
        result = check_infrastructure(
            [("polaris", 8181), "polaris"],
            raise_on_failure=False,
        )
        assert len(result) == 1
        assert "polaris" in result

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_string_entry_health_false_when_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a string entry returns False when the service is unreachable.

        Ensures the function actually performs a health check on string entries,
        not just returning True unconditionally.
        """
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: False,
        )
        result = check_infrastructure(
            ["polaris"],
            raise_on_failure=False,
        )
        assert result["polaris"] is False

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_multiple_string_entries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that multiple bare string entries all work.

        Guards against an implementation that only handles the first string.
        """
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )
        result = check_infrastructure(
            ["polaris", "minio", "postgres"],
            raise_on_failure=False,
        )
        assert set(result.keys()) == {"polaris", "minio", "postgres"}
        assert all(v is True for v in result.values())

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_multiple_strings_resolve_distinct_ports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that each string entry resolves to its own default port.

        Guards against a hardcoded port for all string entries.
        """
        captured_ports: dict[int, str] = {}

        def capturing_health_check(host: str, port: int, timeout: float) -> bool:
            captured_ports[port] = host
            return True

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            capturing_health_check,
        )
        check_infrastructure(
            ["polaris", "minio", "postgres"],
            raise_on_failure=False,
        )
        assert 8181 in captured_ports, "polaris should resolve to port 8181"
        assert 9000 in captured_ports, "minio should resolve to port 9000"
        assert 5432 in captured_ports, "postgres should resolve to port 5432"

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_string_entry_raise_on_failure_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that raise_on_failure=True works with string entries.

        When a string entry fails health check with raise_on_failure=True,
        ServiceUnavailableError should be raised (same as tuple entries).
        """
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: False,
        )
        with pytest.raises(ServiceUnavailableError):
            check_infrastructure(
                ["polaris"],
                raise_on_failure=True,
            )

    @pytest.mark.requirement("env-resilient-AC-6")
    def test_string_unknown_service_raises_valueerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a string for an unknown service (no default port) raises ValueError.

        If 'totally-unknown-service' has no entry in SERVICE_DEFAULT_PORTS
        and no env var, port resolution should fail with ValueError.
        """
        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )
        monkeypatch.delenv("TOTALLY_UNKNOWN_SERVICE_PORT", raising=False)
        with pytest.raises(ValueError, match="totally-unknown-service"):
            check_infrastructure(
                ["totally-unknown-service"],
                raise_on_failure=False,
            )


# ---------------------------------------------------------------------------
# AC-7: IntegrationTestBase port resolution
# ---------------------------------------------------------------------------


class TestIntegrationTestBasePortResolution:
    """Tests for IntegrationTestBase accepting string-format required_services
    and instance check_infrastructure with optional port parameter.

    These tests verify:
    - required_services accepts bare strings (not just tuples)
    - check_infrastructure(service_name) works without explicit port
    - Port resolution uses get_effective_port when port is omitted
    - Backward compatibility: tuple format and explicit port still work
    """

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_string_required_services_setup_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a subclass with required_services = ['polaris'] passes setup_method.

        The module-level check_infrastructure already handles strings, so this
        should work once the ClassVar type hint is updated to accept strings.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )

        class MyTest(IntegrationTestBase):
            required_services = ["polaris"]

        instance = MyTest()
        # Should not raise -- setup_method delegates to module check_infrastructure
        instance.setup_method()

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_string_required_services_resolves_correct_port(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that string-format required_services resolves port from defaults.

        When required_services = ['polaris'], setup_method should call
        check_infrastructure which resolves polaris to port 8181.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        captured_ports: list[int] = []

        def capturing_health_check(host: str, port: int, timeout: float) -> bool:
            captured_ports.append(port)
            return True

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = ["polaris"]

        instance = MyTest()
        instance.setup_method()

        assert 8181 in captured_ports, (
            "String 'polaris' should resolve to port 8181 via SERVICE_DEFAULT_PORTS"
        )

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_tuple_required_services_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test backward compat: required_services = [('polaris', 8181)] still works.

        Ensures the change to accept strings does not break existing tuple format.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )

        class MyTest(IntegrationTestBase):
            required_services = [("polaris", 8181)]

        instance = MyTest()
        # Must not raise
        instance.setup_method()

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_mixed_required_services(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test mixed format: required_services = [('dagster', 3100), 'polaris'].

        Both tuple and string entries must be accepted in a single list.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        captured_ports: list[int] = []

        def capturing_health_check(host: str, port: int, timeout: float) -> bool:
            captured_ports.append(port)
            return True

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = [("dagster", 3100), "polaris"]

        instance = MyTest()
        instance.setup_method()

        assert 3100 in captured_ports, "Explicit tuple port 3100 should be checked"
        assert 8181 in captured_ports, "String 'polaris' should resolve to 8181"

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_no_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test self.check_infrastructure('polaris') without explicit port.

        This is the core AC-7 requirement: calling check_infrastructure with
        only a service name should resolve the port via get_effective_port.
        Currently FAILS because port: int is a required parameter.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        monkeypatch.setattr(
            "testing.fixtures.services._tcp_health_check",
            lambda host, port, timeout: True,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        # Must not raise TypeError for missing 'port' argument
        instance.check_infrastructure("polaris")

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_no_port_resolves_8181(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test self.check_infrastructure('polaris') resolves port to 8181.

        When port is omitted, the method must use get_effective_port to
        determine the correct port. For polaris, that's 8181.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        captured_ports: list[int] = []

        def capturing_health_check(
            service_name: str,
            port: int,
            namespace: str,
            timeout: float = 5.0,
        ) -> bool:
            captured_ports.append(port)
            return True

        monkeypatch.setattr(
            "testing.base_classes.integration_test_base.check_service_health",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        instance.check_infrastructure("polaris")

        assert len(captured_ports) == 1
        assert captured_ports[0] == 8181, (
            "check_infrastructure('polaris') must resolve port to 8181"
        )

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_no_port_different_services(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that port resolution works for multiple services, not just polaris.

        Guards against a hardcoded 8181 return when port is omitted.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        captured_calls: list[tuple[str, int]] = []

        def capturing_health_check(
            service_name: str,
            port: int,
            namespace: str,
            timeout: float = 5.0,
        ) -> bool:
            captured_calls.append((service_name, port))
            return True

        monkeypatch.setattr(
            "testing.base_classes.integration_test_base.check_service_health",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        instance.check_infrastructure("polaris")
        instance.check_infrastructure("minio")
        instance.check_infrastructure("postgres")

        assert len(captured_calls) == 3
        ports_by_service = dict(captured_calls)
        assert ports_by_service["polaris"] == 8181
        assert ports_by_service["minio"] == 9000
        assert ports_by_service["postgres"] == 5432

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_explicit_port_still_works(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test backward compat: self.check_infrastructure('polaris', 8181) still works.

        The explicit port parameter must continue to be accepted and used.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        captured_ports: list[int] = []

        def capturing_health_check(
            service_name: str,
            port: int,
            namespace: str,
            timeout: float = 5.0,
        ) -> bool:
            captured_ports.append(port)
            return True

        monkeypatch.setattr(
            "testing.base_classes.integration_test_base.check_service_health",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        instance.check_infrastructure("polaris", 8181)

        assert captured_ports == [8181]

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_explicit_port_overrides_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that explicit port 7777 is used, not the default 8181.

        Guards against implementation that ignores the port parameter and
        always resolves from defaults.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        captured_ports: list[int] = []

        def capturing_health_check(
            service_name: str,
            port: int,
            namespace: str,
            timeout: float = 5.0,
        ) -> bool:
            captured_ports.append(port)
            return True

        monkeypatch.setattr(
            "testing.base_classes.integration_test_base.check_service_health",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        instance.check_infrastructure("polaris", 7777)

        assert captured_ports == [7777], "Explicit port 7777 must be used, not default 8181"

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_no_port_env_var_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that POLARIS_PORT=9999 is used when port is omitted.

        With env var set, check_infrastructure('polaris') should resolve to
        port 9999 via get_effective_port, not the default 8181.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        monkeypatch.setenv("POLARIS_PORT", "9999")

        captured_ports: list[int] = []

        def capturing_health_check(
            service_name: str,
            port: int,
            namespace: str,
            timeout: float = 5.0,
        ) -> bool:
            captured_ports.append(port)
            return True

        monkeypatch.setattr(
            "testing.base_classes.integration_test_base.check_service_health",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        instance.check_infrastructure("polaris")

        assert len(captured_ports) == 1
        assert captured_ports[0] == 9999, (
            "With POLARIS_PORT=9999, check_infrastructure('polaris') must use 9999"
        )

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_namespace_passthrough(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that namespace parameter is still forwarded when port is omitted.

        check_infrastructure('polaris', namespace='custom-ns') with no port
        must forward 'custom-ns' to check_service_health.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        captured_namespaces: list[str] = []

        def capturing_health_check(
            service_name: str,
            port: int,
            namespace: str,
            timeout: float = 5.0,
        ) -> bool:
            captured_namespaces.append(namespace)
            return True

        monkeypatch.setattr(
            "testing.base_classes.integration_test_base.check_service_health",
            capturing_health_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        instance.check_infrastructure("polaris", namespace="custom-ns")

        assert captured_namespaces == ["custom-ns"]

    @pytest.mark.requirement("env-resilient-AC-7")
    def test_instance_check_infrastructure_fails_on_unhealthy_service(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that check_infrastructure still calls pytest.fail when service is down.

        Port resolution must not break the failure behavior. When port is
        omitted and service is unhealthy, pytest.fail must be called.
        """
        from testing.base_classes.integration_test_base import IntegrationTestBase

        def unhealthy_check(
            service_name: str,
            port: int,
            namespace: str,
            timeout: float = 5.0,
        ) -> bool:
            return False

        monkeypatch.setattr(
            "testing.base_classes.integration_test_base.check_service_health",
            unhealthy_check,
        )

        class MyTest(IntegrationTestBase):
            required_services = []

        instance = MyTest()
        instance.setup_method()

        with pytest.raises(pytest.fail.Exception, match="polaris"):
            instance.check_infrastructure("polaris")


# ---------------------------------------------------------------------------
# AC-8: test-e2e.sh canonical env var exports
# ---------------------------------------------------------------------------


class TestShellEnvVarExports:
    """Tests for canonical env var exports in testing/ci/test-e2e.sh.

    After port-forward setup and before pytest invocation, test-e2e.sh must
    export DAGSTER_WEBSERVER_PORT, DAGSTER_PORT, and MARQUEZ_PORT so they
    propagate to the pytest child process. These are static content tests
    that read the shell script as text and verify the correct export lines
    exist in the correct order.
    """

    @pytest.fixture()
    def script_content(self) -> str:
        """Read the test-e2e.sh script content."""
        from pathlib import Path

        script_path = Path(__file__).resolve().parents[3] / "testing" / "ci" / "test-e2e.sh"
        return script_path.read_text()

    @pytest.fixture()
    def script_lines(self, script_content: str) -> list[str]:
        """Split script content into lines for positional analysis."""
        return script_content.splitlines()

    # --- Existence tests ---

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_export_dagster_webserver_port_exists(self, script_content: str) -> None:
        """Test that 'export DAGSTER_WEBSERVER_PORT' appears in the script.

        Without this export, the pytest child process will not see the
        DAGSTER_WEBSERVER_PORT env var set by the shell script.
        """
        assert "export DAGSTER_WEBSERVER_PORT" in script_content

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_export_dagster_port_exists(self, script_content: str) -> None:
        """Test that 'export DAGSTER_PORT' appears in the script.

        This must be a distinct line from DAGSTER_WEBSERVER_PORT.
        """
        assert "export DAGSTER_PORT" in script_content

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_export_dagster_port_is_distinct_from_webserver(self, script_lines: list[str]) -> None:
        """Test that DAGSTER_PORT and DAGSTER_WEBSERVER_PORT are on separate lines.

        A sloppy implementation might only export DAGSTER_WEBSERVER_PORT and
        claim DAGSTER_PORT is 'covered'. They must be distinct export lines
        so both env var names are available to the pytest child process.
        """
        dagster_port_lines = [
            line.strip() for line in script_lines if line.strip().startswith("export DAGSTER_PORT=")
        ]
        dagster_webserver_lines = [
            line.strip()
            for line in script_lines
            if line.strip().startswith("export DAGSTER_WEBSERVER_PORT=")
        ]
        assert len(dagster_port_lines) >= 1, "No 'export DAGSTER_PORT=...' line found"
        assert len(dagster_webserver_lines) >= 1, (
            "No 'export DAGSTER_WEBSERVER_PORT=...' line found"
        )
        # They must be different lines (DAGSTER_PORT= must not be a substring
        # match of DAGSTER_WEBSERVER_PORT=)
        assert dagster_port_lines[0] != dagster_webserver_lines[0], (
            "DAGSTER_PORT and DAGSTER_WEBSERVER_PORT should be separate export lines"
        )

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_export_marquez_port_exists(self, script_content: str) -> None:
        """Test that 'export MARQUEZ_PORT' appears in the script."""
        assert "export MARQUEZ_PORT" in script_content

    # --- Use `export` (not plain assignment) ---

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_dagster_webserver_port_uses_export(self, script_lines: list[str]) -> None:
        """Test that DAGSTER_WEBSERVER_PORT uses 'export', not plain assignment.

        A plain 'DAGSTER_WEBSERVER_PORT=...' (without export) would set the
        var only in the shell, not propagating to the pytest child process.
        """
        export_lines = [
            line.strip()
            for line in script_lines
            if line.strip().startswith("export DAGSTER_WEBSERVER_PORT=")
        ]
        assert len(export_lines) >= 1, "DAGSTER_WEBSERVER_PORT must be set with 'export'"

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_dagster_port_uses_export(self, script_lines: list[str]) -> None:
        """Test that DAGSTER_PORT uses 'export', not plain assignment."""
        export_lines = [
            line.strip() for line in script_lines if line.strip().startswith("export DAGSTER_PORT=")
        ]
        assert len(export_lines) >= 1, "DAGSTER_PORT must be set with 'export'"

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_marquez_port_uses_export(self, script_lines: list[str]) -> None:
        """Test that MARQUEZ_PORT uses 'export', not plain assignment."""
        export_lines = [
            line.strip() for line in script_lines if line.strip().startswith("export MARQUEZ_PORT=")
        ]
        assert len(export_lines) >= 1, "MARQUEZ_PORT must be set with 'export'"

    # --- Source variable correctness ---

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_dagster_webserver_port_uses_dagster_host_port(self, script_lines: list[str]) -> None:
        """Test that DAGSTER_WEBSERVER_PORT derives from DAGSTER_HOST_PORT.

        Must not be hardcoded to a port number like '3100'. It must reference
        the DAGSTER_HOST_PORT variable so users can override the port.
        """
        export_lines = [
            line.strip()
            for line in script_lines
            if line.strip().startswith("export DAGSTER_WEBSERVER_PORT=")
        ]
        assert len(export_lines) >= 1
        assert "DAGSTER_HOST_PORT" in export_lines[0], (
            "DAGSTER_WEBSERVER_PORT must reference DAGSTER_HOST_PORT, not hardcode a port"
        )

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_dagster_port_uses_dagster_host_port(self, script_lines: list[str]) -> None:
        """Test that DAGSTER_PORT derives from DAGSTER_HOST_PORT.

        Must not be hardcoded to a port number like '3100'.
        """
        export_lines = [
            line.strip() for line in script_lines if line.strip().startswith("export DAGSTER_PORT=")
        ]
        assert len(export_lines) >= 1
        assert "DAGSTER_HOST_PORT" in export_lines[0], (
            "DAGSTER_PORT must reference DAGSTER_HOST_PORT, not hardcode a port"
        )

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_marquez_port_uses_marquez_host_port_with_default(
        self, script_lines: list[str]
    ) -> None:
        """Test that MARQUEZ_PORT derives from MARQUEZ_HOST_PORT with default 5100.

        The export must reference MARQUEZ_HOST_PORT and provide a fallback
        default of 5100, e.g. '${MARQUEZ_HOST_PORT:-5100}'.
        """
        export_lines = [
            line.strip() for line in script_lines if line.strip().startswith("export MARQUEZ_PORT=")
        ]
        assert len(export_lines) >= 1
        line = export_lines[0]
        assert "MARQUEZ_HOST_PORT" in line, "MARQUEZ_PORT must reference MARQUEZ_HOST_PORT"
        assert "5100" in line, "MARQUEZ_PORT must have default 5100"

    # --- Ordering: after port-forward setup, before pytest ---

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_exports_after_port_forwards_established(self, script_lines: list[str]) -> None:
        """Test that all exports appear AFTER 'Port-forwards established' message.

        The exports must come after port-forward setup is complete, otherwise
        the DAGSTER_HOST_PORT variable may not be fully resolved yet.
        """
        port_forwards_line: int | None = None
        export_lines_idx: list[int] = []

        for idx, line in enumerate(script_lines):
            if "Port-forwards established" in line:
                port_forwards_line = idx
            if line.strip().startswith("export DAGSTER_WEBSERVER_PORT="):
                export_lines_idx.append(idx)
            if line.strip().startswith("export DAGSTER_PORT="):
                export_lines_idx.append(idx)
            if line.strip().startswith("export MARQUEZ_PORT="):
                export_lines_idx.append(idx)

        assert port_forwards_line is not None, (
            "Script must contain 'Port-forwards established' message"
        )
        assert len(export_lines_idx) >= 3, f"Expected 3 export lines, found {len(export_lines_idx)}"
        for idx in export_lines_idx:
            assert idx > port_forwards_line, (
                f"Export at line {idx + 1} must come after 'Port-forwards established' "
                f"at line {port_forwards_line + 1}"
            )

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_exports_before_pytest_invocation(self, script_lines: list[str]) -> None:
        """Test that all exports appear BEFORE 'uv run pytest' invocation.

        The exports must be set before pytest runs, otherwise the pytest
        child process will not see them.
        """
        pytest_line: int | None = None
        export_lines_idx: list[int] = []

        for idx, line in enumerate(script_lines):
            if "uv run pytest" in line and pytest_line is None:
                pytest_line = idx
            if line.strip().startswith("export DAGSTER_WEBSERVER_PORT="):
                export_lines_idx.append(idx)
            if line.strip().startswith("export DAGSTER_PORT="):
                export_lines_idx.append(idx)
            if line.strip().startswith("export MARQUEZ_PORT="):
                export_lines_idx.append(idx)

        assert pytest_line is not None, "Script must contain 'uv run pytest' invocation"
        assert len(export_lines_idx) >= 3, f"Expected 3 export lines, found {len(export_lines_idx)}"
        for idx in export_lines_idx:
            assert idx < pytest_line, (
                f"Export at line {idx + 1} must come before 'uv run pytest' "
                f"at line {pytest_line + 1}"
            )

    # --- Guard against hardcoded values ---

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_dagster_exports_not_hardcoded_to_3100(self, script_lines: list[str]) -> None:
        """Test that DAGSTER_WEBSERVER_PORT and DAGSTER_PORT are not hardcoded to 3100.

        A sloppy implementation might write 'export DAGSTER_PORT=3100' instead
        of referencing the DAGSTER_HOST_PORT variable. This would break when
        users override DAGSTER_HOST_PORT to a different value.
        """
        for line in script_lines:
            stripped = line.strip()
            if stripped.startswith("export DAGSTER_WEBSERVER_PORT="):
                assert stripped != 'export DAGSTER_WEBSERVER_PORT="3100"', (
                    "DAGSTER_WEBSERVER_PORT must not be hardcoded to 3100"
                )
                assert stripped != "export DAGSTER_WEBSERVER_PORT=3100", (
                    "DAGSTER_WEBSERVER_PORT must not be hardcoded to 3100"
                )
            if stripped.startswith("export DAGSTER_PORT="):
                assert stripped != 'export DAGSTER_PORT="3100"', (
                    "DAGSTER_PORT must not be hardcoded to 3100"
                )
                assert stripped != "export DAGSTER_PORT=3100", (
                    "DAGSTER_PORT must not be hardcoded to 3100"
                )

    @pytest.mark.requirement("env-resilient-AC-8")
    def test_marquez_port_not_hardcoded_to_5100(self, script_lines: list[str]) -> None:
        """Test that MARQUEZ_PORT is not hardcoded to 5100 without referencing variable.

        'export MARQUEZ_PORT=5100' would ignore any user override of
        MARQUEZ_HOST_PORT. It must use '${MARQUEZ_HOST_PORT:-5100}' or similar.
        """
        for line in script_lines:
            stripped = line.strip()
            if stripped.startswith("export MARQUEZ_PORT="):
                assert stripped != 'export MARQUEZ_PORT="5100"', (
                    "MARQUEZ_PORT must reference MARQUEZ_HOST_PORT, not hardcode 5100"
                )
                assert stripped != "export MARQUEZ_PORT=5100", (
                    "MARQUEZ_PORT must reference MARQUEZ_HOST_PORT, not hardcode 5100"
                )
