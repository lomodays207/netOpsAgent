import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api import GeneralChatRequestWithRAG, general_chat_stream_v2


@pytest.mark.asyncio
async def test_host_port_status_query_skips_rag():
    request = GeneralChatRequestWithRAG(
        message="请帮我检查10.0.2.20 主机上的 8008 是否正常监听？",
        use_rag=True,
        session_id=None,
    )

    with patch("src.api.session_manager") as mock_session_manager, patch(
        "src.api._init_rag_services"
    ) as mock_init_rag, patch("src.api.GeneralChatToolAgent") as mock_tool_agent, patch(
        "src.api.LLMClient"
    ):
        mock_session = MagicMock()
        mock_session.messages = []
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = MagicMock(return_value=mock_session)
        mock_session_manager.add_message = AsyncMock()
        mock_session_manager.update_session = MagicMock()

        mock_rag_chain = MagicMock()
        mock_rag_chain.has_knowledge = MagicMock(return_value=True)
        mock_rag_chain.build_enhanced_prompt = MagicMock(
            return_value=("query", "prompt", [{"content": "doc"}])
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)

        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="检查结果")
        mock_tool_agent.return_value = mock_agent_instance

        response = await general_chat_stream_v2(request)
        events = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            if chunk.startswith("data: "):
                event_data = chunk[6:].strip()
                if event_data:
                    events.append(json.loads(event_data))

    event_types = [event.get("type") for event in events]
    assert "rag_skipped" in event_types
    assert "rag_start" not in event_types
    assert "rag_result" not in event_types
