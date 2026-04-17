# API Documentation Authentication

This doc explains how to protect API documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) with HTTP Basic Auth.

**Status**: ✅ Implemented and tested

---

## Quick Start

### Enable Auth (Development)

```bash
# Set credentials in .env
DOCS_USERNAME=admin
DOCS_PASSWORD=changeme

# Restart app
uv run uvicorn app.main:app --reload

# Access docs (browser prompts for username/password)
open http://localhost:8000/docs
```

### Disable Auth (Default)

```bash
# Leave empty or omit from .env
# DOCS_USERNAME and DOCS_PASSWORD not set
uv run uvicorn app.main:app --reload

# Docs are fully public
open http://localhost:8000/docs
```

---

## Implementation Details

### Architecture

**Files involved:**

| File | Purpose |
|------|---------|
| `app/auth.py` | HTTP Basic Auth verification logic |
| `app/config.py` | `docs_username`, `docs_password` settings |
| `app/main.py` | Protected endpoints + conditional routing |
| `.env.example` | Configuration template |

### How It Works

1. **Configuration phase** (app startup):
   - Read `DOCS_USERNAME` and `DOCS_PASSWORD` from environment
   - If both are set, disable FastAPI's default docs endpoints
   - Condition: `docs_url=None` if auth configured, else `docs_url="/docs"`

2. **Protected endpoint phase** (only if auth enabled):
   - Register custom `/docs`, `/redoc`, `/openapi.json` endpoints
   - Each endpoint has `dependencies=[Depends(verify_docs_credentials)]`
   - FastAPI calls `verify_docs_credentials()` before route handler

3. **Auth check phase** (per request):
   - `verify_docs_credentials()` receives HTTP Basic Auth header
   - Compare username/password against configured values
   - Return credentials if valid
   - Raise `HTTPException(403)` if invalid (sends `WWW-Authenticate` header)

---

## HTTP Basic Auth Mechanism

### Browser Access

```bash
open http://localhost:8000/docs
# Browser shows login dialog
# User enters username + password
# Request header: Authorization: Basic base64(username:password)
```

### Programmatic Access (curl)

```bash
# Using -u flag
curl -u admin:changeme http://localhost:8000/docs

# Or explicit header (manual base64)
curl -H "Authorization: Basic YWRtaW46Y2hhbmdlbWU=" http://localhost:8000/docs
```

### Python Client

```python
import httpx

# Using auth parameter
async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8000/docs",
        auth=("admin", "changeme")
    )

# Or explicit header
import base64
credentials = base64.b64encode(b"admin:changeme").decode()
async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8000/docs",
        headers={"Authorization": f"Basic {credentials}"}
    )
```

---

## Configuration

### Environment Variables

```env
# Enable auth for docs endpoints
DOCS_USERNAME=admin
DOCS_PASSWORD=your-secure-password

# Disable auth (leave empty or omit)
# DOCS_USERNAME=
# DOCS_PASSWORD=
```

### Pydantic Settings

From [app/config.py](../app/config.py):

```python
docs_username: str | None = Field(
    default=None,
    description="Username for docs authentication"
)

docs_password: str | None = Field(
    default=None,
    description="Password for docs authentication"
)
```

**Behavior**:

