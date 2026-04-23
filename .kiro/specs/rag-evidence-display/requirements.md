# 需求文档 - RAG证据来源展示功能

## 引言

本文档定义了RAG证据来源展示功能的用户需求和验收标准。该功能旨在提高系统透明度，让用户了解AI回答的知识来源，并支持用户查看完整的源文档内容。

## 术语表

- **System**: RAG证据来源展示系统
- **RAG_Engine**: RAG检索引擎，负责从知识库检索相关文档
- **Evidence_Source**: 证据来源，包含文档ID、文件名、相关度评分和预览文本
- **Document_Service**: 文档服务，负责提供完整文档内容
- **Frontend**: 前端界面，负责展示证据来源和文档预览
- **SSE_Stream**: Server-Sent Events流，用于实时推送数据到前端
- **User**: 系统用户，提出知识性问题并查看证据来源

## 需求

### 需求 1: 证据来源检索与返回

**用户故事**: 作为用户，我希望在提问后能看到AI回答所依据的知识来源，以便我了解信息的可靠性和出处。

#### 验收标准

1. WHEN User提交知识性问题 THEN THE RAG_Engine SHALL检索相关文档并返回证据来源列表
2. WHEN RAG_Engine检索到文档 THEN THE System SHALL为每个文档生成唯一的文档ID
3. WHEN RAG_Engine返回检索结果 THEN THE System SHALL计算每个文档的相关度评分（0-1范围）
4. WHEN 文档相关度评分低于0.05 THEN THE System SHALL过滤掉该文档
5. WHEN 检索到多个文档 THEN THE System SHALL限制返回的证据来源数量不超过5个

### 需求 2: 证据来源信息结构

**用户故事**: 作为用户，我希望证据来源包含足够的信息（文件名、相关度、预览），以便我快速判断文档是否相关。

#### 验收标准

1. THE Evidence_Source SHALL包含文档ID字段
2. THE Evidence_Source SHALL包含文件名字段
3. THE Evidence_Source SHALL包含相关度评分字段（数值类型，范围0-1）
4. THE Evidence_Source SHALL包含预览文本字段（最多200字符）
5. WHERE 文档包含元数据 THE Evidence_Source SHALL包含元数据字段（来源路径、创建时间、文件大小）

### 需求 3: SSE事件流扩展

**用户故事**: 作为前端开发者，我希望通过SSE流接收证据来源数据，以便实时展示给用户。

#### 验收标准

1. WHEN RAG检索完成 THEN THE System SHALL通过SSE流发送evidence_sources事件
2. THE evidence_sources事件 SHALL包含type字段，值为"evidence_sources"
3. THE evidence_sources事件 SHALL包含sources数组，包含所有证据来源对象
4. WHEN 发送evidence_sources事件 THEN THE System SHALL在发送LLM回答内容之前发送该事件
5. WHEN 未检索到相关文档 THEN THE System SHALL不发送evidence_sources事件

### 需求 4: 文档内容查询API

**用户故事**: 作为用户，我希望点击证据来源后能查看完整的文档内容，以便深入了解知识细节。

#### 验收标准

1. THE System SHALL提供GET /api/v1/knowledge/document/{doc_id}端点
2. WHEN 请求有效的文档ID THEN THE Document_Service SHALL返回完整文档内容
3. WHEN 请求无效的文档ID THEN THE Document_Service SHALL返回错误响应（状态码404）
4. THE 文档查询响应 SHALL包含文档ID、文件名、完整内容和元数据
5. WHEN 文档大小超过10MB THEN THE Document_Service SHALL拒绝返回并返回错误响应

### 需求 5: 前端证据来源展示

**用户故事**: 作为用户，我希望在聊天界面中清晰地看到证据来源列表，以便我了解有哪些相关文档。

#### 验收标准

1. WHEN Frontend接收到evidence_sources事件 THEN THE Frontend SHALL渲染证据来源面板
2. THE 证据来源面板 SHALL显示证据来源数量
3. THE 证据来源面板 SHALL为每个证据来源显示卡片
4. THE 证据卡片 SHALL显示文件名、相关度评分和预览文本
5. WHEN 证据来源数量为0 THEN THE Frontend SHALL不显示证据来源面板

### 需求 6: 文档预览交互

**用户故事**: 作为用户，我希望点击证据卡片后能在弹窗中查看完整文档，以便我不离开聊天界面就能阅读详细内容。

#### 验收标准

1. WHEN User点击证据卡片 THEN THE Frontend SHALL发送GET请求到/api/v1/knowledge/document/{doc_id}
2. WHEN 文档内容加载中 THEN THE Frontend SHALL显示加载指示器
3. WHEN 文档内容加载成功 THEN THE Frontend SHALL在模态框中显示文档标题和完整内容
4. THE 文档预览模态框 SHALL支持内容滚动
5. WHEN User点击关闭按钮 THEN THE Frontend SHALL关闭文档预览模态框

### 需求 7: 文档ID生成策略

**用户故事**: 作为系统开发者，我希望文档ID生成策略稳定可靠，以便确保文档查询的准确性。

#### 验收标准

1. THE System SHALL使用向量数据库（ChromaDB）的文档ID作为文档ID
2. WHEN RAG_Engine检索文档 THEN THE System SHALL从检索结果中提取文档ID
3. THE 文档ID SHALL在向量数据库中唯一标识一个文档
4. WHEN 同一文档被多次检索 THEN THE System SHALL返回相同的文档ID

