## Plan: Phase 12 — Kubernetes Pod Spec Probes

Follows Phase 11 (CI Workflow Matrix Updates). All 5 services now have `/health` and `/readyz`
endpoints (Phase 10). Kubernetes manifests currently exist only for `ingestor` and `query_api`
and only in a local overlay. Phase 12 extends coverage to all 5 services, adds correct probe
configuration, resource limits, security contexts, and aligns the local overlay for a full
`k3d` stack run.

---

### Current State Audit

| Service | K8s manifest | `livenessProbe` | `readinessProbe` | `startupProbe` | Resources | SecurityContext |
|---|---|---|---|---|---|---|
| `ingestor` | ✅ manifests + chart + overlay | ✅ `/health` | ✅ `/readyz` | ❌ missing | ✅ requests+limits | ✅ non-root, drop ALL |
| `query_api` | ✅ manifests + chart + overlay | ⚠️ needs verify | ⚠️ needs verify | ❌ missing | ⚠️ needs verify | ⚠️ needs verify |
| `ai_gateway` | ❌ no manifest | — | — | — | — | — |
| `processor` | ❌ no manifest | — | — | — | — | — |
| `dashboard` | ❌ no manifest | — | — | — | — | — |

---

### Critical Findings

**Gap 1 — `ai_gateway`, `processor`, `dashboard` have no K8s manifests**
Three services cannot be deployed to Kubernetes at all. The local overlay only wires
`ingestor` and `query-api`. A full stack local test (`k3d`) requires all 5 services.

**Bug 2 — `startupProbe` missing from all manifests**
Services with slow startup (ai_gateway loads sentence-transformers; processor waits for
Redpanda consumer group join) will flap under `livenessProbe` before they are ready.
`startupProbe` with a generous `failureThreshold` prevents premature restarts during
cold boot while keeping the liveness check tight for steady-state.

**Gap 3 — `processor` is a StatefulSet candidate but was previously not deployable**
After Phase 10.4, processor is a FastAPI service. It remains a single-replica consumer
(Kafka partition affinity requires single consumer per topic partition in this config).
Use `Deployment` with `replicas: 1` and document the constraint; do NOT use StatefulSet
yet (overkill for current scale).

**Gap 4 — No `NetworkPolicy` isolating services**
All pods can talk to all other pods in the `data-zoo` namespace. `ingestor` should only
accept ingress; `processor` should only egress to Redpanda and `ingestor`. Adding basic
default-deny + allow-list `NetworkPolicy` resources closes this at the K8s layer.

---

### Architecture Decisions

#### Probe Configuration Per Service

| Service | `startupProbe` `failureThreshold` | `livenessProbe` period | `readinessProbe` period | Rationale |
|---|---|---|---|---|
| `ingestor` | 6 × 10s = 60s | 20s | 10s | Fast startup, DB ready quickly |
| `ai_gateway` | 30 × 10s = 300s | 30s | 15s | sentence-transformers slow to load |
| `processor` | 18 × 10s = 180s | 30s | 15s | Waits for Redpanda consumer join |
| `dashboard` | 6 × 10s = 60s | 20s | 10s | No heavy startup dep |
| `query_api` | 6 × 10s = 60s | 20s | 10s | DB pool created in lifespan |

All probes use `httpGet` on the named `http` port — no exec, no tools in container.

```yaml
startupProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 30     # × periodSeconds = max startup window
  timeoutSeconds: 5
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 0   # startupProbe guards the window
  periodSeconds: 20
  timeoutSeconds: 5
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /readyz
    port: http
  initialDelaySeconds: 0
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

Note: once `startupProbe` passes, `livenessProbe` takes over. Set `initialDelaySeconds: 0`
on liveness because `startupProbe` already guards the cold-boot window.

#### Resource Budgets

Conservative starting values — tune after measuring with `kubectl top pod`:

| Service | CPU request | CPU limit | Memory request | Memory limit |
|---|---|---|---|---|
| `ingestor` | 100m | 500m | 256Mi | 512Mi |
| `ai_gateway` | 500m | 2000m | 1Gi | 2Gi |
| `processor` | 100m | 500m | 256Mi | 512Mi |
| `dashboard` | 50m | 200m | 128Mi | 256Mi |
| `query_api` | 100m | 500m | 256Mi | 512Mi |

`ai_gateway` is high because sentence-transformers loads a 400 MB model into memory.
Adjust limits downward after profiling — these are safe starting ceilings.

#### Security Context (all services)

All containers run non-root (`runAsUser: 1001`, `runAsGroup: 1001`, `runAsNonRoot: true`),
drop all capabilities, and set `allowPrivilegeEscalation: false`. `readOnlyRootFilesystem`
is `false` for now — some services write temp files to `/tmp`; add `emptyDir` volume mounts
and set to `true` in Phase 13 after auditing each service's filesystem writes.

#### Processor Replicas

`replicas: 1` is mandatory. A Kafka consumer group with partition-count = 1 can only
have one active consumer. Adding replicas would cause consumer group rebalancing churn.
Document in the Deployment with an annotation:

```yaml
annotations:
  data-zoo/replica-constraint: "single-consumer; scale by increasing topic partitions first"
