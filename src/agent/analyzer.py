"""
结果分析器

汇总执行结果，推断根因，生成修复建议
"""
import json
from typing import List, Optional

from ..integrations.llm_client import LLMClient
from ..models.report import DiagnosticReport
from ..models.results import StepResult
from ..models.task import DiagnosticTask


class DiagnosticAnalyzer:
    """
    诊断结果分析器

    Phase 1实现：基于规则的分析
    Phase 2实现：规则 + AI辅助分析
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, use_llm: bool = False):
        """
        初始化分析器

        Args:
            llm_client: LLM客户端
            use_llm: 是否启用LLM辅助分析
        """
        self.llm_client = llm_client
        self.use_llm = use_llm

    def analyze(
        self,
        task: DiagnosticTask,
        results: List[StepResult]
    ) -> DiagnosticReport:
        """
        分析排查结果

        Args:
            task: 诊断任务
            results: 所有步骤执行结果

        Returns:
            DiagnosticReport: 诊断报告
        """
        # 基于规则的分析
        rule_result = self._rule_based_analysis(task, results)

        # 如果规则分析置信度高，直接返回
        if rule_result.confidence >= 0.8:
            return rule_result

        # 如果启用LLM且置信度不高，使用AI辅助分析
        if self.use_llm and self.llm_client:
            try:
                ai_result = self._ai_analysis(task, results, rule_result)
                # 如果AI分析置信度更高，使用AI结果
                if ai_result.confidence > rule_result.confidence:
                    return ai_result
            except Exception as e:
                print(f"AI分析失败，使用规则分析结果: {str(e)}")

        return rule_result

    def _rule_based_analysis(
        self,
        task: DiagnosticTask,
        results: List[StepResult]
    ) -> DiagnosticReport:
        """
        基于规则的根因判断

        Args:
            task: 诊断任务
            results: 步骤结果列表

        Returns:
            DiagnosticReport
        """
        # 计算总耗时
        total_time = sum(
            step.command_result.execution_time
            for step in results
            if step.command_result
        )

        # 提取关键信息
        metadata_summary = {
            f"step_{step.step_number}": step.metadata
            for step in results
        }

        # 场景1: Connection Refused + 端口未监听
        if self._check_pattern(metadata_summary, "refused_not_listening"):
            return DiagnosticReport(
                task_id=task.task_id,
                root_cause="目标主机上服务未启动或未监听指定端口",
                confidence=0.9,
                evidence=[
                    "Telnet连接被拒绝（Connection refused）",
                    "ss命令显示端口未监听",
                    "ICMP可达（网络层正常）"
                ],
                fix_suggestions=[
                    f"检查目标服务状态: systemctl status <service>",
                    f"确认服务配置的监听端口是否为 {task.port}",
                    f"查看服务日志: journalctl -u <service>"
                ],
                need_human=False,
                executed_steps=results,
                total_time=total_time
            )

        # 场景2: Ping通 + Telnet超时 + 防火墙DROP
        if self._check_pattern(metadata_summary, "timeout_ping_ok_firewall"):
            return DiagnosticReport(
                task_id=task.task_id,
                root_cause="目标主机防火墙阻断了指定端口的入站流量",
                confidence=0.85,
                evidence=[
                    "Telnet连接超时",
                    "ICMP可达（Ping成功）",
                    f"iptables规则阻断了端口 {task.port}"
                ],
                fix_suggestions=[
                    f"检查目标主机防火墙规则: iptables -L INPUT -n -v",
                    f"添加允许规则: iptables -I INPUT -p tcp --dport {task.port} -j ACCEPT",
                    "确认安全组或云防火墙配置"
                ],
                need_human=False,
                executed_steps=results,
                total_time=total_time
            )

        # 场景3: Ping不通 + Traceroute断点
        if self._check_pattern(metadata_summary, "ping_fail_traceroute_broken"):
            last_reachable_ip = self._extract_value(
                metadata_summary,
                "last_reachable_ip"
            )
            return DiagnosticReport(
                task_id=task.task_id,
                root_cause="网络路径中存在故障节点或路由配置问题",
                confidence=0.75,
                evidence=[
                    "Telnet连接超时",
                    "ICMP不可达（Ping失败）",
                    f"Traceroute在 {last_reachable_ip} 后中断"
                ],
                fix_suggestions=[
                    "检查源主机到目标的路由配置",
                    "联系网络团队排查交换机或路由器故障",
                    f"登录 {last_reachable_ip} 设备检查路由表"
                ],
                need_human=True,
                executed_steps=results,
                total_time=total_time
            )

        # 默认兜底报告
        return DiagnosticReport(
            task_id=task.task_id,
            root_cause="无法明确判断根因，需要人工深入排查",
            confidence=0.5,
            evidence=[
                f"执行了 {len(results)} 个排查步骤",
                "未匹配到已知故障模式"
            ],
            fix_suggestions=[
                "查看详细排查步骤记录",
                "联系网络专家进行人工分析"
            ],
            need_human=True,
            executed_steps=results,
            total_time=total_time
        )

    def _check_pattern(self, metadata_summary: dict, pattern: str) -> bool:
        """
        检查是否匹配特定故障模式

        Args:
            metadata_summary: 所有步骤的元数据摘要
            pattern: 模式名称

        Returns:
            是否匹配
        """
        if pattern == "refused_not_listening":
            # Step 2: telnet refused, Step 3: 端口未监听
            step2 = metadata_summary.get("step_2", {})
            step3 = metadata_summary.get("step_3", {})
            return (
                step2.get("error_type") == "refused" and
                not step3.get("is_listening", True)
            )

        elif pattern == "timeout_ping_ok_firewall":
            # Step 2: telnet timeout, Step 4: ping成功, Step 5: 防火墙阻断
            step2 = metadata_summary.get("step_2", {})
            step4 = metadata_summary.get("step_4", {})
            step5 = metadata_summary.get("step_5", {})
            return (
                step2.get("error_type") == "timeout" and
                step4.get("is_reachable", False) and
                step5.get("has_blocking_rule", False)
            )

        elif pattern == "ping_fail_traceroute_broken":
            # Step 4: ping失败, Step 6: traceroute断点
            step4 = metadata_summary.get("step_4", {})
            step6 = metadata_summary.get("step_6", {})
            return (
                not step4.get("is_reachable", True) and
                step6.get("first_timeout_hop") is not None
            )

        return False

    def _extract_value(self, metadata_summary: dict, key: str):
        """
        从元数据中提取特定值

        Args:
            metadata_summary: 元数据摘要
            key: 要提取的键

        Returns:
            值或None
        """
        for step_meta in metadata_summary.values():
            if key in step_meta:
                return step_meta[key]
        return None

    def _ai_analysis(
        self,
        task: DiagnosticTask,
        results: List[StepResult],
        rule_result: DiagnosticReport
    ) -> DiagnosticReport:
        """
        LLM辅助分析（兜底）

        当规则分析置信度不高时，使用LLM进行深度分析

        Args:
            task: 诊断任务
            results: 执行结果
            rule_result: 规则分析结果

        Returns:
            DiagnosticReport
        """
        # 构建上下文信息
        context = self._build_analysis_context(task, results)

        # 构建提示词
        prompt = f"""你是网络故障诊断专家。请分析以下排查结果：

