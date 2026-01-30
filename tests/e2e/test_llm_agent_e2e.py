"""
LLM Agent 完整诊断流程端到端测试

测试完整流程：
1. 用户输入 → NLU解析
2. 创建DiagnosticTask
3. LLM Agent 动态决策
4. 调用 network_tools 执行命令
5. 生成诊断报告
"""
import asyncio
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 加载环境变量
load_dotenv()

from src.agent.nlu import NLU
from src.agent.llm_agent import LLMAgent
from src.integrations.llm_client import LLMClient
from src.integrations.automation_platform_client import AutomationPlatformClient

console = Console()


async def test_complete_diagnosis_flow():
    """测试完整的诊断流程"""
    console.print("\n[bold cyan]" + "=" * 70)
    console.print("[bold cyan]LLM Agent 完整诊断流程测试")
    console.print("[bold cyan]" + "=" * 70 + "\n")

    # 测试场景
    test_scenarios = [
        {
            "name": "场景1: 端口拒绝连接（refused）",
            "user_input": "10.0.1.10访问10.0.2.20的80端口失败",
            "scenario": "scenario1_refused",
            "expected_root_cause": ["refused", "未监听", "服务未启动"]
        },
        {
            "name": "场景2: 防火墙阻止",
            "user_input": "web-01到db-01的MySQL连接总是超时",
            "scenario": "scenario2_firewall_blocked",
            "expected_root_cause": ["防火墙", "iptables", "DROP"]
        },
        {
            "name": "场景3: 网络不通",
            "user_input": "server1到server2 ping不通",
            "scenario": "scenario3_network_broken",
            "expected_root_cause": ["网络", "不通", "unreachable", "timeout"]
        }
    ]

    # 初始化LLM客户端
    console.print("[yellow]初始化组件...[/yellow]")
    llm_client = LLMClient()
    nlu = NLU(llm_client=llm_client)

    # 创建LLM Agent（不使用router，使用mock客户端）
    llm_agent = LLMAgent(llm_client=llm_client, verbose=True)

    # 获取默认的automation_client来设置场景
    automation_client = llm_agent.network_tools.default_client

    console.print("[green]OK[/green] 组件初始化完成\n")

    # 执行测试
    results = []

    for i, scenario in enumerate(test_scenarios, 1):
        console.print(f"\n[bold yellow]{'=' * 70}[/bold yellow]")
        console.print(f"[bold yellow]测试 {i}/{len(test_scenarios)}: {scenario['name']}[/bold yellow]")
        console.print(f"[bold yellow]{'=' * 70}[/bold yellow]\n")

        console.print(Panel(
            scenario['user_input'],
            title="[cyan]用户输入[/cyan]",
            border_style="cyan"
        ))

        try:
            # Step 1: NLU解析
            console.print("\n[yellow]Step 1: NLU解析用户输入...[/yellow]")
            task = nlu.parse_user_input(
                user_input=scenario['user_input'],
                task_id=f"test_{i:03d}"
            )

            console.print(f"[green]OK[/green] 解析完成")
            console.print(f"  - 任务ID: {task.task_id}")
            console.print(f"  - 源主机: {task.source}")
            console.print(f"  - 目标主机: {task.target}")
            console.print(f"  - 协议: {task.protocol.value}")
            console.print(f"  - 端口: {task.port}")
            console.print(f"  - 故障类型: {task.fault_type.value}")

            # Step 2: 设置Mock场景
            console.print(f"\n[yellow]Step 2: 设置Mock场景...[/yellow]")
            automation_client.set_scenario(scenario['scenario'])
            console.print(f"[green]OK[/green] 场景设置为: {scenario['scenario']}")

            # Step 3: LLM Agent 执行诊断
            console.print(f"\n[yellow]Step 3: LLM Agent 执行诊断...[/yellow]")
            console.print("[dim]（LLM将动态决策并调用网络工具）[/dim]\n")

            report = await llm_agent.diagnose(task)

            # Step 4: 显示诊断结果
            console.print(f"\n[yellow]Step 4: 诊断完成，分析结果...[/yellow]\n")

            # 创建结果表格
            result_table = Table(title="诊断报告", show_header=True, header_style="bold magenta")
            result_table.add_column("项目", style="cyan", width=20)
            result_table.add_column("内容", style="white", width=50)

            result_table.add_row("任务ID", report.task_id)
            result_table.add_row("根因分析", report.root_cause[:100] + "..." if len(report.root_cause) > 100 else report.root_cause)
            result_table.add_row("置信度", f"{report.confidence * 100:.1f}%")
            result_table.add_row("执行步骤数", str(len(report.executed_steps)))
            result_table.add_row("总耗时", f"{report.total_time:.2f}秒")
            result_table.add_row("需要人工介入", "是" if report.need_human else "否")

            console.print(result_table)

            # 显示执行步骤
            if report.executed_steps:
                console.print("\n[bold]执行步骤详情:[/bold]")
                steps_table = Table(show_header=True, header_style="bold cyan")
                steps_table.add_column("步骤", width=8)
                steps_table.add_column("操作", width=20)
                steps_table.add_column("结果", width=10)
                steps_table.add_column("详情", width=30)

                for step in report.executed_steps:
                    status = "[green]成功[/green]" if step.success else "[red]失败[/red]"
                    details = ""
                    if step.command_result:
                        if step.command_result.stdout:
                            details = step.command_result.stdout[:30] + "..."
                        elif step.command_result.stderr:
                            details = step.command_result.stderr[:30] + "..."

                    steps_table.add_row(
                        f"Step {step.step_number}",
                        step.step_name,
                        status,
                        details
                    )

                console.print(steps_table)

            # 显示建议措施
            if report.fix_suggestions:
                console.print("\n[bold]建议措施:[/bold]")
                for idx, suggestion in enumerate(report.fix_suggestions, 1):
                    console.print(f"  {idx}. {suggestion}")

            # 验证根因是否正确
            console.print(f"\n[yellow]Step 5: 验证诊断结果...[/yellow]")
            root_cause_lower = report.root_cause.lower()
            expected_keywords = scenario['expected_root_cause']

            match_found = any(keyword.lower() in root_cause_lower for keyword in expected_keywords)

            if match_found:
                console.print(f"[green]OK PASS[/green] - 根因分析正确")
                console.print(f"  匹配关键词: {', '.join(expected_keywords)}")
                test_passed = True
            else:
                console.print(f"[red]X FAIL[/red] - 根因分析不符合预期")
                console.print(f"  期望关键词: {', '.join(expected_keywords)}")
                console.print(f"  实际根因: {report.root_cause}")
                test_passed = False

            results.append({
                "scenario": scenario['name'],
                "passed": test_passed,
                "task_id": task.task_id,
                "steps": len(report.executed_steps),
                "confidence": report.confidence,
                "root_cause": report.root_cause
            })

        except Exception as e:
            console.print(f"\n[red]X 测试失败: {str(e)}[/red]")
            import traceback
            traceback.print_exc()

            results.append({
                "scenario": scenario['name'],
                "passed": False,
                "error": str(e)
            })

    # 输出测试总结
    console.print("\n\n[bold cyan]" + "=" * 70)
    console.print("[bold cyan]测试总结")
    console.print("[bold cyan]" + "=" * 70 + "\n")

    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("场景", style="cyan", width=35)
    summary_table.add_column("结果", width=10)
    summary_table.add_column("步骤数", width=8)
    summary_table.add_column("置信度", width=10)

    total_passed = 0
    for result in results:
        if result['passed']:
            total_passed += 1
            status = "[green]PASS[/green]"
        else:
            status = "[red]FAIL[/red]"

        summary_table.add_row(
            result['scenario'],
            status,
            str(result.get('steps', 'N/A')),
            f"{result.get('confidence', 0) * 100:.1f}%" if 'confidence' in result else "N/A"
        )

    console.print(summary_table)

    # 统计信息
    console.print(f"\n[bold]统计信息:[/bold]")
    console.print(f"  总测试数: {len(results)}")
    console.print(f"  [green]通过: {total_passed}[/green]")
    console.print(f"  [red]失败: {len(results) - total_passed}[/red]")
    console.print(f"  成功率: {total_passed/len(results)*100:.1f}%\n")

    if total_passed == len(results):
        console.print("[bold green]OK 所有测试通过！[/bold green]")
        console.print("\n[bold]LLM Agent 诊断流程验证成功！[/bold]")
        console.print("  OK NLU解析正常")
        console.print("  OK LLM决策正常")
        console.print("  OK 网络工具调用正常")
        console.print("  OK 诊断报告生成正常")
        return True
    else:
        console.print("[bold red]X 部分测试失败[/bold red]")
        return False


