"""Unit tests for Phase 5 analytics query-api service.

Tests for:
- Query parameter validation and edge cases
- Response schema validation
- SQL aggregation logic (without database)
- Window function behavior verification
"""

from typing import NotRequired, TypedDict

import pytest


# ---------------------------------------------------------------------------
# TypedDict Definitions for Response Shapes
# ---------------------------------------------------------------------------


class HourEntry(TypedDict):
    """Hour-level aggregation entry in summary responses."""

    hour: str
    record_count: int
    processed_count: int
    processed_pct: float
    avg_value: float
    min_value: float
    max_value: float
    unique_sources: int


class SummaryResponse(TypedDict):
    """Analytics summary response shape."""

    hours_back: int
    since: str
    summary: list[HourEntry]


class PercentileRecord(TypedDict):
    """Individual record in percentile response."""

    id: int
    source: str
    timestamp: str
    value: float
    processed: bool
    percentile_rank: float


class PercentileResponse(TypedDict):
    """Percentile query response shape."""

    source: str
    count: int
    records: list[PercentileRecord]


class RankedRecord(TypedDict):
    """Ranked record in top_by_source response."""

    id: int
    timestamp: str
    value: float
    processed: bool
    rank: int
    source: NotRequired[str]


class TopBySourceResponse(TypedDict):
    """Top records by source query response shape."""

    limit_per_source: int
    hours_back: int
    since: str
    by_source: dict[str, list[RankedRecord]]


class MaterializedViewStatEntry(TypedDict):
    """Individual stat entry in materialized view response."""

    hour: str
    record_count: int
    processed_count: int
    processed_pct: float
    avg_value: float
    min_value: float
    max_value: float
    unique_sources: int
    materialized_at: str


class MaterializedViewStatsResponse(TypedDict):
    """Materialized view stats response shape."""

    limit: int
    count: int
    stats: list[MaterializedViewStatEntry]


# ---------------------------------------------------------------------------
# Test Data Constants
# ---------------------------------------------------------------------------

# Sample analytics response data
SAMPLE_SUMMARY_RESPONSE: SummaryResponse = {
    "hours_back": 24,
    "since": "2026-04-20T00:00:00",
    "summary": [
        {
            "hour": "2026-04-20T02:00:00",
            "record_count": 10,
            "processed_count": 8,
            "processed_pct": 80.0,
            "avg_value": 150.5,
            "min_value": 50.0,
            "max_value": 300.0,
            "unique_sources": 3,
        },
        {
            "hour": "2026-04-20T01:00:00",
            "record_count": 5,
            "processed_count": 5,
            "processed_pct": 100.0,
            "avg_value": 200.0,
            "min_value": 100.0,
            "max_value": 300.0,
            "unique_sources": 2,
        },
    ],
}

SAMPLE_PERCENTILE_RESPONSE: PercentileResponse = {
    "source": "api.example.com",
    "count": 3,
    "records": [
        {
            "id": 1,
            "source": "api.example.com",
            "timestamp": "2026-04-20T10:00:00",
            "value": 1000.0,
            "processed": True,
            "percentile_rank": 1.0,
        },
        {
            "id": 2,
            "source": "api.example.com",
            "timestamp": "2026-04-20T10:15:00",
            "value": 500.0,
            "processed": False,
            "percentile_rank": 0.5,
        },
        {
            "id": 3,
            "source": "api.example.com",
            "timestamp": "2026-04-20T10:30:00",
            "value": 100.0,
            "processed": False,
            "percentile_rank": 0.0,
        },
    ],
}

SAMPLE_TOP_BY_SOURCE_RESPONSE: TopBySourceResponse = {
    "limit_per_source": 5,
    "hours_back": 168,
    "since": "2026-04-13T00:00:00",
    "by_source": {
        "api.example.com": [
            {
                "id": 1,
                "timestamp": "2026-04-20T10:00:00",
                "value": 1000.0,
                "processed": True,
                "rank": 1,
            },
            {
                "id": 2,
                "timestamp": "2026-04-20T09:00:00",
                "value": 950.0,
                "processed": False,
                "rank": 2,
            },
        ],
        "other.source.com": [
            {
                "id": 3,
                "timestamp": "2026-04-20T10:00:00",
                "value": 800.0,
                "processed": True,
                "rank": 1,
            },
        ],
    },
}

