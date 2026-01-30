# netOpsAgent 产品规格说明书

**版本**: v1.0
**创建日期**: 2026-01-05
**作者**: 产品设计团队
**状态**: Draft

---

## 1. 项目概述

### 1.1 项目背景
在大规模数据中心环境（几千台服务器，Spine-Leaf架构）中，网络故障排查是一项高频、繁琐且耗时的工作。目前网络运维人员需要手动登录多个设备、执行重复性命令、分析日志，导致故障定位时间长（数小时），影响业务稳定性。

### 1.2 核心痛点
- **排查耗时长**：从接到报障到定位根因，平均需要2-4小时
- **步骤繁琐**：需要在多台设备间切换，执行大量重复命令
- **经验依赖**：新手难以快速定位问题，依赖资深工程师
- **缺乏自动化**：80%的常见故障（连通性、端口不可达、DNS）排查流程固定但仍需人工执行

### 1.3 项目目标
构建一个智能网络故障排查Agent，通过结合**固定流程引擎**和**AI推理能力**，实现：
- 将故障排查时间从数小时缩短至5-10分钟
- 自动化处理80%的常见网络故障
- 降低对人员技能要求，初级运维也能快速定位问题
- 生成结构化排查报告，便于审计和知识沉淀

### 1.4 目标用户
- **主要用户**：数据中心网络运维人员（具备基础网络知识，能看懂tcpdump）
- **技能水平**：初级到中级（不需要是网络专家）
- **使用场景**：接到用户报障后，通过聊天机器人输入故障描述，获得诊断结果和修复建议

---

## 2. 系统架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                       用户层                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Web Chat UI (Phase 1)                   │   │
│  │              - 浏览器聊天界面                         │   │
│  │              - SSE 流式响应                           │   │
│  └──────────────────────────┬───────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Core (Python)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. NLU Module (自然语言理解)                         │   │
│  │     - LLM解析用户输入 → 结构化任务                   │   │
│  │     - 提取: 源/目标IP、协议、端口、故障类型          │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  2. Task Planner (任务规划器)                        │   │
│  │     - 固定流程引擎 (Rule-based, Phase 1)             │   │
│  │     - AI推理兜底 (LLM-driven, Phase 2)               │   │
│  │     - 生成执行计划 (命令序列 + 决策树)               │   │
│  │     - 支持快速模式和深度模式                         │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  3. Executor (执行引擎)                              │   │
│  │     - 命令白名单验证器                               │   │
│  │     - 自动化平台Client (调用远程命令)                │   │
│  │     - CMDB Client (查询拓扑/设备信息)                │   │
│  │     - 结果解析器 (正则/结构化提取)                   │   │
│  │     - 异步任务管理器 (支持长时间排查)                │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  4. Analyzer (结果分析器)                            │   │
│  │     - 汇总执行结果                                   │   │
│  │     - 根因推断 (基于规则 + LLM)                      │   │
│  │     - 生成修复建议                                   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  5. Response Generator (响应生成器)                  │   │
│  │     - JSON 格式诊断结果                              │   │
│  │     - SSE 实时推送诊断进度                           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────┬───────────────────┬───────────────────────┘
                  │                   │
                  ▼                   ▼
    ┌──────────────────────┐   ┌─────────────────────┐
    │  自动化平台 API      │   │   CMDB API          │
    │  - 统一命令执行接口  │   │  - 设备信息         │
    │  - 已适配多厂商设备  │   │  - 网络拓扑(含Pod)  │
    │  - 凭证管理          │   │  - Leaf/Spine映射   │
    │  - 返回结构化结果    │   │  - 交换机管理IP     │
    └──────────┬───────────┘   └─────────────────────┘
               │
               ▼
    ┌──────────────────────────────────────┐
    │  数据中心基础设施                     │
    │  - 服务器 (物理机/虚拟机/K8s Pod)     │
    │  - 网络设备 (Spine/Leaf交换机)        │
    │  - 抓包探针 (已有pcap数据)            │
    └──────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **开发语言** | Python 3.10+ | 主力开发语言 |
| **AI框架** | LangChain | LLM编排、Agent框架 |
| **LLM** | Claude (Anthropic API) | 意图识别、推理、分析 |
| **并发执行** | asyncio + aiohttp | 异步命令执行 |
| **数据存储** | SQLite | 存储排查历史 |
| **配置管理** | YAML | 白名单配置、流程定义 |
| **日志** | structlog | 结构化日志 |
| **Web框架** | FastAPI | RESTful API + SSE 流式推送 |
| **前端** | HTML/CSS/JS | 浏览器聊天界面 |

---

## 3. 核心模块详细设计

### 3.1 NLU模块 (自然语言理解)

**职责**：将用户的自然语言输入转换为结构化任务

**输入示例**：

- "server1到server2 ping不通"
- "10.0.1.10 telnet 10.0.2.20的80端口失败"
- "测试环境的web01访问db01很慢"

**输出结构**：
```python
class DiagnosticTask:
    task_id: str              # 唯一任务ID
    source: str               # 源主机 (IP/主机名)
    target: str               # 目标主机 (IP/主机名)
    protocol: str             # 协议: icmp, tcp, udp
    port: Optional[int]       # 端口号 (如果是TCP/UDP)
    fault_type: str           # 故障类型: connectivity, port_unreachable, slow, dns
    context: Dict[str, Any]   # 额外上下文信息
```

**实现方式**：
1. 使用LLM (Claude) + Few-shot prompt提取结构化信息
2. Prompt工程示例：
```python
EXTRACTION_PROMPT = """
你是一个网络故障排查专家。请从用户描述中提取关键信息。

用户输入: {user_input}

请提取以下信息（JSON格式）:
{{
  "source": "源主机IP或主机名",
  "target": "目标主机IP或主机名",
  "protocol": "icmp/tcp/udp",
  "port": 端口号(数字，如果是ping则为null),
  "fault_type": "connectivity/port_unreachable/slow/dns"
}}

示例：
输入: "server1到server2 ping不通"
输出: {{"source": "server1", "target": "server2", "protocol": "icmp", "port": null, "fault_type": "connectivity"}}
"""
```

### 3.2 Task Planner (任务规划器)

**职责**：根据故障类型生成排查计划（固定流程 + AI推理）

#### 3.2.1 固定流程引擎 (Phase 1核心)

针对常见故障，定义**决策树**流程：

**故障类型1: 连通性故障 (connectivity)**

