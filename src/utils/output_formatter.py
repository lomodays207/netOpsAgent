"""
工具输出格式化器

提供美化的工具调用结果输出，支持verbose和默认两种模式
"""
from rich.console import Console
from rich.panel import Panel
from typing import Dict


class ToolOutputFormatter:
    """工具输出格式化器"""

    def __init__(self, verbose: bool = False):
        """
        初始化格式化器

        Args:
            verbose: 是否启用详细模式
        """
        self.console = Console(emoji=False, legacy_windows=False)
        self.verbose = verbose

    def format_tool_call(self, tool_name: str, arguments: Dict, result: Dict):
        """
        格式化工具调用结果

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            result: 执行结果
        """
        # 基本信息
        self.console.print(f"\n[bold cyan]工具调用: {tool_name}[/bold cyan]")

        # 参数
        self.console.print("[dim]参数:[/dim]")
        for key, value in arguments.items():
            self.console.print(f"  {key}: {value}")

        # 执行结果
        success = result.get('success', False)
        status_color = "green" if success else "red"
        status_text = "成功" if success else "失败"
        self.console.print(f"\n[{status_color}]状态: {status_text}[/{status_color}]")

        # 详细输出
        if self.verbose:
            self._print_detailed_output(result)
        else:
            self._print_summary_output(result)

    def _print_detailed_output(self, result: Dict):
        """打印详细输出（verbose模式）"""
        # 完整stdout
        if result.get('stdout'):
            self.console.print("\n[bold]标准输出:[/bold]")
            # 使用Panel美化输出，避免emoji
            self.console.print(Panel(result['stdout'], border_style="green", title="stdout"))

        # 完整stderr
        if result.get('stderr'):
            self.console.print("\n[bold]错误输出:[/bold]")
            self.console.print(Panel(result['stderr'], border_style="red", title="stderr"))

        # 其他信息
        self.console.print(f"\n退出码: {result.get('exit_code', 'N/A')}")
        self.console.print(f"执行时间: {result.get('execution_time', 0):.2f}秒")
        self.console.print(f"执行主机: {result.get('host', 'N/A')}")

    def _print_summary_output(self, result: Dict):
        """打印摘要输出（默认模式）"""
        # 显示前300字符（比原来的100字符多）
        stdout = result.get('stdout', '')
        if stdout:
            display_text = stdout[:300]
            if len(stdout) > 300:
                display_text += f"\n... (还有{len(stdout)-300}字符，使用--verbose查看完整输出)"
            self.console.print(f"\n输出: {display_text}")

        # 如果有错误，总是显示
        if result.get('stderr'):
            stderr = result['stderr']
            display_stderr = stderr[:200]
            if len(stderr) > 200:
                display_stderr += f"\n... (还有{len(stderr)-200}字符)"
            self.console.print(f"[red]错误: {display_stderr}[/red]")
