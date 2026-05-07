"""Unit tests for Polaris tracing helpers."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from floe_catalog_polaris.tracing import set_error_attributes


class RecordingSpan:
    """Minimal span stub that records attributes set by tracing helpers."""

    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


def test_set_error_attributes_sanitizes_error_message(monkeypatch) -> None:
    """Error attributes must not record raw credential-bearing messages."""
    telemetry_pkg = ModuleType("floe_core.telemetry")
    sanitization_mod = ModuleType("floe_core.telemetry.sanitization")

    def sanitize_error_message(message: str) -> str:
        return message.replace("password=super-secret", "password=<REDACTED>")

    sanitization_mod.sanitize_error_message = sanitize_error_message
    monkeypatch.setitem(sys.modules, "floe_core.telemetry", telemetry_pkg)
    monkeypatch.setitem(sys.modules, "floe_core.telemetry.sanitization", sanitization_mod)

    span = RecordingSpan()
    set_error_attributes(span, RuntimeError("connect failed password=super-secret"))

    assert span.attributes["error.type"] == "RuntimeError"
    assert span.attributes["error.message"] == "connect failed password=<REDACTED>"
    assert "super-secret" not in span.attributes["error.message"]
