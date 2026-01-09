"""Pytest configuration for testing module tests.

This conftest.py configures pytest for testing the testing infrastructure itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add testing module to path for imports
testing_root = Path(__file__).parent.parent.parent
if str(testing_root) not in sys.path:
    sys.path.insert(0, str(testing_root))
