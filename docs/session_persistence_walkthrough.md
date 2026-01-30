# 多轮对话SQLite持久化实现完成

## 概述

成功实现了基于 SQLite 的会话持久化存储，使多轮对话能够在服务重启后继续进行。系统现在可以：
- ✅ 将会话数据持久化到 SQLite 数据库
- ✅ 在服务重启后自动恢复会话
- ✅ 重建 Agent 和 LLMClient 对象
- ✅ 保持完整的对话历史和上下文

---

## 实现的变更

### 新增文件

#### 1. [database.py](file:///d:/study/aicode/netOpsAgent/src/db/database.py)

**功能**：SQLite 数据库管理模块

**核心特性**：
- 使用 `aiosqlite` 实现异步数据库操作
- 启用 WAL 模式提高并发性能
- 实现完整的 CRUD 操作
- 自动创建索引优化查询性能

**数据库表结构**：

```sql
-- 会话主表
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    task_data TEXT NOT NULL,           -- JSON序列化的DiagnosticTask
    context TEXT,                       -- JSON序列化的context列表
    status TEXT NOT NULL,               -- active, waiting_user, completed, error
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    pending_question TEXT,              -- LLM的提问
    llm_config TEXT                     -- LLM配置（用于重建LLMClient）
);

-- 对话历史表
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                 -- user, assistant, system
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata TEXT,                      -- JSON序列化的metadata
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
```

---

#### 2. [serializers.py](file:///d:/study/aicode/netOpsAgent/src/db/serializers.py)

**功能**：对象序列化/反序列化工具

**核心函数**：
- `serialize_task()` / `deserialize_task()` - DiagnosticTask 序列化
- `serialize_context()` / `deserialize_context()` - 上下文序列化
- `extract_llm_config()` / `rebuild_llm_client()` - LLMClient 配置提取和重建

**关键设计**：
- 使用 JSON 格式存储，便于调试和迁移
- 处理特殊对象（如 datetime）的序列化
- 支持枚举类型的正确转换

---

#### 3. [__init__.py](file:///d:/study/aicode/netOpsAgent/src/db/__init__.py)

**功能**：数据库模块导出

导出所有核心类和函数，简化导入路径。

---

### 修改的文件

#### 1. [session_manager.py](file:///d:/study/aicode/netOpsAgent/src/session_manager.py)

**新增 `SQLiteSessionManager` 类**

继承自 `SessionManager`，添加持久化功能：

```python
class SQLiteSessionManager(SessionManager):
    """SQLite持久化会话管理器"""
    
    async def initialize(self):
        """初始化数据库"""
        # 创建数据库连接和表结构
    
    def create_session(self, ...):
        """创建新会话并持久化"""
        # 序列化数据并保存到数据库
    
    async def get_session(self, session_id):
        """从数据库恢复会话"""
        # 反序列化数据，重建 Agent 和 LLMClient
    
    def update_session(self, ...):
        """更新会话状态并持久化"""
        # 更新内存和数据库
    
    # ... 其他方法
```

**关键实现细节**：

1. **会话恢复逻辑**：
   ```python
   async def get_session(self, session_id: str):
       # 1. 先从内存缓存获取
       if session_id in self.sessions:
           return self.sessions[session_id]
       
       # 2. 从数据库读取
       session_data = await self.db.get_session(session_id)
       
       # 3. 反序列化 task 和 context
       task = deserialize_task(session_data['task_data'])
       context = deserialize_context(session_data['context'])
       
       # 4. 重建 LLMClient
       llm_client = rebuild_llm_client(session_data['llm_config'])
       
       # 5. 重建 Agent 并恢复上下文
       agent = LLMAgent(llm_client=llm_client)
       agent.current_context = context  # 关键：恢复上下文
       
       # 6. 加载消息历史
       messages = await self.db.get_messages(session_id)
       
       # 7. 构造完整的 DiagnosisSession 对象
       return DiagnosisSession(...)
   ```

2. **双层存储策略**：
   - 内存：快速访问，减少数据库查询
   - 数据库：持久化存储，服务重启后可恢复

---

#### 2. [api.py](file:///d:/study/aicode/netOpsAgent/src/api.py)

**变更内容**：

1. **启动时初始化数据库**（第46-53行）：
   ```python
   @app.on_event("startup")
   async def startup_event():
       # 初始化数据库
       await session_manager.initialize()
       # 启动会话清理任务
       await session_manager.start_cleanup()
   ```

2. **异步获取会话**（第427行）：
   ```python
   # 使用 await 因为 get_session 现在是异步的
   session = await session_manager.get_session(request.session_id)
   ```

---

#### 3. [requirements.txt](file:///d:/study/aicode/netOpsAgent/requirements.txt)

**新增依赖**：
```
aiosqlite>=0.19.0
```

---

## 测试验证

### 自动化测试