```

#### Kustomize Overlay Strategy

The existing `overlays/local/` only patches `ingestor` and `query-api`. Phase 12 extends
it to include all 5 services. The overlay structure:

```
infra/kubernetes/
  manifests/
    ingestor/           (exists)
    query-api/          (exists)
    ai-gateway/         (create)
    processor/          (create)
    dashboard/          (create)
  overlays/
    local/
      kustomization.yaml  (update — add 3 new services)
      ingress.yaml        (update — add routes for new services)
      ai-gateway-deployment.yaml  (create — image tag patch)
      processor-deployment.yaml   (create — image tag patch)
      dashboard-deployment.yaml   (create — image tag patch)
```

---

### Steps

**Phase 12.0: Verify and align existing manifests**

1. Read `infra/kubernetes/manifests/query-api/deployment.yaml` — verify `livenessProbe`,
   `readinessProbe`, resource requests/limits, and securityContext match the standards
   above; update if stale
2. Add `startupProbe` to `infra/kubernetes/manifests/ingestor/deployment.yaml` (currently
   missing) — use `failureThreshold: 6`, `periodSeconds: 10`, `httpGet: /health`
3. Add `startupProbe` to `infra/kubernetes/manifests/query-api/deployment.yaml`

**Phase 12.1: Create `ai_gateway` manifests**

4. Create `infra/kubernetes/manifests/ai-gateway/deployment.yaml`:
   - `containerPort: 8001`, named `http`
   - `startupProbe`: `failureThreshold: 30`, `periodSeconds: 10` (300s window for model load)
   - `livenessProbe`: `/health`, `periodSeconds: 30`
   - `readinessProbe`: `/readyz` (Qdrant health check), `periodSeconds: 15`
   - Resources: CPU 500m/2000m, Memory 1Gi/2Gi
   - Env: `QDRANT_URL` from Secret; `LOG_LEVEL` from ConfigMap
   - SecurityContext: non-root, drop ALL, `allowPrivilegeEscalation: false`
5. Create `infra/kubernetes/manifests/ai-gateway/service.yaml` — `ClusterIP`, port 8001

**Phase 12.2: Create `processor` manifests**

6. Create `infra/kubernetes/manifests/processor/deployment.yaml`:
   - `replicas: 1` with annotation `data-zoo/replica-constraint`
   - `containerPort: 8002`, named `http`
   - `startupProbe`: `failureThreshold: 18`, `periodSeconds: 10` (180s for Redpanda join)
   - `livenessProbe`: `/health`, `periodSeconds: 30`
   - `readinessProbe`: `/readyz` (consumer task alive), `periodSeconds: 15`
   - Resources: CPU 100m/500m, Memory 256Mi/512Mi
   - Env: `KAFKA_BOOTSTRAP_SERVERS` from Secret; `KAFKA_TOPIC` from ConfigMap
   - SecurityContext: non-root, drop ALL
7. Create `infra/kubernetes/manifests/processor/service.yaml` — `ClusterIP`, port 8002
   (internal only — processor has no public-facing routes)

**Phase 12.3: Create `dashboard` manifests**

8. Create `infra/kubernetes/manifests/dashboard/deployment.yaml`:
   - `containerPort: 8003`, named `http`
   - `startupProbe`: `failureThreshold: 6`, `periodSeconds: 10`
   - `livenessProbe`: `/health`, `periodSeconds: 20`
   - `readinessProbe`: `/readyz` (ingestor probe), `periodSeconds: 10`
   - Resources: CPU 50m/200m, Memory 128Mi/256Mi
   - Env: `INGESTOR_URL` from ConfigMap
   - SecurityContext: non-root, drop ALL
9. Create `infra/kubernetes/manifests/dashboard/service.yaml` — `ClusterIP`, port 8003

**Phase 12.4: NetworkPolicy**

10. Create `infra/kubernetes/manifests/network-policies.yaml` — default deny-all ingress
    for the `data-zoo` namespace, then explicit allow rules:
    - `ingestor`: allow ingress from `ingress-nginx` namespace only
    - `ai_gateway`: allow ingress from `ingestor` pod label only
    - `processor`: no ingress (consumer only); allow egress to Redpanda + ingestor
    - `dashboard`: allow ingress from `ingress-nginx` namespace only
    - `query_api`: allow ingress from `ingress-nginx` namespace only

**Phase 12.5: Update `overlays/local/`**

11. Update `infra/kubernetes/overlays/local/kustomization.yaml` — add resources:
    `../../manifests/ai-gateway`, `../../manifests/processor`, `../../manifests/dashboard`,
    `../../manifests/network-policies.yaml`
12. Create overlay patches for `ai-gateway`, `processor`, `dashboard` — image tag set to
    `latest` for local k3d (same pattern as existing `ingestor-deployment.yaml` overlay)
13. Update `infra/kubernetes/overlays/local/ingress.yaml` — add routing rules:
    - `ai-gateway.127.0.0.1.nip.io:8080` → `ai-gateway` service port 8001
    - `dashboard.127.0.0.1.nip.io:8080` → `dashboard` service port 8003
    - `query-api.127.0.0.1.nip.io:8080` → `query-api` service port 8005
    (processor has no ingress route — internal only)
14. Update `infra/kubernetes/README.md` — add all 5 services to local apply commands and
    ingress host table

**Phase 12.6: Helm chart scaffolding**

15. Create `infra/kubernetes/charts/ai-gateway/` — scaffold from existing `charts/ingestor/`
    pattern: `Chart.yaml`, `values.yaml` (image repo, tag, port 8001, resource defaults),
    `templates/deployment.yaml`, `templates/service.yaml`
16. Create `infra/kubernetes/charts/processor/` — same pattern; `values.yaml` includes
    `replicas: 1` as default with comment warning against scaling
17. Create `infra/kubernetes/charts/dashboard/` — same pattern; port 8003

---

### Relevant Files

- `infra/kubernetes/manifests/ingestor/deployment.yaml` — add `startupProbe`
- `infra/kubernetes/manifests/query-api/deployment.yaml` — verify + add `startupProbe`
- `infra/kubernetes/manifests/ai-gateway/` — create (deployment + service)
- `infra/kubernetes/manifests/processor/` — create (deployment + service)
- `infra/kubernetes/manifests/dashboard/` — create (deployment + service)
- `infra/kubernetes/manifests/network-policies.yaml` — create
- `infra/kubernetes/overlays/local/kustomization.yaml` — add 3 new services + network policies
- `infra/kubernetes/overlays/local/ingress.yaml` — add 3 new routes
- `infra/kubernetes/overlays/local/ai-gateway-deployment.yaml` — create (image patch)
- `infra/kubernetes/overlays/local/processor-deployment.yaml` — create (image patch)
- `infra/kubernetes/overlays/local/dashboard-deployment.yaml` — create (image patch)
- `infra/kubernetes/charts/ai-gateway/` — create
- `infra/kubernetes/charts/processor/` — create
- `infra/kubernetes/charts/dashboard/` — create
- `infra/kubernetes/README.md` — update with all 5 services

---

### Verification

```bash
# Prerequisite: k3d cluster running
kubectl config use-context k3d-data-zoo
kubectl create namespace data-zoo --dry-run=client -o yaml | kubectl apply -f -

