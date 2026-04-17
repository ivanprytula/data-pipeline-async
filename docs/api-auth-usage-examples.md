# API Authentication — Usage Examples

Quick reference for using all three authentication mechanisms.

## HTTP Basic Auth (Docs)

Access `/docs` endpoint with username/password.

**With curl:**

```bash
curl -u admin:admin http://localhost:8000/docs
```

**With Python requests:**

```python
import requests
from requests.auth import HTTPBasicAuth

response = requests.get(
    "http://localhost:8000/docs",
    auth=HTTPBasicAuth("admin", "admin")
)
```

**Environment (.env):**

```
DOCS_USERNAME=admin
DOCS_PASSWORD=admin
```

---

## Bearer Token (v1 API)

Static token-based authentication. No expiry, no server state.

**Get token:**

```
Set via environment: API_V1_BEARER_TOKEN=dev-secret-bearer-token
```

**Protected endpoints:**

- `POST /api/v1/records/batch/protected` — Create records with bearer auth
- `GET /api/v1/records/{id}/secure` — Read record with session auth (example)

**With curl:**

```bash
# Create records
curl -X POST http://localhost:8000/api/v1/records/batch/protected \
  -H "Authorization: Bearer dev-secret-bearer-token" \
  -H "Content-Type: application/json" \
  -d '[
    {"source": "curl", "timestamp": "2024-01-15T10:00:00", "data": {"val": 1}, "tags": []}
  ]'

# Response (201 Created):
[
  {
    "id": 1,
    "source": "curl",
    "timestamp": "2024-01-15T10:00:00",
    "data": {"val": 1},
    "tags": []
  }
]
```

**With Python requests:**

```python
import requests

token = "dev-secret-bearer-token"
headers = {"Authorization": f"Bearer {token}"}

# Create records
response = requests.post(
    "http://localhost:8000/api/v1/records/batch/protected",
    headers=headers,
    json=[
        {
            "source": "python",
            "timestamp": "2024-01-15T10:00:00",
            "data": {"val": 1},
            "tags": []
        }
    ]
)
print(response.json())  # [{"id": 1, ...}]
```

**With httpx (async):**

```python
import httpx

async def create_records_with_bearer():
    token = "dev-secret-bearer-token"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/records/batch/protected",
            headers=headers,
            json=[{"source": "httpx", "timestamp": "2024-01-15T10:00:00", "data": {}, "tags": []}]
        )
        return response.json()
```

---

## Session-Based Auth (v1 API)

Server-side session storage with cookie-based authentication.

**Flow:**

1. POST `/api/v1/records/auth/login?user_id=<user>` → Get session ID
2. Use `session_id` cookie in subsequent requests

**With curl:**

```bash
# 1. Login (creates session, returns session_id)
curl -X POST "http://localhost:8000/api/v1/records/auth/login?user_id=alice" \
  -v  # Use -v to see Set-Cookie header

# Extract session_id from Set-Cookie header:
# Set-Cookie: session_id=...; HttpOnly; Secure; SameSite=Strict

# 2. Use session in next request (curl stores cookies by default with -b flag)
curl -b "session_id=<EXTRACTED_SESSION_ID>" \
  -X GET "http://localhost:8000/api/v1/records/1/secure"
```

**With Python requests:**

```python
import requests

# Requests automatically handles cookies with a Session object
session = requests.Session()

# 1. Login
response = session.post("http://localhost:8000/api/v1/records/auth/login?user_id=alice")
print(f"Login response: {response.json()}")
# {"session_id": "...", "message": "Session created"}

# 2. Cookie is now in session.cookies, used automatically in next request
response = session.get("http://localhost:8000/api/v1/records/1/secure")
print(f"Secure read: {response.json()}")
# {"id": 1, "source": "...", ...}
```

**With httpx (async):**

```python
import httpx

async def session_workflow():
    # httpx.AsyncClient maintains cookies across requests (like requests.Session)
    async with httpx.AsyncClient() as client:
        # 1. Login
        response = await client.post(
            "http://localhost:8000/api/v1/records/auth/login?user_id=alice"
        )
        print(f"Login: {response.json()}")

        # 2. Cookie automatically included in next request
        response = await client.get("http://localhost:8000/api/v1/records/1/secure")
        print(f"Secure read: {response.json()}")
```

**Environment (.env):**

```
# Session expiry time (hours)
TOKEN_EXPIRY_HOURS=24
```

---

## JWT Token Auth (v2 API)

Stateless token authentication. Token signed by server, verified via signature.

**Flow:**

1. POST `/api/v2/records/token?user_id=<user>` → Get JWT token
2. Use JWT in `Authorization: Bearer <token>` header for protected endpoints

**Get token with curl:**

```bash
# Issue JWT token for user "bob"
curl -X POST "http://localhost:8000/api/v2/records/token?user_id=bob"

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJib2IiLCJleHAiOjE3MDUzMjM...",
  "token_type": "bearer"
}
```

**Use JWT token with curl:**

```bash
# Create record with JWT
curl -X POST "http://localhost:8000/api/v2/records/jwt" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJib2I..." \
  -H "Content-Type: application/json" \
  -d '{
    "source": "curl-jwt",
    "timestamp": "2024-01-15T10:00:00",
    "data": {"count": 1},
    "tags": ["example"]
  }'

# Response (201 Created):
{
  "id": 5,
  "source": "curl-jwt",
  "timestamp": "2024-01-15T10:00:00",
  "data": {"count": 1},
  "tags": ["example"]
}
```

**With Python:**

