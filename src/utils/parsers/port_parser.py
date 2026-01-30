"""
端口监听状态解析器

解析ss -tunlp或netstat输出，判断指定端口是否在监听
"""
import re

from ...models.results import CommandResult
from .base import PortListeningStatus


def check_port_listening(result: CommandResult, port: int) -> PortListeningStatus:
    """
    解析ss命令输出，检查端口是否在监听

    Args:
        result: 命令执行结果
        port: 要检查的端口号

    Returns:
        PortListeningStatus: 端口监听状态信息

    示例输入:
        tcp   LISTEN  0   128   *:80   *:*   users:(("nginx",pid=1234,fd=6))
        tcp   LISTEN  0   128   127.0.0.1:3306   *:*   users:(("mysqld",pid=5678,fd=10))

    解析逻辑:
        1. 查找包含目标端口的行
        2. 检查状态是否为LISTEN
        3. 提取进程名和PID
    """
    stdout = result.stdout

    # 正则表达式匹配ss输出格式
    # 格式: tcp   LISTEN  ...  *:80  ...  users:(("nginx",pid=1234,fd=6))
    pattern = rf"tcp\s+LISTEN\s+.*?[\*:]({port})\s+.*?users:\(\(\"([^\"]+)\",pid=(\d+)"

    match = re.search(pattern, stdout, re.MULTILINE)
    if match:
        process_name = match.group(2)
        pid = int(match.group(3))

        # 提取绑定地址
        bind_pattern = rf"([\d\.:]+):({port})\s"
        bind_match = re.search(bind_pattern, stdout)
        bind_address = bind_match.group(1) if bind_match else "*"

        return PortListeningStatus(
            is_listening=True,
            process_name=process_name,
            pid=pid,
            bind_address=bind_address
        )

    # 未找到监听记录
    return PortListeningStatus(
        is_listening=False,
        process_name=None,
        pid=None,
        bind_address=""
    )
