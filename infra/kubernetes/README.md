# Kubernetes Local Deploy Scaffolding

This directory provides Kubernetes deployment assets for `ingestor` and `query_api`.

## Included

- Static manifests:
  - `infra/kubernetes/manifests/ingestor/`
  - `infra/kubernetes/manifests/query-api/`
- Helm charts:
  - `infra/kubernetes/charts/ingestor/`
  - `infra/kubernetes/charts/query-api/`
- Local kustomize overlay with ingress wiring:
  - `infra/kubernetes/overlays/local/`

## Local k3d Apply (manifests + overlay)

```bash
kubectl config use-context k3d-data-zoo
kubectl create namespace data-zoo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n data-zoo -f infra/kubernetes/overlays/local/secret.example.yaml
kubectl apply -k infra/kubernetes/overlays/local
```

Ingress host routing:

- `http://ingestor.127.0.0.1.nip.io:8080/health`
- `http://query-api.127.0.0.1.nip.io:8080/health`

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

kubectl apply -n data-zoo -f infra/kubernetes/overlays/local/ingress.yaml
```
