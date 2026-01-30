"""
任务规划器

根据故障类型生成排查计划（Phase 1使用固定流程）
"""
from typing import Dict, List

from ..models.task import DiagnosticTask, FaultType


class TaskPlanner:
    """
    任务规划器

    Phase 1实现：基于固定流程YAML（简化为硬编码决策树）
    Phase 2实现：加载YAML配置 + AI推理兜底
    """

    def __init__(self):
        """初始化规划器"""
        pass

    def plan(self, task: DiagnosticTask, mode: str = "fast") -> List[Dict]:
        """
        根据任务生成执行计划

        Args:
            task: 诊断任务
            mode: 执行模式（fast | deep）- Phase 1只支持fast

        Returns:
            步骤列表，每个步骤包含：
            {
                "step": 步骤编号,
                "name": 步骤名称,
                "action": 动作类型,
                "command_template": 命令模板,
                "on_host": 执行主机,
                "params": 参数字典
            }
        """
        if task.fault_type == FaultType.PORT_UNREACHABLE:
            return self._plan_port_unreachable(task)
        elif task.fault_type == FaultType.CONNECTIVITY:
            return self._plan_connectivity(task)
        else:
            # 其他故障类型暂不支持
            return []

    def _plan_port_unreachable(self, task: DiagnosticTask) -> List[Dict]:
        """
        端口不可达故障排查流程

        固定流程：
        1. Telnet测试
        2. 判断refused vs timeout
        3. 如果refused → 检查端口监听
        4. 如果timeout → Ping测试 → 防火墙检查 / Traceroute
        """
        plan = [
            {
                "step": 1,
                "name": "验证主机存在性",
                "action": "query_cmdb",
                "params": {
                    "hosts": [task.source, task.target]
                }
            },
            {
                "step": 2,
                "name": "端口连通性测试（telnet）",
                "action": "execute_command",
                "command_template": "telnet_test",
                "on_host": task.source,
                "params": {
                    "target": task.target,
                    "port": task.port,
                    "timeout": 5
                }
            },
            # 后续步骤根据telnet结果动态决定
        ]
        return plan

    def _plan_connectivity(self, task: DiagnosticTask) -> List[Dict]:
        """
        连通性故障排查流程

        固定流程：
        1. Ping测试
        2. 如果失败 → Traceroute定位断点
        """
        plan = [
            {
                "step": 1,
                "name": "验证主机存在性",
                "action": "query_cmdb",
                "params": {
                    "hosts": [task.source, task.target]
                }
            },
            {
                "step": 2,
                "name": "基础连通性测试（ping）",
                "action": "execute_command",
                "command_template": "ping",
                "on_host": task.source,
                "params": {
                    "target": task.target,
                    "count": 4,
                    "timeout": 5
                }
            }
        ]
        return plan

    def get_next_step(
        self,
        current_step: int,
        step_result: Dict,
        task: DiagnosticTask
    ) -> List[Dict]:
        """
        根据当前步骤结果决定下一步

        Args:
            current_step: 当前步骤编号
            step_result: 当前步骤执行结果
            task: 诊断任务

        Returns:
            下一批要执行的步骤列表
        """
        if task.fault_type == FaultType.PORT_UNREACHABLE:
            return self._next_step_port_unreachable(current_step, step_result, task)
        else:
            return []

    def _next_step_port_unreachable(
        self,
        current_step: int,
        step_result: Dict,
        task: DiagnosticTask
    ) -> List[Dict]:
        """
        端口不可达故障的下一步决策

        决策树：
        - Step 2 telnet失败 → 判断error_type
          - refused → Step 3: 检查端口监听
          - timeout → Step 4: Ping测试
        - Step 4 ping成功 → Step 5: 检查防火墙
        - Step 4 ping失败 → Step 6: Traceroute
        """
        if current_step == 2:
            # Telnet测试完成，根据错误类型决定
            error_type = step_result.get("metadata", {}).get("error_type", "unknown")

            if error_type == "refused":
                # Connection refused → 检查目标端口监听
                return [{
                    "step": 3,
                    "name": "检查目标端口监听",
                    "action": "execute_command",
                    "command_template": "ss_listen",
                    "on_host": task.target,
                    "params": {"port": task.port}
                }]
            elif error_type == "timeout":
                # Connection timeout → Ping测试
                return [{
                    "step": 4,
                    "name": "基础连通性测试（ping）",
                    "action": "execute_command",
                    "command_template": "ping",
                    "on_host": task.source,
                    "params": {
                        "target": task.target,
                        "count": 4,
                        "timeout": 5
                    }
                }]

        elif current_step == 4:
            # Ping测试完成
            is_reachable = step_result.get("metadata", {}).get("is_reachable", False)

            if is_reachable:
                # Ping通但端口不通 → 检查防火墙
                return [{
                    "step": 5,
                    "name": "检查目标主机入站防火墙",
                    "action": "execute_command",
                    "command_template": "iptables_list_input",
                    "on_host": task.target,
                    "params": {"port": task.port}
                }]
            else:
                # Ping不通 → Traceroute定位断点
                return [{
                    "step": 6,
                    "name": "路由追踪定位断点",
                    "action": "execute_command",
                    "command_template": "traceroute",
                    "on_host": task.source,
                    "params": {
                        "target": task.target,
                        "max_hops": 30,
                        "timeout": 3
                    }
                }]

        # 没有更多步骤
        return []
