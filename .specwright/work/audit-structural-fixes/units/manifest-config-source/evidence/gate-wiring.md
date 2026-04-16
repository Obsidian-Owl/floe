# Gate: Wiring
**Status**: PASS
**Ran**: 2026-04-04T21:04:00Z

## Structural Connections Verified
1. extract-manifest-config.py reads YAML (yaml.safe_load) ✓
2. test-e2e.sh references extract-manifest-config.py (eval call) ✓
3. test-e2e.sh uses MANIFEST_ environment variables (4 references) ✓
4. conftest.py defines and calls _read_manifest_config (2 references) ✓
5. conftest.py references manifest.yaml (5 references) ✓
6. All 3 test files exist ✓

## Data Flow
demo/manifest.yaml → extract-manifest-config.py → shell exports → test-e2e.sh defaults
demo/manifest.yaml → _read_manifest_config() → _manifest_cfg → conftest.py fixtures
