# Feature Specification: Agent Memory Validation & Quality

**Epic**: 10B (Agent Memory Quality)
**Feature Branch**: `10b-agent-memory-quality`
**Created**: 2026-01-16
**Status**: Draft
**Input**: User description: "Address testing gaps from Epic 10A. Validate API contracts, improve test coverage, establish regression prevention for Cognee Cloud integration."

## Context

This specification addresses critical quality issues discovered during Epic 10A implementation. A bug caused all synced content to be replaced with default values because integration tests validated "does it return results?" rather than "does it return the correct results?".

**Root Cause**: The Cognee Cloud API uses camelCase field names (`textData`, `searchType`, `topK`) but our implementation used snake_case (`data`, `search_type`, `top_k`). Since the expected field names were never sent, the API used default values for every document synced.

**Solution**: Add contract tests that validate exact field names, unit tests that verify payload construction, and integration tests that verify content searchability.

## Clarifications

### Session 2026-01-16

- Q: Should Epic 10B include contract/unit tests for the cogwit_sdk integration (memify), or is SDK testing out of scope? → A: Refactor memify to use REST API (`POST /api/v1/memify`) instead of cogwit_sdk, then include in contract tests. This unifies the integration pattern and removes the cogwit_sdk dependency.
- Q: Should we add read-after-write verification to confirm content was successfully loaded? → A: Add optional `verify=True` flag to `add_content()` for read-after-write verification. Also expose this flag in the CLI sync command (`--verify`).
- Q: Should integration tests verify cognify completion status before searching? → A: Add status polling after `cognify()` - poll `/api/datasets/status` until processing is complete before proceeding to search.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contract Test Protection (Priority: P1)

As a developer contributing to the agent-memory module, I want contract tests that validate API field names against the Cognee Cloud API specification, so that field name mismatches are caught before code is merged.

**Why this priority**: This is the direct fix for the root cause. Contract tests would have caught the "dad jokes" bug immediately - they validate the exact structure of API payloads before any network call is made.

**Independent Test**: Can be fully tested by running contract tests locally without any external services. Delivers value by preventing API contract regressions.

**Acceptance Scenarios**:

1. **Given** a developer modifies the `add_content()` method, **When** they run contract tests, **Then** the tests validate that `textData` (not `data`) is used in the JSON payload
2. **Given** a developer modifies the `search()` method, **When** they run contract tests, **Then** the tests validate that `searchType` and `topK` (camelCase) are used
3. **Given** a developer introduces a new API call, **When** they create a contract test, **Then** the test validates field names against the API specification

---

### User Story 2 - CogneeClient Unit Test Coverage (Priority: P1)

As a developer, I want comprehensive unit tests for the CogneeClient class that verify payload construction and response parsing, so that bugs in API interaction logic are caught without requiring external services.

**Why this priority**: Unit tests run fast and catch issues early. They complement contract tests by validating all code paths including error handling and response parsing variations.

**Independent Test**: Can be fully tested with mocked HTTP responses. Delivers value by ensuring payload construction and response parsing work correctly.

**Acceptance Scenarios**:

1. **Given** a CogneeClient unit test suite exists, **When** all tests pass, **Then** the suite achieves at least 80% code coverage of the CogneeClient class
2. **Given** the `search()` method receives a response, **When** the response is in any of the known formats (list, dict with results, dict with data, nested search_result), **Then** the response is parsed correctly
3. **Given** an API error occurs, **When** the CogneeClient handles it, **Then** appropriate exceptions are raised with clear error messages

---

### User Story 3 - Content Searchability Verification (Priority: P2)

As a developer, I want integration tests that verify synced content actually appears in search results, so that I have confidence the end-to-end flow works correctly.

**Why this priority**: Integration tests validate the complete flow against real services. They're slower but essential for confidence that the system works end-to-end.

**Independent Test**: Requires Cognee Cloud access. Delivers value by validating content is properly indexed and searchable.

**Acceptance Scenarios**:

1. **Given** content has been synced via `add_content()`, **When** the `cognify()` operation completes, **Then** searching for unique terms from that content returns relevant results
2. **Given** a test syncs content with a unique identifier, **When** searching for that identifier, **Then** the search results contain that identifier (not default values)
3. **Given** test datasets are used, **When** tests complete, **Then** test datasets are cleaned up to prevent cross-test pollution

---

### User Story 4 - Fix Verification Protocol (Priority: P2)

As a developer who fixed the API field names, I want a documented verification protocol to confirm the fixes work, so that I can be confident the "dad jokes" contamination is eliminated.

**Why this priority**: Validates that the bug fixes in Epic 10A actually work. Without verification, we can't be sure the problem is solved.

