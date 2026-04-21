import asyncio
import json
from types import SimpleNamespace

import src.api as api
from src.agent.intent_router import IntentDecision


class FakeSessionManager:
    def __init__(self, existing_session=None):
        self.existing_session = existing_session
        self.created_session = None
        self.messages = []

    async def get_session(self, session_id):
        if self.existing_session and self.existing_session.session_id == session_id:
            return self.existing_session
        return None

    def create_session(self, session_id, task, llm_client, agent):
        session = SimpleNamespace(
            session_id=session_id,
            task=task,
            llm_client=llm_client,
            agent=agent,
            messages=[],
            status="active",
        )
        self.created_session = session
        return session

    async def add_message(self, session_id, role, content, metadata=None):
        self.messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
        )

    def update_session(self, session_id, **kwargs):
        session = self.created_session
        if self.existing_session and self.existing_session.session_id == session_id:
            session = self.existing_session
        if session:
            for key, value in kwargs.items():
                setattr(session, key, value)


class RaisingLLMClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("LLMClient should not be created for clarify responses")


class FakeLLMClient:
    pass


class FakeGeneralChatToolAgent:
    def __init__(self, llm_client, session_manager, session_id, event_callback=None):
        self.llm_client = llm_client
        self.session_manager = session_manager
        self.session_id = session_id
        self.event_callback = event_callback

    async def run(self, session_messages, system_prompt):
        return "general reply"


async def _read_streaming_response(response):
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))
    return "".join(chunks)


def _extract_content_text(payload):
    text_parts = []
    for line in payload.splitlines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line[6:])
        if event.get("type") == "content":
            text_parts.append(event.get("text", ""))
    return "".join(text_parts)


def test_chat_stream_clarify_uses_lightweight_session(monkeypatch):
    fake_manager = FakeSessionManager()

    monkeypatch.setattr(api, "session_manager", fake_manager)
    monkeypatch.setattr(
        api,
        "intent_router",
        SimpleNamespace(
            route_message=lambda message, session=None: IntentDecision(
                route="clarify",
                confidence=0.9,
                reason="needs_clarify",
                clarify_message="请提供源主机、目标主机和端口。",
            )
        ),
    )
    monkeypatch.setattr(api, "LLMClient", RaisingLLMClient)

    async def run_test():
        response = await api.chat_stream(api.ChatStreamRequest(message="我现在访问不通"))
        return await _read_streaming_response(response)

    payload = asyncio.run(run_test())

    assert fake_manager.created_session is not None
    assert fake_manager.created_session.llm_client is None
    assert fake_manager.created_session.agent is None
    assert "请提供源主机、目标主机和端口" in _extract_content_text(payload)


def test_general_chat_stream_creates_llm_for_lightweight_session(monkeypatch):
    session = SimpleNamespace(
        session_id="session-1",
        task=SimpleNamespace(source="general_chat", target="general_chat"),
        llm_client=None,
        agent=None,
        messages=[],
        status="completed",
    )
    fake_manager = FakeSessionManager(existing_session=session)

    monkeypatch.setattr(api, "session_manager", fake_manager)
    monkeypatch.setattr(api, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(api, "GeneralChatToolAgent", FakeGeneralChatToolAgent)

    async def run_test():
        response = await api.general_chat_stream_v2(
            api.GeneralChatRequestWithRAG(
                message="怎么排查端口不通",
                session_id="session-1",
                use_rag=False,
            )
        )
        return await _read_streaming_response(response)

    payload = asyncio.run(run_test())

    assert isinstance(session.llm_client, FakeLLMClient)
    assert _extract_content_text(payload) == "general reply"


def test_general_chat_non_stream_creates_llm_for_lightweight_session(monkeypatch):
    session = SimpleNamespace(
        session_id="session-2",
        task=SimpleNamespace(source="general_chat", target="general_chat"),
        llm_client=None,
        agent=None,
        messages=[],
        status="completed",
    )
    fake_manager = FakeSessionManager(existing_session=session)

    monkeypatch.setattr(api, "session_manager", fake_manager)
    monkeypatch.setattr(api, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(api, "GeneralChatToolAgent", FakeGeneralChatToolAgent)

    async def run_test():
        return await api.general_chat_v2(
            api.GeneralChatRequest(
                message="How do I troubleshoot a port issue?",
                session_id="session-2",
            )
        )

    response = asyncio.run(run_test())

    assert isinstance(session.llm_client, FakeLLMClient)
    assert response["response"] == "general reply"
    assert response["session_id"] == "session-2"
