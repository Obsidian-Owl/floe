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

MCP (Model Context Protocol) allows Claude Code to directly query the Cognee knowledge graph during conversations.

### Step 1: Start MCP Server

```bash
# Start Cognee MCP server (interactive mode)
make cognee-mcp-start

# Or in background (detached mode)
make cognee-mcp-start DETACH=1

# Custom port
make cognee-mcp-start PORT=9000

# Stop running server
make cognee-mcp-stop
```

**Note**: The server requires `COGNEE_API_KEY` and `OPENAI_API_KEY` environment variables.

### Step 2: Configure Claude Code

```bash
# Generate and install MCP configuration
make cognee-mcp-config INSTALL=1

# This creates/updates .claude/mcp.json with:
# {
#   "mcpServers": {
#     "cognee": {
#       "transport": "http",
#       "url": "http://localhost:8000/mcp"
#     }
#   }
# }
```

**Or manually configure**:

```bash
# View configuration (without installing)
make cognee-mcp-config

# Then add to .claude/mcp.json manually
```

### Step 3: Verify Integration

1. Restart Claude Code (or reload the conversation)
2. The MCP server should appear in Claude Code's available tools
3. Test with a query:

```
User: "What is the plugin system architecture?"

Claude: (searches Cognee via MCP automatically)
Based on the architecture documentation in ADR-0001...
```

### Available MCP Tools

| Tool | Description | Example Usage |
|------|-------------|---------------|
| `search` | Query knowledge graph | "Search for plugin architecture" |
| `cognify` | Index new content | Automatically indexes conversations |
| `codify` | Index code with docstrings | Index Python files |
| `list_data` | List indexed datasets | "What datasets are available?" |
| `delete` | Remove specific content | Remove outdated entries |

### Manual Docker Command

If you prefer to run Docker directly:

```bash
docker run --rm -it \
  -e TRANSPORT_MODE=http \
  -e LLM_API_KEY="$OPENAI_API_KEY" \
  -e API_URL=https://api.cognee.ai \
  -e API_TOKEN="$COGNEE_API_KEY" \
  -p 8000:8000 \
  cognee/cognee-mcp:main
```

### Troubleshooting MCP

**Server won't start**:
```bash
# Check environment variables
make cognee-check-env

# Check if port is in use
lsof -i :8000
```

**Claude Code doesn't see MCP server**:
1. Verify server is running: `docker ps | grep cognee`
2. Test server directly: `curl http://localhost:8000/mcp`
3. Reload Claude Code configuration

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

### Coverage Shows 0% Despite Files Being Indexed

This happens when running commands from the wrong directory. The `.cognee/checksums.json` file stores **relative paths** from your CLI working directory.

```bash
# ❌ WRONG: Running from subdirectory
cd devtools/agent-memory
uv run agent-memory coverage  # Shows 0%!

# ✅ CORRECT: Run from project root (where .cognee/ is)
cd /path/to/floe
uv run agent-memory coverage  # Shows 100%

# Or use make targets (always run from root)
make cognee-coverage
```

**Why this happens**: `checksums.json` stores paths like `../../docs/architecture/...`. These are relative to where you ran `init`. Coverage compares these against absolute filesystem paths, so the working directory must match.

### Search Returns Results But Content is Empty

Cognee Cloud API returns search results in a nested format. If you see results with empty content:

```bash
# Check raw API response format
uv run agent-memory search "test query" --verbose

# Expected format from Cognee Cloud:
# {
#   "search_result": ["paragraph 1", "paragraph 2"],
#   "score": 0.85
# }
```

The `search_result` field is an array of strings, not a single `content` field. The CLI handles this automatically, but if writing custom integrations, parse `search_result` array.

### Quality Tests Fail Due to LLM Variability

Quality tests (`make cognee-test`) use keyword matching against LLM-generated responses. LLM responses vary, so:

```bash
# If tests fail with "missing keywords":
# 1. Check what content was actually indexed
make cognee-search QUERY="architecture" --verbose

# 2. Run tests with verbose output to see actual responses
make cognee-test VERBOSE=1

# 3. The default tests use flexible keywords:
#    - "architecture" (not "layer" or "plugin")
#    - "plugin" (not specific plugin names)
#    - "test" (not "pytest" or "coverage")
```

**Best practice**: When creating custom test queries, use broad keywords that should appear in any reasonable LLM response about the topic.

### Git Blocks Commits Due to "Secrets" in checksums.json

The `.cognee/checksums.json` file contains SHA256 file hashes that may trigger secret detection:

```bash
# Example content that triggers false positive:
# "docs/architecture/security.md": "a3f2b1c9e8d7..."

# Solution: These files are gitignored
cat devtools/agent-memory/.gitignore
# .cognee/checksums.json
# .cognee/state.json
# .cognee/checkpoint.json
```

If you see Aikido or other secret scanners flag these files, verify the `.gitignore` is in place. The hashes are file content checksums, not actual secrets.

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

# Or use the session-recover hook directly
./scripts/session-recover
```

**What session recovery does**:
1. Syncs Linear issues (`bd linear sync --pull`)
2. Shows ready work (`bd ready`)
3. Queries Cognee for relevant context based on active issues
4. Provides a summary of where you left off

**Tip**: If Cognee is unavailable, session recovery still works - it just skips the context injection step.

---

## 10. Next Steps

1. **Read the full specification**: `specs/10a-agent-memory/spec.md`
2. **Review the data model**: `specs/10a-agent-memory/data-model.md`
3. **Check the research**: `specs/10a-agent-memory/research.md`
4. **Report issues**: Create issue in Linear with `agent-memory` label
