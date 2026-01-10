"""Credential vending helper module.

This module encapsulates the logic for extracting and validating vended
credentials from PyIceberg table.io properties. It provides a clean API
for parsing STS credentials returned by the Polaris catalog.

Functions:
    extract_credentials_from_io_properties: Extract credentials from table.io
    parse_expiration: Parse expiration timestamp string to datetime
    validate_credential_structure: Validate credential dict has required keys
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Property keys used by PyIceberg for S3 credentials
S3_ACCESS_KEY_ID = "s3.access-key-id"
S3_SECRET_ACCESS_KEY = "s3.secret-access-key"
S3_SESSION_TOKEN = "s3.session-token"
S3_SESSION_TOKEN_EXPIRES_AT = "s3.session-token-expires-at"

# Required keys in credential response
REQUIRED_CREDENTIAL_KEYS = frozenset({"access_key", "secret_key", "expiration"})


def parse_expiration(expiration_str: str) -> datetime | None:
    """Parse expiration timestamp string to datetime.

    Handles various ISO 8601 formats including:
    - "2026-01-09T12:00:00Z" (UTC with Z suffix)
    - "2026-01-09T12:00:00+00:00" (UTC with offset)
    - "2026-01-09T12:00:00" (naive, assumed UTC)
    - Epoch milliseconds as string (e.g., "1736431200000")

    Args:
        expiration_str: Expiration timestamp as string.

    Returns:
        Parsed datetime in UTC, or None if parsing fails.

    Example:
        >>> parse_expiration("2026-01-09T12:00:00Z")
        datetime.datetime(2026, 1, 9, 12, 0, tzinfo=datetime.timezone.utc)
    """
    if not expiration_str:
        return None

    # Try ISO 8601 format first
    try:
        # Handle Z suffix
        normalized = expiration_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

        # Ensure timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except ValueError:
        pass

    # Try epoch milliseconds
    if re.match(r"^\d{13}$", expiration_str):
        try:
            epoch_ms = int(expiration_str)
            return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        except (ValueError, OSError):
            pass

    # Try epoch seconds
    if re.match(r"^\d{10}$", expiration_str):
        try:
            epoch_s = int(expiration_str)
            return datetime.fromtimestamp(epoch_s, tz=timezone.utc)
        except (ValueError, OSError):
            pass

    logger.warning(
        "failed_to_parse_expiration",
        expiration_str=expiration_str,
    )
    return None


def validate_credential_structure(credentials: dict[str, Any]) -> list[str]:
    """Validate credential dictionary has required keys.

    Checks that the credentials dictionary contains the minimum required
    keys for valid STS credentials.

    Args:
        credentials: Credential dictionary to validate.

    Returns:
        List of missing keys (empty if valid).

    Example:
        >>> validate_credential_structure({"access_key": "...", "secret_key": "..."})
        ['expiration']
    """
    missing = []
    for key in REQUIRED_CREDENTIAL_KEYS:
        if key not in credentials or not credentials[key]:
            missing.append(key)
    return missing


def extract_credentials_from_io_properties(
    io_properties: dict[str, Any],
) -> dict[str, Any]:
    """Extract vended credentials from PyIceberg table.io properties.

    PyIceberg stores vended credentials in the table.io.properties dictionary
    when the catalog supports credential vending (via X-Iceberg-Access-Delegation
    header). This function extracts and normalizes those credentials.

    Args:
        io_properties: Dictionary from table.io.properties containing S3
            credentials vended by the catalog.

    Returns:
        Dictionary containing normalized credentials:
            - access_key: Temporary access key
            - secret_key: Temporary secret key
            - token: Session token (may be empty string if not using STS)
            - expiration: Expiration timestamp as ISO 8601 string

    Example:
        >>> props = {
        ...     "s3.access-key-id": "ASIA...",
        ...     "s3.secret-access-key": "secret...",
        ...     "s3.session-token": "token...",
        ...     "s3.session-token-expires-at": "2026-01-09T12:00:00Z",
        ... }
        >>> creds = extract_credentials_from_io_properties(props)
        >>> creds["access_key"]
        'ASIA...'
    """
    credentials: dict[str, Any] = {
        "access_key": io_properties.get(S3_ACCESS_KEY_ID, ""),
        "secret_key": io_properties.get(S3_SECRET_ACCESS_KEY, ""),
        "token": io_properties.get(S3_SESSION_TOKEN, ""),
        "expiration": io_properties.get(S3_SESSION_TOKEN_EXPIRES_AT, ""),
    }

    logger.debug(
        "extracted_credentials_from_io",
        has_access_key=bool(credentials["access_key"]),
        has_secret_key=bool(credentials["secret_key"]),
        has_token=bool(credentials["token"]),
        has_expiration=bool(credentials["expiration"]),
    )

    return credentials


def credentials_are_valid(credentials: dict[str, Any]) -> bool:
    """Check if credentials have required fields with non-empty values.

    Validates that access_key and secret_key are present and non-empty.
    Token and expiration are optional for some storage backends.

    Args:
        credentials: Credential dictionary to validate.

    Returns:
        True if credentials have required fields, False otherwise.

    Example:
        >>> credentials_are_valid({"access_key": "key", "secret_key": "secret"})
        True
        >>> credentials_are_valid({"access_key": "", "secret_key": "secret"})
        False
    """
    return bool(credentials.get("access_key")) and bool(credentials.get("secret_key"))


def is_expired(credentials: dict[str, Any]) -> bool:
    """Check if credentials have expired.

    Parses the expiration field and compares to current time.

    Args:
        credentials: Credential dictionary with expiration field.

    Returns:
        True if credentials are expired, False if valid or no expiration set.

    Example:
        >>> creds = {"expiration": "2020-01-01T00:00:00Z"}
        >>> is_expired(creds)
        True
    """
    expiration_str = credentials.get("expiration", "")
    if not expiration_str:
        # No expiration set - assume valid
        return False

    expiration_dt = parse_expiration(expiration_str)
    if expiration_dt is None:
        # Could not parse - assume valid to avoid false negatives
        logger.warning(
            "could_not_parse_expiration_assuming_valid",
            expiration=expiration_str,
        )
        return False

    return datetime.now(timezone.utc) >= expiration_dt


def get_expiration_datetime(credentials: dict[str, Any]) -> datetime | None:
    """Get expiration as datetime object.

    Args:
        credentials: Credential dictionary with expiration field.

    Returns:
        Expiration as datetime, or None if not set or unparseable.
    """
    expiration_str = credentials.get("expiration", "")
    if not expiration_str:
        return None
    return parse_expiration(expiration_str)
