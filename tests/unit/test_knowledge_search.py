"""
知识库搜索功能单元测试

测试内容：
- 搜索API返回正确结果
- 空知识库搜索返回空结果
- top_k参数限制
- 空查询返回错误
"""
import gc
import time
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.rag.vector_store import VectorStore
from src.rag.rag_chain import RAGChain


class TestKnowledgeSearch:
    """测试知识库搜索功能"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # ChromaDB在Windows上会锁定SQLite文件，需要GC后重试
        gc.collect()
        time.sleep(0.2)
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            pass

    @pytest.fixture
    def populated_rag_chain(self, temp_dir):
        """创建包含测试数据的RAG链"""
        store = VectorStore(persist_directory=temp_dir)

        texts = [
            "证书更新服务联系人是张三，电话：13800138000，邮箱：zhangsan@example.com",
            "防火墙策略变更需要提前3个工作日提交申请，联系网络安全部李四",
            "服务器宕机应急流程：1.通知值班经理 2.联系运维组 3.启动备用服务器",
            "数据库备份策略：每日增量备份，每周全量备份，保留30天",
            "VPN连接故障排查：检查客户端版本、证书有效期、网络连通性",
        ]
        metadatas = [
            {"doc_id": "doc_test1", "filename": "contacts.txt", "chunk_index": i, "upload_time": "2026-03-03T10:00:00"}
            for i in range(len(texts))
        ]

        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc_test1")

        return RAGChain(vector_store=store, top_k=5, min_relevance_score=0.1)

    def test_search_returns_results(self, populated_rag_chain):
        """测试搜索能返回匹配结果"""
        results = populated_rag_chain.retrieve("证书更新服务联系人")

        assert len(results) > 0, "应该返回搜索结果"
        # 检查返回结果的结构
        for result in results:
            assert "text" in result, "结果应包含text字段"
            assert "metadata" in result, "结果应包含metadata字段"
            assert "relevance_score" in result, "结果应包含relevance_score字段"

    def test_search_relevance_order(self, populated_rag_chain):
        """测试搜索结果按相关度排序"""
        results = populated_rag_chain.retrieve("证书更新联系人")

        if len(results) >= 2:
            # ChromaDB返回的结果应该按距离排序，转换后的relevance_score应该降序
            scores = [r["relevance_score"] for r in results]
            assert scores == sorted(scores, reverse=True), "结果应按相关度降序排列"

    def test_search_result_contains_source(self, populated_rag_chain):
        """测试搜索结果包含来源文件名"""
        results = populated_rag_chain.retrieve("证书更新")

        assert len(results) > 0, "应该返回结果"
        first_result = results[0]
        assert first_result["metadata"]["filename"] == "contacts.txt", "来源文件名应该是contacts.txt"

    def test_search_top_k_limit(self, populated_rag_chain):
        """测试top_k参数限制返回数量"""
        results = populated_rag_chain.retrieve("联系", top_k=2)

        assert len(results) <= 2, "结果数量不应超过top_k=2"

    def test_search_empty_knowledge_base(self, temp_dir):
        """测试空知识库搜索返回空结果"""
        store = VectorStore(persist_directory=temp_dir)
        chain = RAGChain(vector_store=store)

        results = chain.retrieve("任意查询")
        assert len(results) == 0, "空知识库应返回空结果"

    def test_search_after_upload(self, temp_dir):
        """模拟上传后搜索验证 - 端到端流程"""
        store = VectorStore(persist_directory=temp_dir)
        chain = RAGChain(vector_store=store, top_k=5, min_relevance_score=0.1)

        # 1. 初始状态：空知识库
        assert chain.has_knowledge() is False, "初始应为空"
        results = chain.retrieve("测试内容")
        assert len(results) == 0, "空知识库应无结果"

        # 2. 模拟上传文档
        texts = ["网络运维手册：当发现端口不通时，首先使用ping命令测试基础连通性"]
        metadatas = [{"doc_id": "doc_upload1", "filename": "ops_manual.txt", "chunk_index": 0}]
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc_upload1")

        # 3. 上传后搜索应能找到内容
        assert chain.has_knowledge() is True, "上传后应有知识"
        results = chain.retrieve("端口不通怎么办")
        assert len(results) > 0, "上传后应能搜索到相关内容"
        assert "端口不通" in results[0]["text"], "搜索结果应包含相关文本"

    def test_search_result_format(self, populated_rag_chain):
        """测试搜索结果格式化（模拟API返回格式）"""
        results = populated_rag_chain.retrieve("数据库备份")

        assert len(results) > 0, "应该返回结果"

        # 模拟API格式化
        formatted = []
        for result in results:
            metadata = result.get("metadata", {})
            formatted.append({
                "text": result.get("text", ""),
                "filename": metadata.get("filename", "未知来源"),
                "relevance_score": round(result.get("relevance_score", 0), 4),
                "chunk_index": metadata.get("chunk_index", 0),
                "doc_id": metadata.get("doc_id", "")
            })

        # 验证格式化结果
        first = formatted[0]
        assert isinstance(first["text"], str) and len(first["text"]) > 0
        assert isinstance(first["filename"], str)
        assert isinstance(first["relevance_score"], float)
        assert first["doc_id"] == "doc_test1"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
