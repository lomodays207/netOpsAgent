"""
测试知识库API的问题
"""
import sys
import os

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rag.vector_store import get_vector_store

def test_list_documents():
    """测试list_documents方法"""
    try:
        print("[测试] 初始化向量存储...")
        vector_store = get_vector_store()
        
        print(f"[测试] vector_store类型: {type(vector_store)}")
        print(f"[测试] list_documents类型: {type(vector_store.list_documents)}")
        
        print("[测试] 调用list_documents()...")
        documents = vector_store.list_documents()
        
        print(f"[测试] 成功! 返回 {len(documents)} 个文档")
        for doc in documents:
            print(f"  - {doc}")
            
    except Exception as e:
        print(f"[错误] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_list_documents()
