# Agent Memory (Cognee Integration)

**INTERNAL TOOLING ONLY** - For floe contributors.

This package provides persistent, graph-augmented memory for AI coding agents contributing to the floe codebase using Cognee Cloud.

## Audience

This tool is exclusively for:
- AI coding agents (Claude Code, Cursor) contributing to floe
- floe project maintainers managing the knowledge graph

**Not intended for**: End users of the floe platform.

## Quick Start

See [quickstart.md](../../specs/10a-agent-memory/quickstart.md) for detailed setup instructions.

```bash
# Install (dev mode)
cd devtools/agent-memory
pip install -e .

# Check health
agent-memory health

# Search indexed content
agent-memory search "plugin system"
```

## Commands

| Command | Description |
|---------|-------------|
| `agent-memory init` | Initialize Cognee Cloud configuration |
| `agent-memory health` | Check Cognee Cloud connectivity |
| `agent-memory sync` | Sync content to Cognee Cloud |
| `agent-memory search QUERY` | Search indexed content |
| `agent-memory coverage` | Analyze indexing coverage |
| `agent-memory drift` | Detect stale entries |
| `agent-memory repair` | Repair drifted entries |
| `agent-memory reset` | Full reset (requires confirmation) |
| `agent-memory test` | Run quality validation |

## Documentation

- [Feature Specification](../../specs/10a-agent-memory/spec.md)
- [Implementation Plan](../../specs/10a-agent-memory/plan.md)
- [Data Model](../../specs/10a-agent-memory/data-model.md)
- [Quickstart Guide](../../specs/10a-agent-memory/quickstart.md)
