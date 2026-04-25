from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage

from src.agent.general_chat_agent import GeneralChatToolAgent
from src.agent.llm_agent import LLMAgent
from src.db.database import SessionDatabase
from src.models.task import DiagnosticTask, FaultType, Protocol
from src.tracing.recorder import TraceRecorder


def _schedule(tasks: list[asyncio.Task[object]]):
    def factory(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    return factory


@pytest.fixture
async def trace_database(tmp_path):
    database = SessionDatabase(str(tmp_path / "traces_e2e.db"))
    await database.initialize()
    return database


def _build_task() -> DiagnosticTask:
    return DiagnosticTask(
        task_id="task-e2e-1",
        user_input="10.0.1.10 to 10.0.2.20 port 80 unreachable",
        source="10.0.1.10",
        target="10.0.2.20",
        protocol=Protocol.TCP,
        fault_type=FaultType.PORT_UNREACHABLE,
        port=80,
    )


@pytest.mark.asyncio
async def test_diagnosis_trace_e2e_persists_full_chain(trace_database: SessionDatabase, monkeypatch: pytest.MonkeyPatch):
    tasks: list[asyncio.Task[object]] = []
    recorder = TraceRecorder(database=trace_database, enabled=True, task_factory=_schedule(tasks))
    agent = LLMAgent(llm_client=object(), verbose=False, max_steps=3, trace_recorder=recorder)

    decisions = [
        {
            "reasoning": "先检查目标端口是否在监听",
            "tool_calls": [
                {
                    "id": "call-e2e-1",
                    "name": "check_port_alive",
                    "arguments": {"host": "10.0.2.20", "port": 80},
                }
            ],
            "conclude": False,
        },
        {
            "reasoning": "端口未监听，问题定位完成",
            "tool_calls": [],
            "conclude": True,
        },
    ]

    async def fake_decide(context, task):
        return decisions.pop(0)

    async def fake_execute(tool_call, task):
        return {"success": True, "stdout": "closed", "execution_time": 0.75}

    monkeypatch.setattr(agent, "_llm_decide_next_step", fake_decide)
    monkeypatch.setattr(agent, "_execute_tool", fake_execute)

    report = await agent.diagnose(_build_task(), session_id="session-e2e-diagnosis")
    await asyncio.gather(*tasks)

    assert report.root_cause == "端口未监听，问题定位完成"

    traces = await trace_database.list_session_traces("session-e2e-diagnosis")
    assert len(traces) == 1
    trace_id = traces[0]["trace_id"]

    detail = await trace_database.get_trace_detail(trace_id)
    assert detail is not None
    assert detail["trace"]["status"] == "completed"
    assert detail["trace"]["request_type"] == "diagnosis"
    assert len(detail["reasoning_steps"]) == 2
    assert len(detail["tool_calls"]) == 1
    assert detail["tool_calls"][0]["tool_name"] == "check_port_alive"


class FakeToolDB:
    async def query_access_relations(self, **kwargs):
        return {
            "items": [
                {
                    "src_system": "N-CRM",
                    "dst_system": "N-AQM",
                    "protocol": "TCP",
                    "port": "8080",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 50,
        }


class FakeSessionManager:
    def __init__(self) -> None:
        self.db = FakeToolDB()
        self.messages: list[dict] = []

    async def add_message(self, session_id, role, content, metadata=None):
        self.messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
        )


class FakeGeneralChatLLMClient:
    def __init__(self) -> None:
        self.round = 0

    def invoke_langchain_messages_with_tools(self, messages, tools, temperature=None, max_tokens=None):
        self.round += 1
        if self.round == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "chat-tool-1",
                        "name": "query_access_relations",
                        "args": {"system_code": "N-CRM", "direction": "outbound"},
                    }
                ],
            )
        return AIMessage(content="Found 1 outbound relation for N-CRM.")

    def invoke_langchain_messages(self, messages, temperature=None, max_tokens=None):
        return AIMessage(content="fallback")


@pytest.mark.asyncio
async def test_general_chat_trace_e2e_persists_tool_call_chain(trace_database: SessionDatabase):
    tasks: list[asyncio.Task[object]] = []
    recorder = TraceRecorder(database=trace_database, enabled=True, task_factory=_schedule(tasks))
    session_manager = FakeSessionManager()
    agent = GeneralChatToolAgent(
        llm_client=FakeGeneralChatLLMClient(),
        session_manager=session_manager,
        session_id="session-e2e-chat",
        trace_recorder=recorder,
    )

    answer = await agent.run(
        session_messages=[{"role": "user", "content": "查询 N-CRM 的访问关系", "metadata": {}}],
        system_prompt="test prompt",
    )
    await asyncio.gather(*tasks)

    assert answer == "Found 1 outbound relation for N-CRM."

    traces = await trace_database.list_session_traces("session-e2e-chat")
    assert len(traces) == 1

    detail = await trace_database.get_trace_detail(traces[0]["trace_id"])
    assert detail is not None
    assert detail["trace"]["status"] == "completed"
    assert detail["trace"]["request_type"] == "general_chat"
    assert detail["reasoning_steps"] == []
    assert len(detail["tool_calls"]) == 1
    assert detail["tool_calls"][0]["tool_name"] == "query_access_relations"
