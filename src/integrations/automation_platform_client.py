"""
自动化平台客户端

执行远程命令（Phase 1使用Mock响应）
"""
import hashlib
import json
import random
from pathlib import Path
from typing import Dict, Optional

from ..models.results import CommandResult


# 自定义异常类
class AutomationAPIError(Exception):
    """自动化平台 API 错误基类"""
    pass


class DeviceNotFoundError(AutomationAPIError):
    """设备不存在异常"""
    pass


class CommandExecutionError(AutomationAPIError):
    """命令执行失败异常"""
    pass


class MockDataNotFoundError(AutomationAPIError):
    """Mock 数据不存在异常"""
    pass


class AutomationPlatformClient:
    """
    自动化平台API客户端

    Phase 1实现：从Mock JSON文件读取预定义的命令响应
    Phase 2实现：调用真实自动化平台API
    """

    def __init__(
        self,
        mock_responses_path: Optional[str] = None,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        """
        初始化自动化平台客户端

        Args:
            mock_responses_path: Mock响应数据文件路径（Phase 1）
            api_url: 自动化平台API地址（Phase 3多MCP server支持）
            api_token: 自动化平台API令牌（Phase 3多MCP server支持）
        """
        self.api_url = api_url
        self.api_token = api_token
        self.mock_responses_path = mock_responses_path or self._get_default_mock_path()
        self.mock_responses = self._load_mock_responses()
        self.current_scenario = None  # 当前自动选择的场景

    def _get_default_mock_path(self) -> str:
        """获取默认Mock响应数据路径"""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "tests" / "fixtures" / "mock_automation_responses.json")

    def _load_mock_responses(self) -> Dict:
        """
        加载Mock响应数据

        Returns:
            Mock响应数据字典

        Raises:
            MockDataNotFoundError: Mock数据文件不存在且无法创建默认数据
        """
        try:
            with open(self.mock_responses_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[AutomationClient] 成功加载 Mock 数据: {self.mock_responses_path}")
                return data
        except FileNotFoundError:
            print(f"[AutomationClient] 警告: Mock响应数据文件不存在: {self.mock_responses_path}")
            print(f"[AutomationClient] 将使用空的场景数据")
            return {"scenarios": {}}
        except json.JSONDecodeError as e:
            print(f"[AutomationClient] 错误: Mock数据JSON格式错误: {e}")
            print(f"[AutomationClient] 将使用空的场景数据")
            return {"scenarios": {}}
        except Exception as e:
            print(f"[AutomationClient] 错误: 加载Mock数据失败: {e}")
            print(f"[AutomationClient] 将使用空的场景数据")
            return {"scenarios": {}}

    def _auto_select_scenario(self, key: str) -> str:
        """
        根据key自动选择故障场景

        使用哈希算法保证同样的输入总是得到同样的场景

        Args:
            key: 用于选择场景的key（如device、或source-target-port组合）

        Returns:
            场景名称
        """
        # 如果已经选择了场景，直接返回
        if self.current_scenario:
            return self.current_scenario

        # 根据key生成哈希值
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)

        # 获取可用的场景列表
        scenarios = list(self.mock_responses.get("scenarios", {}).keys())
        if not scenarios:
            return "scenario1_refused"  # 默认场景

        # 根据哈希值选择场景
        scenario_index = hash_value % len(scenarios)
        self.current_scenario = scenarios[scenario_index]

        print(f"[自动选择场景] {key} -> {self.current_scenario}")
        return self.current_scenario

    async def execute(
        self,
        device: str,
        command: str,
        timeout: int = 30,
        scenario: Optional[str] = None
    ) -> CommandResult:
        """
        在指定设备上执行命令

        Args:
            device: 目标设备名称（服务器主机名或交换机名称）
            command: 要执行的命令
            timeout: 超时时间（秒）
            scenario: 测试场景名称（Phase 1 Mock用，如果为None则自动选择）

        Returns:
            CommandResult: 命令执行结果

        Raises:
            DeviceNotFoundError: 设备不存在
            TimeoutError: 命令执行超时
        """
        # Phase 1: 从Mock数据中查找响应
        # 如果没有指定scenario，自动选择一个
        if scenario is None:
            scenario = self._auto_select_scenario(device)

        return self._get_mock_response(device, command, scenario)

    def _get_mock_response(self, device: str, command: str, scenario: str) -> CommandResult:
        """
        从Mock数据中获取响应

        Args:
            device: 设备名称
            command: 命令
            scenario: 场景名称

        Returns:
            CommandResult对象
        """
        scenarios = self.mock_responses.get("scenarios", {})
        scenario_data = scenarios.get(scenario, {})

        # 根据命令类型匹配Mock响应
        command_key = self._match_command_key(command)
        commands = scenario_data.get("commands", {})

        if command_key in commands:
            mock_data = commands[command_key]
            # 如果没有 explicit success 字段，根据 exit_code 判断
            success = mock_data.get("success")
            if success is None:
                success = mock_data.get("exit_code", 0) == 0

            return CommandResult(
                command=command,
                host=device,
                success=success,
                stdout=mock_data.get("stdout", ""),
                stderr=mock_data.get("stderr", ""),
                exit_code=mock_data.get("exit_code", 0),
                execution_time=mock_data.get("execution_time", 0.5)
            )

        # 未找到Mock数据，随机从其他场景中选择一个响应
        return self._get_random_response(command, device, command_key)

    def _match_command_key(self, command: str) -> str:
        """
        匹配命令的Mock key

        Args:
            command: 实际命令字符串

        Returns:
            Mock数据中的key名称
        """
        # 规范化命令：去除多余空格，转换为小写
        normalized_cmd = ' '.join(command.lower().split())

        # 关键字匹配（与mock_automation_responses.json中的key保持一致）
        if "telnet" in normalized_cmd or "/dev/tcp" in normalized_cmd:
            return "telnet_test"
        elif "ss" in normalized_cmd and ("tuln" in normalized_cmd or "tunlp" in normalized_cmd or "tlnp" in normalized_cmd):
            # 支持 ss -tuln, ss -tunlp 和 ss -tlnp 等格式
            return "ss_listen"
        elif "netstat" in normalized_cmd and ("tunlp" in normalized_cmd or "tlnp" in normalized_cmd):
            # 支持 netstat 命令
            return "ss_listen"
        elif "ping" in normalized_cmd and "-c" in normalized_cmd:
            return "ping"
        elif "iptables" in normalized_cmd and ("-l" in normalized_cmd or "list" in normalized_cmd):
            return "iptables_list"
        elif "traceroute" in normalized_cmd:
            return "traceroute"
        else:
            return "unknown_command"

    def _get_random_response(self, command: str, device: str, command_key: str) -> CommandResult:
        """
        当未找到匹配的命令时，随机返回一个场景的响应

        Args:
            command: 命令字符串
            device: 设备名称
            command_key: 命令key

        Returns:
            CommandResult对象
        """
        scenarios = self.mock_responses.get("scenarios", {})
        
        if scenarios:
            # 从所有场景中收集该命令类型的所有可能响应
            available_responses = []
            for scenario_name, scenario_data in scenarios.items():
                if command_key in scenario_data.get("commands", {}):
                    available_responses.append(scenario_data["commands"][command_key])
            
            # 如果找到可用的响应，随机选择一个
            if available_responses:
                mock_data = random.choice(available_responses)
                
                # 如果没有 explicit success 字段，根据 exit_code 判断
                success = mock_data.get("success")
                if success is None:
                    success = mock_data.get("exit_code", 0) == 0

                print(f"[随机返回] 命令 '{command}' 未在当前场景中找到，随机返回一个可用响应")
                return CommandResult(
                    command=command,
                    host=device,
                    success=success,
                    stdout=mock_data.get("stdout", ""),
                    stderr=mock_data.get("stderr", ""),
                    exit_code=mock_data.get("exit_code", 0),
                    execution_time=mock_data.get("execution_time", 0.5)
                )
        
        # 如果所有场景中都没有该命令类型，返回通用的fallback响应
        # 根据命令类型返回合理的默认值
        if command_key == "ss_listen":
            # 随机返回端口存在或不存在
            port_exists = random.choice([True, False])
            if port_exists:
                return CommandResult(
                    command=command,
                    host=device,
                    success=True,
                    stdout="tcp   LISTEN  0   128   *:80   *:*   users:((\"nginx\",pid=1234,fd=6))",
                    stderr="",
                    exit_code=0,
                    execution_time=0.091
                )
            else:
                return CommandResult(
                    command=command,
                    host=device,
                    success=True,
                    stdout="",
                    stderr="",
                    exit_code=0,
                    execution_time=0.089
                )
        
        # 其他未知命令，返回成功但无输出
        print(f"[通用fallback] 命令 '{command}' 返回通用响应")
        return CommandResult(
            command=command,
            host=device,
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            execution_time=0.1
        )

    def set_scenario(self, scenario_name: str):
        """
        设置当前测试场景（用于测试）

        Args:
            scenario_name: 场景名称
        """
        self.current_scenario = scenario_name
