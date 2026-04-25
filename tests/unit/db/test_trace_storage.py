from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.db.database import SessionDatabase


def _fetch_one(db_path: Path, query: str, params: tuple = ()) -> tuple | None:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(query, params)
        return cursor.fetchone()
    finally:
        conn.close()


def _fetch_all(db_path: Path, query: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_initialize_creates_trace_tables_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-test.db"
    database = SessionDatabase(str(db_path))

    await database.initialize()

    tables = {
        row[0]
        for row in _fetch_all(
            db_path,
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        )
    }
    indexes = {
        row[0]
        for row in _fetch_all(
            db_path,
            "SELECT name FROM sqlite_master WHERE type = 'index'",
        )
    }

    assert {"traces", "reasoning_steps", "tool_calls"}.issubset(tables)
    assert "idx_traces_session_id" in indexes
    assert "idx_traces_created_at" in indexes


@pytest.mark.asyncio
async def test_create_and_update_trace_persists_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-test.db"
    database = SessionDatabase(str(db_path))
    await database.initialize()

    created = await database.create_trace(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "session_id": "session-1",
            "user_input": "10.0.1.10到10.0.2.20端口80不通",
            "request_type": "diagnosis",
            "status": "running",
            "created_at": "2026-04-24T20:00:00+08:00",
            "completed_at": None,
            "total_time": None,
            "final_answer": None,
            "error_message": None,
        }
    )

    updated = await database.update_trace(
        "trace_20260424T120000Z_ab12cd34",
        {
            "status": "completed",
            "completed_at": "2026-04-24T20:00:05+08:00",
            "total_time": 5.0,
            "final_answer": "防火墙拦截导致不通",
        },
    )

    row = _fetch_one(
        db_path,
        """
        SELECT status, completed_at, total_time, final_answer
        FROM traces
        WHERE trace_id = ?
        """,
        ("trace_20260424T120000Z_ab12cd34",),
    )

    assert created is True
    assert updated is True
    assert row == (
        "completed",
        "2026-04-24T20:00:05+08:00",
        5.0,
        "防火墙拦截导致不通",
    )


@pytest.mark.asyncio
async def test_add_reasoning_step_and_tool_call_records(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-test.db"
    database = SessionDatabase(str(db_path))
    await database.initialize()
    await database.create_trace(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "session_id": "session-1",
            "user_input": "诊断请求",
            "request_type": "diagnosis",
            "status": "running",
            "created_at": "2026-04-24T20:00:00+08:00",
            "completed_at": None,
            "total_time": None,
            "final_answer": None,
            "error_message": None,
        }
    )

    reasoning_added = await database.add_reasoning_step(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 1,
            "reasoning_content": "先检查目标端口是否监听",
            "timestamp": "2026-04-24T20:00:01+08:00",
        }
    )
    tool_created = await database.create_tool_call(
        {
            "tool_call_id": "tool_trace_1",
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 1,
            "tool_name": "check_port_alive",
            "arguments": '{"host":"10.0.2.20","port":80}',
            "status": "running",
            "started_at": "2026-04-24T20:00:01+08:00",
            "completed_at": None,
            "execution_time": None,
            "result": None,
        }
    )
    tool_completed = await database.complete_tool_call(
        "tool_trace_1",
        {
            "status": "success",
            "result": '{"alive":false}',
            "completed_at": "2026-04-24T20:00:02+08:00",
            "execution_time": 1.02,
        },
    )

    reasoning_row = _fetch_one(
        db_path,
        """
        SELECT trace_id, step_number, reasoning_content
        FROM reasoning_steps
        WHERE trace_id = ?
        """,
        ("trace_20260424T120000Z_ab12cd34",),
    )
    tool_row = _fetch_one(
        db_path,
        """
        SELECT tool_name, status, result, execution_time
        FROM tool_calls
        WHERE tool_call_id = ?
        """,
        ("tool_trace_1",),
    )

    assert reasoning_added is True
    assert tool_created is True
    assert tool_completed is True
    assert reasoning_row == (
        "trace_20260424T120000Z_ab12cd34",
        1,
        "先检查目标端口是否监听",
    )
    assert tool_row == ("check_port_alive", "success", '{"alive":false}', 1.02)


