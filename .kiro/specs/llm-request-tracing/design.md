# 设计文档 - LLM请求链路追踪功能

## 概述

LLM 请求链路追踪功能用于记录一次请求从用户输入、LLM 决策、工具调用到最终回答的完整执行链路，并在本地 SQLite 中持久化，供 API 查询、静态页面展示、导出审计和问题排查使用。

本设计采用“兼容优先”的策略：优先复用仓库现有的 `aiosqlite + SessionDatabase + SQLiteSessionManager + FastAPI + static/*.html/js` 结构，不为 tracing 单独引入 SQLAlchemy、Repository/Service 分层或前端框架路由。这样可以降低改造成本，减少和现有代码风格的偏离，并避免在任务执行过程中反复返工。

## 设计目标

1. 完整记录诊断流和通用聊天流中的关键信息。
2. tracing 写入失败时不影响主流程执行。
3. 查询、导出和会话关联能力与现有 API、页面结构一致。
4. 前端继续沿用静态页面模式，不额外引入新的运行时依赖。
5. 通过清理、脱敏和 feature flag 保持可维护性与可控风险。

## 明确约束

### 兼容性约束

1. 不引入 SQLAlchemy。
2. 不新建通用 repository/service 架构。
3. 不为 tracing 单独新建数据库文件。
4. 不引入 React、Vue 或前端路由框架。
5. 不为 tracing 顺手补一套新的认证系统。

### 需求适配约束

1. 需求 14.2 的“查询 API 验证用户权限”在当前仓库内没有现成认证体系支撑，因此本期只预留统一拦截点或依赖注入位置，不新增真实鉴权实现。
2. `GeneralChatToolAgent` 当前没有稳定、结构化的“推理步骤”输出，因此通用聊天流程默认只记录工具调用和最终回答，不强行生成 `reasoning_steps`。
3. 会话关联功能必须提供专用后端接口，不能依赖前端拿全量 traces 后自行过滤。

## 现有代码基础

当前仓库已经具备与 tracing 高度相关的基础设施：

1. `src/db/database.py` 中的 `SessionDatabase` 已负责 SQLite 初始化、建表和 CRUD。
2. `src/session_manager.py` 中的 `SQLiteSessionManager` 已负责数据库初始化、消息持久化和后台清理循环。
3. `src/api.py` 已集中承载 API、启动链、静态资源挂载和简单内存限流逻辑。
4. `src/agent/llm_agent.py` 与 `src/agent/general_chat_agent.py` 已显式暴露工具调用、最终回答和会话历史写入节点。
5. 前端页面采用 `static/*.html + static/*.js` 的静态页面模式，不存在组件化测试或框架路由基础设施。

因此 tracing 的实现应建立在这些已有入口之上，而不是另起一套新架构。

## 总体架构

### 架构原则

1. SQLite 表结构和 SQL 查询放在 `SessionDatabase` 中统一维护。
2. tracing 的业务编排逻辑集中在新的 `src/tracing/` 包中。
3. FastAPI 路由只负责参数校验、调用 tracing 查询接口和返回响应。
4. Agent 在关键节点调用 `TraceRecorder`，不直接拼接 SQL。
5. 静态页面直接调用 tracing API 获取数据。

### 系统结构

```mermaid
graph TB
    subgraph "静态前端"
        A[traces.html]
        B[trace_detail.html]
        C[history.html]
    end

    subgraph "API 层"
        D[GET /api/v1/traces]
        E[GET /api/v1/traces/{trace_id}]
        F[GET /api/v1/traces/stats]
        G[POST /api/v1/traces/export]
        H[GET /api/v1/sessions/{session_id}/traces]
    end

    subgraph "Tracing 业务层"
        I[TraceRecorder]
        J[trace utils / cleanup]
    end

    subgraph "现有运行链路"
        K[LLMAgent]
        L[GeneralChatToolAgent]
        M[SQLiteSessionManager]
    end

    subgraph "数据层"
        N[SessionDatabase]
        O[(runtime/sessions.db)]
    end

    A --> D
    B --> E
    C --> H
    D --> N
    E --> N
    F --> N
    G --> N
    H --> N
    K --> I
    L --> I
    I --> N
    M --> N
    N --> O
    J --> N
```

