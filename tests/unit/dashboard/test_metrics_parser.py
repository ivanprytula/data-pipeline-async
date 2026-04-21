"""Unit tests for dashboard metrics parsing."""

from services.dashboard.routers.sse import _parse_prometheus_text


# -----------------------------------------------------------------------
# Prometheus Text Format Parsing
# -----------------------------------------------------------------------
async def test_parse_prometheus_text_extracts_http_counters() -> None:
    """Parse Prometheus text format and extract HTTP request counters."""
    prometheus_output = """# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} 1234.0
http_requests_total{method="POST",status="201"} 567.0
# HELP records_created_total Total records created
# TYPE records_created_total counter
records_created_total 890.0
"""
    result = _parse_prometheus_text(prometheus_output)

    assert result['http_requests_total{method="GET",status="200"}'] == 1234.0
    assert result['http_requests_total{method="POST",status="201"}'] == 567.0
    assert result["records_created_total"] == 890.0


async def test_parse_prometheus_text_ignores_comments() -> None:
    """Comments and blank lines are skipped."""
    prometheus_output = """# HELP http_requests_total Help text
# TYPE http_requests_total counter

http_requests_total 42.0
"""
    result = _parse_prometheus_text(prometheus_output)

    assert result["http_requests_total"] == 42.0
    assert len(result) == 1


async def test_parse_prometheus_text_handles_missing_metrics() -> None:
    """If no matching metrics exist, return empty dict."""
    prometheus_output = """# HELP unrelated_metric Unrelated metric
# TYPE unrelated_metric gauge
unrelated_metric 100.0
"""
    result = _parse_prometheus_text(prometheus_output)

    # Should be empty since we only look for http_requests_total, etc.
    assert result == {}


async def test_parse_prometheus_text_handles_invalid_values() -> None:
    """Non-numeric values are skipped gracefully."""
    prometheus_output = """http_requests_total not_a_number
http_responses_total 200.0
"""
    result = _parse_prometheus_text(prometheus_output)

    # "not_a_number" fails to parse, is skipped
    # but "http_responses_total" should still be included
    assert result["http_responses_total"] == 200.0
    assert "http_requests_total" not in result


async def test_parse_prometheus_text_handles_empty_input() -> None:
    """Empty or comment-only input returns empty dict."""
    result = _parse_prometheus_text("")
    assert result == {}

    result = _parse_prometheus_text("# Only comments\n# More comments")
    assert result == {}
