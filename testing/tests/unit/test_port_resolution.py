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
