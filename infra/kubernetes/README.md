# Kubernetes Local Deploy Scaffolding

This directory provides Kubernetes deployment assets for all 5 data-zoo services.

## Included

- Static manifests:
  - `infra/kubernetes/manifests/ingestor/`
  - `infra/kubernetes/manifests/query-api/`
  - `infra/kubernetes/manifests/ai-gateway/`
  - `infra/kubernetes/manifests/processor/`
  - `infra/kubernetes/manifests/dashboard/`
  - `infra/kubernetes/manifests/network-policies/`
- Helm charts:
  - `infra/kubernetes/charts/ingestor/`
  - `infra/kubernetes/charts/query-api/`
  - `infra/kubernetes/charts/ai-gateway/`
  - `infra/kubernetes/charts/processor/`
  - `infra/kubernetes/charts/dashboard/`
- Local kustomize overlay with ingress wiring:
  - `infra/kubernetes/overlays/local/`

## Local k3d Apply (manifests + overlay)

```bash
kubectl config use-context k3d-data-zoo
kubectl create namespace data-zoo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n data-zoo -f infra/kubernetes/overlays/local/secret.example.yaml
kubectl apply -k infra/kubernetes/overlays/local
```

Verify all deployments are available:

```bash
kubectl -n data-zoo rollout status deployment/ingestor
kubectl -n data-zoo rollout status deployment/ai-gateway
kubectl -n data-zoo rollout status deployment/processor
kubectl -n data-zoo rollout status deployment/dashboard
kubectl -n data-zoo rollout status deployment/query-api
kubectl -n data-zoo get deployments
kubectl -n data-zoo get pods
```

Ingress host routing:

| Host | Port | Service |
|------|------|---------|
| `ingestor.127.0.0.1.nip.io` | 8080 | ingestor:8000 |
| `query-api.127.0.0.1.nip.io` | 8080 | query-api:8005 |
| `ai-gateway.127.0.0.1.nip.io` | 8080 | ai-gateway:8001 |
| `dashboard.127.0.0.1.nip.io` | 8080 | dashboard:8003 |

`processor` has no ingress route — internal consumer only. Use port-forward to probe:

```bash
kubectl -n data-zoo port-forward deployment/processor 8002:8002 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/readyz
```

## Helm Install (alternative)

```bash
kubectl create namespace data-zoo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n data-zoo -f infra/kubernetes/overlays/local/secret.example.yaml

helm upgrade --install ingestor infra/kubernetes/charts/ingestor \
  -n data-zoo \
  --set image.repository=data-zoo/ingestor \
  --set image.tag=latest

helm upgrade --install query-api infra/kubernetes/charts/query-api \
  -n data-zoo \
  --set image.repository=data-zoo/query_api \
  --set image.tag=latest

helm upgrade --install ai-gateway infra/kubernetes/charts/ai-gateway \
  -n data-zoo \
  --set image.repository=data-zoo/ai_gateway \
  --set image.tag=latest

helm upgrade --install processor infra/kubernetes/charts/processor \
  -n data-zoo \
  --set image.repository=data-zoo/processor \
  --set image.tag=latest

helm upgrade --install dashboard infra/kubernetes/charts/dashboard \
  -n data-zoo \
  --set image.repository=data-zoo/dashboard \
  --set image.tag=latest

kubectl apply -n data-zoo -f infra/kubernetes/overlays/local/ingress.yaml
```

## Probe Strategy

All services use `startupProbe` + `livenessProbe` + `readinessProbe` via `httpGet` on the
named `http` port. `initialDelaySeconds: 0` on liveness and readiness — `startupProbe`
guards the cold-boot window.

| Service | Startup window | Liveness period | Readiness period | Notes |
|---------|---------------|-----------------|------------------|-------|
| ingestor | 60s (6×10s) | 20s | 10s | Fast startup |
| query-api | 60s (6×10s) | 20s | 10s | DB pool in lifespan |
| ai-gateway | 300s (30×10s) | 30s | 15s | sentence-transformers load |
| processor | 180s (18×10s) | 30s | 15s | Redpanda consumer join |
| dashboard | 60s (6×10s) | 20s | 10s | No heavy dep |

## NetworkPolicy

`manifests/network-policies/` contains individual NetworkPolicy manifests that apply a default-deny-all-ingress policy for the
`data-zoo` namespace with explicit allow rules:

- `ingestor`, `query-api`, `dashboard` — accept ingress from `ingress-nginx` namespace only
- `ai-gateway` — accept ingress from `ingestor` pods only
- `processor` — zero ingress; egress restricted to Redpanda (9092), ingestor (8000), and DNS
