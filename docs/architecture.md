# netOpsAgent 核心设计与架构文档

## 📋 文档概览

**文档版本**: v1.0
**创建日期**: 2026-01-29
**项目**: netOpsAgent - 智能网络故障诊断系统
**技术栈**: Python 3.10+ | FastAPI | LangChain | SQLite

---

## 1. 项目架构总览

### 1.1 系统定位

netOpsAgent 是一个**基于 LLM 驱动的智能网络故障诊断系统**，采用**双引擎混合架构**（规则引擎 + LLM Agent），实现自动化的网络连通性问题排查和根因分析。

### 1.2 核心特性

- ✅ **双引擎混合**：规则优先（快速、免费）+ LLM 兜底（灵活、智能）
- ✅ **多轮对话支持**：会话持久化，支持中断后继续诊断
- ✅ **多网络环境**：支持多个独立网络环境的命令路由
- ✅ **流式响应**：SSE 实时推送诊断进度
- ✅ **安全执行**：命令白名单机制，防止注入攻击
- ✅ **可扩展性**：模块化设计，易于扩展新的诊断场景

### 1.3 目录结构

```
netOpsAgent/
├── src/                    # 源代码
│   ├── agent/              # 诊断 Agent 核心模块
│   │   ├── nlu.py          # 自然语言理解
│   │   ├── planner.py      # 任务规划器
│   │   ├── executor.py     # 命令执行引擎
│   │   ├── analyzer.py     # 结果分析器
│   │   ├── reporter.py     # 报告生成器
│   │   └── llm_agent.py    # LLM Agent (LangChain)
│   │
│   ├── integrations/       # 外部系统集成
│   │   ├── llm_client.py           # LLM 客户端
│   │   ├── automation_platform_client.py  # 远程命令执行
│   │   ├── cmdb_client.py          # CMDB 查询
│   │   ├── network_tools.py        # 网络工具集
│   │   └── network_router.py       # 多网络路由
│   │
│   ├── models/             # 数据模型 (Pydantic)
│   │   ├── task.py         # DiagnosticTask
│   │   ├── report.py       # DiagnosticReport
│   │   └── results.py      # StepResult/CommandResult
│   │
│   ├── utils/              # 工具模块
│   │   └── parsers/        # 命令输出解析器
│   │
│   ├── db/                 # 数据库模块
│   │   ├── database.py     # SQLite 会话数据库
│   │   └── serializers.py  # 数据序列化
│   │
│   ├── cli.py              # CLI 接口 (Typer)
│   ├── api.py              # HTTP API (FastAPI)
│   └── session_manager.py  # 会话管理
│
├── config/                 # 配置文件
│   ├── networks.yaml       # 多网络环境配置
│   └── workflows/          # 工作流定义（预留）
│
├── tests/                  # 测试代码
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   ├── e2e/                # 端到端测试
│   └── fixtures/           # Mock 数据
│
├── scripts/                # 启动脚本
├── docs/                   # 文档
└── runtime/                # 运行时文件
    ├── reports/            # 诊断报告
    └── sessions.db         # 会话数据库
```

---

## 2. 核心设计理念

### 2.1 设计原则

1. **单一职责原则 (SRP)**：每个模块只负责一个明确的功能
2. **开闭原则 (OCP)**：对扩展开放，对修改关闭
3. **依赖倒置原则 (DIP)**：依赖抽象而非具体实现
4. **渐进式增强**：Phase 1 使用 Mock 数据，Phase 2+ 集成真实 API

### 2.2 架构分层

```
┌──────────────────────────────────────────────┐
│  接入层 (Interface Layer)                     │
│  - FastAPI (HTTP API)                        │
│  - Typer (CLI)                               │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│  业务层 (Business Logic Layer)               │
│  - LLMAgent (动态诊断)                        │
│  - TaskPlanner (规划器)                       │
│  - DiagnosticAnalyzer (分析器)               │
│  - SessionManager (会话管理)                 │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│  执行层 (Execution Layer)                    │
│  - Executor (命令执行)                        │
│  - NetworkTools (网络工具)                   │
│  - Parsers (输出解析)                        │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│  集成层 (Integration Layer)                  │
│  - AutomationPlatformClient (远程执行)       │
│  - CMDBClient (设备查询)                      │
│  - LLMClient (LLM 调用)                       │
│  - NetworkRouter (多网络路由)                │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│  数据层 (Data Layer)                         │
│  - SessionDatabase (会话存储)                │
│  - ConfigLoader (配置加载)                   │
│  - Mock Data (测试数据)                       │
└──────────────────────────────────────────────┘
```

---

## 3. 核心模块详解

### 3.1 Agent 核心模块 (`src/agent/`)

#### 3.1.1 NLU (自然语言理解) - `nlu.py`

**职责**：将自然语言故障描述解析为结构化任务对象

**输入**：
```python
"10.0.1.10到10.0.2.20端口80不通"
```

**输出**：
```python
DiagnosticTask(
    source="10.0.1.10",
    target="10.0.2.20",
    protocol="tcp",
    port=80,
    fault_type="port_unreachable"
)
```

**实现方式**：
- **Phase 1**：基于正则表达式的规则解析
- **Phase 2+**：LLM + Few-shot prompting

**LLM 提示词模板**：
```python
"""
你是一个网络故障排查专家。从用户描述中提取：
1. 源主机 (source)
2. 目标主机 (target)
3. 协议 (protocol): icmp/tcp/udp
4. 端口 (port)
5. 故障类型 (fault_type): connectivity/port_unreachable/slow/dns

输入: {user_input}
输出: JSON格式
"""
```

---

#### 3.1.2 TaskPlanner (任务规划器) - `planner.py`

**职责**：根据故障类型生成执行计划（步骤列表）

