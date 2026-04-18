# Code Intelligence Tool Selection

## Tool Escalation Ladder

Use the cheapest tool that answers the question. Escalate only when it fails.

| Step | Tool | Use when | Token cost |
|------|------|----------|-----------|
| 1 | `Grep` | Known symbol or string name | ~50 |
| 2 | `Auggie` (`augment_code_search`) | Conceptual "how does X work?" or multi-file discovery | ~2,000 |
| 3 | `GitNexus impact()` | Before editing shared contracts or cross-package symbols | ~4,000 |
| 4 | `GitNexus cypher()` | Structural queries Grep can't answer ("all implementors of X") | ~1,000 |
| 5 | `GitNexus detect_changes()` | Pre-commit scope verification | ~500 |

---

## Grep (Default — Use First)

Grep is the right tool for 70%+ of searches. Use it whenever you know the symbol name, function name, class name, or error string.

```
Grep("def compile_pipeline", type="py")     # Find definition
Grep("CompiledArtifacts", type="py")         # Find all references
Grep("class.*CatalogPlugin", type="py")      # Find implementations
```

---

## Auggie Context Engine

Auggie (`augment_code_search`) is a remote semantic search over the GitHub-indexed repo. It returns actual source code at natural granularity — readable without follow-up file reads.

**Use for:**
- "How does the compilation pipeline work?"
- "Show me how Polaris authentication is handled"
- "Where is plugin discovery implemented?"
- Any conceptual question spanning multiple files

**Configuration:**
```
repo_owner: Obsidian-Owl
repo_name: floe
branch: main (default)
```

**Do NOT use for:**
- Known symbol lookup (use Grep — 50x cheaper)
- "What breaks if I change X?" (cannot model dependencies)
- Feature branch code (indexes main only)

---

## GitNexus

GitNexus is a local code knowledge graph. It models symbol relationships, call chains, and execution flows. Most of its tools are too expensive for routine use — use only the two that justify their token cost.

### impact() — Use Before Editing Shared Code

The only tool that answers "what breaks if I change X?" Returns depth-grouped dependents with risk level.

**Use when editing:**
- Shared contract types (`CompiledArtifacts`, `FloeSpec`)
- Plugin ABCs in `floe-core/plugins/` or `testing/base_classes/*`
- Functions with >5 callers or called from another package
- Cross-package refactors

**Do NOT use for:**
- Local edits inside a single file
- Private/underscore-prefixed functions
- Test-only changes
- Docstring, type hint, or formatting changes

**Always pass `repo: "floe"`** — the index contains multiple repos and will error without it.

### detect_changes() — Use Before Committing

Maps staged diffs to affected symbols and execution flows. Cheap safety net.

```
gitnexus_detect_changes({scope: "staged", repo: "floe"})
```

### cypher() — Use for Structural Queries

Precise graph queries when Grep's regex isn't enough.

```
gitnexus_cypher({
  query: "MATCH (c)-[:CodeRelation {type: 'IMPLEMENTS'}]->(i {name: 'CatalogPlugin'}) RETURN c.name, c.filePath",
  repo: "floe"
})
```

### Tools to AVOID in Routine Use

| Tool | Problem | Use Instead |
|------|---------|-------------|
| `gitnexus_query()` | 2-5k tokens, noisy results, ranks test files above source | Auggie or Grep |
| `gitnexus_context()` | 3-5k tokens for a full 360-degree dump | `Read` the file directly |
| `gitnexus_rename()` | Heavyweight for simple renames | Grep + manual Edit |

These tools exist and work, but their token cost rarely justifies the result over cheaper alternatives. Reserve them for genuinely complex structural questions where no simpler tool suffices.

---

## Anti-Patterns

- **Running `gitnexus_impact` on every edit**: Wastes 4k tokens on changes to private functions. Only use for shared contracts and cross-package symbols.
- **Using `gitnexus_query` for known names**: It returns noisy process-grouped JSON. Grep finds the exact file in 50 tokens.
- **Using `gitnexus_context` to "understand" a symbol**: Reading the file directly is cheaper and gives you the actual code, not a JSON manifest of relationships.
- **Using Auggie for known symbol lookup**: Semantic search is overkill when you have the exact name. Grep first.
- **Skipping Grep and jumping to semantic search**: The token savings from using Grep first compound across a session. 20 Grep queries = ~1k tokens. 20 Auggie queries = ~40k tokens.
