"""Main entry point for the floe CLI.

This module provides the main entry point that dispatches to subcommands.

Commands:
    floe compile: Compile FloeSpec + Manifest into CompiledArtifacts
    floe artifact: Manage OCI registry artifacts (push, pull, inspect, list)

Example:
    $ floe compile --spec floe.yaml --manifest manifest.yaml
    Compilation successful: target/compiled_artifacts.json

See Also:
    - cli/compile.py: Compile command implementation
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import NoReturn


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subcommands.

    Returns:
        Configured ArgumentParser with subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="floe",
        description="floe - Data platform configuration compiler",
        epilog="Use 'floe <command> --help' for command-specific help",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.2.0",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
    )

    # Add compile subcommand
    _add_compile_subparser(subparsers)

    # Add artifact subcommand group
    _add_artifact_subparser(subparsers)

    return parser


def _add_compile_subparser(
    subparsers: Any,
) -> None:
    """Add the compile subcommand to subparsers.

    Args:
        subparsers: Subparsers action to add to.
    """
    from floe_core.cli.compile import create_parser as create_compile_parser

    # Get the compile parser and copy its arguments
    compile_template = create_compile_parser()

    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile FloeSpec + Manifest into CompiledArtifacts",
        description=compile_template.description,
        epilog=compile_template.epilog,
    )

    # Copy arguments from template
    for action in compile_template._actions:
        if isinstance(action, argparse._HelpAction):
            continue  # Skip help, it's added automatically
        if action.dest == "help":
            continue

        # Recreate the argument
        kwargs: dict[str, Any] = {
            "dest": action.dest,
            "help": action.help,
        }

        if action.option_strings:
            if isinstance(action, argparse._StoreTrueAction):
                kwargs["action"] = "store_true"
            elif isinstance(action, argparse._StoreFalseAction):
                kwargs["action"] = "store_false"
            else:
                if action.type is not None:
                    kwargs["type"] = action.type
                if action.default is not None:
                    kwargs["default"] = action.default
                if action.required:
                    kwargs["required"] = action.required
                if action.metavar:
                    kwargs["metavar"] = action.metavar

            compile_parser.add_argument(*action.option_strings, **kwargs)


def _add_artifact_subparser(
    subparsers: Any,
) -> None:
    """Add the artifact subcommand group to subparsers.

    Args:
        subparsers: Subparsers action to add to.
    """
    # Create artifact parser with nested subcommands
    artifact_parser = subparsers.add_parser(
        "artifact",
        help="Manage OCI artifacts (push, pull, inspect, list)",
        description="Commands for managing floe CompiledArtifacts in OCI registries",
    )

    artifact_subparsers = artifact_parser.add_subparsers(
        title="artifact commands",
        dest="artifact_command",
        required=True,
    )

    # Add push subcommand
    _add_artifact_push_subparser(artifact_subparsers)


def _add_artifact_push_subparser(
    subparsers: Any,
) -> None:
    """Add the artifact push subcommand.

    Args:
        subparsers: Subparsers action to add to.
    """
    from floe_core.cli.artifact import create_push_parser

    # Get the push parser template
    push_template = create_push_parser()

    push_parser = subparsers.add_parser(
        "push",
        help="Push CompiledArtifacts to OCI registry",
        description=push_template.description,
        epilog=push_template.epilog,
    )

    # Copy arguments from template
    for action in push_template._actions:
        if isinstance(action, argparse._HelpAction):
            continue  # Skip help, it's added automatically
        if action.dest == "help":
            continue

        kwargs: dict[str, Any] = {
            "dest": action.dest,
            "help": action.help,
        }

        if action.option_strings:
            if isinstance(action, argparse._StoreTrueAction):
                kwargs["action"] = "store_true"
            elif isinstance(action, argparse._StoreFalseAction):
                kwargs["action"] = "store_false"
            else:
                if action.type is not None:
                    kwargs["type"] = action.type
                if action.default is not None:
                    kwargs["default"] = action.default
                if action.required:
                    kwargs["required"] = action.required
                if action.metavar:
                    kwargs["metavar"] = action.metavar

            push_parser.add_argument(*action.option_strings, **kwargs)


def main(argv: list[str] | None = None) -> NoReturn:
    """Main entry point for the floe CLI.

    Args:
        argv: Command-line arguments (uses sys.argv if None).

    Raises:
        SystemExit: Always exits with appropriate code.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "compile":
        from floe_core.cli.compile import run_compile

        exit_code = run_compile(args)
        sys.exit(exit_code)
    elif args.command == "artifact":
        if args.artifact_command == "push":
            from floe_core.cli.artifact import run_push

            exit_code = run_push(args)
            sys.exit(exit_code)
        else:
            parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