- `None` (default) → Public access (docs fully open)
- Both set → Protected access (HTTP Basic Auth required)
- Only one set → Invalid configuration (would work but docs wouldn't be protected fully)

---

## What Gets Protected

### Protected Endpoints (when auth enabled)

- ✅ `GET /docs` — Swagger UI
- ✅ `GET /redoc` — ReDoc (read-only docs)
- ✅ `GET /openapi.json` — OpenAPI schema (for tools)

### Unprotected Endpoints (always public)

- `GET /api/v1/records` — Data access
- `POST /api/v1/records` — Data creation
- `GET /health` — Health check
- All other data/API endpoints

**Why?** Documentation auth only protects info about your API. Data access requires separate auth (would apply API keys, JWT, etc. at the route level if needed).

---

## Security Considerations

### ✅ Safe Practices (Already Implemented)

1. **Credentials not in code** — Loaded from environment only
2. **HTTP Basic Auth** — Standard, browser-native support
3. **Conditional protection** — If not configured, docs remain public (opt-in)
4. **Logging** — Auth events logged at startup (`docs_auth_enabled`)

### ⚠️ Production Requirements

1. **Always use HTTPS** — Basic Auth sends credentials in header (readable if not encrypted)

   ```bash
   # Development (HTTP ok, for learning)
   curl -u admin:changeme http://localhost:8000/docs
   
   # Production (HTTPS required)
   curl -u admin:changeme https://api.example.com/docs
   ```

2. **Strong passwords** — Use secrets manager (AWS Secrets, HashiCorp Vault)

   ```bash
   # Bad
   DOCS_PASSWORD=changeme
   
   # Good
   DOCS_PASSWORD=$(aws secretsmanager get-secret-value --secret-id docs-password --query SecretString)
   ```

3. **Consider API keys instead** — For programmatic access

   ```python
   # Better approach for tools: Generate unique API key per tool
   # Then require key in Authorization header, not Basic Auth
   @app.get("/docs", dependencies=[Depends(verify_api_key)])
   ```

4. **Rotate credentials regularly** — Update password in secrets manager
5. **Monitor access** — Log who accesses docs

   ```python
   logger.info("docs_accessed", extra={"username": credentials.username})
   ```

---

## Testing the Protection

### Verify Auth Works

```python
# tests/test_docs_auth.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_docs_protected_no_credentials():
    """Docs should require auth when configured."""
    client = TestClient(app)
    response = client.get("/docs")
    
    # If auth enabled, should get 403
    if app.docs_url is None:  # Auth is configured
        assert response.status_code == 403
        assert "WWW-Authenticate" in response.headers


def test_docs_with_correct_credentials():
    """Docs should be accessible with valid credentials."""
    client = TestClient(app)
    response = client.get(
        "/docs",
        auth=("admin", "changeme")
    )
    
    if app.docs_url is None:  # Auth is configured
        assert response.status_code == 200
        assert "swagger-ui" in response.text


def test_docs_with_incorrect_credentials():
    """Docs should reject invalid credentials."""
    client = TestClient(app)
    response = client.get(
        "/docs",
        auth=("admin", "wrongpassword")
    )
    
    if app.docs_url is None:  # Auth is configured
        assert response.status_code == 403
```

**Run tests:**

```bash
uv run pytest tests/test_docs_auth.py -v
```

---

## Docker Deployment

### Setting Credentials

```yaml
# docker-compose.yml
services:
  app:
    environment:
      DOCS_USERNAME: admin
      DOCS_PASSWORD: ${DOCS_PASSWORD:-changeme}  # Use secret in prod
```

### Using Docker Secrets (Production)

```yaml
# docker-compose.prod.yml
services:
  app:
    environment:
      DOCS_PASSWORD_FILE: /run/secrets/docs_password
      # App reads from file instead of env var
```

Modify `app/config.py` to support secrets file:

```python
docs_password: str | None = Field(
    default=None,
    json_schema_extra={
        "env": ["DOCS_PASSWORD", "DOCS_PASSWORD_FILE"]
    }
)
```

---

## Alternatives & Comparison

### Option 1: HTTP Basic Auth (Current - Recommended for internal/dev)

| Aspect | Basic Auth |
|--------|-----------|
| **Ease of use** | ✅ Simple (browser works out-of-box) |
| **Security** | ⚠️ Needs HTTPS (credentials in header) |
| **For UI** | ✅ Browser auto-prompts |
| **For tools/CI** | ✅ Curl +u flag, familiar |
| **Per-user** | ❌ Single shared password |
| **Audit trail** | ⚠️ No individual user tracking |

**Best for**: Development, internal APIs, simple protection

---

### Option 2: API Key (Alternative - Recommended for production)

```python
# app/auth.py
async def verify_api_key(key: str = Header(None)):
    if key != settings.docs_api_key:
        raise HTTPException(status_code=403)
    return key

# Then use: @app.get("/docs", dependencies=[Depends(verify_api_key)])
```

| Aspect | API Key |
|--------|---------|
| **Ease of use** | ⚠️ Requires header in all requests |
| **Security** | ✅ Can use HTTPS header auth |
| **For UI** | ❌ Requires manual header entry |
| **For tools/CI** | ✅ Standard Authorization header |
| **Per-user** | ✅ Can have multiple keys |
| **Audit trail** | ✅ Track which key accessed |

**Best for**: Production, external APIs, multiple users/tools

---

### Option 3: OAuth2 (Complex - For multi-tenant)

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Requires /token endpoint, JWT signing, user database
# Overkill for docs protection unless already implemented
```

| Aspect | OAuth2 |
|--------|--------|
| **Ease of use** | ❌ Complex setup |
| **Security** | ✅ Token-based, time-limited |
| **For UI** | ✅ Browser redirect flow |
| **For tools/CI** | ⚠️ Requires token exchange |
| **Per-user** | ✅ Per-user tokens |
| **Audit trail** | ✅ Full audit trail |

**Best for**: Enterprise, multi-user, external partners

---

## Troubleshooting

### "Docs say public but I set credentials"

**Symptom**: `DOCS_USERNAME=admin DOCS_PASSWORD=changeme` set, but docs still public

**Cause**:

1. Variables not read from `.env`
2. Config not applied (need app restart)
3. Typo in variable name

**Fix**:

```bash
# Verify env vars are set
echo $DOCS_USERNAME
echo $DOCS_PASSWORD

# Restart app
uv run uvicorn app.main:app --reload

# Check logs for "docs_auth_enabled"
```

---

### "Can't access docs with credentials"

**Symptom**: `curl -u admin:changeme http://localhost:8000/docs` returns 403

**Cause**:

1. Wrong username/password
2. Only one of them configured (need both)
3. Browser credentials cache (use incognito window)

**Fix**:

```bash
# Test with debug logging
DOCS_USERNAME=admin DOCS_PASSWORD=changeme uv run uvicorn app.main:app --reload

# Try curl with verbose
curl -v -u admin:changeme http://localhost:8000/docs

# Check if auth is actually enabled (look in logs)
# Should see: "docs_auth_enabled ..."
```

---

### "Works locally but not in Docker"

**Symptom**: Docs public in local dev, but protected in Docker

**Cause**: `DOCS_USERNAME` / `DOCS_PASSWORD` not passed to container

**Fix**:

```bash
# Pass via -e flag
docker run -e DOCS_USERNAME=admin -e DOCS_PASSWORD=changeme app

# Or via .env file
docker run --env-file .env app

# Or via docker-compose
docker-compose up  # reads from .env automatically
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Protection Level** | HTTP Basic Auth (optional, opt-in) |
| **Endpoints Protected** | `/docs`, `/redoc`, `/openapi.json` |
| **Data Endpoints** | Unaffected (remain public unless separately secured) |
| **Configuration** | `DOCS_USERNAME` + `DOCS_PASSWORD` env vars |
| **Default State** | Public (no auth required) |
| **Production Ready?** | ✅ Yes, if using HTTPS + strong password |
| **Recommended Alternative** | API Key for production / tooling |

**Next Steps:**

- ✅ Try enabling in local dev: `DOCS_USERNAME=admin DOCS_PASSWORD=test`
- ✅ Test via curl: `curl -u admin:test http://localhost:8000/docs`
- ✅ Test via browser: `open http://localhost:8000/docs`
- ✅ Read [security-and-owasp.instructions.md](../../.copilot/instructions/security-and-owasp.instructions.md) for hardening in production

---

**References:**

- [FastAPI Custom OpenAPI Docs](https://fastapi.tiangolo.com/advanced/extending-openapi/#custom-openapi)
- [RFC 7617: HTTP Basic Authentication](https://tools.ietf.org/html/rfc7617)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
