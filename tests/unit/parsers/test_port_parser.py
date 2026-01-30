"""
端口监听解析器单元测试
"""
import pytest

from src.models.results import CommandResult
from src.utils.parsers.port_parser import check_port_listening


class TestCheckPortListening:
    """端口监听状态检查测试"""

    def test_port_listening(self):
        """测试端口正在监听的场景"""
        result = CommandResult(
            command="ss -tunlp | grep ':80'",
            host="server2",
            success=True,
            stdout='tcp   LISTEN  0   128   *:80   *:*   users:(("nginx",pid=1234,fd=6))',
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        status = check_port_listening(result, 80)

        assert status.is_listening is True
        assert status.process_name == "nginx"
        assert status.pid == 1234

    def test_port_not_listening(self):
        """测试端口未监听的场景"""
        result = CommandResult(
            command="ss -tunlp | grep ':80'",
            host="server2",
            success=True,
            stdout='tcp   LISTEN  0   128   *:443   *:*   users:(("nginx",pid=1234,fd=6))',
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        status = check_port_listening(result, 80)

        assert status.is_listening is False
        assert status.process_name is None
        assert status.pid is None

    def test_port_listening_on_localhost(self):
        """测试仅监听127.0.0.1的场景"""
        result = CommandResult(
            command="ss -tunlp | grep ':3306'",
            host="server3",
            success=True,
            stdout='tcp   LISTEN  0   128   127.0.0.1:3306   *:*   users:(("mysqld",pid=5678,fd=10))',
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        status = check_port_listening(result, 3306)

        assert status.is_listening is True
        assert status.process_name == "mysqld"
        assert status.pid == 5678
        assert status.bind_address == "127.0.0.1"

    def test_empty_output(self):
        """测试空输出场景"""
        result = CommandResult(
            command="ss -tunlp | grep ':80'",
            host="server2",
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        status = check_port_listening(result, 80)

        assert status.is_listening is False
