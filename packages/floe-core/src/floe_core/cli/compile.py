"""CLI command for compiling FloeSpec + Manifest into CompiledArtifacts.

This module implements the `floe compile` command which executes the
6-stage compilation pipeline.

Example:
    $ floe compile --spec floe.yaml --manifest manifest.yaml --output target/
    Compilation successful: target/compiled_artifacts.json

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - CompilationStage: Pipeline stages
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from typing import NoReturn

logger = structlog.get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for compile command.

    Returns:
        Configured ArgumentParser for the compile command.

    Example:
        >>> parser = create_parser()
        >>> args = parser.parse_args(["--spec", "floe.yaml", "--manifest", "manifest.yaml"])
        >>> args.spec
        Path('floe.yaml')
    """
    parser = argparse.ArgumentParser(
        prog="floe compile",
        description="Compile FloeSpec + Manifest into CompiledArtifacts",
        epilog="Exit codes: 0=success, 1=validation error, 2=compilation error",
    )

    parser.add_argument(
        "--spec",
        type=Path,
        required=True,
        help="Path to floe.yaml (FloeSpec)",
        metavar="PATH",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to manifest.yaml (PlatformManifest)",
        metavar="PATH",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("target"),
        help="Output directory for compiled_artifacts.json (default: target/)",
        metavar="PATH",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and compile without writing files",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run LOAD and VALIDATE stages only",
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


def run_compile(args: argparse.Namespace) -> int:
    """Execute the compile command.

    Runs the 6-stage compilation pipeline and writes output.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code: 0=success, 1=validation error, 2=compilation error.

    Example:
        >>> args = create_parser().parse_args(["--spec", "floe.yaml", "--manifest", "manifest.yaml"])
        >>> exit_code = run_compile(args)
        >>> exit_code
        0
    """
    # Late import to avoid circular dependencies
    from floe_core.compilation.errors import CompilationException
    from floe_core.compilation.stages import CompilationStage, compile_pipeline

    log = logger.bind(
        spec_path=str(args.spec),
        manifest_path=str(args.manifest),
        output_path=str(args.output),
    )

    if not args.quiet:
        log.info("compilation_start")

    try:
        # Execute pipeline
        artifacts = compile_pipeline(args.spec, args.manifest)

        # Validate-only mode stops here
        if args.validate_only:
            if not args.quiet:
                log.info(
                    "validation_complete",
                    product_name=artifacts.metadata.product_name,
                )
                _print_success("Validation successful", args.quiet)
            return 0

        # Dry-run mode doesn't write files
        if args.dry_run:
            if not args.quiet:
                log.info(
                    "dry_run_complete",
                    product_name=artifacts.metadata.product_name,
                    version=artifacts.version,
                )
                _print_success(
                    f"Dry run successful: {artifacts.metadata.product_name}",
                    args.quiet,
                )
            return 0

        # Write output
        output_path = _write_artifacts(artifacts, args.output, args.quiet)

        if not args.quiet:
            log.info(
                "compilation_complete",
                output_path=str(output_path),
                product_name=artifacts.metadata.product_name,
                version=artifacts.version,
            )
            _print_success(f"Compilation successful: {output_path}", args.quiet)

        return 0

    except CompilationException as e:
        error = e.error
        log.error(
            "compilation_failed",
            stage=error.stage.value,
            code=error.code,
            message=error.message,
        )

        # Print user-friendly error message
        _print_error(error, args.quiet)

        # Return exit code based on stage
        return error.stage.exit_code


def _write_artifacts(
    artifacts: "CompiledArtifacts",
    output_dir: Path,
    quiet: bool,
) -> Path:
    """Write CompiledArtifacts to output directory.

    Args:
        artifacts: Compiled artifacts to write.
        output_dir: Directory to write to.
        quiet: Whether to suppress output.

    Returns:
        Path to written file.
    """
    # Late import to avoid circular dependencies
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts  # noqa: F401

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write to file
    output_path = output_dir / "compiled_artifacts.json"
    output_path.write_text(
        json.dumps(artifacts.model_dump(mode="json", by_alias=True), indent=2)
    )

    return output_path


def _print_success(message: str, quiet: bool) -> None:
    """Print success message to stdout.

    Args:
        message: Message to print.
        quiet: Whether to suppress output.
    """
    if not quiet:
        print(message)


def _print_error(error: "CompilationError", quiet: bool) -> None:
    """Print error message to stderr.

    Formats the error with stage, code, message, and suggestion.

    Args:
        error: CompilationError to print.
        quiet: Whether to suppress verbose output.
    """
    # Late import
    from floe_core.compilation.errors import CompilationError  # noqa: F401

    # Always print errors (even in quiet mode)
    print(f"\nError [{error.stage.value}] {error.code}: {error.message}", file=sys.stderr)

    if error.suggestion and not quiet:
        print(f"\nSuggestion: {error.suggestion}", file=sys.stderr)

    if error.context and not quiet:
        context_str = ", ".join(f"{k}={v}" for k, v in error.context.items())
        print(f"Context: {context_str}", file=sys.stderr)


def main(argv: list[str] | None = None) -> NoReturn:
    """Main entry point for floe compile command.

    Args:
        argv: Command-line arguments (uses sys.argv if None).

    Raises:
        SystemExit: Always exits with appropriate code.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    exit_code = run_compile(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
