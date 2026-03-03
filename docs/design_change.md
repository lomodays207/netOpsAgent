# 设计变更记录 (Design Change Log)

本文件用于记录项目中的重大功能变更、架构调整及设计决策。

---

## [2026-01-29] 优化中断响应速度及流式输出逻辑

### 变更背景
用户反馈在 LLM 流式输出过程中，点击“停止”按钮后响应延迟，页面往往会继续输出一段内容才真正停止。

### 变更内容

#### 1. 后端 (Python/FastAPI)
- **SSE 循环优化 (`src/api.py`)**: 
  - 减小了 `asyncio.wait_for` 的超时时间（从 0.05s 调整为 0.1s，并移除了心跳过于频繁导致的潜在阻塞风险）。
  - 移除了冗余的 `: event sent` 注释，减少数据包大小。
  - 增加了对后台任务 `done()` 状态的显式检查，确保在任务异常退出时能立即关闭连接。
- **Agent 执行检查点 (`src/agent/llm_agent.py`)**:
  - 在 `diagnose` 和 `continue_diagnose` 的工具执行前后增加了 `stop_event.is_set()` 检查。
  - 确保即使在执行长耗时工具（如网络扫描）时，也能在子步骤间迅速响应中断信号。
- **Agent 初始化重构**:
  - 移除了硬编码的 `max_steps`，支持从环境变量 `LLM_AGENT_MAX_STEPS` 读取。

#### 2. 前端 (Javascript)
- **UI 零延迟响应**: 
  - 点击“停止”按钮后立即将 `isWaitingForResponse` 设为 `false`。
  - 立即调用 `hideTypingIndicator()` 和 `setInputEnabled(true)`，无需等待服务器端确认。
- **打字机效果感知中断**: 
  - 修改了 `addAssistantMessageWithTyping` 函数，使其在每一字符渲染前检查 `isWaitingForResponse` 状态，实现“点击即停”。
- **流生命周期管理**: 
  - `processStream` 现在能感知外部中断信号并主动调用 `reader.cancel()` 释放流资源。

### 修复内容 (Hotfix)
- 修复了因为 `generalChat` 未正确维护 `isWaitingForResponse` 状态导致中断按钮在通用聊天模式下“点击不动”的问题。
- 修复了打字机逻辑在正常结束时可能出现的闪退问题。

## [2026-01-30] 新增自动提交代码脚本

### 变更背景
为了简化开发流程，通过脚本实现一键提交代码到 GitHub。

### 变更内容
#### 1. 脚本工具 (`scripts/auto_push.bat`)
- 创建了批处理脚本，支持自动执行 `git add .` -> `git commit` -> `git push` 流程。
- 支持自定义提交信息，若为空则默认为 "Auto update"。
- 增加了 `chcp 65001` 以支持 UTF-8 字符显示。

---

## [2026-02-04] 新增RAG知识库检索增强功能

### 变更背景
为了让AI助手能够基于用户上传的私有知识文档进行回答，增强通用问答的准确性和针对性，实现了RAG（检索增强生成）功能。

### 技术选型
- **向量数据库**: ChromaDB (轻量级，无需额外服务)
- **Embedding模型**: bge-small-zh-v1.5 (本地运行，中文优化)
- **文档格式**: TXT文本文件
- **文本分割**: 500字符/块，100字符重叠

### 变更内容

#### 1. 后端核心模块 (`src/rag/`)
新增4个核心模块：
- **embeddings.py**: Embedding模型封装，单例模式，延迟加载
- **vector_store.py**: ChromaDB向量存储管理，持久化到 `runtime/knowledge_base/vectordb/`
- **document_processor.py**: 文档处理器，支持TXT上传、智能分割、元数据生成
- **rag_chain.py**: RAG检索链，语义检索、相关性过滤、Prompt增强

#### 2. API接口扩展 (`src/api.py`)
新增5个知识库管理接口：
- `POST /api/v1/knowledge/upload`: 上传TXT文档
- `GET /api/v1/knowledge/list`: 获取文档列表
- `DELETE /api/v1/knowledge/{doc_id}`: 删除文档
- `GET /api/v1/knowledge/stats`: 获取统计信息
- `POST /api/v1/chat/general/stream`: RAG增强的流式聊天

#### 3. 前端界面 (`static/`)
- **knowledge.html/js**: 知识库管理页面，支持拖拽上传、列表展示、删除操作
- **index.html**: 添加"启用知识库检索"复选框和知识库管理入口
- **app.js**: 支持RAG流式聊天，显示检索状态和来源信息

