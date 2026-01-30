# 命令输出解析器详细设计

**文档版本**: v1.0
**创建日期**: 2026-01-13
**作者**: 技术设计团队

---

## 1. 概述

本文档定义了netOpsAgent中所有命令输出解析器的详细逻辑。每个解析器负责从特定命令的stdout/stderr中提取结构化信息，供后续决策使用。

### 1.1 设计原则

- **鲁棒性优先**: 解析器必须能处理各种异常输出（空输出、格式错误、多厂商差异）
- **正则表达式 + 规则**: 优先使用正则表达式，复杂场景使用规则引擎
- **返回结构化数据**: 所有解析器返回Python dataclass或dict，不返回原始字符串
- **错误处理**: 解析失败时返回`ParseError`，带明确的错误原因
- **可测试性**: 每个解析器独立，易于单元测试

---

## 2. 核心解析器设计

### 2.1 detect_telnet_error_type()

**功能**: 判断telnet失败是Connection Refused还是Connection Timeout

**输入**:
```python
@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
```

**输出**:
```python
@dataclass
class TelnetErrorType:
    error_type: str  # "refused" | "timeout" | "unknown"
    confidence: float  # 0-1
    raw_output: str
```

**伪代码实现**:

```python
import re

def detect_telnet_error_type(result: CommandResult) -> TelnetErrorType:
    """
    解析telnet命令的失败类型

    示例输入:
    - stderr: "Connection refused"
    - stderr: "Connection timed out"
    - stderr: "Temporary failure in name resolution"

    返回:
    - refused: 网络通，端口未监听
    - timeout: 网络不通或防火墙阻断
    - unknown: 无法判断（如DNS解析失败）
    """
    combined_output = result.stdout + result.stderr

    # 规则1: Connection refused 或 Connection reset by peer
    refused_patterns = [
        r"connection refused",
        r"connection reset by peer",
        r"no route to host",  # 某些情况下也表示refused
    ]
    for pattern in refused_patterns:
        if re.search(pattern, combined_output, re.IGNORECASE):
            return TelnetErrorType(
                error_type="refused",
                confidence=0.95,
                raw_output=combined_output
            )

    # 规则2: Timeout 相关
    timeout_patterns = [
        r"connection timed out",
        r"timeout",
        r"no response",
    ]
    for pattern in timeout_patterns:
        if re.search(pattern, combined_output, re.IGNORECASE):
            return TelnetErrorType(
                error_type="timeout",
                confidence=0.95,
                raw_output=combined_output
            )

    # 规则3: 使用bash的/dev/tcp测试的成功情况
    if result.exit_code == 0 and "SUCCESS" in combined_output:
        return TelnetErrorType(
            error_type="success",
            confidence=1.0,
            raw_output=combined_output
        )

    # 规则4: 未知错误（如DNS解析失败）
    return TelnetErrorType(
        error_type="unknown",
        confidence=0.5,
        raw_output=combined_output
    )


# 单元测试用例
def test_detect_telnet_error_type():
    # Case 1: Connection refused
    result1 = CommandResult(
        stdout="",
        stderr="telnet: Unable to connect to remote host: Connection refused",
        exit_code=1
    )
    assert detect_telnet_error_type(result1).error_type == "refused"

    # Case 2: Connection timeout
    result2 = CommandResult(
        stdout="",
        stderr="telnet: Unable to connect to remote host: Connection timed out",
        exit_code=1
    )
    assert detect_telnet_error_type(result2).error_type == "timeout"

    # Case 3: 使用bash /dev/tcp成功
    result3 = CommandResult(
        stdout="SUCCESS",
        stderr="",
        exit_code=0
    )
    assert detect_telnet_error_type(result3).error_type == "success"
```

---

### 2.2 check_port_listening()

**功能**: 解析`ss -tunlp`或`netstat`输出，判断指定端口是否在监听

**输入**:
```python
result: CommandResult  # ss命令的执行结果
port: int              # 要检查的端口号
```

**输出**:
```python
@dataclass
class PortListeningStatus:
    is_listening: bool
    process_name: Optional[str]  # 监听该端口的进程名
    pid: Optional[int]           # 进程ID
    bind_address: str            # 绑定的地址（0.0.0.0 或特定IP）
```

