# Quickstart: Agent Memory (Cognee Integration)

**Time to complete**: ~15 minutes
**Prerequisites**: Cognee Cloud account, OpenAI API key

---

## Overview

Agent Memory provides persistent, graph-augmented memory for AI coding agents (Claude Code, Cursor) working on the floe codebase. This guide walks through initial setup and basic operations.

---

## 1. Prerequisites

### Required Accounts

1. **Cognee Cloud** - Sign up at https://cognee.ai
   - Create team workspace for floe contributors
   - Generate API key from account settings

2. **OpenAI** - API key for LLM-powered entity extraction
   - Used during `cognify` to extract entities and relationships

### Environment Setup

```bash
# Required environment variables
export COGNEE_API_KEY="your-cognee-cloud-api-key"
export OPENAI_API_KEY="your-openai-api-key"

# Optional: Add to your shell profile (.zshrc, .bashrc)
echo 'export COGNEE_API_KEY="your-cognee-cloud-api-key"' >> ~/.zshrc
echo 'export OPENAI_API_KEY="your-openai-api-key"' >> ~/.zshrc
```

---

## 2. Installation

```bash
# Install agent-memory as dev dependency
cd /path/to/floe
pip install -e ".[dev]"

# Verify installation
python -c "import agent_memory; print(agent_memory.__version__)"
```

---

## 3. Initial Configuration

### Create Configuration File

```bash
# Initialize configuration
make cognee-init --setup

# Or manually create .cognee/config.yaml
mkdir -p .cognee
cat > .cognee/config.yaml << 'EOF'
version: "1.0"

cognee:
  api_url: "https://api.cognee.ai"
  api_key_env: "COGNEE_API_KEY"

llm:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"

datasets:
  architecture: "architecture"
  governance: "governance"
  codebase: "codebase"
  skills: "skills"

sources:
  - path: "docs/architecture/**/*.md"
    dataset: "architecture"
    file_extensions: [".md"]
  - path: ".specify/memory/constitution.md"
    dataset: "governance"
  - path: ".claude/rules/*.md"
    dataset: "governance"
  - path: ".claude/skills/*/SKILL.md"
    dataset: "skills"
  - path: "packages/*/src/**/*.py"
    dataset: "codebase"
    file_extensions: [".py"]

operations:
  batch_size: 20
  search_top_k: 10
  default_search_type: "GRAPH_COMPLETION"
EOF
```

### Verify Connection

```bash
# Check Cognee Cloud connectivity
make cognee-health

# Expected output:
# HealthStatus: healthy
# - Cognee Cloud: healthy (150ms)
# - LLM Provider: healthy (200ms)
# - Local State: healthy
```

---

## 4. Initial Indexing

### Index Architecture Documentation

```bash
# Full initial load (may take 5-10 minutes)
make cognee-init

# With progress display
make cognee-init PROGRESS=1

# Resume interrupted load
make cognee-init RESUME=1
```

### Verify Indexing

```bash
# Check coverage
make cognee-coverage

# Expected output:
# Coverage Report
# - Filesystem files: 95
# - Indexed files: 95
# - Coverage: 100%
```

---

## 5. Basic Operations

### Search

```bash
# Search architecture documentation
make cognee-search QUERY="What is the plugin system?"

# Search with specific strategy
make cognee-search QUERY="How does CompiledArtifacts work?" TYPE=GRAPH_COMPLETION

# Search codebase docstrings
make cognee-search QUERY="What does CogneeClient do?" TYPE=CODE DATASET=codebase
```

### Sync Changes

```bash
# Sync files changed since last commit
make cognee-sync

# Sync specific files
make cognee-sync FILES="docs/architecture/adr/0046-agent-memory.md"

# Check what would be synced (dry run)
make cognee-sync DRY_RUN=1
```

### Operational Commands

```bash
# Health check
make cognee-health

# Coverage analysis
make cognee-coverage

# Drift detection
make cognee-drift

# Repair drifted entries (without full rebuild)
make cognee-repair

# Full reset (destructive - requires confirmation)
make cognee-reset CONFIRM=1

# Run quality validation tests
make cognee-test
```

