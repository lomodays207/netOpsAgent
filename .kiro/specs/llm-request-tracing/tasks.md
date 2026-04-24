# LLM 请求链路追踪功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 netOpsAgent 中新增可持久化、可查询、可导出、可视化的 LLM 请求链路追踪能力，覆盖诊断流、通用聊天流和会话详情页关联展示。

**Architecture:** 基于现有 `aiosqlite + SessionDatabase + SQLiteSessionManager + FastAPI + static/*.html/js` 结构增量实现 tracing。数据库表结构和 SQL 方法继续放在 `SessionDatabase` 中，运行时采集逻辑集中在 `src/tracing/` 包，前端继续使用静态 HTML/JS 页面。

**Tech Stack:** Python 3.10+, FastAPI, aiosqlite, LangChain, 原生 HTML/CSS/JS, pytest, pytest-asyncio

---

## 执行前提

1. 复用 `runtime/sessions.db`，不新建独立 tracing 数据库。
2. 不引入 SQLAlchemy、Repository/Service 分层、APScheduler、Prometheus、React、Vue。
3. `GeneralChatToolAgent` 默认不记录 `reasoning_steps`，仅记录工具调用和最终答复。
4. tracing 查询接口本期不新增真实鉴权逻辑，只预留统一依赖或钩子位置。
5. 前端测试不引入新的组件测试框架，静态页以 smoke test、API 集成测试和手工验证为主。

## 文件结构总览

**Create:**

- `src/tracing/__init__.py`
- `src/tracing/constants.py`
- `src/tracing/utils.py`
- `src/tracing/recorder.py`
- `src/tracing/cleanup.py`
- `static/traces.html`
- `static/traces.js`
- `static/trace_detail.html`
- `static/trace_detail.js`
- `tests/unit/tracing/test_trace_utils.py`
- `tests/unit/tracing/test_trace_recorder.py`
- `tests/unit/db/test_trace_storage.py`
- `tests/integration/test_traces_api.py`
- `tests/e2e/test_traces_e2e.py`
- `docs/tracing_guide.md`

**Modify:**

- `.env.example`
- `src/db/database.py`
- `src/session_manager.py`
- `src/api.py`
- `src/agent/llm_agent.py`
- `src/agent/general_chat_agent.py`
- `static/index.html`
- `static/app.js`
- `static/history.html`
- `static/history.js`
- `README.md`

## Task 1: 建立 tracing 配置和公共模块

**Files:**
- Create: `src/tracing/__init__.py`
- Create: `src/tracing/constants.py`
- Create: `src/tracing/utils.py`
- Create: `tests/unit/tracing/test_trace_utils.py`
- Modify: `.env.example`

- [ ] 在 `.env.example` 中新增 `ENABLE_TRACING`、`TRACE_RETENTION_DAYS`、`TRACE_QUERY_RATE_LIMIT_PER_MINUTE`、`TRACE_REASONING_MAX_BYTES`、`TRACE_TOOL_RESULT_MAX_BYTES`。
- [ ] 在 `src/tracing/constants.py` 中集中定义 trace 状态、tool call 状态、请求类型、默认字节限制和环境变量名，避免在 Agent、API、数据库层散落字符串字面量。
- [ ] 在 `src/tracing/utils.py` 中实现 `build_trace_id()`、`mask_sensitive_data()`、`truncate_text()`、`truncate_json_payload()`、`calculate_total_time()` 等纯函数。
- [ ] 在 `tests/unit/tracing/test_trace_utils.py` 中覆盖 trace_id 格式、敏感字段脱敏、5KB/10KB 截断和空值输入场景。
- [ ] Run: `pytest tests/unit/tracing/test_trace_utils.py -q`
- [ ] 预期：trace 工具函数测试全部通过。

_需求: 1.1-1.9, 12.3-12.4, 14.1, 14.5, 16.1-16.2_

## Task 2: 扩展 SessionDatabase 的 tracing 表结构与基础写入接口

**Files:**
- Modify: `src/db/database.py`
- Create: `tests/unit/db/test_trace_storage.py`

- [ ] 在 `SessionDatabase.initialize()` 中新增 `traces`、`reasoning_steps`、`tool_calls` 三张表及其索引和外键约束。
- [ ] 增加基础写入接口：`create_trace()`、`update_trace()`、`add_reasoning_step()`、`create_tool_call()`、`complete_tool_call()`。
- [ ] 明确 `trace_id` 主键、`session_id`/`created_at` 索引、`reasoning_steps(trace_id, step_number)` 唯一约束和 tool call 级联删除。
- [ ] 在 `tests/unit/db/test_trace_storage.py` 中使用临时 SQLite 数据库验证建表、主键/外键、基础写入、状态更新和级联删除。
- [ ] Run: `pytest tests/unit/db/test_trace_storage.py -q`
- [ ] 预期：数据库 schema 与基础 CRUD 测试全部通过。

