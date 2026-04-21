import asyncio

from langchain_core.messages import AIMessage, SystemMessage

from src.agent.general_chat_agent import GeneralChatToolAgent


class FakeDB:
    def __init__(self):
        self.calls = []

    async def query_access_relations(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "items": [
                {
                    "id": 1,
                    "src_system": "N-CRM",
                    "src_system_name": "CRM",
                    "src_deploy_unit": "CRMJS_AP",
                    "src_ip": "10.38.1.100",
                    "dst_system": "N-AQM",
                    "dst_deploy_unit": "AQMJS_AP",
                    "dst_ip": "10.37.1.116",
                    "protocol": "TCP",
                    "port": "8080",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 50,
        }


class FakeSessionManager:
    def __init__(self):
        self.db = FakeDB()
        self.messages = []

    async def add_message(self, session_id, role, content, metadata=None):
        self.messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
        )


class FakeLLMClient:
    def __init__(self):
        self.tool_round = 0

    def invoke_langchain_messages_with_tools(self, messages, tools, temperature=None, max_tokens=None):
        self.tool_round += 1
        if self.tool_round == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "query_access_relations",
                        "args": {
                            "system_code": "N-CRM",
                            "direction": "outbound",
                        },
                    }
                ],
            )
        return AIMessage(content="Found 1 outbound access relation for N-CRM.")

    def invoke_langchain_messages(self, messages, temperature=None, max_tokens=None):
        return AIMessage(content="fallback")


def test_general_chat_agent_executes_access_relation_tool():
    session_manager = FakeSessionManager()
    llm_client = FakeLLMClient()
    events = []

    async def event_callback(event):
        events.append(event)

    agent = GeneralChatToolAgent(
        llm_client=llm_client,
        session_manager=session_manager,
        session_id="session-1",
        event_callback=event_callback,
    )

    async def run_test():
        return await agent.run(
            session_messages=[
                {"role": "user", "content": "What access relations does N-CRM have?", "metadata": {}}
            ],
            system_prompt="test prompt",
        )

    response = asyncio.run(run_test())

    assert response == "Found 1 outbound access relation for N-CRM."
    assert session_manager.db.calls == [
        {
            "system_code": "N-CRM",
            "system_name": None,
            "deploy_unit": None,
            "direction": "outbound",
            "peer_system_code": None,
            "peer_system_name": None,
            "page": 1,
            "page_size": 50,
        }
    ]
    assert [event["type"] for event in events] == ["tool_start", "tool_result"]
    assert session_manager.messages[0]["metadata"]["tool_call"]["name"] == "query_access_relations"


def test_general_chat_agent_includes_tool_history_as_context():
    agent = GeneralChatToolAgent(
        llm_client=FakeLLMClient(),
        session_manager=FakeSessionManager(),
        session_id="session-2",
    )

    messages = agent._build_langchain_messages(
        session_messages=[
            {
                "role": "assistant",
                "content": "Executed tool: query_access_relations",
                "metadata": {
                    "tool_call": {
                        "name": "query_access_relations",
                        "arguments": {"system_code": "N-CRM", "direction": "outbound"},
                        "result": {"data": "Target N-CRM, direction outbound, 2 hits", "total": 2},
                    }
                },
            }
        ],
        system_prompt="system prompt",
    )

    history_messages = [
        msg
        for msg in messages
        if isinstance(msg, SystemMessage) and "query_access_relations" in msg.content
    ]
    assert history_messages
    assert "N-CRM" in history_messages[0].content
