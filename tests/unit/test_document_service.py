"""
文档服务单元测试

测试文档查询、缓存和安全验证功能
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.rag.document_service import (
    validate_document_id,
    get_document_by_id,
    clear_document_cache,
    MAX_DOCUMENT_SIZE
)


class TestValidateDocumentId:
    """测试文档ID验证功能"""
    
    def test_valid_document_id(self):
        """测试有效的文档ID"""
        assert validate_document_id("doc_123") is True
        assert validate_document_id("file_abc_456") is True
        assert validate_document_id("document-with-dashes") is True
        assert validate_document_id("document_with_underscores") is True
    
    def test_empty_document_id(self):
        """测试空文档ID"""
        assert validate_document_id("") is False
        assert validate_document_id(None) is False
    
    def test_path_traversal_attack_unix(self):
        """测试Unix风格路径遍历攻击"""
        assert validate_document_id("../etc/passwd") is False
        assert validate_document_id("doc/../../../etc/passwd") is False
        assert validate_document_id("../../sensitive_file") is False
    
    def test_path_traversal_attack_windows(self):
        """测试Windows风格路径遍历攻击"""
        assert validate_document_id("..\\windows\\system32") is False
        assert validate_document_id("doc\\..\\..\\sensitive") is False
    
    def test_absolute_path_rejection(self):
        """测试拒绝绝对路径"""
        assert validate_document_id("/etc/passwd") is False
        assert validate_document_id("\\windows\\system32") is False
    
    def test_windows_drive_letter_rejection(self):
        """测试拒绝Windows驱动器字母"""
        assert validate_document_id("C:\\windows\\system32") is False
        assert validate_document_id("D:\\data\\file.txt") is False
        assert validate_document_id("c:\\temp") is False


class TestGetDocumentById:
    """测试文档查询功能"""
    
    def setup_method(self):
        """每个测试前清空缓存"""
        clear_document_cache()
    
    def teardown_method(self):
        """每个测试后清空缓存"""
        clear_document_cache()
    
    @patch('src.rag.document_service.get_vector_store')
    def test_get_valid_document(self, mock_get_vector_store):
        """测试查询有效文档返回正确内容"""
        # 模拟VectorStore返回
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc_123"],
            "documents": ["这是文档内容"],
            "metadatas": [{
                "filename": "test.txt",
                "source": "docs/knowledge/",
                "upload_time": "2026-01-15T10:30:00Z",
                "doc_id": "doc_123"
            }]
        }
        
        mock_vector_store = Mock()
        mock_vector_store.collection = mock_collection
        mock_get_vector_store.return_value = mock_vector_store
        
        # 查询文档
        result = get_document_by_id("doc_123")
        
        # 验证结果
        assert result is not None
        assert result["id"] == "doc_123"
        assert result["filename"] == "test.txt"
        assert result["content"] == "这是文档内容"
        assert result["metadata"]["source"] == "docs/knowledge/"
        assert result["metadata"]["created_at"] == "2026-01-15T10:30:00Z"
        assert result["metadata"]["file_size"] > 0
        
        # 验证调用
        mock_collection.get.assert_called_once_with(
            ids=["doc_123"],
            include=["documents", "metadatas"]
        )
    
    @patch('src.rag.document_service.get_vector_store')
    def test_get_nonexistent_document(self, mock_get_vector_store):
        """测试查询不存在的文档返回None"""
        # 模拟VectorStore返回空结果
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": []
        }
        
        mock_vector_store = Mock()
        mock_vector_store.collection = mock_collection
        mock_get_vector_store.return_value = mock_vector_store
        
        # 查询文档
        result = get_document_by_id("nonexistent_doc")
        
        # 验证返回None
        assert result is None
    
    def test_get_document_with_invalid_id(self):
        """测试查询无效文档ID返回None"""
        # 路径遍历攻击
        result = get_document_by_id("../etc/passwd")
        assert result is None
        
        # 绝对路径
        result = get_document_by_id("/etc/passwd")
        assert result is None
        
        # Windows驱动器
        result = get_document_by_id("C:\\windows\\system32")
        assert result is None
    
    @patch('src.rag.document_service.get_vector_store')
    def test_document_size_limit(self, mock_get_vector_store):
        """测试文档大小限制（超过10MB拒绝）"""
        # 创建超过10MB的文档内容
        large_content = "x" * (MAX_DOCUMENT_SIZE + 1)
        
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["large_doc"],
            "documents": [large_content],
            "metadatas": [{
                "filename": "large.txt",
                "source": "docs/",
                "upload_time": "2026-01-15",
                "doc_id": "large_doc"
            }]
        }
        
        mock_vector_store = Mock()
        mock_vector_store.collection = mock_collection
        mock_get_vector_store.return_value = mock_vector_store
        
        # 查询大文档
        result = get_document_by_id("large_doc")
        
        # 验证返回None（文档过大）
        assert result is None
    
    @patch('src.rag.document_service.get_vector_store')
    def test_lru_cache_behavior(self, mock_get_vector_store):
        """测试LRU缓存行为"""
        # 模拟VectorStore返回
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc_123"],
            "documents": ["缓存测试内容"],
            "metadatas": [{
                "filename": "cache_test.txt",
                "source": "docs/",
                "upload_time": "2026-01-15",
                "doc_id": "doc_123"
            }]
        }
        
        mock_vector_store = Mock()
        mock_vector_store.collection = mock_collection
        mock_get_vector_store.return_value = mock_vector_store
        
        # 第一次查询（缓存未命中）
        result1 = get_document_by_id("doc_123")
        assert result1 is not None
        assert mock_collection.get.call_count == 1
        
        # 第二次查询（缓存命中）
        result2 = get_document_by_id("doc_123")
        assert result2 is not None
        assert result2 == result1  # 返回相同对象
        assert mock_collection.get.call_count == 1  # 没有再次调用
        
        # 清空缓存
        clear_document_cache()
        
        # 第三次查询（缓存未命中）
        result3 = get_document_by_id("doc_123")
        assert result3 is not None
        assert mock_collection.get.call_count == 2  # 再次调用
    
    @patch('src.rag.document_service.get_vector_store')
    def test_cache_eviction(self, mock_get_vector_store):
        """测试缓存淘汰（LRU策略）"""
        # 模拟VectorStore
        def mock_get_side_effect(ids, include):
            doc_id = ids[0]
            return {
                "ids": [doc_id],
                "documents": [f"内容_{doc_id}"],
                "metadatas": [{
                    "filename": f"{doc_id}.txt",
                    "source": "docs/",
                    "upload_time": "2026-01-15",
                    "doc_id": doc_id
                }]
            }
        
        mock_collection = Mock()
        mock_collection.get.side_effect = mock_get_side_effect
        
        mock_vector_store = Mock()
        mock_vector_store.collection = mock_collection
        mock_get_vector_store.return_value = mock_vector_store
        
        # 查询101个不同的文档（超过缓存大小100）
        for i in range(101):
            doc_id = f"doc_{i}"
            result = get_document_by_id(doc_id)
            assert result is not None
        
        # 此时应该有101次调用（没有缓存命中）
        assert mock_collection.get.call_count == 101
        
        # 再次查询第100个文档（应该在缓存中）
        result = get_document_by_id("doc_100")
        assert result is not None
        assert mock_collection.get.call_count == 101  # 没有新调用
        
        # 再次查询第0个文档（应该已被淘汰）
        result = get_document_by_id("doc_0")
        assert result is not None
        assert mock_collection.get.call_count == 102  # 有新调用
    
    @patch('src.rag.document_service.get_vector_store')
    def test_exception_handling(self, mock_get_vector_store):
        """测试异常处理"""
        # 模拟VectorStore抛出异常
        mock_collection = Mock()
        mock_collection.get.side_effect = Exception("数据库连接失败")
        
        mock_vector_store = Mock()
        mock_vector_store.collection = mock_collection
        mock_get_vector_store.return_value = mock_vector_store
        
        # 查询文档
        result = get_document_by_id("doc_123")
        
        # 验证返回None（异常被捕获）
        assert result is None


class TestClearDocumentCache:
    """测试缓存清空功能"""
    
    @patch('src.rag.document_service.get_vector_store')
    def test_clear_cache(self, mock_get_vector_store):
        """测试清空缓存功能"""
        # 模拟VectorStore
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc_123"],
            "documents": ["内容"],
            "metadatas": [{
                "filename": "test.txt",
                "source": "docs/",
                "upload_time": "2026-01-15",
                "doc_id": "doc_123"
            }]
        }
        
        mock_vector_store = Mock()
        mock_vector_store.collection = mock_collection
        mock_get_vector_store.return_value = mock_vector_store
        
        # 查询文档（缓存）
        get_document_by_id("doc_123")
        assert mock_collection.get.call_count == 1
        
        # 再次查询（缓存命中）
        get_document_by_id("doc_123")
        assert mock_collection.get.call_count == 1
        
        # 清空缓存
        clear_document_cache()
        
        # 再次查询（缓存未命中）
        get_document_by_id("doc_123")
        assert mock_collection.get.call_count == 2
