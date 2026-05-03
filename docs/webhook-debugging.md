# Webhook Debugging Guide

This guide covers common failure modes and how to diagnose and resolve them.

## Query the Audit Log

Every inbound webhook attempt is stored in the `webhook_events` table regardless of outcome.

```sql
-- Recent events for a source
SELECT id, delivery_id, status, created_at, error_detail
FROM webhook_events
WHERE source = 'my-app'
ORDER BY created_at DESC
LIMIT 20;

-- Failed events in the last hour
SELECT id, delivery_id, source, status, error_detail, created_at
FROM webhook_events
WHERE status IN ('failed', 'signature_invalid')
  AND created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;

-- Duplicate delivery IDs
SELECT delivery_id, COUNT(*) AS hits
FROM webhook_events
WHERE source = 'my-app'
GROUP BY delivery_id
HAVING COUNT(*) > 1;
```

Via admin API (no Postgres client needed):

```bash
curl "http://localhost:8004/api/v1/admin/webhooks/events?source=my-app&status=failed" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Common Failures

### Signature Mismatch (401)

Causes:

- Wrong signing key configured in the environment variable
- Sender is signing a modified payload (e.g., pretty-printed JSON vs compact)
- Sender using a different algorithm (MD5 vs SHA-256)

Diagnosis:

```bash
# 1. Verify which key is loaded for the source
echo $WEBHOOK_SIGNING_KEY_MY_APP

# 2. Manually compute expected HMAC from the raw body
BODY='{"event":"test"}'
echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SIGNING_KEY_MY_APP"

# 3. Compare with the X-Webhook-Signature header value in the logs
```

Resolution:

- Rotate the key on both sides simultaneously (see [Key Rotation](#key-rotation))
- Confirm sender uses the raw request body bytes, not a re-serialised copy

### Source Not Found (503)

The source name in the URL does not match any active row in `webhook_sources`.

```bash
# Check registered sources
curl http://localhost:8004/api/v1/admin/sources \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Register the missing source
curl -X POST http://localhost:8004/api/v1/admin/sources \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app", "description": "...", "signing_algorithm": "hmac-sha256"}'
```

### Duplicate Events (409)

The same `X-Delivery-Id` was received twice. This is expected if the sender retries on timeout.

The event was already processed — the 409 is the idempotency guard working correctly.
No action needed unless the first delivery failed (check the `status` column).

If the first delivery failed and you need to retry:

```bash
# Find the event_id
curl "http://localhost:8004/api/v1/admin/webhooks/events?source=my-app&delivery_id=..." \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Mark for replay
curl -X POST http://localhost:8004/api/v1/admin/webhooks/replay \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_ids": [<event_id>]}'
```

### Payload Too Large (413)

The body exceeds 10 MB. Ask the sender to paginate or compress the payload.

## Replay Workflow

Events can be replayed when downstream processing failed after ingestion.

```
webhook_events.status = 'replay_queued'
           │
           │  (daemon polls every 5 minutes)
           ▼
replay_daemon.py → Kafka topic webhook.events.{source}
           │
           └─► status updated to 'replayed'
```

Steps:

1. Identify the failed event IDs from the audit log.
2. Mark them for replay via the admin API.
3. The daemon picks them up within 5 minutes and re-publishes to Kafka.
4. Verify the status changed to `replayed`.

```bash
# Step 2: Mark for replay
curl -X POST http://localhost:8004/api/v1/admin/webhooks/replay \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_ids": [101, 102]}'

# Step 4: Verify
curl "http://localhost:8004/api/v1/admin/webhooks/events?source=my-app" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.[] | select(.id == 101) | .status'
```

## Key Rotation

To rotate a signing key without dropping events:

1. Add the new key to AWS Secrets Manager (or update the env var in staging).
2. Coordinate with the sender to switch to the new key at an agreed cutover time.
3. Update `WEBHOOK_SIGNING_KEY_{SOURCE_UPPER}` (or the Secrets Manager secret).
4. Restart the webhook service (or wait up to 5 minutes for the cache to expire).
5. Verify new signatures are accepted via the `/readyz` endpoint and a test delivery.

> **Note**: There is no dual-key validation period currently. Plan a brief maintenance window
> or accept a small number of 401s during the cutover if the sender transitions gradually.

## Kafka Topic Verification

```bash
# List topics (Redpanda / Kafka CLI)
rpk topic list | grep webhook

# Consume events from the topic
rpk topic consume webhook.events.my-app --num 5

# Check consumer lag
rpk group describe <consumer-group>
```

## Log Correlation

Every request includes structured JSON logs. Use the delivery ID to correlate:

```bash
# Find all log lines for a delivery
grep '"delivery_id": "550e8400"' logs/webhook.log | jq .

# Check signature validation outcome
grep '"source": "my-app"' logs/webhook.log | grep "signature" | jq '{ts: .timestamp, event: .event, source: .source}'
```

## Service Health

```bash
# Liveness
curl -s http://localhost:8004/health | jq .

# Readiness (checks Postgres + Kafka)
curl -sv http://localhost:8004/readyz 2>&1 | grep -E "< HTTP|status|detail"
```

A 503 from `/readyz` indicates either Postgres or Kafka is unreachable. Check Docker Compose
service status and broker connectivity.