**Independent Test**: Requires Cognee Cloud access and ability to reset data. Delivers value by confirming the fix.

**Acceptance Scenarios**:

1. **Given** the Cognee Cloud data is reset, **When** content is re-synced with the fixed code, **Then** searching for "floe" returns content about the floe platform (not "dad jokes")
2. **Given** the full sync completes, **When** a sample of documents is searched, **Then** all search results contain actual content (no default values)

---

### User Story 5 - API Quirks Documentation (Priority: P3)

As a future developer working on Cognee integration, I want API quirks documented in project documentation, so that I don't repeat the same mistakes.

**Why this priority**: Documentation prevents future developers from falling into the same traps. Lower priority because it doesn't directly fix bugs but prevents future ones.

**Independent Test**: Can be validated by documentation review. Delivers value by knowledge transfer.

**Acceptance Scenarios**:

1. **Given** a new developer reads the project documentation, **When** they look for Cognee API requirements, **Then** they find documentation about camelCase field requirements
2. **Given** the documentation exists, **When** it lists response format variations, **Then** all known response formats are documented with examples

---

### Edge Cases

- What happens when Cognee Cloud API returns an unexpected response format?
- How does the system handle partial sync failures (some documents succeed, others fail)?
- What happens if contract tests pass but the Cognee API spec changes server-side?
- How does the system handle rate limiting or temporary API unavailability during integration tests?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Contract tests MUST validate that `add_content()` sends `textData` field (not `data`)
- **FR-002**: Contract tests MUST validate that `add_content()` sends `datasetName` field (not `dataset_name`)
- **FR-003**: Contract tests MUST validate that `search()` sends `searchType` field (not `search_type`)
- **FR-004**: Contract tests MUST validate that `search()` sends `topK` field (not `top_k`)
- **FR-005**: Contract tests MUST validate that `cognify()` sends `datasets` field in the correct format
- **FR-006**: The `memify()` method MUST remain using cogwit_sdk (no REST endpoint available) with SDK-level error handling
- **FR-007**: Documentation MUST note that memify is SDK-only (not REST API) due to missing Cognee endpoint
- **FR-008**: Unit tests MUST cover the memify() method's SDK integration and error handling paths
- **FR-009**: The `add_content()` method MUST support an optional `verify` parameter for read-after-write verification with a default timeout of 30 seconds
- **FR-010**: When `verify=True`, `add_content()` MUST confirm content exists in dataset before returning success
- **FR-011**: The CLI sync command MUST support a `--verify` flag that enables read-after-write verification
- **FR-012**: The `cognify()` method MUST poll `/api/datasets/status` until processing is complete before returning
- **FR-013**: Status polling MUST have a configurable timeout with default of 300 seconds (5 minutes)
- **FR-014**: Unit tests MUST achieve at least 80% code coverage of the CogneeClient class
- **FR-015**: Unit tests MUST cover all response parsing paths (list, dict with results, dict with data, nested search_result)
- **FR-016**: Integration tests MUST verify content searchability (not just result count)
- **FR-017**: Integration tests MUST use unique datasets per test to prevent cross-test pollution
- **FR-018**: Integration tests MUST clean up test datasets after completion
- **FR-019**: A verification protocol MUST exist to confirm the fix eliminates "default value" contamination
- **FR-020**: Project documentation MUST include a section on Cognee API camelCase requirements
- **FR-021**: Project documentation MUST list all known response format variations

### Key Entities

- **Contract Test**: A test that validates the structure of API payloads against the expected specification, without making actual network calls
- **CogneeClient**: The client class responsible for all Cognee Cloud API interactions via REST API (add_content, search, cognify, delete) and SDK (memify only due to missing REST endpoint)
- **Test Dataset**: An isolated dataset created for a specific test run, with a unique identifier to prevent cross-test pollution

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All contract tests pass on every pull request, catching field name mismatches before merge
- **SC-002**: CogneeClient unit test coverage reaches at least 80%
- **SC-003**: Integration tests verify content appears in search results (not just that results exist)
- **SC-004**: Verification protocol confirms no "dad jokes" or default values appear in search results after re-sync
- **SC-005**: API quirks documentation is findable within project documentation (CLAUDE.md or dedicated section)
- **SC-006**: Future field name bugs are caught in under 5 seconds (contract test execution time)
- **SC-007**: Unit test suite runs in under 30 seconds without external services
- **SC-008**: All CogneeClient methods except memify use REST API consistently; memify documented as SDK-only due to missing Cognee endpoint
- **SC-009**: Load assurance (`--verify` flag) catches content indexing failures before cognify begins
- **SC-010**: Integration tests wait for cognify completion (via status polling) before searching, eliminating timing-related flakiness