**伪代码实现**:

```python
import re

def check_port_listening(result: CommandResult, port: int) -> PortListeningStatus:
    """
    解析ss命令输出，检查端口是否在监听

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


# 单元测试用例
def test_check_port_listening():
    # Case 1: 端口正在监听
    result1 = CommandResult(
        stdout='tcp   LISTEN  0   128   *:80   *:*   users:(("nginx",pid=1234,fd=6))',
        stderr="",
        exit_code=0
    )
    status1 = check_port_listening(result1, 80)
    assert status1.is_listening == True
    assert status1.process_name == "nginx"
    assert status1.pid == 1234

    # Case 2: 端口未监听
    result2 = CommandResult(
        stdout='tcp   LISTEN  0   128   *:443   *:*   users:(("nginx",pid=1234,fd=6))',
        stderr="",
        exit_code=0
    )
    status2 = check_port_listening(result2, 80)
    assert status2.is_listening == False

    # Case 3: 只监听127.0.0.1（本地）
    result3 = CommandResult(
        stdout='tcp   LISTEN  0   128   127.0.0.1:3306   *:*   users:(("mysqld",pid=5678,fd=10))',
        stderr="",
        exit_code=0
    )
    status3 = check_port_listening(result3, 3306)
    assert status3.is_listening == True
    assert status3.bind_address == "127.0.0.1"
```

---

### 2.3 parse_ping_result()

**功能**: 解析ping命令输出，提取丢包率、延迟等信息

**输入**:
```python
result: CommandResult
```

**输出**:
```python
@dataclass
class PingResult:
    packets_transmitted: int
    packets_received: int
    packet_loss_percent: float
    rtt_min: Optional[float]  # ms
    rtt_avg: Optional[float]  # ms
    rtt_max: Optional[float]  # ms
    is_reachable: bool
```

**伪代码实现**:

```python
import re

def parse_ping_result(result: CommandResult) -> PingResult:
    """
    解析ping命令输出

    示例输入:
    PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data.
    64 bytes from 10.0.2.20: icmp_seq=1 ttl=64 time=0.123 ms
    64 bytes from 10.0.2.20: icmp_seq=2 ttl=64 time=0.089 ms

    --- 10.0.2.20 ping statistics ---
    4 packets transmitted, 4 received, 0% packet loss, time 3001ms
    rtt min/avg/max/mdev = 0.089/0.125/0.234/0.052 ms
    """
    stdout = result.stdout

    # 解析丢包率行
    # 格式: 4 packets transmitted, 4 received, 0% packet loss
    loss_pattern = r"(\d+) packets transmitted, (\d+) received, ([\d.]+)% packet loss"
    loss_match = re.search(loss_pattern, stdout)

    if not loss_match:
        # 解析失败，返回默认值
        return PingResult(
            packets_transmitted=0,
            packets_received=0,
            packet_loss_percent=100.0,
            rtt_min=None,
            rtt_avg=None,
            rtt_max=None,
            is_reachable=False
        )

    transmitted = int(loss_match.group(1))
    received = int(loss_match.group(2))
    loss_percent = float(loss_match.group(3))

    # 解析RTT行（如果有）
    # 格式: rtt min/avg/max/mdev = 0.089/0.125/0.234/0.052 ms
    rtt_pattern = r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)"
    rtt_match = re.search(rtt_pattern, stdout)

    if rtt_match:
        rtt_min = float(rtt_match.group(1))
        rtt_avg = float(rtt_match.group(2))
        rtt_max = float(rtt_match.group(3))
    else:
        rtt_min = rtt_avg = rtt_max = None

    return PingResult(
        packets_transmitted=transmitted,
        packets_received=received,
        packet_loss_percent=loss_percent,
        rtt_min=rtt_min,
        rtt_avg=rtt_avg,
        rtt_max=rtt_max,
        is_reachable=(loss_percent < 100.0)
    )


# 单元测试用例
def test_parse_ping_result():
    # Case 1: Ping成功
    result1 = CommandResult(
        stdout="""PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data.
64 bytes from 10.0.2.20: icmp_seq=1 ttl=64 time=0.123 ms

--- 10.0.2.20 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3001ms
rtt min/avg/max/mdev = 0.089/0.125/0.234/0.052 ms""",
        stderr="",
        exit_code=0
    )
    ping1 = parse_ping_result(result1)
    assert ping1.is_reachable == True
    assert ping1.packet_loss_percent == 0.0
    assert ping1.rtt_avg == 0.125

    # Case 2: Ping失败（100%丢包）
    result2 = CommandResult(
        stdout="""PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data.

--- 10.0.2.20 ping statistics ---
4 packets transmitted, 0 received, 100% packet loss, time 3001ms""",
        stderr="",
        exit_code=1
    )
    ping2 = parse_ping_result(result2)
    assert ping2.is_reachable == False
    assert ping2.packet_loss_percent == 100.0
```

