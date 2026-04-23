# 访问关系查询数据流文档

## 概述

当用户提问"XX系统有什么访问关系？"时，系统会通过一系列组件协同工作，从数据库查询访问关系数据并返回给用户。本文档详细说明了这个查询流程的核心走向、入口点、LLM调用以及工具调用的具体代码位置。

---

## 1. 核心数据流程图

```
用户提问 "XX系统有什么访问关系？"
    ↓
[API 入口] src/api.py::chat_stream()
    ↓
[意图路由] src/agent/intent_router.py::IntentRouter.route_message()
    ↓
判断：是否为访问关系查询？
    ├─ 是 → [通用聊天] src/api.py::general_chat_stream_v2()
    └─ 否 → 其他路由（诊断/澄清等）
    ↓
[RAG 跳过检测] src/api.py::is_access_relation_data_query()
    ↓
判断：是否跳过 RAG？
    ├─ 是 → 跳过知识库检索，直接进入 LLM 工具调用
    └─ 否 → 使用 RAG 增强回答
    ↓
[通用聊天 Agent] src/agent/general_chat_agent.py::GeneralChatToolAgent.run()
    ↓
[LLM 工具调用] LLM 决策调用 query_access_relations 工具
    ↓
[工具执行] src/agent/general_chat_agent.py::query_access_relations_func()
    ↓
[数据库查询] src/db/database.py::SessionDatabase.query_access_relations()
    ↓
[结果返回] 返回访问关系数据（JSON 格式）
    ↓
[LLM 格式化] LLM 将结果格式化为 Markdown 表格
    ↓
[流式输出] 通过 SSE 流式返回给前端
    ↓
用户看到访问关系表格
```

---

## 2. 关键入口点

### 2.1 HTTP API 入口

**文件**: `src/api.py`

**函数**: `chat_stream(request: ChatStreamRequest)`

**位置**: 第 ~300 行

**功能**: 统一的聊天流式入口，接收用户消息并进行后端意图路由。

```python
@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    """Unified streaming entrypoint with backend intent routing."""
    session = await session_manager.get_session(request.session_id) if request.session_id else None
    decision = intent_router.route_message(request.message, session=session)
    
    # 根据意图路由到不同的处理流程
    if decision.route == "start_diagnosis":
        return await diagnose_stream(...)
    elif decision.route == "continue_diagnosis":
        return await chat_answer(...)
    elif decision.route == "clarify":
        return _build_clarify_stream_response(...)
    else:
        # 访问关系查询走这里
        return await general_chat_stream_v2(...)
```

---

## 3. 意图路由

### 3.1 意图路由器

**文件**: `src/agent/intent_router.py`

**类**: `IntentRouter`

**方法**: `route_message(message: str, session: Optional[Any] = None) -> IntentDecision`

**位置**: 第 ~50 行

**功能**: 根据用户消息内容判断意图类型（诊断、澄清、通用聊天等）。

**关键逻辑**:

```python
# 访问关系查询检测
ACCESS_RELATION_RE = re.compile(
    r"(访问关系|哪些系统访问|谁访问|被哪些系统访问|之间.*访问关系)",
    re.IGNORECASE,
)

def route_message(self, message: str, session: Optional[Any] = None) -> IntentDecision:
    is_access_relation_query = bool(ACCESS_RELATION_RE.search(text))
    
    if is_access_relation_query:
        return IntentDecision(
            route="general_chat",
            confidence=0.95,
            reason="access_relation_query",
        )
```

**输出**: 返回 `IntentDecision` 对象，包含路由类型、置信度和原因。

---

## 4. RAG 跳过检测

### 4.1 访问关系数据查询检测

**文件**: `src/api.py`

**函数**: `is_access_relation_data_query(message: str) -> bool`

**位置**: 第 ~150 行

**功能**: 检测消息是否为访问关系数据查询（而非知识咨询），决定是否跳过 RAG 知识库检索。