_需求: 1.1-1.9, 2.1-2.5, 3.1-3.10, 4.1-4.8_

## Task 3: 扩展 SessionDatabase 的 tracing 查询、统计、导出和清理接口

**Files:**
- Modify: `src/db/database.py`
- Modify: `tests/unit/db/test_trace_storage.py`

- [ ] 增加 `list_traces()`，支持 `page`、`page_size`、`session_id`、`request_type`、`start_time`、`end_time`、统一 `query` 参数，并默认按 `created_at DESC` 排序。
- [ ] 增加 `get_trace_detail()`，返回 trace、`reasoning_steps`、`tool_calls`，并保证两个子列表按 `step_number ASC` 排序。
- [ ] 增加 `get_trace_stats()`，返回总数、按请求类型计数、按状态计数、平均执行时间、最近 24 小时和最近 7 天计数。
- [ ] 增加 `list_session_traces()`，按 `created_at ASC` 返回指定 session 的 trace 摘要列表，供会话详情页使用。
- [ ] 增加 `export_traces()` 和 `delete_expired_traces()`，分别用于 CSV 导出和按保留期清理过期记录。
- [ ] 在现有数据库测试中补充过滤、模糊搜索、精确匹配、分页、导出上限和清理逻辑用例。
- [ ] Run: `pytest tests/unit/db/test_trace_storage.py -q`
- [ ] 预期：查询、统计、导出、清理相关单测全部通过。

_需求: 7.1-7.7, 8.1-8.7, 11.1-11.5, 17.1-17.5, 18.1-18.5, 19.1-19.7, 20.1-20.5_

## Task 4: 实现 TraceRecorder 与 tracing 清理循环

**Files:**
- Create: `src/tracing/recorder.py`
- Create: `src/tracing/cleanup.py`
- Create: `tests/unit/tracing/test_trace_recorder.py`
- Modify: `src/session_manager.py`

- [ ] 在 `src/tracing/recorder.py` 中实现 `TraceRecorder`，封装 `start_trace()`、`add_reasoning_step()`、`start_tool_call()`、`complete_tool_call()`、`complete_trace()`、`fail_trace()`、`interrupt_trace()`。
- [ ] 让 `TraceRecorder` 在 `ENABLE_TRACING=false` 时退化为空操作，并在数据库异常时吞掉异常、记录日志，不影响主流程。
- [ ] 在 recorder 中统一做敏感字段脱敏、payload 截断和 `asyncio.create_task(...)` 方式的轻量异步提交。
- [ ] 在 `src/tracing/cleanup.py` 中实现 tracing 清理任务入口和每天凌晨 2 点执行的后台循环逻辑。
- [ ] 在 `src/session_manager.py` 中接入 tracing cleanup 的启动逻辑，保持与现有 `SQLiteSessionManager` 启动链一致。
- [ ] 在 `tests/unit/tracing/test_trace_recorder.py` 中覆盖关闭开关、完整生命周期、数据库失败降级、工具调用更新和清理任务调用。
- [ ] Run: `pytest tests/unit/tracing/test_trace_recorder.py -q`
- [ ] 预期：recorder 与 cleanup 相关单测全部通过。

_需求: 5.1-5.6, 6.1-6.5, 11.1-11.5, 12.1-12.5, 13.1, 14.1, 14.5, 15.5, 16.1-16.5_

## Task 5: 将 tracing 集成到 LLMAgent 诊断流程

**Files:**
- Modify: `src/agent/llm_agent.py`
- Modify: `tests/unit/agent/test_llm_agent_simple.py`

- [ ] 在 `LLMAgent` 中注入 `TraceRecorder`，优先通过构造参数传入，默认可从现有 session/database 上下文创建。
- [ ] 在 `diagnose()` 和 `continue_diagnose()` 入口创建或续接 trace，并记录 `request_type=diagnosis`。
- [ ] 在每次 `_llm_decide_next_step()` 返回后记录 reasoning 内容；在工具调用开始/结束时记录 tool call；在用户主动停止时写 `interrupted`。
- [ ] 将 `NeedUserInputException` 视为流程暂停而非失败，避免在追问用户时过早结束 trace。
- [ ] 在正常诊断完成、异常失败和中断场景中分别写入 `completed`、`failed`、`interrupted`。
- [ ] 在 `tests/unit/agent/test_llm_agent_simple.py` 中补充 tracing 接入用例，覆盖正常完成、工具调用、用户追问后续接和 stop_event 中断。
- [ ] Run: `pytest tests/unit/agent/test_llm_agent_simple.py -q`
- [ ] 预期：LLMAgent 现有能力不回归，新增 tracing 断言通过。

