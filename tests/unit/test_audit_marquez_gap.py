"""Unit test: AUDIT.md documents the Marquez root-user gap (AC-10).

AC-10 requires `AUDIT.md` to carry an entry documenting:
  - the finding (Marquez runs as root / UID 0)
  - the upstream reference (GitHub issue #3060)
  - the risk (PSS restricted profile cannot be enforced namespace-wide)
  - the mitigation (accepted for now, future separate namespace)

This test parses AUDIT.md as plain text and asserts each required element
is present. It fails if a future edit removes the Marquez gap section.
"""

from __future__ import annotations

from pathlib import Path

import pytest

AUDIT_FILE = Path(__file__).resolve().parents[2] / ".specwright" / "AUDIT.md"


@pytest.mark.requirement("security-hardening-AC-10")
def test_audit_md_documents_marquez_root_user_gap() -> None:
    """AUDIT.md MUST contain the Marquez gap entry with all required elements."""
    assert AUDIT_FILE.exists(), f"AUDIT.md missing at {AUDIT_FILE}"
    text = AUDIT_FILE.read_text(encoding="utf-8")

    # Required elements per AC-10
    required_markers: list[tuple[str, str]] = [
        ("Marquez", "mention of Marquez by name"),
        ("root", "mention of root user"),
        ("UID 0", "explicit UID 0 reference"),
        ("3060", "upstream GitHub issue #3060"),
        ("PSS", "PSS restricted profile risk"),
        ("Mitigation", "mitigation statement"),
    ]

    missing = [(marker, desc) for marker, desc in required_markers if marker not in text]
    assert not missing, (
        "AC-10 violation: AUDIT.md Marquez gap entry is missing required "
        "elements:\n" + "\n".join(f"  - '{m}' ({d})" for m, d in missing)
    )


@pytest.mark.requirement("security-hardening-AC-10")
def test_audit_md_marquez_entry_has_stable_id() -> None:
    """The Marquez gap must have a stable ID so future tooling can reference it."""
    text = AUDIT_FILE.read_text(encoding="utf-8")
    # Any SEC-### style ID is acceptable; SEC-001 is the first slot.
    assert "SEC-001" in text, (
        "AC-10 violation: AUDIT.md Marquez gap must carry a stable ID "
        "(e.g., SEC-001) for future cross-references"
    )