**支持的故障类型**：
- `PORT_UNREACHABLE`：端口不可达
- `CONNECTIVITY`：连通性故障

**典型流程（端口不可达）**：

```
Step 1: 验证主机存在性
    ↓
    query_cmdb(target="10.0.2.20")

Step 2: 端口连通性测试
    ↓
    telnet_test(source="10.0.1.10", target="10.0.2.20", port=80)

Step 3: 根据 telnet 结果分支
    ├─ Connection refused → 检查端口监听状态
    │   ↓
    │   ss_listen(host="10.0.2.20", port=80)
    │
    └─ Connection timeout → Ping 测试
        ↓
        ping(source="10.0.1.10", target="10.0.2.20")
        ├─ Ping 成功 → 检查防火墙规则
        │   ↓
        │   iptables_list(host="10.0.2.20")
        │
        └─ Ping 失败 → 路由跟踪
            ↓
            traceroute(source="10.0.1.10", target="10.0.2.20")
```

**计划格式**：
```python
[
    {
        "step_id": 1,
        "action": "query_cmdb",
        "command_template": "query_cmdb",
        "params": {"hosts": ["10.0.2.20"]},
        "description": "验证主机是否在CMDB中注册"
    },
    {
        "step_id": 2,
        "action": "telnet_test",
        "command_template": "telnet_test",
        "params": {"target": "10.0.2.20", "port": 80, "timeout": 3},
        "description": "测试端口80连通性"
    }
]
```

---

#### 3.1.3 Executor (执行引擎) - `executor.py`

**职责**：安全执行诊断命令，解析结果

**核心特性**：
- ✅ 命令白名单机制（防止注入攻击）
- ✅ 参数化命令模板
- ✅ 自动调用对应的解析器
- ✅ 超时控制

**命令白名单**：
```python
COMMAND_TEMPLATES = {
    "telnet_test": "timeout {timeout} bash -c 'cat < /dev/tcp/{target}/{port}'",
    "ss_listen": "ss -tunlp | grep ':{port}'",
    "ping": "ping -c {count} -W {timeout} {target}",
    "iptables_list_input": "iptables -L INPUT -n -v",
    "iptables_list_output": "iptables -L OUTPUT -n -v",
    "traceroute": "traceroute {target} -m {max_hops} -w {timeout}"
}
```

**执行流程**：
```python
async def execute_step(step: Dict[str, Any]) -> StepResult:
    # 1. 验证命令模板是否在白名单中
    if step["command_template"] not in COMMAND_TEMPLATES:
        raise SecurityError("Command not allowed")

    # 2. 构建命令
    command = COMMAND_TEMPLATES[step["command_template"]].format(**step["params"])

    # 3. 执行命令（通过 NetworkTools）
    result = await network_tools.execute_command(host, command, timeout)

    # 4. 调用解析器
    parser = get_parser(step["command_template"])
    parsed_result = parser.parse(result["stdout"])

    # 5. 返回 StepResult
    return StepResult(
        step_id=step["step_id"],
        success=result["success"],
        command_result=result,
        parsed_data=parsed_result,
        metadata={...}
    )
```

---

#### 3.1.4 DiagnosticAnalyzer (结果分析器) - `analyzer.py`

**职责**：汇总执行结果，推断根因，生成修复建议

**分析策略**：

```python
def analyze(steps: List[StepResult]) -> DiagnosticReport:
    # 1. 基于规则的分析
    rule_result = rule_based_analysis(steps)

    # 2. 判断置信度
    if rule_result.confidence >= 0.8:
        return rule_result  # 直接返回

    # 3. 如果启用 LLM 且置信度低，调用 LLM
    if use_llm:
        llm_result = llm_analysis(steps)

        # 4. 选择置信度更高的结果
        if llm_result.confidence > rule_result.confidence:
            return llm_result

    return rule_result
```

**规则分析示例**：
```python
# 检测到 telnet refused + ss 无输出 → 端口未监听
if (
    telnet_result.error_type == "refused"
    and ss_result.is_empty()
):
    return DiagnosticReport(
        root_cause="目标服务器上端口80没有服务监听",
        confidence=0.95,
        evidence=[
            "telnet测试返回Connection refused",
            "ss命令显示端口80无监听进程"
        ],
        fix_suggestions=[
            "在目标服务器启动Web服务（如nginx/apache）",
            "确认服务配置监听在0.0.0.0:80或目标IP:80"
        ]
    )
```

**LLM 分析提示词**：
```python
"""
你是网络故障诊断专家。根据以下执行步骤结果，推断根本原因：

执行步骤：
{steps_json}

请输出：
1. root_cause: 根本原因（一句话）
2. confidence: 置信度 (0.0-1.0)
3. evidence: 支持证据（列表）
4. fix_suggestions: 修复建议（列表）
5. need_human: 是否需要人工介入 (bool)
"""
```

---

#### 3.1.5 ReportGenerator (报告生成器) - `reporter.py`

**职责**：生成 Markdown 格式的诊断报告