---

## 6. Git Hook Integration

### Install Hooks

```bash
# Install git hooks for automatic sync
make setup-hooks

# This adds:
# - post-commit: async sync of changed files
# - post-merge: trigger rebuild notification
```

### How Hooks Work

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  git commit │────►│ post-commit  │────►│ cognee-sync  │
│             │     │ (async)      │     │ (background) │
└─────────────┘     └──────────────┘     └──────────────┘
       │
       │ Non-blocking: commit completes immediately
       ▼
┌─────────────┐
│  Commit     │
│  Completed  │
└─────────────┘
```

---

## 7. Claude Code MCP Integration

### Configure MCP Server

```bash
# Add Cognee MCP to Claude Code
claude mcp add --transport http cognee http://localhost:8000/mcp -s project
```

### Start MCP Server

```bash
# Start Cognee MCP server (Docker)
docker run -e TRANSPORT_MODE=http \
  -e LLM_API_KEY=$OPENAI_API_KEY \
  -e API_URL=https://api.cognee.ai \
  -e API_TOKEN=$COGNEE_API_KEY \
  -p 8000:8000 --rm -it cognee/cognee-mcp:main

# Or via make target
make cognee-mcp-start
```

### Using in Claude Code

```
User: "What is the plugin system architecture?"

Claude: (searches Cognee via MCP)
Based on the architecture documentation, the plugin system...
[References ADR-0001, ADR-0003]
```

### Available MCP Tools

| Tool | Usage |
|------|-------|
| `search` | Query knowledge graph |
| `cognify` | Index new content |
| `codify` | Index code with docstrings |
| `list_data` | List indexed datasets |
| `delete` | Remove specific content |

---

## 8. Troubleshooting

### Connection Issues

```bash
# Test Cognee Cloud connection
curl -H "Authorization: Bearer $COGNEE_API_KEY" \
  https://api.cognee.ai/health

# Check environment variables
echo $COGNEE_API_KEY | head -c 10  # Should show first 10 chars
echo $OPENAI_API_KEY | head -c 10
```

### Sync Failures

```bash
# Check sync state
cat .cognee/state.json | jq .last_sync_status

# View failed files
cat .cognee/state.json | jq .failed_files

# Retry failed files
make cognee-sync FILES="$(cat .cognee/state.json | jq -r '.failed_files[]')"
```

### Quality Issues

```bash
# Run quality validation
make cognee-test

# If searches return poor results:
# 1. Check if content is indexed
make cognee-coverage

# 2. Try different search types
make cognee-search QUERY="your query" TYPE=RAG_COMPLETION
make cognee-search QUERY="your query" TYPE=CHUNKS

# 3. Rebuild affected dataset
make cognee-rebuild DATASETS=architecture CONFIRM=1
```

### Reset Everything

```bash
# Nuclear option: full reset and rebuild
make cognee-reset CONFIRM=1
make cognee-init
```

---

## 9. Common Workflows

### After Adding New ADRs

```bash
# 1. Add new ADR file
vim docs/architecture/adr/0050-new-decision.md

# 2. Commit (hook triggers sync)
git add . && git commit -m "Add ADR-0050"

# 3. Verify indexed (optional)
make cognee-search QUERY="ADR-0050"
```

### Before Major Refactoring

```bash
# 1. Check current coverage
make cognee-coverage

# 2. Detect any drift
make cognee-drift

# 3. Repair if needed
make cognee-repair
```

### Session Recovery (After Compaction)

```bash
# When starting a new Claude Code session after compaction:
# The bd prime command includes Cognee context injection

bd prime  # Beads prime command with Cognee integration
```

---

## 10. Next Steps

1. **Read the full specification**: `specs/10a-agent-memory/spec.md`
2. **Review the data model**: `specs/10a-agent-memory/data-model.md`
3. **Check the research**: `specs/10a-agent-memory/research.md`
4. **Report issues**: Create issue in Linear with `agent-memory` label
