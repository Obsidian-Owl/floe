"""Unit tests for network security exceptions.

Tests the exception hierarchy and behavior of all network security exceptions.
"""

from __future__ import annotations

import pytest

from floe_core.network.exceptions import (
    CIDRValidationError,
    NamespaceValidationError,
    NetworkSecurityError,
    PortValidationError,
)


class TestNetworkSecurityError:
    """Test suite for NetworkSecurityError base exception."""

    @pytest.mark.requirement("FR-070")
    def test_is_exception_subclass(self) -> None:
        """Test that NetworkSecurityError is a subclass of Exception."""
        assert issubclass(NetworkSecurityError, Exception)

    @pytest.mark.requirement("FR-070")
    def test_can_raise_with_message(self) -> None:
        """Test that NetworkSecurityError can be raised with a message."""
        message = "Network security error occurred"
        with pytest.raises(NetworkSecurityError, match=message):
            raise NetworkSecurityError(message)

    @pytest.mark.requirement("FR-070")
    def test_can_raise_without_message(self) -> None:
        """Test that NetworkSecurityError can be raised without a message."""
        with pytest.raises(NetworkSecurityError):
            raise NetworkSecurityError()

    @pytest.mark.requirement("FR-070")
    def test_message_preserved_in_str(self) -> None:
        """Test that exception message is preserved in string representation."""
        message = "Test error message"
        exc = NetworkSecurityError(message)
        assert message in str(exc)

    @pytest.mark.requirement("FR-070")
    def test_message_preserved_in_args(self) -> None:
        """Test that exception message is preserved in args tuple."""
        message = "Test error message"
        exc = NetworkSecurityError(message)
        assert exc.args == (message,)


class TestCIDRValidationError:
    """Test suite for CIDRValidationError exception."""

    @pytest.mark.requirement("FR-070")
    def test_inherits_from_network_security_error(self) -> None:
        """Test that CIDRValidationError inherits from NetworkSecurityError."""
        assert issubclass(CIDRValidationError, NetworkSecurityError)

    @pytest.mark.requirement("FR-070")
    def test_can_raise_with_cidr_message(self) -> None:
        """Test that CIDRValidationError can be raised with CIDR-specific message."""
        message = "Invalid CIDR: 999.999.999.999/32"
        with pytest.raises(CIDRValidationError, match=message):
            raise CIDRValidationError(message)

    @pytest.mark.requirement("FR-070")
    def test_catchable_as_base_exception(self) -> None:
        """Test that CIDRValidationError can be caught as NetworkSecurityError."""
        message = "Invalid CIDR notation"
        with pytest.raises(NetworkSecurityError):
            raise CIDRValidationError(message)

    @pytest.mark.requirement("FR-070")
    def test_message_preserved(self) -> None:
        """Test that CIDR error message is preserved."""
        message = "Invalid CIDR: 10.0.0.0/33"
        exc = CIDRValidationError(message)
        assert message in str(exc)
        assert exc.args == (message,)


class TestPortValidationError:
    """Test suite for PortValidationError exception."""

    @pytest.mark.requirement("FR-070")
    def test_inherits_from_network_security_error(self) -> None:
        """Test that PortValidationError inherits from NetworkSecurityError."""
        assert issubclass(PortValidationError, NetworkSecurityError)

    @pytest.mark.requirement("FR-070")
    def test_can_raise_with_port_message(self) -> None:
        """Test that PortValidationError can be raised with port-specific message."""
        message = "Port 70000 out of range (1-65535)"
        with pytest.raises(PortValidationError, match=r"Port 70000 out of range \(1-65535\)"):
            raise PortValidationError(message)

    @pytest.mark.requirement("FR-070")
    def test_catchable_as_base_exception(self) -> None:
        """Test that PortValidationError can be caught as NetworkSecurityError."""
        message = "Invalid port number"
        with pytest.raises(NetworkSecurityError):
            raise PortValidationError(message)

    @pytest.mark.requirement("FR-070")
    def test_message_preserved(self) -> None:
        """Test that port error message is preserved."""
        message = "Port 0 is not valid"
        exc = PortValidationError(message)
        assert message in str(exc)
        assert exc.args == (message,)


class TestNamespaceValidationError:
    """Test suite for NamespaceValidationError exception."""

    @pytest.mark.requirement("FR-070")
    def test_inherits_from_network_security_error(self) -> None:
        """Test that NamespaceValidationError inherits from NetworkSecurityError."""
        assert issubclass(NamespaceValidationError, NetworkSecurityError)

    @pytest.mark.requirement("FR-070")
    def test_can_raise_with_namespace_message(self) -> None:
        """Test that NamespaceValidationError can be raised with namespace-specific message."""
        message = "Invalid namespace: My_Namespace"
        with pytest.raises(NamespaceValidationError, match=message):
            raise NamespaceValidationError(message)

    @pytest.mark.requirement("FR-070")
    def test_catchable_as_base_exception(self) -> None:
        """Test that NamespaceValidationError can be caught as NetworkSecurityError."""
        message = "Invalid namespace name"
        with pytest.raises(NetworkSecurityError):
            raise NamespaceValidationError(message)

    @pytest.mark.requirement("FR-070")
    def test_message_preserved(self) -> None:
        """Test that namespace error message is preserved."""
        message = "Namespace exceeds 63 character limit"
        exc = NamespaceValidationError(message)
        assert message in str(exc)
        assert exc.args == (message,)


