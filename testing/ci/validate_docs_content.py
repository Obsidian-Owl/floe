"""Importable wrapper for validate-docs-content.py."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import cast

_SCRIPT = Path(__file__).with_name("validate-docs-content.py")
_SPEC = importlib.util.spec_from_file_location("_validate_docs_content_script", _SCRIPT)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load {_SCRIPT}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

validate_docs_content = cast(Callable[..., list[str]], _MODULE.validate_docs_content)
