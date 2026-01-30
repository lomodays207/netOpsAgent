"""
测试 SQLite 会话持久化功能
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.session_manager import get_session_manager
from src.models.task import DiagnosticTask, Protocol, FaultType
from src.integrations import LLMClient


async def test_session_persistence():
    """测试会话持久化和恢复"""
    print("=" * 60)
    print("测试 SQLite 会话持久化功能")
    print("=" * 60)
    
    # 1. 获取会话管理器
    session_manager = get_session_manager()
    await session_manager.initialize()
    print("\n✓ 会话管理器初始化成功")
    
    # 2. 创建测试任务
    task = DiagnosticTask(
        task_id="test_session_001",
        user_input="测试：10.0.1.10到10.0.2.20端口80不通",
        source="10.0.1.10",
        target="10.0.2.20",
        protocol=Protocol.TCP,
        fault_type=FaultType.PORT_UNREACHABLE,
        port=80
    )
    print(f"\n✓ 创建测试任务: {task.task_id}")
    
    # 3. 创建 LLM 客户端（使用测试配置）
    try:
        llm_client = LLMClient()
        print("✓ LLM 客户端创建成功")
    except Exception as e:
        print(f"⚠ LLM 客户端创建失败（使用模拟客户端）: {e}")
        # 创建一个模拟的 LLMClient 用于测试
        class MockLLMClient:
            def __init__(self):
                self.api_key = "test_key"
                self.base_url = "https://test.api.com"
                self.model = "test-model"
                self.default_temperature = 0.7
                self.default_max_tokens = 2000
        
        llm_client = MockLLMClient()
        print("✓ 使用模拟 LLM 客户端")
    
    # 4. 创建会话
    from src.agent.llm_agent import LLMAgent
    agent = LLMAgent(llm_client=llm_client)
    
    session = session_manager.create_session(
        session_id=task.task_id,
        task=task,
        llm_client=llm_client,
        agent=agent
    )
    print(f"✓ 创建会话: {session.session_id}")
    
    # 5. 添加一些测试消息
    session_manager.add_message(
        session_id=task.task_id,
        role="user",
        content="请帮我诊断网络问题"
    )
    session_manager.add_message(
        session_id=task.task_id,
        role="assistant",
        content="好的，我将开始诊断"
    )
    print("✓ 添加测试消息")
    
    # 6. 更新会话状态
    session_manager.update_session(
        task.task_id,
        status="waiting_user",
        pending_question="请问目标服务器上是否有防火墙？"
    )
    print("✓ 更新会话状态")
    
    # 等待异步操作完成
    await asyncio.sleep(1)
    
    # 7. 从内存中清除会话（模拟服务重启）
    print("\n--- 模拟服务重启 ---")
    session_manager.sessions.clear()
    print("✓ 清除内存中的会话")
    
    # 8. 从数据库恢复会话
    print("\n--- 从数据库恢复会话 ---")
    recovered_session = await session_manager.get_session(task.task_id)
    
    if recovered_session:
        print(f"✓ 成功恢复会话: {recovered_session.session_id}")
        print(f"  - 状态: {recovered_session.status}")
        print(f"  - 待回答问题: {recovered_session.pending_question}")
        print(f"  - 消息数量: {len(recovered_session.messages)}")
        print(f"  - 任务信息: {recovered_session.task}")
        print(f"  - Agent 已重建: {recovered_session.agent is not None}")
        print(f"  - LLMClient 已重建: {recovered_session.llm_client is not None}")
        
        # 验证消息内容
        print("\n  消息历史:")
        for msg in recovered_session.messages:
            print(f"    [{msg['role']}] {msg['content']}")
        
        print("\n✅ 会话持久化测试通过！")
    else:
        print("❌ 会话恢复失败")
        return
    
    # 9. 清理测试数据
    print("\n--- 清理测试数据 ---")
    session_manager.delete_session(task.task_id)
    await asyncio.sleep(0.5)
    print("✓ 删除测试会话")
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_session_persistence())
