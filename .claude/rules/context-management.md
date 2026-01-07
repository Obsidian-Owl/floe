# Context Management Best Practices

Based on Claude Code official documentation and community best practices (December 2025).

## How Subagent & Skill Auto-Invocation Works

### Subagents
Claude Code **automatically delegates** to subagents when:
1. The task matches the subagent's `description` field
2. The description contains trigger phrases like:
   - `MUST BE USED PROACTIVELY`
   - `Use IMMEDIATELY when...`
   - `ALWAYS delegate...`

Without these phrases, Claude may not proactively use your subagents.

### Skills
Skills are **always on** — Claude pre-loads the `name` and `description` from all SKILL.md files into its system prompt. Claude automatically activates skills when:
1. The task context matches the skill description
2. Key terms in user messages match skill description terms

Skills load their full content **on-demand** via progressive disclosure.

## Built-in Subagents (Use These First!)

Claude Code includes built-in subagents that work automatically:

| Agent | Purpose | When Used |
|-------|---------|-----------|
| **Explore** | Fast, read-only codebase searching | Haiku model, auto-delegates for file discovery |
| **Plan** | Research during plan mode | Only in plan mode, gathers context for planning |
| **General-purpose** | Complex multi-step tasks | Sonnet model, when modification is needed |

**Key insight**: Claude automatically uses the Explore subagent for codebase searches to preserve main context. You don't need to create a separate "codebase-explorer" agent.

## Context Preservation Strategies

### 1. Use /clear Strategically
```bash
/clear  # Wipes conversation history, keeps CLAUDE.md and project files
```
Use after:
- Completing a feature/ticket
- Before switching to unrelated tasks
- When context is polluted with old debug info

### 2. Keep CLAUDE.md Lean
Your CLAUDE.md is ~800 lines. This consumes ~15-20k tokens on every interaction.

**Recommended structure:**
```
CLAUDE.md (root) - 100-150 lines max
├── Quick start commands
├── Project structure overview
├── Core standards summary (link to details)
└── Skill/Agent delegation reminders

.claude/CLAUDE.md - Full development standards (loaded via @import)
.claude/rules/*.md - Specific rules (loaded on-demand)
.claude/skills/*/SKILL.md - Domain expertise (loaded when needed)
```

### 3. Let Skills Handle Domain Context
Instead of putting everything in CLAUDE.md, use skills for domain-specific knowledge. Skills only load when relevant.

Example: Pydantic rules in `pydantic-skill/SKILL.md` only load when Claude detects Pydantic work.

### 4. Delegate Log Analysis ALWAYS
Logs are context killers. One `kubectl logs <pod>` can consume 10-50k tokens.

**Rule**: Never run log commands in main context. Always delegate to:
- `docker-log-analyser` agent
- `helm-debugger` agent
- Or use the built-in Explore subagent with `--tail=N`

## Trigger Phrase Reference

Add these to subagent/skill descriptions for proactive invocation:

```yaml
# Strong triggers (most proactive)
description: MUST BE USED PROACTIVELY for...
description: ALWAYS USE when working with...
description: Use IMMEDIATELY when...

# Moderate triggers
description: Use proactively for...
description: Automatically invoke for...

# Weak triggers (may not auto-invoke)
description: Use for...  # Too passive
description: Handles...  # No action trigger
```

## Debugging Auto-Invocation Issues

If Claude isn't using your subagents/skills:

1. **Check the description** — is it specific enough? Does it include trigger phrases?
2. **Validate YAML syntax** — invalid frontmatter silently fails
3. **Check file location** — `.claude/agents/` for agents, `.claude/skills/` for skills
4. **Restart session** — newly added files need a session restart (or use `/agents`)
5. **Test explicitly first** — "Use the helm-debugger agent to..." then check if it auto-invokes next time

## The "Master-Clone" Pattern (Alternative)

Some experts prefer NOT using custom subagents. Instead:
1. Put key context in CLAUDE.md
2. Let Claude use its built-in `Task(...)` to spawn clones of itself
3. Claude manages its own orchestration dynamically

This avoids the "context gatekeeping" problem where specialized agents hide context from the main agent.

**When to use custom subagents:**
- Highly specialized workflows (security audit, data science)
- Strict tool restrictions (read-only agents)
- Team-wide consistency (versioned in repo)

**When to skip custom subagents:**
- Dynamic, exploratory work
- Tasks that need holistic context
- When you want Claude to decide how to delegate

## References

- [Claude Code Subagents Docs](https://code.claude.com/docs/en/sub-agents)
- [Agent Skills Docs](https://code.claude.com/docs/en/skills)
- [Best Practices for Agentic Coding](https://www.anthropic.com/engineering/claude-code-best-practices)
