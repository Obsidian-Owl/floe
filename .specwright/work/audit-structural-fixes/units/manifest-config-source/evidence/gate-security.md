# Gate: Security
**Status**: PASS
**Ran**: 2026-04-04T21:03:00Z

## Bandit Results
- 10 Low severity findings — all pre-existing in conftest.py
- B404/B603/B607: subprocess with list args (correct, no shell=True)
- B105: `demo-secret` in fallback dict — intentional fallback default, used only
  when manifest is missing. Production credentials come from K8s secrets.
- No new security issues introduced by this work unit
- extract-manifest-config.py: clean (0 findings)
- Shell injection prevention: single-quoted output with ANSI-C escaping for embedded quotes
