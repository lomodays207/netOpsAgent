"""Tracing cleanup loop helpers."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any, Callable

from .constants import DEFAULT_TRACE_RETENTION_DAYS, ENV_ENABLE_TRACING, ENV_TRACE_RETENTION_DAYS
from .metrics import record_trace_cleanup


def _parse_bool_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int_env(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return parsed if parsed > 0 else default


def is_tracing_enabled() -> bool:
    return _parse_bool_env(os.getenv(ENV_ENABLE_TRACING), False)


def get_trace_retention_days() -> int:
    return _parse_int_env(os.getenv(ENV_TRACE_RETENTION_DAYS), DEFAULT_TRACE_RETENTION_DAYS)


def seconds_until_next_cleanup(now: datetime | None = None, hour: int = 2) -> float:
    current = now or datetime.now()
    next_run = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    if current >= next_run:
        next_run = next_run + timedelta(days=1)
    return max((next_run - current).total_seconds(), 0.0)


async def run_trace_cleanup_once(database: Any, retention_days: int) -> int:
    deleted = await database.delete_expired_traces(retention_days)
    record_trace_cleanup(deleted_count=deleted, success=True)
    return deleted


async def trace_cleanup_loop(
    database: Any,
    retention_days: int,
    sleep_func: Callable[[float], Any] = asyncio.sleep,
) -> None:
    try:
        while True:
            await sleep_func(seconds_until_next_cleanup())
            try:
                deleted = await run_trace_cleanup_once(database, retention_days)
                if deleted > 0:
                    print(f"[TraceCleanup] deleted {deleted} expired traces")
            except Exception as exc:
                record_trace_cleanup(success=False)
                print(f"[TraceCleanup] cleanup failed: {exc}")
    except asyncio.CancelledError:
        raise


def start_trace_cleanup_loop(
    database: Any,
    retention_days: int | None = None,
    task_factory: Callable[[Any], Any] = asyncio.create_task,
):
    if not is_tracing_enabled():
        return None

    resolved_retention_days = retention_days or get_trace_retention_days()
    return task_factory(trace_cleanup_loop(database, resolved_retention_days))
