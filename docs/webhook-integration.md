# Webhook Integration Guide

This guide explains how to configure and integrate with the webhook gateway service.

## Overview

The webhook gateway receives inbound HTTP webhooks from external sources (Stripe, Segment, Zapier,
or any custom sender), validates HMAC-SHA256 signatures, deduplicates events, and publishes them
to a Kafka topic for downstream processing.

```
External source
    │
    │  POST /api/v1/webhooks/{source}
    ▼
Webhook Gateway (port 8004)
    ├─► Signature validation (HMAC-SHA256)
    ├─► Idempotency check (delivery_id dedup)
    ├─► Audit log → PostgreSQL (webhook_events)
    └─► Publish → Kafka (webhook.events.{source})
```

## Quick Start

### Prerequisites

- Webhook service running on port 8004
- Source registered in the `webhook_sources` table (via admin API)
- Signing key configured as an environment variable

### Register a Source

```bash
curl -X POST http://localhost:8004/api/v1/admin/sources \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "description": "My application webhooks",
    "signing_algorithm": "hmac-sha256",
    "rate_limit_per_minute": 60
  }'
```

### Configure a Signing Key

Set the environment variable before starting the service:

```bash
export WEBHOOK_SIGNING_KEY_MY_APP="your-shared-secret-here"
```

The variable name follows the pattern `WEBHOOK_SIGNING_KEY_{SOURCE_UPPER}` where hyphens in the
source name are replaced with underscores.

| Source name | Environment variable |
|-------------|---------------------|
| `stripe` | `WEBHOOK_SIGNING_KEY_STRIPE` |
| `my-app` | `WEBHOOK_SIGNING_KEY_MY_APP` |
| `segment-prod` | `WEBHOOK_SIGNING_KEY_SEGMENT_PROD` |

### Send a Webhook

```bash
BODY='{"event":"payment.completed","amount":9999}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SIGNING_KEY_MY_APP" | awk '{print $2}')

curl -X POST http://localhost:8004/api/v1/webhooks/my-app \
  -H "Content-Type: application/json" \
  -H "X-Delivery-Id: $(uuidgen)" \
  -H "X-Webhook-Signature: $SIG" \
  -d "$BODY"
```

## Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Delivery-Id` | Recommended | UUID for idempotency. Auto-generated if missing. |
| `X-Webhook-Signature` | Recommended | HMAC-SHA256 hex digest of the raw request body. |
| `X-Timestamp` | Optional | Epoch timestamp of the event (informational, not validated). |
| `Content-Type` | Required | Must be `application/json`. |

### Signature Format

Two formats are accepted:

Plain hex:

```text
X-Webhook-Signature: 3b4c...f1a2
```

Stripe-compatible (timestamp prefix, `v1=` prefix):

```text
X-Stripe-Signature: t=1614556800,v1=3b4c...f1a2
```

## Response Codes

| Status | Meaning |
|--------|---------|
| `202 Accepted` | Event queued successfully. |
| `400 Bad Request` | Malformed JSON body. |
| `401 Unauthorized` | Invalid or missing HMAC signature (when key is configured). |
| `409 Conflict` | Duplicate `X-Delivery-Id` — event already processed. |
| `413 Payload Too Large` | Body exceeds 10 MB. |
| `503 Service Unavailable` | Source is not registered or inactive. |

### 202 Response Body

```json
{
  "status": "accepted",
  "event_id": 42,
  "delivery_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "my-app"
}
```

## Signing Key Resolution

Keys are resolved in this priority order:

1. In-memory cache (5-minute TTL)
2. Environment variable `WEBHOOK_SIGNING_KEY_{SOURCE_UPPER}`
3. AWS Secrets Manager secret `data-zoo/webhook/{source}/signing-key`
4. `WEBHOOK_SIGNING_KEY_DEFAULT` (dev fallback — not for production)

## Admin API

All admin endpoints require `Authorization: Bearer $ADMIN_TOKEN`.

### List Sources

```bash
curl http://localhost:8004/api/v1/admin/sources \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Update a Source

```bash
curl -X PATCH http://localhost:8004/api/v1/admin/sources/my-app \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

### Query Events

```bash
curl "http://localhost:8004/api/v1/admin/webhooks/events?source=my-app&limit=20" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Replay Events

Mark events for replay (the daemon re-publishes them to Kafka within 5 minutes):

```bash
curl -X POST http://localhost:8004/api/v1/admin/webhooks/replay \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_ids": [101, 102, 103]}'
```

## Health Endpoints

```bash
# Liveness — always 200 if process is alive
curl http://localhost:8004/health

# Readiness — 200 if Postgres + Kafka are reachable, 503 otherwise
curl http://localhost:8004/readyz
```
