# 访问关系查询数据流文档

## 概述

当用户提问“XX 系统有哪些访问关系？”、“哪些系统访问 XX？”或“IP 为 10.0.1.10 的主机有哪些访问关系？”时，系统会先通过聊天入口做意图路由，再在通用聊天流中判断是否跳过 RAG，最后由 `GeneralChatToolAgent` 调用 `query_access_relations` 工具查询 SQLite 中的访问关系资产，并通过 SSE 返回工具执行过程和最终回答。

本文档按当前代码描述访问关系查询的实际数据流。当前实现中，聊天入口不再直接实例化单一 `IntentRouter`，而是通过 `build_intent_router()` 构建规则路由或可选的 hybrid 路由。

---

## 1. 核心数据流程

```text
用户提问“XX 系统有哪些访问关系？”
    ↓
[API 入口] src/api.py::chat_stream()
    ↓
[意图路由工厂] src/agent/intent_router.py::build_intent_router()
    ├─ 默认：RuleIntentRouter
    └─ INTENT_ROUTER_MODE=hybrid：HybridIntentRouter
    ↓
[规则信号收集] src/agent/rule_intent_router.py::RuleIntentRouter.classify()
    ↓
判断是否为访问关系数据查询
    ├─ 是：route="general_chat"，reason="access_relation_query"，certainty="hard"
    └─ 否：按诊断、澄清或通用聊天逻辑继续路由
    ↓
[通用聊天流] src/api.py::general_chat_stream_v2()
    ↓
[RAG 跳过检测] src/api.py::is_access_relation_data_query()
    ├─ use_rag=True 且检测为访问关系数据查询：发送 rag_skipped，跳过知识库检索
    ├─ use_rag=True 且不是访问关系数据查询：执行 RAG 检索并增强系统提示词
    └─ use_rag=False：不执行 RAG，也不发送 rag_skipped
    ↓
[通用聊天工具 Agent] src/agent/general_chat_agent.py::GeneralChatToolAgent.run()
    ↓
[LLM 工具决策] invoke_langchain_messages_with_tools(...)
    ↓
[工具执行事件] SSE tool_start
    ↓
[工具函数] query_access_relations_func()
    ↓
[数据库查询] src/db/database.py::SessionDatabase.query_access_relations()
    ↓
[工具结果事件] SSE tool_result
    ↓
[会话历史] 保存 metadata.tool_call，供后续追问复用
    ↓
[LLM 最终回答] 基于工具 JSON 结果格式化 Markdown 表格
    ↓
[内容流式输出] SSE content 分块 + complete
```

---

## 2. HTTP 入口

**文件**: `src/api.py`

**函数**: `chat_stream(request: ChatStreamRequest)`

**当前位置**: 第 318 行附近

`chat_stream()` 是统一聊天流式入口。它先读取现有会话，再调用全局 `intent_router.route_message(...)`。全局路由器在模块加载时由 `build_intent_router()` 创建。

```python
intent_router = build_intent_router()

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    session = await session_manager.get_session(request.session_id) if request.session_id else None
    decision = intent_router.route_message(request.message, session=session)

    if decision.route == "start_diagnosis":
        return await diagnose_stream(...)

    if decision.route == "continue_diagnosis":
        return await chat_answer(...)

    if decision.route == "clarify":
        return _build_clarify_stream_response(...)

    return await general_chat_stream_v2(...)
```

访问关系数据查询会被路由到 `general_chat_stream_v2()`。普通网络知识问答也会进入同一个通用聊天流，但后续是否跳过 RAG 由 `is_access_relation_data_query()` 决定。

---

## 3. 意图路由

### 3.1 路由工厂

**文件**: `src/agent/intent_router.py`

**函数**: `build_intent_router(llm_client=None)`

**当前位置**: 第 49 行附近

`intent_router.py` 现在是兼容 facade 和工厂：

- `IntentRouter = RuleIntentRouter` 仍保留兼容导出。
- 默认 `INTENT_ROUTER_MODE` 为 `rule`，返回 `RuleIntentRouter()`。
- 当 `INTENT_ROUTER_MODE=hybrid` 时，尝试创建 `HybridIntentRouter` 和 `LLMIntentClassifier`。
- hybrid 初始化失败时会安全回退到 `RuleIntentRouter()`。

