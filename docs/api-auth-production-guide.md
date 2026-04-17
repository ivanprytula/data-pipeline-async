# API Authentication — Production Hardening Guide

## Overview

This project implements three authentication mechanisms for learning and demonstration:

1. **v1 API**: Bearer tokens + session-based (cookie)
2. **v2 API**: JWT tokens (stateless)
3. **Docs API**: HTTP Basic Auth (already deployed)

This guide covers production-grade security hardening, load testing, and operational considerations.

---

## Layer 1: HTTP Basic Auth (Documentation)

### Current Implementation

- Credentials: `docs_username` / `docs_password` (from `.env`)
- Protected endpoints: `/docs`, `/redoc`, `/openapi.json`
- Mechanism: HTTP Basic Auth header with base64-encoded credentials

### Production Hardening

#### SSL/TLS Enforcement

```text
✗ NEVER send Basic Auth over HTTP
✓ Always use HTTPS with TLS 1.3+
```

#### Credential Strategy

```text
Development  → Shared test credentials (docs_username=admin, docs_password=admin)
Production   → Rotate credentials quarterly
             → Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
             → Alert on failed auth attempts (3+ in 5 minutes)
```

#### Reverse Proxy

```text
Place API behind nginx or ALB:
- Rate limit docs endpoints separately (e.g., 1 req/sec per IP)
- Log all auth attempts (success + failure)
- Force HTTPS redirect
- Add CSP, HSTS, X-Content-Type-Options headers
```

#### Audit Trail

```python
# Log successful + failed attempts
logger.info("docs_auth_success", extra={"user": username, "ip": client_ip})
logger.warning("docs_auth_failure", extra={"attempt": username, "ip": client_ip})
```

---

## Layer 2: Bearer Token (v1 API, Stateless)

### Current Implementation

- Token: Static `API_V1_BEARER_TOKEN` from `.env`
- Pattern: `Authorization: Bearer <token>`
- Validation: Exact string match (no expiry, no rotation)

### Production Hardening

#### Key Rotation Strategy

```text
Problem: Static bearer token never expires → leaked token = permanent breach

Solution 1: Key Versioning (AWS-style)
  - Maintain N active keys (e.g., current + 1 old)
  - Every 30 days, generate new key, promote to "current"
  - Old key → grace period (7 days) before deactivation
  - Clients update their config within grace period

Solution 2: API Key Service
  - Issue time-limited API keys (similar to JWT but with server lookup)
  - Keys stored in database with: issue_time, expiry, last_used, revoked_at
  - On each request: lookup key in cache (Redis) or database
  - Supports instant revocation without client update
```

#### Implementation Example: Key Versioning

```python
# app/config.py
API_V1_BEARER_TOKEN: str              # Current key
API_V1_BEARER_TOKEN_OLD: str | None   # Grace-period key (can be None)
TOKEN_ROTATION_DAYS: int = 30
TOKEN_GRACE_PERIOD_DAYS: int = 7

# app/auth.py
async def verify_bearer_token(authorization: str | None = Header(None)) -> bool:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid scheme")

    # Accept current or grace-period key
    is_current = credentials == settings.api_v1_bearer_token
    is_grace = (settings.api_v1_bearer_token_old and
                credentials == settings.api_v1_bearer_token_old)

    if is_current:
        logger.info("bearer_token_valid", extra={"version": "current"})
        return True
    elif is_grace:
        logger.warning("bearer_token_grace_period", extra={"days_left": 7})
        return True
    else:
        raise HTTPException(status_code=401, detail="Invalid token")
```

#### Rate Limit Per Client

```python
# Map bearer token to client_id instead of IP
# This prevents one malicious IP from blocking legitimate clients

async def get_rate_limit_key(authorization: str | None = Header(None)) -> str:
    """Return client_id from bearer token (first 8 chars as identifier)."""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            return f"client_{token[:8]}"  # Anonymized client ID
    return f"ip_{request.client.host}"    # Fallback to IP

# In rate limiter:
allowed = await limiter.consume(rate_limit_key)
```

#### Token Format Best Practices

```text
❌ BAD:   bearer_token_12345
✓ GOOD:  sk_prod_v1_abc1234567890... (type + env + version + random)

Benefits:
- Type prefix: sk_ = secret key, pk_ = public key, jwt_ = JWT family
- Environment: prod, staging, dev
- Version: v1, v2 (supports deprecation)
- Random suffix: >32 chars, URL-safe base64
```

---

## Layer 3: Session-Based Auth (v1 API, Stateful)

### Current Implementation

