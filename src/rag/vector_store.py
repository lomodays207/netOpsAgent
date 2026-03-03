"""
ChromaDB向量存储管理

提供文档向量的存储、检索和管理功能
"""
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings

from .embeddings import ChromaEmbeddingFunction, get_embedding_model


# 默认存储路径
DEFAULT_PERSIST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "runtime", "knowledge_base", "vectordb"
)

# 默认集合名称
DEFAULT_COLLECTION_NAME = "netops_knowledge"


class VectorStore:
    """
    向量存储管理类
    
    使用ChromaDB进行向量存储和检索
    """
    
    def __init__(
        self, 
        persist_directory: str = None,
        collection_name: str = None
    ):
        """
        初始化向量存储
        
        Args:
            persist_directory: 持久化目录路径
            collection_name: 集合名称
        """
        self.persist_directory = persist_directory or DEFAULT_PERSIST_DIR
        self.collection_name = collection_name or DEFAULT_COLLECTION_NAME
        
        # 确保目录存在
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 获取或创建集合
        self.embedding_function = ChromaEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"description": "netOpsAgent知识库"}
        )
        
        print(f"[VectorStore] 初始化完成，集合: {self.collection_name}, 文档数: {self.collection.count()}")
    
    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]] = None,
        ids: List[str] = None,
        doc_id: str = None
    ) -> List[str]:
        """
        添加文档到向量存储
        
        Args:
            texts: 文本列表
            metadatas: 元数据列表
            ids: 文档ID列表（可选，自动生成）
            doc_id: 文档ID（用于关联所有chunk）
            
        Returns:
            文档ID列表
        """
        if not texts:
            return []
        
        # 生成ID
        if ids is None:
            ids = [f"{doc_id or 'doc'}_{uuid.uuid4().hex[:8]}_{i}" for i in range(len(texts))]
        
        # 确保元数据存在
        if metadatas is None:
            metadatas = [{"doc_id": doc_id} for _ in texts]
        else:
            # 确保每个metadata都有doc_id
            for meta in metadatas:
                if doc_id and "doc_id" not in meta:
                    meta["doc_id"] = doc_id
        
        # 添加到集合
        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"[VectorStore] 添加了 {len(texts)} 个文档块")
        return ids
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_dict: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_dict: 过滤条件
            
        Returns:
            搜索结果列表，每个结果包含:
            - id: 文档块ID
            - text: 文档内容
            - metadata: 元数据
            - distance: 距离分数
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filter_dict
        )
        
        # 转换结果格式
        documents = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                doc = {
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0
                }
                documents.append(doc)
        
        return documents
    
    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        删除指定文档ID的所有块
        
        Args:
            doc_id: 文档ID
            
        Returns:
            删除的文档块数量
        """
        # 先查询该doc_id下的所有文档
        results = self.collection.get(
            where={"doc_id": doc_id}
        )
        
        if results and results["ids"]:
            count = len(results["ids"])
            self.collection.delete(ids=results["ids"])
            print(f"[VectorStore] 删除了文档 {doc_id} 的 {count} 个块")
            return count
        
        return 0
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        列出所有唯一的文档（按doc_id分组）
        
        Returns:
            文档列表，每个文档包含:
            - doc_id: 文档ID
            - filename: 文件名
            - chunk_count: 块数量
            - upload_time: 上传时间
        """
        try:
            print(f"[VectorStore.list_documents] 开始获取文档列表...")
            print(f"[VectorStore.list_documents] collection类型: {type(self.collection)}")
            print(f"[VectorStore.list_documents] collection.get类型: {type(self.collection.get)}")
            
            # 获取所有文档
            results = self.collection.get()
            print(f"[VectorStore.list_documents] results类型: {type(results)}")
            
            if not results or not results.get("metadatas"):
                print("[VectorStore.list_documents] 没有找到文档")
                return []
            
            # 按doc_id分组统计
            doc_map = {}
            for metadata in results["metadatas"]:
                doc_id = metadata.get("doc_id", "unknown")
                if doc_id not in doc_map:
                    doc_map[doc_id] = {
                        "doc_id": doc_id,
                        "filename": metadata.get("filename", "未知文件"),
                        "upload_time": metadata.get("upload_time", ""),
                        "chunk_count": 0
                    }
                doc_map[doc_id]["chunk_count"] += 1
            
            print(f"[VectorStore.list_documents] 找到 {len(doc_map)} 个文档")
            result_list = list(doc_map.values())
            
            # 按上传时间(upload_time)倒序排列，最新的在前
            result_list.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
            
            print(f"[VectorStore.list_documents] 返回列表类型: {type(result_list)}")
            return result_list
        except Exception as e:
            print(f"[VectorStore.list_documents] 错误: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "collection_name": self.collection_name,
            "total_chunks": self.collection.count(),
            "persist_directory": self.persist_directory
        }
    
    def clear(self):
        """清空所有文档"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"description": "netOpsAgent知识库"}
        )
        print(f"[VectorStore] 已清空集合 {self.collection_name}")


# 单例模式
_vector_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """
    获取向量存储单例
    
    Returns:
        VectorStore实例
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