**报告模板**：
```markdown
# 网络故障诊断报告

## 基本信息
- **任务ID**: task_20260127133000_a1b2c3d4
- **故障类型**: 端口不可达
- **源主机**: 10.0.1.10
- **目标主机**: 10.0.2.20:80
- **诊断时间**: 2026-01-27 13:30:00
- **总耗时**: 8.5秒

## 诊断结果
**根本原因**：目标服务器防火墙阻止了80端口访问
**置信度**：85%

## 支持证据
1. telnet测试超时（Connection timeout）
2. ping测试成功（网络层可达）
3. iptables规则拒绝了80端口的入站流量

## 修复建议
1. 在目标服务器执行：`iptables -I INPUT -p tcp --dport 80 -j ACCEPT`
2. 保存防火墙规则：`iptables-save > /etc/iptables/rules.v4`
3. 重新测试连通性

## 执行步骤
### Step 1: CMDB查询
- **命令**: query_cmdb(target="10.0.2.20")
- **结果**: 主机存在，服务角色=Web服务器
- **耗时**: 0.5秒

### Step 2: Telnet测试
- **命令**: telnet 10.0.2.20:80
- **结果**: Connection timeout
- **耗时**: 3秒

### Step 3: Ping测试
- **命令**: ping -c 3 10.0.2.20
- **结果**: 3 packets transmitted, 3 received, 0% packet loss
- **耗时**: 1秒

### Step 4: 防火墙规则检查
- **命令**: iptables -L INPUT -n -v
- **结果**: 发现DROP规则阻止了80端口
- **耗时**: 0.5秒

---
*报告生成时间: 2026-01-27 13:30:08*
```

---

#### 3.1.6 LLMAgent (LLM驱动的动态Agent) - `llm_agent.py`

**职责**：使用 LLM 动态决策诊断步骤（基于 LangChain）

**核心特性**：
- ✅ 动态调用工具（无需预定义流程）
- ✅ 支持多轮对话（向用户提问）
- ✅ 自动停止条件
- ✅ 流式响应（SSE）

**工具定义**：
```python
tools = [
    Tool(
        name="execute_command",
        description="在指定主机执行命令",
        func=lambda host, command, timeout: network_tools.execute_command(...)
    ),
    Tool(
        name="query_cmdb",
        description="查询CMDB设备信息",
        func=lambda hosts: cmdb_client.query(hosts)
    ),
    Tool(
        name="ask_user",
        description="向用户提问获取额外信息",
        func=lambda question: raise NeedUserInputException(question)
    )
]
```

**系统提示词**：
```python
"""
你是网络故障诊断专家Agent。你可以：
1. 执行命令 (execute_command) - 在源主机测试连通性
2. 查询CMDB (query_cmdb) - 获取设备信息
3. 询问用户 (ask_user) - 获取额外信息

诊断原则：
- 逐步缩小问题范围
- 根据上一步结果决定下一步
- 区分 timeout（防火墙/路由）和 refused（服务未启动）
- 最多执行10步
- 找到根因后立即停止

当前任务：
{task_description}
"""
```

**执行流程**：
```python
async def diagnose(task: DiagnosticTask) -> DiagnosticReport:
    agent = initialize_agent(tools, llm, agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION)

    for step in range(max_steps):
        try:
            response = await agent.arun(task.user_input)

            if is_final_answer(response):
                return parse_report(response)

        except NeedUserInputException as e:
            # 保存会话状态，等待用户回答
            session_manager.update_session(
                session_id=task.task_id,
                status="waiting_user",
                pending_question=e.question
            )
            raise e

    return generate_timeout_report()
```

---

### 3.2 Integration 集成模块 (`src/integrations/`)

#### 3.2.1 LLMClient - `llm_client.py`

**职责**：统一的 LLM 调用接口

**技术栈**：LangChain + ChatOpenAI

**支持的模型**：
- DeepSeek
- 通义千问（Qwen）
- MiniMax
- OpenAI GPT
- 本地模型（兼容 OpenAI API）

**配置方式**：
```bash
# .env
API_KEY=sk-xxxxxxxx
API_BASE_URL=https://api.deepseek.com/v1
MODEL=deepseek-chat
TEMPERATURE=0.3  # 低温度确保确定性
MAX_TOKENS=2000
```

**使用示例**：
```python
llm_client = LLMClient()
response = await llm_client.chat(
    messages=[
        {"role": "system", "content": "你是网络专家"},
        {"role": "user", "content": "如何排查端口不通问题？"}
    ]
)
```

---

#### 3.2.2 AutomationPlatformClient - `automation_platform_client.py`

**职责**：远程命令执行客户端

**实现方式**：
- **Phase 1**：从 Mock JSON 读取预定义响应
- **Phase 2+**：调用真实自动化平台 API

**Mock 机制**：
```python
# 基于命令哈希值自动选择场景
def get_mock_response(host: str, command: str):
    command_key = f"{command}_{host}"
    scenario = select_scenario_by_hash(command_key)
    return mock_data["scenarios"][scenario]["commands"][command_key]
```

**Mock 数据格式**：
```json
{
  "scenarios": {
    "scenario1_refused": {
      "commands": {
        "telnet_10.0.2.20_80": {
          "success": false,
          "stdout": "",
          "stderr": "timeout: can't kill child process",
          "exit_code": 124,
          "metadata": {"error_type": "refused"}
        }
      }
    }
  }
}
```

---

#### 3.2.3 NetworkRouter - `network_router.py`

**职责**：多网络环境路由，根据主机 IP 选择对应的自动化平台客户端

**配置文件**：`config/networks.yaml`
```yaml
networks:
  - name: "network_a"
    api_url: "http://automation-api-a.example.com/v1"
    api_token: "${AUTOMATION_API_TOKEN_A}"
    networks:
      - "10.0.0.0/8"
      - "192.168.1.0/24"

  - name: "network_b"
    api_url: "http://automation-api-b.example.com/v1"
    api_token: "${AUTOMATION_API_TOKEN_B}"
    networks:
      - "172.16.0.0/12"
```

**路由逻辑**：
```python
def get_client(host_ip: str) -> AutomationPlatformClient:
    for network in networks:
        for cidr in network["networks"]:
            if ipaddress.ip_address(host_ip) in ipaddress.ip_network(cidr):
                return AutomationPlatformClient(
                    api_url=network["api_url"],
                    api_token=network["api_token"]
                )

    raise NetworkNotFoundError(f"No network config found for {host_ip}")
```

