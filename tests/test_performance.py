"""Async performance baseline tests — run with pytest -s to see timings."""

import time

from httpx import AsyncClient


_RECORD = {
    "source": "perf.test",
    "timestamp": "2024-01-15T10:00:00",
    "data": {"value": 0},
    "tags": [],
}


async def test_batch_insert_1000(client: AsyncClient) -> None:
    payload = {"records": [{**_RECORD, "data": {"value": i}} for i in range(1000)]}
    start = time.perf_counter()
    r = await client.post("/api/v1/records/batch", json=payload)
    elapsed = time.perf_counter() - start
    print(f"\n[perf] 1 000 records inserted in {elapsed:.3f}s")
    assert r.status_code == 201
    assert elapsed < 5.0


async def test_list_1000_records(client: AsyncClient) -> None:
    payload = {"records": [{**_RECORD, "data": {"value": i}} for i in range(1000)]}
    await client.post("/api/v1/records/batch", json=payload)

    start = time.perf_counter()
    r = await client.get("/api/v1/records?limit=1000")
    elapsed = time.perf_counter() - start
    print(f"\n[perf] 1 000 records listed in {elapsed:.3f}s")
    assert r.status_code == 200
    assert elapsed < 1.0
