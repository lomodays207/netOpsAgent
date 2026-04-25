"""
简化的 LLM Agent 测试 - 验证核心功能

快速验证：
1. NLU解析
2. LLM Agent创建
3. 工具调用（使用Mock数据）
4. 报告生成
"""
import asyncio
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv

load_dotenv()

from src.agent.nlu import NLU
from src.agent.llm_agent import LLMAgent, NeedUserInputException
from src.integrations.llm_client import LLMClient
from src.integrations.automation_platform_client import AutomationPlatformClient
from src.models.report import DiagnosticReport
from src.models.task import DiagnosticTask, FaultType, Protocol

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

class RecordingTraceRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def start_trace(self, **kwargs):
        self.calls.append(("start_trace", kwargs))
        return "trace_test_1"

    def add_reasoning_step(self, **kwargs):
        self.calls.append(("add_reasoning_step", kwargs))

    def start_tool_call(self, **kwargs):
        self.calls.append(("start_tool_call", kwargs))
        return "tool_test_1"

    def complete_tool_call(self, **kwargs):
        self.calls.append(("complete_tool_call", kwargs))

    def complete_trace(self, **kwargs):
        self.calls.append(("complete_trace", kwargs))

    def fail_trace(self, **kwargs):
        self.calls.append(("fail_trace", kwargs))

    def interrupt_trace(self, **kwargs):
        self.calls.append(("interrupt_trace", kwargs))


def _build_task() -> DiagnosticTask:
    return DiagnosticTask(
        task_id="task-1",
        user_input="10.0.1.10 to 10.0.2.20 port 80 unreachable",
        source="10.0.1.10",
        target="10.0.2.20",
        protocol=Protocol.TCP,
        fault_type=FaultType.PORT_UNREACHABLE,
        port=80,
    )


@pytest.mark.asyncio
async def test_llm_agent_records_trace_for_completed_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = RecordingTraceRecorder()
    agent = LLMAgent(llm_client=object(), verbose=False, max_steps=3, trace_recorder=recorder)

    decisions = [
        {
            "reasoning": "check the target port first",
            "tool_calls": [
                {
                    "id": "call-1",
                    "name": "check_port_alive",
                    "arguments": {"host": "10.0.2.20", "port": 80},
                }
            ],
            "conclude": False,
        },
        {
            "reasoning": "the port is not listening on the target host",
            "tool_calls": [],
            "conclude": True,
        },
    ]

    async def fake_decide(context, task):
        return decisions.pop(0)

    async def fake_execute(tool_call, task):
        return {"success": True, "stdout": "closed", "execution_time": 1.25}

    monkeypatch.setattr(agent, "_llm_decide_next_step", fake_decide)
    monkeypatch.setattr(agent, "_execute_tool", fake_execute)

    report = await agent.diagnose(_build_task())

    assert report.root_cause == "the port is not listening on the target host"
    assert [name for name, _ in recorder.calls] == [
        "start_trace",
        "add_reasoning_step",
        "start_tool_call",
        "complete_tool_call",
        "add_reasoning_step",
        "complete_trace",
    ]
    assert recorder.calls[0][1]["request_type"] == "diagnosis"
    assert recorder.calls[-1][1]["final_answer"] == "the port is not listening on the target host"


@pytest.mark.asyncio
async def test_llm_agent_reuses_trace_after_need_user_input(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = RecordingTraceRecorder()
    agent = LLMAgent(llm_client=object(), verbose=False, max_steps=4, trace_recorder=recorder)
    task = _build_task()

    first_decisions = [
        {
            "reasoning": "need user confirmation before next step",
            "tool_calls": [
                {
                    "id": "call-ask",
                    "name": "ask_user",
                    "arguments": {"question": "is there a firewall?"},
                }
            ],
            "conclude": False,
        }
    ]
    second_decisions = [
        {
            "reasoning": "the firewall denies the connection",
            "tool_calls": [],
            "conclude": True,
        }
    ]

    async def fake_decide_first(context, task):
        return first_decisions.pop(0)

    async def fake_execute_ask(tool_call, task):
        raise NeedUserInputException("is there a firewall?", agent.current_context)

    monkeypatch.setattr(agent, "_llm_decide_next_step", fake_decide_first)
    monkeypatch.setattr(agent, "_execute_tool", fake_execute_ask)

    with pytest.raises(NeedUserInputException):
        await agent.diagnose(task)

    async def fake_decide_second(context, task):
        return second_decisions.pop(0)

    monkeypatch.setattr(agent, "_llm_decide_next_step", fake_decide_second)

    report = await agent.continue_diagnose(task, agent.current_context, "yes", stop_event=None)

    assert report.root_cause == "the firewall denies the connection"
    assert [name for name, _ in recorder.calls].count("start_trace") == 1
    assert [name for name, _ in recorder.calls].count("complete_trace") == 1
    assert all(name != "fail_trace" for name, _ in recorder.calls)


@pytest.mark.asyncio
async def test_llm_agent_interrupts_trace_when_stop_event_is_set() -> None:
    recorder = RecordingTraceRecorder()
    agent = LLMAgent(llm_client=object(), verbose=False, max_steps=2, trace_recorder=recorder)
    stop_event = asyncio.Event()
    stop_event.set()

    report = await agent.diagnose(_build_task(), stop_event=stop_event)

    assert isinstance(report, DiagnosticReport)
    assert [name for name, _ in recorder.calls] == ["start_trace", "interrupt_trace"]


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        exit(0 if result else 1)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
