"""CLI commands for floe artifact operations.

This module implements the `floe artifact` subcommand group for managing
OCI artifacts:
    - floe artifact push: Push CompiledArtifacts to OCI registry
    - floe artifact pull: Pull CompiledArtifacts from OCI registry (T029)
    - floe artifact inspect: Inspect artifact metadata (T034)
    - floe artifact list: List available artifacts (T039)

Example:
    $ floe artifact push --source target/compiled_artifacts.json --tag v1.0.0
    Pushed artifact with digest: sha256:abc123...

Exit Codes:
    0: Success
    1: General error (network failure, invalid config, etc.)
    2: Authentication error
    4: Immutability violation (attempting to overwrite semver tag)
    5: Circuit breaker open (registry unavailable)

See Also:
    - specs/08a-oci-client/spec.md: Feature specification
    - floe_core.oci.client: OCIClient implementation
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from datetime import datetime
    from typing import NoReturn

logger = structlog.get_logger(__name__)


# Exit codes for artifact commands
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_AUTH_ERROR = 2
EXIT_NOT_FOUND_ERROR = 3
EXIT_IMMUTABILITY_ERROR = 4
EXIT_CIRCUIT_BREAKER_ERROR = 5


def create_push_parser() -> argparse.ArgumentParser:
    """Create argument parser for artifact push command.

    Returns:
        Configured ArgumentParser for the push command.

    Example:
        >>> parser = create_push_parser()
        >>> args = parser.parse_args(
        ...     ["--source", "target/compiled_artifacts.json", "--tag", "v1.0.0"]
        ... )
        >>> args.source
        Path('target/compiled_artifacts.json')
    """
    parser = argparse.ArgumentParser(
        prog="floe artifact push",
        description="Push CompiledArtifacts to OCI registry",
        epilog="Exit codes: 0=success, 1=error, 2=auth error, 4=immutability violation",
    )

    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to CompiledArtifacts JSON file",
        metavar="PATH",
    )

    parser.add_argument(
        "--tag",
        type=str,
        required=True,
        help="Tag for the artifact (e.g., v1.0.0, latest-dev)",
        metavar="TAG",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.yaml"),
        help="Path to manifest.yaml with registry config (default: manifest.yaml)",
        metavar="PATH",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-error output",
    )

    return parser


def run_push(args: argparse.Namespace) -> int:
    """Execute the artifact push command.

    Loads CompiledArtifacts from the source file and pushes to the
    OCI registry configured in manifest.yaml.

    Args:
        args: Parsed command-line arguments with:
            - source: Path to CompiledArtifacts JSON file
            - tag: Tag for the artifact
            - manifest: Path to manifest.yaml
            - verbose: Enable verbose output
            - quiet: Suppress non-error output

    Returns:
        Exit code: 0=success, 1=error, 2=auth error, 4=immutability violation.

    Example:
        >>> args = create_push_parser().parse_args(
        ...     ["--source", "compiled.json", "--tag", "v1.0.0"]
        ... )
        >>> exit_code = run_push(args)
    """
    # Late imports to avoid circular dependencies
    from floe_core.oci.client import OCIClient
    from floe_core.oci.errors import (
        AuthenticationError,
        CircuitBreakerOpenError,
        ImmutabilityViolationError,
        OCIError,
    )
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts

    log = logger.bind(
        source_path=str(args.source),
        tag=args.tag,
        manifest_path=str(args.manifest),
    )

    # Validate source file exists
    if not args.source.exists():
        if not args.quiet:
            print(f"Error: Source file not found: {args.source}", file=sys.stderr)
        log.error("source_file_not_found", source=str(args.source))
        return EXIT_GENERAL_ERROR

    if not args.quiet:
        log.info("push_started")

    try:
        # Load CompiledArtifacts from source file
        artifacts = CompiledArtifacts.from_json_file(args.source)

        if args.verbose and not args.quiet:
            log.info(
                "artifacts_loaded",
                product_name=artifacts.metadata.product_name,
                product_version=artifacts.metadata.product_version,
            )

        # Create OCI client from manifest
        client = OCIClient.from_manifest(args.manifest)

        if args.verbose and not args.quiet:
            log.info(
                "client_initialized",
                registry=client.registry_uri,
            )

        # Push artifact
        digest = client.push(artifacts, tag=args.tag)

        if not args.quiet:
            print(f"Pushed artifact with digest: {digest}")
            log.info(
                "push_completed",
                digest=digest,
                tag=args.tag,
            )

        return EXIT_SUCCESS

    except AuthenticationError as e:
        if not args.quiet:
            print(f"Error: Authentication failed - {e}", file=sys.stderr)
        log.error("push_auth_failed", error=str(e))
        return EXIT_AUTH_ERROR

    except ImmutabilityViolationError as e:
        if not args.quiet:
            print(f"Error: Immutability violation - {e}", file=sys.stderr)
            print("Hint: Use a different version number or a mutable tag", file=sys.stderr)
        log.error("push_immutability_violation", error=str(e))
        return EXIT_IMMUTABILITY_ERROR

    except CircuitBreakerOpenError as e:
        if not args.quiet:
            print(f"Error: Registry unavailable - {e}", file=sys.stderr)
            print("Hint: Wait for circuit breaker to reset and retry", file=sys.stderr)
        log.error("push_circuit_breaker_open", error=str(e))
        return EXIT_CIRCUIT_BREAKER_ERROR

    except OCIError as e:
        if not args.quiet:
            print(f"Error: Push failed - {e}", file=sys.stderr)
        log.error("push_failed", error=str(e))
        return EXIT_GENERAL_ERROR

    except Exception as e:
        if not args.quiet:
            print(f"Error: Unexpected error - {e}", file=sys.stderr)
        log.exception("push_unexpected_error", error=str(e))
        return EXIT_GENERAL_ERROR


def create_pull_parser() -> argparse.ArgumentParser:
    """Create argument parser for artifact pull command.

    Returns:
        Configured ArgumentParser for the pull command.

    Example:
        >>> parser = create_pull_parser()
        >>> args = parser.parse_args(["--tag", "v1.0.0", "--output", "./artifacts/"])
        >>> args.tag
        'v1.0.0'
    """
    parser = argparse.ArgumentParser(
        prog="floe artifact pull",
        description="Pull CompiledArtifacts from OCI registry",
        epilog="Exit codes: 0=success, 1=error, 2=auth error, 3=not found",
    )

    parser.add_argument(
        "--tag",
        type=str,
        required=True,
        help="Tag for the artifact to pull (e.g., v1.0.0, latest-dev)",
        metavar="TAG",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory path for the pulled artifact",
        metavar="PATH",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.yaml"),
        help="Path to manifest.yaml with registry config (default: manifest.yaml)",
        metavar="PATH",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-error output",
    )

    return parser


def run_pull(args: argparse.Namespace) -> int:
    """Execute the artifact pull command.

    Pulls CompiledArtifacts from the OCI registry configured in manifest.yaml
    and saves to the output directory.

    Args:
        args: Parsed command-line arguments with:
            - tag: Tag of the artifact to pull
            - output: Output directory path
            - manifest: Path to manifest.yaml
            - verbose: Enable verbose output
            - quiet: Suppress non-error output

    Returns:
        Exit code: 0=success, 1=error, 2=auth error, 3=not found.

    Example:
        >>> args = create_pull_parser().parse_args(
        ...     ["--tag", "v1.0.0", "--output", "./artifacts/"]
        ... )
        >>> exit_code = run_pull(args)
    """
    # Late imports to avoid circular dependencies
    from floe_core.oci.client import OCIClient
    from floe_core.oci.errors import (
        ArtifactNotFoundError,
        AuthenticationError,
        CircuitBreakerOpenError,
        OCIError,
    )

    log = logger.bind(
        tag=args.tag,
        output_path=str(args.output),
        manifest_path=str(args.manifest),
    )

    # Validate output directory exists
    if not args.output.exists():
        if not args.quiet:
            print(f"Error: Output directory not found: {args.output}", file=sys.stderr)
        log.error("output_dir_not_found", output=str(args.output))
        return EXIT_GENERAL_ERROR

    if not args.quiet:
        log.info("pull_started")

    try:
        # Create OCI client from manifest
        client = OCIClient.from_manifest(args.manifest)

        if args.verbose and not args.quiet:
            log.info(
                "client_initialized",
                registry=client.registry_uri,
            )

        # Pull artifact
        artifacts = client.pull(tag=args.tag)

        # Save to output directory
        output_file = args.output / "compiled_artifacts.json"
        artifacts.to_json_file(output_file)

        if not args.quiet:
            print(f"Pulled artifact to: {output_file}")
            log.info(
                "pull_completed",
                tag=args.tag,
                output=str(output_file),
            )

        return EXIT_SUCCESS

    except ArtifactNotFoundError as e:
        if not args.quiet:
            print(f"Error: Artifact not found - {e}", file=sys.stderr)
            print("Hint: Check the tag and registry configuration", file=sys.stderr)
        log.error("pull_not_found", error=str(e))
        return EXIT_NOT_FOUND_ERROR

    except AuthenticationError as e:
        if not args.quiet:
            print(f"Error: Authentication failed - {e}", file=sys.stderr)
        log.error("pull_auth_failed", error=str(e))
        return EXIT_AUTH_ERROR

    except CircuitBreakerOpenError as e:
        if not args.quiet:
            print(f"Error: Registry unavailable - {e}", file=sys.stderr)
            print("Hint: Wait for circuit breaker to reset and retry", file=sys.stderr)
        log.error("pull_circuit_breaker_open", error=str(e))
        return EXIT_CIRCUIT_BREAKER_ERROR

    except OCIError as e:
        if not args.quiet:
            print(f"Error: Pull failed - {e}", file=sys.stderr)
        log.error("pull_failed", error=str(e))
        return EXIT_GENERAL_ERROR

    except Exception as e:
        if not args.quiet:
            print(f"Error: Unexpected error - {e}", file=sys.stderr)
        log.exception("pull_unexpected_error", error=str(e))
        return EXIT_GENERAL_ERROR


def create_inspect_parser() -> argparse.ArgumentParser:
    """Create argument parser for artifact inspect command.

    Returns:
        Configured ArgumentParser for the inspect command.

    Example:
        >>> parser = create_inspect_parser()
        >>> args = parser.parse_args(["--tag", "v1.0.0"])
        >>> args.tag
        'v1.0.0'
    """
    parser = argparse.ArgumentParser(
        prog="floe artifact inspect",
        description="Inspect artifact metadata from OCI registry",
        epilog="Exit codes: 0=success, 1=error, 2=auth error, 3=not found",
    )

    parser.add_argument(
        "--tag",
        type=str,
        required=True,
        help="Tag for the artifact to inspect (e.g., v1.0.0, latest-dev)",
        metavar="TAG",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.yaml"),
        help="Path to manifest.yaml with registry config (default: manifest.yaml)",
        metavar="PATH",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of human-readable format",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-error output (only show result)",
    )

    return parser


def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string like "12.3 KB" or "1.5 MB".
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def run_inspect(args: argparse.Namespace) -> int:
    """Execute the artifact inspect command.

    Retrieves artifact metadata from the OCI registry without downloading
    the full artifact content.

    Args:
        args: Parsed command-line arguments with:
            - tag: Tag of the artifact to inspect
            - manifest: Path to manifest.yaml
            - json_output: Output as JSON
            - verbose: Enable verbose output
            - quiet: Suppress non-error output

    Returns:
        Exit code: 0=success, 1=error, 2=auth error, 3=not found.

    Example:
        >>> args = create_inspect_parser().parse_args(["--tag", "v1.0.0"])
        >>> exit_code = run_inspect(args)
    """
    import json

    # Late imports to avoid circular dependencies
    from floe_core.oci.client import OCIClient
    from floe_core.oci.errors import (
        ArtifactNotFoundError,
        AuthenticationError,
        CircuitBreakerOpenError,
        OCIError,
    )

    log = logger.bind(
        tag=args.tag,
        manifest_path=str(args.manifest),
    )

    if not args.quiet:
        log.info("inspect_started")

    try:
        # Create OCI client from manifest
        client = OCIClient.from_manifest(args.manifest)

        if args.verbose and not args.quiet:
            log.info(
                "client_initialized",
                registry=client.registry_uri,
            )

        # Inspect artifact
        manifest = client.inspect(tag=args.tag)

        # Format output
        if args.json_output:
            # JSON output mode
            output_data = {
                "digest": manifest.digest,
                "artifact_type": manifest.artifact_type,
                "size": manifest.size,
                "size_human": _format_size(manifest.size),
                "created_at": manifest.created_at.isoformat(),
                "product_name": manifest.product_name,
                "product_version": manifest.product_version,
                "signature_status": manifest.signature_status.value,
                "layers": [
                    {
                        "digest": layer.digest,
                        "media_type": layer.media_type,
                        "size": layer.size,
                    }
                    for layer in manifest.layers
                ],
                "annotations": manifest.annotations,
            }
            print(json.dumps(output_data, indent=2))
        else:
            # Human-readable output
            product_info = "N/A"
            if manifest.product_name:
                if manifest.product_version:
                    product_info = f"{manifest.product_name} v{manifest.product_version}"
                else:
                    product_info = manifest.product_name

            print(f"Digest:        {manifest.digest}")
            print(f"Artifact Type: {manifest.artifact_type}")
            print(f"Size:          {_format_size(manifest.size)}")
            print(f"Created:       {manifest.created_at.isoformat()}")
            print(f"Product:       {product_info}")
            print(f"Signature:     {manifest.signature_status.value}")

            if args.verbose:
                print(f"\nLayers ({len(manifest.layers)}):")
                for layer in manifest.layers:
                    print(f"  - {layer.digest[:19]}... ({_format_size(layer.size)})")

        if not args.quiet:
            log.info(
                "inspect_completed",
                digest=manifest.digest,
                tag=args.tag,
            )

        return EXIT_SUCCESS

    except ArtifactNotFoundError as e:
        if not args.quiet:
            print(f"Error: Artifact not found - {e}", file=sys.stderr)
            print("Hint: Check the tag and registry configuration", file=sys.stderr)
        log.error("inspect_not_found", error=str(e))
        return EXIT_NOT_FOUND_ERROR

    except AuthenticationError as e:
        if not args.quiet:
            print(f"Error: Authentication failed - {e}", file=sys.stderr)
        log.error("inspect_auth_failed", error=str(e))
        return EXIT_AUTH_ERROR

    except CircuitBreakerOpenError as e:
        if not args.quiet:
            print(f"Error: Registry unavailable - {e}", file=sys.stderr)
            print("Hint: Wait for circuit breaker to reset and retry", file=sys.stderr)
        log.error("inspect_circuit_breaker_open", error=str(e))
        return EXIT_CIRCUIT_BREAKER_ERROR

    except OCIError as e:
        if not args.quiet:
            print(f"Error: Inspect failed - {e}", file=sys.stderr)
        log.error("inspect_failed", error=str(e))
        return EXIT_GENERAL_ERROR

    except Exception as e:
        if not args.quiet:
            print(f"Error: Unexpected error - {e}", file=sys.stderr)
        log.exception("inspect_unexpected_error", error=str(e))
        return EXIT_GENERAL_ERROR


def create_list_parser() -> argparse.ArgumentParser:
    """Create argument parser for artifact list command.

    Returns:
        Configured ArgumentParser for the list command.

    Example:
        >>> parser = create_list_parser()
        >>> args = parser.parse_args(["--filter", "v1.*"])
        >>> args.filter
        'v1.*'
    """
    parser = argparse.ArgumentParser(
        prog="floe artifact list",
        description="List available artifacts in OCI registry",
        epilog="Exit codes: 0=success, 1=error, 2=auth error",
    )

    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Glob pattern to filter tags (e.g., v1.*, latest-*)",
        metavar="PATTERN",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.yaml"),
        help="Path to manifest.yaml with registry config (default: manifest.yaml)",
        metavar="PATH",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of table format",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-error output (only show result)",
    )

    return parser


def _format_date(dt: datetime) -> str:
    """Format datetime to date string.

    Args:
        dt: Datetime to format.

    Returns:
        Formatted date string like "2026-01-19".
    """
    return dt.strftime("%Y-%m-%d")


def _truncate_digest(digest: str, length: int = 15) -> str:
    """Truncate digest for display.

    Args:
        digest: Full digest string.
        length: Maximum length (default 15).

    Returns:
        Truncated digest with "..." suffix.
    """
    if len(digest) <= length:
        return digest
    return digest[:length] + "..."


def run_list(args: argparse.Namespace) -> int:
    """Execute the artifact list command.

    Lists available artifacts in the OCI registry configured in manifest.yaml.

    Args:
        args: Parsed command-line arguments with:
            - filter: Optional glob pattern to filter tags
            - manifest: Path to manifest.yaml
            - json_output: Output as JSON
            - verbose: Enable verbose output
            - quiet: Suppress non-error output

    Returns:
        Exit code: 0=success, 1=error, 2=auth error.

    Example:
        >>> args = create_list_parser().parse_args(["--filter", "v1.*"])
        >>> exit_code = run_list(args)
    """
    import json

    # Late imports to avoid circular dependencies
    from floe_core.oci.client import OCIClient
    from floe_core.oci.errors import (
        AuthenticationError,
        CircuitBreakerOpenError,
        OCIError,
    )

    log = logger.bind(
        filter_pattern=args.filter,
        manifest_path=str(args.manifest),
    )

    if not args.quiet:
        log.info("list_started")

    try:
        # Create OCI client from manifest
        client = OCIClient.from_manifest(args.manifest)

        if args.verbose and not args.quiet:
            log.info(
                "client_initialized",
                registry=client.registry_uri,
            )

        # List artifacts
        tags = client.list(filter_pattern=args.filter)

        # Format output
        if args.json_output:
            # JSON output mode
            output_data = [
                {
                    "name": tag.name,
                    "digest": tag.digest,
                    "size": tag.size,
                    "size_human": _format_size(tag.size),
                    "created_at": tag.created_at.isoformat(),
                }
                for tag in tags
            ]
            print(json.dumps(output_data, indent=2))
        else:
            # Table output mode
            if not tags:
                print("No artifacts found")
            else:
                # Print header
                print(f"{'TAG':<15} {'DIGEST':<20} {'SIZE':<10} {'CREATED':<12}")
                print("-" * 60)

                # Print rows
                for tag in tags:
                    tag_name = tag.name[:15] if len(tag.name) <= 15 else tag.name[:12] + "..."
                    digest_short = _truncate_digest(tag.digest, 20)
                    size_human = _format_size(tag.size)
                    created_date = _format_date(tag.created_at)

                    print(f"{tag_name:<15} {digest_short:<20} {size_human:<10} {created_date:<12}")

        if not args.quiet:
            log.info(
                "list_completed",
                tag_count=len(tags),
            )

        return EXIT_SUCCESS

    except AuthenticationError as e:
        if not args.quiet:
            print(f"Error: Authentication failed - {e}", file=sys.stderr)
        log.error("list_auth_failed", error=str(e))
        return EXIT_AUTH_ERROR

    except CircuitBreakerOpenError as e:
        if not args.quiet:
            print(f"Error: Registry unavailable - {e}", file=sys.stderr)
            print("Hint: Wait for circuit breaker to reset and retry", file=sys.stderr)
        log.error("list_circuit_breaker_open", error=str(e))
        return EXIT_CIRCUIT_BREAKER_ERROR

    except OCIError as e:
        if not args.quiet:
            print(f"Error: List failed - {e}", file=sys.stderr)
        log.error("list_failed", error=str(e))
        return EXIT_GENERAL_ERROR

    except Exception as e:
        if not args.quiet:
            print(f"Error: Unexpected error - {e}", file=sys.stderr)
        log.exception("list_unexpected_error", error=str(e))
        return EXIT_GENERAL_ERROR


def create_cache_status_parser() -> argparse.ArgumentParser:
    """Create argument parser for artifact cache status command.

    Returns:
        Configured ArgumentParser for the cache status command.

    Example:
        >>> parser = create_cache_status_parser()
        >>> args = parser.parse_args([])
        >>> args.quiet
        False
    """
    parser = argparse.ArgumentParser(
        prog="floe artifact cache status",
        description="Display cache status and statistics",
        epilog="Shows cache path, size, entry count, and expired entries.",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.yaml"),
        help="Path to manifest.yaml with cache config (default: manifest.yaml)",
        metavar="PATH",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (show per-entry details)",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output (exit code only)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    return parser


def run_cache_status(args: argparse.Namespace) -> int:
    """Run the cache status command.

    Displays cache statistics including path, size, entry count, and expired entries.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).

    Example:
        >>> args = create_cache_status_parser().parse_args([])
        >>> exit_code = run_cache_status(args)
    """
    import json

    from floe_core.oci.cache import CacheManager
    from floe_core.schemas.oci import CacheConfig

    log = logger.bind(command="cache_status")
    log.debug("cache_status_start")

    try:
        # Load manifest if exists
        cache_config: CacheConfig | None = None
        if args.manifest.exists():
            import yaml

            manifest_data = yaml.safe_load(args.manifest.read_text())
            if manifest_data and "oci" in manifest_data:
                oci_config = manifest_data["oci"]
                if "cache" in oci_config:
                    cache_config = CacheConfig(**oci_config["cache"])

        # Handle case where cache is not configured
        if cache_config is None:
            log.info("cache_not_configured")
            if not args.quiet:
                if args.json:
                    print(
                        json.dumps(
                            {
                                "status": "not_configured",
                                "message": "Cache not configured in manifest",
                            },
                            indent=2,
                        )
                    )
                else:
                    print("Cache not configured")
            return EXIT_SUCCESS

        # Create cache manager with config
        manager = CacheManager(cache_config)
        stats = manager.stats()

        log.info(
            "cache_status_retrieved",
            entry_count=stats["entry_count"],
            total_size_bytes=stats["total_size_bytes"],
        )

        if args.json:
            # JSON output
            if not args.quiet:
                print(json.dumps(stats, indent=2, default=str))
        else:
            # Human-readable output
            if not args.quiet:
                max_size_bytes = stats["max_size_gb"] * 1024 * 1024 * 1024
                print(f"Cache Path:   {stats['path']}")
                print(
                    f"Total Size:   {_format_size(stats['total_size_bytes'])} / "
                    f"{_format_size(max_size_bytes)}"
                )
                print(f"Entries:      {stats['entry_count']}")
                print(f"  Immutable:  {stats['immutable_count']}")
                print(f"  Mutable:    {stats['mutable_count']}")
                print(f"Expired:      {stats['expired_count']}")

                if args.verbose:
                    print(f"\nTTL Hours:    {stats['ttl_hours']}")
                    print(f"Max Size GB:  {stats['max_size_gb']}")
                    print(f"Last Updated: {stats['last_updated']}")

        return EXIT_SUCCESS

    except Exception as e:
        if not args.quiet:
            print(f"Error: Failed to get cache status - {e}", file=sys.stderr)
        log.exception("cache_status_error", error=str(e))
        return EXIT_GENERAL_ERROR


def create_cache_clear_parser() -> argparse.ArgumentParser:
    """Create argument parser for artifact cache clear command.

    Returns:
        Configured ArgumentParser for the cache clear command.

    Example:
        >>> parser = create_cache_clear_parser()
        >>> args = parser.parse_args([])
        >>> args.yes
        False
    """
    parser = argparse.ArgumentParser(
        prog="floe artifact cache clear",
        description="Clear cached OCI artifacts",
        epilog="Clears all cached artifacts or specific tags.",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.yaml"),
        help="Path to manifest.yaml with cache config (default: manifest.yaml)",
        metavar="PATH",
    )

    parser.add_argument(
        "--tag",
        "-t",
        type=str,
        default=None,
        help="Clear only artifacts with this tag (default: clear all)",
        metavar="TAG",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress all output except errors",
    )

    return parser


def run_cache_clear(args: argparse.Namespace) -> int:
    """Run the cache clear command.

    Clears all cached artifacts or only those matching a specific tag.
    Prompts for confirmation unless --yes flag is provided.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).

    Example:
        >>> args = create_cache_clear_parser().parse_args(["--yes"])
        >>> exit_code = run_cache_clear(args)
    """
    from floe_core.oci.cache import CacheManager
    from floe_core.schemas.oci import CacheConfig

    log = logger.bind(command="cache_clear", tag=args.tag)
    log.debug("cache_clear_start")

    try:
        # Load manifest if exists
        cache_config: CacheConfig | None = None
        if args.manifest.exists():
            import yaml

            manifest_data = yaml.safe_load(args.manifest.read_text())
            if manifest_data and "oci" in manifest_data:
                oci_config = manifest_data["oci"]
                if "cache" in oci_config:
                    cache_config = CacheConfig(**oci_config["cache"])

        # Handle case where cache is not configured
        if cache_config is None:
            log.info("cache_not_configured")
            if not args.quiet:
                print("Cache not configured")
            return EXIT_SUCCESS

        # Create cache manager with config
        manager = CacheManager(cache_config)
        stats = manager.stats()

        if args.tag:
            # Clear specific tag
            matching_entries = manager.get_entries_by_tag(args.tag)

            if not matching_entries:
                if not args.quiet:
                    print(f"No cached artifacts found with tag '{args.tag}'")
                return EXIT_SUCCESS

            # Confirm before clearing
            if not args.yes and not args.quiet:
                count = len(matching_entries)
                response = input(
                    f"Clear {count} cached artifact(s) with tag '{args.tag}'? [y/N] "
                )
                if response.lower() not in ("y", "yes"):
                    print("Aborted")
                    return EXIT_SUCCESS

            # Clear matching entries
            cleared = 0
            for entry in matching_entries:
                if manager.remove(entry.digest):
                    cleared += 1

            log.info("cache_cleared_tag", tag=args.tag, cleared=cleared)
            if not args.quiet:
                print(f"Cleared {cleared} cached artifact(s) with tag '{args.tag}'")

        else:
            # Clear all
            entry_count = stats.get("entry_count", 0)

            if entry_count == 0:
                if not args.quiet:
                    print("Cache is empty")
                return EXIT_SUCCESS

            # Confirm before clearing
            if not args.yes and not args.quiet:
                total_size = _format_size(stats.get("total_size_bytes", 0))
                response = input(
                    f"Clear {entry_count} cached artifact(s) ({total_size})? [y/N] "
                )
                if response.lower() not in ("y", "yes"):
                    print("Aborted")
                    return EXIT_SUCCESS

            manager.clear()

            log.info("cache_cleared_all", entry_count=entry_count)
            if not args.quiet:
                print(f"Cleared {entry_count} cached artifact(s)")

        return EXIT_SUCCESS

    except Exception as e:
        if not args.quiet:
            print(f"Error: Failed to clear cache - {e}", file=sys.stderr)
        log.exception("cache_clear_error", error=str(e))
        return EXIT_GENERAL_ERROR


def main(argv: list[str] | None = None) -> NoReturn:
    """Main entry point for floe artifact push command.

    Args:
        argv: Command-line arguments (uses sys.argv if None).

    Raises:
        SystemExit: Always exits with appropriate code.
    """
    parser = create_push_parser()
    args = parser.parse_args(argv)

    exit_code = run_push(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
