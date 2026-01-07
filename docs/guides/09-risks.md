# 09. Risks and Technical Debt

This document describes known risks, technical debt, and mitigation strategies for floe.

---

## 1. Risk Overview

| ID | Risk | Impact | Probability | Priority |
|----|------|--------|-------------|----------|
| R-1 | Dagster daemon crash | High | Medium | High |
| R-2 | PostgreSQL failover | High | Low | Medium |
| R-3 | OCI registry unavailability | Medium | Low | Medium |
| R-4 | Polaris catalog corruption | High | Low | High |
| R-5 | Network policy blocks traffic | Medium | Medium | Medium |
| R-6 | Version upgrade failures | Medium | Medium | Medium |

---

## 2. Risk Details

### R-1: Dagster Daemon Crash Recovery

**Description:**
The Dagster daemon is responsible for scheduling sensor evaluations and run coordination. If the daemon crashes or becomes unresponsive, scheduled runs will not trigger and sensors will stop evaluating.

**Impact:** High
- Scheduled pipelines stop executing
- Sensors stop detecting new data
- Run queue stalls

**Probability:** Medium
- Daemon is stateless and restartable
- PostgreSQL connection issues can cause daemon failures
- Memory pressure in constrained environments

**Mitigation Strategy:**
1. Deploy daemon as Kubernetes Deployment with `restartPolicy: Always`
2. Configure liveness and readiness probes:
   ```yaml
   livenessProbe:
     httpGet:
       path: /health
       port: 8080
     initialDelaySeconds: 30
     periodSeconds: 10
   ```
3. Set up alerting on daemon heartbeat metrics
4. Document manual restart procedure: `kubectl rollout restart deployment/dagster-daemon -n floe-platform`

**Status:** Partially mitigated (Helm chart includes probes, alerting not documented)

---

### R-2: PostgreSQL Failover Procedures

**Description:**
Dagster and Polaris both depend on PostgreSQL for metadata storage. In production deployments, PostgreSQL should be configured for high availability, but failover procedures are not fully documented.

**Impact:** High
- Dagster loses run history and schedule state
- Polaris loses catalog metadata
- Complete platform outage during failover

**Probability:** Low
- Managed PostgreSQL services (RDS, Cloud SQL) handle failover automatically
- Self-managed PostgreSQL requires manual HA configuration

**Mitigation Strategy:**
1. Use managed PostgreSQL with Multi-AZ replication (recommended)
2. For self-managed PostgreSQL:
   - Deploy PostgreSQL with Patroni or Stolon for HA
   - Configure synchronous replication for zero data loss
   - Test failover quarterly
3. Document connection string updates during manual failover
4. Backup PostgreSQL daily with retention per `06-deployment-view.md`

**Status:** Partially mitigated (HA mentioned in deployment view, procedures not documented)

---

### R-3: OCI Registry Unavailability

**Description:**
Platform manifests are stored in an OCI registry (GHCR, ECR, Harbor). If the registry becomes unavailable, `floe compile` cannot fetch platform manifests, and new deployments cannot pull container images.

**Impact:** Medium
- New pipeline deployments fail
- Existing running pipelines continue (images already pulled)
- CI/CD pipelines blocked

**Probability:** Low
- Major cloud registries have high availability SLAs
- Self-hosted registries may have lower availability

**Mitigation Strategy:**
1. Use ImagePullPolicy: IfNotPresent to cache images on nodes
2. Cache platform manifests locally during `floe compile --cache`
3. For air-gapped deployments, use local registry mirror (see `oci-registry-requirements.md`)
4. Monitor registry availability with uptime checks

**Status:** Partially mitigated (air-gapped support documented, caching not implemented)

---

### R-4: Polaris Catalog Corruption

**Description:**
Apache Polaris stores Iceberg table metadata including table locations, schemas, and partition specs. Catalog corruption could result in inability to access tables or data loss if table pointers are corrupted.

**Impact:** High
- Tables become inaccessible
- Data may appear lost (though Iceberg data files remain intact)
- Recovery requires manual intervention