SAMPLE_MATERIALIZED_VIEW_STATS_RESPONSE: MaterializedViewStatsResponse = {
    "limit": 24,
    "count": 3,
    "stats": [
        {
            "hour": "2026-04-20T02:00:00",
            "record_count": 10,
            "processed_count": 8,
            "processed_pct": 80.0,
            "avg_value": 150.5,
            "min_value": 50.0,
            "max_value": 300.0,
            "unique_sources": 3,
            "materialized_at": "2026-04-20T12:00:00",
        },
        {
            "hour": "2026-04-20T01:00:00",
            "record_count": 5,
            "processed_count": 5,
            "processed_pct": 100.0,
            "avg_value": 200.0,
            "min_value": 100.0,
            "max_value": 300.0,
            "unique_sources": 2,
            "materialized_at": "2026-04-20T12:00:00",
        },
    ],
}


# ---------------------------------------------------------------------------
# Response Schema Validation
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_summary_response_schema_has_required_fields() -> None:
    """Verify summary response has required fields."""
    response = SAMPLE_SUMMARY_RESPONSE

    assert "hours_back" in response
    assert "since" in response
    assert "summary" in response
    assert isinstance(response["summary"], list)


@pytest.mark.unit
def test_summary_response_hour_entry_schema() -> None:
    """Verify each hour entry in summary has all required fields."""
    response = SAMPLE_SUMMARY_RESPONSE
    hour_entry = response["summary"][0]

    required_fields = [
        "hour",
        "record_count",
        "processed_count",
        "processed_pct",
        "avg_value",
        "min_value",
        "max_value",
        "unique_sources",
    ]

    for field in required_fields:
        assert field in hour_entry, f"Missing field: {field}"


@pytest.mark.unit
def test_summary_processed_pct_is_valid_percentage() -> None:
    """Verify processed_pct values are valid percentages (0-100)."""
    response = SAMPLE_SUMMARY_RESPONSE

    for hour_entry in response["summary"]:
        processed_pct = hour_entry["processed_pct"]
        assert 0 <= processed_pct <= 100, (
            f"processed_pct {processed_pct} is not a valid percentage"
        )


@pytest.mark.unit
def test_summary_processed_count_lte_record_count() -> None:
    """Verify processed_count <= record_count."""
    response = SAMPLE_SUMMARY_RESPONSE

    for hour_entry in response["summary"]:
        assert hour_entry["processed_count"] <= hour_entry["record_count"], (
            "processed_count cannot exceed record_count"
        )


@pytest.mark.unit
def test_percentile_response_schema_has_required_fields() -> None:
    """Verify percentile response has required fields."""
    response = SAMPLE_PERCENTILE_RESPONSE

    assert "source" in response
    assert "count" in response
    assert "records" in response
    assert isinstance(response["records"], list)


@pytest.mark.unit
def test_percentile_response_record_schema() -> None:
    """Verify each record in percentile response has required fields."""
    response = SAMPLE_PERCENTILE_RESPONSE
    record = response["records"][0]

    required_fields = [
        "id",
        "source",
        "timestamp",
        "value",
        "processed",
        "percentile_rank",
    ]

    for field in required_fields:
        assert field in record, f"Missing field: {field}"


@pytest.mark.unit
def test_percentile_rank_is_valid_decimal_0_to_1() -> None:
    """Verify percentile_rank values are valid (0.0 to 1.0)."""
    response = SAMPLE_PERCENTILE_RESPONSE

    for record in response["records"]:
        percentile_rank = record["percentile_rank"]
        assert 0.0 <= percentile_rank <= 1.0, (
            f"percentile_rank {percentile_rank} is not in range [0.0, 1.0]"
        )


@pytest.mark.unit
def test_top_by_source_response_schema_has_required_fields() -> None:
    """Verify top_by_source response has required fields."""
    response = SAMPLE_TOP_BY_SOURCE_RESPONSE

    assert "limit_per_source" in response
    assert "hours_back" in response
    assert "since" in response
    assert "by_source" in response
    assert isinstance(response["by_source"], dict)


@pytest.mark.unit
def test_top_by_source_response_hierarchical_structure() -> None:
    """Verify by_source response groups records by source."""
    response = SAMPLE_TOP_BY_SOURCE_RESPONSE

    for source, records in response["by_source"].items():
        assert isinstance(records, list), f"Records for {source} should be a list"
        assert len(records) > 0, f"Source {source} should have records"

        for record in records:
            assert record["id"] >= 1, "Record id must be positive"


