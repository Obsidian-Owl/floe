"""Network security exceptions.

This module defines the exception hierarchy for network security operations.
All exceptions inherit from NetworkSecurityError for consistent error handling.
"""

from __future__ import annotations


class NetworkSecurityError(Exception):
    """Base exception for network security errors.

    All network security-related exceptions should inherit from this class
    to enable consistent error handling in CLI commands.
    """

    pass


class CIDRValidationError(NetworkSecurityError):
    """Invalid CIDR notation.

    Raised when a CIDR string does not conform to valid IPv4 or IPv6
    network notation (e.g., "10.0.0.0/8", "2001:db8::/32").

    Example:
        raise CIDRValidationError("Invalid CIDR: 999.999.999.999/32")
    """

    pass


class PortValidationError(NetworkSecurityError):
    """Invalid port number.

    Raised when a port number is outside the valid range (1-65535).

    Example:
        raise PortValidationError("Port 70000 out of range (1-65535)")
    """

    pass


class NamespaceValidationError(NetworkSecurityError):
    """Invalid Kubernetes namespace name.

    Raised when a namespace name does not conform to Kubernetes naming rules:
    - Must be lowercase alphanumeric with optional hyphens
    - Must start and end with alphanumeric character
    - Maximum 63 characters

    Example:
        raise NamespaceValidationError("Invalid namespace: My_Namespace")
    """

    pass