**Probability:** Low
- Polaris uses PostgreSQL for storage (ACID guarantees)
- Corruption typically results from storage failures or bugs

**Mitigation Strategy:**
1. Backup PostgreSQL containing Polaris metadata daily
2. Enable Iceberg's metadata backup feature:
   ```yaml
   catalog:
     config:
       write.metadata.previous-versions-max: 10
   ```
3. Document recovery procedure:
   - Restore PostgreSQL from backup
   - If metadata lost, Iceberg tables can be recovered from data files using `spark-sql` to re-register tables
4. Test recovery procedure quarterly

**Status:** Not mitigated (backup exists but recovery procedure not documented)

---

### R-5: Network Policy Blocks Traffic

**Description:**
floe deploys NetworkPolicies to restrict traffic between namespaces (see ADR-0022). Misconfigured policies can block legitimate traffic, causing pipeline failures that are difficult to diagnose.

**Impact:** Medium
- Pipeline jobs fail with connection timeouts
- Error messages may not indicate network policy as cause
- Debugging requires Kubernetes network expertise

**Probability:** Medium
- Custom network policies may conflict with floe defaults
- CNI plugin differences affect policy behavior

**Mitigation Strategy:**
1. Use `kubectl describe networkpolicy` to audit active policies
2. Test connectivity from job pods:
   ```bash
   kubectl run test-pod --rm -it --image=busybox -n floe-jobs -- \
     wget -qO- http://polaris.floe-platform.svc.cluster.local:8181/health
   ```
3. Enable NetworkPolicy logging if CNI supports it (Calico, Cilium)
4. Document common network policy troubleshooting in runbooks

**Status:** Not mitigated (network policies deployed but debugging guidance absent)

---

### R-6: Version Upgrade Failures

**Description:**
Upgrading floe (Python packages, Helm charts, or platform manifests) may introduce breaking changes. Without documented upgrade procedures, teams may encounter unexpected failures during upgrades.

**Impact:** Medium
- Pipeline failures after upgrade
- Rollback may be complex if database migrations applied
- Downtime during failed upgrades

**Probability:** Medium
- Breaking changes possible between minor versions
- Database schema changes require careful handling

**Mitigation Strategy:**
1. Follow semantic versioning for breaking changes
2. Document upgrade procedure:
   - Backup PostgreSQL before upgrade
   - Upgrade packages: `uv pip install --upgrade floe-cli`
   - Upgrade Helm: `helm upgrade floe-platform ./charts/floe-platform`
   - Verify health checks pass
3. Maintain changelog with breaking changes highlighted
4. Test upgrades in staging environment before production

**Status:** Not mitigated (no upgrade documentation exists)

---

## 3. Technical Debt

### TD-1: Python Transforms Deferred

**Description:** Python-based transforms are deferred to future scope due to complexity with telemetry and lineage integration.

**Impact:** Users cannot define Python UDFs or custom transformations outside of dbt SQL.

**Mitigation:** Use dbt Python models where compute target supports them (Snowflake, Databricks).

---

### TD-2: Flink Streaming Deferred

**Description:** Real-time streaming via Apache Flink is deferred (ADR-0014).

**Impact:** floe currently supports batch pipelines only.

**Mitigation:** Use Kafka + dbt microbatch pattern for near-real-time scenarios.

---

### TD-3: Some Plugins in Beta

**Description:** Several plugins are marked as beta:
- `floe-compute-spark` (beta)
- `floe-catalog-glue` (beta)
- `floe-semantic-cube` (beta)

**Impact:** API stability not guaranteed, may have undocumented limitations.

**Mitigation:** Use default plugins (DuckDB, Polaris, Dagster) for production workloads until plugins reach stable status.

---

## 4. Related Documentation

- [ADR-0022: Security & RBAC Model](../architecture/adr/0022-security-rbac-model.md) - Network policies
- [ADR-0023: Secrets Management](../architecture/adr/0023-secrets-management.md) - Credential handling
- [06-Deployment View](06-deployment-view.md) - Backup procedures
- [07-Crosscutting](07-crosscutting.md) - Error handling patterns
