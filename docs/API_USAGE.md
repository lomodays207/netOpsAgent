# netOpsAgent HTTP API 使用说明

## 启动 API 服务

### Windows 启动

```bash
# 使用启动脚本（推荐）
start_api.bat

# 或手动启动
.venv\Scripts\uvicorn.exe src.api:app --host 0.0.0.0 --port 8000 --reload
```

### Linux/Mac 启动

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动服务
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：
- **API 文档**：http://localhost:8000/docs （交互式 Swagger UI）
- **健康检查**：http://localhost:8000/health

---

## API 接口说明

### 1. 健康检查

**接口**：`GET /health`

**响应示例**：
```json
{
  "status": "healthy",
  "llm_available": true,
  "timestamp": "2026-01-23T10:50:30.123456"
}
```

---

### 2. 执行网络故障诊断（主接口）

**接口**：`POST /api/v1/diagnose`

**请求参数**：
```json
{
  "description": "10.0.1.10到10.0.2.20端口80不通",
  "use_llm": true,
  "verbose": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| description | string | 是 | 故障描述，至少5个字符 |
| use_llm | boolean | 否 | 是否使用 LLM 解析（默认：true） |
| verbose | boolean | 否 | 是否返回详细输出（默认：false） |

**响应示例**：
```json
{
  "task_id": "task_20260123105030_a1b2c3d4",
  "status": "success",
  "root_cause": "目标服务器防火墙策略阻止了80端口访问",
  "confidence": 85.0,
  "execution_time": 8.5,
  "steps": [
    {
      "step": 1,
      "name": "ping测试",
      "command": "ping -c 4 10.0.2.20",
      "success": true,
      "output": null
    },
    {
      "step": 2,
      "name": "端口检查",
      "command": "ss -tlnp | grep :80",
      "success": true,
      "output": null
    }
  ],
  "suggestions": [
    "在目标服务器开放80端口的防火墙规则"
  ]
}
```

**错误响应**：
```json
{
  "task_id": "task_20260123105030_a1b2c3d4",
  "status": "failed",
  "root_cause": null,
  "confidence": null,
  "execution_time": null,
  "steps": [],
  "suggestions": [],
  "error": "错误信息详情"
}
```

---

## 使用示例

### 1. curl 命令

```bash
# 基本诊断
curl -X POST "http://localhost:8000/api/v1/diagnose" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "10.0.1.10到10.0.2.20端口80不通",
    "use_llm": true,
    "verbose": false
  }'

# 详细输出模式
curl -X POST "http://localhost:8000/api/v1/diagnose" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "服务器A访问服务器B的HTTP服务失败",
    "use_llm": true,
    "verbose": true
  }'
```

### 2. Python 示例

```python
import requests

# 发送诊断请求
response = requests.post(
    "http://localhost:8000/api/v1/diagnose",
    json={
        "description": "10.0.1.10到10.0.2.20端口80不通",
        "use_llm": True,
        "verbose": False
    }
)

