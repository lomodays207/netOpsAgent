# Bugfix Requirements Document

## Introduction

当用户在聊天窗口查询具体系统或部署单元的访问关系数据（如"N-CRM有哪些访问关系"、"CRMJS_AP部署单元有哪些访问关系"）时，系统错误地先执行 RAG 知识库检索，而不是让 LLM 直接调用 `query_access_relations` 工具函数查询数据库。这导致访问关系数据查询的响应路径不正确，可能返回知识库中的示例数据或过时信息，而不是从数据库获取实时准确的访问关系数据。

**重要区分**：
- **访问关系数据查询**（如"N-CRM有哪些访问关系"）→ 应该直接调用工具，跳过 RAG
- **访问关系知识咨询**（如"访问关系如何开权限"、"如何提单"）→ 应该使用 RAG 检索知识库

本 bugfix 旨在修复这个问题，确保访问关系**数据查询**直接走工具调用路径，跳过 RAG 检索，而访问关系**知识咨询**仍然使用 RAG。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 用户消息是访问关系数据查询（如"N-CRM有哪些访问关系"、"哪些系统访问N-OA"、"CRMJS_AP部署单元有哪些访问关系"）且 `use_rag=True` THEN 系统先执行 RAG 知识库检索，然后才将消息传递给 LLM 进行工具调用判断

1.2 WHEN 用户询问"N-CRM有哪些访问关系"且 `use_rag=True` THEN 系统在 `general_chat_stream_v2` 函数中先调用 `rag_chain.build_enhanced_prompt`，将知识库检索结果注入到 system prompt 中

1.3 WHEN 访问关系数据查询触发 RAG 检索 THEN 系统可能返回知识库中的示例数据或过时信息，而不是数据库中的实时访问关系数据

1.4 WHEN 用户询问"N-CRM有哪些访问关系" THEN LLM 可能基于知识库中的示例数据回答，而不是调用 `query_access_relations` 工具查询数据库

### Expected Behavior (Correct)

2.1 WHEN 用户消息是访问关系数据查询（包含系统编码、系统名称或部署单元，并询问访问关系）THEN 系统 SHALL 跳过 RAG 知识库检索，直接将消息传递给 GeneralChatToolAgent 进行工具调用

2.2 WHEN 用户询问"N-CRM有哪些访问关系" THEN 系统 SHALL 跳过 RAG 检索，让 LLM 识别这是访问关系数据查询意图，直接调用 `query_access_relations` 工具函数，从数据库查询并返回实时数据

2.3 WHEN 用户询问"CRMJS_AP部署单元有哪些访问关系" THEN 系统 SHALL 跳过 RAG 检索，让 LLM 调用 `query_access_relations(system_code="N-CRM", deploy_unit="CRMJS_AP", direction="outbound")`

2.4 WHEN 用户询问"哪些系统访问N-OA" THEN 系统 SHALL 跳过 RAG 检索，让 LLM 调用 `query_access_relations(system_code="N-OA", direction="inbound")`

2.5 WHEN 访问关系数据查询被识别 THEN 系统 SHALL 在事件流中发出 `rag_skipped` 事件，说明跳过 RAG 的原因（如"检测到访问关系数据查询，跳过知识库检索"）

2.6 WHEN 用户询问访问关系相关知识（如"访问关系如何开权限"、"如何提单"、"访问关系管理流程"）THEN 系统 SHALL 执行 RAG 知识库检索，增强 system prompt

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 用户询问访问关系相关知识（如"访问关系如何开权限"、"如何提单"、"访问关系管理流程是什么"）且 `use_rag=True` THEN 系统 SHALL CONTINUE TO 执行 RAG 知识库检索，增强 system prompt

3.2 WHEN 用户询问一般网络运维问题（如"如何排查网络故障"）且 `use_rag=True` THEN 系统 SHALL CONTINUE TO 调用 `rag_chain.build_enhanced_prompt`，将知识库中的相关文档注入到 system prompt 中

3.3 WHEN `use_rag=False` THEN 系统 SHALL CONTINUE TO 跳过 RAG 检索，无论用户消息内容是什么

3.4 WHEN RAG 检索失败（抛出异常）THEN 系统 SHALL CONTINUE TO 发出 `rag_error` 事件，并继续执行后续的工具调用流程

3.5 WHEN 用户消息同时包含访问关系数据查询和知识咨询（如"N-CRM有哪些访问关系？另外访问关系如何开权限？"）THEN 系统 SHALL 跳过 RAG 检索（优先处理数据查询的特殊性，LLM 可以基于已有知识回答知识咨询部分）

## Bug Condition and Property