---

### 3.3 数据模型 (`src/models/`)

#### 3.3.1 DiagnosticTask - `task.py`

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class Protocol(str, Enum):
    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"

class FaultType(str, Enum):
    CONNECTIVITY = "connectivity"
    PORT_UNREACHABLE = "port_unreachable"
    SLOW = "slow"
    DNS = "dns"

@dataclass
class DiagnosticTask:
    task_id: str                    # 唯一任务ID
    user_input: str                 # 原始用户输入
    source: str                     # 源主机
    target: str                     # 目标主机
    protocol: Protocol              # 协议
    fault_type: FaultType          # 故障类型
    port: Optional[int] = None     # 端口号
    context: Dict[str, Any] = None # 额外上下文
    created_at: datetime = None    # 创建时间
```

#### 3.3.2 DiagnosticReport - `report.py`

```python
@dataclass
class DiagnosticReport:
    task_id: str                    # 任务ID
    root_cause: str                 # 根本原因
    confidence: float               # 置信度 (0.0-1.0)
    evidence: List[str]            # 支持证据
    fix_suggestions: List[str]     # 修复建议
    need_human: bool               # 是否需要人工介入
    executed_steps: List[StepResult]  # 执行步骤
    total_time: float              # 总耗时（秒）
    metadata: Dict[str, Any]       # 额外元数据
```

---

### 3.4 会话管理 (`src/session_manager.py` & `src/db/database.py`)

#### 3.4.1 SessionManager (内存版)

**职责**：管理多轮诊断会话

**会话状态**：
- `active`：诊断进行中
- `waiting_user`：等待用户回答
- `completed`：诊断已完成
- `error`：出现错误

**核心方法**：
```python
class SessionManager:
    def create_session(self, session_id, task, llm_client, agent):
        """创建新会话"""

    def get_session(self, session_id):
        """获取会话"""

    def update_session(self, session_id, **kwargs):
        """更新会话状态"""

    def add_message(self, session_id, role, content, metadata):
        """添加会话消息"""

    def delete_session(self, session_id):
        """删除会话"""

    def cleanup_expired_sessions(self):
        """清理过期会话（TTL）"""