**检测规则**:

1. **包含系统标识符**: 系统编码（N-XXX, P-XXX-XXX）、部署单元（XXXJS_XXX）、中文系统名、或 IP 地址
2. **询问访问关系**: 包含"有哪些访问关系"、"哪些系统访问"等关键词
3. **不是知识性问题**: 不包含"如何"、"怎么"、"流程"、"权限"等知识查询关键词

**示例**:

```python
# 数据查询（跳过 RAG）
is_access_relation_data_query("N-CRM有哪些访问关系")  # True
is_access_relation_data_query("客户关系管理系统有哪些访问关系")  # True
is_access_relation_data_query("10.0.1.10 有哪些访问关系")  # True

# 知识查询（使用 RAG）
is_access_relation_data_query("访问关系如何开权限")  # False
is_access_relation_data_query("如何申请访问关系")  # False
```

---

## 5. 通用聊天处理

### 5.1 通用聊天流式接口

**文件**: `src/api.py`

**函数**: `general_chat_stream_v2(request: GeneralChatRequestWithRAG)`

**位置**: 第 ~600 行（需要在代码中确认具体位置）

**功能**: 处理通用聊天请求，支持 RAG 增强和工具调用。

**关键步骤**:

1. 检测是否为访问关系数据查询
2. 如果是，跳过 RAG 检索
3. 创建或获取会话
4. 调用 `GeneralChatToolAgent` 执行 LLM 工具调用
5. 流式返回结果

---

## 6. LLM 工具调用 Agent

### 6.1 通用聊天工具 Agent

**文件**: `src/agent/general_chat_agent.py`

**类**: `GeneralChatToolAgent`

**方法**: `run(session_messages: List[Dict], system_prompt: str) -> str`

**位置**: 第 ~300 行

**功能**: 使用 LLM 进行多轮工具调用，直到获得最终答案。

**系统提示词**: `GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE`（第 ~10 行）

**关键内容**:

```python
GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE = """你是一个网络运维助手，负责两类任务：

1. 回答一般网络运维与故障诊断问题
2. 查询应用系统之间的网络访问关系

当用户询问访问关系时，你必须优先调用 query_access_relations 工具，禁止凭记忆、猜测、示例数据或常识直接编造访问关系。

访问关系查询的参数提取规则如下：

一、识别实体
1. 系统编码，例如 N-CRM、N-OA、N-AQM、P-DB-MAIN。
2. 中文系统名，例如 客户关系管理系统、办公自动化系统。
3. 部署单元，例如 CRMJS_AP、OAJS_AP、OAJS_WEB。
4. 对端系统，例如"X 和 Y 之间有哪些访问关系"里的 Y。

二、默认语义
1. 用户说"X有哪些访问关系"：
   默认理解为 X 主动访问其他系统，direction="outbound"。
2. 用户说"哪些系统访问X"或"X被哪些系统访问"：
   理解为其他系统访问 X，direction="inbound"。
3. 用户说"X和Y之间有哪些访问关系"：
   理解为查询 X 与 Y 的双向关系，direction="both"。
...
"""
```

**工具调用流程**:

```python
async def run(self, session_messages: List[Dict], system_prompt: str) -> str:
    messages = self._build_langchain_messages(session_messages, system_prompt)
    
    for _ in range(self.max_tool_rounds):  # 最多 3 轮工具调用
        # 1. LLM 决策是否调用工具
        response = self.llm_client.invoke_langchain_messages_with_tools(
            messages=messages,
            tools=self.tools,
            temperature=0.2,
        )
        
        # 2. 如果没有工具调用，返回最终答案
        if not response.tool_calls:
            return response.content
        
        # 3. 执行工具调用
        for tool_call in response.tool_calls:
            result = await tool.ainvoke(tool_call.arguments)
            messages.append(ToolMessage(content=result, tool_call_id=tool_call.id))
    
    # 4. 如果达到最大轮次，强制 LLM 给出最终答案
    return final_response.content
```

