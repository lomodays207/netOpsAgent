---
# 代码的入口
主入口文件：src/cli.py
这个项目使用 Typer 框架构建 CLI 工具，入口点在 pyproject.toml:33 中定义为：
[project.scripts]
netops = "src.cli:main"
---
---
# 启动方式
方案1：HTTP API 接口（推荐）

(.venv) PS D:\study\aicode\netOpsAgent> .\scripts\start_api.bat

  调用示例：
  curl -X POST "http://localhost:8000/api/v1/diagnose" \
    -H "Content-Type: application/json" \
    -d '{"description": "10.0.1.10到10.0.2.20端口80不通", "use_llm": true}'

  API 文档地址：http://localhost:8000/docs （启动后访问）

  方案2：继续使用 CLI
  python -m src.cli diagnose "10.0.1.10到10.0.2.20端口80不通" --agent-mode
---

---
# 测试 API

  # 健康检查
  curl http://localhost:8000/health

  # 查看API文档
  浏览器访问: http://localhost:8000/docs

  # 测试诊断
  curl -X POST http://localhost:8000/api/v1/diagnose ^
    -H "Content-Type: application/json" ^
    -d "{\"description\":\"10.0.1.10到10.0.2.20端口80不通\",\"use_llm\":true}"

  # 测试流式诊断
  curl -X POST http://localhost:8000/api/v1/diagnose/stream ^
    -H "Content-Type: application/json" ^
    -d "{\"description\":\"10.0.1.10到10.0.2.20端口80不通\",\"use_llm\":true}"

  # 测试多轮对话
  curl -X POST http://localhost:8000/api/v1/chat/answer ^
    -H "Content-Type: application/json" ^
    -d "{\"description\":\"10.0.1.10到10.0.2.20端口80不通\",\"use_llm\":true}"

  ---
  
# 开发规范
## 所有的测试代码 要放到 tests 目录里面
## 启动、关闭脚本都放 scripts 目录里面
## 所有的文档，需求分析、设计文档等，都放 docs 目录里面
## 任何涉及外部工具调用，都使用 Mock 数据，不要调用真实的工具，返回的格式要和真实工具返回的格式一致