```yaml
# config/workflows/connectivity.yaml
name: "连通性排查流程（优化版）"
fault_type: connectivity
steps:
  - step: 1
    name: "验证主机存在性"
    action: query_cmdb
    params:
      hosts: [source, target]
    success_next: 2
    fail_action: report_error
    fail_message: "主机不存在于CMDB"

  - step: 2
    name: "基础连通性测试（ping）"
    action: execute_command
    command_template: ping
    params:
      target: "{{ target }}"
      count: 4
      timeout: 5
    on_host: "{{ source }}"
    success_condition: "packet_loss < 100%"
    success_next: report_success
    fail_next: 3

  - step: 3
    name: "检查目标是否禁ping"
    action: execute_command
    command_template: check_icmp_disabled
    on_host: "{{ target }}"
    parse_output: is_ping_disabled
    success_next: 4
    fail_next: 5
    context: "部分服务器可能配置禁止ICMP响应"

  - step: 4
    name: "目标禁ping，测试网关连通性"
    action: execute_command
    command_template: ping_gateway
    params:
      target_ip: "{{ target_ip }}"
    on_host: "{{ source }}"
    parse_output: extract_gateway_and_ping
    success_condition: "gateway_reachable == true"
    success_next: 6
    fail_next: 5
    context: "如果网关可达但目标不可达，说明目标服务器本身有问题"

  - step: 5
    name: "检查源主机路由配置"
    action: execute_command
    command_template: ip_route_get
    params:
      target_ip: "{{ target_ip }}"
    on_host: "{{ source }}"
    success_condition: "route_exists == true"
    success_next: 7
    fail_next: report_no_route
    fail_context: "源主机无到目标的路由"

  - step: 6
    name: "网关通但目标不通（禁ping场景），检查目标服务器"
    action: parallel_execute
    commands:
      - name: "检查目标网络配置"
        command_template: ip_addr_show
        on_host: "{{ target }}"
      - name: "检查目标路由表"
        command_template: ip_route_show
        on_host: "{{ target }}"
      - name: "检查目标防火墙"
        command_template: iptables_list
        on_host: "{{ target }}"
    next: analyze_target_issue
    context: "网关可达说明网络路径正常，问题在目标服务器"

  - step: 7
    name: "路由追踪定位断点"
    action: execute_command
    command_template: traceroute
    params:
      target: "{{ target }}"
      max_hops: 30
      timeout: 3
    on_host: "{{ source }}"
    parse_output: extract_broken_hop
    success_next: 8
    context: "定位网络路径中的故障节点"

  - step: 8
    name: "分析traceroute断点位置"
    action: analyze_traceroute_result
    parse_output: identify_failed_hop
    conditions:
      - if: "failed_hop_type == 'leaf_switch'"
        next: 9
      - if: "failed_hop_type == 'spine_switch'"
        next: 10
      - if: "failed_hop_type == 'source_firewall'"
        next: 11
      - if: "failed_hop_type == 'target_firewall'"
        next: 12
      - if: "failed_hop_type == 'unknown'"
        next: fallback_to_ai

  - step: 9
    name: "排查Leaf交换机路由策略"
    action: execute_command
    command_template: check_switch_routes
    on_host: "{{ failed_leaf_switch }}"
    parse_output: check_routing_policy
    next: analyze_results

  - step: 10
    name: "排查Spine交换机路由策略"
    action: execute_command
    command_template: check_switch_routes
    on_host: "{{ failed_spine_switch }}"
    parse_output: check_routing_policy
    next: analyze_results

  - step: 11
    name: "检查源主机防火墙规则"
    action: execute_command
    command_template: iptables_list
    on_host: "{{ source }}"
    parse_output: check_icmp_blocked
    next: analyze_results

  - step: 12
    name: "检查目标主机防火墙规则"
    action: execute_command
    command_template: iptables_list
    on_host: "{{ target }}"
    parse_output: check_icmp_blocked
    next: analyze_results

  - step: fallback_to_ai
    name: "AI推理兜底"
    action: invoke_llm_reasoning
    context: all_previous_results
```

**故障类型2: 端口不可达 (port_unreachable)**

```yaml
name: "端口可达性排查（基于实际运维经验优化）"
fault_type: port_unreachable
steps:
  - step: 1
    name: "验证主机存在性"
    action: query_cmdb
    params:
      hosts: [source, target]
    success_next: 2
    fail_action: report_error
    fail_message: "主机不存在于CMDB"

  - step: 2
    name: "端口连通性测试（telnet）"
    action: execute_command
    command_template: telnet_test
    params:
      target: "{{ target }}"
      port: "{{ port }}"
      timeout: 5
    on_host: "{{ source }}"
    parse_output: detect_telnet_error_type  # 解析refused vs timeout
    success_next: report_success
    fail_next: 3

  - step: 3
    name: "判断telnet失败类型"
    action: branch_on_error_type
    conditions:
      - if: "error_type == 'connection_refused'"
        next: 4
        reason: "网络通但端口未监听，检查目标服务"
      - if: "error_type == 'timeout'"
        next: 5
        reason: "连接超时，需排查网络层或防火墙"

  - step: 4
    name: "检查目标端口监听（refused分支）"
    action: execute_command
    command_template: ss_listen
    params:
      port: "{{ port }}"
    on_host: "{{ target }}"
    parse_output: check_port_listening
    success_next: report_port_not_listening
    fail_next: report_service_not_running
    context: "Connection refused说明网络通，大概率是服务未启动或端口配置错误"

  - step: 5
    name: "基础连通性测试（timeout分支）"
    action: execute_command
    command_template: ping
    params:
      target: "{{ target }}"
      count: 4
      timeout: 5
    on_host: "{{ source }}"
    success_condition: "packet_loss < 100%"
    success_next: 6
    fail_next: 7

  - step: 6
    name: "ping通但端口不通，排查防火墙/安全组"
    action: parallel_execute
    commands:
      - name: "检查源主机出站防火墙"
        command_template: iptables_list_output
        on_host: "{{ source }}"
        parse_output: check_outbound_blocked
      - name: "检查目标主机入站防火墙"
        command_template: iptables_list_input
        params:
          port: "{{ port }}"
        on_host: "{{ target }}"
        parse_output: check_inbound_blocked
      - name: "检查目标端口监听状态"
        command_template: ss_listen
        params:
          port: "{{ port }}"
        on_host: "{{ target }}"
    next: analyze_firewall_results
    context: "大概率是防火墙或安全组策略问题"

  - step: 7
    name: "ping不通，检查目标是否禁ping"
    action: execute_command
    command_template: check_icmp_disabled
    on_host: "{{ target }}"
    parse_output: is_ping_disabled
    success_next: 8
    fail_next: 9
    context: "某些服务器配置禁止ICMP响应"

  - step: 8
    name: "目标禁ping，测试网关连通性"
    action: execute_command
    command_template: ping_gateway
    params:
      target_ip: "{{ target_ip }}"
    on_host: "{{ source }}"
    parse_output: extract_gateway_and_ping
    success_condition: "gateway_reachable == true"
    success_next: 10
    fail_next: 9
    context: "通过ping网关判断网络路径是否畅通"

  - step: 9
    name: "网关不通或目标不禁ping但ping不通，执行traceroute"
    action: execute_command
    command_template: traceroute
    params:
      target: "{{ target }}"
      max_hops: 30
      timeout: 3
    on_host: "{{ source }}"
    parse_output: extract_broken_hop
    success_next: 11
    context: "定位网络路径中的断点"

  - step: 10
    name: "网关通但目标不通，判断为目标服务器问题"
    action: parallel_execute
    commands:
      - name: "检查目标网络配置"
        command_template: ip_addr_show
        on_host: "{{ target }}"
      - name: "检查目标路由表"
        command_template: ip_route_show
        on_host: "{{ target }}"
      - name: "检查目标防火墙"
        command_template: iptables_list
        on_host: "{{ target }}"
    next: analyze_target_issue
    context: "网关可达说明网络路径正常，问题在目标服务器本身"

  - step: 11
    name: "分析traceroute断点，定位故障网络设备"
    action: analyze_traceroute_result
    parse_output: identify_failed_hop
    conditions:
      - if: "failed_hop_type == 'leaf_switch'"
        next: 12
      - if: "failed_hop_type == 'spine_switch'"
        next: 13
      - if: "failed_hop_type == 'unknown'"
        next: fallback_to_ai

  - step: 12
    name: "Leaf交换机路由策略排查"
    action: execute_command
    command_template: check_switch_routes
    on_host: "{{ failed_leaf_switch }}"
    parse_output: check_routing_policy
    next: analyze_results
    context: "登录故障Leaf交换机检查路由配置"

  - step: 13
    name: "Spine交换机路由策略排查"
    action: execute_command
    command_template: check_switch_routes
    on_host: "{{ failed_spine_switch }}"
    parse_output: check_routing_policy
    next: analyze_results
    context: "登录故障Spine交换机检查路由配置"

  - step: fallback_to_ai
    name: "AI推理兜底"
    action: invoke_llm_reasoning
    context: all_previous_results
```

