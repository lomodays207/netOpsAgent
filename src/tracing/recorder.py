"""Trace recording facade."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .constants import (
    DEFAULT_TRACE_REASONING_MAX_BYTES,
    DEFAULT_TRACE_TOOL_RESULT_MAX_BYTES,
    ENV_ENABLE_TRACING,
    ENV_TRACE_REASONING_MAX_BYTES,
    ENV_TRACE_TOOL_RESULT_MAX_BYTES,
    TOOL_CALL_STATUS_SUCCESS,
    TRACE_STATUS_COMPLETED,
    TRACE_STATUS_FAILED,
    TRACE_STATUS_INTERRUPTED,
    TRACE_STATUS_RUNNING,
)
from .metrics import record_trace_write
from .utils import (
    build_trace_id,
    calculate_total_time,
    mask_sensitive_data,
    truncate_json_payload,
    truncate_text,
)


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


class TraceRecorder:
    """Fire-and-forget trace writer around SessionDatabase methods."""

    def __init__(
        self,
        database: Any,
        enabled: bool | None = None,
        reasoning_max_bytes: int | None = None,
        tool_result_max_bytes: int | None = None,
        task_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        self.database = database
        self.enabled = (
            enabled
            if enabled is not None
            else _parse_bool_env(os.getenv(ENV_ENABLE_TRACING), False)
        )
        self.reasoning_max_bytes = reasoning_max_bytes or _parse_int_env(
            os.getenv(ENV_TRACE_REASONING_MAX_BYTES),
            DEFAULT_TRACE_REASONING_MAX_BYTES,
        )
        self.tool_result_max_bytes = tool_result_max_bytes or _parse_int_env(
            os.getenv(ENV_TRACE_TOOL_RESULT_MAX_BYTES),
            DEFAULT_TRACE_TOOL_RESULT_MAX_BYTES,
        )
        self.task_factory = task_factory or asyncio.create_task
        self._trace_started_at: dict[str, datetime] = {}
        self._tool_started_at: dict[str, datetime] = {}
        self._trace_write_tasks: dict[str, Any] = {}
        self._tool_trace_ids: dict[str, str] = {}

    def start_trace(
        self,
        session_id: str | None,
        user_input: Any,
        request_type: str,
        trace_id: str | None = None,
        created_at: datetime | None = None,
    ) -> str:
        started_at = created_at or datetime.now(timezone.utc)
        resolved_trace_id = trace_id or build_trace_id(started_at)
        self._trace_started_at[resolved_trace_id] = started_at

        payload = {
            "trace_id": resolved_trace_id,
            "session_id": session_id,
            "user_input": truncate_text(user_input, self.tool_result_max_bytes),
            "request_type": request_type,
            "status": TRACE_STATUS_RUNNING,
            "created_at": started_at.isoformat(),
            "completed_at": None,
            "total_time": None,
            "final_answer": None,
            "error_message": None,
        }
        self._dispatch_call(self.database.create_trace, payload, trace_key=resolved_trace_id)
        return resolved_trace_id

    def add_reasoning_step(
        self,
        trace_id: str,
        step_number: int,
        content: Any,
        timestamp: datetime | None = None,
    ) -> None:
        payload = {
            "trace_id": trace_id,
            "step_number": step_number,
            "reasoning_content": truncate_text(content, self.reasoning_max_bytes),
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        }
        self._dispatch_call(self.database.add_reasoning_step, payload, trace_key=trace_id)

    def start_tool_call(
        self,
        trace_id: str,
        step_number: int | None,
        tool_name: str,
        arguments: Any,
        tool_call_id: str | None = None,
        started_at: datetime | None = None,
        status: str = TRACE_STATUS_RUNNING,
    ) -> str:
        resolved_started_at = started_at or datetime.now(timezone.utc)
        resolved_tool_call_id = tool_call_id or f"tool_{uuid.uuid4().hex[:8]}"
        self._tool_started_at[resolved_tool_call_id] = resolved_started_at
        self._tool_trace_ids[resolved_tool_call_id] = trace_id

        payload = {
            "tool_call_id": resolved_tool_call_id,
            "trace_id": trace_id,
            "step_number": step_number,
            "tool_name": tool_name,
            "arguments": truncate_json_payload(
                mask_sensitive_data(arguments),
                max(self.tool_result_max_bytes, 256),
            ),
            "status": status,
            "started_at": resolved_started_at.isoformat(),
            "completed_at": None,
            "execution_time": None,
            "result": None,
        }
        self._dispatch_call(self.database.create_tool_call, payload, trace_key=trace_id)
        return resolved_tool_call_id

    def complete_tool_call(
        self,
        tool_call_id: str,
        result: Any,
        completed_at: datetime | None = None,
        status: str = TOOL_CALL_STATUS_SUCCESS,
        execution_time: float | None = None,
    ) -> None:
        resolved_completed_at = completed_at or datetime.now(timezone.utc)
        started_at = self._tool_started_at.pop(tool_call_id, None)
        resolved_execution_time = execution_time
        if resolved_execution_time is None:
            resolved_execution_time = calculate_total_time(started_at, resolved_completed_at)
        trace_id = self._tool_trace_ids.pop(tool_call_id, None)

        payload = {
            "status": status,
            "result": truncate_json_payload(
                mask_sensitive_data(result),
                self.tool_result_max_bytes,
            ),
            "completed_at": resolved_completed_at.isoformat(),
            "execution_time": resolved_execution_time,
        }
        self._dispatch_call(
            self.database.complete_tool_call,
            tool_call_id,
            payload,
            trace_key=trace_id,
        )

    def complete_trace(
        self,
        trace_id: str,
        final_answer: Any,
        completed_at: datetime | None = None,
        total_time: float | None = None,
    ) -> None:
        self._finish_trace(
            trace_id=trace_id,
            status=TRACE_STATUS_COMPLETED,
            completed_at=completed_at,
            total_time=total_time,
            final_answer=final_answer,
            error_message=None,
        )

    def fail_trace(
        self,
        trace_id: str,
        error_message: Any,
        completed_at: datetime | None = None,
        total_time: float | None = None,
    ) -> None:
        self._finish_trace(
            trace_id=trace_id,
            status=TRACE_STATUS_FAILED,
            completed_at=completed_at,
            total_time=total_time,
            final_answer=None,
            error_message=error_message,
        )

    def interrupt_trace(
        self,
        trace_id: str,
        completed_at: datetime | None = None,
        total_time: float | None = None,
    ) -> None:
        self._finish_trace(
            trace_id=trace_id,
            status=TRACE_STATUS_INTERRUPTED,
            completed_at=completed_at,
            total_time=total_time,
            final_answer=None,
            error_message=None,
        )

    def _finish_trace(
        self,
        trace_id: str,
        status: str,
        completed_at: datetime | None,
        total_time: float | None,
        final_answer: Any,
        error_message: Any,
    ) -> None:
        resolved_completed_at = completed_at or datetime.now(timezone.utc)
        started_at = self._trace_started_at.pop(trace_id, None)
        resolved_total_time = total_time
        if resolved_total_time is None:
            resolved_total_time = calculate_total_time(started_at, resolved_completed_at)

        payload = {
            "status": status,
            "completed_at": resolved_completed_at.isoformat(),
            "total_time": resolved_total_time,
            "final_answer": truncate_text(final_answer, self.tool_result_max_bytes),
            "error_message": truncate_text(error_message, self.tool_result_max_bytes),
        }
        self._dispatch_call(self.database.update_trace, trace_id, payload, trace_key=trace_id)

    def _dispatch_call(
        self,
        method: Callable[..., Any],
        *args: Any,
        trace_key: str | None = None,
    ) -> None:
        if not self.enabled or self.database is None:
            return

        previous_task = self._trace_write_tasks.get(trace_key) if trace_key else None

        async def runner() -> None:
            if previous_task is not None:
                try:
                    await previous_task
                except Exception:
                    pass
            try:
                await method(*args)
                record_trace_write(True)
            except Exception as exc:
                record_trace_write(False)
                print(f"[TraceRecorder] tracing write failed: {exc}")

        task = self.task_factory(runner())
        if trace_key:
            self._trace_write_tasks[trace_key] = task

            if hasattr(task, "add_done_callback"):
                def _cleanup(completed_task: Any, key: str = trace_key) -> None:
                    if self._trace_write_tasks.get(key) is completed_task:
                        self._trace_write_tasks.pop(key, None)

                task.add_done_callback(_cleanup)
