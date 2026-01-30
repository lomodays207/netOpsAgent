"""
NLU模块 - 自然语言理解

使用LLM从用户自然语言描述中提取结构化任务信息
"""
import json
import re
from typing import Dict, Optional

from ..integrations.llm_client import LLMClient
from ..models.task import DiagnosticTask, FaultType, Protocol


class NLU:
    """
    自然语言理解模块

    使用LLM提取用户输入中的关键信息：
    - 源主机
    - 目标主机
    - 协议类型
    - 端口号
    - 故障类型
    """

    SYSTEM_PROMPT = """你是一个网络故障排查专家。你的任务是从用户的自然语言描述中提取关键信息。

你需要识别：
1. 源主机（source）：发起连接的主机，可能是IP或主机名
2. 目标主机（target）：目标主机，可能是IP或主机名
3. 协议（protocol）：icmp/tcp/udp
4. 端口（port）：如果是TCP/UDP，提取端口号
5. 故障类型（fault_type）：
   - connectivity: 连通性问题（ping不通、网络不可达）
   - port_unreachable: 端口不可达（telnet失败、端口不通）
   - slow: 响应慢、延迟高
   - dns: DNS解析问题

请严格按照JSON格式输出，不要有任何其他文字。"""

    EXTRACTION_PROMPT_TEMPLATE = """用户描述: {user_input}

请提取以下信息（JSON格式）:
{{
  "source": "源主机IP或主机名",
  "target": "目标主机IP或主机名",
  "protocol": "icmp/tcp/udp",
  "port": 端口号(数字，如果是ping/connectivity则为null),
  "fault_type": "connectivity/port_unreachable/slow/dns"
}}

示例1 - 标准ping场景:
用户描述: "server1到server2 ping不通"
输出: {{"source": "server1", "target": "server2", "protocol": "icmp", "port": null, "fault_type": "connectivity"}}

示例2 - IP+端口场景:
用户描述: "10.0.1.10访问10.0.2.20的80端口失败"
输出: {{"source": "10.0.1.10", "target": "10.0.2.20", "protocol": "tcp", "port": 80, "fault_type": "port_unreachable"}}

示例3 - 自然语言场景:
用户描述: "我们的应用服务器连不上数据库了"
输出: {{"source": "应用服务器", "target": "数据库", "protocol": "tcp", "port": 3306, "fault_type": "port_unreachable"}}

示例4 - 服务名称场景:
用户描述: "web-01到db-01的MySQL连接总是超时"
输出: {{"source": "web-01", "target": "db-01", "protocol": "tcp", "port": 3306, "fault_type": "port_unreachable"}}

示例5 - HTTP服务场景:
用户描述: "服务器A访问服务器B的HTTP服务失败"
输出: {{"source": "服务器A", "target": "服务器B", "protocol": "tcp", "port": 80, "fault_type": "port_unreachable"}}

示例6 - 混合格式场景:
用户描述: "app-01(10.0.1.5)到db-01的3306端口refused"
输出: {{"source": "10.0.1.5", "target": "db-01", "protocol": "tcp", "port": 3306, "fault_type": "port_unreachable"}}

示例7 - 性能问题场景:
用户描述: "10.0.1.10访问10.0.2.20很慢，延迟很高"
输出: {{"source": "10.0.1.10", "target": "10.0.2.20", "protocol": "icmp", "port": null, "fault_type": "slow"}}

示例8 - 缺少端口号场景:
用户描述: "从办公网到生产环境server-prod连接失败"
输出: {{"source": "办公网", "target": "server-prod", "protocol": "tcp", "port": null, "fault_type": "port_unreachable"}}

示例9 - DNS问题场景:
用户描述: "无法解析www.example.com的域名"
输出: {{"source": "local", "target": "www.example.com", "protocol": "tcp", "port": null, "fault_type": "dns"}}

示例10 - Redis场景:
用户描述: "应用无法连接到Redis缓存服务器cache-01"
输出: {{"source": "应用", "target": "cache-01", "protocol": "tcp", "port": 6379, "fault_type": "port_unreachable"}}

注意事项:
- 常见服务端口: HTTP=80, HTTPS=443, MySQL=3306, Redis=6379, SSH=22, PostgreSQL=5432
- 如果描述中有IP地址，优先使用IP而不是主机名
- 如果缺少端口号且无法推断，设置为null
- 模糊描述优先判断为port_unreachable

现在请处理用户的输入："""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化NLU模块

        Args:
            llm_client: LLM客户端，如果为None则创建新实例
        """
        self.llm_client = llm_client or LLMClient()

    def parse_user_input(self, user_input: str, task_id: str) -> DiagnosticTask:
        """
        使用LLM解析用户输入

        Args:
            user_input: 用户输入的自然语言描述
            task_id: 任务ID

        Returns:
            DiagnosticTask对象
        """
        # 构建提示词
        prompt = self.EXTRACTION_PROMPT_TEMPLATE.format(user_input=user_input)

        try:
            # 调用LLM
            response = self.llm_client.invoke_with_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.3  # 较低温度以获得更确定的结果
            )
            print("----qiubo----")
            print(response)
            # 解析JSON响应
            extracted_info = self._parse_json_response(response)

            # 自动修复常见问题
            extracted_info = self._auto_fix_info(extracted_info, user_input)

            # 验证提取的信息
            self._validate_extracted_info(extracted_info)

            # 构建DiagnosticTask
            return DiagnosticTask(
                task_id=task_id,
                user_input=user_input,
                source=extracted_info["source"],
                target=extracted_info["target"],
                protocol=self._parse_protocol(extracted_info["protocol"]),
                port=extracted_info.get("port"),
                fault_type=self._parse_fault_type(extracted_info["fault_type"])
            )

        except Exception as e:
            # LLM调用失败，回退到规则解析
            print(f"LLM解析失败，回退到规则解析: {str(e)}")
            return self._fallback_rule_based_parse(user_input, task_id)

    def _parse_json_response(self, response: str) -> Dict:
        """
        解析LLM的JSON响应

        Args:
            response: LLM响应文本

        Returns:
            解析后的字典

        Raises:
            ValueError: 如果无法解析JSON或格式不正确
        """
        # 尝试提取JSON内容（支持嵌套括号）
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if not json_match:
            raise ValueError(f"无法在响应中找到JSON格式数据: {response[:100]}")

        json_str = json_match.group(0)
        try:
            parsed = json.loads(json_str)
            # 检查必需字段是否存在
            required_fields = ["source", "target", "protocol", "fault_type"]
            missing_fields = [f for f in required_fields if f not in parsed]
            if missing_fields:
                raise ValueError(f"JSON缺少必需字段: {', '.join(missing_fields)}")
            return parsed
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON格式错误: {str(e)}, 内容: {json_str[:100]}")

    def _validate_extracted_info(self, info: Dict) -> None:
        """
        验证提取的信息是否合理

        Args:
            info: 提取的信息字典

        Raises:
            ValueError: 如果信息不合理
        """
        # 验证source和target不为空
        if not info.get("source") or info["source"].strip() == "":
            raise ValueError("源主机不能为空")
        if not info.get("target") or info["target"].strip() == "":
            raise ValueError("目标主机不能为空")

        # 验证协议
        valid_protocols = ["icmp", "tcp", "udp"]
        protocol = info.get("protocol", "").lower()
        if protocol not in valid_protocols:
            raise ValueError(f"无效的协议: {protocol}，必须是 {', '.join(valid_protocols)}")

        # 验证端口号范围
        port = info.get("port")
        if port is not None:
            try:
                port_int = int(port)
                if port_int < 1 or port_int > 65535:
                    raise ValueError(f"端口号超出范围: {port_int}，必须在1-65535之间")
            except (ValueError, TypeError):
                if port != "null":  # null是允许的
                    raise ValueError(f"无效的端口号格式: {port}")

        # 验证故障类型
        valid_fault_types = ["connectivity", "port_unreachable", "slow", "dns"]
        fault_type = info.get("fault_type", "").lower()
        if fault_type not in valid_fault_types:
            raise ValueError(f"无效的故障类型: {fault_type}，必须是 {', '.join(valid_fault_types)}")

    def _auto_fix_info(self, info: Dict, user_input: str) -> Dict:
        """
        自动修复常见问题

        Args:
            info: 提取的信息字典
            user_input: 原始用户输入

        Returns:
            修复后的信息字典
        """
        # 服务名称到端口的映射
        service_port_map = {
            "http": 80,
            "https": 443,
            "mysql": 3306,
            "redis": 6379,
            "ssh": 22,
            "postgresql": 5432,
            "postgres": 5432,
            "mongodb": 27017,
            "ftp": 21,
            "smtp": 25,
            "dns": 53,
            "telnet": 23
        }

        # 如果端口为null，尝试从服务名称推断
        if info.get("port") is None or info.get("port") == "null":
            user_input_lower = user_input.lower()
            for service, port in service_port_map.items():
                if service in user_input_lower:
                    info["port"] = port
                    break

        # 协议拼写修正
        protocol = info.get("protocol", "").lower()
        protocol_fix_map = {
            "tcp/ip": "tcp",
            "icmpv4": "icmp",
            "ping": "icmp",
            "http": "tcp",
            "https": "tcp"
        }
        if protocol in protocol_fix_map:
            info["protocol"] = protocol_fix_map[protocol]

        # 如果source或target中包含IP地址，提取出来
        source = info.get("source", "")
        target = info.get("target", "")

        # 提取括号中的IP地址（如"app-01(10.0.1.5)"）
        source_ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', source)
        if source_ip_match:
            info["source"] = source_ip_match.group(1)

        target_ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', target)
        if target_ip_match:
            info["target"] = target_ip_match.group(1)

        return info

    def _parse_protocol(self, protocol_str: str) -> Protocol:
        """解析协议字符串"""
        protocol_str = protocol_str.lower()
        if protocol_str == "icmp":
            return Protocol.ICMP
        elif protocol_str == "udp":
            return Protocol.UDP
        else:
            return Protocol.TCP

    def _parse_fault_type(self, fault_type_str: str) -> FaultType:
        """解析故障类型字符串"""
        fault_type_str = fault_type_str.lower()
        if fault_type_str == "connectivity":
            return FaultType.CONNECTIVITY
        elif fault_type_str == "slow":
            return FaultType.SLOW
        elif fault_type_str == "dns":
            return FaultType.DNS
        else:
            return FaultType.PORT_UNREACHABLE

    def _fallback_rule_based_parse(self, user_input: str, task_id: str) -> DiagnosticTask:
        """
        回退到规则解析（当LLM失败时）

        Args:
            user_input: 用户输入
            task_id: 任务ID

        Returns:
            DiagnosticTask对象
        """
        # 简单的规则解析
        if "端口" in user_input or "telnet" in user_input.lower():
            fault_type = FaultType.PORT_UNREACHABLE
            protocol = Protocol.TCP
        elif "ping" in user_input.lower() or "连通" in user_input:
            fault_type = FaultType.CONNECTIVITY
            protocol = Protocol.ICMP
        else:
            fault_type = FaultType.PORT_UNREACHABLE
            protocol = Protocol.TCP

        # 提取主机名（简化版）
        parts = user_input.replace("到", " ").replace("端口", " ").replace("不通", "").strip().split()

        source = parts[0] if len(parts) > 0 else "unknown_source"
        target = parts[1] if len(parts) > 1 else "unknown_target"

        # 提取端口号
        port = None
        for part in parts:
            if part.isdigit():
                port = int(part)
                break

        return DiagnosticTask(
            task_id=task_id,
            user_input=user_input,
            source=source,
            target=target,
            protocol=protocol,
            fault_type=fault_type,
            port=port
        )