#### 4. 依赖更新
新增依赖: chromadb, sentence-transformers, python-multipart

### 实现特性
1. **延迟初始化**: RAG服务仅在首次使用时加载，避免启动延迟
2. **流式体验**: 检索和生成过程实时反馈给用户
3. **来源追溯**: 显示知识来源文件和相关性分数
4. **智能分割**: 根据中文标点和语义边界分割文本
5. **持久化存储**: 向量数据库和原始文件分别持久化

### 使用流程
1. 访问知识库管理页面上传TXT文档
2. 在主界面勾选"启用知识库检索"
3. 提问时系统自动检索相关知识并增强回答

---

## [2026-02-04] 修复知识库列表API错误

### 变更背景
用户访问知识库管理页面时遇到 `'str' object is not callable` 错误,导致无法获取文档列表和统计信息。

### 问题根源
`ChromaEmbeddingFunction` 类中的 `name` 属性被实现为字符串,但 ChromaDB 内部期望 `name` 是一个可调用的方法。当 ChromaDB 尝试调用 `embedding_function.name()` 时,触发了 `'str' object is not callable` 错误。

### 修复内容

#### 修改文件: `src/rag/embeddings.py`
将 `ChromaEmbeddingFunction.name` 从字符串属性改为方法:

**修改前**:
```python
class ChromaEmbeddingFunction:
    def __init__(self, embedding_model: EmbeddingModel = None):
        self.embedding_model = embedding_model or get_embedding_model()
        self.name = "bge-small-zh-v1.5"  # 字符串属性
```

**修改后**:
```python
class ChromaEmbeddingFunction:
    def __init__(self, embedding_model: EmbeddingModel = None):
        self.embedding_model = embedding_model or get_embedding_model()
        self._name = "bge-small-zh-v1.5"  # 私有属性存储名称
    
    def name(self) -> str:
        """返回embedding函数名称"""
        return self._name
```

### 验证结果
- ✅ `GET /api/v1/knowledge/list` 正常返回文档列表
- ✅ `GET /api/v1/knowledge/stats` 正常返回统计信息
- ✅ 知识库管理页面正常加载,无控制台错误
- ✅ 文档列表和统计信息正确显示

### 影响范围
仅影响 RAG 知识库功能,不影响其他功能。

---

## [2026-02-04] RAG检索与知识库增强

### 变更背景
用户反馈在询问"检查服务监听状态"时无法匹配到知识库。经排查，原因为知识库缺失相关内容，且默认的相关性阈值（0.5）对于某些语义匹配较为严格。

### 变更内容

#### 1. 知识库扩充
- **新增知识文件**: `docs/knowledge/service_listening.txt`
  - 包含 netstat, ss, lsof 等命令的详细使用说明。
- **新增导入脚本**: `scripts/ingest_knowledge.py`
  - 自动扫描 `docs/knowledge` 目录下的 TXT 文件并导入向量数据库。

#### 2. RAG 参数调整 (`src/rag/rag_chain.py`)
- **调整相关性阈值**:
  - 将 `min_relevance_score` 默认值从 `0.5` 调整为 `0.35`。
  - 原因：测试发现"检查服务监听状态具体怎么做？"与文档标题"如何检查服务监听状态"的匹配度约为 0.375，低于原阈值。调整后可正常召回。

### 验证结果
- 运行 `scripts/ingest_knowledge.py` 成功导入新知识。
- 运行验证脚本确认查询能够正确召回相关文档。

#### 3. 文档分割策略优化 (`src/rag/document_processor.py`)
- **新增 Markdown 标题感知分割**:
  - 修改 `split_text` 方法，优先根据 Markdown 标题 (`#`, `##`, `###`) 进行分割。
  - 解决长文档或多步骤文档被合并到一个大块中，导致具体步骤（如 "ping命令"）相关性被稀释的问题。
  - 验证：对于 `test_knowledge.txt`，"telnet不通" 的相关性从 0.06 提升至 0.40+。

---

## [2026-02-06] 工具调用可折叠展示功能

### 变更背景
为了提升诊断任务执行时的用户体验，需要优化工具调用的展示方式，使其更加清晰、简洁，并支持折叠/展开交互，方便用户查看详细信息。

### 变更内容

