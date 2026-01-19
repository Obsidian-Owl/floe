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
