#!/usr/bin/env python3
"""Compatibility wrapper for the importable Customer 360 validator module."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testing.ci.validate_customer_360_demo import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