```python
def build_intent_router(llm_client=None):
    mode = (os.getenv("INTENT_ROUTER_MODE") or "rule").strip().lower()
    if mode != "hybrid":
        return RuleIntentRouter()

    try:
        client = llm_client if llm_client is not None else _create_default_llm_client()
        classifier = LLMIntentClassifier(llm_client=client)
        return HybridIntentRouter(...)
    except Exception:
        return RuleIntentRouter()
```

### 3.2 规则路由

**文件**: `src/agent/rule_intent_router.py`

**类**: `RuleIntentRouter`

**方法**: `classify(...)` / `route_message(...)`

访问关系数据查询由规则路由硬判定：

```python
ACCESS_RELATION_RE = re.compile(
    r"(访问关系|哪些系统访问|谁访问|被哪些系统访问|之间.*访问关系)",
    re.IGNORECASE,
)
ACCESS_RELATION_KNOWLEDGE_RE = re.compile(
    r"(怎么|如何|为什么|什么是|是什么|步骤|原理|思路|办法|开权限|配置|申请|提单|权限|审批|必填|准备|流程)",
    re.IGNORECASE,
)
```

如果命中访问关系关键词，且没有命中知识咨询关键词，返回：

```python
RuleIntentResult(
    route="general_chat",
    confidence=0.95,
    reason="access_relation_query",
    certainty="hard",
)
```

### 3.3 Hybrid 路由

**文件**: `src/agent/hybrid_intent_router.py`

**类**: `HybridIntentRouter`

hybrid 模式采用“规则优先，LLM 只处理 soft 结果”的策略：

- 规则结果 `certainty="hard"` 时直接返回，不调用 LLM。
- 访问关系数据查询在规则层是 hard，因此不会进入 LLM 意图分类。
- 访问关系知识咨询通常不会被当作访问关系数据查询，可能作为一般网络问题进入 `general_chat`，并按 `use_rag` 决定是否检索知识库。

---

## 4. RAG 跳过检测

**文件**: `src/api.py`

**函数**: `is_access_relation_data_query(message: str) -> bool`

**当前位置**: 第 162 行附近

该函数只判断“是否为访问关系数据查询”，用于决定通用聊天流是否跳过知识库检索。它不负责意图路由。

当前检测条件：

1. 包含系统标识符：系统编码、部署单元、中文系统名或 IP 地址。
2. 包含访问关系查询表达：如“有哪些访问关系”、“哪些系统访问”、“被...访问”、“访问...系统”、“之间...访问关系”、“的访问关系”。
3. 不包含知识咨询表达：如“如何”、“怎么”、“流程”、“权限”、“提单”、“申请”、“审批”等。

```python
system_identifier_pattern = (
    r"(N-[A-Z]+|P-[A-Z-]+|[A-Z]+JS_[A-Z]+|[\u4e00-\u9fa5]{2,}系统|"
    r"客户关系管理|办公自动化|部署单元|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)
relation_query_pattern = r"(有哪些访问关系|哪些系统访问|被.*访问|访问.*系统|之间.*访问关系|的访问关系)"
knowledge_query_pattern = r"(如何|怎么|流程|权限|提单|申请|审批)(?!系统)|(?<!关系)管理(?!系统)"
```

示例：

```python
is_access_relation_data_query("N-CRM有哪些访问关系")  # True
is_access_relation_data_query("CRMJS_AP部署单元有哪些访问关系")  # True
is_access_relation_data_query("IP 为 10.0.1.10 的主机有哪些访问关系")  # True
is_access_relation_data_query("访问关系如何开权限")  # False
is_access_relation_data_query("有哪些访问关系")  # False
```

在 `general_chat_stream_v2()` 中，只有 `request.use_rag=True` 且该函数返回 `True` 时，才发送：

```json
{"type": "rag_skipped", "reason": "检测到访问关系数据查询,跳过知识库检索"}
```

---

## 5. 通用聊天流

**文件**: `src/api.py`

**函数**: `general_chat_stream_v2(request: GeneralChatRequestWithRAG)`

**当前位置**: 第 1837 行附近

当前通用聊天流的主要步骤：

1. 复用已有会话，或创建新的轻量 general-chat 会话。
2. 发送 `start` SSE 事件，包含 `session_id`。
3. 构建 `GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE`，根据 `use_rag` 注入 RAG 指令。
4. 如果 `use_rag=True` 且是访问关系数据查询，发送 `rag_skipped` 并跳过 RAG。
5. 如果 `use_rag=True` 且没有跳过，执行知识库检索，发送 `rag_start` / `rag_result` / `rag_error`。
6. 将用户消息写入会话。
7. 创建 `GeneralChatToolAgent`，用 `event_callback` 把工具事件写入队列。
8. 异步运行 agent，同时把队列中的 `tool_start` / `tool_result` 事件流式发给前端。
9. agent 返回最终回答后，将 assistant 消息写入会话。
10. 将最终回答按 10 个字符一段发送为 `content` 事件。
11. 发送 `complete` 事件，包含 `session_id` 和 `rag_used`。