#### 1. UI设计改进 (`static/style.css`)
- **左侧状态条**: 
  - 使用 CSS `::before` 伪元素在卡片左侧添加4px宽的彩色状态条
  - 状态映射：执行中（蓝色）、成功（绿色 #10b981）、失败（红色 #ef4444）
- **折叠/展开动画**:
  - 添加折叠箭头图标，展开时显示▼，折叠时显示▶（通过CSS transform实现旋转）
  - 详情区域使用 `max-height` + `opacity` 实现平滑过渡动画
- **视觉优化**:
  - 移除原有的状态标签（running/success/error），改用状态图标（⏳/✓/✗）
  - 添加执行时间显示区域，右对齐显示在卡片顶部
  - 优化参数和结果区域的标签样式（小写字母、灰色）

#### 2. HTML模板更新 (`static/index.html`)
更新工具调用卡片模板结构：
- 添加折叠箭头元素 `<span class="tool-collapse-icon">`
- 添加执行时间元素 `<span class="tool-time">`
- 将状态标签改为状态图标 `<span class="tool-status-icon">`
- 添加详情区域的标签 "参数 [ARGUMENTS]" 和 "结果 [RESULT]"
- 默认状态设置为折叠 `class="tool-call-card collapsed"`

#### 3. JavaScript功能实现 (`static/app.js`)

**createToolCallCard 函数**:
- 初始状态设置为折叠，状态条显示蓝色（运行中）
- 状态图标设置为 "⏳"
- 添加点击头部事件监听器，实现折叠/展开切换

**updateToolCallResult 函数**:
- 根据执行结果更新卡片状态类：`status-success` 或 `status-error`
- 成功状态：状态图标改为 "✓"，状态条变绿色
- 失败状态：状态图标改为 "✗"，状态条变红色
- 更新执行时间显示（单位：毫秒）

**createToolCallCardFromHistory 函数**:
- 历史记录加载时默认展开状态（移除 `collapsed` 类）
- 为历史卡片生成唯一ID（使用时间戳+随机数）
- 添加折叠/展开交互事件

### 实现特性
1. **一键折叠/展开**: 点击工具卡片头部即可切换详情显示状态
2. **视觉状态反馈**: 
   - 左侧彩色状态条直观显示执行状态
   - 状态图标（⏳/✓/✗）提供快速识别
3. **执行时间显示**: 卡片右上角显示工具执行耗时（毫秒级精度）
4. **默认折叠**: 新执行的工具默认折叠，保持界面简洁
5. **平滑动画**: 折叠/展开过程使用CSS过渡动画，提升交互体验

### 验证结果
- ✅ 工具卡片左侧状态条颜色正确（绿色/红色）
- ✅ 折叠/展开交互流畅，动画效果自然
- ✅ 执行时间准确显示（如 5.012ms, 3.125ms）
- ✅ 历史会话加载时工具卡片正常展示
- ✅ 状态图标清晰可辨（✓ 成功, ✗ 失败）

### 影响范围
仅影响前端工具调用卡片的展示效果,不影响后端逻辑和数据结构。

---

## [2026-02-06] 用户输入IP地址格式验证

### 变更背景
用户输入无效的IP地址(如 "10.1.10到10.0.2.20端口80不通",其中10.1.10缺少最后一个字段)时,系统没有进行验证就直接开始诊断流程,导致后续处理出现异常。为了提升用户体验,需要在接收用户输入后立即验证IP地址格式的合法性。

### 技术方案
- **验证时机**: 在解析用户输入时（NLU、CLI、API三个入口处）
- **验证内容**: IP地址格式(x.x.x.x,每个字段0-255)、端口号范围(1-65535)
- **错误处理**: 抛出ValueError异常,返回友好的错误提示

### 变更内容

#### 1. 新增输入验证工具 (`src/utils/input_validator.py`)
新增3个核心函数:
- **is_valid_ip()**: 验证IP地址格式是否正确
  - 检查格式为 x.x.x.x
  - 验证每个字段在0-255范围内
- **is_valid_port()**: 验证端口号范围(1-65535)
- **extract_network_info()**: 从用户输入中提取并验证网络信息
  - 返回: (源IP, 目标IP, 端口, 错误消息)
  - 如验证失败,返回详细的错误提示信息

#### 2. NLU模块集成验证 (`src/agent/nlu.py`)
- **parse_user_input()**: 在LLM解析主流程中添加IP验证
  - 在 `_validate_extracted_info()` 之后添加IP格式验证
  - 验证LLM解析出的源IP和目标IP格式
  - 若验证失败,抛出 ValueError 异常,触发回退到规则解析
