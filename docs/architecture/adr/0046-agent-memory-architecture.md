# ADR-0046: Agent Memory Architecture (Cognee Integration)

## Status

Proposed - Epic 10A

## Context

AI coding agents (Claude Code, Cursor, etc.) contributing to the floe codebase lose context during compaction cycles. This creates several problems:

- **Decision amnesia**: Reasoning behind "why not Alternative B" is lost
- **Session recovery overhead**: 5-10 minutes of manual context reconstruction
- **Capability blindness**: Agents don't know "have we solved this before?"
- **Isolated sessions**: Cross-session learning doesn't persist

**Target Persona**: AI coding agents and human maintainers contributing TO the floe codebase.

**Not For**: End users of floe (Platform Engineers, Data Engineers).

## Decision

Integrate **Cognee Cloud** as persistent, graph-augmented memory for AI coding agents contributing to the floe codebase.

### Why Cognee?

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Vector-only RAG | Simple, fast | No relationships, flat | Rejected |
| Neo4j + embeddings | Powerful graphs | Self-hosted, complex | Rejected |
| Cognee | Graph + vectors, MCP support, SaaS | Cloud dependency | **Selected** |
| LangGraph/LangMem | Good tooling | Less graph-native | Rejected |

### Key Decisions

1. **Cognee Cloud (SaaS)** over self-hosted: Shared team knowledge, no infrastructure burden
2. **Graph-augmented RAG** over vector-only: Relationships between decisions matter
3. **MCP integration** over custom CLI: Native Claude Code support
4. **Async git hooks** over sync: Non-blocking, don't slow commits

## Implementation

### Package Location

```text
devtools/                              # INTERNAL ONLY - never distributed
└── agent-memory/                      # Cognee integration
    ├── pyproject.toml                 # "Private :: Do Not Upload" classifier
    └── src/agent_memory/              # Package code
```

**Why `devtools/`?**
- Signals "not for distribution" (vs `packages/` which are published)
- Common pattern for internal tooling
- Installed via `[project.optional-dependencies].dev` only
- CI excludes from production artifacts

### Integration Points

```text
┌─────────────────┐       ┌─────────────────┐
│  Claude Code    │──MCP──│  Cognee Cloud   │
│  (AI Agent)     │       │  (Knowledge     │
└────────┬────────┘       │   Graph)        │
         │                └────────┬────────┘
         │                         │
    ┌────▼────┐               ┌────▼────┐
    │ .claude/│               │ docs/   │
    │ mcp.json│               │ ADRs    │
    └─────────┘               │ Rules   │
                              └─────────┘
```

### Cognification Pipeline

1. **Architecture docs**: All ADRs, constitution, rules indexed with relationships
2. **Docstrings**: Python docstrings extracted, linked to architecture concepts
3. **Decisions**: Git commit messages with decision context preserved
4. **Sessions**: Session state persisted for recovery after compaction

### MCP Tools

Cognee MCP server exposes three tools to Claude Code:

- `cognify`: Add content to knowledge graph
- `search`: Query knowledge graph
- `codify`: Generate code from knowledge

## Consequences

### Positive

- Cross-session context preservation (no more "what were we doing?")
- Decision traceability ("why did we choose Dagster over Airflow?")
- Capability discovery ("have we implemented something like this?")
- Shared team knowledge (all contributors access same graph)

### Negative

- Cloud dependency (Cognee Cloud availability)
- API costs (batch processing mitigates)
- Sync latency (async hooks, eventual consistency)

### Mitigations

| Risk | Mitigation |
|------|------------|
| Cloud dependency | Cognee has SLA, data export available |
| API costs | Batch processing, selective cognify |
| Hook performance | Async execution, don't block commits |
| Knowledge noise | Careful ontology design, validation |

## Security

- Cognee API key stored in GitHub secrets + `.cognee/config.yaml` (gitignored)
- No secrets committed to knowledge graph
- Data classification: Internal development context only

## References

- [Cognee GitHub](https://github.com/topoteretes/cognee)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [ADR-0042: Linear + Beads Traceability](0042-linear-beads-traceability.md) (superseded — beads removed)
- [Epic 10A: Agent Memory](../../plans/epics/10-contributor/epic-10a-agent-memory.md)
