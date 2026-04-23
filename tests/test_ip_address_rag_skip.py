"""
Bug Condition Exploration Test for IP Address Access Relation Queries

This test demonstrates that IP address queries are not yet supported:
- IP address access relation queries (e.g., "IP 为 10.0.1.10 的主机有哪些访问关系") with use_rag=True
  incorrectly execute RAG retrieval instead of skipping it
- Expected to FAIL on current code (proving IP address support is missing)
- Expected to PASS after IP address support is added

Property 1: Bug Condition - IP Address Access Relation Queries Execute RAG on Current Code
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.api import general_chat_stream_v2, GeneralChatRequestWithRAG


@pytest.mark.asyncio
async def test_bug_condition_full_ip_query_executes_rag_on_current_code():
    """
    Bug Condition Exploration Test - Full IP Address Query
    
    This test verifies the bug exists on CURRENT code:
    - When user asks "IP 为 10.0.1.10 的主机有哪些访问关系" with use_rag=True
    - System incorrectly executes RAG retrieval (IP address not recognized)
    - Should emit rag_start and rag_result events (not rag_skipped)
    
    EXPECTED OUTCOME ON CURRENT CODE: Test FAILS (proves IP support missing)
    EXPECTED OUTCOME AFTER FIX: Test PASSES (proves IP support added)
    """
    # Arrange: Create request for IP address access relation query
    request = GeneralChatRequestWithRAG(
        message="IP 为 10.0.1.10 的主机有哪些访问关系",
        use_rag=True,
        session_id=None
    )
    
    # Mock dependencies
    with patch('src.api.session_manager') as mock_session_manager, \
         patch('src.api._init_rag_services') as mock_init_rag, \
         patch('src.api.GeneralChatToolAgent') as mock_tool_agent, \
         patch('src.api.LLMClient') as mock_llm_client:
        
        # Setup session manager mock
        mock_session = MagicMock()
        mock_session.messages = []
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = MagicMock(return_value=mock_session)
        mock_session_manager.add_message = AsyncMock()
        mock_session_manager.update_session = MagicMock()
        
        # Setup RAG mock
        mock_rag_chain = MagicMock()
        mock_rag_chain.has_knowledge = MagicMock(return_value=True)
        mock_rag_chain.build_enhanced_prompt = MagicMock(
            return_value=(
                "enhanced_query",
                "enhanced_system_prompt",
                [{"content": "example doc", "metadata": {"filename": "example.txt"}}]
            )
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        # Setup tool agent mock
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="查询结果")
        mock_tool_agent.return_value = mock_agent_instance
        
        # Act: Call the function and collect events
        response = await general_chat_stream_v2(request)
        events = []
        async for chunk in response.body_iterator:
            # Decode chunk if it's bytes
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            if chunk.startswith("data: "):
                event_data = chunk[6:].strip()
                if event_data:
                    try:
                        event = json.loads(event_data)
                        events.append(event)
                    except json.JSONDecodeError:
                        pass
        
        # Assert: On CURRENT code, RAG should be executed (bug behavior)
        # This assertion will FAIL on current code, proving IP support is missing
        event_types = [e.get('type') for e in events]
        
        # On CURRENT code: rag_start and rag_result are emitted (BUG - IP not recognized)
        # On FIXED code: rag_skipped is emitted (CORRECT - IP recognized)
        assert 'rag_start' not in event_types, \
            "Bug detected: RAG retrieval was executed for IP address query (should be skipped)"
        assert 'rag_result' not in event_types, \
            "Bug detected: RAG result was emitted for IP address query (should be skipped)"
        assert 'rag_skipped' in event_types, \
            "Expected rag_skipped event for IP address query"
        
        # Verify rag_skipped event has correct reason
        rag_skipped_events = [e for e in events if e.get('type') == 'rag_skipped']
        assert len(rag_skipped_events) > 0, "Should have at least one rag_skipped event"
        assert '访问关系数据查询' in rag_skipped_events[0].get('reason', ''), \
            "rag_skipped event should mention access relation data query"


@pytest.mark.asyncio
async def test_bug_condition_short_ip_query_executes_rag_on_current_code():
    """
    Bug Condition Exploration Test - Short IP Address Query
    
    Test case: "10.0.1.10 有哪些访问关系" with use_rag=True
    Expected: Should skip RAG (but executes RAG on current code - BUG)
    """
    request = GeneralChatRequestWithRAG(
        message="10.0.1.10 有哪些访问关系",
        use_rag=True,
        session_id=None
    )
    
    with patch('src.api.session_manager') as mock_session_manager, \
         patch('src.api._init_rag_services') as mock_init_rag, \
         patch('src.api.GeneralChatToolAgent') as mock_tool_agent, \
         patch('src.api.LLMClient') as mock_llm_client:
        
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
        mock_agent_instance.run = AsyncMock(return_value="结果")
        mock_tool_agent.return_value = mock_agent_instance
        
        response = await general_chat_stream_v2(request)
        events = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            if chunk.startswith("data: "):
                event_data = chunk[6:].strip()
                if event_data:
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        pass
        
        event_types = [e.get('type') for e in events]
        assert 'rag_start' not in event_types, "Bug: RAG executed for short IP query"
        assert 'rag_skipped' in event_types, "Expected rag_skipped for short IP query"


@pytest.mark.asyncio
async def test_bug_condition_query_ip_executes_rag_on_current_code():
    """
    Bug Condition Exploration Test - Query IP Address
    
    Test case: "查询 10.0.1.10 的访问关系" with use_rag=True
    Expected: Should skip RAG (but executes RAG on current code - BUG)
    """
    request = GeneralChatRequestWithRAG(
        message="查询 10.0.1.10 的访问关系",
        use_rag=True,
        session_id=None
    )
    
    with patch('src.api.session_manager') as mock_session_manager, \
         patch('src.api._init_rag_services') as mock_init_rag, \
         patch('src.api.GeneralChatToolAgent') as mock_tool_agent, \
         patch('src.api.LLMClient') as mock_llm_client:
        
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
        mock_agent_instance.run = AsyncMock(return_value="结果")
        mock_tool_agent.return_value = mock_agent_instance
        
        response = await general_chat_stream_v2(request)
        events = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            if chunk.startswith("data: "):
                event_data = chunk[6:].strip()
                if event_data:
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        pass
        
        event_types = [e.get('type') for e in events]
        assert 'rag_start' not in event_types, "Bug: RAG executed for query IP"
        assert 'rag_skipped' in event_types, "Expected rag_skipped for query IP"


@pytest.mark.asyncio
async def test_bug_condition_different_ip_format_executes_rag_on_current_code():
    """
    Bug Condition Exploration Test - Different IP Format
    
    Test case: "192.168.1.1 有哪些访问关系" with use_rag=True
    Expected: Should skip RAG (but executes RAG on current code - BUG)
    """
    request = GeneralChatRequestWithRAG(
        message="192.168.1.1 有哪些访问关系",
        use_rag=True,
        session_id=None
    )
    
    with patch('src.api.session_manager') as mock_session_manager, \
         patch('src.api._init_rag_services') as mock_init_rag, \
         patch('src.api.GeneralChatToolAgent') as mock_tool_agent, \
         patch('src.api.LLMClient') as mock_llm_client:
        
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
        mock_agent_instance.run = AsyncMock(return_value="结果")
        mock_tool_agent.return_value = mock_agent_instance
        
        response = await general_chat_stream_v2(request)
        events = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            if chunk.startswith("data: "):
                event_data = chunk[6:].strip()
                if event_data:
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        pass
        
        event_types = [e.get('type') for e in events]
        assert 'rag_start' not in event_types, "Bug: RAG executed for different IP format"
        assert 'rag_skipped' in event_types, "Expected rag_skipped for different IP format"