- **_fallback_rule_based_parse()**: 在规则解析回退函数中集成IP验证
  - 调用 `extract_network_info()` 提取并验证信息
  - 若验证失败,抛出 ValueError 异常

#### 3. CLI模块集成验证 (`src/cli.py`)
- **parse_user_input()**: 在CLI规则解析函数中集成IP验证
  - 在解析故障类型前先验证IP格式
  - 移除原有的简单字符串分割逻辑

#### 4. API接口错误处理 (`src/api.py`)
**诊断接口** (`POST /api/v1/diagnose`):
- 在规则解析部分添加输入验证
- 新增 `ValueError` 异常捕获,返回友好提示

**流式诊断接口** (`POST /api/v1/diagnose/stream`):
- 同样在规则解析部分添加验证
- 在事件生成器的异常处理中添加 `ValueError` 专门处理
- 通过SSE返回验证错误信息

#### 5. 单元测试 (`tests/unit/test_input_validation.py`)
新增完整测试用例:
- `TestIPValidation`: IP地址和端口验证函数测试(10个测试)
- `TestNLUWithValidation`: NLU模块集成测试
- `TestCLIWithValidation`: CLI模块集成测试

### 错误提示示例
- 源IP格式错误: "源IP地址格式不正确: 10.1.10。正确格式应为: x.x.x.x (如: 192.168.1.1)"
- 目标IP格式错误: "目标IP地址格式不正确: 10.0.2。正确格式应为: x.x.x.x (如: 192.168.1.1)"
- 端口超范围: "端口号超出有效范围: 99999。端口号应在 1-65535 之间"
- 信息不完整: "无法识别源IP和目标IP。请使用格式: '源IP到目标IP端口XX不通' (例如: 10.0.1.10到10.0.2.20端口80不通)"

### 验证结果
- ✅ 工具函数独立测试通过(验证了有效和无效IP的各种情况)
- ✅ 10个单元测试通过(1个失败仅因API密钥未设置,与功能无关)
- ✅ IP验证工具正确识别无效IP(10.1.10, 10.0.2等)
- ✅ 端口验证正确拦截超范围端口(99999等)
- ✅ 错误提示信息友好清晰,指导用户正确输入

### 影响范围
- 所有用户输入解析路径(NLU、CLI、API)均已集成验证
- 提升了系统的健壮性,避免无效输入导致后续异常
- 不影响现有功能,仅增强输入验证逻辑

---

## [2026-02-10] 知识库文档在线预览功能

### 变更背景
知识库管理页面中，已上传的文档只能看到文件名和知识块数量，无法直接查看文档内容。用户需要能够在线预览文档，以便确认上传内容是否正确。

### 变更内容

#### 1. 后端 - 文档处理器 (`src/rag/document_processor.py`)
- **新增 `get_file_content()` 方法**: 根据 `doc_id` 在文档存储目录查找并读取文件内容
  - 支持 UTF-8、GBK、GB2312、Latin-1 多种编码自动检测
  - 返回原始文件名、文本内容和文件大小
  - 文件不存在时返回 None

#### 2. 后端 - API接口 (`src/api.py`)
- **新增 `GET /api/v1/knowledge/{doc_id}/content`**: 获取文档内容用于在线预览
  - 响应：`{ status, doc_id, filename, content, size }`
  - 文档不存在时返回 404

#### 3. 前端 - 知识库页面 (`static/knowledge.html`, `static/knowledge.js`)
- **预览按钮**: 文档列表每项新增"👁️ 查看"按钮
- **预览弹窗**: 全屏模态窗口展示文档文本内容
  - 毛玻璃暗色主题，等宽字体显示
  - 自定义滚动条样式
  - 显示文件名和文件大小
  - 加载状态提示
- **交互支持**: 点击关闭按钮 / 点击遮罩层 / ESC键均可关闭弹窗

#### 4. 单元测试 (`tests/unit/test_document_preview.py`)
- 正常读取文件内容
- 文件不存在返回 None
- GBK编码文件读取
- 空文件读取
- 原始文件名正确提取

### 验证结果
- ✅ 单元测试全部通过（5个测试用例）
- ✅ 已上传文档显示"查看"按钮
- ✅ 点击查看按钮正确展示文档全文
- ✅ 弹窗关闭交互正常（关闭按钮/遮罩层/ESC键）

