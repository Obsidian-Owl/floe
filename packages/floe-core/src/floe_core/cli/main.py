"""Main entry point for the floe CLI.

This module provides the main entry point that dispatches to subcommands.

Commands:
    floe compile: Compile FloeSpec + Manifest into CompiledArtifacts

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
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