async def test_agent_step_by_step():
    """测试单个场景的详细步骤"""
    console.print("\n[bold cyan]" + "=" * 70)
    console.print("[bold cyan]详细步骤演示: 端口拒绝连接场景")
    console.print("[bold cyan]" + "=" * 70 + "\n")

    user_input = "生产环境app-01访问db-01的3306端口refused"

    console.print(Panel(
        user_input,
        title="[cyan]用户报告故障[/cyan]",
        border_style="cyan"
    ))

    # 初始化组件
    console.print("\n[yellow]→ 初始化LLM Agent...[/yellow]")
    llm_client = LLMClient()
    nlu = NLU(llm_client=llm_client)
    llm_agent = LLMAgent(llm_client=llm_client, verbose=True)
    automation_client = llm_agent.network_tools.default_client
    console.print("[green]OK[/green] 初始化完成\n")

    # 解析
    console.print("[yellow]→ NLU解析...[/yellow]")
    task = nlu.parse_user_input(user_input, "demo_001")
    console.print(f"[green]OK[/green] 解析结果: {task.source} → {task.target}:{task.port}\n")

    # 设置场景
    automation_client.set_scenario("scenario1_refused")

    # 执行诊断
    console.print("[yellow]→ 开始诊断（LLM将动态决策）...[/yellow]\n")
    report = await llm_agent.diagnose(task)

    console.print(f"\n[bold green]OK 诊断完成！[/bold green]")
    console.print(f"\n[bold]根因:[/bold] {report.root_cause}")
    console.print(f"[bold]置信度:[/bold] {report.confidence * 100:.1f}%")
    console.print(f"[bold]执行步骤:[/bold] {len(report.executed_steps)}步")

    return True


