# Research: Agent Memory (Cognee Integration)

**Feature**: Epic 10A - Agent Memory (Cognee Integration)
**Date**: 2026-01-14
**Status**: Complete

---

## Executive Summary

Cognee is a graph-augmented RAG (Retrieval-Augmented Generation) platform that transforms raw data into persistent, searchable knowledge structures. Unlike basic RAG that uses flat vector chunks, Cognee combines **vector similarity search** with **graph-based relationship reasoning**, enabling richer context retrieval for AI agents.

**Key Decision**: Use **Cognee Cloud (SaaS)** for shared team knowledge graphs with no infrastructure management.

---

## Research Questions Resolved

### Q1: What is Cognee and how does it differ from basic RAG?

**Decision**: Cognee's graph-augmented approach is ideal for maintaining architectural context across AI agent sessions.

| Aspect | Basic RAG | Cognee |
|--------|-----------|--------|
| Data Structure | Flat vector chunks | Connected knowledge graph + vectors |
| Relationships | Not captured | Explicitly modeled as graph edges |
| Memory | Session-based | Persistent across interactions |
| Retrieval | Vector similarity only | Vector + graph traversal + LLM reasoning |
| Customization | Limited | User-defined ontologies, custom pipelines |

**Rationale**: Architecture documentation benefits significantly from relationship modeling (ADRs relate to principles, principles relate to code patterns). Graph-based retrieval surfaces these connections.

**Alternatives Considered**:
- **Plain vector store (Qdrant/Pinecone)**: Simpler but loses relationship context
- **Custom Neo4j + embeddings**: More control but significant implementation burden
- **LlamaIndex/LangChain**: Framework-level, not persistent memory

---

### Q2: What are Cognee's core operations?

**Decision**: Use Cognee's built-in ECL (Extract, Cognify, Load) pipeline via the Python SDK.

**Core Operations**:

| Operation | Purpose | Our Use Case |
|-----------|---------|--------------|
| `cognee.add()` | Ingest data (files, URLs, text) | Add ADRs, architecture docs, docstrings |
| `cognee.cognify()` | Generate knowledge graphs with LLM | Process indexed content into graph |
| `cognee.codify()` | Code-specific knowledge graphs | Process Python source with docstrings |
| `cognee.search()` | Query with multiple strategies | AI agent memory retrieval |
| `cognee.prune.*` | System/data cleanup | Operational management |

**Search Types** (8 modes):

| Type | Use Case | Speed |
|------|----------|-------|
| `GRAPH_COMPLETION` | Complex architectural questions | Slowest (default) |
| `RAG_COMPLETION` | Quick fact retrieval | Medium |
| `CHUNKS` | Raw passage matching | Fastest |
| `CODE` | Function/class lookup | Medium |
| `SUMMARIES` | Document overviews | Fast |

**Rationale**: `GRAPH_COMPLETION` is ideal for "why" questions about architecture; `CODE` is ideal for docstring queries.

---

### Q3: What is Cognee Cloud vs self-hosted?

**Decision**: Use **Cognee Cloud** (SaaS) for team-shared knowledge.

| Aspect | Cognee Cloud | Self-Hosted |
|--------|-------------|-------------|
| Infrastructure | Fully managed | User manages (EC2, K8s, Modal) |
| Team Features | Built-in multi-tenancy, RBAC | Must configure |
| Updates | Automatic | Manual |
| Cost | $25/month (1GB + 10K API calls) | Infrastructure + maintenance |
| Data Export | Available via API | Full control |

**Rationale**:
- Shared team knowledge graph requires centralized backend
- No infrastructure burden for dev-only tooling
- Cloud provides RBAC for future team scaling

**Alternatives Considered**:
- **Self-hosted K8s**: Higher maintenance, not justified for dev tooling
- **Modal serverless**: Good but still requires management
- **Local per-developer**: Loses team knowledge sharing benefit

---

### Q4: How does MCP integration work?

**Decision**: Configure Cognee MCP server in Claude Code for native tool access.

**MCP Tools Available** (11):

