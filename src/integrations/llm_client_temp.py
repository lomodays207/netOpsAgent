"""
LLM瀹㈡埛绔?
浣跨敤LangChain妗嗘灦锛屾敮鎸丱penAI鍗忚鍏煎鐨凙PI锛堝MiniMax銆丏eepSeek銆丵wen绛夛級
"""
import os
from typing import Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import Tool


class LLMClient:
    """
    LLM瀹㈡埛绔紝浣跨敤LangChain妗嗘灦

    鏀寔浠讳綍鍏煎OpenAI API鐨勬ā鍨嬶細
    - DeepSeek
    - Qwen/閫氫箟鍗冮棶
    - MiniMax
    - OpenAI GPT绯诲垪
    绛夌瓑
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        鍒濆鍖朙LM瀹㈡埛绔?
        Args:
            api_key: API瀵嗛挜锛岄粯璁や粠鐜鍙橀噺璇诲彇
            base_url: API鍩虹URL锛岄粯璁や粠鐜鍙橀噺璇诲彇
            model: 妯″瀷鍚嶇О锛岄粯璁や粠鐜鍙橀噺璇诲彇
            temperature: 榛樿娓╁害鍙傛暟锛?-1锛?            max_tokens: 榛樿鏈€澶oken鏁?        """
        self.api_key = api_key or os.getenv("API_KEY", "")
        self.base_url = base_url or os.getenv("API_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("MODEL", "gpt-3.5-turbo")
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens

        if not self.api_key:
            raise ValueError("LLM API瀵嗛挜鏈缃紝璇峰湪.env鏂囦欢涓厤缃瓵PI_KEY")

        # 鍒濆鍖?LangChain ChatOpenAI
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        璋冪敤LLM鐢熸垚鍝嶅簲

        Args:
            prompt: 鐢ㄦ埛鎻愮ず璇?            system_prompt: 绯荤粺鎻愮ず璇?            temperature: 娓╁害鍙傛暟锛圢one浣跨敤榛樿鍊硷級
            max_tokens: 鏈€澶oken鏁帮紙None浣跨敤榛樿鍊硷級

        Returns:
            LLM鍝嶅簲鏂囨湰
        """
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=prompt))

        # 浣跨敤涓存椂鍙傛暟鏇存柊
        llm = self.llm
        if temperature is not None or max_tokens is not None:
            llm = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens
            )

        try:
            response = llm.invoke(messages)
            return response.content if response else ""
        except Exception as e:
            raise RuntimeError(f"LLM璋冪敤澶辫触: {str(e)}")

    def invoke_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3
    ) -> str:
