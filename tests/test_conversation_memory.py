"""
测试跨诊断任务的对话记忆功能
"""
import asyncio
import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.llm_agent import LLMAgent, NeedUserInputException
from src.integrations import LLMClient
from src.models.task import DiagnosticTask, FaultType, Protocol


async def test_conversation_memory():
    """测试对话记忆功能"""

    print("=" * 80)
    print("[TEST] 测试场景：跨诊断任务的对话记忆")
    print("=" * 80)

    # 初始化 LLM 客户端和 Agent
    llm_client = LLMClient()
    agent = LLMAgent(llm_client=llm_client, verbose=False)

    # 创建第一个诊断任务
    task1 = DiagnosticTask(
        task_id="test_task_001",
        user_input="10.0.1.10到10.0.2.20端口80不通",
        source="10.0.1.10",
        target="10.0.2.20",
        protocol=Protocol.TCP,
        fault_type=FaultType.PORT_UNREACHABLE,
        port=80
    )

    print("\n[第一次对话]")
    print("-" * 80)
    print(f"用户输入: {task1.user_input}")
    print()

    # 事件记录
    events = []

    async def event_callback(event):
        events.append(event)
        event_type = event.get('type')

        if event_type == 'start':
            print(f"[OK] 诊断开始 - 任务ID: {event['data']['task_id']}")
        elif event_type == 'tool_start':
            print(f"[TOOL] Step {event['step']}: {event['tool']}")
            print(f"       参数: {json.dumps(event['arguments'], ensure_ascii=False)}")
        elif event_type == 'tool_result':
            success = event['result'].get('success')
            status = "[OK]" if success else "[FAIL]"
            print(f"       {status} 结果: {event['result'].get('stdout', event['result'].get('error', ''))[:100]}")
        elif event_type == 'ask_user':
            print(f"[QUESTION] LLM 询问: {event['question']}")
        elif event_type == 'complete':
            print(f"\n[REPORT] 诊断完成")
            print(f"         根因: {event['report']['root_cause']}")
            print(f"         置信度: {event['report']['confidence']:.1f}%")

    # 执行第一次诊断
    try:
        await agent.diagnose(task1, event_callback=event_callback)
        print("\n[OK] 第一次诊断完成")
    except NeedUserInputException as e:
        print(f"\n[WARN] 需要用户输入: {e.question}")
        return
    except Exception as e:
        print(f"\n[ERROR] 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 保存第一次诊断的上下文
    context_after_first = agent.current_context.copy()

    print("\n" + "=" * 80)
    print("[第二次对话（测试记忆）]")
    print("-" * 80)

    # 模拟用户的第二次输入
    second_user_input = "把上面的10.0.2.20:80换成10.0.2.21:90再诊断下"
    print(f"用户输入: {second_user_input}")
    print()

    # 创建第二个诊断任务（LLM 应该从对话历史中提取信息）
    task2 = DiagnosticTask(
        task_id="test_task_001",  # 使用相同的任务ID（模拟会话保持）
        user_input=second_user_input,
        source="10.0.1.10",  # 这些信息 LLM 应该从上下文中获取
        target="10.0.2.21",
        protocol=Protocol.TCP,
        fault_type=FaultType.PORT_UNREACHABLE,
        port=90
    )

    print("[CHECK] 检查 LLM 提示词中是否包含对话历史...")

    # 构建决策提示词，查看是否包含历史
    prompt = agent._build_decision_prompt(context_after_first, task2)

    print("\n[PROMPT] LLM 收到的提示词（前 1000 字符）:")
    print("-" * 80)
    print(prompt[:1000])
    print("..." if len(prompt) > 1000 else "")
    print("-" * 80)

    # 检查提示词中是否包含第一次诊断的信息
    has_first_task_info = "10.0.2.20" in prompt and "80" in prompt
    has_history_section = "已执行的诊断步骤" in prompt or "对话历史" in prompt

    print("\n[VERIFY] 验证结果:")
    print(f"  提示词包含第一次任务信息: {'是' if has_first_task_info else '否'}")
    print(f"  提示词包含历史对话标记: {'是' if has_history_section else '否'}")

    if has_first_task_info and has_history_section:
        print("\n[SUCCESS] 记忆功能正常！LLM 可以看到完整的对话历史")
    else:
        print("\n[WARN] 记忆功能可能有问题，LLM 看不到完整历史")

    print("\n" + "=" * 80)
    print("[SUMMARY] 测试总结")
    print("=" * 80)
    print(f"第一次诊断步骤数: {len([c for c in context_after_first if c.get('tool')])}")
    print(f"对话上下文大小: {len(context_after_first)} 项")
    print(f"LLM 提示词长度: {len(prompt)} 字符")
    print("\n[OK] 测试完成！")


if __name__ == "__main__":
    asyncio.run(test_conversation_memory())
