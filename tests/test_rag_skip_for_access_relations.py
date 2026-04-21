"""
Bug Condition Exploration Test for RAG Skipping on Access Relation Data Queries

This test demonstrates the bug on UNFIXED code:
- Access relation data queries (e.g., "N-CRM有哪些访问关系") with use_rag=True
  incorrectly execute RAG retrieval instead of skipping it
- Expected to FAIL on unfixed code (proving the bug exists)
- Expected to PASS after fix is implemented

Property 1: Bug Condition - Access Relation Data Queries Execute RAG on Unfixed Code
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.api import general_chat_stream_v2, GeneralChatRequestWithRAG


@pytest.mark.asyncio
async def test_bug_condition_access_relation_data_query_executes_rag_on_unfixed_code():
    """
    Bug Condition Exploration Test
    
    This test verifies the bug exists on UNFIXED code:
    - When user asks "N-CRM有哪些访问关系" with use_rag=True
    - System incorrectly executes RAG retrieval
    - Should emit rag_start and rag_result events (not rag_skipped)
    
    EXPECTED OUTCOME ON UNFIXED CODE: Test FAILS (proves bug exists)
    EXPECTED OUTCOME ON FIXED CODE: Test PASSES (proves bug is fixed)
    """
    # Arrange: Create request for access relation data query
    request = GeneralChatRequestWithRAG(
        message="N-CRM有哪些访问关系",
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
        
        # Assert: On UNFIXED code, RAG should be executed (bug behavior)
        # This assertion will FAIL on unfixed code, proving the bug exists
        event_types = [e.get('type') for e in events]
        
        # On UNFIXED code: rag_start and rag_result are emitted (BUG)
        # On FIXED code: rag_skipped is emitted (CORRECT)
        assert 'rag_start' not in event_types, \
            "Bug detected: RAG retrieval was executed for access relation data query (should be skipped)"
        assert 'rag_result' not in event_types, \
            "Bug detected: RAG result was emitted for access relation data query (should be skipped)"
        assert 'rag_skipped' in event_types, \
            "Expected rag_skipped event for access relation data query"
        
        # Verify rag_skipped event has correct reason
        rag_skipped_events = [e for e in events if e.get('type') == 'rag_skipped']
        assert len(rag_skipped_events) > 0, "Should have at least one rag_skipped event"
        assert '访问关系数据查询' in rag_skipped_events[0].get('reason', ''), \
            "rag_skipped event should mention access relation data query"


@pytest.mark.asyncio
async def test_bug_condition_deploy_unit_query_executes_rag_on_unfixed_code():
    """
    Bug Condition Exploration Test - Deploy Unit Query
    
    Test case: "CRMJS_AP部署单元有哪些访问关系" with use_rag=True
    Expected: Should skip RAG (but executes RAG on unfixed code - BUG)
    """
    request = GeneralChatRequestWithRAG(
        message="CRMJS_AP部署单元有哪些访问关系",
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
        assert 'rag_start' not in event_types, "Bug: RAG executed for deploy unit query"
        assert 'rag_skipped' in event_types, "Expected rag_skipped for deploy unit query"


@pytest.mark.asyncio
async def test_bug_condition_inbound_query_executes_rag_on_unfixed_code():
    """
    Bug Condition Exploration Test - Inbound Query
    
    Test case: "哪些系统访问N-OA" with use_rag=True
    Expected: Should skip RAG (but executes RAG on unfixed code - BUG)
    """
    request = GeneralChatRequestWithRAG(
        message="哪些系统访问N-OA",
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
        assert 'rag_start' not in event_types, "Bug: RAG executed for inbound query"
        assert 'rag_skipped' in event_types, "Expected rag_skipped for inbound query"



# ============================================================================
# Preservation Property Tests
# These tests verify that non-data queries preserve RAG behavior
# Expected to PASS on both unfixed and fixed code
# ============================================================================

@pytest.mark.asyncio
async def test_preservation_knowledge_query_executes_rag():
    """
    Preservation Test - Knowledge Query
    
    Test case: "访问关系如何开权限" with use_rag=True
    Expected: Should execute RAG (knowledge query, not data query)
    This behavior should be PRESERVED after fix
    """
    request = GeneralChatRequestWithRAG(
        message="访问关系如何开权限",
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
            return_value=("query", "prompt", [{"content": "权限文档"}])
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="权限开通流程...")
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
        # Knowledge query should execute RAG
        assert 'rag_start' in event_types, "Knowledge query should execute RAG"
        assert 'rag_skipped' not in event_types, "Knowledge query should NOT skip RAG"


@pytest.mark.asyncio
async def test_preservation_general_question_executes_rag():
    """
    Preservation Test - General Question
    
    Test case: "如何排查网络故障" with use_rag=True
    Expected: Should execute RAG (general network ops question)
    This behavior should be PRESERVED after fix
    """
    request = GeneralChatRequestWithRAG(
        message="如何排查网络故障",
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
            return_value=("query", "prompt", [{"content": "故障排查文档"}])
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="排查步骤...")
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
        # General question should execute RAG
        assert 'rag_start' in event_types, "General question should execute RAG"
        assert 'rag_skipped' not in event_types, "General question should NOT skip RAG"


@pytest.mark.asyncio
async def test_preservation_rag_disabled_skips_rag():
    """
    Preservation Test - RAG Disabled
    
    Test case: Any message with use_rag=False
    Expected: Should skip RAG (RAG disabled)
    This behavior should be PRESERVED after fix
    """
    request = GeneralChatRequestWithRAG(
        message="N-CRM有哪些访问关系",
        use_rag=False,  # RAG disabled
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
        # When RAG is disabled, should not execute RAG
        assert 'rag_start' not in event_types, "RAG disabled should not execute RAG"
        assert 'rag_result' not in event_types, "RAG disabled should not emit rag_result"


@pytest.mark.asyncio
async def test_preservation_rag_error_continues():
    """
    Preservation Test - RAG Error Handling
    
    Test case: RAG retrieval fails with exception
    Expected: Should emit rag_error event and continue with tool calling
    This behavior should be PRESERVED after fix
    """
    request = GeneralChatRequestWithRAG(
        message="如何排查网络故障",
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
        
        # Simulate RAG error
        mock_init_rag.side_effect = Exception("RAG service unavailable")
        
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
        # RAG error should emit rag_error and continue
        assert 'rag_error' in event_types, "RAG error should emit rag_error event"
        assert 'complete' in event_types, "Should continue after RAG error"



# ============================================================================
# Preservation Property Tests
# These tests verify that non-data query RAG behavior remains unchanged
# Expected to PASS on both unfixed and fixed code
# ============================================================================

@pytest.mark.asyncio
async def test_preservation_knowledge_query_executes_rag():
    """
    Preservation Test - Knowledge Query
    
    Test case: "访问关系如何开权限" with use_rag=True
    Expected: Should execute RAG (knowledge query, not data query)
    This behavior should be preserved after fix
    """
    request = GeneralChatRequestWithRAG(
        message="访问关系如何开权限",
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
            return_value=("query", "prompt", [{"content": "权限文档"}])
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="权限开通流程...")
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
        # Knowledge query should execute RAG (preserve this behavior)
        assert 'rag_start' in event_types, "Knowledge query should execute RAG"
        assert 'rag_result' in event_types, "Knowledge query should have RAG result"
        assert 'rag_skipped' not in event_types, "Knowledge query should not skip RAG"


@pytest.mark.asyncio
async def test_preservation_general_question_executes_rag():
    """
    Preservation Test - General Question
    
    Test case: "如何排查网络故障" with use_rag=True
    Expected: Should execute RAG (general question, not access relation query)
    This behavior should be preserved after fix
    """
    request = GeneralChatRequestWithRAG(
        message="如何排查网络故障",
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
            return_value=("query", "prompt", [{"content": "故障排查文档"}])
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="排查步骤...")
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
        # General question should execute RAG (preserve this behavior)
        assert 'rag_start' in event_types, "General question should execute RAG"
        assert 'rag_result' in event_types, "General question should have RAG result"
        assert 'rag_skipped' not in event_types, "General question should not skip RAG"


@pytest.mark.asyncio
async def test_preservation_rag_disabled_skips_rag():
    """
    Preservation Test - RAG Disabled
    
    Test case: Any message with use_rag=False
    Expected: Should skip RAG (RAG disabled)
    This behavior should be preserved after fix
    """
    request = GeneralChatRequestWithRAG(
        message="N-CRM有哪些访问关系",
        use_rag=False,  # RAG disabled
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
        # When RAG is disabled, should not execute RAG (preserve this behavior)
        assert 'rag_start' not in event_types, "RAG disabled should not execute RAG"
        assert 'rag_result' not in event_types, "RAG disabled should not have RAG result"
        # Note: rag_skipped event is not emitted when use_rag=False (different from data query skip)


@pytest.mark.asyncio
async def test_preservation_rag_error_continues():
    """
    Preservation Test - RAG Error Handling
    
    Test case: RAG retrieval fails with exception
    Expected: Should emit rag_error event and continue with tool calling
    This behavior should be preserved after fix
    """
    request = GeneralChatRequestWithRAG(
        message="如何排查网络故障",
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
        
        # Simulate RAG error
        mock_init_rag.side_effect = Exception("RAG service unavailable")
        
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
        # RAG error should emit rag_error and continue (preserve this behavior)
        assert 'rag_error' in event_types, "RAG error should emit rag_error event"
        assert 'complete' in event_types, "Should continue after RAG error"
