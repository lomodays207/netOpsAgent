# Repository Guidelines

## Project Structure & Module Organization
`src/` 是主代码目录：`agent/` 负责诊断与意图路由，`integrations/` 对接 LLM、CMDB 和网络工具，`rag/` 负责知识检索，`models/` 与 `db/` 提供数据模型和持久化，`utils/` 放解析器与格式化工具。`tests/` 按 `unit/`、`integration/`、`e2e/` 分层，根目录还保留少量回归测试文件。静态页面位于 `static/`，流程配置在 `config/workflows/`，运行产物写入 `runtime/`，设计与计划文档集中在 `docs/` 和 `docs/superpowers/`。

## Build, Test, and Development Commands
先创建虚拟环境并安装依赖：`python -m venv .venv`，激活后执行 `make install`。
本地 CLI 调试可用 `python -m src.cli diagnose "10.0.1.10到10.0.2.20端口80不通"`。
启动 API 用 `uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload`。
常用质量命令：`make test` 运行全部测试并生成覆盖率，`make test-unit` / `make test-integration` 跑分层测试，`make lint` 执行 `black --check`、`ruff check`、`mypy src/`，`make format` 自动格式化。

## Coding Style & Naming Conventions
项目使用 Python 3.10+，统一 4 空格缩进，`black` 与 `ruff` 行宽均为 100。新增函数应补全类型标注；`mypy` 已开启 `disallow_untyped_defs`。模块与文件使用 `snake_case`，类使用 `PascalCase`，测试函数命名为 `test_*`。优先复用现有目录边界，不要把 API、诊断逻辑和工具封装混写到同一文件。

## Testing Guidelines
测试框架为 `pytest` + `pytest-asyncio` + `pytest-cov`。提交前至少运行与改动相关的测试；涉及路由、解析器或 RAG 行为时，优先补充 `tests/unit/` 回归用例，跨模块流程变更放入 `tests/integration/` 或 `tests/e2e/`。覆盖率默认统计 `src/`，报告输出到 `htmlcov/`。测试数据放在 `tests/fixtures/` 或现有 JSON 样例中，避免把临时脚本当正式测试。

## Commit & Pull Request Guidelines
最近提交同时使用简短中文摘要和 Conventional Commit 前缀，如 `fix: ...`、`feat: ...`、`test: ...`。保持单次提交只表达一个意图，标题使用祈使句并点明范围，例如 `fix: harden hybrid intent routing`。PR 需要说明变更目的、影响范围、测试结果；若改动 `static/` 页面或接口交互，请附截图、录屏或示例请求。关联对应 issue、设计文档或 `docs/superpowers/plans/` 计划文件。

## Security & Configuration Tips
从 `.env.example` 复制生成本地 `.env`，不要提交真实密钥、接口地址或运行期数据。`runtime/`、`htmlcov/`、`.coverage` 和调试输出文件仅用于本地验证；除非变更明确要求，否则不要纳入提交。