#### 3.2.2 排障决策逻辑说明

**核心排障理念**：分层诊断、逐步缩小问题范围

##### 端口不可达排障决策树

```
用户报障: 服务器A(ip1)到服务器B(ip2)端口访问不通
                    ↓
┌───────────────────────────────────────────────────┐
│ Step 1: 登录服务器A执行 telnet ip2 port           │
└───────────┬────────────────────┬──────────────────┘
            │                    │
      [Connection Refused]  [Connection Timeout]
            │                    │
            ↓                    ↓
┌──────────────────────┐  ┌────────────────────────┐
│ 说明: 网络是通的      │  │ 说明: 网络层或防火墙   │
│ 结论: 端口未监听      │  │        可能有问题      │
└──────────┬───────────┘  └────────────┬───────────┘
            │                          │
            ↓                          ↓
┌──────────────────────┐  ┌────────────────────────┐
│ Step 2a: 登录服务器B │  │ Step 2b: 从服务器A     │
│ 执行 ss -tunlp       │  │ ping 服务器B的IP       │
│ 检查端口是否监听     │  └────────────┬───────────┘
└──────────┬───────────┘               │
            │                    ┌─────┴──────┐
            ↓                 [成功]      [失败]
      端口未监听→              │            │
      反馈用户网络通           ↓            ↓
      但服务端口没启动  ┌───────────────┐  ┌──────────────┐
                       │ Step 3a:      │  │ Step 3b:     │
                       │ 调用工具查询   │  │ 查询目标网关  │
                       │ 防火墙/安全组  │  │ 并ping网关   │
                       │ 策略          │  └──────┬───────┘
                       └───────────────┘         │
                              │            ┌──────┴──────┐
                              │        [网关通]    [网关不通]
                              │            │              │
                              │            ↓              │
                              │   目标服务器可能禁ping      │
                              │   需进一步验证             │
                              │                           ↓
                              │                  ┌──────────────┐
                              │                  │ Step 4:      │
                              └──────────────────→ traceroute   │
                                                 │ 定位断点     │
                                                 └──────┬───────┘
                                                        │
                                                        ↓
                                               ┌─────────────────┐
                                               │ Step 5: 分析断点│
                                               │ 识别故障网络设备│
                                               └────────┬────────┘
                                                        │
                                                        ↓
                                               ┌─────────────────┐
                                               │ Step 6: 调用工具│
                                               │ 登录网络设备    │
                                               │ 查询路由/ACL策略│
                                               └─────────────────┘
```

**关键判断点说明**：

1. **telnet返回类型的区分**：
   - `Connection refused`: TCP连接被明确拒绝 → **网络层是通的**，问题在应用层（服务未启动或端口未监听）
   - `Connection timeout`: TCP连接超时 → **网络层或传输层有问题**，可能是防火墙、路由、链路故障

2. **ping测试的作用**：
   - ping成功 + telnet失败 → **网络通但TCP端口被阻断** → 防火墙/安全组策略问题
   - ping失败 → **网络层不通** → 需进一步判断是路由问题还是目标主机问题

3. **禁ping场景的处理**：
   - 很多生产环境服务器禁止ICMP响应（安全策略）
   - 此时ping失败不代表网络不通
   - **替代方案**: ping目标服务器的**网关地址**
   - 如果网关能ping通，说明到该网段的路由是正常的，问题在目标服务器本身

4. **网关测试的意义**：
   - 网关通 → 网络路径正常 → 问题在目标服务器（网卡故障、防火墙DROP、服务器宕机）
   - 网关不通 → 网络路径有问题 → 需要traceroute定位

5. **traceroute的使用**：
   - 定位数据包在哪个节点被阻断
   - 根据CMDB拓扑信息，判断该节点是Leaf交换机、Spine交换机还是其他设备
   - 进一步登录该网络设备检查路由策略、ACL配置

##### 连通性故障排障决策树

```
用户报障: 服务器A到服务器B ping不通
                    ↓
┌───────────────────────────────────────────────────┐
│ Step 1: ping <ip2>                                │
└───────────┬────────────────────┬──────────────────┘
            │                    │
         [成功]               [失败]
            │                    │
            ↓                    ↓
      正常无需排查         ┌──────────────┐
                          │ Step 2:      │
                          │ 检查是否禁ping│
                          └──────┬───────┘
                                 │
                          ┌──────┴──────┐
                      [禁ping]      [不禁ping]
                          │              │
                          ↓              ↓
                  ┌──────────────┐  ┌──────────────┐
                  │ Step 3:      │  │ Step 3':     │
                  │ ping 网关     │  │ 检查路由配置  │
                  └──────┬───────┘  └──────┬───────┘
                         │                 │
                  ┌──────┴──────┐          │
              [网关通]    [网关不通]       │
                  │            │           │
                  ↓            └───────────┘
            目标服务器问题          ↓
                          ┌──────────────┐
                          │ Step 4:      │
                          │ traceroute   │
                          └──────┬───────┘
                                 │
                    分析断点位置，登录网络设备排查
```

**典型根因分类**：

| 现象 | 判断结果 | 可能根因 | 修复建议 |
|------|---------|---------|---------|
| telnet refused | 网络通，应用层问题 | 服务未启动、端口配置错误 | 检查服务状态，查看服务配置 |
| telnet timeout + ping通 | 网络通，TCP被阻断 | 防火墙/安全组规则 | 检查iptables、云安全组配置 |
| telnet timeout + ping不通 + 禁ping + 网关通 | 目标服务器自身问题 | 服务器宕机、网卡故障、防火墙DROP所有 | 检查服务器状态、网卡、防火墙 |
| telnet timeout + ping不通 + 网关不通 | 网络路径故障 | 路由缺失、交换机故障、链路中断 | traceroute定位断点，检查网络设备 |
| ping不通 + 不禁ping + 有路由 | 网络路径故障 | 交换机ACL、路由黑洞、链路故障 | traceroute + 登录网络设备排查 |

#### 3.2.3 AI推理兜底 (Phase 2)

当固定流程无法定位问题时，调用AI推理：

```python
class AIReasoningEngine:
    def reason(self, context: Dict) -> DiagnosticPlan:
        """
        基于上下文进行推理，生成下一步排查计划

        Args:
            context: {
                'task': DiagnosticTask,
                'executed_steps': List[StepResult],
                'cmdb_data': Dict,
                'failed_at_step': str
            }
        """
        prompt = self._build_reasoning_prompt(context)
        response = self.llm.invoke(prompt)
        return self._parse_llm_response(response)

    def _build_reasoning_prompt(self, context):
        return f"""
你是网络故障排查专家。已知信息：
- 故障描述: {context['task'].description}
- 已执行步骤: {self._format_steps(context['executed_steps'])}
- CMDB拓扑: {context['cmdb_data']}
- 当前卡在: {context['failed_at_step']}

Spine-Leaf架构特点:
- 每个Leaf下挂40台服务器
- 跨Leaf通信需经过Spine
- 可能的故障点: Leaf交换机、Spine交换机、服务器网卡、路由配置

请分析可能的根因，并给出下一步排查建议（最多3个命令）。
输出格式:
{{
  "hypothesis": "你的假设",
  "next_steps": [
    {{"command": "...", "on_host": "...", "reason": "..."}},
    ...
  ],
  "confidence": 0.8
}}
"""
```

### 3.3 Executor (执行引擎)

**职责**：安全地执行命令、调用外部服务、解析结果

#### 3.3.1 命令白名单验证器

