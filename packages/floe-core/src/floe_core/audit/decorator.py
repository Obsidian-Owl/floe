"""Audit logging decorator for secret access operations.

This module provides a decorator that automatically logs audit events
for secret access operations with OpenTelemetry trace context.

Task: T077
Requirements: FR-060 (Audit logging for secret access operations)

Example:
    >>> from floe_core.audit.decorator import audit_secret_access
    >>> from floe_core.schemas.audit import AuditOperation
    >>>
    >>> class MySecretsPlugin(SecretsPlugin):
    ...     @audit_secret_access(AuditOperation.GET)
    ...     def get_secret(self, key: str) -> str | None:
    ...         return self._fetch_secret(key)
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from floe_core.audit.logger import get_audit_logger
from floe_core.schemas.audit import AuditOperation

if TYPE_CHECKING:
    from collections.abc import Callable

# TypeVar for decorated function return type
T = TypeVar("T")


def audit_secret_access(
    operation: AuditOperation,
    *,
    secret_path_arg: str = "key",
    plugin_type_attr: str = "name",
    namespace_attr: str | None = "namespace",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to automatically log audit events for secret operations.

    Wraps a method to log audit events before and after execution,
    capturing success, errors, and permission denied cases.

    Args:
        operation: The type of secret operation being performed.
        secret_path_arg: Name of the argument containing the secret path/key.
            Defaults to "key".
        plugin_type_attr: Attribute name on self to get plugin type.
            Defaults to "name".
        namespace_attr: Attribute name on self to get namespace, or None to skip.
            Defaults to "namespace".

    Returns:
        Decorator function that wraps the method with audit logging.

    Example:
        >>> class MySecretsPlugin(SecretsPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my-plugin"
        ...
        ...     @property
        ...     def namespace(self) -> str:
        ...         return "default"
        ...
        ...     @audit_secret_access(AuditOperation.GET)
        ...     def get_secret(self, key: str) -> str | None:
        ...         return self._fetch_secret(key)
        ...
        ...     @audit_secret_access(AuditOperation.SET, secret_path_arg="key")
        ...     def set_secret(self, key: str, value: str, metadata=None) -> None:
        ...         self._store_secret(key, value, metadata)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            # Extract audit context from self and arguments
            plugin_type = _get_attr_safe(self, plugin_type_attr)
            namespace = _get_attr_safe(self, namespace_attr) if namespace_attr else None

            # Get requester ID (from self if available, otherwise "unknown")
            requester_id = _get_attr_safe(self, "requester_id") or "system"

            # Extract secret path from arguments
            secret_path = _extract_secret_path(func, args, kwargs, secret_path_arg)

            logger = get_audit_logger()

            try:
                # Execute the actual method
                result = func(self, *args, **kwargs)

                # Log success
                logger.log_success(
                    requester_id=requester_id,
                    secret_path=secret_path,
                    operation=operation,
                    plugin_type=plugin_type,
                    namespace=namespace,
                )

                return result

            except PermissionError as e:
                # Log access denied
                logger.log_denied(
                    requester_id=requester_id,
                    secret_path=secret_path,
                    operation=operation,
                    reason=str(e),
                    plugin_type=plugin_type,
                    namespace=namespace,
                )
                raise

            except Exception as e:
                # Log error
                logger.log_error(
                    requester_id=requester_id,
                    secret_path=secret_path,
                    operation=operation,
                    error=str(e),
                    plugin_type=plugin_type,
                    namespace=namespace,
                )
                raise

        return wrapper

    return decorator


def _get_attr_safe(obj: Any, attr: str | None) -> str | None:
    """Safely get an attribute from an object.

    Args:
        obj: Object to get attribute from.
        attr: Attribute name, or None.

    Returns:
        Attribute value as string, or None if not found.
    """
    if attr is None:
        return None
    try:
        value = getattr(obj, attr, None)
        return str(value) if value is not None else None
    except Exception:
        return None


def _extract_secret_path(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    arg_name: str,
) -> str:
    """Extract secret path from function arguments.

    Args:
        func: The decorated function.
        args: Positional arguments.
        kwargs: Keyword arguments.
        arg_name: Name of the argument containing the secret path.

    Returns:
        Secret path string, or "unknown" if not found.
    """
    # First check kwargs
    if arg_name in kwargs:
        return str(kwargs[arg_name])

    # Try to find in positional args by inspecting function signature
    try:
        import inspect

        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Skip 'self' parameter
        if params and params[0] == "self":
            params = params[1:]

        if arg_name in params:
            idx = params.index(arg_name)
            if idx < len(args):
                return str(args[idx])
    except Exception:
        pass

    # Fallback: check if first arg looks like a path
    if args:
        return str(args[0])

    return "unknown"


__all__ = [
    "audit_secret_access",
]
