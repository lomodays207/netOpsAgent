"""
RAG检索链

整合检索和生成，提供RAG增强的问答功能
"""
from typing import List, Dict, Any, Optional

from .vector_store import VectorStore, get_vector_store


class RAGChain:
    """
    RAG检索链
    
    检索相关文档并构造增强Prompt
    """
    
    def __init__(
        self,
        vector_store: VectorStore = None,
        top_k: int = 5,
        min_relevance_score: float = 0.05
    ):
        """
        初始化RAG检索链
        
        Args:
            vector_store: 向量存储实例
            top_k: 检索返回的文档数量
            min_relevance_score: 最小相关性分数（0-1，越大越相关）
        """
        self.vector_store = vector_store or get_vector_store()
        self.top_k = top_k
        self.min_relevance_score = min_relevance_score
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        filter_dict: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回数量（可选）
            filter_dict: 过滤条件
            
        Returns:
            相关文档列表
        """
        k = top_k or self.top_k
        results = self.vector_store.search(query, top_k=k, filter_dict=filter_dict)
        
        # 过滤低相关性结果（ChromaDB的distance越小越相关）
        # 将distance转换为相关性分数：1 - distance
        filtered_results = []
        for result in results:
            relevance = 1 - result.get("distance", 1.0)
            if relevance >= self.min_relevance_score:
                result["relevance_score"] = relevance
                filtered_results.append(result)
        
        return filtered_results
    
    def build_context(
        self,
        query: str,
        top_k: int = None
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        构建RAG上下文
        
        Args:
            query: 用户问题
            top_k: 返回数量
            
        Returns:
            (上下文文本, 检索到的文档列表)
        """
        # 检索相关文档
        relevant_docs = self.retrieve(query, top_k=top_k)
        
        if not relevant_docs:
            return "", []
        
        # 构建上下文
        context_parts = []
        for i, doc in enumerate(relevant_docs, 1):
            filename = doc.get("metadata", {}).get("filename", "未知来源")
            text = doc.get("text", "")
            relevance = doc.get("relevance_score", 0)
            context_parts.append(f"[来源 {i}: {filename}，相关度: {relevance:.2f}]\n{text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        return context, relevant_docs
    
    def build_enhanced_prompt(
        self,
        query: str,
        top_k: int = None,
        system_prompt_template: str = None
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        """
        构建RAG增强的Prompt
        
        Args:
            query: 用户问题
            top_k: 返回数量
            system_prompt_template: 系统提示词模板
            
        Returns:
            (增强后的用户prompt, 系统prompt, 检索到的文档列表)
        """
        # 获取上下文
        context, docs = self.build_context(query, top_k=top_k)
        
        # 默认系统提示词
        if system_prompt_template is None:
            system_prompt_template = """你是一个专业的网络故障诊断助手。你的主要职责是帮助用户诊断和解决网络问题。

当用户提问时，你应该：
1. 优先参考提供的知识库内容来回答问题
2. 如果知识库中有相关信息，请基于这些信息进行回答
3. 如果知识库中没有相关信息，可以基于你的专业知识回答
4. 回答要准确、专业、易于理解

{rag_instruction}

请用简洁、专业但友好的语气回答。"""
        
        # 构建RAG指令
        if context:
            rag_instruction = f"""以下是从知识库中检索到的相关参考资料，请在回答时优先参考这些内容：

【参考资料开始】
{context}
【参考资料结束】"""
        else:
            rag_instruction = "（注意：知识库中没有找到与当前问题相关的内容，请基于你的专业知识回答）"
        
        # 替换模板中的占位符
        system_prompt = system_prompt_template.format(rag_instruction=rag_instruction)
        
        return query, system_prompt, docs
    
    def has_knowledge(self) -> bool:
        """
        检查知识库是否有内容
        
        Returns:
            是否有知识库内容
        """
        stats = self.vector_store.get_stats()
        return stats.get("total_chunks", 0) > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取RAG统计信息
        
        Returns:
            统计信息
        """
        return {
            "vector_store": self.vector_store.get_stats(),
            "top_k": self.top_k,
            "min_relevance_score": self.min_relevance_score
        }


# 单例模式
_rag_chain_instance: Optional[RAGChain] = None


def get_rag_chain() -> RAGChain:
    """
    获取RAG链单例
    
    Returns:
        RAGChain实例
    """
    global _rag_chain_instance
    if _rag_chain_instance is None:
        _rag_chain_instance = RAGChain()
    return _rag_chain_instance