### Bug Condition Function

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type GeneralChatRequest
  OUTPUT: boolean
  
  // 返回 true 当消息是访问关系数据查询且 RAG 开关打开
  // 访问关系数据查询的特征：
  // 1. 包含系统编码（如 N-CRM、N-OA）或系统名称（如"客户关系管理系统"）或部署单元（如 CRMJS_AP）
  // 2. 询问访问关系（如"有哪些访问关系"、"哪些系统访问"、"被哪些系统访问"）
  // 3. 不是询问流程、权限、提单等知识性问题
  
  RETURN X.use_rag = true AND 
         is_access_relation_data_query(X.message)
END FUNCTION

FUNCTION is_access_relation_data_query(message)
  // 检测是否包含系统标识符
  has_system_identifier = MATCHES(message, "(N-[A-Z]+|P-[A-Z-]+|[A-Z]+JS_[A-Z]+|客户关系管理系统|办公自动化系统)")
  
  // 检测是否询问访问关系数据
  asks_for_relations = MATCHES(message, "(有哪些访问关系|哪些系统访问|被.*访问|访问.*系统|之间.*访问关系)")
  
  // 检测是否询问知识性问题（如果是，则不应跳过 RAG）
  asks_for_knowledge = MATCHES(message, "(如何|怎么|流程|权限|提单|申请|审批|管理)")
  
  RETURN has_system_identifier AND asks_for_relations AND NOT asks_for_knowledge
END FUNCTION
```

### Property Specification

```pascal
// Property: Fix Checking - 访问关系查询应跳过 RAG
FOR ALL X WHERE isBugCondition(X) DO
  result ← general_chat_stream_v2'(X)
  ASSERT NOT executed_rag_retrieval(result) AND 
         emitted_event(result, "rag_skipped") AND
         tool_called(result, "query_access_relations")
END FOR
```

### Preservation Goal

```pascal
// Property: Preservation Checking - 非访问关系查询的 RAG 行为不变
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT general_chat_stream_v2(X) = general_chat_stream_v2'(X)
END FOR
```

**Key Definitions:**
- **general_chat_stream_v2**: 原始（未修复）函数 - 修复前的代码
- **general_chat_stream_v2'**: 修复后的函数 - 应用修复后的代码
- **executed_rag_retrieval(result)**: 检查是否执行了 RAG 检索
- **emitted_event(result, event_type)**: 检查是否发出了指定类型的事件
- **tool_called(result, tool_name)**: 检查是否调用了指定的工具

## Counterexample

### Example 1: 访问关系数据查询（应跳过 RAG）

**输入**：
```python
request = GeneralChatRequestWithRAG(
    message="N-CRM有哪些访问关系",
    use_rag=True,
    session_id=None
)
```

**当前行为（错误）**：
1. 系统执行 `rag_chain.build_enhanced_prompt("N-CRM有哪些访问关系", ...)`
2. 发出 `rag_start` 事件："正在检索知识库..."
3. 发出 `rag_result` 事件，可能包含知识库中的示例数据
4. 将增强后的 system prompt（包含知识库检索结果）传递给 GeneralChatToolAgent
5. LLM 可能基于知识库中的示例数据回答，而不是调用 `query_access_relations` 工具

**期望行为（正确）**：
1. 系统检测到消息是访问关系数据查询（包含系统编码 N-CRM，询问访问关系，不是知识性问题）
2. 跳过 RAG 检索
3. 发出 `rag_skipped` 事件："检测到访问关系数据查询，跳过知识库检索"
4. 将原始 system prompt 传递给 GeneralChatToolAgent
5. LLM 识别访问关系数据查询意图，调用 `query_access_relations(system_code="N-CRM", direction="outbound")`
6. 从数据库查询并返回实时访问关系数据

### Example 2: 访问关系知识咨询（应使用 RAG）

**输入**：
```python
request = GeneralChatRequestWithRAG(
    message="访问关系如何开权限",
    use_rag=True,
    session_id=None
)
```

**当前行为（正确，应保持）**：
1. 系统执行 `rag_chain.build_enhanced_prompt("访问关系如何开权限", ...)`
2. 发出 `rag_start` 事件："正在检索知识库..."
3. 发出 `rag_result` 事件，包含知识库中关于权限开通流程的文档
4. 将增强后的 system prompt 传递给 GeneralChatToolAgent
5. LLM 基于知识库中的文档回答权限开通流程

**期望行为（正确，应保持）**：
与当前行为相同，因为这是知识性问题，应该使用 RAG 检索。

### Example 3: 部署单元访问关系查询（应跳过 RAG）

**输入**：
```python
request = GeneralChatRequestWithRAG(
    message="CRMJS_AP部署单元有哪些访问关系",
    use_rag=True,
    session_id=None
)
```

**期望行为（正确）**：
1. 系统检测到消息是访问关系数据查询（包含部署单元 CRMJS_AP，询问访问关系）
2. 跳过 RAG 检索
3. 发出 `rag_skipped` 事件
4. LLM 调用 `query_access_relations(deploy_unit="CRMJS_AP", direction="outbound")`
5. 从数据库查询并返回实时访问关系数据