---

## 7. 访问关系查询工具

### 7.1 工具定义

**文件**: `src/agent/general_chat_agent.py`

**类**: `QueryAccessRelationsInput`（Pydantic 模型）

**位置**: 第 ~80 行

**参数定义**:

```python
class QueryAccessRelationsInput(BaseModel):
    system_code: Optional[str] = Field(default=None, description="主查询系统编码，例如 N-CRM、N-OA")
    system_name: Optional[str] = Field(default=None, description="主查询系统中文名称，例如 客户关系管理系统")
    deploy_unit: Optional[str] = Field(default=None, description="部署单元名称，例如 CRMJS_AP、OAJS_AP、OAJS_WEB")
    direction: str = Field(default="outbound", description='查询方向，只能是 outbound、inbound、both')
    peer_system_code: Optional[str] = Field(default=None, description="对端系统编码，例如 N-OA")
    peer_system_name: Optional[str] = Field(default=None, description="对端系统中文名称")
    src_ip: Optional[str] = Field(default=None, description="源 IP 地址，例如 10.0.1.10、192.168.1.1")
    dst_ip: Optional[str] = Field(default=None, description="目标 IP 地址，例如 10.0.2.20、192.168.1.100")
```

### 7.2 工具实现函数

**文件**: `src/agent/general_chat_agent.py`

**方法**: `GeneralChatToolAgent._create_tools()` 中的 `query_access_relations_func`

**位置**: 第 ~150 行

**功能**: 调用数据库查询访问关系数据。

```python
async def query_access_relations_func(
    system_code: Optional[str] = None,
    system_name: Optional[str] = None,
    deploy_unit: Optional[str] = None,
    direction: str = "outbound",
    peer_system_code: Optional[str] = None,
    peer_system_name: Optional[str] = None,
    src_ip: Optional[str] = None,
    dst_ip: Optional[str] = None
) -> Dict[str, Any]:
    # 调用数据库查询
    result = await self.session_manager.db.query_access_relations(
        system_code=system_code,
        system_name=system_name,
        deploy_unit=deploy_unit,
        direction=direction,
        peer_system_code=peer_system_code,
        peer_system_name=peer_system_name,
        src_ip=src_ip,
        dst_ip=dst_ip,
        page=1,
        page_size=50,
    )
    
    return {
        "success": True,
        "data": self._build_tool_summary(query=query, total=total),
        "query": query,
        "total": total,
        "items": result.get("items", []),
    }
```

---

## 8. 数据库查询

### 8.1 数据库查询方法

**文件**: `src/db/database.py`

**类**: `SessionDatabase`

**方法**: `query_access_relations(...) -> Dict[str, Any]`

**位置**: 第 ~500 行

**功能**: 从 SQLite 数据库查询访问关系数据，支持多种查询条件和分页。

**查询逻辑**:

1. **解析系统编码**: 如果提供了系统名称，先从数据库中查找对应的系统编码
2. **构建查询条件**: 根据 direction（outbound/inbound/both）构建不同的 SQL 查询
3. **执行查询**: 查询 `network_access_assets` 表
4. **分页返回**: 返回分页后的结果

**关键代码**:

```python
async def query_access_relations(
    self,
    system_code: Optional[str] = None,
    system_name: Optional[str] = None,
    deploy_unit: Optional[str] = None,
    direction: str = "outbound",
    peer_system_code: Optional[str] = None,
    peer_system_name: Optional[str] = None,
    src_ip: Optional[str] = None,
    dst_ip: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    # 1. 解析系统编码
    system_codes = await self._resolve_system_codes(db, system_code, system_name)
    peer_system_codes = await self._resolve_system_codes(db, peer_system_code, peer_system_name)
    
    # 2. 根据方向查询
    if direction == "both":
        outbound_items = await self._query_directional_access_relations(db, "outbound", ...)
        inbound_items = await self._query_directional_access_relations(db, "inbound", ...)
        items = merge(outbound_items, inbound_items)
    else:
        items = await self._query_directional_access_relations(db, direction, ...)
    
    # 3. 分页返回
    return {
        "items": paged_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
```