## 文件设计

### 新增文件

1. `src/tracing/__init__.py`
   暴露 tracing 包公共接口。
2. `src/tracing/constants.py`
   集中定义请求类型、trace 状态、tool call 状态、默认限制值和环境变量名。
3. `src/tracing/utils.py`
   放 `trace_id` 生成、敏感信息脱敏、JSON 截断、时间计算等纯函数。
4. `src/tracing/recorder.py`
   提供 `TraceRecorder`，负责异步写入调度、feature flag 判断、降级保护和 Agent 接入门面。
5. `src/tracing/cleanup.py`
   提供 trace 清理任务入口和后台循环逻辑。
6. `static/traces.html`
   追踪记录列表页。
7. `static/traces.js`
   列表页交互逻辑，含筛选、搜索、分页、导出。
8. `static/trace_detail.html`
   追踪详情页。
9. `static/trace_detail.js`
   详情页加载与展示逻辑。
10. `tests/unit/tracing/`
    tracing 纯逻辑和 recorder 单测目录。
11. `tests/unit/db/test_trace_queries.py`
    `SessionDatabase` 中 traces 相关 SQL 方法测试。
12. `tests/integration/test_traces_api.py`
    traces API 集成测试。

### 修改文件

1. `src/db/database.py`
   扩展建表、查询、导出、统计、清理相关 SQL。
2. `src/session_manager.py`
   启动时初始化 trace cleanup，必要时暴露 tracing 所需数据库入口。
3. `src/api.py`
   增加 traces API、页面入口和独立限流逻辑。
4. `src/agent/llm_agent.py`
   接入 `TraceRecorder` 并在关键节点记录 trace。
5. `src/agent/general_chat_agent.py`
   接入 `TraceRecorder` 并记录通用聊天工具调用与最终答复。
6. `static/index.html` / `static/app.js`
   增加 traces 页面入口。
7. `static/history.html` / `static/history.js`
   在会话详情区域展示当前 session 的 traces 摘要列表。
8. `.env.example`
   补充 tracing 相关配置项。
9. `README.md` 与 tracing 指南文档
   补充功能说明、开关、接口和页面入口。

## 数据模型设计

### 数据库存放位置

tracing 数据与现有会话数据共用 `runtime/sessions.db`。这样可以复用当前启动链和 SQLite 初始化路径，避免双数据库生命周期管理。

### 表结构

#### `traces`

字段：

1. `trace_id TEXT PRIMARY KEY`
2. `session_id TEXT NULL`
3. `user_input TEXT NOT NULL`
4. `request_type TEXT NOT NULL`
5. `status TEXT NOT NULL`
6. `final_answer TEXT NULL`
7. `created_at TIMESTAMP NOT NULL`
8. `completed_at TIMESTAMP NULL`
9. `total_time REAL NULL`
10. `error_message TEXT NULL`

索引：

1. `trace_id` 主键索引
2. `session_id` 索引
3. `created_at` 索引
4. `request_type` 索引
5. `status` 索引

#### `reasoning_steps`

字段：

1. `id INTEGER PRIMARY KEY AUTOINCREMENT`
2. `trace_id TEXT NOT NULL`
3. `step_number INTEGER NOT NULL`
4. `reasoning_content TEXT NOT NULL`
5. `timestamp TIMESTAMP NOT NULL`

约束：

1. `FOREIGN KEY(trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE`
2. `UNIQUE(trace_id, step_number)`

#### `tool_calls`

字段：

1. `tool_call_id TEXT PRIMARY KEY`
2. `trace_id TEXT NOT NULL`
3. `step_number INTEGER NOT NULL`
4. `tool_name TEXT NOT NULL`
5. `arguments TEXT NOT NULL`
6. `result TEXT NULL`
7. `status TEXT NOT NULL`
8. `started_at TIMESTAMP NOT NULL`
9. `completed_at TIMESTAMP NULL`
10. `execution_time REAL NULL`

约束：

1. `FOREIGN KEY(trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE`

### 标识符约定

