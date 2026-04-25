from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.session_manager import SessionManager, SQLiteSessionManager
from src.tracing.cleanup import run_trace_cleanup_once
from src.tracing.recorder import TraceRecorder


class RecordingDB:
    def __init__(self) -> None:
        self.trace_creates: list[dict] = []
        self.reasoning_steps: list[dict] = []
        self.tool_creates: list[dict] = []
        self.tool_updates: list[tuple[str, dict]] = []
        self.trace_updates: list[tuple[str, dict]] = []
        self.cleanup_calls: list[int] = []

    async def create_trace(self, payload: dict) -> bool:
        self.trace_creates.append(payload)
        return True

    async def add_reasoning_step(self, payload: dict) -> bool:
        self.reasoning_steps.append(payload)
        return True

    async def create_tool_call(self, payload: dict) -> bool:
        self.tool_creates.append(payload)
        return True

    async def complete_tool_call(self, tool_call_id: str, payload: dict) -> bool:
        self.tool_updates.append((tool_call_id, payload))
        return True

    async def update_trace(self, trace_id: str, payload: dict) -> bool:
        self.trace_updates.append((trace_id, payload))
        return True

    async def delete_expired_traces(self, retention_days: int) -> int:
        self.cleanup_calls.append(retention_days)
        return 2


class FailingDB:
    async def create_trace(self, payload: dict) -> bool:
        raise RuntimeError("boom")

    async def add_reasoning_step(self, payload: dict) -> bool:
        raise RuntimeError("boom")

    async def create_tool_call(self, payload: dict) -> bool:
        raise RuntimeError("boom")

    async def complete_tool_call(self, tool_call_id: str, payload: dict) -> bool:
        raise RuntimeError("boom")

    async def update_trace(self, trace_id: str, payload: dict) -> bool:
        raise RuntimeError("boom")