---

## 6. 通用聊天工具 Agent

**文件**: `src/agent/general_chat_agent.py`

**类**: `GeneralChatToolAgent`

**方法**: `run(session_messages, system_prompt) -> str`

**当前位置**: 第 292 行附近

`GeneralChatToolAgent` 是访问关系查询实际触发工具调用的组件。它最多执行 3 轮工具调用：

```python
for _ in range(self.max_tool_rounds):
    response = self.llm_client.invoke_langchain_messages_with_tools(
        messages=messages,
        tools=self.tools,
        temperature=0.2,
    )
    messages.append(response)

    tool_calls = getattr(response, "tool_calls", None) or []
    if not tool_calls:
        return self._stringify_content(response.content)

    for tool_call in tool_calls:
        ...
```

当前工具事件和历史处理：

- 执行前发送 `tool_start`，包含 `step`、`tool`、`arguments`。
- 执行后发送 `tool_result`，包含 `result` 和 `execution_time`。
- 成功或失败的工具执行结果都会作为 `ToolMessage` 放回 LLM 上下文。
- 已知工具调用会通过 `_save_tool_call_history()` 写入会话消息：

```python
metadata={
    "tool_call": {
        "name": tool_name,
        "arguments": arguments,
        "result": result,
        "execution_time": round(execution_time, 2),
    }
}
```

后续构建 LangChain 消息时，`_build_langchain_messages()` 会把历史 `metadata.tool_call` 转成系统消息，作为追问上下文参考。

---

## 7. 访问关系查询工具

### 7.1 工具参数

**文件**: `src/agent/general_chat_agent.py`

**类**: `QueryAccessRelationsInput`

**当前位置**: 第 74 行附近

```python
class QueryAccessRelationsInput(BaseModel):
    system_code: Optional[str] = Field(default=None, description="主查询系统编码，例如 N-CRM、N-OA")
    system_name: Optional[str] = Field(default=None, description="主查询系统中文名称，例如 客户关系管理系统")
    deploy_unit: Optional[str] = Field(default=None, description="部署单元名称，例如 CRMJS_AP、OAJS_AP、OAJS_WEB")
    direction: str = Field(default="outbound", description="查询方向，只能是 outbound、inbound、both")
    peer_system_code: Optional[str] = Field(default=None, description="对端系统编码，例如 N-OA")
    peer_system_name: Optional[str] = Field(default=None, description="对端系统中文名称")
    src_ip: Optional[str] = Field(default=None, description="源 IP 地址，例如 10.0.1.10、192.168.1.1")
    dst_ip: Optional[str] = Field(default=None, description="目标 IP 地址，例如 10.0.2.20、192.168.1.100")
```

工具描述也明确支持按系统、中文系统名、部署单元、IP 地址或两个系统之间的关系查询。

### 7.2 工具函数

**文件**: `src/agent/general_chat_agent.py`

**函数**: `query_access_relations_func(...)`

**位置**: `GeneralChatToolAgent._create_tools()` 内

工具函数做两件事：

1. 校验 `session_manager.db` 是否可用；不可用时返回 `success=False`。
2. 调用 `session_manager.db.query_access_relations(...)`，固定查询第一页、每页 50 条。

返回结构：

```python
{
    "success": True,
    "data": self._build_tool_summary(query=query, total=total),
    "query": query,
    "total": total,
    "items": result.get("items", []),
}
```

`data` 是给工具卡片和 LLM 使用的摘要，例如：

```text
主对象: N-CRM；方向: 出向；命中记录: 2 条
```

---

## 8. 数据库查询

**文件**: `src/db/database.py`

**类**: `SessionDatabase`

**方法**: `query_access_relations(...) -> Dict[str, Any]`

**当前位置**: 第 544 行附近

数据库查询流程：

