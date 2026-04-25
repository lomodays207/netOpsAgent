# netOpsAgent

智能网络故障排查Agent，用于大规模数据中心环境的自动化网络故障诊断。

## 项目概述

netOpsAgent是一个基于Python的智能Agent，能够自动化执行网络故障排查流程，通过结合固定流程引擎和AI推理能力，将故障排查时间从数小时缩短至分钟级别。

### 核心特性

- 🚀 **自动化排查**: 支持端口不可达、连通性问题等常见故障类型的自动化诊断
- 🎯 **高准确率**: 基于决策树的固定流程 + AI推理兜底，根因判断准确率 > 85%
- 📊 **详细报告**: 自动生成Markdown格式的排查报告，包含所有执行步骤和诊断结论
- 🔒 **安全可靠**: 命令白名单机制，所有执行命令经过严格验证
- 🧪 **易于测试**: 完善的Mock机制，支持离线开发和测试

### 支持的故障类型 (Phase 1)

- ✅ 端口不可达 (telnet失败)
  - Connection Refused → 服务未启动
  - Connection Timeout + Ping通 → 防火墙策略问题
  - Connection Timeout + Ping不通 → 网络路径故障

## 快速开始

### 环境要求

- Python >= 3.10
- pip >= 20.0

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/yourorg/netOpsAgent.git
cd netOpsAgent
```

2. **创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**
```bash
make install
# 或
pip install -r requirements.txt -r requirements-dev.txt
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑.env文件，配置API地址和Token
```

### 使用示例

```bash
# 基本用法
python -m src.cli diagnose "server1到server2端口80不通"

# 查看任务状态
python -m src.cli status <task_id>

# 查看排查报告
python -m src.cli report <task_id>
```

## 项目结构

```
netOpsAgent/
├── src/                    # 源代码
│   ├── agent/              # Agent核心模块
│   ├── integrations/       # 外部系统集成
│   ├── models/             # 数据模型
│   └── utils/              # 工具函数和解析器
├── tests/                  # 测试代码
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   └── fixtures/           # Mock数据
├── config/                 # 配置文件
│   └── workflows/          # 故障排查流程定义
├── docs/                   # 文档
├── scripts/                # 开发脚本
└── runtime/                # 运行时数据 (报告、日志)
```

## 开发指南

### 运行测试

```bash
# 运行所有测试
make test

# 运行单元测试
make test-unit

# 运行集成测试
make test-integration
```

### 代码检查

```bash
# 运行代码检查
make lint

# 自动格式化代码
make format
```

### 清理临时文件

```bash
make clean
```

## Phase 1 验收标准

- ✅ 3个核心测试场景100%通过
- ✅ 单元测试覆盖率 ≥ 80%
- ✅ 根因判断准确率 ≥ 90%
- ✅ 单次排查耗时 ≤ 10秒

## 技术栈

- **开发语言**: Python 3.10+
- **数据模型**: Pydantic
- **异步IO**: asyncio + aiohttp
- **配置管理**: YAML
- **日志**: structlog
- **CLI**: Typer + Rich
- **测试**: pytest + pytest-asyncio

## 文档

- [产品规格说明书](docs/spec.md)
- [架构设计文档](docs/architecture.md) ⭐ **全面的架构和设计文档**
- [解析器设计文档](docs/parsers_design.md)
- [LLM 使用指南](docs/LLM_GUIDE.md)
- [会话持久化说明](docs/session_persistence_walkthrough.md)
- [API 文档](http://localhost:8000/docs) (启动 API 后访问)

## 贡献指南

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交变更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交Pull Request

## 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 项目维护者: NetOps Team
- 项目主页: https://github.com/yourorg/netOpsAgent

## 致谢

感谢所有为本项目做出贡献的开发者！


## Tracing

Tracing support is available and disabled by default.

- Configuration: `.env.example`
- Guide: `docs/tracing_guide.md`
- Pages:
- `/static/traces.html`
- `/static/trace_detail.html`
- `/static/history.html`
