# Plan: Commit dbt Manifests for Docker Build

## Tasks

### Task 1: Add .gitignore exception
- File: `.gitignore`
- After the existing `target/` line, add:
  ```
  !demo/*/target/manifest.json
  ```
- Add comment explaining why (same pattern as definitions.py)

### Task 2: Stage and commit existing manifests
- Run: `git add demo/*/target/manifest.json`
- Verify all 3 files are staged
- Verify each is valid JSON with `"nodes"` key

### Task 3: Add CI staleness gate
- File: `Makefile` — add `check-manifests` target:
  ```makefile
  check-manifests: compile-demo
  	git diff --exit-code demo/*/target/manifest.json || \
  	  (echo "ERROR: Committed manifests are stale. Run 'make compile-demo' and commit." && exit 1)
  ```
- Wire into existing `check` target if appropriate

## File Change Map
| File | Change |
|------|--------|
| `.gitignore` | Add exception line |
| `demo/*/target/manifest.json` | Stage existing files (no content change) |
| `Makefile` | Add `check-manifests` target |

## Dependencies
- None (independent unit)
