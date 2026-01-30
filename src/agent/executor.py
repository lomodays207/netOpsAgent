"""
执行引擎

安全地执行命令、调用外部服务、解析结果
"""
from typing import Dict, Optional

from ..integrations import AutomationPlatformClient, CMDBClient
from ..models.results import CommandResult, StepResult
from ..utils.parsers import (
    check_port_listening,
    detect_telnet_error_type,
    identify_failed_hop,
    parse_iptables_rules,
    parse_ping_result,
    parse_traceroute_output,
)


class Executor:
    """
    执行引擎

    Phase 1实现：
    - 命令白名单验证（简化为模板匹配）
    - Mock自动化平台调用
    - 解析器调用
    """

    # 命令模板定义
    COMMAND_TEMPLATES = {
        "telnet_test": "timeout {timeout} bash -c 'cat < /dev/tcp/{target}/{port}' && echo SUCCESS || echo FAILED",
        "ss_listen": "ss -tunlp | grep ':{port}'",
        "ping": "ping -c {count} -W {timeout} {target}",
        "iptables_list_input": "iptables -L INPUT -n -v",
        "iptables_list_output": "iptables -L OUTPUT -n -v",
        "traceroute": "traceroute {target} -m {max_hops} -w {timeout}",
    }

    def __init__(
        self,
        automation_client: AutomationPlatformClient,
        cmdb_client: CMDBClient,
        scenario: Optional[str] = None
    ):
        """
        初始化执行引擎

        Args:
            automation_client: 自动化平台客户端
            cmdb_client: CMDB客户端
            scenario: 测试场景名称（Phase 1 Mock用）
        """
        self.automation_client = automation_client
        self.cmdb_client = cmdb_client
        self.scenario = scenario

    async def execute_step(self, step: Dict) -> StepResult:
        """
        执行单个步骤

        Args:
            step: 步骤定义字典

        Returns:
            StepResult: 步骤执行结果
        """
        action = step.get("action")

        if action == "query_cmdb":
            return await self._execute_cmdb_query(step)
        elif action == "execute_command":
            return await self._execute_command(step)
        else:
            return StepResult(
                step_number=step.get("step", 0),
                step_name=step.get("name", "Unknown"),
                action=action,
                success=False,
                metadata={"error": f"Unknown action: {action}"}
            )

    async def _execute_cmdb_query(self, step: Dict) -> StepResult:
        """
        执行CMDB查询

        Args:
            step: 步骤定义

        Returns:
            StepResult
        """
        hosts = step.get("params", {}).get("hosts", [])
        results = {}

        for host in hosts:
            host_info = self.cmdb_client.get_host_info(host)
            if host_info:
                results[host] = {
                    "exists": True,
                    "ip": host_info.ip,
                    "status": host_info.status
                }
            else:
                results[host] = {
                    "exists": False
                }

        # 判断是否所有主机都存在
        all_exist = all(r["exists"] for r in results.values())

        return StepResult(
            step_number=step.get("step", 0),
            step_name=step.get("name", "CMDB查询"),
            action="query_cmdb",
            success=all_exist,
            metadata={"hosts": results}
        )

    async def _execute_command(self, step: Dict) -> StepResult:
        """
        执行命令

        Args:
            step: 步骤定义

        Returns:
            StepResult
        """
        # 构建命令
        command_template = step.get("command_template", "")
        params = step.get("params", {})
        on_host = step.get("on_host", "")

        command = self._build_command(command_template, params)

        # 执行命令
        try:
            result = await self.automation_client.execute(
                device=on_host,
                command=command,
                timeout=params.get("timeout", 30),
                scenario=self.scenario
            )
        except Exception as e:
            return StepResult(
                step_number=step.get("step", 0),
                step_name=step.get("name", "命令执行"),
                action="execute_command",
                success=False,
                metadata={"error": str(e)}
            )

        # 解析结果
        metadata = self._parse_command_result(command_template, result, params)

        return StepResult(
            step_number=step.get("step", 0),
            step_name=step.get("name", "命令执行"),
            action="execute_command",
            command_result=result,
            success=result.success,
            metadata=metadata
        )

    def _build_command(self, template_name: str, params: Dict) -> str:
        """
        根据模板构建命令

        Args:
            template_name: 模板名称
            params: 参数字典

        Returns:
            完整的命令字符串
        """
        template = self.COMMAND_TEMPLATES.get(template_name, "")
        if not template:
            return f"# Unknown template: {template_name}"

        try:
            return template.format(**params)
        except KeyError as e:
            return f"# Missing parameter: {e}"

    def _parse_command_result(
        self,
        command_template: str,
        result: CommandResult,
        params: Dict
    ) -> Dict:
        """
        根据命令类型解析结果

        Args:
            command_template: 命令模板名称
            result: 命令执行结果
            params: 命令参数

        Returns:
            解析后的元数据字典
        """
        metadata = {}

        try:
            if command_template == "telnet_test":
                telnet_result = detect_telnet_error_type(result)
                metadata["error_type"] = telnet_result.error_type
                metadata["confidence"] = telnet_result.confidence

            elif command_template == "ss_listen":
                port = params.get("port", 0)
                port_status = check_port_listening(result, port)
                metadata["is_listening"] = port_status.is_listening
                metadata["process_name"] = port_status.process_name
                metadata["pid"] = port_status.pid

            elif command_template == "ping":
                ping_result = parse_ping_result(result)
                metadata["is_reachable"] = ping_result.is_reachable
                metadata["packet_loss"] = ping_result.packet_loss_percent
                metadata["rtt_avg"] = ping_result.rtt_avg

            elif command_template in ["iptables_list_input", "iptables_list_output"]:
                port = params.get("port", 0)
                chain = "INPUT" if "input" in command_template else "OUTPUT"
                iptables_result = parse_iptables_rules(result, port, chain)
                metadata["has_blocking_rule"] = iptables_result.has_blocking_rule
                metadata["rule_action"] = iptables_result.rule_action
                metadata["policy"] = iptables_result.policy

            elif command_template == "traceroute":
                traceroute_result = parse_traceroute_output(result)
                metadata["is_complete"] = traceroute_result.is_complete
                metadata["first_timeout_hop"] = traceroute_result.first_timeout_hop
                metadata["last_reachable_ip"] = (
                    traceroute_result.last_reachable_hop.ip_address
                    if traceroute_result.last_reachable_hop
                    else None
                )
                # 保存完整的traceroute结果供后续分析
                metadata["traceroute_result"] = traceroute_result

        except Exception as e:
            metadata["parse_error"] = str(e)

        return metadata
