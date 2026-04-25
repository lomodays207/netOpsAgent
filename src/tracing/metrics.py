"""In-process runtime metrics for tracing."""

from __future__ import annotations

import os
from typing import Any

_RUNTIME_METRICS: dict[str, float | int] = {
    "write_success_count": 0,
    "write_failure_count": 0,
    "query_count": 0,
    "query_error_count": 0,
    "query_total_ms": 0.0,
    "cleanup_runs": 0,
    "cleanup_failures": 0,
    "cleanup_deleted_count": 0,
}


def reset_trace_runtime_metrics() -> None:
    for key in list(_RUNTIME_METRICS.keys()):
        _RUNTIME_METRICS[key] = 0.0 if "total_ms" in key else 0


def record_trace_write(success: bool) -> None:
    key = "write_success_count" if success else "write_failure_count"
    _RUNTIME_METRICS[key] += 1


def record_trace_query(duration_ms: float, success: bool) -> None:
    _RUNTIME_METRICS["query_count"] += 1
    _RUNTIME_METRICS["query_total_ms"] += max(float(duration_ms), 0.0)
    if not success:
        _RUNTIME_METRICS["query_error_count"] += 1


def record_trace_cleanup(deleted_count: int = 0, success: bool = True) -> None:
    _RUNTIME_METRICS["cleanup_runs"] += 1
    _RUNTIME_METRICS["cleanup_deleted_count"] += max(int(deleted_count), 0)
    if not success:
        _RUNTIME_METRICS["cleanup_failures"] += 1


def get_trace_runtime_metrics(database: Any | None = None) -> dict[str, Any]:
    metrics = dict(_RUNTIME_METRICS)
    query_count = int(metrics["query_count"])
    query_total_ms = float(metrics["query_total_ms"])
    metrics["average_query_ms"] = query_total_ms / query_count if query_count else None

    sqlite_file_size_bytes = None
    db_path = getattr(database, "db_path", None)
    if db_path and os.path.exists(db_path):
        sqlite_file_size_bytes = os.path.getsize(db_path)

    metrics["sqlite_file_size_bytes"] = sqlite_file_size_bytes
    return metrics
