"""
简化的 LLM Agent 测试 - 验证核心功能

快速验证：
1. NLU解析
2. LLM Agent创建
3. 工具调用（使用Mock数据）
4. 报告生成
"""
import asyncio
from dotenv import load_dotenv

load_dotenv()

from src.agent.nlu import NLU
from src.agent.llm_agent import LLMAgent
from src.integrations.llm_client import LLMClient
from src.integrations.automation_platform_client import AutomationPlatformClient

print("=" * 70)
print("简化LLM Agent测试")
print("=" * 70)

async def main():
    # 用户输入
    user_input = "10.0.1.10访问10.0.2.20的80端口refused"
    print(f"\n用户输入: {user_input}")

    # Step 1: NLU解析
    print("\nStep 1: NLU解析...")
    llm_client = LLMClient()
    nlu = NLU(llm_client=llm_client)
    task = nlu.parse_user_input(user_input, "test_001")
    print(f"  OK - 解析结果: {task.source} -> {task.target}:{task.port}")

    # Step 2: 创建LLM Agent（禁用网络路由，使用Mock）
    print("\nStep 2: 创建LLM Agent...")
    llm_agent = LLMAgent(llm_client=llm_client, verbose=False)

    # 设置Mock场景
    automation_client = llm_agent.network_tools.default_client
    automation_client.set_scenario("scenario1_refused")
    print("  OK - Agent创建完成，Mock场景已设置")

    # Step 3: 执行诊断
    print("\nStep 3: 执行诊断...")
    print("  (LLM正在动态决策并调用工具，请稍候...)\n")

    report = await llm_agent.diagnose(task)

    # Step 4: 显示结果
    print("\n" + "=" * 70)
    print("诊断报告")
    print("=" * 70)
    print(f"任务ID: {report.task_id}")
    print(f"根因: {report.root_cause[:200]}...")
    print(f"置信度: {report.confidence * 100:.1f}%")
    print(f"执行步骤: {len(report.executed_steps)}步")
    print(f"总耗时: {report.total_time:.2f}秒")
    print(f"需要人工: {'是' if report.need_human else '否'}")

    if report.executed_steps:
        print(f"\n执行的步骤:")
        for step in report.executed_steps:
            status = "成功" if step.success else "失败"
            print(f"  - Step {step.step_number}: {step.step_name} [{status}]")

    if report.fix_suggestions:
        print(f"\n建议措施:")
        for idx, suggestion in enumerate(report.fix_suggestions, 1):
            print(f"  {idx}. {suggestion}")

    print("\n" + "=" * 70)

    # 验证
    root_cause_lower = report.root_cause.lower()
    expected_keywords = ["refused", "未监听", "服务"]

    if any(kw in root_cause_lower for kw in expected_keywords):
        print("OK - 测试通过！根因分析正确")
        return True
    else:
        print("FAIL - 根因分析不符合预期")
        print(f"  期望关键词: {expected_keywords}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        exit(0 if result else 1)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
