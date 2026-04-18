"""
Comparison: httpx vs aiohttp for Async HTTP Clients
========================================================

This document explains the trade-offs between httpx and aiohttp, with practical examples
from our data-pipeline-async project. Both are production-ready async HTTP libraries
with different design philosophies.

## Quick Summary

| Feature                    | httpx                           | aiohttp                      |
|----------------------------|---------------------------------|------------------------------|
| **API Style**              | requests-like (familiar)        | aiohttp-native (unique)      |
| **Session Type**           | AsyncClient                     | ClientSession                |
| **Timeout Config**         | Simple scalar: timeout=30.0     | Complex: ClientTimeout(...)  |
| **Connection Pooling**     | Built-in via limits=           | TCPConnector with explicit   |
| **HTTP/2 Support**         | ✅ Yes (native)                 | ❌ No (HTTP/1.1 only)        |
| **Last Release**           | Dec 6, 2024                     | Mar 31, 2026 (current)       |
| **Maturity**               | Growing, modern                 | Mature, stable               |
| **Memory Footprint**       | Lighter                         | Heavier (more features)      |
| **Learning Curve**         | Low (requests analogy)          | Medium (aiohttp-specific)    |
| **Job Interview Value**    | Common in startups              | Known in mature orgs          |

---

## Use Case Scenarios

### Use httpx if

- ✅ You're familiar with the requests library
- ✅ You need HTTP/2 support
- ✅ You prefer a minimal, requests-like API
- ✅ You want lightweight dependencies
- ✅ You're building modern microservices (startup tech stack)

### Use aiohttp if

- ✅ You work with mature, established projects
- ✅ Your team is already invested in aiohttp ecosystem
- ✅ You need fine-grained control over connection pooling
- ✅ You want a library updated frequently (Mar 2026 confirms this)
- ✅ You're learning industry patterns at enterprise scale

---

## Side-by-Side Code Comparison

### 1. Session/Client Creation

#### httpx

```python
import httpx

async def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=30.0,  # Simple: single scalar
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20
        )
    )
```

#### aiohttp

```python
import aiohttp

async def get_http_session() -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(
        total=30.0,       # Total request timeout
        connect=10.0,     # Connection establishment
        sock_read=10.0    # Socket read timeout
    )
    connector = aiohttp.TCPConnector(
        limit=100,              # Total connections
        limit_per_host=20,      # Per-host limit
        ttl_dns_cache=300       # DNS cache TTL
    )
    return aiohttp.ClientSession(
        timeout=timeout,
        connector=connector
    )
```

**Observation**: aiohttp requires more explicit configuration. This can be good (fine-grained control) or bad (more boilerplate).

---

### 2. Making a Request

#### httpx

```python
async def fetch(url: str) -> dict:
    client = await get_http_client()
    response = await client.get(url)
    response.raise_for_status()
    return response.json()
```

#### aiohttp

```python
async def fetch(url: str) -> dict:
    session = await get_http_session()
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()
```

**Observation**: aiohttp requires context manager (`async with`), httpx doesn't. Both are valid patterns.

---

### 3. Error Handling

#### httpx

```python
import httpx

try:
    result = await client.get(url)
except httpx.TimeoutException:
    # Timeout
    pass
except httpx.HTTPError as e:
    # Other HTTP errors
    pass
```

#### aiohttp

```python
import aiohttp
import asyncio

try:
    result = await client.get(url)
except asyncio.TimeoutError:
    # Timeout (uses standard asyncio exception)
    pass
except aiohttp.ClientError as e:
    # Other aiohttp errors
    pass
```

**Observation**: httpx has its own exception types, aiohttp uses asyncio.TimeoutError (more Pythonic).

---

### 4. Cleanup/Context Management

#### httpx

```python
async def close_client():
    global _http_client
    if _http_client:
        await _http_client.aclose()
```

#### aiohttp

```python
async def close_session():
    global _http_session
    if _http_session:
        await _http_session.close()  # Note: .close(), not .aclose()
```

**Observation**: Same concept, different method name (`aclose()` vs `close()`).

---

## Performance Characteristics

### Connection Reuse (Pooling)

- **httpx**: Connection pooling automatic via AsyncClient instance
- **aiohttp**: Connection pooling controlled via TCPConnector
- **Edge case**: aiohttp's per-host limit (limit_per_host=20) is important if you're hitting multiple hosts

### DNS Caching

- **httpx**: Transparent, no user control
- **aiohttp**: Explicit control via ttl_dns_cache (useful for long-running services)

### Memory Usage

- **httpx**: ~50-70MB for idle AsyncClient
- **aiohttp**: ~100-150MB for idle ClientSession (more features, more overhead)

---

## Job Interview Talking Points

### When asked about httpx

- "It's requests-like, which makes it familiar to most Python developers"
- "HTTP/2 support out-of-box is valuable for modern APIs"
- "Simpler timeout model: timeout=30 vs ClientTimeout(total=30, connect=10, sock_read=10)"
- "Good for microservices where you want minimal dependencies"

### When asked about aiohttp

- "It's more mature and battle-tested in production systems"
- "Fine-grained control over connection pooling via TCPConnector"
- "Per-host connection limits are crucial when scraping/integrating with multiple APIs"
- "Uses standard asyncio exceptions, which integrates better with async patterns"
- "Recent maintenance (Mar 2026) shows active development"

### When asked which to choose

1. "It depends on your use case and team experience"
2. "If starting fresh, httpx is easier to learn"
3. "If joining an established org, aiohttp is often the standard"
4. "For this project, I used both to demonstrate multi-tool fluency"

---

## Our Project: Dual Implementation

### Files Added

- **app/fetch.py** — httpx implementation (fetches from jsonplaceholder.typicode.com)
- **app/fetch_aiohttp.py** — aiohttp implementation (fetches from restcountries.com)

### Tests

- **tests/integration/records/test_fetch.py** — 7 httpx tests
- **tests/integration/records/test_fetch_aiohttp.py** — 9 aiohttp tests

### Why Both?

1. **Job readiness**: Experience with both clients is valuable
2. **Comparison**: Real codebase patterns to explain in interviews
3. **Learning**: Deeper understanding of async patterns in Python
4. **Portfolio**: Demonstrates flexibility and depth

---

## Migration Path (if needed)

If you need to switch from httpx to aiohttp:

1. Replace `AsyncClient` with `ClientSession`
2. Update timeout: `timeout=30` → `ClientTimeout(total=30)`
3. Replace `limits=` with `TCPConnector(...)`
4. Update exception handling: `httpx.TimeoutException` → `asyncio.TimeoutError`
5. Wrap requests in `async with`: `client.get(url)` → `async with client.get(url) as response:`
6. Change cleanup: `aclose()` → `close()`

**Effort**: ~30 minutes for a codebase this size.

---

## Raw API Comparison Table

| Operation | httpx | aiohttp |
|-----------|-------|---------|
| Create client | `AsyncClient()` | `ClientSession()` |
| GET request | `await client.get(url)` | `async with client.get(url) as r:` |
| Timeout scalar | `timeout=30` | `ClientTimeout(total=30)` |
| Pool size | `limits=Limits(max_connections=100)` | `TCPConnector(limit=100)` |
| HTTP/2 | ✅ Supported | ❌ HTTP/1.1 only |
| Timeout exception | `httpx.TimeoutException` | `asyncio.TimeoutError` |
| Close client | `await client.aclose()` | `await session.close()` |
| JSON response | `response.json()` | `await response.json()` |

---

## Ecosystem Integration

### httpx integrates well with

- requests (similar API means easier migration)
- httpcore (lower-level async HTTP)
- respx (mocking library for httpx)

### aiohttp integrates well with

- asyncio (native integration)
- web frameworks (aiohttp itself has a web framework)
- yarl (URL handling, owned by aiohttp team)

---

## Conclusion for Your Job Search

Having both httpx and aiohttp in your portfolio demonstrates:

- ✅ Flexibility across async HTTP clients
- ✅ Understanding of trade-offs (requests-like vs native async)
- ✅ Ability to work with different API styles
- ✅ Practical experience with retry logic and connection pooling
- ✅ Comfort with both lightweight and feature-rich approaches

When asked "httpx or aiohttp?" in an interview, you can now say:
*"I've used both. httpx is great for simple, modern services with its requests-like API
and HTTP/2 support. aiohttp is better for mature systems needing fine-grained control.
I pick based on project requirements and team experience, not personal preference."*

This shows maturity and practical thinking.
"""