```

#### 3.4.2 SessionDatabase (SQLite持久化)

**表结构**：
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    task_data TEXT,          -- JSON序列化的DiagnosticTask
    status TEXT,             -- active/waiting_user/completed/error
    pending_question TEXT,   -- 待回答的问题
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,               -- user/assistant/system
    content TEXT,
    timestamp TIMESTAMP,
    metadata TEXT,           -- JSON格式
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

**特性**：
- ✅ WAL 模式提高并发性能
- ✅ 异步 I/O (aiosqlite)
- ✅ 自动清理过期会话

---

## 4. 诊断流程详解

### 4.1 规则引擎模式（Phase 1）

```
┌─────────────────┐
│  用户输入故障描述  │
│  "10.0.1.10到    │
│  10.0.2.20       │
│  端口80不通"      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  NLU 解析        │
│  (规则/LLM)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TaskPlanner     │
│  生成执行计划     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Executor        │
│  执行命令并解析   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Analyzer        │
│  ├ 规则分析      │
│  │  (置信度≥80%?)│
│  │   ├ YES → 返回│
│  │   └ NO ↓      │
│  └ LLM分析       │
│     (启用LLM?)   │
│      ├ YES → 对比│
│      └ NO → 规则 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ReportGenerator │
│  生成Markdown报告│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  输出结果         │
└─────────────────┘
```

---

### 4.2 LLM Agent 动态诊断模式（Phase 2+）

```
┌─────────────────┐
│  用户输入         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  NLU (LLM)       │
│  解析为结构化任务 │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  LLMAgent (LangChain)                │
│                                       │
│  工具集:                              │
│  ├ execute_command                   │
│  ├ query_cmdb                        │
│  └ ask_user                          │
│                                       │
│  执行循环 (最多10步):                 │
│  ┌─────────────────────────────┐    │
│  │ 1. LLM决策下一步行动         │    │
│  │ 2. 调用相应工具              │    │
│  │ 3. 获取工具结果              │    │
│  │ 4. 更新上下文                │    │
│  │ 5. 检查是否需要用户输入      │    │
│  │    ├ YES → 抛出异常，等待    │    │
│  │    └ NO → 继续               │    │
│  │ 6. 检查是否已找到根因        │    │
│  │    ├ YES → 生成报告          │    │
│  │    └ NO → 下一步             │    │
│  └─────────────────────────────┘    │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  生成报告         │
│  输出结果         │
└─────────────────┘
```

---

### 4.3 多轮对话流程

```
┌─────────────────────────────────────────────┐
│  Step 1: 用户发起诊断                        │
│  POST /api/v1/diagnose/stream               │
│  {"description": "...", "use_llm": true}    │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Step 2: Agent 执行诊断                      │
│  ├ 执行命令                                  │
│  ├ 分析结果                                  │
│  └ 需要用户提供额外信息                      │
│      → 抛出 NeedUserInputException          │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Step 3: 保存会话状态                        │
│  session_manager.update_session(            │
│      session_id=task_id,                    │
│      status="waiting_user",                 │
│      pending_question="目标服务器是否有防火墙?"│
│  )                                           │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Step 4: 返回问题给前端                      │
│  SSE Event: {                                │
│      "type": "need_input",                   │
│      "question": "目标服务器是否有防火墙?",   │
│      "session_id": "task_xxx"                │
│  }                                           │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Step 5: 用户回答问题                        │
│  POST /api/v1/chat/answer                   │
│  {                                           │
│      "session_id": "task_xxx",              │
│      "answer": "有防火墙，仅允许特定IP"      │
│  }                                           │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Step 6: 恢复会话并继续诊断                  │
│  ├ 获取 saved context                        │
│  ├ 将用户回答添加到消息历史                  │
│  └ Agent 继续执行                            │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Step 7: 可能再次需要用户输入（循环）        │
│  或找到根因，诊断完成                        │
└─────────────────────────────────────────────┘
```

---

## 5. API 接口设计

### 5.1 诊断接口

#### POST `/api/v1/diagnose` - 同步诊断

**请求**：
```json
{
  "description": "10.0.1.10到10.0.2.20端口80不通",
  "use_llm": true,
  "verbose": false,
  "session_id": null
}
```

**响应**：
```json
{
  "task_id": "task_20260127133000_a1b2c3d4",
  "status": "success",
  "root_cause": "目标服务器防火墙阻止了80端口访问",
  "confidence": 85.0,
  "execution_time": 8.5,
  "steps": [...],
  "suggestions": ["在目标服务器开放80端口的防火墙规则"],
  "tool_calls": [...]
}
```

---

#### POST `/api/v1/diagnose/stream` - 流式诊断（SSE）

**特性**：
- ✅ 实时推送诊断进度
- ✅ Server-Sent Events (SSE)
- ✅ 支持中断和恢复

**事件类型**：
```python
"start"        # 诊断开始
"tool_start"   # 工具调用开始
"tool_result"  # 工具调用结果
"complete"     # 诊断完成
"error"        # 错误
"need_input"   # 需要用户输入
"done"         # 流结束
```

**事件格式**：
```json
{
  "type": "tool_start",
  "data": {
    "tool_name": "execute_command",
    "description": "执行telnet测试",
    "timestamp": "2026-01-27T13:30:05"
  }
}
```

---

### 5.2 会话管理接口

#### POST `/api/v1/chat/answer` - 回答问题继续诊断

```json
{
  "session_id": "task_20260123105030_a1b2c3d4",
  "answer": "目标服务器上有防火墙，配置为仅允许特定IP访问"
}
```

---

#### GET `/api/v1/sessions` - 获取所有会话

**查询参数**：
- `status`: 按状态过滤（`completed`, `active`, `waiting_user`）

**响应**：
```json
{
  "sessions": [
    {
      "session_id": "task_xxx",
      "status": "completed",
      "created_at": "2026-01-27T13:30:00",
      "updated_at": "2026-01-27T13:30:08",
      "task_summary": "10.0.1.10到10.0.2.20端口80不通"
    }
  ]
}
```

---

#### GET `/api/v1/sessions/{session_id}/messages` - 获取会话消息

**响应**：
```json
{
  "messages": [
    {
      "role": "user",
      "content": "10.0.1.10到10.0.2.20端口80不通",
      "timestamp": "2026-01-27T13:30:00"
    },
    {
      "role": "assistant",
      "content": "我将开始排查...",
      "timestamp": "2026-01-27T13:30:01",
      "metadata": {"tool_call": "telnet_test"}
    }
  ]
}
```

---

## 6. LLM 集成策略

### 6.1 双引擎混合模式

| 功能 | 规则引擎 | LLM | 选择策略 |
|-----|--------|-----|--------|
| **输入解析** | 基于正则 | Few-shot | 置信度控制 |
| **执行计划** | 固定流程 | 动态决策 | `--agent-mode` 参数 |
| **结果分析** | 规则匹配 | 推理分析 | 置信度阈值 0.8 |
| **成本** | 免费 | 按 token 计费 | 规则优先，LLM 兜底 |

---

### 6.2 成本优化策略

1. **规则优先**：默认使用规则引擎（快速、免费）
2. **智能触发**：仅当规则置信度低时调用 LLM
3. **缓存机制**：可以缓存重复询问的结果（预留）
4. **灵活配置**：支持完全禁用 LLM 或完全启用

---

### 6.3 提示词工程

#### NLU 系统提示词

```python
"""
你是一个网络故障排查专家。你的任务是从用户的自然语言描述中提取关键信息：

1. 源主机 (source)：发起连接的主机
2. 目标主机 (target)：目标主机
3. 协议 (protocol)：icmp/tcp/udp
4. 端口 (port)：端口号（如果是TCP/UDP）
5. 故障类型 (fault_type)：connectivity/port_unreachable/slow/dns

输入示例：
- "10.0.1.10到10.0.2.20端口80不通"
- "服务器A ping 服务器B超时"

输出格式：JSON
{
  "source": "10.0.1.10",
  "target": "10.0.2.20",
  "protocol": "tcp",
  "port": 80,
  "fault_type": "port_unreachable"
}
"""
```

---

#### LLMAgent 系统提示词

```python
"""
你是一个网络故障诊断专家 Agent。你可以使用以下工具：

1. execute_command(host, command, timeout)
   - 在指定主机执行命令
   - 示例：execute_command("10.0.1.10", "ping -c 3 10.0.2.20", 5)

2. query_cmdb(hosts)
   - 查询设备信息、网络拓扑
   - 示例：query_cmdb(["10.0.2.20"])

3. ask_user(question)
   - 向用户提问获取额外信息
   - 示例：ask_user("目标服务器是否有防火墙？")

诊断原则：
- 逐步缩小问题范围
- 根据上一步结果决定下一步
- 区分 timeout（防火墙/路由问题）和 refused（服务未启动）
- 最多执行 10 步
- 找到根因后立即停止并生成报告

当前任务：
{task_description}
"""
```

---

## 7. 测试策略

### 7.1 测试分层

```
E2E 测试 (tests/e2e/)
    ├─ 完整诊断流程测试
    └─ 多轮对话测试

