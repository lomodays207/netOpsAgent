"""
对象序列化/反序列化工具

用于将复杂对象序列化为JSON字符串，以便存储到SQLite数据库中
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..models.task import DiagnosticTask, Protocol, FaultType
from ..integrations import LLMClient


def serialize_task(task: DiagnosticTask) -> str:
    """
    将 DiagnosticTask 序列化为 JSON 字符串
    
    Args:
        task: 诊断任务对象
        
    Returns:
        JSON 字符串
    """
    return json.dumps(task.to_dict(), ensure_ascii=False)


def deserialize_task(data: str) -> DiagnosticTask:
    """
    从 JSON 字符串反序列化 DiagnosticTask
    
    Args:
        data: JSON 字符串
        
    Returns:
        DiagnosticTask 对象
    """
    task_dict = json.loads(data)
    
    # 转换枚举类型
    protocol = Protocol(task_dict['protocol'])
    fault_type = FaultType(task_dict['fault_type'])
    
    # 转换 datetime
    created_at = datetime.fromisoformat(task_dict['created_at'])
    
    return DiagnosticTask(
        task_id=task_dict['task_id'],
        user_input=task_dict['user_input'],
        source=task_dict['source'],
        target=task_dict['target'],
        protocol=protocol,
        fault_type=fault_type,
        created_at=created_at,
        port=task_dict.get('port'),
        context=task_dict.get('context', {})
    )


def serialize_context(context: List[Dict]) -> str:
    """
    序列化上下文列表
    
    Args:
        context: 上下文列表
        
    Returns:
        JSON 字符串
    """
    # 处理可能包含的特殊对象
    def default_handler(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)
    
    return json.dumps(context, ensure_ascii=False, default=default_handler)


def deserialize_context(data: str) -> List[Dict]:
    """
    反序列化上下文列表
    
    Args:
        data: JSON 字符串
        
    Returns:
        上下文列表
    """
    if not data:
        return []
    return json.loads(data)


def extract_llm_config(llm_client: LLMClient) -> str:
    """
    提取 LLMClient 的配置信息
    
    Args:
        llm_client: LLM 客户端对象
        
    Returns:
        JSON 字符串，包含重建所需的配置
    """
    config = {
        'api_key': llm_client.api_key,
        'base_url': llm_client.base_url,
        'model': llm_client.model,
        'temperature': getattr(llm_client, 'temperature', 0.7),
        'max_tokens': getattr(llm_client, 'max_tokens', None)
    }
    return json.dumps(config, ensure_ascii=False)


def rebuild_llm_client(config: str) -> LLMClient:
    """
    从配置重建 LLMClient 对象
    
    Args:
        config: JSON 字符串配置
        
    Returns:
        LLMClient 对象
    """
    config_dict = json.loads(config)
    
    # 使用配置创建新的 LLMClient
    # 注意：这里假设 LLMClient 可以通过这些参数初始化
    # 如果 LLMClient 的构造函数不同，需要相应调整
    return LLMClient(
        api_key=config_dict.get('api_key'),
        base_url=config_dict.get('base_url'),
        model=config_dict.get('model')
    )


def serialize_messages(messages: List[Dict]) -> str:
    """
    序列化消息列表
    
    Args:
        messages: 消息列表
        
    Returns:
        JSON 字符串
    """
    def default_handler(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)
    
    return json.dumps(messages, ensure_ascii=False, default=default_handler)


def deserialize_messages(data: str) -> List[Dict]:
    """
    反序列化消息列表
    
    Args:
        data: JSON 字符串
        
    Returns:
        消息列表
    """
    if not data:
        return []
    return json.loads(data)