- Storage: In-memory Python dict (`_session_store`)
- Expiry: Configurable via `TOKEN_EXPIRY_HOURS` (default: 24h)
- Cookie: `session_id` (HttpOnly flag recommended)

### Production Hardening

#### Session Store: Migrate to Redis

```python
# app/database.py — Replace in-memory dict
import redis.asyncio as redis
from datetime import datetime, timedelta

_session_store: redis.AsyncRedis | None = None

async def init_session_store():
    global _session_store
    _session_store = await redis.from_url("redis://localhost:6379")
    await _session_store.ping()

async def create_session(user_id: str, metadata: dict) -> tuple[str, str]:
    """Create session in Redis with TTL expiry."""
    session_id = secrets.token_urlsafe(32)
    session_data = {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **metadata
    }
    ttl = timedelta(hours=settings.token_expiry_hours)
    await _session_store.setex(
        f"session:{session_id}",
        ttl,
        json.dumps(session_data)
    )
    return session_id, f"session_id={session_id}; HttpOnly; Secure; SameSite=Strict"

async def verify_session(session_id: str | None = Cookie(None)) -> dict[str, Any]:
    """Validate session from Redis."""
    if not session_id:
        raise HTTPException(status_code=401, detail="Missing session cookie")

    data = await _session_store.get(f"session:{session_id}")
    if not data:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return json.loads(data)
```

#### Cookie Security Flags

```python
# FastAPI response to set session cookie
response.set_cookie(
    key="session_id",
    value=session_id,
    max_age=86400,                    # 24 hours
    httponly=True,                    # Prevents JS access (XSS protection)
    secure=True,                      # HTTPS only
    samesite="strict",                # CSRF protection
    domain="api.example.com",         # Restrict to domain
)
```

#### Session Invalidation (Logout)

```python
@router.post("/auth/logout")
async def logout_session(session_id: str | None = Cookie(None)) -> dict[str, str]:
    """Explicitly invalidate session."""
    if session_id:
        await _session_store.delete(f"session:{session_id}")
        logger.info("logout_success", extra={"session_id": session_id[:8]})

    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("session_id")
    return response
```

#### Distributed Session State

```text
Issue: In multi-instance deployments, server A creates session,
       request routed to server B → session not found

Solution: Redis as central session store
  - All instances read/write to same Redis cluster
  - Session data persists across server restarts
  - TTL handled by Redis automatically
  - Supports session affinity or any routing policy

Production checklist:
  ✓ Redis cluster with replication (master + N replicas)
  ✓ Automatic failover (Redis Sentinel or Kubernetes StatefulSet)
  ✓ RDB + AOF persistence
  ✓ Max session count limit (e.g., 1M sessions = ~50GB RAM)
```

---

## Layer 4: JWT Auth (v2 API, Stateless)

### Current Implementation

- Algorithm: HS256 (symmetric: server knows secret)
- Secret: `JWT_SECRET` from `.env` (dev default: unsafe, must set in production)
- Claims: `sub` (user ID), `exp` (expiry), `iat` (issued at), `iss` (issuer)
- Expiry: `JWT_EXPIRY_MINUTES` (default: 60)

### Production Hardening

#### Secret Key Management

```text
❌ Development:
   JWT_SECRET="dev-secret-123"  (weak, shared in repo)

✓ Production:
   JWT_SECRET="<256-bit random key>"  (≥32 bytes, from secrets manager)
```

#### Generating Strong Secret

```bash
# Generate 256-bit random key (base64-encoded)
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: "Drmhze6EPcv0fN_81Bj-nA"  (≥32 chars)

# Or use OpenSSL
openssl rand -base64 32
```

#### Algorithm Choice: HS256 vs RS256

| Aspect | HS256 | RS256 |
| -------- | ------- | ------- |
| Secret Sharing | Single secret (all servers) | Public key (distributed) |
| Key Rotation | Harder (all servers need update atomically) | Easier (new key endpoint) |
| Revocation | No built-in (use token blacklist or short TTL) | Key can be revoked immediately |
| Performance | Faster | Slower (RSA operations) |
| **Use Case** | Monolith, internal tokens | Multi-service, public tokens |

#### Recommendation for Multi-Service

```python
# Use RS256 with JWKS (JSON Web Key Set) endpoint
# - Issuer publishes /jwks.json with public keys
# - Consumers fetch + cache the public keys
# - Issuer can rotate private key without coordinating consumers

# Setup:
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key = private_key.public_key()

# Use in auth:
token = jwt.encode(payload, private_key, algorithm="RS256")
jwt.decode(token, public_key, algorithms=["RS256"])
```

