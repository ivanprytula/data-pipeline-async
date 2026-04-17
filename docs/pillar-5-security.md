# Pillar 5: Security

**Tier**: Middle (🟡) → Senior (🔴)
**Project**: Required for any public API

---

## Middle Tier (🟡)

### Authentication / Authorization

**JWT (JSON Web Tokens)**:

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

def create_access_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(hours=24)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def verify_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**OAuth2 with FastAPI**:

```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = verify_credentials(form_data.username, form_data.password)
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/records")
async def list_records(token: str = Depends(oauth2_scheme)):
    user_id = await verify_token(token)
    # User is authenticated
```

**RBAC (Role-Based Access Control)**:

```python
async def require_admin(user_id: int) -> User:
    user = await db.get(User, user_id)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user

@app.delete("/records/{id}")
async def delete_record(record_id: int, user: User = Depends(require_admin)):
    # Only admin can delete
```

---

### Input Validation & Injection Prevention

**Pydantic** validates at boundary:

```python
class RecordRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=255)
    timestamp: str  # Validated as ISO 8601
    data: dict = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v):
        from datetime import datetime
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("Invalid ISO 8601")
        return v
```

**SQL Injection prevention** (always use ORM or parameterized queries):

```python
# SAFE: ORM handles parameterization
stmt = select(Record).where(Record.source == user_input)
records = await db.scalars(stmt)

# UNSAFE: string concatenation (never do this)
stmt = f"SELECT * FROM records WHERE source = '{user_input}'"  # ❌
```

---

### API Hardening

**CORS** (restrict domains):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],  # NOT "*"
    allow_methods=["GET", "POST"],
    allow_credentials=True,
)
```

**Security Headers**:

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

**Rate Limiting** (see Pillar 1) prevents brute force on `/login`

---

## Senior (🔴)

### HMAC Webhook Verification

```python
import hmac
import hashlib

@app.post("/webhooks/stripe")
async def handle_webhook(request: Request):
    signature = request.headers.get("X-Signature-256")
    body = await request.body()

    expected = hmac.new(
        b"webhook-secret",
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Process webhook
```

---

### Docker Security

**Always use**:

```dockerfile
FROM python:3.14-slim
USER appuser  # Non-root
RUN useradd -m appuser
```

In Kubernetes:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
```

---

### CI Secret Scanning

Use `gitleaks` or `truffleHog` in GitHub Actions:

```yaml
- uses: gitleaks/gitleaks-action@v2
```

Prevents accidentally committing API keys

---

## You Should Be Able To

✅ Implement JWT authentication + refresh tokens
✅ Add CORS + security headers
✅ Validate all input with Pydantic
✅ Explain SQL injection + why parameterized queries prevent it
✅ Implement RBAC with role checks
✅ Verify HMAC webhook signatures
✅ Run secret scanning in CI
✅ Explain why `os.environ["SECRET"]` is wrong (use Secrets Manager)

---

## References

- [python-jose](https://github.com/mpdavis/python-jose)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [gitleaks](https://github.com/gitleaks/gitleaks)