result = response.json()
print(f"任务ID: {result['task_id']}")
print(f"根因: {result['root_cause']}")
print(f"置信度: {result['confidence']}%")
print(f"执行时间: {result['execution_time']}秒")
print(f"建议: {result['suggestions']}")
```

### 3. JavaScript/Node.js 示例

```javascript
fetch('http://localhost:8000/api/v1/diagnose', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    description: '10.0.1.10到10.0.2.20端口80不通',
    use_llm: true,
    verbose: false
  })
})
.then(response => response.json())
.then(data => {
  console.log('任务ID:', data.task_id);
  console.log('根因:', data.root_cause);
  console.log('置信度:', data.confidence);
  console.log('建议:', data.suggestions);
})
.catch(error => console.error('错误:', error));
```

### 4. PowerShell 示例

```powershell
$body = @{
    description = "10.0.1.10到10.0.2.20端口80不通"
    use_llm = $true
    verbose = $false
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/diagnose" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"

Write-Host "任务ID: $($response.task_id)"
Write-Host "根因: $($response.root_cause)"
Write-Host "置信度: $($response.confidence)%"
Write-Host "建议: $($response.suggestions)"
```

---

## 支持的故障描述格式

API 支持自然语言描述，例如：

1. **端口不可达**
   - "10.0.1.10到10.0.2.20端口80不通"
   - "服务器A访问服务器B的HTTP服务失败"
   - "无法telnet到192.168.1.100的8080端口"

2. **连通性问题**
   - "10.0.1.10到10.0.2.20 ping不通"
   - "服务器A和服务器B之间网络不通"
   - "192.168.1.100无法ping通192.168.1.200"

---

## 常见问题

### Q: API 返回 503 错误？
A: 检查 LLM 配置，确保 `.env` 文件中的 `API_KEY` 和 `API_BASE_URL` 正确配置。

### Q: 诊断时间过长？
A: 正常诊断需要 5-15 秒，涉及多个网络测试步骤。可以通过 `verbose: true` 查看详细执行过程。

### Q: 如何集成到现有系统？
A: 直接调用 HTTP API 接口即可，支持任何编程语言的 HTTP 客户端。

### Q: 支持异步诊断吗？
A: 当前版本为同步诊断，后续版本会支持异步任务队列。

---

## 生产部署建议

1. **使用 Gunicorn + Uvicorn 部署**

```bash
gunicorn src.api:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

2. **使用 Docker 容器化**

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. **添加 Nginx 反向代理**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 监控和日志

- **日志级别**：在 `.env` 中配置 `LOG_LEVEL`
- **日志格式**：在 `.env` 中配置 `LOG_FORMAT`
- **健康检查**：定期访问 `/health` 端点监控服务状态

---

## 联系方式

- 项目维护者: NetOps Team
- Email: netops@example.com
- 项目主页: https://github.com/yourorg/netOpsAgent


---

## RAG证据来源功能 API

### 3. 通用聊天流式接口（支持证据来源）

**接口**：`POST /api/v1/chat/stream`

**请求参数**：
```json
{
  "message": "访问关系如何进行开通提单？",
  "session_id": null,
  "use_llm": true,
  "use_rag": true,
  "verbose": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户消息内容 |
| session_id | string | 否 | 会话ID（用于继续对话） |
| use_llm | boolean | 否 | 是否使用LLM（默认：true） |
| use_rag | boolean | 否 | 是否使用RAG检索（默认：true） |
| verbose | boolean | 否 | 是否返回详细输出（默认：false） |

**响应格式**：Server-Sent Events (SSE) 流

#### SSE 事件类型

##### 1. start 事件
```json
{
  "type": "start",
  "session_id": "task_20260123105030_a1b2c3d4"
}
```

##### 2. rag_start 事件
```json
{
  "type": "rag_start",
  "message": "正在检索知识库..."
}
```

##### 3. rag_result 事件
```json
{
  "type": "rag_result",
  "count": 2,
  "sources": ["访问关系开通流程.txt", "网络权限申请指南.txt"]
}
```

##### 4. evidence_sources 事件（新增）
```json
{
  "type": "evidence_sources",
  "sources": [
    {
      "id": "doc_123abc",
      "filename": "访问关系开通流程.txt",
      "relevance_score": 0.85,
      "preview": "访问关系开通需要提交工单，包括源IP、目标IP、端口、协议和用途说明...",
      "metadata": {
        "source": "docs/knowledge/service_listening.txt",
        "created_at": "2026-01-15T10:30:00Z",
        "file_size": 2048,
        "doc_id": "doc_123abc"
      }
    },
    {
      "id": "doc_456def",
      "filename": "网络权限申请指南.txt",
      "relevance_score": 0.72,
      "preview": "网络权限申请流程包括填写申请表、提交审批、配置防火墙规则...",
      "metadata": {
        "source": "docs/knowledge/test_knowledge.txt",
        "created_at": "2026-01-16T14:20:00Z",
        "file_size": 1536,
        "doc_id": "doc_456def"
      }
    }
  ]
}
```

**字段说明**：
- `id`: 文档唯一标识（ChromaDB的文档ID）
- `filename`: 文件名
- `relevance_score`: 相关度评分（0-1范围，越高越相关）
- `preview`: 预览文本（前200字符）
- `metadata`: 文档元数据
  - `source`: 来源路径
  - `created_at`: 创建时间
  - `file_size`: 文件大小（字节）
  - `doc_id`: 文档ID

**特性**：
- 证据来源数量限制为最多5个
- 相关度评分低于0.05的文档会被过滤
- 事件在content事件之前发送
- 当未检索到文档时，不发送此事件

##### 5. content 事件
```json
{
  "type": "content",
  "text": "根据知识库，访问关系开通需要..."
}
```

##### 6. complete 事件
```json
{
  "type": "complete",
  "session_id": "task_20260123105030_a1b2c3d4",
  "rag_used": true
}
```

##### 7. error 事件
```json
{
  "type": "error",
  "message": "错误信息"
}
```

---

### 4. 获取文档详情（证据预览）

**接口**：`GET /api/v1/knowledge/document/{doc_id}`

**路径参数**：
- `doc_id`: 文档ID（从evidence_sources事件中获取）

**响应示例（成功）**：
```json
{
  "status": "success",
  "data": {
    "id": "doc_123abc",
    "filename": "访问关系开通流程.txt",
    "content": "# 访问关系开通流程\n\n## 1. 提交工单\n...",
    "metadata": {
      "source": "docs/knowledge/service_listening.txt",
      "created_at": "2026-01-15T10:30:00Z",
      "file_size": 2048,
      "doc_id": "doc_123abc"
    }
  }
}
```

**响应示例（文档不存在）**：
```json
{
  "status": "error",
  "message": "文档不存在"
}
```

**响应示例（文档过大）**：
```json
{
  "status": "error",
  "message": "文档过大，无法加载（超过10MB限制）"
}
```

**速率限制**：
- 每分钟最多10次请求
- 超过限制返回429错误

**安全特性**：
- 文档ID验证（防止路径遍历攻击）
- 文档大小限制（最大10MB）
- LRU缓存（最多缓存100个文档）
- 速率限制（每分钟10次）

---

## 证据来源功能配置

### 环境变量

在 `.env` 文件中配置：

```bash
# RAG Evidence Sources Feature Flag
ENABLE_EVIDENCE_SOURCES=true  # Enable/disable evidence sources display feature
```

- `ENABLE_EVIDENCE_SOURCES`: 启用/禁用证据来源功能（默认：true）
  - `true`: 启用证据来源功能，发送evidence_sources事件
  - `false`: 禁用证据来源功能，不发送evidence_sources事件

### 向后兼容性

- 旧版前端会忽略evidence_sources事件，不影响现有功能
- 新增API端点不影响现有接口
- 可通过feature flag控制功能启用/禁用

---

## 使用示例 - 证据来源功能

### JavaScript 示例（SSE客户端）

```javascript
// 发送聊天请求
const response = await fetch('/api/v1/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: '访问关系如何进行开通提单？',
    session_id: null,
    use_llm: true,
    use_rag: true,
    verbose: false
  })
});