### 需求 8: 文档内容缓存

**用户故事**: 作为系统运维人员，我希望系统能缓存文档内容，以便减少重复查询和提高响应速度。

#### 验收标准

1. THE Document_Service SHALL使用LRU缓存策略缓存文档内容
2. THE 缓存 SHALL最多存储100个文档
3. WHEN 查询已缓存的文档 THEN THE Document_Service SHALL从缓存返回内容
4. WHEN 查询未缓存的文档 THEN THE Document_Service SHALL从数据源加载并缓存
5. WHEN 缓存已满 THEN THE Document_Service SHALL移除最久未使用的文档

### 需求 9: 安全防护

**用户故事**: 作为系统安全管理员，我希望系统能防止恶意访问和攻击，以便保护知识库数据安全。

#### 验收标准

1. WHEN 接收到文档ID请求 THEN THE System SHALL验证文档ID的合法性
2. WHEN 检测到路径遍历攻击模式 THEN THE System SHALL拒绝请求并返回错误
3. WHEN 文档内容包含HTML标签 THEN THE Frontend SHALL对内容进行HTML转义
4. THE System SHALL限制文档查询频率为每分钟最多10次
5. WHEN 超过查询频率限制 THEN THE System SHALL返回429错误（Too Many Requests）

### 需求 10: 向后兼容性

**用户故事**: 作为系统维护者，我希望新功能不影响现有系统，以便平滑升级和灰度发布。

#### 验收标准

1. WHEN 旧版前端接收到evidence_sources事件 THEN THE 旧版前端 SHALL忽略该事件并正常运行
2. WHEN 新增API端点部署 THEN THE 现有API端点 SHALL继续正常工作
3. THE System SHALL支持通过feature flag控制证据来源功能的启用/禁用
4. WHEN 证据来源功能禁用 THEN THE System SHALL不发送evidence_sources事件
5. WHEN RAG检索失败 THEN THE System SHALL继续生成回答，不因证据来源功能而中断

### 需求 11: 性能优化

**用户故事**: 作为用户，我希望证据来源加载快速，不影响聊天体验，以便我能流畅地使用系统。

#### 验收标准

1. THE 预览文本 SHALL限制为200字符以减少传输数据量
2. WHEN 发送evidence_sources事件 THEN THE System SHALL将所有证据来源合并为一个事件批量发送
3. WHEN 文档内容超过1MB THEN THE System SHALL对内容进行gzip压缩
4. THE Frontend SHALL仅在用户点击证据卡片时才加载完整文档（懒加载）
5. THE 证据来源面板 SHALL默认为折叠状态，用户可点击展开

### 需求 12: 错误处理

**用户故事**: 作为用户，我希望在出现错误时能看到清晰的提示信息，以便我了解问题所在。

#### 验收标准

1. WHEN 文档查询失败 THEN THE Frontend SHALL显示错误提示"无法加载文档内容"
2. WHEN 网络请求超时 THEN THE Frontend SHALL显示错误提示"请求超时，请重试"
3. WHEN RAG检索异常 THEN THE System SHALL记录错误日志并继续处理用户请求
4. WHEN 文档ID不存在 THEN THE Document_Service SHALL返回404错误和描述性错误消息
5. WHEN 系统内部错误 THEN THE System SHALL返回500错误并记录详细错误信息

### 需求 13: 聊天消息持久化

**用户故事**: 作为用户，我希望历史消息中也能查看证据来源，以便我回顾之前的对话时了解信息来源。

#### 验收标准

1. WHEN 保存聊天消息 THEN THE System SHALL在消息对象中包含evidenceSources字段
2. THE evidenceSources字段 SHALL存储该消息关联的所有证据来源
3. WHEN 加载历史消息 THEN THE Frontend SHALL渲染历史消息的证据来源面板
4. WHEN 点击历史消息的证据卡片 THEN THE Frontend SHALL能够查询并显示文档内容
5. WHERE 消息没有证据来源 THE evidenceSources字段 SHALL为空数组或null

### 需求 14: 相关度评分可视化

**用户故事**: 作为用户，我希望直观地看到每个证据来源的相关度，以便我优先查看最相关的文档。

#### 验收标准

1. THE 证据卡片 SHALL以可视化方式显示相关度评分（如进度条、星级、百分比）
2. WHEN 相关度评分高于0.7 THEN THE Frontend SHALL使用高亮颜色标识该证据卡片
3. WHEN 相关度评分在0.4-0.7之间 THEN THE Frontend SHALL使用中性颜色标识该证据卡片
4. WHEN 相关度评分低于0.4 THEN THE Frontend SHALL使用低亮度颜色标识该证据卡片
5. THE 证据来源列表 SHALL默认按相关度评分从高到低排序

### 需求 15: 监控与日志

**用户故事**: 作为系统运维人员，我希望能监控证据来源功能的使用情况，以便优化系统性能和用户体验。

#### 验收标准

1. THE System SHALL记录RAG检索耗时到日志
2. THE System SHALL记录文档查询耗时到日志
3. THE System SHALL记录证据来源点击次数到指标系统
4. THE System SHALL记录文档预览加载时间到指标系统
5. THE System SHALL记录每次RAG检索返回的证据来源数量到日志