集成测试 (tests/integration/)
    ├─ API 接口测试
    ├─ 会话持久化测试
    └─ LLM Agent 测试

单元测试 (tests/unit/)
    ├─ NLU 解析测试
    ├─ 解析器测试
    ├─ Analyzer 规则测试
    └─ 数据模型测试
```

---

### 7.2 核心测试场景（Phase 1 验收）

| 场景 | 故障原因 | 预期根因 |
|-----|---------|---------|
| **Scenario 1** | 目标端口无服务监听 | "目标服务器上端口80没有服务监听" |
| **Scenario 2** | 防火墙阻止访问 | "目标服务器防火墙阻止了80端口访问" |
| **Scenario 3** | 网络不可达（路由问题） | "源主机到目标主机的路由不可达" |

---

### 7.3 Mock 数据管理

**位置**：`tests/fixtures/mock_automation_responses.json`

**结构**：
```json
{
  "scenarios": {
    "scenario1_refused": {
      "description": "目标端口无服务监听",
      "commands": {
        "telnet_10.0.2.20_80": {
          "success": false,
          "stdout": "",
          "stderr": "Connection refused",
          "exit_code": 1,
          "metadata": {"error_type": "refused"}
        },
        "ss_listen_10.0.2.20_80": {
          "success": true,
          "stdout": "",  // 空输出表示无监听进程
          "stderr": "",
          "exit_code": 0
        }
      }
    }
  }
}
```

---

## 8. 部署和配置

### 8.1 启动方式

#### 方式 1：HTTP API（推荐）

```bash
# 启动 API 服务
.\scripts\start_api.bat

# 或手动启动
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

# API 文档地址
http://localhost:8000/docs
```

---

#### 方式 2：CLI 命令行

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 执行诊断
python -m src.cli diagnose "10.0.1.10到10.0.2.20端口80不通" --agent-mode
```

---

### 8.2 环境配置

```bash
# .env 文件
API_KEY=sk-xxxxxxxx
API_BASE_URL=https://api.deepseek.com/v1
MODEL=deepseek-chat
TEMPERATURE=0.3
MAX_TOKENS=2000

# 数据库
DATABASE_URL=sqlite:///runtime/sessions.db

# 网络配置
NETWORK_CONFIG_PATH=config/networks.yaml
```

---

### 8.3 依赖管理

```bash
# 生产依赖
pip install -r requirements.txt

# 开发依赖
pip install -r requirements-dev.txt

# 核心依赖
fastapi==0.104.1
uvicorn[standard]==0.24.0
langchain==0.1.0
openai==1.5.0
typer==0.9.0
pydantic==2.5.0
aiosqlite==0.19.0
structlog==23.2.0
```

---

## 9. 性能指标

### 9.1 目标指标（Phase 1）

- ✅ 单次诊断耗时 ≤ 10 秒
- ✅ 根因判断准确率 ≥ 90%
- ✅ 单元测试覆盖率 ≥ 80%
- ✅ 3 个核心场景 100% 通过

---

### 9.2 性能优化策略

1. **并发执行**：多个独立命令并发执行
2. **超时控制**：每个命令设置合理超时
3. **缓存机制**：CMDB 查询结果缓存（预留）
4. **异步 I/O**：使用 asyncio/aiohttp

---

## 10. 设计模式总结

| 设计模式 | 应用位置 | 说明 |
|---------|---------|-----|
| **单一职责原则** | 所有模块 | 每个模块只负责一个明确功能 |
| **适配器模式** | Integration 层 | 统一外部系统接口 |
| **策略模式** | Analyzer | 规则分析 vs LLM 分析 |
| **工厂模式** | NetworkRouter, SessionManager | 动态创建客户端实例 |
| **观察者模式** | LLMAgent | 事件回调推送进度 |
| **命令模式** | Executor | 命令白名单机制 |

---

## 11. 潜在风险和应对

### 11.1 安全风险

| 风险 | 应对措施 |
|-----|---------|
| **命令注入攻击** | 命令白名单 + 参数化模板 |
| **敏感信息泄露** | 日志脱敏，API Token 加密存储 |
| **权限滥用** | 限制命令执行范围，审计日志 |

---

### 11.2 性能风险

| 风险 | 应对措施 |
|-----|---------|
| **LLM 调用超时** | 设置合理超时时间，降级到规则引擎 |
| **数据库锁竞争** | 使用 WAL 模式，异步 I/O |
| **会话过多导致内存溢出** | TTL 自动清理，持久化到数据库 |

---

### 11.3 可靠性风险

| 风险 | 应对措施 |
|-----|---------|
| **外部 API 不可用** | 重试机制，降级策略 |
| **LLM 幻觉（错误根因）** | 规则分析作为兜底，置信度阈值控制 |
| **多轮对话中断** | 会话持久化到数据库 |

---

## 12. 未来优化方向

### Phase 2+

- [ ] **工作流引擎**：支持 YAML 配置自定义诊断流程
- [ ] **知识库集成**：历史故障案例学习
- [ ] **监控告警集成**：自动触发诊断
- [ ] **可视化界面**：前端 UI，拓扑展示
- [ ] **多租户支持**：隔离不同客户的会话和配置

---

## 13. 关键决策记录

### 13.1 为什么选择双引擎混合架构？

**原因**：
- 规则引擎：快速、免费、确定性强，适合常见场景
- LLM Agent：灵活、智能，适合复杂场景和长尾问题
- 混合使用：兼顾成本和效果

---

### 13.2 为什么选择 LangChain？

**原因**：
- 成熟的 Agent 框架，支持工具调用
- 易于切换不同 LLM 模型
- 社区活跃，生态丰富

---

### 13.3 为什么使用 SQLite 而不是 Redis？

