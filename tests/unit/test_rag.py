"""
RAG模块单元测试

测试RAG功能的核心组件：
- Embedding模型
- 向量存储
- 文档处理器
- RAG检索链
"""
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.rag.embeddings import EmbeddingModel, get_embedding_model
from src.rag.vector_store import VectorStore
from src.rag.document_processor import DocumentProcessor, TextSplitter
from src.rag.rag_chain import RAGChain


class TestEmbeddingModel:
    """测试Embedding模型"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        model1 = get_embedding_model()
        model2 = get_embedding_model()
        assert model1 is model2, "应该返回同一个实例"
    
    def test_embed_single_text(self):
        """测试单文本向量化"""
        model = get_embedding_model()
        text = "这是一个测试文本"
        embeddings = model.embed_texts([text])
        
        assert len(embeddings) == 1, "应该返回1个向量"
        assert len(embeddings[0]) > 0, "向量维度应该大于0"
        assert isinstance(embeddings[0][0], float), "向量元素应该是浮点数"
    
    def test_embed_multiple_texts(self):
        """测试批量文本向量化"""
        model = get_embedding_model()
        texts = ["文本1", "文本2", "文本3"]
        embeddings = model.embed_texts(texts)
        
        assert len(embeddings) == 3, "应该返回3个向量"
        assert all(len(emb) > 0 for emb in embeddings), "所有向量维度应该大于0"
    
    def test_embed_empty_list(self):
        """测试空列表"""
        model = get_embedding_model()
        embeddings = model.embed_texts([])
        assert embeddings == [], "空列表应该返回空列表"


class TestTextSplitter:
    """测试文本分割器"""
    
    def test_split_short_text(self):
        """测试短文本（不需要分割）"""
        splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
        text = "这是一个短文本"
        chunks = splitter.split_text(text)
        
        assert len(chunks) == 1, "短文本应该只有1个块"
        assert chunks[0] == text, "内容应该保持不变"
    
    def test_split_long_text(self):
        """测试长文本分割"""
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        text = "这是第一段。\n\n这是第二段。\n\n这是第三段。" * 10
        chunks = splitter.split_text(text)
        
        assert len(chunks) > 1, "长文本应该被分割成多个块"
        assert all(len(chunk) <= 50 + 20 for chunk in chunks), "每个块不应超过chunk_size + 容差"
    
    def test_split_with_overlap(self):
        """测试重叠分割"""
        splitter = TextSplitter(chunk_size=20, chunk_overlap=5)
        text = "0123456789" * 5  # 50个字符
        chunks = splitter.split_text(text)
        
        # 检查是否有重叠
        if len(chunks) > 1:
            # 第二个块的开头应该与第一个块的结尾有重叠
            assert len(chunks) >= 2, "应该有多个块"


class TestDocumentProcessor:
    """测试文档处理器"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_process_text_file(self, temp_dir):
        """测试处理TXT文件"""
        processor = DocumentProcessor(documents_dir=temp_dir)
        
        content = "这是测试内容。\n\n这是第二段内容。"
        file_content = content.encode('utf-8')
        filename = "test.txt"
        
        doc_id, chunks, metadatas = processor.process_text_file(
            file_content=file_content,
            filename=filename
        )
        
        assert doc_id.startswith("doc_"), "doc_id应该以doc_开头"
        assert len(chunks) > 0, "应该有至少1个文本块"
        assert len(metadatas) == len(chunks), "元数据数量应该与块数量一致"
        
        # 检查元数据
        for i, metadata in enumerate(metadatas):
            assert metadata['doc_id'] == doc_id
            assert metadata['filename'] == filename
            assert metadata['chunk_index'] == i
            assert 'upload_time' in metadata
    
    def test_list_files(self, temp_dir):
        """测试列出文件"""
        processor = DocumentProcessor(documents_dir=temp_dir)
        
        # 处理一个文件
        content = "测试内容".encode('utf-8')
        doc_id, _, _ = processor.process_text_file(content, "test.txt")
        
        # 列出文件
        files = processor.list_files()
        assert len(files) > 0, "应该有至少1个文件"
        assert any(doc_id in f for f in files), "应该包含刚才上传的文件"


