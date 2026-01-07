# Agent Delegation Rules

## CRITICAL: Context Preservation via Subagent Delegation

When working on tasks that involve log analysis, debugging, or repetitive extraction, you MUST delegate to specialised agents to preserve the main conversation's context window.

## Mandatory Delegation Triggers

### Docker/Container Log Analysis
**Trigger**: Any request involving `docker logs`, container debugging, or service troubleshooting

**Action**: Spawn `docker-log-analyser` agent with:
```
Task: Analyse [container/service] for [specific issue]
Focus: [error type if known]
Return: Diagnosis, fix, verification command only
```

**Command**: Use `Task(docker-log-analyser, "...")`

### Helm/K8s Debugging  
**Trigger**: Any request involving `kubectl logs`, pod failures, Helm deployments, or K8s troubleshooting

**Action**: Spawn `helm-debugger` agent with:
```
Task: Debug [chart/pod/deployment]
Issue: [symptom]
Return: Root cause and fix only
```

**Command**: Use `Task(helm-debugger, "...")`

## Delegation Protocol

1. **Never dump full logs in main context** — always delegate
2. **Subagent returns summary only** — not raw output
3. **Main context asks clarifying questions** — subagent does extraction
4. **Use `/project:k8s-debug` command** for complex debugging sessions

## Anti-Patterns (FORBIDDEN)

❌ Running `docker logs <container>` without `--tail=N` in main context
❌ Running `kubectl logs <pod>` without delegation for analysis
❌ Pasting 50+ lines of log output into the conversation
❌ Multiple back-and-forth log extraction cycles in main context

## Example Delegation

**User**: "The Dagster webserver pod keeps crashing"

**Bad Response** (consumes context):
```bash
kubectl logs dagster-webserver-abc123
# [200 lines of logs pasted]
```

**Good Response** (preserves context):
```
I'll delegate this to the helm-debugger agent for context-efficient analysis.

Task(helm-debugger, "Debug dagster-webserver pod crash. Focus on startup errors and database connection. Return root cause and fix only.")
```