```python
import requests

# 1. Get token
token_response = requests.post("http://localhost:8000/api/v2/records/token?user_id=bob")
token = token_response.json()["access_token"]
print(f"Token: {token}")

# 2. Use token to create record
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    "http://localhost:8000/api/v2/records/jwt",
    headers=headers,
    json={
        "source": "python-jwt",
        "timestamp": "2024-01-15T10:00:00",
        "data": {"count": 1},
        "tags": ["example"]
    }
)
print(f"Created: {response.json()}")
```

**With httpx (async):**

```python
import httpx
from datetime import datetime

async def jwt_workflow():
    async with httpx.AsyncClient() as client:
        # 1. Get JWT token
        token_response = await client.post(
            "http://localhost:8000/api/v2/records/token?user_id=bob"
        )
        token = token_response.json()["access_token"]

        # 2. Use token to make authenticated request
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post(
            "http://localhost:8000/api/v2/records/jwt",
            headers=headers,
            json={
                "source": "httpx-jwt",
                "timestamp": datetime.now().isoformat(),
                "data": {"count": 1},
                "tags": ["example"]
            }
        )
        return response.json()
```

**Decode JWT (for inspection):**

```python
import jwt

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
secret = "your-jwt-secret"  # From config

# Decode without verification (inspection only)
unverified = jwt.decode(token, options={"verify_signature": False})
print(unverified)
# Output: {"sub": "bob", "iat": 1705321200, "exp": 1705324800, "iss": "data-pipeline-async", ...}

# Verify signature (what the API does)
try:
    verified = jwt.decode(token, secret, algorithms=["HS256"])
    print(f"Valid token for user: {verified['sub']}")
except jwt.ExpiredSignatureError:
    print("Token expired")
except jwt.InvalidSignatureError:
    print("Invalid token signature")
```

**Environment (.env):**

```
JWT_SECRET=your-super-secret-key-at-least-32-chars-long
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
```

---

## Comparison: Which Auth to Use?

| Scenario | Method | Why |
|----------|--------|-----|
| Internal docs (API docs) | HTTP Basic Auth | Simple, no client setup required |
| Mobile app | Bearer Token or JWT | Stateless, works offline |
| Server-to-server API | Bearer Token (key rotation) | Can rotate keys per client |
| Multi-service ecosystem | JWT with RS256 | Stateless, signature verification across services |
| Web app with sessions | Session-based | Stateful, can revoke instantly |
| Learning/demo | All three | Understand tradeoffs |

---

## Rate Limiting Headers

All v2 endpoints return rate-limit headers:

```
X-RateLimit-Strategy: token-bucket | sliding-window
X-RateLimit-Limit: 20 (max capacity)
X-RateLimit-Remaining: 18 (after this request)
Retry-After: 5 (seconds, only on 429)
```

Check headers with curl `-i`:

```bash
curl -i -X POST http://localhost:8000/api/v2/records/token-bucket \
  -d '{...}'

HTTP/1.1 201 Created
X-RateLimit-Strategy: token-bucket
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 19
...
```

---

## Error Responses

**Missing Authorization header:**

```
Status: 401
{"detail": "Missing Authorization header"}
```

**Invalid token:**

```
Status: 401
{"detail": "Invalid token"}
```

**Expired JWT:**

```
Status: 401
{"detail": "Token expired"}
```

**Rate limit exceeded:**

```
Status: 429
{"detail": "Rate limit exceeded"}
Retry-After: 3
X-RateLimit-Remaining: 0
```

---

## Scripts

### Load Test Script

```bash
#!/bin/bash
# scripts/test-auth.sh — Test all auth mechanisms

BASE_URL="http://localhost:8000"

echo "=== Bearer Token Auth ==="
curl -X POST "$BASE_URL/api/v1/records/batch/protected" \
  -H "Authorization: Bearer dev-secret-bearer-token" \
  -H "Content-Type: application/json" \
  -d '[{"source": "bearer", "timestamp": "2024-01-15T10:00:00", "data": {}, "tags": []}]'

echo -e "\n\n=== Session Auth (1/2: Login) ==="
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/records/auth/login?user_id=alice")
echo "$SESSION_RESPONSE"

echo -e "\n\n=== Session Auth (2/2: Protected Request) ==="
SESSION=$(echo "$SESSION_RESPONSE" | jq -r '.session_id')
curl -X GET "http://localhost:8000/api/v1/records/1/secure" \
  -b "session_id=$SESSION"

echo -e "\n\n=== JWT Auth (1/2: Issue Token) ==="
JWT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v2/records/token?user_id=bob")
echo "$JWT_RESPONSE"

echo -e "\n\n=== JWT Auth (2/2: Protected Request) ==="
JWT=$(echo "$JWT_RESPONSE" | jq -r '.access_token')
curl -X POST "$BASE_URL/api/v2/records/jwt" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"source": "jwt", "timestamp": "2024-01-15T10:00:00", "data": {}, "tags": []}'
```

Run: `bash scripts/test-auth.sh`

---

## Troubleshooting

**Token expired?**

```
Response: 401 Token expired
→ Get a new token with POST /api/v2/records/token?user_id=<user>
```

**Invalid Bearer format?**

```
Response: 401 Invalid scheme. Use: Authorization: Bearer <token>
→ Make sure header is exactly: Authorization: Bearer eyJ...
```

**Rate limit 429?**

```
Response: 429 Rate limit exceeded
Retry-After: 5
→ Wait 5 seconds, then retry
```

**Session not found?**

```
Response: 401 Session expired or invalid
→ Create new session: POST /api/v1/records/auth/login?user_id=<user>
→ Old sessions expire after TOKEN_EXPIRY_HOURS
```