_需求: 2.1-2.5, 3.1-3.10, 5.1-5.6, 12.1-12.5, 13.1, 16.3-16.5_

## Task 6: 将 tracing 集成到 GeneralChatToolAgent 通用聊天流程

**Files:**
- Modify: `src/agent/general_chat_agent.py`
- Modify: `tests/test_general_chat_agent.py`

- [ ] 在 `GeneralChatToolAgent` 中注入 `TraceRecorder` 并记录 `request_type=general_chat`。
- [ ] 在 `run()` 入口创建 trace，在每次工具调用开始/结束时记录 tool call。
- [ ] 对“无工具直接答复”和“多轮工具调用后答复”两条路径都写入最终 trace 状态。
- [ ] 显式保持通用聊天流程不生成 `reasoning_steps`，避免存入不可靠的“思考文本”。
- [ ] 在异常路径上调用 `fail_trace()`，同时确保 tracing 失败不影响聊天主流程。
- [ ] 在 `tests/test_general_chat_agent.py` 中补充 tracing 用例，覆盖无工具回复、query_access_relations 工具调用和工具异常降级。
- [ ] Run: `pytest tests/test_general_chat_agent.py -q`
- [ ] 预期：通用聊天场景新增 tracing 行为验证通过。

_需求: 3.1-3.10, 6.1-6.5, 12.1-12.5, 13.1, 16.3-16.5_

## Task 7: 在 FastAPI 中暴露 tracing 查询接口和访问钩子

**Files:**
- Modify: `src/api.py`
- Create: `tests/integration/test_traces_api.py`

- [ ] 在 `src/api.py` 中新增 tracing 查询依赖或钩子函数，例如 `require_trace_access()`，当前版本默认放行，但要让接口边界显式存在。
- [ ] 实现 `GET /api/v1/traces` 和 `GET /api/v1/traces/{trace_id}`，包括参数校验、trace_id 格式校验、404/400 响应和数据库调用。
- [ ] 实现 `GET /api/v1/sessions/{session_id}/traces`，供会话详情页展示当前 session 的 trace 摘要列表。
- [ ] 为 tracing 查询接口增加独立的内存限流逻辑，限制为每分钟 30 次，不与现有知识库文档预览接口共用计数桶。
- [ ] 在 `tests/integration/test_traces_api.py` 中补充列表、详情、session traces、trace_id 非法、trace 不存在和 429 限流场景。
- [ ] Run: `pytest tests/integration/test_traces_api.py -q`
- [ ] 预期：tracing 基础查询接口和限流测试全部通过。

_需求: 7.1-7.7, 8.1-8.7, 13.5, 14.2-14.4, 18.1-18.5, 20.1-20.5_

## Task 8: 在 FastAPI 中实现 tracing 统计与导出接口

**Files:**
- Modify: `src/api.py`
- Modify: `tests/integration/test_traces_api.py`

- [ ] 实现 `GET /api/v1/traces/stats`，返回总数、按请求类型计数、按状态计数、平均执行时间、最近 24 小时和最近 7 天计数。
- [ ] 实现 `POST /api/v1/traces/export`，支持复用列表过滤条件并导出 CSV，单次导出上限为 1000 条。
- [ ] 保持导出接口的错误消息、空结果行为和响应头与静态页面下载场景兼容。
- [ ] 在 integration 测试中补充统计返回、CSV 内容、过滤导出和超限导出场景。
- [ ] Run: `pytest tests/integration/test_traces_api.py -q`
- [ ] 预期：统计与导出接口相关集成测试全部通过。

_需求: 13.1-13.5, 17.1-17.5, 19.1-19.7_

## Task 9: 实现 traces 列表静态页面和入口导航

**Files:**
- Create: `static/traces.html`
- Create: `static/traces.js`
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `static/style.css`