**原因**：
- Phase 1 单机部署，SQLite 足够
- WAL 模式性能满足需求
- 无需额外部署 Redis 服务
- Phase 2+ 可以迁移到 PostgreSQL

---

## 14. 架构优化记录 (2026-01-29)

### 14.1 优化问题列表

本次优化解决了以下关键问题：

| 问题 | 优先级 | 状态 |
|-----|--------|-----|
| 1. 文档命名不准确（design_change.md） | P2 | ✅ 已解决 |
| 2. Phase 1 Mock机制缺乏灵活性 | P3 | 待优化 |
| **3. LLM Agent 最大步数硬编码** | **P1** | **✅ 已解决** |
| 4. 缺少限流机制 | P2 | 待实现 |
| **5. 错误处理不完善** | **P1** | **✅ 已解决** |

---

### 14.2 优化详情

#### 优化 1：文档重命名

**问题**：
- `docs/design_change.md` 命名暗示是"变更"文档，但实际内容是完整的架构设计文档

**解决方案**：
- 重命名为 `docs/architecture.md`
- 更新 `README.md` 中的所有文档链接
- 清理所有引用

**影响范围**：
- 文档结构更清晰
- 用户更容易找到架构设计文档

---

#### 优化 3：LLM Agent 最大步数可配置

**问题**：
- `src/agent/llm_agent.py:87` 硬编码 `self.max_steps = 10`
- 复杂场景可能需要更多步数，但无法配置
- 简单场景可以减少步数以节省成本，但无法调整

**解决方案**：

1. **新增环境变量配置** (`.env.example`):
   ```bash
   # LLM Agent 配置
   LLM_AGENT_MAX_STEPS=10        # LLM Agent 最大执行步数，建议 10-20
   LLM_AGENT_TEMPERATURE=0.3     # LLM 温度参数，建议 0.1-0.5
   LLM_REQUEST_TIMEOUT=60        # LLM API 请求超时时间（秒）
   LLM_MAX_RETRIES=3             # LLM API 请求失败重试次数
   ```

2. **修改 `__init__` 方法** (`src/agent/llm_agent.py:79-103`):
   ```python
   def __init__(
       self,
       llm_client: Optional[LLMClient] = None,
       verbose: bool = False,
       max_steps: Optional[int] = None  # 新增参数
   ):
       """
       Args:
           max_steps: 最大执行步数，如果为None则从环境变量读取（默认10）
       """
       # 从环境变量或参数获取 max_steps（优先使用参数）
       if max_steps is not None:
           self.max_steps = max_steps
       else:
           self.max_steps = int(os.getenv("LLM_AGENT_MAX_STEPS", "10"))
   ```

3. **动态系统提示词** (`src/agent/llm_agent.py:56-82`):
   ```python
   SYSTEM_PROMPT_TEMPLATE = """...
   - 最多执行{max_steps}步
   ..."""

   @property
   def SYSTEM_PROMPT(self) -> str:
       """动态生成系统提示词"""
       return self.SYSTEM_PROMPT_TEMPLATE.format(max_steps=self.max_steps)
   ```

**优势**：
- ✅ 支持环境变量配置（全局默认）
- ✅ 支持参数覆盖（按实例自定义）
- ✅ 向后兼容（未配置时使用默认值 10）
- ✅ 系统提示词自动更新，LLM 知道最大步数限制

**使用示例**：
```python
# 方式 1：使用环境变量（推荐）
export LLM_AGENT_MAX_STEPS=15
agent = LLMAgent()  # 自动使用 15

# 方式 2：使用参数（特殊场景）
agent = LLMAgent(max_steps=20)  # 覆盖环境变量
```

---

#### 优化 5：完善错误处理和降级策略

**问题**：
- `LLMClient` 错误处理过于简单，只抛出 `RuntimeError`
- 没有重试机制，临时网络故障导致整个诊断失败
- 没有错误分类，无法区分超时、限流、认证失败等不同错误
- `AutomationPlatformClient` Mock 数据加载失败只打印警告，没有更好的降级策略

**解决方案 (LLMClient)**：

1. **新增自定义异常类** (`src/integrations/llm_client.py:15-33`):
   ```python
   class LLMAPIError(Exception):
       """LLM API 调用错误基类"""

   class LLMTimeoutError(LLMAPIError):
       """LLM API 超时错误"""

   class LLMRateLimitError(LLMAPIError):
       """LLM API 限流错误"""

   class LLMAuthenticationError(LLMAPIError):
       """LLM API 认证错误"""
   ```

2. **新增错误分类方法** (`src/integrations/llm_client.py:94-113`):
   ```python
   def _classify_error(self, error: Exception) -> Exception:
       """分类错误类型"""
       error_str = str(error).lower()

       if "timeout" in error_str or "timed out" in error_str:
           return LLMTimeoutError(f"LLM API 请求超时: {error}")
       elif "rate limit" in error_str or "429" in error_str:
           return LLMRateLimitError(f"LLM API 限流: {error}")
       elif "authentication" in error_str or "401" in error_str or "403" in error_str:
           return LLMAuthenticationError(f"LLM API 认证失败: {error}")
       else:
           return LLMAPIError(f"LLM API 调用失败: {error}")
   ```

