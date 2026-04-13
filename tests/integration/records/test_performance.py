"""Async performance baseline tests — run with pytest -v --log-cli-level=INFO to see timings."""

import logging
import time

import pytest
from httpx import AsyncClient

from tests.shared.payloads import RECORD_PERF

logger = logging.getLogger(__name__)


_RECORD = RECORD_PERF


@pytest.mark.integration
async def test_batch_insert_1000(client: AsyncClient) -> None:
    # Arrange
    payload = {"records": [{**_RECORD, "data": {"value": i}} for i in range(1000)]}
    start = time.perf_counter()

    # Act
    r = await client.post("/api/v1/records/batch", json=payload)
    elapsed = time.perf_counter() - start

    # Assert
    logger.info(f"[perf] 1 000 records inserted in {elapsed:.3f}s")
    assert r.status_code == 201
    assert elapsed < 10.0


@pytest.mark.integration
async def test_list_1000_records(client: AsyncClient) -> None:
    # Arrange
    payload = {"records": [{**_RECORD, "data": {"value": i}} for i in range(1000)]}
    await client.post("/api/v1/records/batch", json=payload)
    start = time.perf_counter()

    # Act
    r = await client.get("/api/v1/records?limit=1000")
    elapsed = time.perf_counter() - start

    # Assert
    logger.info(f"[perf] 1 000 records listed in {elapsed:.3f}s")
    assert r.status_code == 200
    assert elapsed < 3.0