- [ ] 新增 traces 列表页模板，展示 trace_id、用户提问、请求类型、状态、创建时间、执行时间。
- [ ] 在 `static/traces.js` 中实现分页、筛选、统一搜索框、防抖刷新和导出按钮逻辑。
- [ ] 在首页或现有导航中增加进入 traces 列表页的入口，保持视觉风格与现有静态页面一致。
- [ ] 对列表加载失败和空结果分别给出明确提示文案“无法加载追踪记录”和“暂无追踪记录”。
- [ ] 为静态资源和页面入口增加至少一个 smoke test，优先复用现有 HTML/JS 页面测试模式。
- [ ] Run: `pytest tests/integration/test_traces_api.py -q`
- [ ] 预期：前端列表页可通过 API 正常加载数据，页面入口可访问。

_需求: 9.1-9.7, 13.2, 17.1, 18.1-18.5_

## Task 10: 实现 trace 详情页和会话详情页集成

**Files:**
- Create: `static/trace_detail.html`
- Create: `static/trace_detail.js`
- Modify: `static/history.html`
- Modify: `static/history.js`
- Modify: `static/style.css`

- [ ] 新增 trace 详情页，展示 trace 基本信息、reasoning 时间线、tool call 时间线、最终回答和 JSON 格式化工具参数/结果。
- [ ] 在 `static/trace_detail.js` 中实现 trace_id 读取、详情加载、错误提示“无法加载追踪详情”和空数据保护。
- [ ] 在 `static/history.html/js` 中新增当前 session 的 traces 列表区域，支持展开/折叠并按 `created_at ASC` 展示。
- [ ] 点击会话页中的 trace 项可跳转到详情页；点击列表页中的行也可进入详情页。
- [ ] 为详情页和会话页集成添加 smoke test 或最小行为验证，至少覆盖页面入口和关键 DOM 标识存在性。
- [ ] Run: `pytest tests/integration/test_traces_api.py -q`
- [ ] 预期：trace 详情页和会话详情页关联展示工作正常。

_需求: 10.1-10.8, 13.3, 20.1-20.5_

## Task 11: 完成日志、轻量监控、文档和端到端验证

**Files:**
- Modify: `src/tracing/recorder.py`
- Modify: `src/tracing/cleanup.py`
- Modify: `src/api.py`
- Create: `tests/e2e/test_traces_e2e.py`
- Create: `docs/tracing_guide.md`
- Modify: `README.md`
- Modify: `.env.example`

- [ ] 在 tracing 写入、查询、清理路径上补齐结构化日志，确保数据库失败、导出失败和 cleanup 执行结果都有明确日志。
- [ ] 实现轻量监控方案：记录 tracing 写入成功次数、失败次数、查询耗时和 SQLite 文件大小，不引入新的 metrics 依赖。
- [ ] 更新 `README.md` 和 `docs/tracing_guide.md`，说明开关、保留期、限制、页面入口和主要 API。
- [ ] 编写 `tests/e2e/test_traces_e2e.py`，至少覆盖“诊断请求完整 trace 链路”和“通用聊天请求完整 trace 链路”两条端到端路径。
- [ ] Run: `pytest tests/unit/tracing tests/unit/db/test_trace_storage.py tests/unit/agent/test_llm_agent_simple.py tests/test_general_chat_agent.py tests/integration/test_traces_api.py tests/e2e/test_traces_e2e.py -q`
- [ ] 预期：tracing 相关单测、集成测试和端到端测试全部通过。

_需求: 11.1-11.5, 13.1-13.5, 15.1-15.5, 16.1-16.5, 17.1-17.5, 19.1-19.7, 所有文档相关需求_

## Final Verification

- [ ] 运行 `pytest tests/unit/tracing tests/unit/db/test_trace_storage.py tests/unit/agent/test_llm_agent_simple.py tests/test_general_chat_agent.py tests/integration/test_traces_api.py tests/e2e/test_traces_e2e.py -q`
- [ ] 手工验证 `static/traces.html`、`static/trace_detail.html`、`static/history.html` 的页面跳转、筛选、导出和错误提示。
- [ ] 确认 tracing 关闭时主流程行为与当前版本一致。
- [ ] 确认 tracing 数据库不可用时，诊断流和通用聊天流仍可正常返回结果。
- [ ] 确认导出上限、trace_id 格式校验、限流 429 和过期清理均符合设计文档。

## 覆盖说明

1. 需求 1-4 由 Task 1-4 覆盖。
2. 需求 5-6 由 Task 5-6 覆盖。
3. 需求 7-8、17-20 由 Task 7-10 覆盖。
4. 需求 11-16 由 Task 1、Task 4、Task 7、Task 11 覆盖。
5. 需求 14.2 在本期以接口钩子和架构预留方式满足，不新增真实鉴权实现。
