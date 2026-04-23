"""
Preservation Property Tests for IP Address Support

These tests verify that existing system identifier query behavior is preserved
when IP address support is added:
- System code queries should continue to skip RAG
- Deploy unit queries should continue to skip RAG
- System name queries should continue to skip RAG

Expected to PASS on both current code and after IP address support is added
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.api import general_chat_stream_v2, GeneralChatRequestWithRAG


@pytest.mark.asyncio
async def test_preservation_system_code_query_skips_rag():
    """
    Preservation Test - System Code Query
    
    Test case: "N-CRM有哪些访问关系" with use_rag=True
    Expected: Should skip RAG (existing behavior)
    This behavior should be PRESERVED after adding IP address support
    """
    request = GeneralChatRequestWithRAG(
        message="N-CRM有哪些访问关系",
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
        # System code query should skip RAG (preserve this behavior)
        assert 'rag_start' not in event_types, "System code query should skip RAG"
        assert 'rag_skipped' in event_types, "System code query should emit rag_skipped"


@pytest.mark.asyncio
async def test_preservation_deploy_unit_query_skips_rag():
    """
    Preservation Test - Deploy Unit Query
    
    Test case: "CRMJS_AP部署单元有哪些访问关系" with use_rag=True
    Expected: Should skip RAG (existing behavior)
    This behavior should be PRESERVED after adding IP address support
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
        # Deploy unit query should skip RAG (preserve this behavior)
        assert 'rag_start' not in event_types, "Deploy unit query should skip RAG"
        assert 'rag_skipped' in event_types, "Deploy unit query should emit rag_skipped"


@pytest.mark.asyncio
async def test_preservation_system_name_query_skips_rag():
    """
    Preservation Test - System Name Query
    
    Test case: "客户关系管理系统有哪些访问关系" with use_rag=True
    Expected: Should skip RAG (existing behavior)
    This behavior should be PRESERVED after adding IP address support
    """
    request = GeneralChatRequestWithRAG(
        message="客户关系管理系统有哪些访问关系",
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
        # System name query should skip RAG (preserve this behavior)
        assert 'rag_start' not in event_types, "System name query should skip RAG"
        assert 'rag_skipped' in event_types, "System name query should emit rag_skipped"


@pytest.mark.asyncio
async def test_preservation_inbound_query_skips_rag():
    """
    Preservation Test - Inbound Query
    
    Test case: "哪些系统访问N-OA" with use_rag=True
    Expected: Should skip RAG (existing behavior)
    This behavior should be PRESERVED after adding IP address support
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
        # Inbound query should skip RAG (preserve this behavior)
        assert 'rag_start' not in event_types, "Inbound query should skip RAG"
        assert 'rag_skipped' in event_types, "Inbound query should emit rag_skipped"
