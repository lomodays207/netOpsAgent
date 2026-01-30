"""
CLI命令行入口

使用Typer框架提供命令行接口
"""
import asyncio
import os
import uuid
from datetime import datetime
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from .agent import DiagnosticAnalyzer, Executor, NLU, ReportGenerator, TaskPlanner
from .integrations import AutomationPlatformClient, CMDBClient, LLMClient
from .models.task import DiagnosticTask, FaultType, Protocol

# 加载环境变量
load_dotenv()

app = typer.Typer(
    name="netops",
    help="智能网络故障排查Agent",
    add_completion=False
)
console = Console()


def generate_task_id() -> str:
    """生成任务ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"task_{timestamp}_{short_uuid}"


@app.command("diagnose")
def diagnose(
    user_input: str = typer.Argument(..., help="故障描述，例如: 'server1到server2端口80不通'"),
    mode: str = typer.Option("fast", "--mode", "-m", help="执行模式: fast | deep"),
    output_dir: str = typer.Option("runtime/reports", "--output", "-o", help="报告输出目录"),
    use_llm: bool = typer.Option(False, "--use-llm", help="是否启用LLM辅助分析（需要配置.env）"),
    agent_mode: bool = typer.Option(False, "--agent-mode", help="启用LLM Agent动态诊断模式（需要配置.env）"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细的工具调用输出")
):
    """
    执行网络故障诊断

    示例:
        # 使用规则引擎（默认）
        netops diagnose "server1到server2端口80不通" --scenario scenario1_refused

        # 启用LLM增强（自动NLU + AI辅助分析）
        netops diagnose "服务器A访问服务器B的HTTP服务失败" --use-llm
    """
    console.print(f"\n[bold cyan]netOpsAgent - 智能网络故障排查[/bold cyan]")
    console.print(f"[dim]{'='*60}[/dim]\n")

    # Agent模式自动启用LLM
    if agent_mode:
        use_llm = True
        console.print("[yellow]已启用LLM Agent动态诊断模式[/yellow]")
    elif use_llm:
        console.print("[yellow]已启用LLM增强模式[/yellow]")

    # 解析用户输入
    if use_llm or agent_mode:
        # 使用LLM进行NLU
        try:
            llm_client = LLMClient()
            nlu = NLU(llm_client)
            task_id = generate_task_id()
            console.print("[cyan]使用LLM解析用户输入...[/cyan]")
            task = nlu.parse_user_input(user_input, task_id)
            console.print("[green]OK[/green] LLM解析完成")
        except Exception as e:
            console.print(f"[yellow]LLM解析失败，回退到规则解析: {str(e)}[/yellow]")
            task = parse_user_input(user_input)
    else:
        # 使用规则解析
        task = parse_user_input(user_input)

    console.print(f"[green]OK[/green] 任务已创建: [bold]{task.task_id}[/bold]")
    console.print(f"  故障类型: [yellow]{task.fault_type.value}[/yellow]")
    console.print(f"  源主机: {task.source}")
    console.print(f"  目标主机: {task.target}")
    if task.port:
        console.print(f"  端口: {task.port}")
    console.print()

    # 执行诊断
    asyncio.run(run_diagnosis(task, mode, output_dir, use_llm, agent_mode, verbose))


async def run_diagnosis(
    task: DiagnosticTask,
    mode: str,
    output_dir: str,
    use_llm: bool = False,
    agent_mode: bool = False,
    verbose: bool = False
):
    """
    执行诊断流程

    Args:
        task: 诊断任务
        mode: 执行模式
        output_dir: 输出目录
        use_llm: 是否启用LLM
        agent_mode: 是否启用LLM Agent模式
        verbose: 是否显示详细输出
    """
    # 初始化客户端
    automation_client = AutomationPlatformClient()
    cmdb_client = CMDBClient()

    # 初始化LLM客户端（如果需要）
    llm_client = None
    if use_llm:
        try:
            llm_client = LLMClient()
            console.print("[green]OK[/green] LLM客户端初始化成功")
        except Exception as e:
            console.print(f"[yellow]LLM初始化失败，将使用规则引擎: {str(e)}[/yellow]")
            use_llm = False
            agent_mode = False  # LLM失败时也禁用agent模式

    # 分支：Agent模式 vs 规则模式
    if agent_mode:
        # ========== LLM Agent模式 ==========
        console.print("\n[bold cyan]使用LLM Agent动态诊断模式[/bold cyan]\n")

        # 导入LLM Agent
        from .agent.llm_agent import LLMAgent

        # 初始化LLM Agent
        agent = LLMAgent(llm_client=llm_client, verbose=verbose)

        # 执行诊断
        report = await agent.diagnose(task)

        # 生成报告
        reporter = ReportGenerator(output_dir)
        report_path = reporter.generate(report)

        # 显示摘要
        console.print(reporter.generate_summary(report))
        console.print(f"\n[green]OK[/green] 详细报告已保存: [bold]{report_path}[/bold]\n")

    else:
        # ========== 规则模式（原有流程）==========
        planner = TaskPlanner()
        executor = Executor(automation_client, cmdb_client)
        analyzer = DiagnosticAnalyzer(llm_client=llm_client, use_llm=use_llm)
        reporter = ReportGenerator(output_dir)

        executed_steps = []

        # Step 1: 生成执行计划
        console.print("[cyan]生成执行计划...[/cyan]")
        plan = planner.plan(task, mode)
        console.print(f"[green]OK[/green] 生成了 {len(plan)} 步执行计划\n")

        # Step 2: 执行排查步骤
        current_plan = plan
        while current_plan:
            for step in current_plan:
                step_num = step.get("step", 0)
                step_name = step.get("name", "Unknown")

                console.print(f"[cyan]Step {step_num}: {step_name}...[/cyan]")

                # 执行步骤
                step_result = await executor.execute_step(step)
                executed_steps.append(step_result)

                # 显示结果
                status_icon = "OK" if step_result.success else "FAIL"
                status_color = "green" if step_result.success else "red"
                console.print(f"[{status_color}]{status_icon}[/{status_color}] Step {step_num}: {step_name}")

                # 显示关键信息
                if step_result.metadata:
                    _print_step_metadata(step_result.metadata)

            # 获取下一步计划
            if current_plan:
                last_step = current_plan[-1]
                current_plan = planner.get_next_step(
                    last_step.get("step", 0),
                    executed_steps[-1].__dict__,
                    task
                )
            else:
                break

        console.print(f"\n[cyan]分析结果...[/cyan]")

        # Step 3: 分析结果
        if use_llm:
            console.print(f"[bold]使用LLM辅助分析诊断结果...[/bold]")
        else:
            console.print(f"[bold]分析诊断结果...[/bold]")
        report = analyzer.analyze(task, executed_steps)

        # Step 4: 生成报告
        console.print(f"[bold]生成诊断报告...[/bold]")
        report_path = reporter.generate(report)

        # 显示摘要
        console.print(reporter.generate_summary(report))
        console.print(f"\n[green]OK[/green] 详细报告已保存: [bold]{report_path}[/bold]\n")


def _print_step_metadata(metadata: dict):
    """打印步骤元数据的关键信息"""
    if "error_type" in metadata:
        console.print(f"  → 错误类型: [yellow]{metadata['error_type']}[/yellow]")
    if "is_listening" in metadata:
        listening = "是" if metadata["is_listening"] else "否"
        console.print(f"  → 端口监听: {listening}")
        if metadata.get("process_name"):
            console.print(f"  → 进程: {metadata['process_name']} (PID: {metadata.get('pid')})")
    if "is_reachable" in metadata:
        reachable = "可达" if metadata["is_reachable"] else "不可达"
        console.print(f"  → 连通性: {reachable}")
        if metadata.get("packet_loss") is not None:
            console.print(f"  → 丢包率: {metadata['packet_loss']}%")
    if "has_blocking_rule" in metadata:
        blocked = "是" if metadata["has_blocking_rule"] else "否"
        console.print(f"  → 防火墙阻断: {blocked}")
        if metadata.get("rule_action"):
            console.print(f"  → 规则动作: {metadata['rule_action']}")


def parse_user_input(user_input: str) -> DiagnosticTask:
    """
    解析用户输入（Phase 1简化版：基于规则的解析）

    Args:
        user_input: 用户输入字符串

    Returns:
        DiagnosticTask对象

    示例:
        "server1到server2端口80不通" → port_unreachable
        "server1到server2 ping不通" → connectivity
    """
    task_id = generate_task_id()

    # 简单的规则解析
    if "端口" in user_input or "telnet" in user_input.lower():
        fault_type = FaultType.PORT_UNREACHABLE
        protocol = Protocol.TCP
    elif "ping" in user_input.lower() or "连通" in user_input:
        fault_type = FaultType.CONNECTIVITY
        protocol = Protocol.ICMP
    else:
        fault_type = FaultType.PORT_UNREACHABLE
        protocol = Protocol.TCP

    # 提取主机名（简化版：假设格式为"源主机到目标主机"）
    parts = user_input.replace("到", " ").replace("端口", " ").replace("不通", "").strip().split()

    source = parts[0] if len(parts) > 0 else "unknown_source"
    target = parts[1] if len(parts) > 1 else "unknown_target"

    # 提取端口号
    port = None
    for part in parts:
        if part.isdigit():
            port = int(part)
            break

    return DiagnosticTask(
        task_id=task_id,
        user_input=user_input,
        source=source,
        target=target,
        protocol=protocol,
        fault_type=fault_type,
        port=port
    )


@app.command("version")
def version():
    """显示版本信息"""
    console.print("[bold cyan]netOpsAgent[/bold cyan] v1.0.0")
    console.print("智能网络故障排查Agent - Phase 1")


@app.command("test")
def test(
    output_dir: str = typer.Option("runtime/reports", "--output", "-o", help="报告输出目录"),
    use_llm: bool = typer.Option(False, "--use-llm", help="是否启用LLM辅助分析")
):
    """
    运行测试场景（自动选择场景）

    示例:
        # 使用规则引擎
        netops test

        # 使用LLM增强
        netops test --use-llm
    """
    # 使用默认的测试输入
    user_input = "10.0.1.10到10.0.2.20端口80不通"

    console.print(f"[bold]运行测试: {user_input}[/bold]\n")
    diagnose(user_input=user_input, mode="fast", output_dir=output_dir, use_llm=use_llm)


def main():
    """主入口函数"""
    app()


if __name__ == "__main__":
    main()