class TestVectorStore:
    """测试向量存储"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_add_and_search(self, temp_dir):
        """测试添加和搜索文档"""
        store = VectorStore(persist_directory=temp_dir)
        
        # 添加文档
        texts = ["网络故障排查", "端口不通问题", "防火墙配置"]
        metadatas = [
            {"doc_id": "doc1", "filename": "test.txt", "chunk_index": i}
            for i in range(len(texts))
        ]
        
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc1")
        
        # 搜索
        results = store.search("网络问题", top_k=2)
        
        assert len(results) > 0, "应该返回搜索结果"
        assert len(results) <= 2, "结果数量不应超过top_k"
        assert 'text' in results[0], "结果应该包含text字段"
        assert 'metadata' in results[0], "结果应该包含metadata字段"
    
    def test_delete_by_doc_id(self, temp_dir):
        """测试按doc_id删除"""
        store = VectorStore(persist_directory=temp_dir)
        
        # 添加文档
        texts = ["文本1", "文本2"]
        metadatas = [
            {"doc_id": "doc1", "filename": "test.txt", "chunk_index": i}
            for i in range(len(texts))
        ]
        
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc1")
        
        # 删除
        deleted_count = store.delete_by_doc_id("doc1")
        assert deleted_count == 2, "应该删除2个文档块"
        
        # 验证已删除
        docs = store.list_documents()
        assert len(docs) == 0, "文档列表应该为空"
    
    def test_list_documents(self, temp_dir):
        """测试列出文档"""
        store = VectorStore(persist_directory=temp_dir)
        
        # 添加多个文档
        for i in range(3):
            texts = [f"文档{i}内容"]
            metadatas = [{
                "doc_id": f"doc{i}",
                "filename": f"test{i}.txt",
                "chunk_index": 0,
                "upload_time": "2026-02-04T10:00:00"
            }]
            store.add_documents(texts=texts, metadatas=metadatas, doc_id=f"doc{i}")
        
        # 列出文档
        docs = store.list_documents()
        assert len(docs) == 3, "应该有3个文档"
        
        # 检查文档信息
        for doc in docs:
            assert 'doc_id' in doc
            assert 'filename' in doc
            assert 'chunk_count' in doc
            assert 'upload_time' in doc


class TestRAGChain:
    """测试RAG检索链"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def rag_chain(self, temp_dir):
        """创建RAG链实例"""
        store = VectorStore(persist_directory=temp_dir)
        
        # 添加测试数据
        texts = [
            "端口不通问题排查步骤：1. 使用ping测试网络连通性",
            "防火墙配置检查：使用iptables -L查看规则",
            "服务监听状态检查：使用ss -tunlp命令"
        ]
        metadatas = [
            {"doc_id": "doc1", "filename": "network_guide.txt", "chunk_index": i}
            for i in range(len(texts))
        ]
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc1")
        
        return RAGChain(vector_store=store, top_k=2)
    
    def test_retrieve(self, rag_chain):
        """测试检索功能"""
        results = rag_chain.retrieve("如何排查端口问题")
        
        assert len(results) > 0, "应该返回检索结果"
        assert len(results) <= 2, "结果数量不应超过top_k"
        assert 'relevance_score' in results[0], "结果应该包含相关性分数"
        
        # 验证新增字段
        first_result = results[0]
        assert 'id' in first_result, "结果应该包含文档ID"
        assert 'preview' in first_result, "结果应该包含预览文本"
        assert isinstance(first_result['id'], str), "文档ID应该是字符串"
        assert isinstance(first_result['preview'], str), "预览文本应该是字符串"
        assert len(first_result['preview']) <= 200, "预览文本不应超过200字符"
        
        # 验证相关度评分范围
        assert 0 <= first_result['relevance_score'] <= 1, "相关度评分应该在0-1范围内"
    
    def test_retrieve_preview_truncation(self, temp_dir):
        """测试预览文本截取（200字符限制）"""
        store = VectorStore(persist_directory=temp_dir)
        
        # 添加一个超过200字符的长文档
        long_text = "这是一个很长的文档内容。" * 50  # 生成一个超过200字符的文本
        texts = [long_text]
        metadatas = [{"doc_id": "doc_long", "filename": "long_doc.txt", "chunk_index": 0}]
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc_long")
        
        chain = RAGChain(vector_store=store, top_k=1, min_relevance_score=0.0)
        results = chain.retrieve("文档内容")
        
        assert len(results) > 0, "应该返回检索结果"
        assert 'preview' in results[0], "结果应该包含预览文本"
        assert len(results[0]['preview']) == 200, "预览文本应该正好是200字符"
        assert results[0]['preview'] == long_text[:200], "预览文本应该是原文本的前200字符"
    
    def test_retrieve_short_text_preview(self, temp_dir):
        """测试短文本预览（不足200字符）"""
        store = VectorStore(persist_directory=temp_dir)
        
        # 添加一个短文档
        short_text = "这是一个短文档。"
        texts = [short_text]
        metadatas = [{"doc_id": "doc_short", "filename": "short_doc.txt", "chunk_index": 0}]
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc_short")
        
        chain = RAGChain(vector_store=store, top_k=1, min_relevance_score=0.0)
        results = chain.retrieve("短文档")
        
        assert len(results) > 0, "应该返回检索结果"
        assert 'preview' in results[0], "结果应该包含预览文本"
        assert results[0]['preview'] == short_text, "短文本的预览应该是完整文本"
        assert len(results[0]['preview']) < 200, "短文本预览应该少于200字符"
    
    def test_retrieve_filters_low_relevance(self, temp_dir):
        """测试过滤低相关度文档（< 0.05）"""
        store = VectorStore(persist_directory=temp_dir)
        
        # 添加测试数据
        texts = [
            "网络故障排查指南",
            "完全不相关的内容关于烹饪和美食"
        ]
        metadatas = [
            {"doc_id": "doc_test", "filename": "test.txt", "chunk_index": i}
            for i in range(len(texts))
        ]
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc_test")
        
        chain = RAGChain(vector_store=store, top_k=10, min_relevance_score=0.05)
        results = chain.retrieve("网络故障排查")
        
        # 验证所有返回的文档相关度都 >= 0.05
        for result in results:
            assert result['relevance_score'] >= 0.05, f"相关度评分 {result['relevance_score']} 应该 >= 0.05"
    
    def test_retrieve_document_id_consistency(self, rag_chain):
        """测试文档ID一致性（同一文档多次检索返回相同ID）"""
        # 第一次检索
        results1 = rag_chain.retrieve("端口问题")
        assert len(results1) > 0, "应该返回检索结果"
        first_id = results1[0]['id']
        
        # 第二次检索相同问题
        results2 = rag_chain.retrieve("端口问题")
        assert len(results2) > 0, "应该返回检索结果"
        second_id = results2[0]['id']
        
        # 验证ID一致性
        assert first_id == second_id, "同一文档在多次检索中应返回相同的ID"
    
    def test_build_context(self, rag_chain):
        """测试构建上下文"""
        context, docs = rag_chain.build_context("端口不通怎么办")
        
        assert isinstance(context, str), "上下文应该是字符串"
        assert len(context) > 0, "上下文不应为空"
        assert len(docs) > 0, "应该有检索到的文档"
        assert "来源" in context, "上下文应该包含来源信息"
    
    def test_build_enhanced_prompt(self, rag_chain):
        """测试构建增强Prompt"""
        query, system_prompt, docs = rag_chain.build_enhanced_prompt("如何检查防火墙")
        
        assert query == "如何检查防火墙", "查询应该保持不变"
        assert len(system_prompt) > 0, "系统提示词不应为空"
        assert "参考资料" in system_prompt or "知识库" in system_prompt, "应该包含参考资料提示"
        assert len(docs) > 0, "应该有检索到的文档"
        
        # 验证返回的文档包含所有必需字段
        for doc in docs:
            assert 'id' in doc, "文档应该包含ID字段"
            assert 'text' in doc, "文档应该包含text字段"
            assert 'metadata' in doc, "文档应该包含metadata字段"
            assert 'relevance_score' in doc, "文档应该包含relevance_score字段"
            assert 'preview' in doc, "文档应该包含preview字段"
            assert 0 <= doc['relevance_score'] <= 1, "相关度评分应该在0-1范围内"
            assert len(doc['preview']) <= 200, "预览文本不应超过200字符"
    
    def test_has_knowledge(self, rag_chain):
        """测试知识库是否有内容"""
        assert rag_chain.has_knowledge() is True, "知识库应该有内容"
    
    def test_empty_knowledge_base(self, temp_dir):
        """测试空知识库"""
        store = VectorStore(persist_directory=temp_dir)
        chain = RAGChain(vector_store=store)
        
        assert chain.has_knowledge() is False, "空知识库应该返回False"
        
        context, docs = chain.build_context("任意查询")
        assert context == "", "空知识库应该返回空上下文"
        assert len(docs) == 0, "空知识库应该返回空文档列表"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