---

### 2.4 parse_iptables_rules()

**功能**: 解析iptables规则，识别是否有阻断特定端口的规则

**输入**:
```python
result: CommandResult
port: int
chain: str  # "INPUT" | "OUTPUT"
```

**输出**:
```python
@dataclass
class IptablesRuleMatch:
    has_blocking_rule: bool
    rule_action: Optional[str]  # "DROP" | "REJECT" | "ACCEPT"
    rule_line: Optional[str]    # 匹配的规则原始行
    policy: str                  # 链的默认策略 (DROP/ACCEPT)
```

**伪代码实现**:

```python
import re

def parse_iptables_rules(result: CommandResult, port: int, chain: str = "INPUT") -> IptablesRuleMatch:
    """
    解析iptables输出，检查是否有阻断特定端口的规则

    示例输入:
    Chain INPUT (policy DROP)
    pkts bytes target  prot opt in  out  source      destination
    100  6000  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:22
      0     0  DROP    tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:80

    解析逻辑:
    1. 提取链的默认策略（policy）
    2. 查找匹配目标端口的规则
    3. 判断是DROP/REJECT还是ACCEPT
    """
    stdout = result.stdout

    # 提取默认策略
    # 格式: Chain INPUT (policy DROP)
    policy_pattern = rf"Chain {chain} \(policy (DROP|ACCEPT|REJECT)\)"
    policy_match = re.search(policy_pattern, stdout, re.IGNORECASE)
    policy = policy_match.group(1).upper() if policy_match else "ACCEPT"

    # 查找匹配端口的规则
    # 格式: 0  0  DROP  tcp  --  *  *  0.0.0.0/0  0.0.0.0/0  tcp dpt:80
    rule_pattern = rf"(DROP|REJECT|ACCEPT)\s+tcp\s+--.*?tcp dpt:{port}"
    rule_match = re.search(rule_pattern, stdout, re.IGNORECASE | re.MULTILINE)

    if rule_match:
        action = rule_match.group(1).upper()
        rule_line = rule_match.group(0)

        # 有明确的DROP或REJECT规则
        if action in ["DROP", "REJECT"]:
            return IptablesRuleMatch(
                has_blocking_rule=True,
                rule_action=action,
                rule_line=rule_line,
                policy=policy
            )
        # 有ACCEPT规则，说明端口被放行
        elif action == "ACCEPT":
            return IptablesRuleMatch(
                has_blocking_rule=False,
                rule_action=action,
                rule_line=rule_line,
                policy=policy
            )

    # 没有明确规则，判断默认策略
    if policy == "DROP":
        return IptablesRuleMatch(
            has_blocking_rule=True,
            rule_action=policy,
            rule_line=None,
            policy=policy
        )
    else:
        return IptablesRuleMatch(
            has_blocking_rule=False,
            rule_action=None,
            rule_line=None,
            policy=policy
        )


# 单元测试用例
def test_parse_iptables_rules():
    # Case 1: 有明确的DROP规则
    result1 = CommandResult(
        stdout="""Chain INPUT (policy ACCEPT)
pkts bytes target  prot opt in  out  source      destination
  0     0  DROP    tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:80""",
        stderr="",
        exit_code=0
    )
    match1 = parse_iptables_rules(result1, 80, "INPUT")
    assert match1.has_blocking_rule == True
    assert match1.rule_action == "DROP"

    # Case 2: 有ACCEPT规则
    result2 = CommandResult(
        stdout="""Chain INPUT (policy DROP)
pkts bytes target  prot opt in  out  source      destination
100  6000  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:80""",
        stderr="",
        exit_code=0
    )
    match2 = parse_iptables_rules(result2, 80, "INPUT")
    assert match2.has_blocking_rule == False
    assert match2.rule_action == "ACCEPT"

    # Case 3: 无明确规则，默认策略DROP
    result3 = CommandResult(
        stdout="""Chain INPUT (policy DROP)
pkts bytes target  prot opt in  out  source      destination
100  6000  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:22""",
        stderr="",
        exit_code=0
    )
    match3 = parse_iptables_rules(result3, 80, "INPUT")
    assert match3.has_blocking_rule == True
    assert match3.policy == "DROP"
```

