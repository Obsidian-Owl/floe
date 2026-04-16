# Research Brief: E2E Tunnel Stability

**Topic**: SSH tunnel and kubectl port-forward stability for DevPod/Hetzner E2E test infrastructure
**Date**: 2026-03-29
**Confidence**: HIGH (official docs + observed failure evidence)
**Tracks**: 4

---

## Context

The floe E2E test suite runs for ~48 minutes against a Kind cluster inside a DevPod workspace on Hetzner. Two layers of tunneling connect the local test runner to remote services:

1. **K8s API tunnel**: `devpod ssh floe -L 26443:172.18.0.2:6443 --command "sleep infinity"` (established by `devpod-sync-kubeconfig.sh`)
2. **Service tunnels**: `ssh -fN -L <port>:localhost:<port> floe.devpod` (established by `devpod-tunnels.sh`, 9 ports)

`kubectl port-forward` is also used by `test-e2e.sh` for services without NodePort mappings (notably Dagster webserver, which Dagster 1.12+ schema disallows NodePort on).

During the last E2E run, tunnels died at ~16% (minute 8 of 48), causing 72 ERRORs and 18 cascading FAILs.

---

## Track 1: kubectl port-forward Reliability Issues

### Key Findings

| Finding | Confidence | Source |
|---------|------------|--------|
| SPDY protocol (pre-K8s 1.31) causes proxy/gateway failures; WebSocket transition is beta since 1.31 | HIGH | [K8s blog: WebSocket transition](https://kubernetes.io/blog/2024/08/20/websockets-transition/) |
| `streamingConnectionIdleTimeout` kubelet default = 4h; terminates idle port-forwards silently | HIGH | [Baeldung: Port-forward timeout](https://www.baeldung.com/ops/kubernetes-timeout-issue-port-forwarding) |
| Port-forward does NOT auto-recover after interruption (kubernetes/kubernetes#78446, closed "not planned") | HIGH | [GH#78446](https://github.com/kubernetes/kubernetes/issues/78446) |
| `--keepalive-time` flag added in kubectl v1.24 but not listed in port-forward docs | MEDIUM | [codestudy.net](https://www.codestudy.net/blog/kubectl-port-forwarding-timeout-issue/) |
| Connection path: kubectl → API server (SPDY/WS) → kubelet → socat into pod netns; failure at any hop is silent | HIGH | [Medium deep-dive](https://dumlutimuralp.medium.com/how-kubectl-port-forward-works-79d0fbb16de3) |

### Root Cause for floe

The port-forwards started by `test-e2e.sh` are backgrounded (`&`) with no health monitoring. When the SSH tunnel to the K8s API dies (Track 2), all `kubectl port-forward` processes lose their control channel and silently stop forwarding. They remain as zombie processes — still running but no longer functional.

---

## Track 2: SSH Tunnel Stability (DevPod)

### Key Findings

| Finding | Confidence | Source |
|---------|------------|--------|
| OpenSSH `ServerAliveInterval` (default: 0 = disabled) is the correct mechanism for preventing idle drops | HIGH | [OpenBSD ssh_config](https://man.openbsd.org/ssh_config) |
| DevPod's Go SSH client (`golang.org/x/crypto/ssh`) does NOT implement `ServerAliveInterval` natively | HIGH | [golang/go#21478](https://github.com/golang/go/issues/21478) |
| When DevPod uses system OpenSSH (default when available), standard SSH options apply | MEDIUM | [devpod-provider-ssh](https://github.com/loft-sh/devpod-provider-ssh) |
| `nohup ... --command "sleep infinity"` without stdin redirect causes hanging | HIGH | [RedHat BZ#467622](https://bugzilla.redhat.com/show_bug.cgi?id=467622) |
| DevPod port forwarding requires an active SSH session (issue #871) | HIGH | [GH#871](https://github.com/loft-sh/devpod/issues/871) |

### Current floe Configuration Gaps

1. **No SSH keepalive**: Neither `devpod-tunnels.sh` nor `devpod-sync-kubeconfig.sh` passes `-o ServerAliveInterval=N` or `-o ServerAliveCountMax=N`
2. **No stdin redirect**: The `nohup devpod ssh ... --command "sleep infinity"` doesn't redirect stdin (`< /dev/null`)
3. **No tunnel health monitoring**: Once established, tunnels are never checked again
4. **Port binding races**: `devpod-ssh.log` shows repeated `bind: address already in use` errors from stale processes

### Evidence from `~/.kube/devpod-ssh.log`

```
"listen tcp 127.0.0.1:26443: bind: address already in use"     (multiple entries)
"wait: remote command exited without exit status or exit signal" (multiple entries)
"timeout waiting for instance connection"                        (cascade failures)
```

---

## Track 3: Alternatives to kubectl port-forward

### Tier 1: Drop-in replacements (minimal change)

| Tool | Auto-reconnect | Mechanism | CI-friendly | Notes |
|------|---------------|-----------|-------------|-------|
| **kubefwd** | Yes (exponential backoff) | K8s Informers | Yes (CLI) | Requires sudo for /etc/hosts; bulk-forwards entire namespace |
| **kftray/kftui** | Yes (event-driven) | K8s Watch API | Yes (TUI mode) | Rust binary, network-aware reconnect |
| **krelay** | Yes (rolling updates) | SPDY-over-WS | Yes (kubectl plugin) | Forwards to Service not Pod |

### Tier 2: Architecture changes

| Approach | Tunnel eliminated? | Complexity | Notes |
|----------|-------------------|------------|-------|
| **In-cluster test runner** | Yes (entirely) | High | Run pytest inside a pod; no port-forward needed |
| **SSH direct to API + NodePorts** | Partially | Medium | Skip port-forward layer, use NodePorts for services |
| **autossh wrapper** | No (monitors SSH) | Low | Auto-restarts SSH tunnel on failure |

### Recommended: autossh + SSH keepalive (lowest effort)

The current architecture is sound — the only gap is keepalive and auto-recovery. `autossh` + SSH keepalive options would fix the root cause with minimal code change:

```bash
# Replace: ssh -fN -L ...
# With: autossh -M 0 -f -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L ...
```

---

## Track 4: Port-forward Auto-Recovery Patterns

### Pattern 1: Restart loop (simple)

```bash
while true; do
    kubectl port-forward svc/my-service 8080:8080
    echo "Port-forward died, restarting in 2s..."
    sleep 2
done &
```

**Limitation**: Does not detect silently-dead port-forwards (kubernetes/kubernetes#78446).

### Pattern 2: Health-check + restart (robust)

```bash
while true; do
    if ! curl -sf http://localhost:8080/health >/dev/null 2>&1; then
        pkill -f "port-forward.*8080" || true
        sleep 1
        kubectl port-forward svc/my-service 8080:8080 &
    fi
    sleep 30
done &
```

**Best for**: Supplementing port-forward with active monitoring during long test runs.

### Pattern 3: Managed tool (recommended for production)

kubefwd or kftray handle reconnection internally via K8s Informers/Watch API.

---

## Synthesis: Root Cause Chain for floe E2E Failures

```
1. SSH tunnel to K8s API (port 26443) has no keepalive
   ↓ idle timeout or network hiccup
2. SSH tunnel process exits silently (logged as "exited without exit status")
   ↓
3. kubectl port-forward loses API server connection
   ↓
4. All service port-forwards die (Dagster, Polaris, MinIO, Marquez, Jaeger, OTel)
   ↓
5. 72 test ERRORs: "TCP connection to localhost:XXXX failed"
   ↓
6. 18 test FAILs: cascading from dead services
```

**Fix hierarchy (least effort first)**:

1. **Add SSH keepalive** to both `devpod-tunnels.sh` and `devpod-sync-kubeconfig.sh`: `-o ServerAliveInterval=30 -o ServerAliveCountMax=3`
2. **Add stdin redirect** to kubeconfig sync: `< /dev/null`
3. **Add port-forward health monitoring** to `test-e2e.sh`: background loop that checks ports and restarts dead forwards
4. **Consider autossh** for the K8s API tunnel (auto-restarts on failure)
5. **Long-term**: Evaluate kubefwd or in-cluster test runner for eliminating port-forward entirely

---

## Open Questions

1. Is `devpod ssh` using the Go SSH client or system OpenSSH? (Determines whether `-o ServerAliveInterval` is respected)
2. What K8s version is the Kind cluster running? (Determines SPDY vs WebSocket for port-forward)
3. Would Dagster accept a PR to allow NodePort configuration? (Would eliminate the most critical port-forward dependency)

---

## Sources

All sources cited inline. Key references:
- [kubernetes/kubernetes#78446](https://github.com/kubernetes/kubernetes/issues/78446) — port-forward no auto-recovery
- [OpenBSD ssh_config](https://man.openbsd.org/ssh_config) — ServerAliveInterval docs
- [golang/go#21478](https://github.com/golang/go/issues/21478) — Go SSH lacks keepalive
- [DevPod#871](https://github.com/loft-sh/devpod/issues/871) — port forwarding requires active session
- [kubefwd](https://github.com/txn2/kubefwd) — managed port forwarding with auto-reconnect
- [kftray](https://github.com/hcavarsan/kftray) — event-driven port forwarding
- [autossh](https://taozhi.medium.com/how-to-keep-ssh-tunnel-alive-5abed92ad598) — SSH tunnel auto-recovery