```python
class CommandWhitelistValidator:
    """
    命令模板白名单 + 参数校验
    """
    WHITELIST = {
        "ping": {
            "template": "ping -c {count} -W {timeout} {target}",
            "params": {
                "target": {"type": "ipv4_or_hostname", "required": True},
                "count": {"type": "int", "range": [1, 10], "default": 4},
                "timeout": {"type": "int", "range": [1, 10], "default": 5}
            },
            "readonly": True
        },
        "ip_route_get": {
            "template": "ip route get {target_ip}",
            "params": {
                "target_ip": {"type": "ipv4", "required": True}
            },
            "readonly": True
        },
        "traceroute": {
            "template": "traceroute -m {max_hops} -w {timeout} {target}",
            "params": {
                "target": {"type": "ipv4_or_hostname", "required": True},
                "max_hops": {"type": "int", "range": [1, 64], "default": 30},
                "timeout": {"type": "int", "range": [1, 10], "default": 3}
            },
            "readonly": True
        },
        "iptables_list": {
            "template": "iptables -L -n -v",
            "params": {},
            "readonly": True,
            "requires_root": True
        },
        "iptables_list_input": {
            "template": "iptables -L INPUT -n -v",
            "params": {},
            "readonly": True,
            "requires_root": True
        },
        "ss_listen": {
            "template": "ss -tunlp | grep ':{port}'",
            "params": {
                "port": {"type": "int", "range": [1, 65535], "required": True}
            },
            "readonly": True
        },
        "ip_addr_show": {
            "template": "ip addr show",
            "params": {},
            "readonly": True
        },
        "telnet_test": {
            "template": "timeout {timeout} bash -c '</dev/tcp/{target}/{port}' 2>&1 && echo 'SUCCESS' || echo 'FAILED'",
            "params": {
                "target": {"type": "ipv4_or_hostname", "required": True},
                "port": {"type": "int", "range": [1, 65535], "required": True},
                "timeout": {"type": "int", "range": [1, 30], "default": 5}
            },
            "readonly": True
        },
        "nslookup": {
            "template": "nslookup {domain}",
            "params": {
                "domain": {"type": "hostname", "required": True}
            },
            "readonly": True
        },
        "read_pcap": {
            "template": "tcpdump -r {pcap_file} -n {filter}",
            "params": {
                "pcap_file": {"type": "file_path", "required": True},
                "filter": {"type": "string", "default": ""}
            },
            "readonly": True
        },
        "check_icmp_disabled": {
            "template": "cat /proc/sys/net/ipv4/icmp_echo_ignore_all",
            "params": {},
            "readonly": True,
            "description": "检查是否禁用ICMP响应（0=允许ping, 1=禁止ping）"
        },
        "ping_gateway": {
            "template": "ip route get {target_ip} | awk '/via/ {{print $3}}' | xargs -I{{}} ping -c 4 -W 5 {{}}",
            "params": {
                "target_ip": {"type": "ipv4", "required": True}
            },
            "readonly": True,
            "description": "自动提取并ping目标IP的网关地址"
        },
        "ip_route_show": {
            "template": "ip route show",
            "params": {},
            "readonly": True,
            "description": "显示完整路由表"
        },
        "check_switch_routes": {
            "template": "show ip route {target_network}",
            "params": {
                "target_network": {"type": "network_cidr", "required": False, "default": ""}
            },
            "readonly": True,
            "requires_network_device": True,
            "description": "查看交换机路由配置（需适配不同厂商命令）"
        },
        "iptables_list_output": {
            "template": "iptables -L OUTPUT -n -v",
            "params": {},
            "readonly": True,
            "requires_root": True,
            "description": "检查出站防火墙规则"
        },
        # ===== 新增工具（用于YAML工作流）=====
        "query_firewall_policy": {
            "type": "api_call",
            "description": "查询防火墙/安全组策略",
            "params": {
                "host": {"type": "string", "required": True},
                "port": {"type": "int", "required": True},
                "source_ip": {"type": "ipv4", "required": False}
            },
            "returns": {
                "policy_exists": "bool",
                "policy_type": "iptables/security_group/firewalld",
                "blocking_rule": "string",
                "suggestion": "string"
            },
            "mock": True
        },
        "query_gateway": {
            "type": "api_call",
            "description": "查询目标IP的网关地址",
            "params": {
                "target_ip": {"type": "ipv4", "required": True}
            },
            "returns": {
                "gateway_ip": "ipv4",
                "gateway_device": "string",
                "network_segment": "cidr",
                "vlan": "string"
            },
            "mock": True
        },
        "ping_gateway": {
            "type": "api_call",
            "description": "从源主机ping目标的网关地址",
            "params": {
                "source_host": {"type": "string", "required": True},
                "gateway_ip": {"type": "ipv4", "required": True}
            },
            "returns": {
                "success": "bool",
                "packet_loss": "float",
                "rtt_avg": "float"
            },
            "mock": True
        },
        "query_network_device_policy": {
            "type": "api_call",
            "description": "查询网络设备的路由和ACL策略",
            "params": {
                "device_name": {"type": "string", "required": True},
                "target_network": {"type": "string", "required": True}
            },
            "returns": {
                "route_exists": "bool",
                "acl_blocking": "bool",
                "interface_status": "up/down",
                "suggestion": "string"
            },
            "mock": True
        },
        "analyze_traceroute": {
            "type": "analysis",
            "description": "分析traceroute输出，识别断点位置",
            "params": {
                "traceroute_output": {"type": "string", "required": True},
                "cmdb_topology": {"type": "dict", "required": False}
            },
            "returns": {
                "first_timeout_hop": "int",
                "failed_device": "string",
                "analysis": "string"
            },
            "mock": True
        }
    }

    def validate(self, command_name: str, params: Dict) -> str:
        """
        验证并生成最终命令

        Raises:
            ValidationError: 命令不在白名单或参数非法
        """
        if command_name not in self.WHITELIST:
            raise ValidationError(f"命令 {command_name} 不在白名单中")

        spec = self.WHITELIST[command_name]
        validated_params = self._validate_params(params, spec['params'])
        final_command = spec['template'].format(**validated_params)

        # 二次校验：防止命令注入
        if self._contains_injection(final_command):
            raise ValidationError(f"检测到命令注入风险: {final_command}")

        return final_command
```

#### 3.3.2 自动化平台Client封装

```python
class AutomationPlatformClient:
    """
    自动化平台API调用封装

    说明：
    - 自动化平台已经适配了多厂商网络设备（Cisco/Arista/Huawei等）
    - 统一提供命令执行接口，无需关心底层SSH/NETCONF等协议
    - 凭证管理由自动化平台负责，Agent无需管理密钥
    """
    async def execute_command(
        self,
        device_name: str,
        command: str,
        timeout: int = 30
    ) -> CommandResult:
        """
        在指定设备上执行命令

        Args:
            device_name: 目标设备名称（服务器主机名或交换机名称）
            command: 已验证的命令字符串
            timeout: 超时时间（秒）

        Returns:
            CommandResult: {
                'success': bool,
                'stdout': str,
                'stderr': str,
                'exit_code': int,
                'execution_time': float
            }
        """
        try:
            response = await self.automation_api.execute(
                device=device_name,
                command=command,
                timeout=timeout
            )
            return CommandResult.from_api_response(response)
        except TimeoutError:
            return CommandResult(
                success=False,
                error="命令执行超时",
                execution_time=timeout
            )
        except DeviceNotFoundError as e:
            return CommandResult(
                success=False,
                error=f"设备 {device_name} 不存在或不可达: {str(e)}"
            )
```

#### 3.3.3 CMDB Client

```python
class CMDBClient:
    """
    查询CMDB获取拓扑和设备信息
    """
    def get_host_info(self, host: str) -> Optional[HostInfo]:
        """
        查询主机信息

        Returns:
            HostInfo: {
                'ip': str,
                'hostname': str,
                'leaf_switch': str,  # 所属Leaf交换机
                'rack': str,
                'status': str
            }
        """

    def get_network_path(self, source: str, target: str) -> NetworkPath:
        """
        获取两台主机间的网络路径

        Returns:
            NetworkPath: {
                'source_leaf': str,
                'target_leaf': str,
                'spine_switches': List[str],  # 如果跨Leaf
                'same_leaf': bool
            }
        """
```