### 影响范围
仅影响知识库管理页面的展示功能，不影响 RAG 检索和其他功能。

---

## [2026-03-03] 修复知识库搜索结果被误过滤的问题

### 变更背景
用户上传知识库文件 `1.txt`（包含"证书更新服务的负责人"等信息），在聊天界面勾选知识库检索后提问，系统提示"知识库中未找到相关内容"。

### 问题根源
`RAGChain` 的 `min_relevance_score` 阈值（0.25）对于 `bge-small-zh-v1.5` 模型 + ChromaDB 的 distance 分布来说过高。

调试数据：
- 查询 "证书更新服务的负责人" → 最佳匹配 distance=0.8231, **relevance=0.1769**（< 0.25，被过滤）
- 查询 "域名解析服务" → 最佳匹配 distance=0.7922, **relevance=0.2078**（< 0.25，被过滤）

该模型在 ChromaDB 中的 distance 范围通常在 0.8~1.3，对应的 relevance 范围约在 -0.3~0.2，导致 0.25 阈值过滤掉了几乎所有有效结果。

### 修复内容

#### 修改文件: `src/rag/rag_chain.py`
将 `min_relevance_score` 默认值从 `0.25` 调整为 `0.05`：

```diff
- min_relevance_score: float = 0.25
+ min_relevance_score: float = 0.05
```

### 验证结果
- ✅ 查询 "证书更新服务的负责人" → 成功返回 `1.txt` 内容（relevance=0.1769）
- ✅ 查询 "域名解析服务的负责人" → 成功返回 `1.txt` 内容（relevance=0.2156）
- ✅ RAG 增强 Prompt 正确引用知识来源

### 影响范围
仅影响 RAG 检索的结果过滤阈值，使更多相关结果能被召回。不影响其他功能。

---

## [2026-03-03] 知识库管理和查询页面全面重构

### 变更背景
现有知识库页面采用深色主题单栏垂直布局，视觉风格较为简单。参考现代化知识库管理系统的原型设计，对页面进行全面重构，提升用户体验和视觉效果。

### 变更内容

#### 1. 页面布局重构 (`static/knowledge.html`)
- **整体布局**: 从单栏垂直布局改为左侧导航栏 + 右侧主内容区的两栏布局
- **配色方案**: 从深色主题（`#1a1a2e`暗色背景）改为浅色白底主题，更加清爽现代
- **左侧导航栏**:
  - KnowledgeBase Logo 品牌标识
  - "Library" 分组 → "All Knowledge" 全部文档视图
  - "Categories" 分组 → 动态分类导航（根据文件名自动推断分类）
  - 底部返回对话界面链接
- **顶部操作栏**: 全局搜索输入框 + 紫色 "Upload" 按钮
- **主内容区**: 3 列卡片网格展示文档列表
- **上传方式**: 从页面内嵌拖拽区改为模态弹窗触发

#### 2. 文档卡片设计
- 每张卡片包含：分类标签（带颜色圆点）、文档标题、摘要描述、知识块数/阅读时间/日期
- 悬停时显示预览和删除操作按钮
- 卡片悬停有阴影提升和上移微动画效果

#### 3. 分类系统
- 根据文件名关键词自动推断分类（Engineering、Product、Design、HR、Marketing、Security等）
- 每个分类配独立颜色标识
- 支持点击左侧分类进行筛选

#### 4. 交互逻辑重构 (`static/knowledge.js`)
- **分类筛选**: 点击左侧导航分类时过滤显示对应文档
- **搜索集成**: 搜索结果以卡片形式展示，显示相关度百分比和分数条
- **上传弹窗**: 点击Upload按钮弹出模态窗口，支持拖拽上传
- **保留功能**: 文档预览弹窗、删除确认、Toast提示、分页

### 验证结果
- ✅ 页面布局符合原型设计：左侧分类栏、顶部搜索/上传、3列卡片网格
- ✅ 分类自动推断正确（Engineering、其他等）
- ✅ 上传弹窗正常弹出和关闭
- ✅ 文档卡片正确显示标题、分类标签、知识块数量、日期等信息

### 影响范围
仅影响知识库管理页面前端展示（`static/knowledge.html`、`static/knowledge.js`），后端API接口无任何变更。

---

## [2026-03-03] 知识库搜索结果文件预览功能

### 变更背景
知识库搜索过滤后的结果卡片不支持点击预览文档内容，而普通文档列表模式已有完整预览功能。用户希望搜索结果也能直接预览查看文件完整内容。