创建了测试脚本 [test_session_persistence.py](file:///d:/study/aicode/netOpsAgent/tests/test_session_persistence.py)

**测试场景**：
1. ✅ 会话创建和持久化
2. ✅ 添加消息到会话
3. ✅ 更新会话状态
4. ✅ 模拟服务重启（清空内存）
5. ✅ 从数据库恢复会话
6. ✅ 验证所有数据完整性
7. ✅ 清理测试数据

**测试结果**：

```
============================================================
测试 SQLite 会话持久化功能
============================================================
[SessionDatabase] 数据库初始化完成: runtime/sessions.db
[SQLiteSessionManager] 数据库初始化完成

✓ 会话管理器初始化成功
✓ 创建测试任务: test_session_001
✓ 使用模拟 LLM 客户端
✓ 创建会话: test_session_001
✓ 添加测试消息
✓ 更新会话状态

--- 模拟服务重启 ---
✓ 清除内存中的会话

--- 从数据库恢复会话 ---
✓ 成功恢复会话: test_session_001
  - 状态: waiting_user
  - 待回答问题: 请问目标服务器上是否有防火墙？
  - 消息数量: 2
  - 任务信息: [test_session_001] 10.0.1.10 → 10.0.2.20:80 (tcp) - port_unreachable
  - Agent 已重建: True
  - LLMClient 已重建: True

  消息历史:
    [user] 请帮我诊断网络问题
    [assistant] 好的，我将开始诊断

✅ 会话持久化测试通过！

--- 清理测试数据 ---
✓ 删除测试会话

============================================================
所有测试完成！
============================================================
```

---

## 使用方法

### 1. 安装依赖

```bash
pip install aiosqlite>=0.19.0
```

### 2. 启动服务

```bash
uvicorn src.api:app --reload
```

服务启动时会自动：
- 创建 `runtime/sessions.db` 数据库文件
- 初始化表结构
- 启动会话清理任务

### 3. 多轮对话示例

**第一步：发起诊断请求**

```bash
curl -X POST http://localhost:8000/api/v1/diagnose/stream \
  -H "Content-Type: application/json" \
  -d '{"description": "10.0.1.10到10.0.2.20端口80不通"}'
```

如果 LLM 需要询问用户，会返回 `need_user_input` 事件，记录 `session_id`。

**第二步：重启服务（可选）**

```bash
# Ctrl+C 停止服务
# 重新启动
uvicorn src.api:app --reload
```

**第三步：继续对话**

```bash
curl -X POST http://localhost:8000/api/v1/chat/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "task_20260125220400_a1b2c3d4",
    "answer": "目标服务器上有防火墙"
  }'
```

系统会：
1. 从数据库恢复会话
2. 重建 Agent 和 LLMClient
3. 恢复对话上下文
4. 继续诊断流程

---

## 数据库管理

### 查看数据库

```bash
# 使用 SQLite 命令行工具
sqlite3 runtime/sessions.db

# 查看所有会话
SELECT session_id, status, created_at, updated_at FROM sessions;

# 查看消息
SELECT * FROM messages WHERE session_id = 'task_xxx';
```

### 清理过期会话

系统会自动每 5 分钟清理超过 1 小时未更新的会话。

手动清理：
```sql
DELETE FROM sessions WHERE updated_at < datetime('now', '-1 hour');
```

---

## 技术亮点

### 1. 序列化策略

**问题**：Agent 和 LLMClient 对象包含方法和运行时状态，无法直接序列化。

**解决方案**：
- 只存储必要的状态数据（task、context、配置）
- 恢复时重新创建对象
- 将保存的 context 恢复到新创建的 Agent 中

### 2. 双层存储

**内存缓存**：
- 快速访问活跃会话
- 减少数据库查询

**数据库持久化**：
- 服务重启后可恢复
- 支持历史会话查询

### 3. 异步操作

使用 `aiosqlite` 实现异步数据库操作，避免阻塞事件循环。

### 4. WAL 模式

启用 Write-Ahead Logging 模式，提高并发读写性能。

---

## 后续优化建议

### 1. 性能优化
- [ ] 添加连接池
- [ ] 批量操作优化
- [ ] 更多索引优化

### 2. 功能扩展
- [ ] 会话导出/导入功能
- [ ] 历史会话查询 API
- [ ] 会话统计分析

### 3. 可观测性
- [ ] 添加数据库操作日志
- [ ] 监控会话数量和存储大小
- [ ] 告警机制（如数据库文件过大）

### 4. 高可用
- [ ] 数据库备份机制
- [ ] 迁移到 PostgreSQL（如需高并发）
- [ ] 分布式会话存储

---

## 总结

✅ **已完成**：
- SQLite 数据库基础设施
- SQLiteSessionManager 实现
- API 接口适配
- 自动化测试验证

✅ **核心功能**：
- 会话持久化存储
- 服务重启后会话恢复
- Agent 和 LLMClient 自动重建
- 完整的对话历史保存

✅ **测试结果**：
- 所有测试通过
- 数据库文件正常创建
- 会话恢复功能正常

现在系统已经支持真正的多轮对话持久化，用户可以在服务重启后继续之前的诊断会话！