### 8.2 数据库表结构

**表名**: `network_access_assets`

**字段**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 主键 |
| src_system | TEXT | 源系统编码（如 N-CRM） |
| src_system_name | TEXT | 源系统中文名称 |
| src_deploy_unit | TEXT | 源部署单元 |
| src_ip | TEXT | 源 IP 地址（可多个，换行分隔） |
| dst_system | TEXT | 目标系统编码 |
| dst_deploy_unit | TEXT | 目标部署单元 |
| dst_ip | TEXT | 目标 IP 地址（可多个，换行分隔） |
| protocol | TEXT | 协议（如 TCP） |
| port | TEXT | 端口（可多个，换行分隔） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 9. LLM 客户端

### 9.1 LLM 客户端

**文件**: `src/integrations/llm_client.py`

**类**: `LLMClient`

**方法**: `invoke_langchain_messages_with_tools(messages, tools, temperature)`

**功能**: 调用 LLM（如 OpenAI、Claude 等）进行推理和工具调用决策。

**关键特性**:

- 支持工具调用（Function Calling）
- 支持流式输出
- 支持多轮对话

---

## 10. 完整调用链示例

### 示例：用户提问 "N-CRM有哪些访问关系？"

```
1. 用户发送消息
   POST /api/v1/chat/stream
   Body: {"message": "N-CRM有哪些访问关系？", "session_id": null}

2. API 入口处理
   src/api.py::chat_stream()
   ↓
   调用 intent_router.route_message("N-CRM有哪些访问关系？")

3. 意图路由
   src/agent/intent_router.py::IntentRouter.route_message()
   ↓
   检测到访问关系查询关键词
   ↓
   返回 IntentDecision(route="general_chat", reason="access_relation_query")

4. RAG 跳过检测
   src/api.py::is_access_relation_data_query("N-CRM有哪些访问关系？")
   ↓
   检测到系统编码 "N-CRM" + 访问关系关键词
   ↓
   返回 True（跳过 RAG）

5. 通用聊天处理
   src/api.py::general_chat_stream_v2()
   ↓
   创建 GeneralChatToolAgent
   ↓
   调用 agent.run(session_messages, system_prompt)

6. LLM 工具调用
   src/agent/general_chat_agent.py::GeneralChatToolAgent.run()
   ↓
   LLM 分析用户消息，决策调用 query_access_relations 工具
   ↓
   提取参数: {system_code: "N-CRM", direction: "outbound"}

7. 工具执行
   src/agent/general_chat_agent.py::query_access_relations_func()
   ↓
   调用 session_manager.db.query_access_relations(system_code="N-CRM", direction="outbound")

8. 数据库查询
   src/db/database.py::SessionDatabase.query_access_relations()
   ↓
   执行 SQL 查询:
   SELECT * FROM network_access_assets WHERE src_system = 'N-CRM' ORDER BY id DESC
   ↓
   返回结果: {"items": [...], "total": 2, "page": 1, "page_size": 50}

9. 工具结果返回
   返回给 LLM:
   {
     "success": True,
     "data": "主对象: N-CRM；方向: 出向；命中记录: 2 条",
     "total": 2,
     "items": [
       {
         "src_system": "N-CRM",
         "src_system_name": "客户关系管理系统",
         "src_deploy_unit": "CRMJS_AP",
         "src_ip": "10.38.1.100\n10.38.1.101",
         "dst_system": "N-AQM",
         "dst_deploy_unit": "AQMJS_AP",
         "dst_ip": "10.37.1.116",
         "protocol": "TCP",
         "port": "8080"
       },
       ...
     ]
   }

10. LLM 格式化输出
    LLM 将结果格式化为 Markdown 表格:
    
    "N-CRM（客户关系管理系统）有 2 条出向访问关系：
    
    | 源系统 | 源部署单元 | 源IP | 目的系统 | 目的部署单元 | 目的IP | 协议 | 端口 |
    |--------|-----------|------|---------|-------------|--------|------|------|
    | N-CRM 客户关系管理系统 | CRMJS_AP | 10.38.1.100<br>10.38.1.101 | N-AQM | AQMJS_AP | 10.37.1.116 | TCP | 8080 |
    | N-CRM 客户关系管理系统 | CRMJS_AP | 10.38.1.100<br>10.38.1.101 | P-DB-MAIN | DBMAIN_DB | 10.20.5.50 | TCP | 1521 |
    "

11. 流式输出
    通过 SSE（Server-Sent Events）流式返回给前端
    ↓
    用户看到访问关系表格
```