// 处理SSE流
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n\n');
  buffer = lines.pop();

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.substring(6));
      
      // 处理证据来源事件
      if (event.type === 'evidence_sources') {
        console.log('收到证据来源:', event.sources);
        // 渲染证据来源面板
        renderEvidencePanel(event.sources);
      }
      
      // 处理内容事件
      if (event.type === 'content') {
        console.log('收到内容:', event.text);
        // 渲染LLM回答
        renderContent(event.text);
      }
    }
  }
}
```

### 获取文档详情示例

```javascript
// 点击证据卡片时获取完整文档
async function showDocumentPreview(docId) {
  try {
    const response = await fetch(`/api/v1/knowledge/document/${docId}`);
    
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('文档不存在');
      } else if (response.status === 429) {
        throw new Error('请求过于频繁，请稍后重试');
      } else {
        throw new Error('无法加载文档内容');
      }
    }

    const data = await response.json();
    
    if (data.status === 'success' && data.data) {
      const doc = data.data;
      console.log('文档标题:', doc.filename);
      console.log('文档内容:', doc.content);
      // 在模态框中显示文档内容
      showModal(doc.filename, doc.content);
    }
  } catch (error) {
    console.error('加载文档失败:', error);
    alert(error.message);
  }
}
```

---

## 监控和日志 - 证据来源功能

### 后端监控日志

系统会自动记录以下监控信息：

```
[MONITORING] RAG检索耗时: 125.50ms, 返回文档数: 3
[MONITORING] 发送证据来源数量: 3
[MONITORING] 文档查询耗时: 15.20ms, 文档ID: doc_123abc
```

### 前端监控日志

前端会记录以下监控信息：

```
[MONITORING] 证据卡片点击, 文档ID: doc_123abc
[MONITORING] 文档预览加载时间: 150.25ms, 文档ID: doc_123abc
```

### 性能指标

- **RAG检索耗时**: 通常在100-300ms之间
- **文档查询耗时**: 通常在10-50ms之间（缓存命中时更快）
- **文档预览加载时间**: 通常在100-500ms之间（包含网络传输）

---

