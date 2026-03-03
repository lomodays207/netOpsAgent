"""
直接测试API端点来获取详细的错误堆栈
"""
import sys
import os
import traceback

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# 模拟FastAPI环境
os.environ['PYTHONPATH'] = os.path.join(os.path.dirname(__file__), '..', 'src')

def test_list_knowledge_endpoint():
    """测试list_knowledge端点"""
    try:
        print("[测试] 导入API模块...")
        from api import _init_rag_services
        
        print("[测试] 初始化RAG服务...")
        document_processor, vector_store, rag_chain = _init_rag_services()
        
        print(f"[测试] vector_store 类型: {type(vector_store)}")
        print(f"[测试] vector_store.list_documents 类型: {type(vector_store.list_documents)}")
        
        # 检查是否是方法
        import inspect
        if inspect.ismethod(vector_store.list_documents):
            print("[测试] list_documents 是一个方法")
        elif callable(vector_store.list_documents):
            print("[测试] list_documents 是可调用的")
        else:
            print(f"[错误] list_documents 不可调用! 类型: {type(vector_store.list_documents)}")
            print(f"[错误] 值: {vector_store.list_documents}")
        
        print("[测试] 调用 list_documents()...")
        documents = vector_store.list_documents()
        
        print(f"[成功] 返回 {len(documents)} 个文档")
        
    except Exception as e:
        print(f"\n[错误] {type(e).__name__}: {e}")
        print("\n完整堆栈:")
        traceback.print_exc()

if __name__ == "__main__":
    test_list_knowledge_endpoint()