| Tool | Category | Description |
|------|----------|-------------|
| `cognify` | Memory | Transform data into knowledge graphs |
| `search` | Memory | Semantic search with multiple strategies |
| `codify` | Code Intel | Code-specific knowledge graphs |
| `prune` | Memory | Clear all memory |
| `list_data` | Data Mgmt | List datasets and items |
| `delete` | Data Mgmt | Remove specific data items |
| `cognify_status` | Data Mgmt | Track pipeline status |
| `save_interaction` | Code Intel | Store Q&A exchanges |
| `get_developer_rules` | Code Intel | Retrieve stored patterns |
| `cognee_add_developer_rules` | Memory | Ingest developer rules |

**Configuration for Claude Code**:

```json
{
  "mcpServers": {
    "cognee": {
      "transport": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Architecture Mode**: **API Mode** - MCP server connects to centralized Cognee Cloud backend for team-shared knowledge.

**Rationale**: Native MCP integration means no custom wrapper needed; Claude Code can directly query the knowledge graph.

---

### Q5: What operational APIs does Cognee provide?

**Decision**: Wrap Cognee's built-in APIs for health, prune, and status; build coverage/drift detection on top.

**Built-in APIs We Wrap**:

| Capability | Cognee API | Our Wrapper |
|------------|-----------|-------------|
| Health check | `GET /health/detailed` | `make cognee-health` |
| Full reset | `prune_system(graph, vector, metadata, cache)` | `make cognee-reset` |
| Pipeline status | `cognify_status`, `codify_status` | Status tracking |
| List datasets | `datasets.list_datasets()` | Coverage analysis input |
| Delete data | `delete(data_id, dataset_id, mode)` | Selective repair |

**APIs We Build** (not in Cognee):

| Capability | Why Cognee Can't | Our Implementation |
|------------|------------------|-------------------|
| Coverage analysis | No filesystem awareness | Compare `list_data` to glob results |
| Drift detection | No rename/delete tracking | Hash-based content tracking via `.cognee/checksums.json` |
| Batch initial load | Per-dataset only | Iterator with progress + checkpoints |
| Quality validation | No test suite concept | Known queries → expected results |
| Selective repair | Prune is all-or-nothing | Delete stale + add missing only |

**Health Response Structure**:
```python
{
    "status": "healthy|degraded|unhealthy",
    "timestamp": "ISO-8601",
    "version": "0.5.x",
    "uptime": 12345,
    "components": {
        "relational_db": {"status": "healthy", "provider": "sqlite", "response_time_ms": 5},
        "vector_db": {"status": "healthy", "provider": "lancedb", "response_time_ms": 10},
        "graph_db": {"status": "healthy", "provider": "kuzu", "response_time_ms": 8},
        "llm_provider": {"status": "healthy", "provider": "openai", "response_time_ms": 150}
    }
}
```

**Rationale**: Cognee provides strong foundation; we add filesystem-aware operations that require local context.

---

### Q6: What are the authentication requirements?

**Decision**: Use environment variables for API keys; Cognee Cloud handles team auth via OAuth2/PKCE.

**Credentials Required**:

| Credential | Purpose | Storage |
|------------|---------|---------|
| `LLM_API_KEY` | OpenAI for cognify entity extraction | Environment variable |
| Cognee Cloud API key | Team workspace access | Environment variable |
| GitHub secret | CI/CD access | GitHub Secrets |

**Auth Flow for Team**:
1. Cognee Cloud account created with team workspace
2. API credentials stored in `.cognee/config.yaml` (gitignored)
3. Environment variables reference config or GitHub secrets
4. MCP server authenticates to Cloud in API mode

**Rationale**: Standard secret management pattern; no hardcoded credentials.

---

### Q7: What Python SDK patterns should we use?

**Decision**: Async/await pattern with error handling for all Cognee operations.

**SDK Installation**:
```bash
pip install cognee  # Basic
pip install "cognee[postgres]"  # With PGVector
pip install "cognee[neo4j]"  # With Neo4j
```

**Pattern for Operations**:
```python
import asyncio
import cognee
from cognee import SearchType

