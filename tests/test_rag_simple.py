"""
RAG模块简单测试脚本

直接运行测试，不依赖pytest框架
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径 (tests/test_rag_simple.py -> netOpsAgent/)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print(f"项目根目录: {project_root}")
print(f"Python路径: {sys.path[0]}")

try:
    from src.rag.embeddings import EmbeddingModel, get_embedding_model
    from src.rag.vector_store import VectorStore
    from src.rag.document_processor import DocumentProcessor, TextSplitter
    from src.rag.rag_chain import RAGChain
    print("✅ 模块导入成功")
except Exception as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)


def test_embedding_model():
    """测试Embedding模型"""
    print("\n=== 测试Embedding模型 ===")
    
    try:
        # 测试单例模式
        model1 = get_embedding_model()
        model2 = get_embedding_model()
        assert model1 is model2, "单例模式失败"
        print("✅ 单例模式测试通过")
        
        # 测试单文本向量化
        text = "这是一个测试文本"
        embeddings = model1.embed_texts([text])
        assert len(embeddings) == 1, "向量数量错误"
        assert len(embeddings[0]) > 0, "向量维度错误"
        print(f"✅ 单文本向量化测试通过 (维度: {len(embeddings[0])})")
        
        # 测试批量向量化
        texts = ["文本1", "文本2", "文本3"]
        embeddings = model1.embed_texts(texts)
        assert len(embeddings) == 3, "批量向量化失败"
        print("✅ 批量向量化测试通过")
        
        return True
    except Exception as e:
        print(f"❌ Embedding模型测试失败: {e}")
        return False


def test_text_splitter():
    """测试文本分割器"""
    print("\n=== 测试文本分割器 ===")
    
    try:
        splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
        
        # 测试短文本
        short_text = "这是一个短文本"
        chunks = splitter.split_text(short_text)
        assert len(chunks) == 1, "短文本分割错误"
        print("✅ 短文本分割测试通过")
        
        # 测试长文本
        long_text = "这是第一段。\n\n这是第二段。\n\n这是第三段。" * 10
        chunks = splitter.split_text(long_text)
        assert len(chunks) > 1, "长文本分割失败"
        print(f"✅ 长文本分割测试通过 (分割为{len(chunks)}个块)")
        
        return True
    except Exception as e:
        print(f"❌ 文本分割器测试失败: {e}")
        return False


def test_document_processor():
    """测试文档处理器"""
    print("\n=== 测试文档处理器 ===")
    
    temp_dir = tempfile.mkdtemp()
    try:
        processor = DocumentProcessor(documents_dir=temp_dir)
        
        # 测试处理TXT文件
        content = "这是测试内容。\n\n这是第二段内容。"
        file_content = content.encode('utf-8')
        filename = "test.txt"
        
        doc_id, chunks, metadatas = processor.process_text_file(
            file_content=file_content,
            filename=filename
        )
        
        assert doc_id.startswith("doc_"), "doc_id格式错误"
        assert len(chunks) > 0, "文本块数量错误"
        assert len(metadatas) == len(chunks), "元数据数量不匹配"
        print(f"✅ 文档处理测试通过 (doc_id: {doc_id}, 块数: {len(chunks)})")
        
        # 测试列出文件
        files = processor.list_files()
        assert len(files) > 0, "文件列表为空"
        print(f"✅ 文件列表测试通过 (文件数: {len(files)})")
        
        return True
    except Exception as e:
        print(f"❌ 文档处理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_vector_store():
    """测试向量存储"""
    print("\n=== 测试向量存储 ===")
    
    temp_dir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_directory=temp_dir)
        
        # 测试添加文档
        texts = ["网络故障排查", "端口不通问题", "防火墙配置"]
        metadatas = [
            {"doc_id": "doc1", "filename": "test.txt", "chunk_index": i}
            for i in range(len(texts))
        ]
        
        store.add_documents(texts=texts, metadatas=metadatas, doc_id="doc1")
        print("✅ 文档添加测试通过")
        
        # 测试搜索
        results = store.search("网络问题", top_k=2)
        assert len(results) > 0, "搜索结果为空"
        assert 'text' in results[0], "搜索结果格式错误"
        print(f"✅ 文档搜索测试通过 (找到{len(results)}个结果)")
        
        # 测试删除
        deleted_count = store.delete_by_doc_id("doc1")
        assert deleted_count == 3, "删除数量错误"
        print("✅ 文档删除测试通过")
        
        # 测试列出文档
        docs = store.list_documents()
        assert len(docs) == 0, "文档列表应该为空"
        print("✅ 文档列表测试通过")
        
        return True
    except Exception as e:
        print(f"❌ 向量存储测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_rag_chain():
    """测试RAG检索链"""
    print("\n=== 测试RAG检索链 ===")
    
    temp_dir = tempfile.mkdtemp()
    try:
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
        
        chain = RAGChain(vector_store=store, top_k=2)
        
        # 测试检索
        results = chain.retrieve("如何排查端口问题")
        assert len(results) > 0, "检索结果为空"
        assert 'relevance_score' in results[0], "缺少相关性分数"
        print(f"✅ RAG检索测试通过 (找到{len(results)}个结果)")
        
        # 测试构建上下文
        context, docs = chain.build_context("端口不通怎么办")
        assert len(context) > 0, "上下文为空"
        assert len(docs) > 0, "文档列表为空"
        print("✅ 上下文构建测试通过")
        
        # 测试构建增强Prompt
        query, system_prompt, docs = chain.build_enhanced_prompt("如何检查防火墙")
        assert len(system_prompt) > 0, "系统提示词为空"
        assert "参考资料" in system_prompt or "知识库" in system_prompt, "缺少参考资料提示"
        print("✅ Prompt增强测试通过")
        
        # 测试知识库状态
        assert chain.has_knowledge() is True, "知识库状态错误"
        print("✅ 知识库状态测试通过")
        
        return True
    except Exception as e:
        print(f"❌ RAG检索链测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def main():
    """运行所有测试"""
    print("=" * 60)
    print("RAG模块测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("Embedding模型", test_embedding_model()))
    results.append(("文本分割器", test_text_splitter()))
    results.append(("文档处理器", test_document_processor()))
    results.append(("向量存储", test_vector_store()))
    results.append(("RAG检索链", test_rag_chain()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed}个通过, {failed}个失败")
    
    if failed == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有{failed}个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
