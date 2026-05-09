"""JSON-safe dlt filesystem source construction."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_OBJECT_STORE_SCHEMES = {"s3", "gs", "az"}
_SUPPORTED_FORMATS = {"csv", "jsonl", "parquet"}
_SAFE_SOURCE_CONFIG_KEYS = {"format", "path", "include_glob", "file_glob", "reader_options"}
_BOOL_STRING_VALUES = {
    "false": False,
    "no": False,
    "0": False,
    "off": False,
    "true": True,
    "yes": True,
    "1": True,
    "on": True,
}
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


@dataclass(frozen=True)
class _FilesystemSourceProbe:
    bucket_url: str
    file_glob: str
    matched: bool | None


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

    readers: dict[str, Callable[..., Any]] = {
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
    source_probe = _filesystem_source_probe(
        target,
        credentials=credentials,
    )
    if credentials:
        filesystem_kwargs["credentials"] = credentials
    filesystem_resource = filesystem(**filesystem_kwargs)
    dlt_resource = filesystem_resource | readers[file_format](**reader_options)
    dlt_resource = dlt_resource.with_name(table_name).apply_hints(table_name=table_name)
    _attach_filesystem_source_probe(dlt_resource, source_probe)
    return dlt_resource


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
        "endpoint_url",
        "s3_endpoint",
        "endpoint",
        "minio_endpoint",
    )
    if endpoint_url is not None:
        credentials["endpoint_url"] = str(endpoint_url)
    region_name = os.environ.get("AWS_REGION") or _first_config_value(
        filesystem_config,
        "region_name",
        "s3_region",
        "region",
    )
    if region_name is not None:
        credentials["region_name"] = str(region_name)
    path_style = _first_config_value(
        filesystem_config,
        "s3_path_style_access",
        "path_style_access",
    )
    if path_style is not None:
        path_style = _bool_like_config_value(path_style)
    if path_style is None:
        explicit_url_style = filesystem_config.get("s3_url_style")
        path_style = (
            explicit_url_style == "path"
            if explicit_url_style is not None
            else (endpoint_url is not None)
        )
    if path_style:
        credentials["s3_url_style"] = "path"
    return credentials


def _filesystem_source_probe(
    target: _FilesystemTarget,
    *,
    credentials: Mapping[str, str],
) -> _FilesystemSourceProbe:
    """Probe whether the configured filesystem target matches at least one file."""
    matched = _local_filesystem_match(target)
    if matched is None:
        matched = _object_store_match(target, credentials=credentials)
    return _FilesystemSourceProbe(
        bucket_url=target.bucket_url,
        file_glob=target.file_glob,
        matched=matched,
    )


def _local_filesystem_match(target: _FilesystemTarget) -> bool | None:
    if urlsplit(target.bucket_url).scheme:
        return None
    bucket_path = Path(target.bucket_url)
    return any(path.is_file() for path in bucket_path.glob(target.file_glob))


def _object_store_match(
    target: _FilesystemTarget,
    *,
    credentials: Mapping[str, str],
) -> bool | None:
    if urlsplit(target.bucket_url).scheme != "s3":
        return None

    try:
        from fsspec.core import url_to_fs
    except ImportError:
        return None

    storage_options = _fsspec_s3_storage_options(credentials)
    try:
        fs, glob_path = url_to_fs(
            _join_filesystem_glob(target.bucket_url, target.file_glob),
            **storage_options,
        )
        return any(not fs.isdir(path) for path in fs.glob(glob_path))
    except Exception:  # noqa: BLE001
        return None


def _fsspec_s3_storage_options(credentials: Mapping[str, str]) -> dict[str, Any]:
    storage_options: dict[str, Any] = {}
    access_key = credentials.get("aws_access_key_id")
    if access_key:
        storage_options["key"] = access_key
    secret_key = credentials.get("aws_secret_access_key")
    if secret_key:
        storage_options["secret"] = secret_key
    session_token = credentials.get("aws_session_token")
    if session_token:
        storage_options["token"] = session_token

    client_kwargs: dict[str, str] = {}
    endpoint_url = credentials.get("endpoint_url")
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    region_name = credentials.get("region_name")
    if region_name:
        client_kwargs["region_name"] = region_name
    if client_kwargs:
        storage_options["client_kwargs"] = client_kwargs
    config_kwargs: dict[str, Any] = {
        "connect_timeout": 1,
        "read_timeout": 1,
        "retries": {"max_attempts": 1},
    }
    if credentials.get("s3_url_style") == "path":
        config_kwargs["s3"] = {"addressing_style": "path"}
    storage_options["config_kwargs"] = config_kwargs
    return storage_options


def _join_filesystem_glob(bucket_url: str, file_glob: str) -> str:
    return f"{bucket_url.rstrip('/')}/{file_glob.lstrip('/')}"


def _attach_filesystem_source_probe(dlt_resource: Any, probe: _FilesystemSourceProbe) -> None:
    try:
        dlt_resource._floe_filesystem_source_probe = probe
    except Exception:  # noqa: BLE001
        return


def _first_config_value(config: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        value = config.get(key)
        if value not in (None, ""):
            return value
    return None


def _bool_like_config_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return _BOOL_STRING_VALUES.get(normalized, value)
    return value


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