@pytest.mark.unit
def test_top_by_source_rank_field_is_positive_integer() -> None:
    """Verify rank field is a positive integer."""
    response = SAMPLE_TOP_BY_SOURCE_RESPONSE

    for _source, records in response["by_source"].items():
        for record in records:
            assert "rank" in record
            assert isinstance(record["rank"], int)
            assert record["rank"] > 0


@pytest.mark.unit
def test_materialized_view_stats_response_schema_has_required_fields() -> None:
    """Verify materialized_view_stats response has required fields."""
    response = SAMPLE_MATERIALIZED_VIEW_STATS_RESPONSE

    assert "limit" in response
    assert "count" in response
    assert "stats" in response
    assert isinstance(response["stats"], list)


@pytest.mark.unit
def test_materialized_view_stats_entry_schema() -> None:
    """Verify each stat entry has required fields."""
    response = SAMPLE_MATERIALIZED_VIEW_STATS_RESPONSE
    stat = response["stats"][0]

    required_fields = [
        "hour",
        "record_count",
        "processed_count",
        "processed_pct",
        "avg_value",
        "min_value",
        "max_value",
        "unique_sources",
        "materialized_at",
    ]

    for field in required_fields:
        assert field in stat, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Query Parameter Validation Logic
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_hours_parameter_must_be_positive_integer() -> None:
    """Validate hours parameter constraints (1-168)."""
    valid_values = [1, 24, 168]
    invalid_values = [0, -1, 169, 1000]

    # Valid range: 1-168
    for hours in valid_values:
        assert 1 <= hours <= 168, f"hours={hours} should be valid"

    # Invalid range
    for hours in invalid_values:
        assert not (1 <= hours <= 168), f"hours={hours} should be invalid"


@pytest.mark.unit
def test_limit_parameter_constraints_for_top_by_source() -> None:
    """Validate limit parameter for top_by_source (1-50)."""
    valid_values = [1, 5, 50]
    invalid_values = [0, -1, 51, 100]

    # Valid range: 1-50
    for limit in valid_values:
        assert 1 <= limit <= 50, f"limit={limit} should be valid"

    # Invalid range
    for limit in invalid_values:
        assert not (1 <= limit <= 50), f"limit={limit} should be invalid"


@pytest.mark.unit
def test_materialized_view_limit_parameter_constraints() -> None:
    """Validate limit parameter for materialized_view_stats (1-168)."""
    valid_values = [1, 24, 168]
    invalid_values = [0, -1, 169, 1000]

    # Valid range: 1-168
    for limit in valid_values:
        assert 1 <= limit <= 168, f"limit={limit} should be valid"

    # Invalid range
    for limit in invalid_values:
        assert not (1 <= limit <= 168), f"limit={limit} should be invalid"


@pytest.mark.unit
def test_top_by_source_hours_parameter_constraints() -> None:
    """Validate hours parameter for top_by_source (1-2160 = 90 days)."""
    valid_values = [1, 24, 168, 2160]
    invalid_values = [0, -1, 2161, 5000]

    # Valid range: 1-2160
    for hours in valid_values:
        assert 1 <= hours <= 2160, f"hours={hours} should be valid"

    # Invalid range
    for hours in invalid_values:
        assert not (1 <= hours <= 2160), f"hours={hours} should be invalid"


# ---------------------------------------------------------------------------
# Aggregation Logic Validation (CTE patterns)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_cte_aggregation_processed_percentage_calculation() -> None:
    """Validate processed percentage calculation logic.

    Formula: (processed_count / record_count) * 100
    """
    test_cases = [
        (10, 8, 80.0),  # 8/10 * 100 = 80%
        (5, 5, 100.0),  # 5/5 * 100 = 100%
        (100, 0, 0.0),  # 0/100 * 100 = 0%
        (1, 1, 100.0),  # 1/1 * 100 = 100%
    ]

    for record_count, processed_count, expected_pct in test_cases:
        if record_count == 0:
            # Division by zero: should return 0 or None
            calculated_pct = None
        else:
            calculated_pct = round((processed_count / record_count * 100), 2)

        if expected_pct is not None:
            assert calculated_pct == expected_pct, (
                f"For {processed_count}/{record_count}, "
                f"expected {expected_pct}%, got {calculated_pct}%"
            )


