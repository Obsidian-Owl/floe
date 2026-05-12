"""Shared pytest configuration for floe-storage-aws-s3 tests."""

from __future__ import annotations

import sys
from pathlib import Path

# The package is intentionally not registered in the root workspace until the
# provider integration branch. Package-local pytest already uses pythonpath,
# but root-level CI collection needs this explicit source path.
PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))
