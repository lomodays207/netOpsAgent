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