# Apply full overlay (all 5 services)
kubectl apply -k infra/kubernetes/overlays/local
kubectl -n data-zoo rollout status deployment/ingestor
kubectl -n data-zoo rollout status deployment/ai-gateway
kubectl -n data-zoo rollout status deployment/processor
kubectl -n data-zoo rollout status deployment/dashboard
kubectl -n data-zoo rollout status deployment/query-api

# All deployments available
kubectl -n data-zoo get deployments

# All pods healthy — startupProbe passes before liveness kicks in
kubectl -n data-zoo get pods

# Probe verification per service
for host in ingestor ai-gateway dashboard query-api; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://$host.127.0.0.1.nip.io:8080/readyz")
  echo "$host readyz: $code"
done
# processor has no ingress — probe via port-forward
kubectl -n data-zoo port-forward deployment/processor 8002:8002 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/readyz

# NetworkPolicy: verify processor cannot be reached from dashboard
kubectl -n data-zoo exec deploy/dashboard -- \
  python3 -c "import urllib.request; urllib.request.urlopen('http://processor:8002/health', timeout=3)"
# Expected: connection refused / timeout (NetworkPolicy blocks it)

# Non-root verification
kubectl -n data-zoo exec deploy/ai-gateway -- id
# Expected: uid=1001(appuser) gid=1001(appgroup)

# Resource sanity
kubectl -n data-zoo top pods
```

---

### Decisions

- **`startupProbe` everywhere**: Prevents flapping during cold boot without relaxing liveness
  thresholds; `ai_gateway` needs up to 300s for sentence-transformers — unachievable with
  `initialDelaySeconds` on liveness alone
- **`processor` replicas: 1**: Kafka consumer group with 1 partition = 1 active consumer;
  scaling requires increasing topic partitions first — documented as annotation
- **`readOnlyRootFilesystem: false` for now**: Auditing each service's tmpfs usage deferred
  to Phase 13; keeping it false is safe but not hardened; Phase 13 adds `emptyDir` mounts
- **NetworkPolicy default-deny**: Closes lateral movement risk; services that need no ingress
  (processor) get zero ingress rules; reduces blast radius of a compromised container
- **Kustomize for local, Helm for prod**: Local overlay is simple (image tag patch only);
  Helm charts carry values for prod-specific resource overrides and secret injection

---

### Out of Scope

- Horizontal Pod Autoscaler (HPA) — requires load testing baselines first (Phase 14)
- Vertical Pod Autoscaler (VPA) — depends on production metrics history
- Istio / Linkerd service mesh (mTLS, traffic policies) — Phase 15
- Terraform ECS task definition update for processor port 8002 (Phase 13)
- `readOnlyRootFilesystem: true` hardening — deferred to Phase 13 after tmpfs audit