### 3.4 Analyzer (结果分析器)

**职责**：汇总执行结果，推断根因，生成修复建议

```python
class DiagnosticAnalyzer:
    def analyze(
        self,
        task: DiagnosticTask,
        results: List[StepResult]
    ) -> DiagnosticReport:
        """
        分析排查结果

        Returns:
            DiagnosticReport: {
                'task_id': str,
                'root_cause': str,        # 根因描述
                'confidence': float,      # 置信度 0-1
                'evidence': List[str],    # 证据列表
                'fix_suggestions': List[str],  # 修复建议
                'need_human': bool        # 是否需要人工介入
            }
        """
        # 1. 基于规则的分析
        rule_result = self._rule_based_analysis(results)
        if rule_result.confidence > 0.8:
            return rule_result

        # 2. AI辅助分析
        ai_result = self._ai_analysis(task, results)
        return ai_result

    def _rule_based_analysis(self, results: List[StepResult]) -> DiagnosticReport:
        """
        基于规则的根因判断
        """
        # 示例规则
        if self._check_pattern(results, "ping失败 + 无路由"):
            return DiagnosticReport(
                root_cause="源主机缺少到目标网段的路由配置",
                confidence=0.95,
                evidence=["ping 100%丢包", "ip route get显示无路由"],
                fix_suggestions=[
                    "检查源主机路由表: ip route show",
                    "联系网络团队添加静态路由或检查BGP配置"
                ]
            )

        if self._check_pattern(results, "ping成功 + telnet失败 + 端口未监听"):
            return DiagnosticReport(
                root_cause="目标主机上服务未启动或未监听指定端口",
                confidence=0.9,
                evidence=["ICMP可达", "TCP连接被拒绝", "ss命令显示端口未监听"],
                fix_suggestions=[
                    "检查目标服务状态: systemctl status <service>",
                    "检查服务配置文件中的监听端口",
                    "查看服务日志: journalctl -u <service>"
                ]
            )

    def _ai_analysis(self, task: DiagnosticTask, results: List[StepResult]) -> DiagnosticReport:
        """
        LLM辅助分析（兜底）
        """
        prompt = f"""
你是网络故障诊断专家。请分析以下排查结果：

故障描述: {task.description}
网络拓扑: {task.topology}

执行步骤及结果:
{self._format_results(results)}

请给出:
1. 最可能的根因 (root_cause)
2. 置信度 (confidence, 0-1)
3. 支持证据 (evidence)
4. 修复建议 (fix_suggestions)
5. 是否需要人工深入排查 (need_human: true/false)

JSON格式输出。
"""
        response = self.llm.invoke(prompt)
        return DiagnosticReport.from_json(response)
```

### 3.5 Response Generator (响应生成器)

**职责**：生成诊断结果的 JSON 响应和 SSE 实时推送

> **注意**：暂不实现 Markdown 文件报告生成，诊断结果通过 API JSON 响应返回。

**输出格式**：JSON API 响应

```json
{
  "task_id": "task_20260105_001",
  "status": "success",
  "root_cause": "目标主机 (server2) 的iptables防火墙规则阻止了80端口的入站流量",
  "confidence": 95.0,
  "execution_time": 8.5,
  "steps": [
    {
      "step": 1,
      "name": "验证主机存在性",
      "success": true
    },
    {
      "step": 2,
      "name": "端口连通性测试",
      "command": "timeout 5 bash -c '<... /dev/tcp/10.0.2.20/80'",
      "success": false
    }
  ],
  "suggestions": [
    "在server2上执行: iptables -D INPUT -p tcp --dport 80 -j DROP",
    "然后执行: iptables -I INPUT -p tcp --dport 80 -j ACCEPT"
  ],
  "tool_calls": [
    {
      "step": 1,
      "tool": "query_cmdb",
      "arguments": {"hosts": ["server1", "server2"]},
      "result_summary": {"success": true}
    }
  ]
}
```

**SSE 流式推送事件类型**：

| 事件类型 | 说明 | 示例 |
|----------|------|------|
| `start` | 诊断开始 | `{"type": "start", "task_id": "task_xxx", "source": "...", "target": "..."}` |
| `tool_start` | 工具调用开始 | `{"type": "tool_start", "step": 1, "tool": "execute_command", "arguments": {...}}` |
| `tool_result` | 工具调用结果 | `{"type": "tool_result", "step": 1, "tool": "execute_command", "result": {...}}` |
| `ask_user` | 需要用户输入 | `{"type": "ask_user", "question": "请问目标服务器上是否有防火墙？"}` |
| `complete` | 诊断完成 | `{"type": "complete", "report": {...}}` |
| `error` | 错误信息 | `{"type": "error", "message": "..."}` |

---

## 4. 数据流和接口定义

### 4.1 核心数据结构

​```python
# models.py

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class FaultType(Enum):
    CONNECTIVITY = "connectivity"          # ping不通
    PORT_UNREACHABLE = "port_unreachable"  # telnet失败
    SLOW = "slow"                          # 延迟高/丢包
    DNS = "dns"                            # DNS解析问题

class Protocol(Enum):
    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"

@dataclass
class DiagnosticTask:
    task_id: str
    user_input: str            # 原始输入
    source: str                # 源主机
    target: str                # 目标主机
    protocol: Protocol
    port: Optional[int]
    fault_type: FaultType
    created_at: datetime
    context: Dict[str, Any]    # 额外信息

@dataclass
class HostInfo:
    ip: str
    hostname: str
    leaf_switch: str
    rack: str
    status: str
    tags: List[str]

@dataclass
class NetworkPath:
    source_leaf: str
    target_leaf: str
    spine_switches: List[str]
    same_leaf: bool
    estimated_hops: int

@dataclass
class CommandResult:
    command: str
    host: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    timestamp: datetime

@dataclass
class StepResult:
    step_number: int
    step_name: str
    action: str
    command_result: Optional[CommandResult]
    success: bool
    next_step: Optional[int]
    metadata: Dict[str, Any]

@dataclass
class DiagnosticReport:
    task_id: str
    root_cause: str
    confidence: float          # 0-1
    evidence: List[str]
    fix_suggestions: List[str]
    need_human: bool
    executed_steps: List[StepResult]
    total_time: float
    created_at: datetime
```

### 4.2 外部接口

#### 4.2.1 自动化平台API接口

```python
# 自动化平台提供的接口
class AutomationPlatformAPI:
    async def execute(
        self,
        device: str,
        command: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        在指定设备上执行命令

        Args:
            device: 设备名称（服务器主机名或交换机名称）
            command: 要执行的命令
            timeout: 超时时间（秒）

        Returns: {
            "success": true,
            "device": "server1",
            "command": "ping -c 4 10.0.2.20",
            "stdout": "PING 10.0.2.20...\n4 packets transmitted, 4 received, 0% packet loss",
            "stderr": "",
            "exit_code": 0,
            "execution_time": 0.523,
            "timestamp": "2026-01-13T10:30:00Z"
        }

        错误响应: {
            "success": false,
            "error_code": "DEVICE_NOT_FOUND",
            "error_message": "设备 server1 不存在或不可达",
            "timestamp": "2026-01-13T10:30:00Z"
        }

        说明：
        - 自动化平台已经适配多厂商设备，无需Agent关心底层协议
        - 凭证管理由自动化平台负责
        - 支持服务器和网络设备的统一接口
        """

    async def batch_execute(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量执行命令（并行）

        Args:
            tasks: [
                {"device": "server1", "command": "ping -c 4 10.0.2.20"},
                {"device": "server2", "command": "ss -tunlp"}
            ]

        Returns:
            List of execution results
        """
```