1. 校验 `direction` 只能是 `outbound`、`inbound` 或 `both`。
2. 通过 `_resolve_system_codes()` 解析 `system_code/system_name` 和 `peer_system_code/peer_system_name`。
3. 如果指定了系统或对端，但解析不到系统编码，直接返回空结果。
4. `direction="outbound"` 查询主对象作为 `src_system` 的记录。
5. `direction="inbound"` 查询主对象作为 `dst_system` 的记录。
6. `direction="both"` 分别查出向和入向，再按 `id` 去重合并。
7. 在内存中分页，`page_size` 最多 100。

方向字段映射：

| direction | 主系统字段 | 主部署单元字段 | 对端系统字段 |
|-----------|------------|----------------|--------------|
| outbound | `src_system` | `src_deploy_unit` | `dst_system` |
| inbound | `dst_system` | `dst_deploy_unit` | `src_system` |

IP 条件当前按数据库绝对列过滤：

```python
if src_ip:
    conditions.append("src_ip = ?")
if dst_ip:
    conditions.append("dst_ip = ?")
```

因此 `src_ip` 始终匹配 `network_access_assets.src_ip`，`dst_ip` 始终匹配 `network_access_assets.dst_ip`，不随 `direction` 反转。

### 8.1 表结构

**表名**: `network_access_assets`

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 主键 |
| src_system | TEXT | 源系统编码 |
| src_system_name | TEXT | 源系统中文名称 |
| src_deploy_unit | TEXT | 源部署单元 |
| src_ip | TEXT | 源 IP 地址，可包含换行分隔的多个值 |
| dst_system | TEXT | 目标系统编码 |
| dst_deploy_unit | TEXT | 目标部署单元 |
| dst_ip | TEXT | 目标 IP 地址，可包含换行分隔的多个值 |
| protocol | TEXT | 协议，默认 TCP |
| port | TEXT | 端口，可包含换行分隔的多个值 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 9. LLM 客户端

**文件**: `src/integrations/llm_client.py`

访问关系查询链路主要使用两个 LLM 调用能力：

- `invoke_langchain_messages_with_tools(...)`：由 `GeneralChatToolAgent.run()` 调用，支持 LangChain 工具调用。
- `invoke_langchain_messages(...)`：达到最大工具轮次后，用已有工具结果强制生成最终回答。

如果启用 hybrid 意图路由，还会使用：

- `invoke_with_json(...)`：由 `LLMIntentClassifier.classify()` 调用，只用于 soft 意图结果的 JSON 路由分类。

---

## 10. 完整调用链示例

### 示例：用户提问“N-CRM 有哪些访问关系？”

```text
1. 用户发送消息
   POST /api/v1/chat/stream
   Body: {"message": "N-CRM有哪些访问关系？", "session_id": null, "use_rag": true}

2. API 入口
   src/api.py::chat_stream()
   调用 intent_router.route_message(...)

3. 意图路由
   默认 RuleIntentRouter.classify(...)
   命中 ACCESS_RELATION_RE，且未命中 ACCESS_RELATION_KNOWLEDGE_RE
   返回 route="general_chat", reason="access_relation_query", certainty="hard"

4. 通用聊天流
   src/api.py::general_chat_stream_v2()
   创建新 general-chat 会话
   发送 SSE: {"type": "start", "session_id": "..."}

5. RAG 跳过
   is_access_relation_data_query("N-CRM有哪些访问关系？") 返回 True
   发送 SSE: {"type": "rag_skipped", "reason": "检测到访问关系数据查询,跳过知识库检索"}

6. 工具 Agent
   创建 GeneralChatToolAgent
   LLM 决策调用 query_access_relations
   参数示例: {"system_code": "N-CRM", "direction": "outbound"}

7. 工具执行
   发送 SSE: {"type": "tool_start", "tool": "query_access_relations", "arguments": {...}}
   调用 SessionDatabase.query_access_relations(system_code="N-CRM", direction="outbound", page=1, page_size=50)

8. 数据库查询
   查询 network_access_assets 中 src_system="N-CRM" 的记录
   返回 {"items": [...], "total": 2, "page": 1, "page_size": 50}

9. 工具结果
   工具返回:
   {
     "success": true,
     "data": "主对象: N-CRM；方向: 出向；命中记录: 2 条",
     "query": {"system_code": "N-CRM", "direction": "outbound", ...},
     "total": 2,
     "items": [...]
   }
   发送 SSE: {"type": "tool_result", "tool": "query_access_relations", "result": {...}}
   写入会话消息 metadata.tool_call

10. LLM 最终回答
    LLM 根据工具 JSON 结果生成 Markdown 表格。
    表格列顺序固定：
    | 源系统 | 源部署单元 | 源IP | 目的系统 | 目的部署单元 | 目的IP | 协议 | 端口 |

11. 内容流式输出
    API 将最终回答拆成 content 事件返回。
    最后发送 complete 事件。
```

