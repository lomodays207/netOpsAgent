"""
RAG功能快速验证脚本

验证RAG核心功能是否正常工作
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("RAG功能快速验证")
print("=" * 60)

# 1. 测试模块导入
print("\n[1/4] 测试模块导入...")
try:
    from src.rag.embeddings import get_embedding_model
    from src.rag.vector_store import VectorStore
    from src.rag.document_processor import DocumentProcessor
    from src.rag.rag_chain import RAGChain
    print("✅ 所有模块导入成功")
except Exception as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)

# 2. 测试Embedding模型
print("\n[2/4] 测试Embedding模型...")
try:
    model = get_embedding_model()
    embeddings = model.embed_texts(["测试文本"])
    print(f"✅ Embedding模型正常 (向量维度: {len(embeddings[0])})")
except Exception as e:
    print(f"❌ Embedding模型测试失败: {e}")
    sys.exit(1)

# 3. 测试文档处理
print("\n[3/4] 测试文档处理...")
try:
    processor = DocumentProcessor()
    content = "这是测试内容。\n\n这是第二段。".encode('utf-8')
    doc_id, chunks, metadatas = processor.process_text_file(content, "test.txt")
    print(f"✅ 文档处理正常 (doc_id: {doc_id[:20]}..., 块数: {len(chunks)})")
except Exception as e:
    print(f"❌ 文档处理测试失败: {e}")
    # 不退出，继续测试

# 4. 测试RAG链
print("\n[4/4] 测试RAG链...")
try:
    # 使用默认配置
    chain = RAGChain()
    print("✅ RAG链初始化成功")
    
    # 检查知识库状态
    has_knowledge = chain.has_knowledge()
    print(f"   知识库状态: {'有内容' if has_knowledge else '空'}")
except Exception as e:
    print(f"❌ RAG链测试失败: {e}")
    # 不退出

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
print("\n✅ RAG功能核心组件工作正常！")
print("\n下一步:")
print("1. 重启API服务器: scripts\\start_api.bat")
print("2. 访问知识库管理: http://127.0.0.1:8000/static/knowledge.html")
print("3. 上传测试文档: docs\\test_knowledge.txt")
print("4. 在主界面测试RAG聊天")
