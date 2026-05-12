"""Shared pytest configuration for floe-catalog-glue tests."""

from __future__ import annotations

import sys
from pathlib import Path

# TODO: Remove once floe-catalog-glue is registered in the root workspace.
# Package-local pytest already uses pyproject.toml pythonpath=["src"], but
# root-level CI collection needs this explicit source path while registration
# is deferred to the provider integration branch.
PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))