@pytest.mark.asyncio
async def test_trace_foreign_key_cascade_removes_children(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-test.db"
    database = SessionDatabase(str(db_path))
    await database.initialize()
    await database.create_trace(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "session_id": "session-1",
            "user_input": "诊断请求",
            "request_type": "diagnosis",
            "status": "running",
            "created_at": "2026-04-24T20:00:00+08:00",
            "completed_at": None,
            "total_time": None,
            "final_answer": None,
            "error_message": None,
        }
    )
    await database.add_reasoning_step(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 1,
            "reasoning_content": "推理内容",
            "timestamp": "2026-04-24T20:00:01+08:00",
        }
    )
    await database.create_tool_call(
        {
            "tool_call_id": "tool_trace_1",
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 1,
            "tool_name": "check_port_alive",
            "arguments": "{}",
            "status": "running",
            "started_at": "2026-04-24T20:00:01+08:00",
            "completed_at": None,
            "execution_time": None,
            "result": None,
        }
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM traces WHERE trace_id = ?", ("trace_20260424T120000Z_ab12cd34",))
        conn.commit()
    finally:
        conn.close()

    assert _fetch_one(
        db_path,
        "SELECT COUNT(*) FROM reasoning_steps WHERE trace_id = ?",
        ("trace_20260424T120000Z_ab12cd34",),
    ) == (0,)
    assert _fetch_one(
        db_path,
        "SELECT COUNT(*) FROM tool_calls WHERE trace_id = ?",
        ("trace_20260424T120000Z_ab12cd34",),
    ) == (0,)


async def _seed_queryable_traces(database: SessionDatabase) -> None:
    await database.create_trace(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "session_id": "session-1",
            "user_input": "check port 80 connectivity",
            "request_type": "diagnosis",
            "status": "running",
            "created_at": "2026-04-24T20:00:00+08:00",
            "completed_at": None,
            "total_time": None,
            "final_answer": None,
            "error_message": None,
        }
    )
    await database.create_trace(
        {
            "trace_id": "trace_20260424T121000Z_cd34ef56",
            "session_id": "session-1",
            "user_input": "firewall policy blocks traffic",
            "request_type": "diagnosis",
            "status": "completed",
            "created_at": "2026-04-24T20:10:00+08:00",
            "completed_at": "2026-04-24T20:10:05+08:00",
            "total_time": 5.0,
            "final_answer": "blocked by firewall",
            "error_message": None,
        }
    )
    await database.create_trace(
        {
            "trace_id": "trace_20260423T080000Z_ef56ab78",
            "session_id": "session-2",
            "user_input": "show me a quick summary",
            "request_type": "general_chat",
            "status": "failed",
            "created_at": "2026-04-23T08:00:00+08:00",
            "completed_at": "2026-04-23T08:00:02+08:00",
            "total_time": 2.0,
            "final_answer": None,
            "error_message": "tool error",
        }
    )

    await database.add_reasoning_step(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 2,
            "reasoning_content": "second step",
            "timestamp": "2026-04-24T20:00:02+08:00",
        }
    )
    await database.add_reasoning_step(
        {
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 1,
            "reasoning_content": "first step",
            "timestamp": "2026-04-24T20:00:01+08:00",
        }
    )
    await database.create_tool_call(
        {
            "tool_call_id": "tool_trace_2",
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 2,
            "tool_name": "check_acl",
            "arguments": "{}",
            "status": "success",
            "started_at": "2026-04-24T20:00:02+08:00",
            "completed_at": "2026-04-24T20:00:03+08:00",
            "execution_time": 1.0,
            "result": '{"allowed": false}',
        }
    )
    await database.create_tool_call(
        {
            "tool_call_id": "tool_trace_1",
            "trace_id": "trace_20260424T120000Z_ab12cd34",
            "step_number": 1,
            "tool_name": "check_port_alive",
            "arguments": "{}",
            "status": "success",
            "started_at": "2026-04-24T20:00:01+08:00",
            "completed_at": "2026-04-24T20:00:02+08:00",
            "execution_time": 1.0,
            "result": '{"alive": false}',
        }
    )