### 变更内容

#### 修改文件: `static/knowledge.js`
- **搜索结果卡片添加点击预览**: 为搜索结果卡片绑定 `onclick` 事件，点击时调用已有的 `previewDocument(doc_id, filename)` 打开预览弹窗
- **搜索结果卡片添加预览按钮**: 在卡片右上角（hover时显示）添加 👁️ 预览按钮，与文档列表模式保持一致
- **兼容处理**: 当 `doc_id` 不存在时不渲染预览按钮，避免异常

### 验证结果
- ✅ 搜索结果卡片点击后成功弹出预览模态框
- ✅ 文档内容完整加载显示
- ✅ 预览弹窗关闭交互正常
- ✅ 原有文档列表模式预览功能不受影响

### 影响范围
仅影响 `static/knowledge.js` 中搜索结果的渲染逻辑，无后端改动。

---

## [2026-03-03] 知识库分类名称自定义修改功能

### 变更背景
知识库分类名称由 `inferCategory()` 自动推断（Engineering、Product、Design 等英文名），用户希望能自定义修改分类的显示名称，例如将 "Engineering" 改为 "工程技术"。

### 变更内容

#### 修改文件: `static/knowledge.js`
- **分类名称映射系统**: 新增 `categoryNameMap` 对象和 `localStorage` 持久化（key: `kb_category_names`），页面加载时自动恢复自定义名称
- **`getCategoryDisplayName(cat)` 函数**: 统一获取分类显示名，替代各处散落的 `cat === 'Default' ? '其他' : cat` 硬编码
- **侧边栏 inline 编辑**: 分类名旁添加 ✏️ 编辑按钮（hover 显示），点击后分类名变为输入框，支持回车确认/ESC取消/失焦确认
- **`startEditCategory()` 函数**: 实现 inline 编辑交互逻辑，确认后更新映射并保存到 `localStorage`
- **4处显示点统一**: 侧边栏、文档卡片标签、搜索结果卡片标签、内容区标题均使用 `getCategoryDisplayName()`

#### 修改文件: `static/knowledge.html`
- **CSS 样式**: 添加 `.cat-edit-btn`（编辑按钮，hover 时显示）和 `.cat-edit-input`（inline 输入框，紫色聚焦边框）样式

### 验证结果
- ✅ 侧边栏分类 hover 时显示编辑图标
- ✅ 点击编辑图标，分类名变为可编辑输入框
- ✅ 确认后侧边栏、卡片标签、内容标题三处同步更新
- ✅ 刷新页面后自定义名称保留（localStorage 持久化）

### 影响范围
仅影响前端展示（`static/knowledge.html`、`static/knowledge.js`），无后端改动。

---

## [2026-03-04] 新增项目技术架构图

### 变更背景
项目缺少一份直观的技术架构图来展示整体技术栈、分层结构和依赖关系，不便于项目汇报和团队沟通。

### 变更内容

#### 新增文件: `docs/architecture_diagram.html`
创建了一份分层式技术架构图页面，参考标准技术架构图风格，从上到下展示8个层次：

1. **客户端层**: Web管理界面、AI对话界面、知识库管理、历史记录、CLI命令行
2. **API服务层**: FastAPI、Uvicorn、RESTful API、Pydantic
3. **应用核心层**: Agent引擎（NLU、Planner、Executor、Analyzer、Reporter、LLM Agent）+ 功能模块（故障诊断、会话管理、YAML工作流、命令白名单、MCP协议）
4. **AI引擎层**: LangChain框架 + 大模型底座（通义千问Qwen、DeepSeek V3.2，通过ModelScope API调用）
5. **RAG检索层**: ChromaDB向量数据库、Sentence-Transformers嵌入、文档处理器、RAG Chain
6. **外部集成层**: CMDB、自动化平台、Network Tools、FastMCP
7. **数据存储层**: SQLite/aiosqlite、ChromaDB持久化、文件系统、YAML配置
8. **运行环境层**: Python 3.10+、asyncio、aiohttp、structlog、pytest

### 设计特性
- 每层使用不同渐变色主题区分（蓝、青、绿、紫、橙、灰、黄、浅灰）
- 卡片悬停时有上移阴影微动画
- 大模型底座使用高亮渐变卡片突出展示
- 层间使用向下箭头连接，直观表达调用关系

### 影响范围
新增独立HTML页面，不影响现有功能。可通过 `http://localhost:8888/architecture_diagram.html` 访问。
