# Context-Efficient Log Analysis

## Rule: Never Dump Full Logs

When debugging Docker or Kubernetes issues, ALWAYS:

1. **Use `--tail=N`** on all log commands (N ≤ 30)
2. **Pipe through grep** to extract only error lines
3. **Summarise findings** rather than pasting raw output
4. **Delegate to subagents** for deep analysis

## Approved Patterns

```bash
# ✅ Context-efficient
kubectl logs <pod> --tail=20 2>&1 | grep -i "error\|fail"
docker logs <container> --tail=30 2>&1 | grep -i "exception"
kubectl get events --sort-by='.lastTimestamp' | tail -20

# ❌ Context-burning (NEVER DO)
kubectl logs <pod>
docker logs <container>
kubectl describe pod <pod>  # without | grep
```

## Subagent Delegation

For complex debugging, spawn the appropriate agent:

- **Log analysis**: `docker-log-analyser`
- **Helm/K8s issues**: `helm-debugger`

Example prompt to spawn:
```
Use the helm-debugger agent to diagnose why floe-dagster pods are in CrashLoopBackOff.
Return only the root cause and fix.
```

## Why This Matters

- Claude Code has ~100-200k token context window
- Full pod logs can be 10-50k tokens
- 3-4 log dumps = context exhaustion
- Efficient extraction preserves context for actual development work

## Enforcement

Before running any log command, ask:
1. Can I use `describe` instead of `logs`?
2. Am I using `--tail=N`?
3. Am I filtering for errors?
4. Should I delegate to a subagent?