1. `trace_id` 使用固定格式：`trace_<UTC时间戳>_<8位uuid>`
2. `tool_call_id` 优先复用 LLM 返回的工具调用 ID；没有时由系统生成 `tool_<trace_id>_<step_number>`

## TraceRecorder 设计

### 职责

`TraceRecorder` 负责：

1. 判断 `ENABLE_TRACING` 是否开启。
2. 生成 `trace_id`。
3. 对输入、推理、工具参数和工具结果做脱敏与截断。
4. 通过轻量异步任务把数据写入 `SessionDatabase`。
5. 兜底吞掉 tracing 相关异常并记录日志。

### 非职责

`TraceRecorder` 不负责：

1. 管理 SQLite 连接生命周期。
2. 承载 API 查询逻辑。
3. 构造页面展示格式。
4. 替代现有 session message 历史记录。

### 写入策略

1. 每次 recorder 方法调用都尽量快速返回。
2. 对持久化调用使用 `asyncio.create_task(...)` 或等价的轻量异步提交模式，保持与 `SQLiteSessionManager` 现有风格一致。
3. 当 tracing 数据库写入失败时，只记日志和指标，不向上抛出异常。

## 运行时数据流

### 诊断流程

1. 请求进入 `LLMAgent.diagnose()` 时创建 trace，状态为 `running`。
2. 每次 `_llm_decide_next_step()` 返回后，若有 `reasoning` 内容，则写入一条 `reasoning_steps`。
3. 每个工具调用开始前创建一条 `tool_calls` 记录，状态为 `running`。
4. 工具调用结束后写入结果、执行时间和完成状态。
5. 当诊断得出结论时，更新 trace 的 `final_answer`、`completed_at`、`total_time` 和 `status=completed`。
6. 当用户主动停止诊断时，更新 `status=interrupted`。
7. 当发生未处理异常时，更新 `status=failed` 和 `error_message`。
8. `NeedUserInputException` 表示流程暂停等待用户输入，不在此时结束 trace；trace 在继续诊断或最终失败时收尾。

### 通用聊天流程

1. 请求进入 `GeneralChatToolAgent.run()` 时创建 trace，状态为 `running`。
2. 每个工具调用开始和结束都写入 `tool_calls`。
3. 若 LLM 直接返回最终答复且没有工具调用，则立即完成 trace。
4. 若经过一轮或多轮工具调用，再拿到最终答复时完成 trace。
5. 通用聊天流程默认不写入 `reasoning_steps`，以避免把最终回答或系统提示误存为“推理过程”。

## API 设计

### `GET /api/v1/traces`

用途：

1. 分页列出 traces。
2. 支持 `session_id`、`request_type`、`start_time`、`end_time` 过滤。
3. 支持统一 `query` 参数：
   - 对 `user_input` 做模糊搜索
   - 对 `trace_id` 做精确匹配
   - 对 `session_id` 做精确匹配

响应结构：

```json
{
  "total": 123,
  "items": [
    {
      "trace_id": "trace_20260424T120000Z_ab12cd34",
      "session_id": "task_20260424195959_xxxx",
      "user_input": "10.0.1.10到10.0.2.20端口80不通",
      "request_type": "diagnosis",
      "status": "completed",
      "created_at": "2026-04-24T20:00:00+08:00",
      "completed_at": "2026-04-24T20:00:06+08:00",
      "total_time": 6.02
    }
  ]
}
```

### `GET /api/v1/traces/{trace_id}`

返回：

1. trace 基本信息
2. `reasoning_steps`
3. `tool_calls`

错误：

1. 格式不合法返回 400
2. 不存在返回 404

### `GET /api/v1/traces/stats`

返回：

1. 总 traces 数
2. 按请求类型计数
3. 按状态计数
4. 平均执行时间
5. 最近 24 小时计数
6. 最近 7 天计数

### `POST /api/v1/traces/export`

1. 入参复用列表查询过滤参数
2. 返回 CSV 流
3. 单次最多导出 1000 条记录

### `GET /api/v1/sessions/{session_id}/traces`

用途：

1. 返回指定 session 的 traces 摘要列表
2. 按 `created_at` 升序排序
3. 供会话详情页直接展示

这是会话关联需求的必要后端支撑接口。

## 前端设计