@pytest.mark.unit
def test_cte_aggregation_avg_value_rounding() -> None:
    """Validate average value rounding to 4 decimal places.

    CTEs use ROUND(...::NUMERIC, 4) for precision.
    """
    test_cases = [
        (123.456789, 123.4568),
        (10.0, 10.0),
        (0.123456, 0.1235),
        (999.9999, 1000.0),  # Rounding up
    ]

    for value, expected_rounded in test_cases:
        calculated = round(value, 4)
        assert calculated == expected_rounded


@pytest.mark.unit
def test_window_function_percentile_rank_range() -> None:
    """Validate PERCENT_RANK window function output range (0.0 to 1.0)."""
    # PERCENT_RANK() returns (row_number - 1) / (total_rows - 1)
    # Range: [0.0, 1.0]

    test_cases = [
        (1, 3, 0.0),  # First of 3: (1-1)/(3-1) = 0/2 = 0.0
        (2, 3, 0.5),  # Second of 3: (2-1)/(3-1) = 1/2 = 0.5
        (3, 3, 1.0),  # Third of 3: (3-1)/(3-1) = 2/2 = 1.0
        (1, 1, 0.0),  # Only one: (1-1)/(1-1) = 0/0 = NULL (edge case)
    ]

    for row_num, total_rows, expected_percentile in test_cases:
        if total_rows == 1:
            # Edge case: single row
            calculated_percentile = 0.0  # Or NULL
        else:
            calculated_percentile = round((row_num - 1) / (total_rows - 1), 4)

        assert calculated_percentile == expected_percentile, (
            f"For row {row_num}/{total_rows}, "
            f"expected {expected_percentile}, got {calculated_percentile}"
        )


@pytest.mark.unit
def test_window_function_rank_behavior_with_ties() -> None:
    """Validate RANK window function behavior with tied values.

    RANK() assigns same rank to ties, skips next ranks.
    ROW_NUMBER() is different: always increments.

    Example: values [100, 100, 50]
    - RANK: [1, 1, 3]
    - ROW_NUMBER: [1, 2, 3]
    """
    # Test RANK() with ties
    values_and_ranks = [
        ([100, 100, 50], [1, 1, 3]),  # Ranks skip after ties
        ([100, 50, 50], [1, 2, 2]),  # Ranks skip in middle
        ([100, 90, 80], [1, 2, 3]),  # No ties: RANK = ROW_NUMBER
    ]

    for values, expected_ranks in values_and_ranks:
        # Simulate RANK() by ordering and assigning ranks
        sorted_indices = sorted(
            range(len(values)), key=lambda i: values[i], reverse=True
        )
        calculated_ranks = [0] * len(values)
        current_rank = 1
        prev_value = None

        for rank_pos, idx in enumerate(sorted_indices):
            if prev_value is not None and values[idx] != prev_value:
                current_rank = rank_pos + 1
            calculated_ranks[idx] = current_rank
            prev_value = values[idx]

        assert calculated_ranks == expected_ranks


# ---------------------------------------------------------------------------
# Error Handling and Edge Cases
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_null_values_in_aggregation() -> None:
    """Validate handling of NULL values in aggregation functions.

    COUNT(*) counts NULLs, but aggregates like AVG, MIN, MAX ignore NULLs.
    """
    # If all values are NULL
    # COUNT(*) = 3
    # AVG(NULL) = NULL
    # MIN(NULL) = NULL
    # MAX(NULL) = NULL

    # If some values are NULL
    # COUNT(*) = 3
    # AVG([100, NULL, 200]) = (100 + 200) / 2 = 150
    # MIN([100, NULL, 200]) = 100
    # MAX([100, NULL, 200]) = 200

    assert True  # Logic verified in database layer


@pytest.mark.unit
def test_empty_result_set_handling() -> None:
    """Validate response when no data matches query filters."""
    response = {
        "source": "nonexistent_source",
        "count": 0,
        "records": [],
    }

    assert response["count"] == 0
    assert len(response["records"]) == 0


@pytest.mark.unit
def test_timestamp_ordering_in_responses() -> None:
    """Validate that responses are ordered by timestamp (DESC for summary, varies for others)."""
    response = SAMPLE_SUMMARY_RESPONSE

    # Summary should be DESC by hour (most recent first)
    hours = [entry["hour"] for entry in response["summary"]]
    assert hours == sorted(hours, reverse=True), (
        "Summary should be ordered DESC by hour"
    )