class TestExceptionHierarchy:
    """Test suite for exception hierarchy and relationships."""

    @pytest.mark.requirement("FR-070")
    def test_all_exceptions_catchable_as_base(self) -> None:
        """Test that all specific exceptions can be caught as NetworkSecurityError."""
        exceptions = [
            CIDRValidationError("CIDR error"),
            PortValidationError("Port error"),
            NamespaceValidationError("Namespace error"),
        ]

        for exc in exceptions:
            with pytest.raises(NetworkSecurityError):
                raise exc

    @pytest.mark.requirement("FR-070")
    def test_exception_chaining_preserved(self) -> None:
        """Test that exception chaining (raise X from Y) is preserved."""
        original_error = ValueError("Original error")
        try:
            raise CIDRValidationError("CIDR validation failed") from original_error
        except CIDRValidationError as exc:
            assert exc.__cause__ is original_error
            assert isinstance(exc.__cause__, ValueError)

    @pytest.mark.requirement("FR-070")
    def test_isinstance_checks(self) -> None:
        """Test isinstance checks for exception hierarchy."""
        cidr_exc = CIDRValidationError("test")
        port_exc = PortValidationError("test")
        namespace_exc = NamespaceValidationError("test")

        # Each specific exception is instance of itself
        assert isinstance(cidr_exc, CIDRValidationError)
        assert isinstance(port_exc, PortValidationError)
        assert isinstance(namespace_exc, NamespaceValidationError)

        # All are instances of base exception
        assert isinstance(cidr_exc, NetworkSecurityError)
        assert isinstance(port_exc, NetworkSecurityError)
        assert isinstance(namespace_exc, NetworkSecurityError)

        # All are instances of Exception
        assert isinstance(cidr_exc, Exception)
        assert isinstance(port_exc, Exception)
        assert isinstance(namespace_exc, Exception)

    @pytest.mark.requirement("FR-070")
    def test_exception_type_discrimination(self) -> None:
        """Test that specific exception types can be discriminated."""
        exceptions = [
            CIDRValidationError("CIDR error"),
            PortValidationError("Port error"),
            NamespaceValidationError("Namespace error"),
        ]

        # Verify each exception is only its own type
        assert isinstance(exceptions[0], CIDRValidationError)
        assert not isinstance(exceptions[0], PortValidationError)
        assert not isinstance(exceptions[0], NamespaceValidationError)

        assert isinstance(exceptions[1], PortValidationError)
        assert not isinstance(exceptions[1], CIDRValidationError)
        assert not isinstance(exceptions[1], NamespaceValidationError)

        assert isinstance(exceptions[2], NamespaceValidationError)
        assert not isinstance(exceptions[2], CIDRValidationError)
        assert not isinstance(exceptions[2], PortValidationError)

    @pytest.mark.requirement("FR-070")
    def test_multiple_exception_handling(self) -> None:
        """Test handling multiple exception types with selective catching."""
        # Test catching specific exception type
        with pytest.raises(CIDRValidationError):
            raise CIDRValidationError("CIDR error")

        # Test catching base exception type
        with pytest.raises(NetworkSecurityError):
            raise PortValidationError("Port error")

        # Test that wrong specific type is not caught
        with pytest.raises(PortValidationError):
            try:
                raise PortValidationError("Port error")
            except CIDRValidationError:
                pass  # Should not reach here

    @pytest.mark.requirement("FR-070")
    def test_exception_with_multiple_args(self) -> None:
        """Test exceptions with multiple arguments."""
        exc = NetworkSecurityError("Error", "Additional context", 42)
        assert exc.args == ("Error", "Additional context", 42)

    @pytest.mark.requirement("FR-070")
    def test_exception_empty_message(self) -> None:
        """Test exceptions with empty string message."""
        exc = CIDRValidationError("")
        assert exc.args == ("",)
        assert str(exc) == ""

    @pytest.mark.requirement("FR-070")
    def test_exception_special_characters_in_message(self) -> None:
        """Test exceptions with special characters in message."""
        message = "Invalid CIDR: 10.0.0.0/8 (expected format: x.x.x.x/y)"
        exc = CIDRValidationError(message)
        assert message in str(exc)
        assert exc.args == (message,)