#### 4.2.2 CMDB API接口

```python
# CMDB提供的接口
class CMDBInterface:
    def get_host(self, identifier: str) -> Optional[Dict]:
        """
        查询主机/Pod信息

        Args:
            identifier: IP、主机名或Pod名称

        Returns: {
            "ip": "10.0.1.10",
            "hostname": "server1",
            "device_type": "physical_server",  # physical_server/vm/pod
            "leaf_switch": "leaf-01",
            "rack": "A01-R05",
            "status": "online",
            "pod_info": {  # 如果是K8s Pod
                "namespace": "default",
                "node": "k8s-node-01",
                "pod_ip": "10.244.1.5"
            }
        }

        说明：
        - 支持物理机、虚拟机、K8s Pod的统一查询
        - Pod IP也录入CMDB，可以直接查询
        - 包含服务器到Leaf交换机的拓扑映射（准确）
        """

    def get_topology(self, host1: str, host2: str) -> Dict:
        """
        查询两台主机间的拓扑路径

        Returns: {
            "source": {
                "hostname": "server1",
                "ip": "10.0.1.10",
                "leaf_switch": "leaf-01"
            },
            "target": {
                "hostname": "server2",
                "ip": "10.0.2.20",
                "leaf_switch": "leaf-02"
            },
            "spine_switches": ["spine-01"],
            "same_leaf": false,
            "path": ["server1", "leaf-01", "spine-01", "leaf-02", "server2"]
        }
        """

    def get_switch_info(self, switch_name: str) -> Dict:
        """
        查询交换机信息

        Returns: {
            "name": "leaf-01",
            "mgmt_ip": "10.10.10.1",
            "vendor": "cisco",
            "model": "nexus-9300",
            "role": "leaf",
            "connected_servers": ["server1", "server2", ...],
            "uplink_switches": ["spine-01", "spine-02"]
        }
        """
```

#### 4.2.3 接口调用示例

```python
# 完整的排查流程示例
async def diagnose_connectivity(source: str, target: str):
    # 1. 查询CMDB拓扑
    cmdb = CMDBClient()
    topology = cmdb.get_topology(source, target)

    # 2. 执行ping测试
    automation = AutomationPlatformClient()
    ping_result = await automation.execute(
        device=source,
        command=f"ping -c 4 {topology['target']['ip']}"
    )

    # 3. 如果ping失败，执行traceroute
    if not ping_result.success:
        traceroute_result = await automation.execute(
            device=source,
            command=f"traceroute {topology['target']['ip']}"
        )

        # 4. 解析traceroute，识别断点
        broken_hop = parse_traceroute(traceroute_result.stdout)

        # 5. 如果断点是交换机，登录交换机检查
        if broken_hop in topology['path']:
            switch_info = cmdb.get_switch_info(broken_hop)
            routes = await automation.execute(
                device=switch_info['name'],
                command="show ip route"
            )
            # 分析路由配置...
```

---

## 5. 性能指标和约束

### 5.1 性能目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **单次排查总时长** | ≤ 5分钟 | 超时后请求人工介入 |
| **单条命令超时** | 30秒 | 可根据命令类型调整 |
| **并发命令数** | ≤ 10 | 避免打爆MCP Server |
| **最大执行命令数** | 50条 | 单次排查上限 |
| **NLU响应时间** | ≤ 3秒 | 意图识别延迟 |
| **AI推理响应** | ≤ 10秒 | LLM推理时间 |

### 5.2 资源限制

- **并发任务数**: 5个（多个用户同时提交）
- **历史记录保留**: 30天
- **报告文件大小**: ≤ 10MB（避免命令输出过大）

### 5.3 交互体验设计

#### 5.3.1 异步任务机制

**需求背景**：排查过程可能需要5分钟，用户不应一直等待

**设计方案**：

```python
class AsyncTaskManager:
    """
    异步任务管理器
    """
    def submit_task(self, task: DiagnosticTask) -> str:
        """
        提交排查任务

        Returns:
            task_id: 任务唯一ID
        """
        task_id = generate_task_id()
        self.task_queue.put(task_id, task)
        return task_id

    def get_task_status(self, task_id: str) -> TaskStatus:
        """
        查询任务状态

        Returns: {
            "task_id": "task_20260113_001",
            "status": "running",  # pending/running/completed/failed
            "progress": 60,  # 0-100
            "current_step": "正在执行traceroute...",
            "elapsed_time": 125.3,
            "estimated_remaining": 95.2
        }
        """

    def cancel_task(self, task_id: str) -> bool:
        """
        取消正在执行的任务
        """

    def wait_for_completion(self, task_id: str, callback=None):
        """
        等待任务完成，支持回调通知

        Args:
            callback: 完成后的通知函数（支持邮件、钉钉、Slack等）
        """
```

**用户交互流程**：

```bash
# 用户提交任务
$ netops diagnose "server1到server2端口80不通" --async
✅ 任务已提交: task_20260113_001
📊 当前进度: 0% | 状态: pending
💡 提示: 使用 `netops status task_20260113_001` 查看进度
       或使用 `netops watch task_20260113_001` 实时监控

# 用户查询进度
$ netops status task_20260113_001
📊 任务进度: 60%
🏃 状态: running
⏱️  已执行: 2分05秒 | 预计剩余: 1分35秒
📍 当前步骤: 正在执行traceroute定位网络断点...
   ├─ ✅ Step 1: 验证主机存在性
   ├─ ✅ Step 2: Telnet端口测试（timeout）
   ├─ ✅ Step 3: Ping连通性测试（失败）
   ├─ ✅ Step 4: 检查是否禁ping（是）
   ├─ ✅ Step 5: Ping网关（失败）
   └─ 🏃 Step 6: Traceroute定位断点...

# 任务完成后通知
✅ 任务完成: task_20260113_001
🎯 根因: Spine交换机spine-01路由配置缺失到10.0.2.0/24网段的路由
📄 报告已生成: /var/log/netops/reports/task_20260113_001.md

# 查看报告
$ netops report task_20260113_001
[显示Markdown格式的详细报告]
```

#### 5.3.2 中断机制

**需求背景**：如果Agent卡在某个步骤（如SSH超时），用户可以手动跳过

**设计方案**：

```python
class InterruptHandler:
    """
    中断控制器
    """
    def skip_current_step(self, task_id: str, reason: str):
        """
        跳过当前卡住的步骤，继续执行后续步骤

        Args:
            task_id: 任务ID
            reason: 跳过原因（记录到报告中）
        """

    def abort_task(self, task_id: str, reason: str):
        """
        直接终止任务

        Args:
            reason: 终止原因
        """
```

**用户交互**：

```bash
# Agent卡在某个步骤
$ netops watch task_20260113_001
📊 任务进度: 45%
⚠️  警告: Step 5执行超时（已等待3分钟）
   命令: traceroute -m 30 -w 3 10.0.2.20
   状态: 超时无响应

💡 可选操作:
   1. 等待继续 (默认还会等待2分钟)
   2. 跳过此步骤 (netops skip task_20260113_001)
   3. 终止任务 (netops abort task_20260113_001)

# 用户选择跳过
$ netops skip task_20260113_001 --reason "traceroute超时，手动跳过"
✅ 已跳过Step 5，继续执行后续步骤
📝 跳过原因已记录到报告中
```

#### 5.3.3 快速模式 vs 深度模式

**快速模式**（默认）：
- 目标：10秒内给出初步判断
- 策略：只执行关键步骤，跳过耗时的详细排查
- 适用场景：快速定位"大方向"问题（如网络不通、服务未启动、防火墙阻断）

