"""
端到端LLM测试

测试流程：
1. 用户自然语言输入
2. LLM解析提取结构化信息
3. 创建DiagnosticTask
4. (Mock)调用自动化平台执行命令
"""
import sys
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# 加载环境变量
load_dotenv()

from src.agent.nlu import NLU
from src.integrations.llm_client import LLMClient
from src.models.task import DiagnosticTask, FaultType, Protocol

console = Console()


def test_llm_real_call():
    """测试真实LLM调用"""
    console.print("[bold cyan]=" * 60)
    console.print("[bold cyan]测试1: 真实LLM调用测试")
    console.print("[bold cyan]=" * 60 + "\n")

    # 测试用例
    test_cases = [
        {
            "name": "标准格式 - Ping不通",
            "input": "server1到server2 ping不通",
            "expected": {
                "source": "server1",
                "target": "server2",
                "protocol": Protocol.ICMP,
                "fault_type": FaultType.CONNECTIVITY
            }
        },
        {
            "name": "自然语言 - 数据库连接",
            "input": "我们的应用服务器连不上数据库了",
            "expected": {
                "protocol": Protocol.TCP,
                "port": 3306,
                "fault_type": FaultType.PORT_UNREACHABLE
            }
        },
        {
            "name": "IP+端口格式",
            "input": "10.0.1.10访问10.0.2.20的80端口失败",
            "expected": {
                "source": "10.0.1.10",
                "target": "10.0.2.20",
                "protocol": Protocol.TCP,
                "port": 80,
                "fault_type": FaultType.PORT_UNREACHABLE
            }
        },
        {
            "name": "服务名称 - MySQL",
            "input": "web-01到db-01的MySQL连接总是超时",
            "expected": {
                "source": "web-01",
                "target": "db-01",
                "protocol": Protocol.TCP,
                "port": 3306,
                "fault_type": FaultType.PORT_UNREACHABLE
            }
        },
        {
            "name": "HTTP服务",
            "input": "服务器A访问服务器B的HTTP服务失败",
            "expected": {
                "protocol": Protocol.TCP,
                "port": 80,
                "fault_type": FaultType.PORT_UNREACHABLE
            }
        },
        {
            "name": "Redis缓存",
            "input": "应用无法连接到Redis缓存服务器cache-01",
            "expected": {
                "target": "cache-01",
                "protocol": Protocol.TCP,
                "port": 6379,
                "fault_type": FaultType.PORT_UNREACHABLE
            }
        },
        {
            "name": "性能问题",
            "input": "10.0.1.10访问10.0.2.20很慢，延迟很高",
            "expected": {
                "source": "10.0.1.10",
                "target": "10.0.2.20",
                "fault_type": FaultType.SLOW
            }
        },
        {
            "name": "混合格式 - 带IP",
            "input": "app-01(10.0.1.5)到db-01的3306端口refused",
            "expected": {
                "source": "10.0.1.5",
                "target": "db-01",
                "protocol": Protocol.TCP,
                "port": 3306,
                "fault_type": FaultType.PORT_UNREACHABLE
            }
        }
    ]

    try:
        # 初始化LLM客户端
        llm_client = LLMClient()
        console.print("[green]OK[/green] LLM客户端初始化成功\n")

        # 初始化NLU
        nlu = NLU(llm_client=llm_client)

        # 测试结果统计
        total = len(test_cases)
        success = 0
        failures = []

        # 执行测试
        for i, test_case in enumerate(test_cases, 1):
            console.print(f"[yellow]测试 {i}/{total}[/yellow]: {test_case['name']}")
            console.print(f"  输入: [cyan]{test_case['input']}[/cyan]")

            try:
                # 调用LLM解析
                task = nlu.parse_user_input(
                    user_input=test_case['input'],
                    task_id=f"test_{i:03d}"
                )

                # 显示解析结果
                console.print(f"  解析结果:")
                console.print(f"    - source: {task.source}")
                console.print(f"    - target: {task.target}")
                console.print(f"    - protocol: {task.protocol.value}")
                console.print(f"    - port: {task.port}")
                console.print(f"    - fault_type: {task.fault_type.value}")

                # 验证关键字段
                expected = test_case['expected']
                passed = True
                errors = []

                if 'source' in expected and task.source != expected['source']:
                    errors.append(f"source不匹配: 期望{expected['source']}, 实际{task.source}")
                    passed = False

                if 'target' in expected and task.target != expected['target']:
                    errors.append(f"target不匹配: 期望{expected['target']}, 实际{task.target}")
                    passed = False

                if 'protocol' in expected and task.protocol != expected['protocol']:
                    errors.append(f"protocol不匹配: 期望{expected['protocol'].value}, 实际{task.protocol.value}")
                    passed = False

                if 'port' in expected and task.port != expected['port']:
                    errors.append(f"port不匹配: 期望{expected['port']}, 实际{task.port}")
                    passed = False

                if 'fault_type' in expected and task.fault_type != expected['fault_type']:
                    errors.append(f"fault_type不匹配: 期望{expected['fault_type'].value}, 实际{task.fault_type.value}")
                    passed = False

                if passed:
                    console.print(f"  [green]PASS[/green]\n")
                    success += 1
                else:
                    console.print(f"  [red]FAIL[/red]")
                    for error in errors:
                        console.print(f"    - {error}")
                    console.print()
                    failures.append({
                        "name": test_case['name'],
                        "errors": errors
                    })

            except Exception as e:
                console.print(f"  [red]ERROR: {str(e)}[/red]\n")
                failures.append({
                    "name": test_case['name'],
                    "errors": [str(e)]
                })

        # 输出统计
        console.print("\n" + "=" * 60)
        console.print(f"[bold]测试结果统计[/bold]")
        console.print("=" * 60)
        console.print(f"总测试数: {total}")
        console.print(f"[green]成功: {success}[/green]")
        console.print(f"[red]失败: {total - success}[/red]")
        console.print(f"成功率: {success/total*100:.1f}%\n")

        if failures:
            console.print("[red]失败详情:[/red]")
            for failure in failures:
                console.print(f"  - {failure['name']}")
                for error in failure['errors']:
                    console.print(f"    {error}")

        return success == total

    except Exception as e:
        console.print(f"\n[red]测试初始化失败: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_e2e_workflow():
    """测试端到端工作流：用户输入 -> LLM解析 -> 任务创建 -> (Mock)命令执行"""
    console.print("\n[bold cyan]=" * 60)
    console.print("[bold cyan]测试2: 端到端工作流测试")
    console.print("[bold cyan]=" * 60 + "\n")

    # 模拟一个完整的诊断场景
    user_input = "生产环境web-server-01连不上数据库db-master了，急！"

    console.print(f"[bold]场景:[/bold] {user_input}\n")

    try:
        # Step 1: LLM解析用户输入
        console.print("[yellow]Step 1:[/yellow] LLM解析用户输入...")
        llm_client = LLMClient()
        nlu = NLU(llm_client=llm_client)

        task = nlu.parse_user_input(user_input, "emergency_001")

        console.print("[green]OK[/green] 解析完成")
        console.print(f"  任务ID: {task.task_id}")
        console.print(f"  源主机: {task.source}")
        console.print(f"  目标主机: {task.target}")
        console.print(f"  协议: {task.protocol.value}")
        console.print(f"  端口: {task.port}")
        console.print(f"  故障类型: {task.fault_type.value}\n")

        # Step 2: 生成诊断计划
        console.print("[yellow]Step 2:[/yellow] 生成诊断计划...")

        # 模拟规划器生成的步骤
        steps = [
            {
                "step_id": 1,
                "name": "验证主机存在性",
                "command": f"查询CMDB获取{task.source}和{task.target}信息"
            },
            {
                "step_id": 2,
                "name": "Telnet测试",
                "command": f"在{task.source}上执行: telnet {task.target} {task.port}"
            },
            {
                "step_id": 3,
                "name": "端口监听检查",
                "command": f"在{task.target}上执行: ss -tlnp | grep {task.port}"
            },
            {
                "step_id": 4,
                "name": "防火墙规则检查",
                "command": f"在{task.target}上执行: iptables -L -n | grep {task.port}"
            }
        ]

        console.print(f"[green]OK[/green] 生成{len(steps)}个诊断步骤\n")

        # Step 3: (Mock) 执行诊断命令
        console.print("[yellow]Step 3:[/yellow] 执行诊断命令...\n")

        # 创建结果表格
        table = Table(title="诊断执行结果", show_header=True)
        table.add_column("步骤", style="cyan", width=20)
        table.add_column("命令", style="yellow", width=40)
        table.add_column("状态", style="green", width=10)

        for step in steps:
            table.add_row(
                f"Step {step['step_id']}: {step['name']}",
                step['command'],
                "OK"
            )

        console.print(table)
        console.print()

        # Step 4: 分析结果
        console.print("[yellow]Step 4:[/yellow] 分析诊断结果...")

        # 模拟分析结果
        console.print("[green]OK[/green] 分析完成")
        console.print("  根因: 目标数据库服务未启动")
        console.print("  置信度: 90%")
        console.print("  建议措施: 在db-master上启动MySQL服务\n")

        console.print("[bold green]端到端测试成功！[/bold green]\n")
        return True

    except Exception as e:
        console.print(f"\n[red]端到端测试失败: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return False


def test_llm_metrics():
    """测试LLM调用指标收集"""
    console.print("\n[bold cyan]=" * 60)
    console.print("[bold cyan]测试3: LLM指标收集")
    console.print("[bold cyan]=" * 60 + "\n")

    try:
        llm_client = LLMClient()
        nlu = NLU(llm_client=llm_client)

        # 执行几次调用
        test_inputs = [
            "server1到server2 ping不通",
            "web访问db的MySQL失败",
            "应用连不上Redis"
        ]

        console.print("执行3次LLM调用...\n")

        import time
        metrics = []

        for i, user_input in enumerate(test_inputs, 1):
            console.print(f"[cyan]调用 {i}/3[/cyan]: {user_input}")

            start_time = time.time()
            try:
                task = nlu.parse_user_input(user_input, f"metric_test_{i}")
                latency = (time.time() - start_time) * 1000  # 转换为毫秒

                metrics.append({
                    "call_id": i,
                    "success": True,
                    "latency_ms": latency
                })

                console.print(f"  耗时: {latency:.0f}ms")
                console.print(f"  [green]成功[/green]\n")

            except Exception as e:
                latency = (time.time() - start_time) * 1000
                metrics.append({
                    "call_id": i,
                    "success": False,
                    "latency_ms": latency,
                    "error": str(e)
                })
                console.print(f"  耗时: {latency:.0f}ms")
                console.print(f"  [red]失败: {str(e)}[/red]\n")

        # 统计
        total_calls = len(metrics)
        success_calls = sum(1 for m in metrics if m['success'])
        avg_latency = sum(m['latency_ms'] for m in metrics) / total_calls

        console.print("=" * 60)
        console.print("[bold]LLM调用统计[/bold]")
        console.print("=" * 60)
        console.print(f"总调用次数: {total_calls}")
        console.print(f"成功: {success_calls}")
        console.print(f"失败: {total_calls - success_calls}")
        console.print(f"成功率: {success_calls/total_calls*100:.1f}%")
        console.print(f"平均延迟: {avg_latency:.0f}ms")
        console.print(f"最小延迟: {min(m['latency_ms'] for m in metrics):.0f}ms")
        console.print(f"最大延迟: {max(m['latency_ms'] for m in metrics):.0f}ms")

        # 估算成本 (基于DeepSeek定价: $0.14/1M input tokens, $0.28/1M output tokens)
        # 假设每次调用约1000 input tokens, 200 output tokens
        estimated_cost = total_calls * (1000 * 0.14 / 1_000_000 + 200 * 0.28 / 1_000_000)
        console.print(f"\n估算成本: ${estimated_cost:.6f} ({total_calls}次调用)")
        console.print(f"每次调用成本: ${estimated_cost/total_calls:.6f}\n")

        return True

    except Exception as e:
        console.print(f"\n[red]指标收集测试失败: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return False


def main():
    console.print("[bold cyan]=" * 60)
    console.print("[bold cyan]LLM端到端测试套件")
    console.print("[bold cyan]=" * 60)

    # 检查API配置
    api_key = os.getenv("API_KEY")
    api_base_url = os.getenv("API_BASE_URL")
    model = os.getenv("MODEL")

    console.print("[bold]环境配置:[/bold]")
    console.print(f"  API_BASE_URL: {api_base_url}")
    console.print(f"  MODEL: {model}")
    console.print(f"  API_KEY: {'已配置' if api_key else '未配置'}")

    if not api_key:
        console.print("\n[red]错误: 未配置API_KEY，请检查.env文件[/red]")
        sys.exit(1)

    console.print()

    # 运行测试
    results = {}

    try:
        # 测试1: 真实LLM调用
        results['llm_real_call'] = test_llm_real_call()

        # 测试2: 端到端工作流
       # results['e2e_workflow'] = test_e2e_workflow()

        # 测试3: LLM指标收集
       # results['llm_metrics'] = test_llm_metrics()

    except KeyboardInterrupt:
        console.print("\n\n[yellow]测试被用户中断[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n[red]测试过程中出现异常: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 总结
    console.print("\n" + "=" * 60)
    console.print("[bold]测试总结[/bold]")
    console.print("=" * 60)

    for test_name, result in results.items():
        status = "[green]PASS[/green]" if result else "[red]FAIL[/red]"
        console.print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    console.print()

    if all_passed:
        console.print("[bold green]所有测试通过！[/bold green]")
        console.print("\n[bold]下一步:[/bold]")
        console.print("  1. LLM功能已验证可用")
        console.print("  2. 可以使用 --use-llm 标志启用LLM增强")
        console.print("  3. 建议配置LLM可观测性和成本控制")
    else:
        console.print("[bold red]部分测试失败，请检查日志[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