async def index_architecture_docs():
    """Index architecture documentation."""
    # Add documentation
    await cognee.add(
        "/path/to/docs/architecture/",
        dataset_name="architecture"
    )

    # Process into knowledge graph
    await cognee.cognify(datasets=["architecture"])

    # Verify with search
    results = await cognee.search(
        query_text="What is the plugin system?",
        query_type=SearchType.GRAPH_COMPLETION,
        datasets=["architecture"]
    )
    return results

asyncio.run(index_architecture_docs())
```

**Error Handling**:
```python
try:
    await cognee.cognify(datasets=["docs"])
except Exception as e:
    logger.error("Cognify failed", error=str(e))
    # Retry or fail gracefully
```

---

### Q8: What storage backends does Cognee support?

**Decision**: Use **Cognee Cloud defaults** (managed storage); no self-managed backends.

**Available Options** (for reference):

| Category | Default | Production Options |
|----------|---------|-------------------|
| Vector Store | LanceDB (file-based) | Qdrant, PGVector, ChromaDB |
| Graph Store | Kuzu (file-based) | Neo4j, Neptune |
| LLM Provider | OpenAI | Anthropic, Ollama, Gemini |
| Embedding | OpenAI | Mistral, Fastembed |

**Rationale**: Cognee Cloud manages storage; we don't need to configure backends for SaaS usage.

---

### Q9: What are rate limits and costs?

**Decision**: Acceptable for dev tooling use case.

| Plan | Cost | Limits |
|------|------|--------|
| Cognee Cloud | $25/month | 1 GB ingestion + 10,000 API calls |

**Mitigation**:
- Batch processing during initial load
- Selective cognify (only changed files)
- Local caching for repeated queries

**Rationale**: Dev tooling doesn't hit production-scale limits; $25/month is reasonable.

---

### Q10: What content should we index?

**Decision**: Index in priority order to match Epic requirements.

| Content Type | Source | Priority | Dataset Name |
|--------------|--------|----------|--------------|
| ADRs | `docs/architecture/adr/*.md` | P0 | `architecture` |
| Architecture docs | `docs/architecture/**/*.md` | P0 | `architecture` |
| Constitution | `.specify/memory/constitution.md` | P0 | `governance` |
| Claude rules | `.claude/rules/*.md` | P1 | `governance` |
| Claude skills | `.claude/skills/*/SKILL.md` | P1 | `skills` |
| Python docstrings | `packages/*/src/**/*.py` | P1 | `codebase` |
| Plugin docstrings | `plugins/*/src/**/*.py` | P1 | `codebase` |

**Total Estimated Content**:
- 45+ ADRs
- 22,700+ lines of architecture docs
- 13 skills
- ~50 Python modules with docstrings

---

## Technology Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Platform | Cognee Cloud (SaaS) | Shared team knowledge, no infrastructure |
| MCP Mode | API Mode | Team collaboration via centralized backend |
| Search Type | GRAPH_COMPLETION (default) | Best for architectural "why" questions |
| Python Version | 3.10+ | Cognee requirement |
| Async Pattern | async/await | Cognee SDK is async-native |
| Secret Storage | Environment variables | Standard, no hardcoded secrets |
| Content Hashing | SHA-256 | Drift detection |
| Checkpoint Format | JSON | Resume batch operations |

---

## Implementation Implications

### What We Build (Thin Wrappers)

1. **CLI Commands**: `make cognee-*` targets wrapping SDK
2. **Coverage Analysis**: Compare `list_data()` to filesystem glob
3. **Drift Detection**: Track file hashes in `.cognee/checksums.json`
4. **Batch Load**: Iterator with progress and checkpoints
5. **Quality Tests**: Known query → expected result assertions

### What We DON'T Build (Use Cognee Directly)

1. Knowledge graph processing (cognify)
2. Search strategies (GRAPH_COMPLETION, etc.)
3. Entity extraction (LLM-powered)
4. Storage management (Cloud handles)
5. MCP server (use official `cognee-mcp`)

---

## References

- Cognee GitHub: https://github.com/topoteretes/cognee
- Cognee Documentation: https://docs.cognee.ai
- Cognee MCP Tools: https://docs.cognee.ai/cognee-mcp/mcp-tools
- Cognee HTTP API: https://docs.cognee.ai/http_api
- MCP Protocol: https://modelcontextprotocol.io/