def _schedule(tasks: list[asyncio.Task[object]]):
    def factory(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    return factory


@pytest.mark.asyncio
async def test_trace_recorder_is_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_TRACING", "false")
    database = RecordingDB()
    tasks: list[asyncio.Task[object]] = []
    recorder = TraceRecorder(database=database, task_factory=_schedule(tasks))

    trace_id = recorder.start_trace(
        session_id="session-1",
        user_input="diagnose connectivity",
        request_type="diagnosis",
    )
    tool_call_id = recorder.start_tool_call(
        trace_id=trace_id,
        step_number=1,
        tool_name="check_port_alive",
        arguments={"token": "secret"},
    )
    recorder.add_reasoning_step(trace_id=trace_id, step_number=1, content="reasoning")
    recorder.complete_tool_call(tool_call_id=tool_call_id, result={"alive": False})
    recorder.complete_trace(trace_id=trace_id, final_answer="done")

    assert trace_id.startswith("trace_")
    assert tool_call_id.startswith("tool_")
    assert tasks == []
    assert database.trace_creates == []
    assert database.reasoning_steps == []
    assert database.tool_creates == []
    assert database.tool_updates == []
    assert database.trace_updates == []


@pytest.mark.asyncio
async def test_trace_recorder_records_full_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_TRACING", "true")
    monkeypatch.setenv("TRACE_REASONING_MAX_BYTES", "24")
    monkeypatch.setenv("TRACE_TOOL_RESULT_MAX_BYTES", "40")

    database = RecordingDB()
    tasks: list[asyncio.Task[object]] = []
    recorder = TraceRecorder(database=database, task_factory=_schedule(tasks))

    started_at = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    trace_id = recorder.start_trace(
        session_id="session-1",
        user_input="diagnose connectivity",
        request_type="diagnosis",
        trace_id="trace_test_1",
        created_at=started_at,
    )
    recorder.add_reasoning_step(
        trace_id=trace_id,
        step_number=1,
        content="x" * 128,
        timestamp=started_at + timedelta(seconds=1),
    )
    tool_call_id = recorder.start_tool_call(
        trace_id=trace_id,
        step_number=1,
        tool_name="check_port_alive",
        arguments={"token": "secret", "nested": {"password": "hidden"}},
        tool_call_id="tool_test_1",
        started_at=started_at + timedelta(seconds=1),
    )
    recorder.complete_tool_call(
        tool_call_id=tool_call_id,
        result={"payload": "y" * 128},
        completed_at=started_at + timedelta(seconds=3),
    )
    recorder.complete_trace(
        trace_id=trace_id,
        final_answer="done",
        completed_at=started_at + timedelta(seconds=5),
    )

    await asyncio.gather(*tasks)

    assert len(database.trace_creates) == 1
    assert database.trace_creates[0]["trace_id"] == "trace_test_1"
    assert database.trace_creates[0]["status"] == "running"
    assert len(database.reasoning_steps) == 1
    assert database.reasoning_steps[0]["reasoning_content"].endswith("[truncated]")
    assert len(database.tool_creates) == 1
    assert '"token":"[REDACTED]"' in database.tool_creates[0]["arguments"]
    assert '"password":"[REDACTED]"' in database.tool_creates[0]["arguments"]
    assert len(database.tool_updates) == 1
    assert database.tool_updates[0][0] == "tool_test_1"
    assert database.tool_updates[0][1]["execution_time"] == 2.0
    assert "truncated" in database.tool_updates[0][1]["result"]
    assert len(database.trace_updates) == 1
    assert database.trace_updates[0][0] == "trace_test_1"
    assert database.trace_updates[0][1]["status"] == "completed"
    assert database.trace_updates[0][1]["total_time"] == 5.0


@pytest.mark.asyncio
async def test_trace_recorder_swallows_database_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_TRACING", "true")

    tasks: list[asyncio.Task[object]] = []
    recorder = TraceRecorder(database=FailingDB(), task_factory=_schedule(tasks))

    trace_id = recorder.start_trace(
        session_id="session-1",
        user_input="diagnose connectivity",
        request_type="diagnosis",
        trace_id="trace_test_1",
    )
    recorder.add_reasoning_step(trace_id=trace_id, step_number=1, content="reasoning")
    tool_call_id = recorder.start_tool_call(
        trace_id=trace_id,
        step_number=1,
        tool_name="check_port_alive",
        arguments={},
        tool_call_id="tool_test_1",
    )
    recorder.complete_tool_call(tool_call_id=tool_call_id, result={"alive": False})
    recorder.fail_trace(trace_id=trace_id, error_message="boom")

    await asyncio.gather(*tasks)

    assert all(task.done() for task in tasks)
    assert all(task.exception() is None for task in tasks)


@pytest.mark.asyncio
async def test_run_trace_cleanup_once_uses_retention_days() -> None:
    database = RecordingDB()

    deleted = await run_trace_cleanup_once(database, retention_days=14)

    assert deleted == 2
    assert database.cleanup_calls == [14]


@pytest.mark.asyncio
async def test_sqlite_session_manager_starts_trace_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = SQLiteSessionManager()
    manager.db = RecordingDB()
    manager._initialized = True

    async def fake_start_cleanup(self: SessionManager) -> None:
        self._cleanup_task = "session-cleanup-task"

    started: list[tuple[object, int]] = []

    def fake_start_trace_cleanup_loop(database: object, retention_days: int):
        started.append((database, retention_days))
        return "trace-cleanup-task"

    monkeypatch.setattr(SessionManager, "start_cleanup", fake_start_cleanup)
    monkeypatch.setattr("src.session_manager.is_tracing_enabled", lambda: True, raising=False)
    monkeypatch.setattr("src.session_manager.get_trace_retention_days", lambda: 14, raising=False)
    monkeypatch.setattr(
        "src.session_manager.start_trace_cleanup_loop",
        fake_start_trace_cleanup_loop,
        raising=False,
    )

    await manager.start_cleanup()

    assert manager._cleanup_task == "session-cleanup-task"
    assert manager._trace_cleanup_task == "trace-cleanup-task"
    assert started == [(manager.db, 14)]