---

## 11. 关键代码文件总结

| 文件路径 | 关键类/函数 | 功能 |
|---------|------------|------|
| `src/api.py` | `chat_stream()` | 统一聊天 SSE 入口 |
| `src/api.py` | `general_chat_stream_v2()` | 通用聊天流，处理 RAG、工具事件和最终内容输出 |
| `src/api.py` | `is_access_relation_data_query()` | 判断访问关系数据查询是否跳过 RAG |
| `src/agent/intent_router.py` | `build_intent_router()` | 构建规则路由或 hybrid 路由 |
| `src/agent/rule_intent_router.py` | `RuleIntentRouter` | 规则意图路由，访问关系数据查询在这里 hard route 到 general_chat |
| `src/agent/hybrid_intent_router.py` | `HybridIntentRouter` | 可选 hybrid 路由，对 soft 规则结果调用 LLM 分类 |
| `src/agent/llm_intent_router.py` | `LLMIntentClassifier` | hybrid 模式下的 JSON-only 意图分类器 |
| `src/agent/general_chat_agent.py` | `GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE` | 通用聊天和访问关系工具调用提示词 |
| `src/agent/general_chat_agent.py` | `GeneralChatToolAgent` | 工具调用 Agent，负责发工具事件和保存工具历史 |
| `src/agent/general_chat_agent.py` | `QueryAccessRelationsInput` | `query_access_relations` 工具参数模型 |
| `src/db/database.py` | `SessionDatabase.query_access_relations()` | SQLite 访问关系查询 |
| `static/app.js` | `attachAccessRelationExport()` | 前端工具卡片支持访问关系 CSV 导出 |

---

## 12. 调试与验证

常用验证点：

1. RAG 跳过检测：`tests/test_is_access_relation_data_query.py`
2. 通用聊天流中 RAG 跳过事件：`tests/test_rag_skip_for_access_relations.py`
3. IP 访问关系 RAG 跳过：`tests/test_ip_address_rag_skip.py`
4. 工具调用 Agent：`tests/test_general_chat_agent.py`
5. 数据库访问关系查询：`tests/test_access_relations_tool_query.py`
6. 意图路由：`tests/unit/agent/test_rule_intent_router.py`、`tests/unit/agent/test_hybrid_intent_router.py`、`tests/unit/agent/test_intent_router_factory.py`

---

## 13. 常见问题

### Q1: 为什么访问关系数据查询要跳过 RAG？

访问关系数据查询需要查询 `network_access_assets` 中的结构化资产数据。RAG 知识库适合回答“如何申请访问关系权限”“访问关系审批流程是什么”这类知识问题，不适合作为访问关系资产数据来源。

### Q2: LLM 如何知道要调用 `query_access_relations`？

`GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE` 明确要求：只要问题属于访问关系查询，就先调用 `query_access_relations`，并禁止凭记忆或猜测编造访问关系。工具 schema 和工具描述也提供了系统编码、中文系统名、部署单元、方向、对端系统和 IP 参数。

### Q3: 访问关系数据查询会不会走 hybrid 意图分类？

默认不会。访问关系数据查询在 `RuleIntentRouter` 中是 hard 结果。`HybridIntentRouter` 对 hard 结果直接返回，只有 soft 结果才可能调用 `LLMIntentClassifier`。

### Q4: 前端如何展示工具过程？

后端通过 SSE 发送 `tool_start` 和 `tool_result`。前端 `static/app.js` 会把这些事件渲染成工具调用卡片。对于 `query_access_relations` 且结果成功、`items` 非空的情况，前端会显示“导出 CSV”按钮。

### Q5: IP 查询有哪些注意点？

RAG 跳过检测已经把 IP 地址视为系统标识符。数据库查询层的 `src_ip` 和 `dst_ip` 当前是对 `src_ip` / `dst_ip` 列做精确匹配；如果数据库字段内保存的是换行分隔的多个 IP，调用方需要传入与字段一致的值，或者后续把查询改成按单个 IP 拆分/匹配。

---

## 14. 更新日志

- **2026-04-23**: 根据当前代码更新文档：补充 `build_intent_router()`、规则/hybrid 路由、RAG 跳过触发条件、工具 SSE 事件、工具历史保存、IP 查询和前端 CSV 导出逻辑。