### 列表页

`static/traces.html` + `static/traces.js` 提供：

1. traces 列表
2. 分页
3. 会话 ID、请求类型、时间范围筛选
4. 搜索框
5. 导出按钮
6. 到详情页的链接

### 详情页

`static/trace_detail.html` + `static/trace_detail.js` 提供：

1. trace 基本信息
2. reasoning 时间线
3. tool call 时间线
4. 最终回答
5. JSON 格式化展示工具参数和结果

### 会话页集成

在 `static/history.html/js` 中追加：

1. 当前 session 的 trace 摘要列表
2. 展开/折叠交互
3. 跳转到详情页的链接

## 安全、隐私与错误处理

### 脱敏与截断

1. 对 `password`、`passwd`、`secret`、`token`、`key`、`credential` 等关键词做字段级脱敏。
2. 对工具参数和工具结果中的敏感键做递归处理。
3. 推理内容最大 5KB，工具结果最大 10KB，超出部分截断并加标记。

### 错误处理

1. tracing 写入失败只记日志，不中断主流程。
2. API 查询失败返回明确错误信息。
3. 静态页面列表页失败显示“无法加载追踪记录”。
4. 静态页面详情页失败显示“无法加载追踪详情”。

### 权限与限流

1. 当前仓库没有统一认证体系，因此 tracing API 本期不新增真实鉴权逻辑。
2. 在 API 层预留统一依赖或拦截点，以便后续接入权限控制。
3. tracing 查询接口使用独立的内存限流器，限制为每分钟 30 次。

## 清理与监控

### 清理

1. 使用 `TRACE_RETENTION_DAYS` 控制保留天数，默认 30 天。
2. 清理任务沿用现有后台 task 风格，不引入 APScheduler。
3. startup 后启动轻量后台循环，每天凌晨 2 点执行清理。
4. 删除过期 trace 时级联删除 `reasoning_steps` 和 `tool_calls`。

### 监控

首期使用轻量实现：

1. 记录 tracing 写入成功次数。
2. 记录 tracing 写入失败次数。
3. 记录 traces 查询耗时日志。
4. 在查询或清理后记录 SQLite 文件大小。

不为 tracing 单独引入 Prometheus 依赖。

## 配置项

新增或明确以下环境变量：

1. `ENABLE_TRACING=true|false`
2. `TRACE_RETENTION_DAYS=30`
3. `TRACE_QUERY_RATE_LIMIT_PER_MINUTE=30`
4. `TRACE_REASONING_MAX_BYTES=5120`
5. `TRACE_TOOL_RESULT_MAX_BYTES=10240`

## 测试策略

### 单元测试

1. `tests/unit/tracing/`：
   - `trace_id` 生成
   - 脱敏逻辑
   - 截断逻辑
   - recorder 在关闭开关和数据库异常下的降级行为
2. `tests/unit/db/`：
   - traces 建表与查询 SQL
   - 过滤、排序、分页
   - 级联删除
3. `tests/unit/agent/`：
   - `LLMAgent` tracing 接入
   - `GeneralChatToolAgent` tracing 接入

### 集成测试

1. traces 列表 API
2. traces 详情 API
3. traces 统计 API
4. traces 导出 API
5. session traces 关联 API

### 端到端测试

1. 诊断请求完整 trace 链路
2. 通用聊天请求完整 trace 链路

### 前端验证策略

前端不引入新的组件测试框架。列表页和详情页优先通过：

1. JS 最小行为测试
2. API 集成测试
3. 端到端手工或自动回归

来覆盖关键行为。

## 非目标

本次设计不包含以下内容：

1. 为 tracing 重构整个项目架构。
2. 引入 ORM 或迁移框架。
3. 引入前端组件化框架。
4. 建立完整的用户认证与授权体系。
5. 记录原始未脱敏的敏感数据。

## 设计结论

本方案以“兼容现有代码组织”为核心原则，将 tracing 作为现有 SQLite、FastAPI、SessionManager 和静态页面体系上的增量能力实现。这样既能满足全量需求，又能把任务拆解为与当前仓库一致、可以直接执行的实现步骤，为后续重写 `tasks.md` 提供明确边界。
