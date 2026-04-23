"""
测试文档详情API端点 (Task 4.1)

测试 GET /api/v1/knowledge/document/{doc_id} 端点的功能：
- 正常返回文档内容
- 处理文档不存在的情况（404）
- 处理文档过大的情况
- 速率限制（每分钟最多10次）
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_document():
    """模拟文档数据"""
    return {
        "id": "doc_test_123",
        "filename": "test_document.txt",
        "content": "这是测试文档的完整内容。包含了一些网络故障排查的知识。",
        "metadata": {
            "source": "docs/knowledge/test_document.txt",
            "created_at": "2026-01-15T10:30:00Z",
            "file_size": 1024,
            "doc_id": "doc_test_123"
        }
    }


def test_get_document_success(client, mock_document):
    """测试成功获取文档"""
    with patch('src.rag.document_service.get_document_by_id') as mock_get_doc:
        mock_get_doc.return_value = mock_document
        
        response = client.get("/api/v1/knowledge/document/doc_test_123")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "data" in data
        assert data["data"]["id"] == "doc_test_123"
        assert data["data"]["filename"] == "test_document.txt"
        assert "content" in data["data"]
        assert "metadata" in data["data"]
        
        # 验证调用了文档服务
        mock_get_doc.assert_called_once_with("doc_test_123")


def test_get_document_not_found(client):
    """测试文档不存在的情况（返回404）"""
    with patch('src.rag.document_service.get_document_by_id') as mock_get_doc:
        mock_get_doc.return_value = None
        
        response = client.get("/api/v1/knowledge/document/nonexistent_doc")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "不存在" in data["detail"]


def test_get_document_invalid_id(client):
    """测试无效的文档ID（路径遍历攻击）"""
    with patch('src.rag.document_service.get_document_by_id') as mock_get_doc:
        # 文档服务应该返回None（因为validate_document_id会拒绝）
        mock_get_doc.return_value = None
        
        response = client.get("/api/v1/knowledge/document/../../../etc/passwd")
        
        assert response.status_code == 404


def test_get_document_too_large(client):
    """测试文档过大的情况"""
    with patch('src.rag.document_service.get_document_by_id') as mock_get_doc:
        # 文档服务返回None表示文档过大
        mock_get_doc.return_value = None
        
        response = client.get("/api/v1/knowledge/document/large_doc")
        
        assert response.status_code == 404


def test_rate_limiting(client, mock_document):
    """测试速率限制（每分钟最多10次）"""
    with patch('src.rag.document_service.get_document_by_id') as mock_get_doc:
        mock_get_doc.return_value = mock_document
        
        # 发送10次请求（应该都成功）
        for i in range(10):
            response = client.get(f"/api/v1/knowledge/document/doc_{i}")
            assert response.status_code == 200, f"Request {i+1} should succeed"
        
        # 第11次请求应该被限流
        response = client.get("/api/v1/knowledge/document/doc_11")
        assert response.status_code == 429
        data = response.json()
        assert "detail" in data
        assert "频繁" in data["detail"] or "rate" in data["detail"].lower()


def test_response_format(client, mock_document):
    """测试响应格式符合设计文档"""
    with patch('src.rag.document_service.get_document_by_id') as mock_get_doc:
        mock_get_doc.return_value = mock_document
        
        response = client.get("/api/v1/knowledge/document/doc_test_123")
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证响应格式
        assert "status" in data
        assert data["status"] == "success"
        assert "data" in data
        
        doc_data = data["data"]
        assert "id" in doc_data
        assert "filename" in doc_data
        assert "content" in doc_data
        assert "metadata" in doc_data
        
        # 验证元数据格式
        metadata = doc_data["metadata"]
        assert "source" in metadata or "created_at" in metadata or "file_size" in metadata


def test_error_response_format(client):
    """测试错误响应格式"""
    with patch('src.rag.document_service.get_document_by_id') as mock_get_doc:
        mock_get_doc.return_value = None
        
        response = client.get("/api/v1/knowledge/document/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
