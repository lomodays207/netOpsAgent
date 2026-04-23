"""
文档服务模块

提供文档查询、缓存和安全验证功能
"""
import re
from functools import lru_cache
from typing import Optional, Dict, Any

from .vector_store import get_vector_store


# 文档大小限制（10MB）
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB in bytes


def validate_document_id(doc_id: str) -> bool:
    """
    验证文档ID的合法性，防止路径遍历攻击
    
    Args:
        doc_id: 文档ID
        
    Returns:
        True if valid, False otherwise
    """
    if not doc_id:
        return False
    
    # 检测路径遍历攻击模式
    # 拒绝包含 ../ 或 ..\ 的ID
    if "../" in doc_id or "..\\" in doc_id:
        return False
    
    # 拒绝包含绝对路径的ID
    if doc_id.startswith("/") or doc_id.startswith("\\"):
        return False
    
    # 拒绝包含驱动器字母的ID (Windows)
    if re.match(r"^[a-zA-Z]:", doc_id):
        return False
    
    return True


@lru_cache(maxsize=100)
def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    """
    根据文档ID获取完整文档内容（带LRU缓存）
    
    Args:
        doc_id: 文档ID（ChromaDB的文档ID）
        
    Returns:
        文档对象，包含:
        - id: 文档ID
        - filename: 文件名
        - content: 完整内容
        - metadata: 元数据
        
        如果文档不存在或无效，返回None
    """
    # 验证文档ID
    if not validate_document_id(doc_id):
        print(f"[DocumentService] 无效的文档ID: {doc_id}")
        return None
    
    try:
        # 从VectorStore查询文档
        vector_store = get_vector_store()
        
        # 使用ChromaDB的get方法通过ID查询
        results = vector_store.collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"]
        )
        
        if not results or not results.get("ids") or len(results["ids"]) == 0:
            print(f"[DocumentService] 文档不存在: {doc_id}")
            return None
        
        # 提取文档内容和元数据
        content = results["documents"][0] if results.get("documents") else ""
        metadata = results["metadatas"][0] if results.get("metadatas") else {}
        
        # 检查文档大小
        content_size = len(content.encode('utf-8'))
        if content_size > MAX_DOCUMENT_SIZE:
            print(f"[DocumentService] 文档过大: {doc_id}, 大小: {content_size} bytes")
            return None
        
        # 构造返回对象
        document = {
            "id": doc_id,
            "filename": metadata.get("filename", "未知文件"),
            "content": content,
            "metadata": {
                "source": metadata.get("source", ""),
                "created_at": metadata.get("upload_time", ""),
                "file_size": content_size,
                "doc_id": metadata.get("doc_id", "")
            }
        }
        
        print(f"[DocumentService] 成功获取文档: {doc_id}, 大小: {content_size} bytes")
        return document
        
    except Exception as e:
        print(f"[DocumentService] 查询文档失败: {doc_id}, 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def clear_document_cache():
    """
    清空文档缓存
    
    用于测试或需要强制刷新缓存的场景
    """
    get_document_by_id.cache_clear()
    print("[DocumentService] 文档缓存已清空")