---

### 2.5 parse_traceroute_output()

**功能**: 解析traceroute输出，识别网络路径和断点位置

**输入**:
```python
result: CommandResult
```

**输出**:
```python
@dataclass
class TracerouteHop:
    hop_number: int
    ip_address: Optional[str]  # None表示超时（* * *）
    hostname: Optional[str]
    rtt_ms: Optional[float]    # 第一次RTT
    is_timeout: bool

@dataclass
class TracerouteResult:
    target_ip: str
    hops: List[TracerouteHop]
    last_reachable_hop: Optional[TracerouteHop]
    first_timeout_hop: Optional[int]  # 第一个超时的hop编号
    is_complete: bool  # 是否到达目标
```

**伪代码实现**:

```python
import re
from typing import List, Optional

def parse_traceroute_output(result: CommandResult) -> TracerouteResult:
    """
    解析traceroute输出

    示例输入:
    traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
     1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
     2  10.10.1.1 (10.10.1.1)  1.234 ms  1.123 ms  1.089 ms
     3  * * *
     4  * * *
     5  * * *

    解析逻辑:
    1. 提取目标IP
    2. 逐行解析每一跳
    3. 识别第一个超时的hop
    4. 记录最后一个可达的hop
    """
    stdout = result.stdout

    # 提取目标IP
    # 格式: traceroute to 10.0.2.20 (10.0.2.20)
    target_pattern = r"traceroute to ([\d.]+)"
    target_match = re.search(target_pattern, stdout)
    target_ip = target_match.group(1) if target_match else ""

    # 解析每一跳
    hops: List[TracerouteHop] = []
    last_reachable_hop: Optional[TracerouteHop] = None
    first_timeout_hop: Optional[int] = None

    # 格式: 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
    hop_pattern = r"^\s*(\d+)\s+([\d.]+)\s+\(([\d.]+)\)\s+([\d.]+)\s+ms"
    # 超时格式: 3  * * *
    timeout_pattern = r"^\s*(\d+)\s+\*\s+\*\s+\*"

    lines = stdout.split('\n')
    for line in lines:
        # 解析正常hop
        hop_match = re.match(hop_pattern, line)
        if hop_match:
            hop_number = int(hop_match.group(1))
            ip_address = hop_match.group(2)
            hostname = hop_match.group(3)
            rtt_ms = float(hop_match.group(4))

            hop = TracerouteHop(
                hop_number=hop_number,
                ip_address=ip_address,
                hostname=hostname,
                rtt_ms=rtt_ms,
                is_timeout=False
            )
            hops.append(hop)
            last_reachable_hop = hop
            continue

        # 解析超时hop
        timeout_match = re.match(timeout_pattern, line)
        if timeout_match:
            hop_number = int(timeout_match.group(1))
            hop = TracerouteHop(
                hop_number=hop_number,
                ip_address=None,
                hostname=None,
                rtt_ms=None,
                is_timeout=True
            )
            hops.append(hop)

            # 记录第一个超时的hop
            if first_timeout_hop is None:
                first_timeout_hop = hop_number

    # 判断是否到达目标
    is_complete = False
    if last_reachable_hop and last_reachable_hop.ip_address == target_ip:
        is_complete = True

    return TracerouteResult(
        target_ip=target_ip,
        hops=hops,
        last_reachable_hop=last_reachable_hop,
        first_timeout_hop=first_timeout_hop,
        is_complete=is_complete
    )


# 单元测试用例
def test_parse_traceroute_output():
    # Case 1: 正常完成
    result1 = CommandResult(
        stdout="""traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
 2  10.0.2.20 (10.0.2.20)  1.234 ms  1.123 ms  1.089 ms""",
        stderr="",
        exit_code=0
    )
    tr1 = parse_traceroute_output(result1)
    assert tr1.is_complete == True
    assert len(tr1.hops) == 2
    assert tr1.first_timeout_hop is None

    # Case 2: 中途断开
    result2 = CommandResult(
        stdout="""traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
 2  10.10.1.1 (10.10.1.1)  1.234 ms  1.123 ms  1.089 ms
 3  * * *
 4  * * *""",
        stderr="",
        exit_code=0
    )
    tr2 = parse_traceroute_output(result2)
    assert tr2.is_complete == False
    assert tr2.last_reachable_hop.ip_address == "10.10.1.1"
    assert tr2.first_timeout_hop == 3
```

