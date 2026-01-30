# Changelog

本项目的所有重要变更都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中
- Phase 2: 接入真实自动化平台和CMDB
- Phase 2: 支持禁ping场景和ping网关验证
- Phase 2: 异步任务机制
- Phase 2: 快速模式vs深度模式
- Phase 3: AI推理增强
- Phase 3: Web UI聊天机器人

## [1.0.0] - 2026-01-13

### 新增
- 基础项目结构搭建
- Phase 1核心功能实现
  - 端口不可达故障排查（3个场景）
  - 固定流程引擎（YAML工作流定义）
  - 6个命令输出解析器
  - Mock自动化平台和CMDB客户端
  - Markdown报告生成器
- 测试框架
  - 单元测试（覆盖率 ≥ 80%）
  - 集成测试（3个场景）
  - Mock数据（50台服务器）
- CLI命令行工具
  - `netops diagnose` - 提交排查任务
  - `netops status` - 查询任务状态
  - `netops report` - 查看排查报告
- 开发工具
  - Makefile快捷命令
  - 代码检查和格式化（black、mypy、ruff）
  - Mock数据生成脚本

### 文档
- 产品规格说明书 (spec.md)
- 解析器设计文档 (parsers_design.md)
- README.md
- API文档
- 工作流设计文档

### 技术栈
- Python 3.10+
- Pydantic 2.0+ (数据模型)
- PyYAML 6.0+ (配置管理)
- Structlog 23.0+ (日志)
- Typer 0.9+ (CLI)
- Rich 13.0+ (终端输出)
- pytest 7.4+ (测试)

## [0.1.0] - 2026-01-05

### 新增
- 项目初始化
- 需求调研和方案设计

---

## 版本说明

- **主版本号**: 重大架构变更或不兼容的API修改
- **次版本号**: 向下兼容的功能新增
- **修订号**: 向下兼容的问题修正

[Unreleased]: https://github.com/yourorg/netOpsAgent/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourorg/netOpsAgent/releases/tag/v1.0.0
[0.1.0]: https://github.com/yourorg/netOpsAgent/releases/tag/v0.1.0