def main():
    """主测试入口"""
    import os

    console.print("[bold cyan]" + "=" * 70)
    console.print("[bold cyan]LLM Agent 端到端测试套件")
    console.print("[bold cyan]" + "=" * 70 + "\n")

    # 检查环境变量
    api_key = os.getenv("API_KEY")
    if not api_key:
        console.print("[red]错误: 未配置API_KEY，请检查.env文件[/red]")
        sys.exit(1)

    console.print("[bold]环境配置:[/bold]")
    console.print(f"  API_BASE_URL: {os.getenv('API_BASE_URL')}")
    console.print(f"  MODEL: {os.getenv('MODEL')}")
    console.print(f"  API_KEY: 已配置\n")

    try:
        # 测试1: 详细步骤演示
        console.print("[bold]测试1: 详细步骤演示[/bold]\n")
        result1 = asyncio.run(test_agent_step_by_step())

        # 测试2: 完整诊断流程（多场景）
        console.print("\n\n[bold]测试2: 完整诊断流程（多场景）[/bold]\n")
        result2 = asyncio.run(test_complete_diagnosis_flow())

        if result1 and result2:
            console.print("\n\n[bold green]" + "=" * 70)
            console.print("OK 所有测试通过！")
            console.print("=" * 70 + "[/bold green]\n")
            sys.exit(0)
        else:
            console.print("\n\n[bold red]" + "=" * 70)
            console.print("X 部分测试失败")
            console.print("=" * 70 + "[/bold red]\n")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]测试被用户中断[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n[red]测试失败: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
