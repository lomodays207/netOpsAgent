"""
端到端测试：通过聊天查询 IP 地址的访问关系
"""
import asyncio
from src.agent.general_chat_agent import GeneralChatToolAgent
from src.integrations import LLMClient
from src.session_manager import get_session_manager


async def test_ip_chat_query():
    """测试通过聊天查询 IP 地址的访问关系"""
    
    # 初始化
    session_manager = get_session_manager()
    await session_manager.initialize()
    
    llm_client = LLMClient()
    
    # 创建 GeneralChatToolAgent
    agent = GeneralChatToolAgent(
        llm_client=llm_client,
        session_manager=session_manager,
        session_id="test_session",
        event_callback=None
    )
    
    # 测试查询
    test_queries = [
        "IP 为 10.40.1.10 的主机有哪些访问关系",
        "10.38.1.100 有哪些访问关系",
        "查询 10.20.5.50 的访问关系"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"用户查询: {query}")
        print(f"{'='*60}")
        
        try:
            response = await agent.run(
                user_message=query,
                system_prompt="你是一个网络运维助手，帮助用户查询系统间的访问关系。",
                chat_history=[]
            )
            
            print(f"\n助手回复:")
            print(response)
            
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_ip_chat_query())