#### Token Structure Best Practices

```python
def create_jwt_token(user_id: str, scopes: list[str]) -> str:
    """Create JWT with essential claims + audit trail."""
    now = datetime.now(timezone.utc)
    jti = str(uuid4())  # JWT ID for tracking/revocation

    payload = {
        "jti": jti,                                  # Unique token ID
        "sub": user_id,                              # Subject (who)
        "aud": "api.example.com",                   # Audience (who can use this)
        "iss": "https://auth.example.com",          # Issuer
        "iat": int(now.timestamp()),                # Issued at
        "exp": int((now + timedelta(hours=1)).timestamp()),  # Expiry (1 hour)
        "nbf": int(now.timestamp()),                # Not before
        "scope": " ".join(scopes),                  # Permissions
        "ip": request.client.host,                  # Context: request IP
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
```

#### Token Blacklist for Logout

```python
# Problem: JWT has no server state; once issued, can't revoke until expiry

# Solution 1: Short TTL (5-15 min) + Refresh Tokens
#   Access token: 5 min (TTL, no lookup needed)
#   Refresh token: 7 days (check Redis blacklist on each use)
@router.post("/auth/refresh")
async def refresh_token(refresh_token: str) -> dict[str, str]:
    # Check if refresh token is blacklisted
    is_blacklisted = await redis.get(f"blacklist:{refresh_token}")
    if is_blacklisted:
        raise HTTPException(status_code=401, detail="Token revoked")

    # Issue new access token
    new_access = create_jwt_token(user_id)
    return {"access_token": new_access, "token_type": "bearer"}

@router.post("/auth/logout")
async def logout(token: str = Depends(verify_jwt_token)) -> dict[str, str]:
    jti = token.get("jti")
    # Blacklist the refresh token (if provided)
    await redis.setex(f"blacklist:{jti}", timedelta(days=7), "1")
    logger.info("logout_token_blacklisted", extra={"jti": jti[:8]})
    return {"message": "Logged out"}

# Solution 2: Validate JTI + expiry in cache
#   On each request, check `jti` in Redis (fast lookup)
#   If not found = already logged out
```

#### Key Rotation

```python
# Store multiple keys with timestamps
# Verify with all active keys (current + grace period)

class JWTKeyManager:
    """Manages JWT key rotation."""

    def __init__(self):
        self.current_kid = "2024-01-15"
        self.keys = {
            "2024-01-15": {"secret": settings.jwt_secret, "status": "current"},
            "2024-01-08": {"secret": "...", "status": "grace_period"},  # Can still verify
        }

    def encode(self, claims: dict) -> str:
        """Sign with current key, include kid (key ID) in header."""
        return jwt.encode(
            claims,
            self.keys[self.current_kid]["secret"],
            algorithm="HS256",
            headers={"kid": self.current_kid}
        )

    def decode(self, token: str) -> dict:
        """Verify with current or grace-period keys."""
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        if kid not in self.keys:
            raise HTTPException(status_code=401, detail="Unknown key version")

        key_data = self.keys[kid]
        if key_data["status"] == "expired":
            raise HTTPException(status_code=401, detail="Key expired")

        return jwt.decode(token, key_data["secret"], algorithms=["HS256"])
```

---

## Cross-Layer Security Practices

### Password / Secret Entropy

```text
Minimum entropy (NIST SP 800-63B):
- Manual passwords: 64 bits (16+ random characters)
- API tokens: 128+ bits (2^128 possible values)
- Cryptographic keys: 256+ bits

If using string keys: len ≥ 32 characters (base64) = ~192 bits
```

### Rate Limiting + Auth

```python
from app.rate_limiting import Limiter

# Rate limit per (auth_type, user_id) not per IP
# This prevents legitimate users from getting blocked by traffic spikes

async def get_limiter_key(claims: dict | None = Depends(verify_jwt_token)) -> str:
    if claims:
        return f"user:{claims['sub']}"  # JWT-authenticated user
    return f"anon:{request.client.host}"  # Anonymous/IP-based

limiter = Limiter(key_func=get_limiter_key)

@app.post("/records", dependencies=[Depends(limiter.limit("100/minute"))])
async def create_record(...): ...
```

### CORS + Auth

```python
from fastapi.middleware.cors import CORSMiddleware

# Only allow authenticated requests from known domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com", "https://admin.example.com"],
    allow_credentials=True,  # Allow cookies + auth headers
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-RateLimit-Remaining"],
)
```

### Logging + Audit Trail