**深度模式**：
- 目标：完整排查，给出详细根因和修复建议
- 策略：执行所有决策树步骤，包括traceroute、交换机路由检查等
- 适用场景：快速模式无法定位时的深入分析

**流程对比**：

| 步骤 | 快速模式 | 深度模式 |
|------|---------|---------|
| 验证主机存在 | ✅ | ✅ |
| Telnet测试 | ✅ | ✅ |
| 检查端口监听 | ✅ (仅refused时) | ✅ |
| Ping测试 | ✅ | ✅ |
| 检查禁ping | ❌ 跳过 | ✅ |
| Ping网关 | ❌ 跳过 | ✅ |
| Traceroute | ❌ 跳过 | ✅ |
| 检查防火墙 | ✅ (简化版) | ✅ (详细) |
| 登录交换机 | ❌ 跳过 | ✅ |
| AI推理兜底 | ✅ | ✅ |

**使用示例**：

```bash
# 快速模式（默认）
$ netops diagnose "server1到server2端口80不通"
⚡ 快速模式启动...
✅ 10秒后返回结果:
   🎯 初步判断: 防火墙策略问题
   💡 建议: 检查server2的iptables INPUT链或云安全组配置
   📌 如需详细排查，使用: netops diagnose <描述> --deep

# 深度模式
$ netops diagnose "server1到server2端口80不通" --deep
🔍 深度模式启动，预计需要3-5分钟...
[完整的排查流程，包含traceroute、交换机检查等]
✅ 5分钟后返回详细报告
```

**实现差异**：

```python
class TaskPlanner:
    def plan(self, task: DiagnosticTask, mode: str = "fast") -> List[Step]:
        """
        根据模式生成执行计划

        Args:
            mode: "fast" | "deep"
        """
        if mode == "fast":
            return self._generate_fast_plan(task)
        else:
            return self._generate_deep_plan(task)

    def _generate_fast_plan(self, task):
        """
        快速模式：跳过耗时步骤，优先使用规则引擎

        执行步骤:
        1. Telnet测试 (5s)
        2. 基于telnet结果直接判断:
           - refused → 服务未启动
           - timeout → ping测试 → 防火墙或网络问题
        3. 简化的防火墙检查 (只看关键规则)
        4. 给出初步建议
        """

    def _generate_deep_plan(self, task):
        """
        深度模式：执行完整决策树

        执行步骤:
        1. Telnet测试
        2. Ping测试
        3. 检查禁ping
        4. Ping网关
        5. Traceroute (可能需要30s-1min)
        6. 识别断点，登录交换机 (可能需要1-2min)
        7. 详细的防火墙和路由分析
        8. AI推理兜底（如需要）
        """
```

---

## 6. 边缘场景和错误处理

### 6.1 异常场景

| 场景 | 处理策略 |
|------|---------|
| **主机不在CMDB** | 立即返回错误，提示用户确认主机名/IP |
| **SSH连接失败** | 重试3次（间隔2s），仍失败则标记为"无法访问" |
| **命令超时** | 记录超时，继续执行后续步骤（标记该步骤为"未完成"） |
| **命令执行失败** | 解析stderr，判断是权限问题还是命令不存在，调整流程 |
| **MCP Server宕机** | 降级模式：只做本地分析（基于历史数据推理） |
| **CMDB API超时** | 使用缓存的拓扑数据（如果有） |
| **LLM API限流** | 回退到纯规则引擎，报告"AI分析不可用" |
| **用户输入无法解析** | 返回澄清问题，引导用户重新输入 |
| **循环依赖**（如DNS不通导致无法解析主机名） | 优先使用IP地址，标记"DNS问题待确认" |

### 6.2 安全保障

1. **命令注入防护**:
   - 所有参数严格校验（正则匹配）
   - 禁止`;`, `|`, `&`, `$()`, ``` `` ```等特殊字符
   - 二次校验最终命令字符串

2. **权限控制**:
   - Agent侧双重校验

3. **审计日志**:
   - 记录所有命令执行（主机、命令、执行者、时间戳）
   - 存储到独立审计表

---

## 7. 分阶段实施计划

### Phase 1: 核心MVP (2-3周)

**目标**: 证明技术可行性，实现端口不可达故障的自动化排查

**范围**:
- ✅ 支持1种故障类型：**端口不可达**（telnet失败）
- ✅ 固定流程引擎（YAML决策树）作为主路径，LLM 作为兆底
- ✅ 命令白名单：`telnet`, `ping`, `ss`, `iptables -L`, `traceroute`
- ✅ Mock 自动化平台API（本地模拟命令执行）
- ✅ Mock CMDB（静态JSON数据，包含50台服务器+拓扑信息）
- ✅ Web Chat UI（浏览器聊天界面 + SSE 流式响应）
- ✅ NLU模块（LLM解析用户自然语言输入）
- ✅ JSON API 响应（包含诊断结果、步骤、建议）
- ✅ 基础日志记录
- ✅ 会话SQLite存储（按任务ID检索）
- ✅ Traceroute输出解析（识别断点位置）

**核心测试场景**（必须覆盖）:

#### 场景1: Connection Refused - 服务未启动
```
用户输入: "server1到server2的80端口访问不通"
Mock数据:
  - server1, server2均在CMDB
  - telnet返回: Connection refused
  - ss -tunlp: 端口80未监听

期望输出:
  🎯 根因: server2上的服务未启动或未监听80端口
  💡 建议: 检查服务状态 (systemctl status nginx)
  📊 置信度: 95%
  ⏱️  排查耗时: < 5秒
```

#### 场景2: Connection Timeout + Ping通 - 防火墙策略未开
```
用户输入: "server1到server2的80端口访问不通"
Mock数据:
  - server1, server2均在CMDB
  - telnet返回: Connection timeout
  - ping结果: 0% packet loss
  - ss -tunlp: 端口80正常监听
  - iptables -L INPUT: 存在DROP tcp dpt:80规则

期望输出:
  🎯 根因: server2的防火墙阻止了80端口入站流量
  💡 建议: 在server2上执行 iptables -I INPUT -p tcp --dport 80 -j ACCEPT
  📊 置信度: 95%
  ⏱️  排查耗时: < 10秒
  ⚠️  注意: 修改前请确认符合安全策略
```

#### 场景3: Connection Timeout + Ping不通 + Traceroute定位断点
```
用户输入: "server1到server2的80端口访问不通"
Mock数据:
  - server1, server2均在CMDB
  - CMDB拓扑: server1 → leaf-01 → spine-01 → leaf-02 → server2
  - telnet返回: Connection timeout
  - ping结果: 100% packet loss
  - traceroute输出:
    traceroute to 10.0.2.20 (10.0.2.20), 30 hops max
     1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms    # leaf-01网关
     2  10.10.1.1 (10.10.1.1)  1.234 ms  1.123 ms  1.089 ms  # spine-01
     3  * * *                                                  # leaf-02 超时
     4  * * *
     5  * * *

期望输出:
  🎯 根因: 网络路径在第3跳断开，疑似leaf-02交换机故障或路由配置问题
  📍 断点位置:
     - 最后可达: spine-01 (10.10.1.1)
     - 失败节点: leaf-02 (根据CMDB拓扑推断)
  💡 建议:
    1. 检查leaf-02交换机状态（CMDB可查询管理IP）
    2. 登录spine-01检查到10.0.2.0/24网段的路由
    3. 检查leaf-02到spine-01的链路状态
    4. 如需深入排查交换机路由配置，建议手动登录或使用 --deep 模式
  📊 置信度: 85% (基于traceroute + CMDB拓扑推断)
  ⏱️  排查耗时: < 15秒

  📝 排查步骤:
     ✅ Step 1: 验证主机存在性
     ✅ Step 2: Telnet端口测试（timeout）
     ✅ Step 3: Ping连通性测试（失败，100%丢包）
     ✅ Step 4: Traceroute定位断点
     ✅ Step 5: 根据CMDB拓扑识别故障节点
     ✅ Step 6: 生成诊断报告
```

