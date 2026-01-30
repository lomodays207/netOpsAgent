"""
网络工具基础功能测试

测试execute_command和query_cmdb工具是否能正常工作
"""
import asyncio
from rich.console import Console
from rich.table import Table

console = Console()


async def test_execute_command():
    """测试execute_command工具"""
    console.print("\n[bold cyan]测试1: execute_command工具[/bold cyan]")
    console.print("=" * 60)

    # 导入网络工具
    from src.integrations.network_tools import NetworkTools
    from src.integrations.automation_platform_client import AutomationPlatformClient

    # 创建客户端并设置场景
    automation_client = AutomationPlatformClient()
    network_tools = NetworkTools(default_client=automation_client, use_router=False)

    # 测试用例
    test_cases = [
        {
            "name": "Telnet测试 (scenario1_refused)",
            "host": "10.0.1.10",
            "command": "timeout 5 bash -c 'cat < /dev/tcp/10.0.2.20/80'",
            "scenario": "scenario1_refused"
        },
        {
            "name": "端口监听检查",
            "host": "10.0.2.20",
            "command": "ss -tlnp | grep ':80'",
            "scenario": "scenario1_refused"
        },
        {
            "name": "Ping测试",
            "host": "10.0.1.10",
            "command": "ping -c 4 10.0.2.20",
            "scenario": "scenario3_network_broken"
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        console.print(f"\n[yellow]测试 {i}/{len(test_cases)}[/yellow]: {test_case['name']}")
        console.print(f"  主机: {test_case['host']}")
        console.print(f"  命令: {test_case['command']}")
        console.print(f"  场景: {test_case['scenario']}")

        try:
            # 设置场景（用于Mock测试）
            automation_client.set_scenario(test_case['scenario'])

            # 调用network_tools执行命令
            result = await network_tools.execute_command(
                host=test_case['host'],
                command=test_case['command'],
                timeout=30
            )

            # 显示结果
            console.print(f"  [green]成功: {result['success']}[/green]")
            console.print(f"  退出码: {result['exit_code']}")
            if result.get('stdout'):
                console.print(f"  输出: {result['stdout'][:100]}...")
            if result.get('stderr'):
                console.print(f"  错误: {result['stderr'][:100]}...")

            results.append({
                "test": test_case['name'],
                "success": result['success'],
                "exit_code": result['exit_code']
            })

        except Exception as e:
            console.print(f"  [red]异常: {str(e)}[/red]")
            results.append({
                "test": test_case['name'],
                "success": False,
                "error": str(e)
            })

    return results


async def test_query_cmdb():
    """测试query_cmdb工具"""
    console.print("\n\n[bold cyan]测试2: query_cmdb工具[/bold cyan]")
    console.print("=" * 60)

    from src.integrations.network_tools import NetworkTools

    # 创建网络工具
    network_tools = NetworkTools(use_router=False)

    # 测试用例
    hosts = ["10.0.1.10", "10.0.2.20", "web-server-01"]

    console.print(f"\n[yellow]查询主机信息[/yellow]")
    console.print(f"  主机列表: {', '.join(hosts)}")

    try:
        # 调用network_tools查询CMDB
        result = await network_tools.query_cmdb(hosts=hosts)

        console.print(f"  [green]成功: {result['success']}[/green]")
        console.print(f"  返回主机数: {len(result.get('hosts', []))}")

        # 显示主机信息
        if result.get('hosts'):
            table = Table(title="主机信息")
            table.add_column("主机名", style="cyan")
            table.add_column("IP", style="yellow")
            table.add_column("业务", style="green")
            table.add_column("状态", style="magenta")

            for host in result['hosts']:
                table.add_row(
                    host.get('hostname', 'N/A'),
                    host.get('ip', 'N/A'),
                    host.get('business', 'N/A'),
                    host.get('status', 'N/A')
                )

            console.print(table)

        return {"success": result['success'], "host_count": len(result.get('hosts', []))}

    except Exception as e:
        console.print(f"  [red]异常: {str(e)}[/red]")
        return {"success": False, "error": str(e)}


async def main():
    """运行所有测试"""
    console.print("[bold cyan]MCP Server基础功能测试[/bold cyan]")
    console.print("=" * 60)

    # 测试1: execute_command
    cmd_results = await test_execute_command()

    # 测试2: query_cmdb
    cmdb_result = await test_query_cmdb()

    # 总结
    console.print("\n\n[bold cyan]测试总结[/bold cyan]")
    console.print("=" * 60)

    # execute_command测试结果
    cmd_success = sum(1 for r in cmd_results if r.get('success'))
    console.print(f"\nexecute_command测试:")
    console.print(f"  总测试数: {len(cmd_results)}")
    console.print(f"  [green]成功: {cmd_success}[/green]")
    console.print(f"  [red]失败: {len(cmd_results) - cmd_success}[/red]")

    # query_cmdb测试结果
    console.print(f"\nquery_cmdb测试:")
    if cmdb_result.get('success'):
        console.print(f"  [green]成功[/green]")
        console.print(f"  返回主机数: {cmdb_result.get('host_count', 0)}")
    else:
        console.print(f"  [red]失败: {cmdb_result.get('error', 'Unknown')}[/red]")

    # 总体结果
    all_success = cmd_success == len(cmd_results) and cmdb_result.get('success')
    if all_success:
        console.print(f"\n[bold green]所有测试通过！[/bold green]")
    else:
        console.print(f"\n[bold yellow]部分测试失败，请检查日志[/bold yellow]")


if __name__ == "__main__":
    asyncio.run(main())

