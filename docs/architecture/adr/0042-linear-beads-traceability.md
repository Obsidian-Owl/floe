# ADR-0042: Linear + Beads for Requirements Traceability

## Decision

Replace custom traceability module with Linear (source of truth) + Beads (local cache, git-backed).

## Rationale

- Beads has native Linear integration (`bd linear sync`)
- Linear provides globally unique IDs (FLO-123 format)
- Bidirectional sync keeps Beads and Linear in sync
- Linear MCP integration enables Claude Code to create/update issues directly
- Eliminates 4,662 lines of custom traceability code (37% adoption)

## Implementation

- Configure `bd linear` with team ID, API key, mappings
- Use Linear custom field "Replaces" to track old req → new issue migration
- SpecKit integrates via Linear MCP server (Claude Code)
- Git commits reference Linear IDs: `git commit -m "epic-03: ... [FLO-301]"`

## Status

Accepted - Implemented in Epic 1