**验收标准**:
- ✅ **功能完整性**: 3个场景100%通过
- ✅ **准确性**: 根因判断正确率 ≥ 90%
- ✅ **性能**: 单次排查耗时 ≤ 10秒
- ✅ **响应质量**: JSON响应包含所有执行步骤、命令输出、诊断结论
- ✅ **代码质量**: 核心模块测试覆盖率 ≥ 80%

**Mock数据准备**:

```python
# mock_cmdb_data.json
{
  "servers": [
    {
      "hostname": "server1",
      "ip": "10.0.1.10",
      "leaf_switch": "leaf-01",
      "status": "online"
    },
    {
      "hostname": "server2",
      "ip": "10.0.2.20",
      "leaf_switch": "leaf-02",
      "status": "online"
    },
    # ... 共50台服务器
  ],
  "topology": {
    "server1_to_server2": {
      "path": ["server1", "leaf-01", "spine-01", "leaf-02", "server2"],
      "same_leaf": false
    }
  }
}

# mock_automation_responses.json
{
  "scenario1_refused": {
    "telnet_server2_80": {
      "stdout": "",
      "stderr": "Connection refused",
      "exit_code": 1
    },
    "ss_server2": {
      "stdout": "",  # 空输出，表示端口未监听
      "exit_code": 0
    }
  },
  "scenario2_firewall": {
    "telnet_server2_80": {
      "stdout": "",
      "stderr": "Connection timed out",
      "exit_code": 1
    },
    "ping_server2": {
      "stdout": "4 packets transmitted, 4 received, 0% packet loss",
      "exit_code": 0
    },
    "ss_server2": {
      "stdout": "tcp   LISTEN  0   128   *:80   *:*   users:(("nginx",pid=1234))",
      "exit_code": 0
    },
    "iptables_server2": {
      "stdout": "Chain INPUT (policy DROP)\\n0     0 DROP    tcp  --  *   *   0.0.0.0/0  0.0.0.0/0  tcp dpt:80",
      "exit_code": 0
    }
  },
  "scenario3_network_broken": {
    "telnet_server2_80": {
      "stdout": "",
      "stderr": "Connection timed out",
      "exit_code": 1
    },
    "ping_server2": {
      "stdout": "4 packets transmitted, 0 received, 100% packet loss",
      "exit_code": 1
    },
    "traceroute_server2": {
      "stdout": "traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets\\n 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms\\n 2  10.10.1.1 (10.10.1.1)  1.234 ms  1.123 ms  1.089 ms\\n 3  * * *\\n 4  * * *\\n 5  * * *",
      "exit_code": 0
    }
  }
}
```


---

### Phase 2: AI推理增强 + 智能化 (3-4周)

**目标**: 增强LLM推理能力，处理复杂场景

**新增功能**:
- ✅ AI推理兜底增强（固定流程失败后调用）
- ✅ LLM辅助根因分析
- ✅ 新增故障类型：**性能问题**（延迟高、丢包）
- ✅ 新增命令：读取抓包文件（`tcpdump -r`）
- ✅ 交互式追问增强（如果信息不足，Agent主动问用户）
- ✅ 快速模式 vs 深度模式支持

**验收标准**:
- AI推理兜底成功率 > 60%（即固定流程失败的case中，AI能解决60%）
- NLU准确率 > 90%
- 支持复杂自然语言输入（如"测试环境web访问数据库很慢"）

---

### Phase 3: 历史学习 + 优化 (后续迭代)

**未来方向**:
- 基于历史排查记录优化流程（高频故障优先排查）
- RAG增强（检索相似历史case）
- 自动生成知识库
- 多Agent协作（网络Agent + 主机Agent + 应用Agent）
- 与监控系统集成（告警自动触发排查）

---

## 8. 项目目录结构

```
netOpsAgent/
├── README.md
├── docs/
│   └── spec.md                # 本文档
├── requirements.txt
├── pyproject.toml
├── config/
│   ├── workflows/             # 固定流程定义
│   │   ├── connectivity.yaml
│   │   ├── port_unreachable.yaml
│   │   └── dns.yaml
│   ├── commands_whitelist.yaml  # 命令白名单
│   └── networks.yaml          # 网络配置
├── src/
│   ├── api.py                 # FastAPI HTTP服务入口
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── llm_agent.py       # LLM Agent主入口
│   │   ├── nlu.py             # 自然语言理解
│   │   ├── planner.py         # 任务规划器（YAML固定流程）
│   │   ├── executor.py        # 执行引擎
│   │   └── analyzer.py        # 结果分析器
│   ├── integrations/
│   │   ├── automation_platform_client.py  # 自动化平台客户端
│   │   ├── cmdb_client.py     # CMDB客户端
│   │   ├── llm_client.py      # LLM客户端（OpenAI兼容API）
│   │   └── network_tools.py   # 网络工具函数
│   ├── models/
│   │   ├── task.py            # 任务数据模型
│   │   ├── results.py         # 结果数据模型
│   │   └── report.py          # 诊断报告模型
│   ├── db/
│   │   └── session_manager.py # SQLite会话管理
│   └── utils/
│       ├── parsers.py         # 命令输出解析
│       └── logger.py          # 日志工具
├── web/
│   ├── index.html             # 前端主页
│   ├── css/                   # 样式文件
│   └── js/                    # JavaScript文件
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/              # Mock数据
│       ├── mock_cmdb_data.json
│       └── mock_automation_responses.json
├── runtime/
│   └── sessions.db            # SQLite会话数据库
└── scripts/
    ├── start_api.bat          # Windows API启动脚本
    └── start_api.sh           # Linux API启动脚本
```

---

## 9. 关键风险和缓解措施

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **LLM API限流/宕机** | AI推理不可用 | 中 | 1. 优先使用固定流程<br>2. 本地缓存LLM响应<br>3. 备用模型 |
| **命令白名单过于严格** | 无法覆盖复杂场景 | 高 | 1. 建立白名单扩展流程<br>2. 人工审核新命令<br>3. 定期回顾日志中被拦截的命令 |
| **固定流程无法覆盖所有场景** | AI推理兜底成功率低 | 高 | 1. 收集失败case持续优化流程<br>2. 增强LLM prompt<br>3. 引入RAG检索历史案例 |
| **并发执行打爆基础设施** | MCP/CMDB过载 | 低 | 1. 严格限流（信号量）<br>2. 请求队列<br>3. 熔断机制 |
| **误报导致错误修复建议** | 用户误操作 | 中 | 1. 标注置信度<br>2. 高风险操作强制人工确认<br>3. 只提供只读命令 |

---


## 12. 附录

### 12.1 术语表

| 术语 | 说明 |
|------|------|
| **Spine-Leaf** | 数据中心网络架构，Spine为核心层，Leaf为接入层 |
| **CMDB** | Configuration Management Database，配置管理数据库 |
| **MCP** | Model Context Protocol，LLM与外部工具交互的协议 |
| **NLU** | Natural Language Understanding，自然语言理解 |
| **决策树流程** | 基于if-else规则的固定排查流程 |
| **AI推理兜底** | 固定流程无法定位时，调用LLM进行开放式推理 |

### 12.2 参考文档

- [MCP协议规范](https://modelcontextprotocol.io/)
- [LangChain文档](https://python.langchain.com/)
- [Claude API文档](https://docs.anthropic.com/)

---

## 变更记录

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-01-05 | 初始版本 | 产品设计团队 |