---

### 2.6 identify_failed_hop()

**功能**: 根据traceroute结果和CMDB拓扑信息，识别故障节点的类型和名称

**输入**:
```python
traceroute_result: TracerouteResult
topology: NetworkPath  # 从CMDB查询的拓扑路径
```

**输出**:
```python
@dataclass
class FailedHopIdentification:
    failed_hop_number: int
    failed_device_name: Optional[str]  # 从CMDB推断的设备名
    failed_device_type: str  # "leaf_switch" | "spine_switch" | "server" | "unknown"
    last_reachable_ip: Optional[str]
    confidence: float
    reasoning: str  # 推断理由
```

**伪代码实现**:

```python
def identify_failed_hop(
    traceroute_result: TracerouteResult,
    topology: NetworkPath
) -> FailedHopIdentification:
    """
    根据traceroute结果和CMDB拓扑推断故障节点

    推断逻辑:
    1. 找到最后可达的hop IP
    2. 在CMDB拓扑中查找该IP对应的设备
    3. 推断下一个节点（超时的hop）是什么设备
    4. 根据Spine-Leaf架构规则推断设备类型

    示例:
    - 最后可达: 10.10.1.1 (spine-01)
    - 第一个超时: hop 3
    - 拓扑路径: [leaf-01, spine-01, leaf-02, server2]
    - 推断: leaf-02故障
    """
    if not traceroute_result.first_timeout_hop:
        # 没有超时，网络正常
        return FailedHopIdentification(
            failed_hop_number=0,
            failed_device_name=None,
            failed_device_type="none",
            last_reachable_ip=None,
            confidence=1.0,
            reasoning="Traceroute完成，未发现超时节点"
        )

    last_reachable_ip = None
    if traceroute_result.last_reachable_hop:
        last_reachable_ip = traceroute_result.last_reachable_hop.ip_address

    # 在拓扑中查找最后可达IP对应的设备
    last_reachable_device = None
    for i, device in enumerate(topology.path):
        device_info = topology.device_details.get(device)
        if device_info and device_info.get('ip') == last_reachable_ip:
            last_reachable_device = device
            # 推断下一个设备
            if i + 1 < len(topology.path):
                failed_device = topology.path[i + 1]
                failed_device_info = topology.device_details.get(failed_device)

                # 判断设备类型
                device_type = "unknown"
                if failed_device_info:
                    if 'leaf' in failed_device.lower():
                        device_type = "leaf_switch"
                    elif 'spine' in failed_device.lower():
                        device_type = "spine_switch"
                    elif 'server' in failed_device.lower():
                        device_type = "server"

                return FailedHopIdentification(
                    failed_hop_number=traceroute_result.first_timeout_hop,
                    failed_device_name=failed_device,
                    failed_device_type=device_type,
                    last_reachable_ip=last_reachable_ip,
                    confidence=0.85,
                    reasoning=f"基于CMDB拓扑，最后可达设备{last_reachable_device}，下一跳应为{failed_device}"
                )

    # 无法匹配CMDB拓扑，返回未知
    return FailedHopIdentification(
        failed_hop_number=traceroute_result.first_timeout_hop,
        failed_device_name=None,
        failed_device_type="unknown",
        last_reachable_ip=last_reachable_ip,
        confidence=0.5,
        reasoning="无法在CMDB拓扑中找到匹配的设备，建议手动排查"
    )


# 单元测试用例
def test_identify_failed_hop():
    # 构造Mock CMDB拓扑
    topology = NetworkPath(
        path=["server1", "leaf-01", "spine-01", "leaf-02", "server2"],
        device_details={
            "leaf-01": {"ip": "10.0.1.1", "type": "leaf_switch"},
            "spine-01": {"ip": "10.10.1.1", "type": "spine_switch"},
            "leaf-02": {"ip": "10.0.2.1", "type": "leaf_switch"},
        }
    )

    # 构造traceroute结果（在spine-01后断开）
    tr_result = TracerouteResult(
        target_ip="10.0.2.20",
        hops=[
            TracerouteHop(1, "10.0.1.1", "10.0.1.1", 0.5, False),
            TracerouteHop(2, "10.10.1.1", "10.10.1.1", 1.2, False),
            TracerouteHop(3, None, None, None, True),
        ],
        last_reachable_hop=TracerouteHop(2, "10.10.1.1", "10.10.1.1", 1.2, False),
        first_timeout_hop=3,
        is_complete=False
    )

    result = identify_failed_hop(tr_result, topology)
    assert result.failed_device_name == "leaf-02"
    assert result.failed_device_type == "leaf_switch"
    assert result.confidence >= 0.8
```