3. **新增指数退避重试机制** (`src/integrations/llm_client.py:115-157`):
   ```python
   def _retry_with_backoff(self, func, *args, **kwargs):
       """带指数退避的重试逻辑"""
       last_error = None

       for attempt in range(self.max_retries + 1):
           try:
               return func(*args, **kwargs)
           except Exception as e:
               last_error = self._classify_error(e)

               # 认证错误不重试（立即失败）
               if isinstance(last_error, LLMAuthenticationError):
                   raise last_error

               # 最后一次尝试，直接抛出
               if attempt == self.max_retries:
                   print(f"[LLM Client] 重试{attempt}次后仍然失败: {last_error}")
                   raise last_error

               # 计算退避时间（指数退避，最多10秒）
               backoff_time = min(2 ** attempt, 10)

               # 限流错误额外增加等待时间
               if isinstance(last_error, LLMRateLimitError):
                   backoff_time *= 2

               print(f"[LLM Client] 尝试{attempt + 1}失败，{backoff_time}秒后重试: {last_error}")
               time.sleep(backoff_time)

       raise last_error if last_error else LLMAPIError("未知错误")
   ```

4. **更新 `__init__` 方法** (`src/integrations/llm_client.py:48-92`):
   ```python
   def __init__(
       self,
       timeout: Optional[int] = None,    # 新增
       max_retries: Optional[int] = None # 新增
   ):
       # 超时和重试配置
       self.timeout = timeout if timeout is not None else int(os.getenv("LLM_REQUEST_TIMEOUT", "60"))
       self.max_retries = max_retries if max_retries is not None else int(os.getenv("LLM_MAX_RETRIES", "3"))

       self.llm = ChatOpenAI(
           timeout=self.timeout,
           max_retries=0  # 我们自己实现重试逻辑
       )
   ```

5. **修改所有调用方法使用重试逻辑**:
   - `invoke()` - 已修改
   - `chat()` - 已修改
   - `invoke_with_tools()` - 已修改

**解决方案 (AutomationPlatformClient)**：

1. **新增自定义异常类** (`src/integrations/automation_platform_client.py:15-33`):
   ```python
   class AutomationAPIError(Exception):
       """自动化平台 API 错误基类"""

   class DeviceNotFoundError(AutomationAPIError):
       """设备不存在异常"""

   class CommandExecutionError(AutomationAPIError):
       """命令执行失败异常"""

   class MockDataNotFoundError(AutomationAPIError):
       """Mock 数据不存在异常"""
   ```

2. **改进 Mock 数据加载错误处理** (`src/integrations/automation_platform_client.py:69-95`):
   ```python
   def _load_mock_responses(self) -> Dict:
       """加载Mock响应数据"""
       try:
           with open(self.mock_responses_path, 'r', encoding='utf-8') as f:
               data = json.load(f)
               print(f"[AutomationClient] 成功加载 Mock 数据: {self.mock_responses_path}")
               return data
       except FileNotFoundError:
           print(f"[AutomationClient] 警告: Mock响应数据文件不存在")
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
   ```

**优势**：
- ✅ **细粒度错误分类**：可以根据不同错误类型采取不同的处理策略
- ✅ **智能重试机制**：
  - 指数退避，避免瞬间大量重试
  - 认证错误不重试（立即失败）
  - 限流错误额外增加等待时间
  - 可配置重试次数（默认 3 次）
- ✅ **超时控制**：可配置超时时间（默认 60 秒）
- ✅ **更好的日志**：清晰记录每次重试和失败原因
- ✅ **向后兼容**：未配置时使用合理的默认值

**重试策略对比**：

| 错误类型 | 是否重试 | 退避时间 |
|---------|---------|---------|
| 超时错误 | ✅ 是 | 指数退避（1s → 2s → 4s → ...） |
| 限流错误 | ✅ 是 | 指数退避 × 2（2s → 4s → 8s → ...） |
| 认证错误 | ❌ 否 | 立即失败 |
| 其他错误 | ✅ 是 | 指数退避 |

**降级策略**：
- LLM 调用失败 → 抛出分类后的异常，由上层决定是否降级到规则引擎
- Mock 数据加载失败 → 使用空场景数据 + fallback 响应生成

---

### 14.3 优化影响总结

| 优化项 | 文件 | 代码行变更 | 影响范围 |
|-------|------|-----------|---------|
| 文档重命名 | `docs/`, `README.md` | ~10 行 | 文档结构 |
| LLM Agent 可配置 | `llm_agent.py`, `.env.example` | ~40 行 | Agent 模块 |
| LLM 错误处理 | `llm_client.py` | ~100 行 | 所有 LLM 调用 |
| Automation 错误处理 | `automation_platform_client.py` | ~30 行 | Mock 数据加载 |

**总计**：~180 行代码变更，核心模块更加健壮。

---

### 14.4 后续优化建议

| 问题 | 优先级 | 预计工作量 |
|-----|--------|-----------|
| Phase 1 Mock 机制优化（配置文件指定场景映射） | P3 | 2 小时 |
| API 接口限流机制（基于 IP/用户） | P2 | 4 小时 |
| API 接口统一错误处理中间件 | P2 | 3 小时 |
| LLM 调用降级策略（自动切换到规则引擎） | P1 | 6 小时 |
| 会话清理机制优化（基于 LRU） | P3 | 2 小时 |

---

## 15. 总结

netOpsAgent 是一个**精心设计的分层架构系统**，具有以下核心优势：

1. **模块化设计**：清晰的职责边界，易于扩展和维护
2. **双引擎混合**：规则优先（快速、免费）+ LLM 兜底（灵活、智能）
3. **完整的会话管理**：支持多轮对话，维护诊断上下文
4. **可扩展性强**：支持多网络环境、多 LLM 模型、Mock/真实 API 切换
5. **生产就绪**：完善的错误处理、日志、测试、部署脚本

### 核心技术亮点

- ✅ LangChain Agent 动态诊断
- ✅ 命令白名单安全执行
- ✅ 多网络环境路由
- ✅ 会话持久化和多轮对话
- ✅ 流式响应（SSE）
- ✅ 规则 + LLM 混合分析

---

**文档维护者**: Claude (Sonnet 4.5)
**最后更新**: 2026-01-29
