"""
Test for evidence_sources event in general_chat_stream_v2

This test verifies that:
1. evidence_sources event is sent after RAG retrieval
2. Event contains correct structure (type, sources array)
3. Each source has required fields (id, filename, relevance_score, preview, metadata)
4. Maximum 5 sources are returned
5. Event is sent before content events
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.api import general_chat_stream_v2, GeneralChatRequestWithRAG


@pytest.mark.asyncio
async def test_evidence_sources_event_sent_after_rag_retrieval():
    """
    Test that evidence_sources event is sent after RAG retrieval
    
    Validates Requirements: 3.1, 3.2, 3.3, 3.4
    """
    # Arrange: Create request with RAG enabled
    request = GeneralChatRequestWithRAG(
        message="访问关系如何进行开通提单",
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
        
        # Setup RAG mock with retrieved documents
        mock_rag_chain = MagicMock()
        mock_rag_chain.has_knowledge = MagicMock(return_value=True)
        mock_rag_chain.build_enhanced_prompt = MagicMock(
            return_value=(
                "enhanced_query",
                "enhanced_system_prompt",
                [
                    {
                        "id": "doc_123",
                        "text": "访问关系开通需要提交工单，包括源IP、目标IP、端口等信息。",
                        "metadata": {"filename": "访问关系开通流程.txt", "source": "docs/knowledge/"},
                        "relevance_score": 0.85,
                        "preview": "访问关系开通需要提交工单，包括源IP、目标IP、端口等信息。"
                    },
                    {
                        "id": "doc_456",
                        "text": "网络权限申请流程包括填写申请表、审批、配置等步骤。",
                        "metadata": {"filename": "网络权限申请指南.txt", "source": "docs/knowledge/"},
                        "relevance_score": 0.72,
                        "preview": "网络权限申请流程包括填写申请表、审批、配置等步骤。"
                    }
                ]
            )
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        # Setup tool agent mock
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="根据知识库，访问关系开通需要提交工单...")
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
        
        # Assert: Verify evidence_sources event exists
        event_types = [e.get('type') for e in events]
        assert 'evidence_sources' in event_types, \
            "evidence_sources event should be sent after RAG retrieval"
        
        # Find evidence_sources event
        evidence_event = next((e for e in events if e.get('type') == 'evidence_sources'), None)
        assert evidence_event is not None, "evidence_sources event should exist"
        
        # Verify event structure
        assert 'sources' in evidence_event, "evidence_sources event should have 'sources' field"
        sources = evidence_event['sources']
        assert isinstance(sources, list), "sources should be a list"
        assert len(sources) == 2, "Should have 2 sources"
        
        # Verify each source has required fields
        for source in sources:
            assert 'id' in source, "Source should have 'id' field"
            assert 'filename' in source, "Source should have 'filename' field"
            assert 'relevance_score' in source, "Source should have 'relevance_score' field"
            assert 'preview' in source, "Source should have 'preview' field"
            assert 'metadata' in source, "Source should have 'metadata' field"
            
            # Verify data types
            assert isinstance(source['id'], str), "id should be string"
            assert isinstance(source['filename'], str), "filename should be string"
            assert isinstance(source['relevance_score'], (int, float)), "relevance_score should be number"
            assert isinstance(source['preview'], str), "preview should be string"
            assert isinstance(source['metadata'], dict), "metadata should be dict"
        
        # Verify event order: evidence_sources should come before content
        evidence_index = event_types.index('evidence_sources')
        content_indices = [i for i, t in enumerate(event_types) if t == 'content']
        if content_indices:
            assert evidence_index < min(content_indices), \
                "evidence_sources event should be sent before content events"


@pytest.mark.asyncio
async def test_evidence_sources_limited_to_5():
    """
    Test that evidence_sources event limits sources to maximum 5
    
    Validates Requirement: 1.5
    """
    # Arrange: Create request with RAG enabled
    request = GeneralChatRequestWithRAG(
        message="网络故障排查",
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
        
        # Setup RAG mock with 7 retrieved documents
        mock_docs = []
        for i in range(7):
            mock_docs.append({
                "id": f"doc_{i}",
                "text": f"文档内容 {i}",
                "metadata": {"filename": f"文档{i}.txt"},
                "relevance_score": 0.9 - i * 0.1,
                "preview": f"文档内容 {i}"
            })
        
        mock_rag_chain = MagicMock()
        mock_rag_chain.has_knowledge = MagicMock(return_value=True)
        mock_rag_chain.build_enhanced_prompt = MagicMock(
            return_value=("query", "prompt", mock_docs)
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        # Setup tool agent mock
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="回答内容")
        mock_tool_agent.return_value = mock_agent_instance
        
        # Act: Call the function and collect events
        response = await general_chat_stream_v2(request)
        events = []
        async for chunk in response.body_iterator:
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
        
        # Assert: Verify sources are limited to 5
        evidence_event = next((e for e in events if e.get('type') == 'evidence_sources'), None)
        assert evidence_event is not None, "evidence_sources event should exist"
        
        sources = evidence_event['sources']
        assert len(sources) <= 5, f"Sources should be limited to 5, but got {len(sources)}"
        assert len(sources) == 5, "Should return exactly 5 sources when more than 5 are available"


@pytest.mark.asyncio
async def test_no_evidence_sources_event_when_no_docs():
    """
    Test that evidence_sources event is NOT sent when no documents are retrieved
    
    Validates Requirement: 3.5
    """
    # Arrange: Create request with RAG enabled
    request = GeneralChatRequestWithRAG(
        message="一个不相关的问题",
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
        
        # Setup RAG mock with NO retrieved documents
        mock_rag_chain = MagicMock()
        mock_rag_chain.has_knowledge = MagicMock(return_value=True)
        mock_rag_chain.build_enhanced_prompt = MagicMock(
            return_value=("query", "prompt", [])  # Empty list - no docs
        )
        mock_init_rag.return_value = (None, None, mock_rag_chain)
        
        # Setup tool agent mock
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="回答内容")
        mock_tool_agent.return_value = mock_agent_instance
        
        # Act: Call the function and collect events
        response = await general_chat_stream_v2(request)
        events = []
        async for chunk in response.body_iterator:
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
        
        # Assert: Verify evidence_sources event is NOT sent
        event_types = [e.get('type') for e in events]
        assert 'evidence_sources' not in event_types, \
            "evidence_sources event should NOT be sent when no documents are retrieved"