---

## 11. 关键代码文件总结

| 文件路径 | 关键类/函数 | 功能 |
|---------|------------|------|
| `src/api.py` | `chat_stream()` | HTTP API 入口 |
| `src/api.py` | `is_access_relation_data_query()` | RAG 跳过检测 |
| `src/api.py` | `general_chat_stream_v2()` | 通用聊天流式处理 |
| `src/agent/intent_router.py` | `IntentRouter.route_message()` | 意图路由 |
| `src/agent/general_chat_agent.py` | `GeneralChatToolAgent` | LLM 工具调用 Agent |
| `src/agent/general_chat_agent.py` | `GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE` | 系统提示词 |
| `src/agent/general_chat_agent.py` | `QueryAccessRelationsInput` | 工具参数定义 |
| `src/agent/general_chat_agent.py` | `query_access_relations_func()` | 工具实现函数 |
| `src/db/database.py` | `SessionDatabase.query_access_relations()` | 数据库查询 |
| `src/integrations/llm_client.py` | `LLMClient` | LLM 客户端 |

---

## 12. 扩展阅读

- **LLM Agent 设计**: 参考 `src/agent/llm_agent.py` 了解诊断 Agent 的实现
- **RAG 实现**: 参考 `src/rag/` 目录了解知识库检索的实现
- **会话管理**: 参考 `src/session_manager.py` 了解会话持久化的实现
- **前端交互**: 参考 `static/` 目录了解前端如何处理 SSE 流式响应

---

## 13. 常见问题

### Q1: 为什么访问关系查询要跳过 RAG？

**A**: 访问关系查询是实时数据查询，需要从数据库获取最新的访问关系数据。RAG 知识库主要用于回答知识性问题（如"如何申请访问关系权限"），不适合实时数据查询。

### Q2: LLM 如何知道要调用 query_access_relations 工具？

**A**: 通过系统提示词（`GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE`）明确告诉 LLM：
1. 当用户询问访问关系时，必须调用 `query_access_relations` 工具
2. 禁止凭记忆或猜测编造访问关系数据
3. 提供详细的参数提取规则和示例

### Q3: 如何支持新的查询条件（如按 IP 地址查询）？

**A**: 需要修改以下几个地方：
1. `QueryAccessRelationsInput`: 添加新的参数字段
2. `query_access_relations_func()`: 传递新参数给数据库查询
3. `SessionDatabase.query_access_relations()`: 实现新的查询逻辑
4. `GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE`: 更新系统提示词，告诉 LLM 如何使用新参数

### Q4: 如何调试访问关系查询？

**A**: 可以通过以下方式调试：
1. 查看 API 日志：`runtime/logs/` 目录
2. 查看数据库内容：`sqlite3 runtime/sessions.db`
3. 使用测试脚本：`tests/test_access_relations_tool_query.py`
4. 查看 LLM 工具调用历史：会话消息中的 `metadata.tool_call` 字段

---

## 14. 更新日志

- **2026-04-23**: 初始版本，文档化访问关系查询的完整数据流
