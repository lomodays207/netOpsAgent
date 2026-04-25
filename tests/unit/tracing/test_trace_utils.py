from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from src.tracing.utils import (
    REDACTED_VALUE,
    build_trace_id,
    calculate_total_time,
    mask_sensitive_data,
    truncate_json_payload,
    truncate_text,
)


def test_build_trace_id_uses_expected_prefix_and_shape() -> None:
    trace_id = build_trace_id()

    assert re.match(r"^trace_\d{8}T\d{6}Z_[0-9a-f]{8}$", trace_id)


def test_mask_sensitive_data_masks_nested_sensitive_fields() -> None:
    payload = {
        "username": "alice",
        "password": "super-secret",
        "nested": {
            "access_token": "token-value",
            "apiKey": "api-key-value",
        },
        "items": [
            {"secret": "top-secret"},
            {"comment": "keep me"},
        ],
    }

    masked = mask_sensitive_data(payload)

    assert masked["username"] == "alice"
    assert masked["password"] == REDACTED_VALUE
    assert masked["nested"]["access_token"] == REDACTED_VALUE
    assert masked["nested"]["apiKey"] == REDACTED_VALUE
    assert masked["items"][0]["secret"] == REDACTED_VALUE
    assert masked["items"][1]["comment"] == "keep me"


def test_truncate_text_returns_original_when_not_over_limit() -> None:
    assert truncate_text("short text", max_bytes=64) == "short text"


def test_truncate_text_marks_and_limits_large_content() -> None:
    truncated = truncate_text("a" * 200, max_bytes=32)

    assert "[truncated]" in truncated
    assert len(truncated.encode("utf-8")) <= 32


def test_truncate_text_returns_empty_string_for_none() -> None:
    assert truncate_text(None, max_bytes=16) == ""


def test_truncate_json_payload_serializes_and_limits_bytes() -> None:
    payload = {
        "summary": "x" * 200,
        "items": [{"name": "n-1", "password": "secret"}],
    }

    serialized = truncate_json_payload(payload, max_bytes=64)

    assert "[truncated]" in serialized
    assert len(serialized.encode("utf-8")) <= 64


def test_truncate_json_payload_returns_empty_json_for_none() -> None:
    assert truncate_json_payload(None, max_bytes=32) == "{}"


def test_calculate_total_time_returns_elapsed_seconds() -> None:
    started_at = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(seconds=5, milliseconds=250)

    assert calculate_total_time(started_at, completed_at) == 5.25


def test_calculate_total_time_returns_none_for_missing_endpoints() -> None:
    started_at = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)

    assert calculate_total_time(None, started_at) is None
    assert calculate_total_time(started_at, None) is None
