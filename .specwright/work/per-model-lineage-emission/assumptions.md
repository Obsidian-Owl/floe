# Assumptions: Per-Model Lineage Emission

| ID | Assumption | Type | Status | Resolution |
|----|-----------|------|--------|------------|
| A1 | `model.floe.{name}` format matches test's `"model."` check | reference | VERIFIED | Test line 975: `"model." in name.lower()` — confirmed match |
| A2 | Immediate START→COMPLETE (no real duration) is acceptable for compilation-time events | clarify | ACCEPTED | Compilation resolves models, doesn't execute them — no meaningful duration to capture |
| A3 | Non-blocking error handling per model (one failure doesn't block others) | clarify | ACCEPTED | Consistent with existing pipeline-level emission pattern (lines 342-344) |