故障描述: {task.user_input}
源主机: {task.source}
目标主机: {task.target}
协议: {task.protocol.value}
端口: {task.port if task.port else 'N/A'}

执行步骤及结果:
{context}

规则引擎的初步分析:
- 根因: {rule_result.root_cause}
- 置信度: {rule_result.confidence}

请给出更深入的分析，输出JSON格式:
{{
  "root_cause": "最可能的根因（详细描述）",
  "confidence": 0.0-1.0之间的置信度,
  "evidence": ["证据1", "证据2", "证据3"],
  "fix_suggestions": ["建议1", "建议2", "建议3"],
  "need_human": true/false（是否需要人工深入排查）
}}"""

        try:
            # 调用LLM
            response = self.llm_client.invoke_with_json(
                prompt=prompt,
                temperature=0.3
            )

            # 解析JSON响应
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))

                # 构建报告
                total_time = sum(
                    step.command_result.execution_time
                    for step in results
                    if step.command_result
                )

                return DiagnosticReport(
                    task_id=task.task_id,
                    root_cause=analysis.get("root_cause", rule_result.root_cause),
                    confidence=float(analysis.get("confidence", rule_result.confidence)),
                    evidence=analysis.get("evidence", rule_result.evidence),
                    fix_suggestions=analysis.get("fix_suggestions", rule_result.fix_suggestions),
                    need_human=bool(analysis.get("need_human", rule_result.need_human)),
                    executed_steps=results,
                    total_time=total_time,
                    metadata={"analysis_method": "llm_assisted"}
                )

        except Exception as e:
            print(f"LLM分析失败: {str(e)}")

        # 失败时返回规则结果
        return rule_result

    def _build_analysis_context(self, task: DiagnosticTask, results: List[StepResult]) -> str:
        """
        构建分析上下文字符串

        Args:
            task: 诊断任务
            results: 执行结果

        Returns:
            格式化的上下文字符串
        """
        context_parts = []

        for step in results:
            context_parts.append(f"\n### Step {step.step_number}: {step.step_name}")
            context_parts.append(f"动作: {step.action}")
            context_parts.append(f"结果: {'成功' if step.success else '失败'}")

            if step.command_result:
                context_parts.append(f"命令: {step.command_result.command}")
                context_parts.append(f"主机: {step.command_result.host}")
                if step.command_result.stdout:
                    stdout_preview = step.command_result.stdout[:200]
                    context_parts.append(f"输出: {stdout_preview}")
                if step.command_result.stderr:
                    stderr_preview = step.command_result.stderr[:200]
                    context_parts.append(f"错误: {stderr_preview}")

            if step.metadata:
                context_parts.append(f"元数据: {step.metadata}")

        return "\n".join(context_parts)