```python
# Every auth decision must be logged with context

logger.info("auth_success", extra={
    "auth_type": "jwt",               # Which layer?
    "user_id": claims.get("sub"),     # Who?
    "endpoint": request.url.path,     # What?
    "method": request.method,
    "ip": request.client.host,        # From where?
    "timestamp": datetime.now(timezone.utc).isoformat(),  # When?
})

logger.warning("auth_failure", extra={
    "auth_type": "bearer",
    "reason": "invalid_token",
    "attempt": token[:8] + "...",     # Partial token for privacy
    "ip": request.client.host,
})
```

### Environment Parity

```text
Development  → Fast iteration, shared temp credentials OK
Staging      → Production-like: Redis sessions, HTTPS, real secrets in secrets manager
Production   → Full hardening: key rotation, TLS 1.3, audit logging, monitoring
```

---

## Load Testing & Scaling

### Session Store Scaling

#### Scenario: 10,000 concurrent authenticated users

```text
Requirement: Store 10k sessions, each ~200 bytes
Total RAM: 10k × 200 B = 2 MB (negligible)

Reality: Each session lookup = Redis network round-trip (~1ms)
At 10k RPS: 10k req/s × 1ms = 10 seconds of latency (not acceptable!)

Solution: Session cache in-process (with TTL sync)
  - FastAPI instance keeps local LRU cache (e.g., 1k hot sessions)
  - Cache hit → instant validation (in-memory)
  - Cache miss → Redis lookup + update local cache
  - Expiry events pushed via Redis Pub/Sub or periodic sync

Example: asyncache + Redis subscriber
```

```python
import asyncache
import redis.asyncio

_session_cache = asyncache.cached(ttl=60)(fetch_session_from_redis)

async def verify_session(session_id: str) -> dict:
    # Tries local cache first, falls back to Redis
    return await _session_cache(session_id)

# To invalidate on logout:
await redis_client.publish("sessions:logout", session_id)
# All instances subscribe and clear local cache entry
```

### JWT Scaling (No Session Store)

```text
Benefit: Zero server state → scales horizontally
At 10k RPS: All instances validate token in-process (no DB/cache lookup)
Latency: ~1ms per JWT verification (cryptographic overhead only)

Cost: No instant revocation (JWT valid until expiry)
Mitigation: Short TTL (5 min) + blacklist for critical actions
```

### Database Connection Pool Scaling

```python
# app/database.py
engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=20,                     # Open 20 connections per process
    max_overflow=10,                  # Allow up to 10 additional (queue if exceeded)
    pool_recycle=3600,                # Recycle connections every hour
    pool_pre_ping=True,               # Check connection before use
)

# At 10k RPS with 20 pool size:
#   Max throughput = 20 connections × 100 queries/sec per conn = 2k queries/sec
#   If exceeding 2k queries/sec: scale horizontally (more instances)
#   or increase pool_size (more RAM/context per process)
```

### Load Test Example (k6)

```javascript
// scripts/loadtest-auth.js — Test all three auth mechanisms

import http from "k6/http";
import { check, group } from "k6";

const BASE_URL = "http://localhost:8000";

export const options = {
  vus: 100,                 // 100 virtual users
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1000"],  // 95% < 500ms
    http_req_failed: ["rate<0.1"],                    // <10% failure
  },
};

export default function () {
  group("Bearer Token Auth", () => {
    const res = http.post(`${BASE_URL}/api/v1/records/batch/protected`,
      JSON.stringify({ source: "k6", timestamp: new Date().toISOString(), data: {}, tags: [] }),
      {
        headers: {
          Authorization: "Bearer dev-secret-bearer-token",
          "Content-Type": "application/json",
        },
      }
    );
    check(res, { "bearer: 201": (r) => r.status === 201 });
  });

  group("JWT Auth", () => {
    // First, get a token
    const tokenRes = http.get(`${BASE_URL}/api/v2/records/token?user_id=loadtest-user`);
    const token = JSON.parse(tokenRes.body).access_token;

    // Then create a record
    const res = http.post(`${BASE_URL}/api/v2/records/jwt`,
      JSON.stringify({ source: "k6", timestamp: new Date().toISOString(), data: {}, tags: [] }),
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      }
    );
    check(res, { "jwt: 201": (r) => r.status === 201 });
  });

  group("Session Auth", () => {
    // Login
    const loginRes = http.post(`${BASE_URL}/api/v1/records/auth/login?user_id=loadtest-user`);
    check(loginRes, { "login: 200": (r) => r.status === 200 });

    // Create record with session cookie
    const res = http.post(`${BASE_URL}/api/v1/records/batch/protected`,
      JSON.stringify({ source: "k6", timestamp: new Date().toISOString(), data: {}, tags: [] }),
      {
        cookies: {
          session_id: loginRes.cookies.session_id.value,
        },
        headers: { "Content-Type": "application/json" },
      }
    );
    check(res, { "session: 201": (r) => r.status === 201 });
  });
}
```