@pytest.mark.asyncio
async def test_list_traces_supports_filters_query_and_pagination(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-test.db"
    database = SessionDatabase(str(db_path))
    await database.initialize()
    await _seed_queryable_traces(database)

    page_one = await database.list_traces(page=1, page_size=1)
    filtered = await database.list_traces(
        page=1,
        page_size=20,
        session_id="session-1",
        request_type="diagnosis",
        start_time="2026-04-24T00:00:00+08:00",
        end_time="2026-04-24T23:59:59+08:00",
        query="firewall",
    )
    by_session_query = await database.list_traces(page=1, page_size=20, query="session-2")
    by_trace_query = await database.list_traces(
        page=1,
        page_size=20,
        query="trace_20260424T120000Z_ab12cd34",
    )

    assert page_one["total"] == 3
    assert [item["trace_id"] for item in page_one["items"]] == ["trace_20260424T121000Z_cd34ef56"]
    assert filtered["total"] == 1
    assert [item["trace_id"] for item in filtered["items"]] == ["trace_20260424T121000Z_cd34ef56"]
    assert [item["trace_id"] for item in by_session_query["items"]] == ["trace_20260423T080000Z_ef56ab78"]
    assert [item["trace_id"] for item in by_trace_query["items"]] == ["trace_20260424T120000Z_ab12cd34"]


@pytest.mark.asyncio
async def test_get_trace_detail_and_list_session_traces_sort_records(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-test.db"
    database = SessionDatabase(str(db_path))
    await database.initialize()
    await _seed_queryable_traces(database)

    detail = await database.get_trace_detail("trace_20260424T120000Z_ab12cd34")
    session_traces = await database.list_session_traces("session-1")

    assert detail is not None
    assert detail["trace"]["trace_id"] == "trace_20260424T120000Z_ab12cd34"
    assert [step["step_number"] for step in detail["reasoning_steps"]] == [1, 2]
    assert [call["step_number"] for call in detail["tool_calls"]] == [1, 2]
    assert [item["trace_id"] for item in session_traces] == [
        "trace_20260424T120000Z_ab12cd34",
        "trace_20260424T121000Z_cd34ef56",
    ]


@pytest.mark.asyncio
async def test_get_trace_stats_export_and_delete_expired_traces(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-test.db"
    database = SessionDatabase(str(db_path))
    await database.initialize()

    now = datetime.now(timezone.utc)
    trace_rows = [
        {
            "trace_id": "trace_recent_completed",
            "session_id": "session-a",
            "user_input": "recent completed trace",
            "request_type": "diagnosis",
            "status": "completed",
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "completed_at": now.isoformat(),
            "total_time": 10.0,
            "final_answer": "ok",
            "error_message": None,
        },
        {
            "trace_id": "trace_week_failed",
            "session_id": "session-b",
            "user_input": "weekly failed trace",
            "request_type": "general_chat",
            "status": "failed",
            "created_at": (now - timedelta(days=2)).isoformat(),
            "completed_at": None,
            "total_time": 20.0,
            "final_answer": None,
            "error_message": "boom",
        },
        {
            "trace_id": "trace_old_running",
            "session_id": "session-c",
            "user_input": "old running trace",
            "request_type": "diagnosis",
            "status": "running",
            "created_at": (now - timedelta(days=10)).isoformat(),
            "completed_at": None,
            "total_time": None,
            "final_answer": None,
            "error_message": None,
        },
    ]
    for row in trace_rows:
        await database.create_trace(row)

    stats = await database.get_trace_stats()
    exported = await database.export_traces(page=1, page_size=2000)
    deleted = await database.delete_expired_traces(retention_days=7)
    remaining = await database.list_traces(page=1, page_size=20)

    assert stats["total"] == 3
    assert stats["by_request_type"] == {"diagnosis": 2, "general_chat": 1}
    assert stats["by_status"] == {"completed": 1, "failed": 1, "running": 1}
    assert stats["average_total_time"] == 15.0
    assert stats["last_24_hours"] == 1
    assert stats["last_7_days"] == 2
    assert len(exported) == 3
    assert deleted == 1
    assert remaining["total"] == 2