---

## 3. 辅助工具函数

### 3.1 extract_ip_from_string()

```python
import re

def extract_ip_from_string(text: str) -> Optional[str]:
    """
    从文本中提取IPv4地址
    """
    pattern = r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
    match = re.search(pattern, text)
    return match.group(1) if match else None
```

### 3.2 normalize_device_name()

```python
def normalize_device_name(name: str) -> str:
    """
    规范化设备名称（去除空格、统一大小写）
    """
    return name.strip().lower()
```

---

## 4. 解析器集成

所有解析器通过`ParserRegistry`统一管理：

```python
class ParserRegistry:
    """
    解析器注册表，方便测试和扩展
    """
    def __init__(self):
        self.parsers = {
            'telnet_error': detect_telnet_error_type,
            'port_listening': check_port_listening,
            'ping_result': parse_ping_result,
            'iptables_rules': parse_iptables_rules,
            'traceroute': parse_traceroute_output,
            'failed_hop': identify_failed_hop,
        }

    def get_parser(self, name: str):
        return self.parsers.get(name)

    def register_parser(self, name: str, parser_func):
        """允许动态注册新解析器（用于扩展）"""
        self.parsers[name] = parser_func
```

---

## 5. 错误处理策略

所有解析器遵循统一的错误处理原则：

1. **解析失败不崩溃**: 返回默认值或低置信度结果
2. **记录原始输出**: 所有结果包含`raw_output`字段，便于调试
3. **置信度标注**: 使用`confidence`字段表示解析结果的可信度（0-1）
4. **详细日志**: 使用structlog记录解析过程

```python
import structlog

logger = structlog.get_logger()

def safe_parse(parser_func):
    """解析器装饰器，统一错误处理"""
    def wrapper(*args, **kwargs):
        try:
            result = parser_func(*args, **kwargs)
            logger.info(f"{parser_func.__name__} success", confidence=result.confidence)
            return result
        except Exception as e:
            logger.error(f"{parser_func.__name__} failed", error=str(e))
            # 返回默认的失败结果
            return create_default_result(parser_func)
    return wrapper
```

---

## 6. 下一步工作

- [ ] 实现所有解析器的单元测试（覆盖率 ≥ 90%）
- [ ] 准备真实命令输出样本（收集10-20个真实案例）
- [ ] 编写集成测试（端到端验证）
- [ ] 性能优化（正则表达式编译缓存）
- [ ] 扩展性设计（支持多厂商命令输出格式差异）

---

**审核清单**：

- [ ] 解析逻辑是否符合实际运维场景？
- [ ] 正则表达式是否覆盖了常见的命令输出格式？
- [ ] 错误处理是否足够鲁棒？
- [ ] 单元测试用例是否覆盖了边缘情况？
- [ ] 是否有遗漏的关键解析器？