**Run load test**:

```bash
k6 run scripts/loadtest-auth.js
```

---

## Monitoring & Alerting

### Metrics to Track

```python
# app/metrics.py - Register Prometheus metrics

from prometheus_client import Counter, Histogram

auth_attempts = Counter(
    "auth_attempts_total",
    "Authentication attempts by type and result",
    ["auth_type", "result"]  # result: success, failure, expired
)

auth_latency = Histogram(
    "auth_latency_seconds",
    "Auth verification latency",
    ["auth_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1]  # 1ms to 100ms
)

session_count = Gauge(
    "sessions_active",
    "Active session count"
)

jwt_tokens_issued = Counter(
    "jwt_tokens_issued_total",
    "JWT tokens issued by user",
    ["user_id"]
)

# Usage in auth.py:
auth_attempts.labels(auth_type="jwt", result="success").inc()
auth_latency.labels(auth_type="bearer").observe(elapsed_time)
```

### Alert Rules

```yaml
# prometheus-rules.yml

groups:
  - name: auth
    rules:
      - alert: HighAuthFailureRate
        expr: rate(auth_attempts_total{result="failure"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High auth failure rate (>10% failures)"

      - alert: JWTExpiryMissing
        expr: rate(jwt_tokens_issued_total[1h]) == 0 and day_of_week() > 1  # Weekdays
        for: 1h
        annotations:
          summary: "No JWT tokens issued in 1 hour (possible misconfiguration)"

      - alert: SessionStoreFullRedis
        expr: used_memory_bytes{instance="redis:6379"} / total_memory_bytes > 0.9
        for: 10m
        annotations:
          summary: "Redis memory >90% — session eviction happening"
```

---

## Compliance & Standards

### OWASP Top 10

| Risk | Mitigation |
| ------ | ----------- |
| **Broken Auth** | Enforce HTTPS, secure session storage, rate limit login attempts |
| **Injection** | Use parameterized queries (SQLAlchemy ORM), no string formatting |
| **Sensitive Data** | Encrypt secrets at rest, use HTTPS, never log tokens |
| **XML/XXXX** | Use JSON only, no XML deserialization |
| **Broken Access** | Principle of least privilege, validate all scopes/permissions |
| **Security Config** | Disable debug mode production, remove default credentials |
| **XSS** | Use HTTPOnly cookies, encode output, CSP headers |
| **CSRF** | SameSite=Strict, CSRF tokens, use POST for state changes |
| **Deserialization** | Use JSON, no pickle/unsafe formats |
| **Logging** | Log all auth events, never log passwords/tokens |

### Standards

- **OWASP ASVS Level 2** for API authentication
- **NIST SP 800-63B-3** for identity and access management
- **RFC 6750** for Bearer Token Usage
- **RFC 7519** for JSON Web Tokens (JWT)

---

## Checklist: Moving to Production

- [ ] All secrets → environment variables or secrets manager (no hardcoded values)
- [ ] Bearer token → key rotation strategy (e.g., 30-day cycle with grace period)
- [ ] Session store → Redis cluster with replication (not in-memory dict)
- [ ] JWT → RS256 algorithm with key versioning (or HS256 with key rotation)
- [ ] HTTPS enforced (TLS 1.3+, certs auto-renewed)
- [ ] Rate limiting per authenticated user (not per IP)
- [ ] Audit logging for all auth events (structure: type, user, endpoint, result, ip, timestamp)
- [ ] CORS restricted to known domains
- [ ] Cookie flags: HttpOnly, Secure, SameSite=Strict
- [ ] Auth latency monitored (<100ms p99)
- [ ] Failed auth attempts alerted (>10% failure rate in 5 min)
- [ ] Session/token expiry tested (manual + automated)
- [ ] Load test passing (10k+ concurrent users, <500ms p95)
- [ ] Key rotation tested (can issue new tokens without downtime)
- [ ] Logout flow validated (tokens revoked promptly)
- [ ] Error messages don't leak secrets (e.g., "invalid credentials" not "user not found")

---

## Further Reading

- [Auth0 Docs](https://auth0.com/docs)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [NIST 800-63 Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT.io](https://jwt.io/)
- [Redis ACL](https://redis.io/docs/latest/operate/oss_cluster/management/access-control-lists/)
