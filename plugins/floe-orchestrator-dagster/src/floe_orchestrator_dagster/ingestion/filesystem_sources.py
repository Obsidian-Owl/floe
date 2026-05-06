"""JSON-safe dlt filesystem source construction."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_OBJECT_STORE_SCHEMES = {"s3", "gs", "az"}
_SUPPORTED_FORMATS = {"csv", "jsonl", "parquet"}
_SAFE_SOURCE_CONFIG_KEYS = {"format", "path", "include_glob", "file_glob", "reader_options"}
_CONNECTION_LIKE_KEYS = {
    "endpoint",
    "access_key",
    "accessKey",
    "api_key",
    "apiKey",
    "secret_key",
    "secretKey",
    "secret_access_key",
    "secretAccessKey",
    "token",
    "database",
    "host",
    "port",
    "username",
    "password",
    "credentials",
    "connection_string",
    "connectionString",
}
_NORMALIZED_CONNECTION_LIKE_KEYS = {
    re.sub(r"[^a-z0-9]", "", key.lower()) for key in _CONNECTION_LIKE_KEYS
}
_READER_OPTION_ALLOWLISTS = {
    "csv": {
        "chunksize",
        "sep",
        "delimiter",
        "header",
        "names",
        "dtype",
        "encoding",
        "quotechar",
        "escapechar",
        "na_values",
        "keep_default_na",
    },
    "jsonl": {"chunksize"},
    "parquet": {"chunksize", "use_pyarrow"},
}
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class _FilesystemTarget:
    bucket_url: str
    file_glob: str


def build_filesystem_source(
    source_config: Mapping[str, Any],
    *,
    project_dir: Path,
    filesystem_config: Mapping[str, Any] | None = None,
) -> Any:
    """Build a dlt filesystem source or resource from compiled ingestion config."""
    source_name = _source_name(source_config)
    _validate_source_type(source_config, source_name)
    table_name = _validate_destination_table(source_config, source_name)
    nested_config = _nested_source_config(source_config, source_name)
    file_format = _file_format(nested_config, source_name)
    _validate_json_safe_keys(nested_config, source_name)
    file_glob = _file_glob(nested_config, source_name)
    target = _filesystem_target(
        nested_config,
        file_glob=file_glob,
        project_dir=project_dir,
        source_name=source_name,
    )
    reader_options = _reader_options(nested_config, file_format, source_name)

    from dlt.sources.filesystem import filesystem, read_csv, read_jsonl, read_parquet

    readers = {
        "csv": read_csv,
        "jsonl": read_jsonl,
        "parquet": read_parquet,
    }
    filesystem_kwargs: dict[str, Any] = {
        "bucket_url": target.bucket_url,
        "file_glob": target.file_glob,
    }
    credentials = _object_store_credentials(
        target.bucket_url,
        filesystem_config=filesystem_config or {},
    )
    if credentials:
        filesystem_kwargs["credentials"] = credentials
    filesystem_resource = filesystem(**filesystem_kwargs)
    dlt_resource = filesystem_resource | readers[file_format](**reader_options)
    return dlt_resource.with_name(table_name).apply_hints(table_name=table_name)


def _source_name(source_config: Mapping[str, Any]) -> str:
    source_name = source_config.get("name", "unnamed")
    return str(source_name)


def _validate_source_type(source_config: Mapping[str, Any], source_name: str) -> None:
    source_type = source_config.get("source_type", "missing")
    if source_type != "filesystem":
        raise ValueError(f"Unsupported ingestion source_type {source_type!r} for {source_name!r}")


def _validate_destination_table(source_config: Mapping[str, Any], source_name: str) -> str:
    destination_table = source_config.get("destination_table")
    if not isinstance(destination_table, str):
        raise ValueError(f"destination_table is required for {source_name!r}")
    parts = destination_table.split(".")
    if len(parts) != 2 or any(part.strip() != part or not part for part in parts):
        raise ValueError(f"destination_table must be exactly namespace.table for {source_name!r}")
    if any(_IDENTIFIER.fullmatch(part) is None for part in parts):
        raise ValueError(
            f"destination_table contains unsafe identifier characters for {source_name!r}"
        )
    return parts[1]


def _nested_source_config(
    source_config: Mapping[str, Any],
    source_name: str,
) -> Mapping[str, Any]:
    nested_config = source_config.get("source_config")
    if not isinstance(nested_config, Mapping):
        raise ValueError(f"source_config must be a mapping for {source_name!r}")
    return nested_config


def _file_format(nested_config: Mapping[str, Any], source_name: str) -> str:
    file_format = nested_config.get("format")
    if not isinstance(file_format, str) or not file_format:
        raise ValueError(f"format is required for {source_name!r}")
    if file_format not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported filesystem format {file_format!r} for {source_name!r}")
    return file_format


def _filesystem_target(
    nested_config: Mapping[str, Any],
    *,
    file_glob: str,
    project_dir: Path,
    source_name: str,
) -> _FilesystemTarget:
    path = nested_config.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError(f"path is required for {source_name!r}")

    parsed = urlsplit(path)
    if parsed.scheme:
        if parsed.scheme in _OBJECT_STORE_SCHEMES:
            return _FilesystemTarget(bucket_url=path, file_glob=file_glob)
        raise ValueError(
            f"path URI scheme must be one of s3://, gs://, or az:// for {source_name!r}"
        )

    local_path = Path(path)
    if local_path.is_absolute():
        raise ValueError(f"absolute local paths are not portable for {source_name!r}")

    project_root = project_dir.resolve()
    resolved_path = (project_root / local_path).resolve()
    try:
        resolved_path.relative_to(project_root)
    except ValueError:
        raise ValueError(f"path escapes project_dir for {source_name!r}") from None

    if _is_directory_path(path, resolved_path):
        return _FilesystemTarget(bucket_url=str(resolved_path), file_glob=file_glob)

    if _has_explicit_glob(nested_config):
        raise ValueError(
            f"file path cannot be combined with file_glob/include_glob for {source_name!r}"
        )
    return _FilesystemTarget(bucket_url=str(resolved_path.parent), file_glob=resolved_path.name)


def _object_store_credentials(
    bucket_url: str,
    *,
    filesystem_config: Mapping[str, Any],
) -> dict[str, str]:
    """Build dlt filesystem credentials from platform config and runtime env."""
    if urlsplit(bucket_url).scheme != "s3":
        return {}

    credentials: dict[str, str] = {}
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    if aws_access_key:
        credentials["aws_access_key_id"] = aws_access_key
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if aws_secret_key:
        credentials["aws_secret_access_key"] = aws_secret_key
    aws_session_token = os.environ.get("AWS_SESSION_TOKEN")
    if aws_session_token:
        credentials["aws_session_token"] = aws_session_token

    endpoint_url = _first_config_value(
        filesystem_config,
        "s3_endpoint",
        "endpoint",
        "minio_endpoint",
    )
    if endpoint_url is not None:
        credentials["endpoint_url"] = str(endpoint_url)
    region_name = os.environ.get("AWS_REGION") or _first_config_value(
        filesystem_config,
        "s3_region",
        "region",
    )
    if region_name is not None:
        credentials["region_name"] = str(region_name)
    path_style = filesystem_config.get(
        "s3_path_style_access",
        filesystem_config.get("path_style_access", endpoint_url is not None),
    )
    if path_style:
        credentials["s3_url_style"] = "path"
    return credentials


def _first_config_value(config: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        value = config.get(key)
        if value not in (None, ""):
            return value
    return None


def _is_directory_path(raw_path: str, resolved_path: Path) -> bool:
    return raw_path.endswith("/") or resolved_path.is_dir() or not Path(raw_path).suffix


def _file_glob(nested_config: Mapping[str, Any], source_name: str) -> str:
    file_glob = nested_config.get("file_glob")
    include_glob = nested_config.get("include_glob")
    if file_glob is not None and include_glob is not None and file_glob != include_glob:
        raise ValueError(f"file_glob and include_glob conflict for {source_name!r}")
    glob_value = file_glob if file_glob is not None else include_glob
    if glob_value is None:
        return "*"
    if not isinstance(glob_value, str) or not glob_value:
        raise ValueError(f"file_glob must be a non-empty string for {source_name!r}")
    return glob_value


def _reader_options(
    nested_config: Mapping[str, Any],
    file_format: str,
    source_name: str,
) -> dict[str, Any]:
    reader_options = nested_config.get("reader_options", {})
    if not isinstance(reader_options, Mapping):
        raise ValueError(f"reader_options must be a mapping for {source_name!r}")
    blocked_keys = _credential_like_keys(reader_options)
    if blocked_keys:
        blocked = ", ".join(blocked_keys)
        raise ValueError(
            f"reader_options contains connection-like keys {blocked} for {source_name!r}"
        )
    allowlist = _READER_OPTION_ALLOWLISTS[file_format]
    unsupported_options = sorted(set(reader_options) - allowlist)
    if unsupported_options:
        unsupported = ", ".join(unsupported_options)
        raise ValueError(
            f"reader_options contains unsupported keys {unsupported} "
            f"for {file_format} source {source_name!r}"
        )
    return dict(reader_options)


def _validate_json_safe_keys(nested_config: Mapping[str, Any], source_name: str) -> None:
    connection_like_keys = _credential_like_keys(nested_config)
    if connection_like_keys:
        blocked = ", ".join(connection_like_keys)
        raise ValueError(
            f"source_config contains connection-like keys {blocked} for {source_name!r}"
        )

    unsupported_keys = sorted(set(nested_config) - _SAFE_SOURCE_CONFIG_KEYS)
    if unsupported_keys:
        unsupported = ", ".join(unsupported_keys)
        raise ValueError(
            f"source_config contains unsupported keys {unsupported} for {source_name!r}"
        )


def _has_explicit_glob(nested_config: Mapping[str, Any]) -> bool:
    return (
        nested_config.get("file_glob") is not None or nested_config.get("include_glob") is not None
    )


def _credential_like_keys(mapping: Mapping[str, Any]) -> list[str]:
    return sorted(
        key
        for key in mapping
        if isinstance(key, str) and _normalize_key(key) in _NORMALIZED_CONNECTION_LIKE_KEYS
    )


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


__all__ = [
    "build_filesystem_source",
]
