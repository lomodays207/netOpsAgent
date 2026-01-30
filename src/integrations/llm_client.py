"""
LLM客户端

使用LangChain框架，支持OpenAI协议兼容的API（如MiniMax、DeepSeek、Qwen等）
"""
import os
import time
from typing import Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import Tool


# 自定义异常类
class LLMAPIError(Exception):
    """LLM API 调用错误基类"""
    pass


class LLMTimeoutError(LLMAPIError):
    """LLM API 超时错误"""
    pass


class LLMRateLimitError(LLMAPIError):
    """LLM API 限流错误"""
    pass


class LLMAuthenticationError(LLMAPIError):
    """LLM API 认证错误"""
    pass


class LLMClient:
    """
    LLM客户端，使用LangChain框架

    支持任何兼容OpenAI API的模型：
    - DeepSeek
    - Qwen/通义千问
    - MiniMax
    - OpenAI GPT系列
    等等
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        """
        初始化LLM客户端

        Args:
            api_key: API密钥，默认从环境变量读取
            base_url: API基础URL，默认从环境变量读取
            model: 模型名称，默认从环境变量读取
            temperature: 默认温度参数（0-1）
            max_tokens: 默认最大token数
            timeout: 请求超时时间（秒），默认从环境变量读取
            max_retries: 最大重试次数，默认从环境变量读取
        """
        self.api_key = api_key or os.getenv("API_KEY", "")
        self.base_url = base_url or os.getenv("API_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("MODEL", "gpt-3.5-turbo")
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens

        # 超时和重试配置
        self.timeout = timeout if timeout is not None else int(os.getenv("LLM_REQUEST_TIMEOUT", "60"))
        self.max_retries = max_retries if max_retries is not None else int(os.getenv("LLM_MAX_RETRIES", "3"))

        if not self.api_key:
            raise ValueError("LLM API密钥未设置，请在.env文件中配置API_KEY")

        # 初始化 LangChain ChatOpenAI
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.timeout,
            max_retries=0  # 我们自己实现重试逻辑
        )

    def _classify_error(self, error: Exception) -> Exception:
        """
        分类错误类型

        Args:
            error: 原始异常

        Returns:
            分类后的异常
        """
        error_str = str(error).lower()

        if "timeout" in error_str or "timed out" in error_str:
            return LLMTimeoutError(f"LLM API 请求超时: {error}")
        elif "rate limit" in error_str or "429" in error_str:
            return LLMRateLimitError(f"LLM API 限流: {error}")
        elif "authentication" in error_str or "401" in error_str or "403" in error_str:
            return LLMAuthenticationError(f"LLM API 认证失败: {error}")
        else:
            return LLMAPIError(f"LLM API 调用失败: {error}")

    def _retry_with_backoff(self, func, *args, **kwargs):
        """
        带指数退避的重试逻辑

        Args:
            func: 要执行的函数
            *args, **kwargs: 函数参数

        Returns:
            函数执行结果

        Raises:
            LLMAPIError: 重试失败后抛出分类后的异常
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = self._classify_error(e)

                # 认证错误不重试
                if isinstance(last_error, LLMAuthenticationError):
                    raise last_error

                # 最后一次尝试，直接抛出
                if attempt == self.max_retries:
                    print(f"[LLM Client] 重试{attempt}次后仍然失败: {last_error}")
                    raise last_error

                # 计算退避时间（指数退避）
                backoff_time = min(2 ** attempt, 10)  # 最多等待10秒

                # 限流错误额外增加等待时间
                if isinstance(last_error, LLMRateLimitError):
                    backoff_time *= 2

                print(f"[LLM Client] 尝试{attempt + 1}失败，{backoff_time}秒后重试: {last_error}")
                time.sleep(backoff_time)

        # 理论上不会到这里，但为了安全
        raise last_error if last_error else LLMAPIError("未知错误")

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        调用LLM生成响应

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数（None使用默认值）
            max_tokens: 最大token数（None使用默认值）

        Returns:
            LLM响应文本

        Raises:
            LLMAPIError: LLM调用失败
        """
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=prompt))

        # 使用临时参数更新
        llm = self.llm
        if temperature is not None or max_tokens is not None:
            llm = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
                timeout=self.timeout,
                max_retries=0
            )

        def _invoke_llm():
            response = llm.invoke(messages)
            return response.content if response else ""

        return self._retry_with_backoff(_invoke_llm)

    def chat(
        self,
        messages: List[Dict],
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        调用LLM进行多轮对话

        Args:
            messages: 消息列表，每个元素为 {"role": "user/assistant/system", "content": "..."}
            system_prompt: 可选的系统提示词（如果有，会作为第一条 SystemMessage）
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            LLM响应文本

        Raises:
            LLMAPIError: LLM调用失败
        """
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        langchain_messages = []

        # 添加系统提示词
        if system_prompt:
            langchain_messages.append(SystemMessage(content=system_prompt))

        # 转换历史消息
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            elif role == "system":
                # 如果历史记录中有 system 消息，也添加进去（通常 system_prompt 参数优先）
                langchain_messages.append(SystemMessage(content=content))

        # 使用临时参数更新
        llm = self.llm
        if temperature is not None or max_tokens is not None:
            llm = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
                timeout=self.timeout,
                max_retries=0
            )

        def _chat_llm():
            response = llm.invoke(langchain_messages)
            return response.content if response else ""

        return self._retry_with_backoff(_chat_llm)

    def invoke_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3
    ) -> str:
        """
        调用LLM生成JSON格式响应

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数（较低以获得更确定的JSON）

        Returns:
            JSON格式的响应文本
        """
        # 确保提示词要求JSON格式
        if "JSON" not in prompt and "json" not in prompt:
            prompt += "\n\n请以JSON格式输出结果。"

        return self.invoke(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )

    def batch_invoke(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None
    ) -> List[str]:
        """
        批量调用LLM

        Args:
            prompts: 提示词列表
            system_prompt: 系统提示词

        Returns:
            响应列表
        """
        results = []
        for prompt in prompts:
            try:
                result = self.invoke(prompt, system_prompt)
                results.append(result)
            except Exception as e:
                results.append(f"Error: {str(e)}")

        return results

    def invoke_with_tools(
        self,
        prompt: str,
        tools: List[Tool],
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> Dict:
        """
        调用LLM并支持工具调用（使用LangChain bind_tools）

        Args:
            prompt: 用户提示词
            tools: LangChain Tool对象列表
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            Dict: 包含响应和可能的工具调用
                {
                    "content": str,           # LLM响应文本
                    "tool_calls": List[Dict]  # 工具调用列表（如果有）
                }

        Raises:
            LLMAPIError: LLM调用失败
        """
        import json

        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=prompt))

        # 如果需要自定义参数，创建新的LLM实例
        llm = self.llm
        if temperature is not None or max_tokens is not None:
            llm = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
                timeout=self.timeout,
                max_retries=0
            )

        # 绑定工具并调用
        llm_with_tools = llm.bind_tools(tools)

        def _invoke_with_tools():
            response = llm_with_tools.invoke(messages)

            result = {
                "content": response.content or "",
                "tool_calls": []
            }

            # 检查是否有工具调用（LangChain 格式）
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tc in response.tool_calls:
                    result["tool_calls"].append({
                        "id": tc.get("id", ""),
                        "name": tc.get("name"),
                        "arguments": tc.get("args", {})
                    })

            return result

        return self._retry_with_backoff(_invoke_with_tools)
