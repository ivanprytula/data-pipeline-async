"""Async API integration tests."""

import pytest
from httpx import AsyncClient

from tests.shared.payloads import RECORD_API


_RECORD = RECORD_API


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_health(client: AsyncClient) -> None:
    # Act
    r = await client.get("/health")

    # Assert
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Create single record
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_create_record(client: AsyncClient) -> None:
    # Act
    r = await client.post("/api/v1/records", json=_RECORD)

    # Assert
    assert r.status_code == 201
    body = r.json()
    assert body["source"] == "api.example.com"
    assert body["tags"] == ["stock", "nasdaq"]
    assert body["id"] is not None
    assert body["processed"] is False


@pytest.mark.integration
async def test_create_record_missing_source(client: AsyncClient) -> None:
    bad = {**_RECORD}
    del bad["source"]

    r = await client.post("/api/v1/records", json=bad)

    assert r.status_code == 422


@pytest.mark.integration
async def test_create_record_empty_source(client: AsyncClient) -> None:
    r = await client.post("/api/v1/records", json={**_RECORD, "source": ""})

    assert r.status_code == 422


@pytest.mark.integration
async def test_create_record_future_timestamp(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/records", json={**_RECORD, "timestamp": "2099-01-01T00:00:00"}
    )

    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Batch create
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_create_batch(client: AsyncClient) -> None:
    payload = {"records": [_RECORD, {**_RECORD, "source": "b.example.com"}]}

    r = await client.post("/api/v1/records/batch", json=payload)

    assert r.status_code == 201
    assert r.json()["created"] == 2


@pytest.mark.integration
async def test_batch_too_large(client: AsyncClient) -> None:
    payload = {"records": [_RECORD] * 1001}

    r = await client.post("/api/v1/records/batch", json=payload)

    assert r.status_code == 422


# ---------------------------------------------------------------------------
# List / pagination
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_list_records_empty(client: AsyncClient) -> None:
    r = await client.get("/api/v1/records")

    assert r.status_code == 200
    body = r.json()
    assert body["records"] == []
    assert body["pagination"]["total"] == 0
    assert body["pagination"]["has_more"] is False


@pytest.mark.integration
async def test_list_records_pagination(client: AsyncClient) -> None:
    for i in range(5):
        await client.post("/api/v1/records", json={**_RECORD, "source": f"src-{i}"})

    r = await client.get("/api/v1/records?skip=0&limit=3")

    body = r.json()
    assert len(body["records"]) == 3
    assert body["pagination"]["total"] == 5
    assert body["pagination"]["has_more"] is True


@pytest.mark.integration
async def test_list_records_filter_source(client: AsyncClient) -> None:
    await client.post("/api/v1/records", json={**_RECORD, "source": "alpha"})
    await client.post("/api/v1/records", json={**_RECORD, "source": "beta"})

    r = await client.get("/api/v1/records?source=alpha")

    body = r.json()
    assert len(body["records"]) == 1
    assert body["records"][0]["source"] == "alpha"


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_get_record(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/records", json=_RECORD)).json()

    r = await client.get(f"/api/v1/records/{created['id']}")

    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.integration
async def test_get_nonexistent_record(client: AsyncClient) -> None:
    r = await client.get("/api/v1/records/99999")

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Mark as processed
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_mark_processed(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/records", json=_RECORD)).json()

    r = await client.patch(f"/api/v1/records/{created['id']}/process")

    assert r.status_code == 200
    assert r.json()["processed"] is True


@pytest.mark.integration
async def test_mark_processed_nonexistent(client: AsyncClient) -> None:
    r = await client.patch("/api/v1/records/99999/process")

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_delete_record(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/records", json=_RECORD)).json()

    r = await client.delete(f"/api/v1/records/{created['id']}")

    assert r.status_code == 204
    # Verify it's actually gone
    r = await client.get(f"/api/v1/records/{created['id']}")
    assert r.status_code == 404


@pytest.mark.integration
async def test_delete_record_not_found(client: AsyncClient) -> None:
    r = await client.delete("/api/v1/records/99999")

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Archive (soft-delete)
# ---------------------------------------------------------------------------
@pytest.mark.integration
async def test_archive_record(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/records", json=_RECORD)).json()
    record_id = created["id"]

    r = await client.patch(f"/api/v1/records/{record_id}/archive")

    assert r.status_code == 200
    body = r.json()
    assert body["deleted_at"] is not None

    # Archived record is hidden from GET and list
    assert (await client.get(f"/api/v1/records/{record_id}")).status_code == 404
    listing = (await client.get("/api/v1/records")).json()
    assert all(rec["id"] != record_id for rec in listing["records"])


@pytest.mark.integration
async def test_archive_record_not_found(client: AsyncClient) -> None:
    r = await client.patch("/api/v1/records/99999/archive")

    assert r.status_code == 404


@pytest.mark.integration
async def test_archive_record_idempotent(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/records", json=_RECORD)).json()
    record_id = created["id"]
    await client.patch(f"/api/v1/records/{record_id}/archive")

    # Second archive attempt returns 404 — already archived
    r = await client.patch(f"/api/v1/records/{record_id}/archive")

    assert r.status_code == 404
