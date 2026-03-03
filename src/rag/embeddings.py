"""
Embedding模型封装

使用sentence-transformers加载bge-small-zh-v1.5模型进行文本向量化
"""
import os
from typing import List, Optional
from functools import lru_cache

# 延迟导入，避免启动时加载模型
_model = None
_model_name = "BAAI/bge-small-zh-v1.5"


class EmbeddingModel:
    """
    Embedding模型封装类
    
    使用bge-small-zh-v1.5模型进行中文文本向量化
    """
    
    def __init__(self, model_name: str = None):
        """
        初始化Embedding模型
        
        Args:
            model_name: 模型名称，默认使用bge-small-zh-v1.5
        """
        self.model_name = model_name or _model_name
        self._model = None
        
    def _load_model(self):
        """延迟加载模型"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"[EmbeddingModel] 正在加载模型: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            print(f"[EmbeddingModel] 模型加载完成")
        return self._model
    
    def embed_text(self, text: str) -> List[float]:
        """
        将单个文本转换为向量
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
        """
        model = self._load_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        批量将文本转换为向量
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表的列表
        """
        if not texts:
            return []
        model = self._load_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()
    
    @property
    def dimension(self) -> int:
        """获取向量维度"""
        model = self._load_model()
        return model.get_sentence_embedding_dimension()


# 单例模式
_embedding_model_instance: Optional[EmbeddingModel] = None


def get_embedding_model() -> EmbeddingModel:
    """
    获取Embedding模型单例
    
    Returns:
        EmbeddingModel实例
    """
    global _embedding_model_instance
    if _embedding_model_instance is None:
        _embedding_model_instance = EmbeddingModel()
    return _embedding_model_instance


# ChromaDB需要的embedding函数封装
class ChromaEmbeddingFunction:
    """
    ChromaDB兼容的Embedding函数封装
    """
    
    def __init__(self, embedding_model: EmbeddingModel = None):
        self.embedding_model = embedding_model or get_embedding_model()
        self._name = "bge-small-zh-v1.5"  # 使用私有属性存储名称
    
    def name(self) -> str:
        """返回embedding函数名称"""
        return self._name
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        ChromaDB调用接口
        
        Args:
            input: 文本列表
            
        Returns:
            向量列表
        """
        return self.embedding_model.embed_texts(input)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        LangChain兼容接口：批量嵌入文档
        
        Args:
            texts: 文档文本列表
            
        Returns:
            向量列表
        """
        return self.embedding_model.embed_texts(texts)
        
    def embed_query(self, text: str = None, input: str = None) -> List[float]:
        """
        LangChain兼容接口：嵌入查询文本
        
        Args:
            text: 查询文本
            input: 兼容某些调用方的参数名
            
        Returns:
            向量
        """
        real_text = text or input
        if not real_text:
            raise ValueError("Must provide either text or input")
        return self.embedding_model.embed_text(real_text)

