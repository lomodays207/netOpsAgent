# 多轮对话持久化功能文档

本目录包含多轮对话持久化功能的完整文档。

## 📚 文档列表

### 1. [实现方案](./session_persistence_implementation_plan.md)
**内容**：详细的技术实现方案
- 背景和目标
- 数据库设计（SQLite表结构）
- 序列化策略
- SessionManager改造方案
- API接口适配
- 验证计划
- 技术风险和缓解措施

**适合阅读对象**：开发人员、架构师

---

### 2. [实现总结](./session_persistence_walkthrough.md)
**内容**：实现完成后的总结文档
- 实现的变更（新增/修改的文件）
- 测试验证结果
- 使用方法和示例
- 数据库管理
- 技术亮点
- 后续优化建议

**适合阅读对象**：所有人

---

### 3. [前端会话持久化](./frontend_session_persistence.md)
**内容**：前端localStorage会话持久化功能
- 新增功能说明
- 工作原理
- 测试步骤
- 开发者调试方法
- 与后端的集成

**适合阅读对象**：前端开发人员、测试人员

---

## 🎯 快速开始

### 用户使用

1. 启动服务：
   ```bash
   uvicorn src.api:app --reload
   ```

2. 打开浏览器访问：http://localhost:8000/

3. 输入故障描述，开始诊断

4. **刷新页面** - 对话历史会自动恢复

5. 继续对话 - 系统会记住之前的上下文

### 开发者测试

查看 [实现总结 - 验证计划](./session_persistence_walkthrough.md#验证计划) 部分

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面                              │
│                    (Web Browser)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP/SSE
                     │
┌────────────────────▼────────────────────────────────────────┐
│                     FastAPI Server                          │
│                      (src/api.py)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │
┌────────────────────▼────────────────────────────────────────┐
│                 SQLiteSessionManager                        │
│                (src/session_manager.py)                     │
│                                                             │
│  ┌──────────────┐        ┌──────────────────────────┐     │
│  │   内存缓存    │        │   SessionDatabase        │     │
│  │  (快速访问)   │  ←→   │   (src/db/database.py)   │     │
│  └──────────────┘        └──────────────────────────┘     │
│                                    │                        │
│                                    │                        │
│                          ┌─────────▼─────────┐             │
│                          │  SQLite Database  │             │
│                          │ runtime/sessions.db│            │
│                          └───────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 核心特性

### 后端持久化 (SQLite)
- ✅ 会话数据持久化到数据库
- ✅ 服务重启后自动恢复会话
- ✅ Agent 和 LLMClient 自动重建
- ✅ 完整的对话历史和上下文保存

### 前端持久化 (localStorage)
- ✅ 会话ID和消息历史保存到浏览器
- ✅ 页面刷新后自动恢复对话
- ✅ 新对话按钮（清除当前会话）
- ✅ 会话恢复提示

### 双层持久化
```
前端 localStorage          后端 SQLite
      ↓                        ↓
  会话ID + 消息      ←→    会话 + 上下文 + Agent
      ↓                        ↓
  页面刷新恢复       ←→    服务重启恢复
```

---

## 📊 数据库表结构

### sessions 表
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    task_data TEXT NOT NULL,           -- JSON序列化的DiagnosticTask
    context TEXT,                       -- JSON序列化的context列表
    status TEXT NOT NULL,               -- active, waiting_user, completed, error
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    pending_question TEXT,              -- LLM的提问
    llm_config TEXT                     -- LLM配置
);
```

### messages 表
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                 -- user, assistant, system
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
```

---

## 🔧 技术栈

- **后端框架**: FastAPI
- **数据库**: SQLite + aiosqlite (异步操作)
- **序列化**: JSON
- **前端存储**: localStorage
- **会话管理**: 双层存储（内存 + 数据库）

---

## 📝 相关文件

### 新增文件
- `src/db/database.py` - 数据库管理
- `src/db/serializers.py` - 对象序列化工具
- `src/db/__init__.py` - 模块导出

### 修改文件
- `src/session_manager.py` - 添加 SQLiteSessionManager
- `src/api.py` - 数据库初始化和异步会话获取
- `static/app.js` - 前端会话持久化
- `requirements.txt` - 添加 aiosqlite 依赖

### 文档文件
- `docs/session_persistence_implementation_plan.md` - 实现方案
- `docs/session_persistence_walkthrough.md` - 实现总结
- `docs/frontend_session_persistence.md` - 前端持久化说明
- `docs/README_session_persistence.md` - 本文档

---

## 🧪 测试

### 自动化测试
```bash
python tests/test_session_persistence.py
```

### 手动测试
1. 启动服务
2. 发起诊断请求
3. 重启服务
4. 继续对话
5. 验证会话恢复

详细测试步骤见 [实现总结 - 验证计划](./session_persistence_walkthrough.md#验证计划)

---

## 🚀 后续优化

### 性能优化
- [ ] 添加连接池
- [ ] 批量操作优化
- [ ] 更多索引优化

### 功能扩展
- [ ] 会话导出/导入功能
- [ ] 历史会话查询 API
- [ ] 会话统计分析

### 可观测性
- [ ] 数据库操作日志
- [ ] 会话数量和存储监控
- [ ] 告警机制

详见 [实现总结 - 后续优化](./session_persistence_walkthrough.md#后续优化建议)

---

## 📞 问题反馈

如有问题或建议，请查看相关文档或联系开发团队。
