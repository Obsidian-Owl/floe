"""Namespace utilities for K8s-native integration tests.

This module provides utilities for generating unique Kubernetes namespace
names to ensure test isolation. Each test gets its own namespace to prevent
interference between parallel test runs.

Functions:
    generate_unique_namespace: Create a unique K8s namespace name
    validate_namespace: Check if a namespace name is valid for K8s

Example:
    from testing.fixtures.namespaces import generate_unique_namespace

    namespace = generate_unique_namespace("test_polaris")
    # Returns: "test-polaris-a1b2c3d4"
"""

from __future__ import annotations

import re
import uuid

# K8s namespace constraints
MAX_NAMESPACE_LENGTH = 63
NAMESPACE_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


class InvalidNamespaceError(ValueError):
    """Raised when a namespace name is invalid for Kubernetes."""

    def __init__(self, namespace: str, reason: str) -> None:
        self.namespace = namespace
        self.reason = reason
        super().__init__(f"Invalid namespace '{namespace}': {reason}")


def generate_unique_namespace(prefix: str = "test") -> str:
    """Generate a unique K8s namespace name.

    Creates a namespace name by combining the given prefix with a UUID suffix.
    The result follows Kubernetes naming conventions:
    - Lowercase alphanumeric characters and hyphens only
    - Must start and end with alphanumeric character
    - Maximum 63 characters

    Args:
        prefix: Namespace prefix (e.g., "test", "test_polaris").
            Underscores are converted to hyphens.

    Returns:
        Unique namespace string (e.g., "test-polaris-a1b2c3d4").

    Raises:
        InvalidNamespaceError: If the prefix is too long or contains
            invalid characters.

    Example:
        >>> ns1 = generate_unique_namespace("test")
        >>> ns2 = generate_unique_namespace("test")
        >>> ns1 != ns2  # Each call generates unique namespace
        True
        >>> len(ns1) <= 63
        True
    """
    # Normalize prefix: lowercase, replace underscores with hyphens
    normalized_prefix = prefix.lower().replace("_", "-")

    # Remove any invalid characters (keep only alphanumeric and hyphens)
    normalized_prefix = re.sub(r"[^a-z0-9-]", "", normalized_prefix)

    # Ensure it doesn't start or end with hyphen
    normalized_prefix = normalized_prefix.strip("-")

    # Generate UUID suffix (8 chars for brevity)
    suffix = uuid.uuid4().hex[:8]

    # Calculate max prefix length (leaving room for hyphen and suffix)
    max_prefix_length = MAX_NAMESPACE_LENGTH - len(suffix) - 1

    if len(normalized_prefix) > max_prefix_length:
        normalized_prefix = normalized_prefix[:max_prefix_length].rstrip("-")

    # Handle empty prefix case
    if not normalized_prefix:
        normalized_prefix = "test"

    namespace = f"{normalized_prefix}-{suffix}"

    # Validate the result
    if not validate_namespace(namespace):
        raise InvalidNamespaceError(
            namespace,
            "Generated namespace does not match K8s naming rules",
        )

    return namespace


def validate_namespace(namespace: str) -> bool:
    """Check if a namespace name is valid for Kubernetes.

    Validates that the namespace follows K8s naming rules:
    - Contains only lowercase alphanumeric characters and hyphens
    - Starts and ends with alphanumeric character
    - Maximum 63 characters

    Args:
        namespace: The namespace name to validate.

    Returns:
        True if valid, False otherwise.

    Example:
        >>> validate_namespace("test-namespace-abc123")
        True
        >>> validate_namespace("Test_Namespace")  # Invalid: uppercase, underscore
        False
        >>> validate_namespace("-invalid")  # Invalid: starts with hyphen
        False
    """
    if not namespace:
        return False

    if len(namespace) > MAX_NAMESPACE_LENGTH:
        return False

    return bool(NAMESPACE_PATTERN.match(namespace))


# Module exports
__all__ = [
    "InvalidNamespaceError",
    "MAX_NAMESPACE_LENGTH",
    "generate_unique_namespace",
    "validate_namespace",
]
