# 需求文档 - LLM请求链路追踪功能

## 引言

本文档定义了LLM请求链路追踪功能的用户需求和验收标准。该功能旨在记录从用户提问到LLM思考过程、工具调用及最终回答的完整链路信息,存储到本地SQLite数据库,并支持从前端页面查看每次请求的全链路追踪数据。

## 术语表

- **System**: LLM请求链路追踪系统
- **Trace**: 追踪记录,包含一次完整请求的所有链路信息
- **Trace_Database**: 追踪数据库,基于SQLite存储追踪记录
- **LLM_Agent**: LLM诊断代理,执行网络故障诊断
- **General_Chat_Agent**: 通用聊天工具代理,处理一般问题和访问关系查询
- **Tool_Call**: 工具调用记录,包含工具名称、入参和执行结果
- **Reasoning_Step**: LLM推理步骤,记录LLM的思考过程
- **Frontend**: 前端界面,负责展示追踪记录
- **User**: 系统用户,提出问题并查看追踪记录
- **Session**: 会话,包含多轮对话的上下文

## 需求

### 需求 1: 追踪记录数据模型

**用户故事**: 作为系统开发者,我希望定义清晰的追踪记录数据模型,以便准确记录每次请求的完整链路信息。

#### 验收标准

1. THE Trace SHALL包含唯一追踪ID字段(trace_id)
2. THE Trace SHALL包含会话ID字段(session_id)
3. THE Trace SHALL包含用户原始提问字段(user_input)
4. THE Trace SHALL包含请求类型字段(request_type),值为"diagnosis"或"general_chat"
5. THE Trace SHALL包含创建时间字段(created_at)
6. THE Trace SHALL包含完成时间字段(completed_at)
7. THE Trace SHALL包含总执行时间字段(total_time)
8. THE Trace SHALL包含最终回答字段(final_answer)
9. THE Trace SHALL包含状态字段(status),值为"running"、"completed"、"failed"或"interrupted"

### 需求 2: LLM推理步骤记录

**用户故事**: 作为用户,我希望查看LLM的思考过程,以便理解AI如何分析问题和做出决策。

#### 验收标准

1. THE Reasoning_Step SHALL包含步骤序号字段(step_number)
2. THE Reasoning_Step SHALL包含追踪ID字段(trace_id)
3. THE Reasoning_Step SHALL包含推理内容字段(reasoning_content)
4. THE Reasoning_Step SHALL包含时间戳字段(timestamp)
5. WHEN LLM生成推理内容 THEN THE System SHALL记录该推理步骤到数据库

### 需求 3: 工具调用记录

**用户故事**: 作为用户,我希望查看每次工具调用的详细信息,以便了解系统执行了哪些操作和获得了什么结果。

#### 验收标准

1. THE Tool_Call SHALL包含工具调用ID字段(tool_call_id)
2. THE Tool_Call SHALL包含追踪ID字段(trace_id)
3. THE Tool_Call SHALL包含步骤序号字段(step_number)
4. THE Tool_Call SHALL包含工具名称字段(tool_name)
5. THE Tool_Call SHALL包含工具入参字段(arguments),以JSON格式存储
6. THE Tool_Call SHALL包含工具结果字段(result),以JSON格式存储
7. THE Tool_Call SHALL包含执行时间字段(execution_time)
8. THE Tool_Call SHALL包含开始时间字段(started_at)
9. THE Tool_Call SHALL包含完成时间字段(completed_at)
10. THE Tool_Call SHALL包含状态字段(status),值为"running"、"success"或"failed"

### 需求 4: 数据库表结构设计

**用户故事**: 作为系统开发者,我希望设计合理的数据库表结构,以便高效存储和查询追踪记录。

#### 验收标准

1. THE Trace_Database SHALL包含traces表,存储追踪记录主表
2. THE Trace_Database SHALL包含reasoning_steps表,存储LLM推理步骤
3. THE Trace_Database SHALL包含tool_calls表,存储工具调用记录
4. THE traces表 SHALL在trace_id字段上创建主键索引
5. THE traces表 SHALL在session_id字段上创建索引
6. THE traces表 SHALL在created_at字段上创建索引
7. THE reasoning_steps表 SHALL在trace_id字段上创建外键约束
8. THE tool_calls表 SHALL在trace_id字段上创建外键约束

### 需求 5: 诊断流程追踪集成

**用户故事**: 作为系统开发者,我希望在LLM诊断流程中集成追踪记录功能,以便自动记录诊断过程的所有信息。

#### 验收标准

1. WHEN LLM_Agent开始诊断 THEN THE System SHALL创建新的追踪记录
2. WHEN LLM_Agent生成推理内容 THEN THE System SHALL记录推理步骤
3. WHEN LLM_Agent调用工具 THEN THE System SHALL记录工具调用开始
4. WHEN 工具调用完成 THEN THE System SHALL更新工具调用记录的结果和执行时间
5. WHEN 诊断完成 THEN THE System SHALL更新追踪记录的最终回答和完成时间
6. WHEN 诊断失败或中断 THEN THE System SHALL更新追踪记录的状态为"failed"或"interrupted"

### 需求 6: 通用聊天流程追踪集成

**用户故事**: 作为系统开发者,我希望在通用聊天流程中集成追踪记录功能,以便记录访问关系查询等工具调用过程。

#### 验收标准

1. WHEN General_Chat_Agent开始处理请求 THEN THE System SHALL创建新的追踪记录
2. WHEN General_Chat_Agent调用query_access_relations工具 THEN THE System SHALL记录工具调用
3. WHEN 工具调用返回结果 THEN THE System SHALL更新工具调用记录
4. WHEN LLM生成最终回答 THEN THE System SHALL更新追踪记录的最终回答
5. WHEN 通用聊天完成 THEN THE System SHALL更新追踪记录的状态为"completed"

### 需求 7: 追踪记录查询API

**用户故事**: 作为用户,我希望通过API查询追踪记录列表,以便在前端页面展示历史追踪记录。

#### 验收标准

1. THE System SHALL提供GET /api/v1/traces端点,返回追踪记录列表
2. THE 追踪记录列表API SHALL支持分页参数(page和page_size)
3. THE 追踪记录列表API SHALL支持按会话ID过滤(session_id参数)
4. THE 追踪记录列表API SHALL支持按请求类型过滤(request_type参数)
5. THE 追踪记录列表API SHALL支持按时间范围过滤(start_time和end_time参数)
6. THE 追踪记录列表API SHALL默认按创建时间倒序排序
7. THE 追踪记录列表响应 SHALL包含总记录数(total)和当前页数据(items)

### 需求 8: 追踪详情查询API

**用户故事**: 作为用户,我希望查询单个追踪记录的详细信息,以便查看完整的链路追踪数据。

#### 验收标准

1. THE System SHALL提供GET /api/v1/traces/{trace_id}端点,返回追踪详情
2. THE 追踪详情响应 SHALL包含追踪记录基本信息
3. THE 追踪详情响应 SHALL包含所有推理步骤列表(reasoning_steps)
4. THE 追踪详情响应 SHALL包含所有工具调用记录列表(tool_calls)
5. THE 推理步骤列表 SHALL按步骤序号升序排序
6. THE 工具调用记录列表 SHALL按步骤序号升序排序
7. WHEN 追踪ID不存在 THEN THE System SHALL返回404错误

### 需求 9: 前端追踪记录列表页面

**用户故事**: 作为用户,我希望在前端页面查看追踪记录列表,以便浏览历史请求的追踪信息。

#### 验收标准

1. THE Frontend SHALL提供追踪记录列表页面(/traces路由)
2. THE 追踪记录列表页面 SHALL显示追踪ID、用户提问、请求类型、状态、创建时间和执行时间
3. THE 追踪记录列表页面 SHALL支持分页导航
4. THE 追踪记录列表页面 SHALL支持按会话ID筛选
5. THE 追踪记录列表页面 SHALL支持按请求类型筛选
6. THE 追踪记录列表页面 SHALL支持按时间范围筛选
7. WHEN 点击追踪记录行 THEN THE Frontend SHALL导航到追踪详情页面

### 需求 10: 前端追踪详情页面

**用户故事**: 作为用户,我希望在详情页面查看完整的链路追踪信息,以便深入了解请求的执行过程。

#### 验收标准

1. THE Frontend SHALL提供追踪详情页面(/traces/{trace_id}路由)
2. THE 追踪详情页面 SHALL显示追踪记录基本信息(追踪ID、会话ID、用户提问、请求类型、状态、时间信息)
3. THE 追踪详情页面 SHALL显示LLM推理步骤时间线
4. THE 追踪详情页面 SHALL显示工具调用记录时间线
5. THE 推理步骤时间线 SHALL显示步骤序号、推理内容和时间戳
6. THE 工具调用时间线 SHALL显示工具名称、入参、结果和执行时间
7. THE 追踪详情页面 SHALL显示最终回答内容
8. THE 工具调用入参和结果 SHALL以格式化JSON展示

### 需求 11: 追踪记录自动清理

**用户故事**: 作为系统运维人员,我希望系统能自动清理过期的追踪记录,以便控制数据库大小和提高查询性能。

#### 验收标准

1. THE System SHALL支持配置追踪记录保留天数(TRACE_RETENTION_DAYS环境变量)
2. THE System SHALL默认保留追踪记录30天
3. THE System SHALL每天凌晨2点执行追踪记录清理任务
4. WHEN 追踪记录创建时间超过保留天数 THEN THE System SHALL删除该追踪记录
5. WHEN 删除追踪记录 THEN THE System SHALL级联删除关联的推理步骤和工具调用记录

### 需求 12: 性能优化

**用户故事**: 作为系统开发者,我希望追踪记录功能不影响主流程性能,以便保证用户体验。

#### 验收标准

1. THE System SHALL使用异步方式写入追踪记录到数据库
2. THE System SHALL使用批量插入方式写入推理步骤和工具调用记录
3. THE 工具调用结果 SHALL限制存储大小不超过10KB,超过部分截断
4. THE 推理内容 SHALL限制存储大小不超过5KB,超过部分截断
5. THE 追踪记录写入失败 SHALL不影响主流程执行

### 需求 13: 错误处理

**用户故事**: 作为用户,我希望在追踪记录功能出现错误时能看到清晰的提示,以便了解问题所在。

#### 验收标准

1. WHEN 追踪记录写入失败 THEN THE System SHALL记录错误日志
2. WHEN 追踪记录查询失败 THEN THE Frontend SHALL显示错误提示"无法加载追踪记录"
3. WHEN 追踪详情查询失败 THEN THE Frontend SHALL显示错误提示"无法加载追踪详情"
4. WHEN 数据库连接失败 THEN THE System SHALL记录错误日志并继续执行主流程
5. WHEN 追踪ID格式无效 THEN THE System SHALL返回400错误和描述性错误消息

### 需求 14: 安全与隐私

**用户故事**: 作为系统安全管理员,我希望追踪记录功能遵循安全和隐私最佳实践,以便保护用户数据。

#### 验收标准

1. THE System SHALL对敏感信息(如密码、密钥)进行脱敏处理后再存储
2. THE 追踪记录查询API SHALL验证用户权限
3. THE System SHALL限制追踪记录查询频率为每分钟最多30次
4. WHEN 超过查询频率限制 THEN THE System SHALL返回429错误
5. THE 工具调用入参和结果 SHALL过滤掉包含敏感关键词的字段

### 需求 15: 监控与日志

**用户故事**: 作为系统运维人员,我希望能监控追踪记录功能的运行状态,以便及时发现和解决问题。

#### 验收标准

1. THE System SHALL记录追踪记录写入成功次数到指标系统
2. THE System SHALL记录追踪记录写入失败次数到指标系统
3. THE System SHALL记录追踪记录查询耗时到日志
4. THE System SHALL记录追踪记录数据库大小到指标系统
5. THE System SHALL记录追踪记录清理任务执行结果到日志

### 需求 16: 向后兼容性

**用户故事**: 作为系统维护者,我希望追踪记录功能不影响现有系统,以便平滑升级。

#### 验收标准

1. THE System SHALL支持通过feature flag控制追踪记录功能的启用/禁用
2. WHEN 追踪记录功能禁用 THEN THE System SHALL不写入追踪记录
3. THE 现有API端点 SHALL继续正常工作
4. THE 现有会话管理功能 SHALL不受追踪记录功能影响
5. WHEN 追踪记录数据库不可用 THEN THE System SHALL继续执行主流程

### 需求 17: 追踪记录导出

**用户故事**: 作为用户,我希望能导出追踪记录数据,以便进行离线分析和审计。

#### 验收标准

1. THE Frontend SHALL在追踪记录列表页面提供导出按钮
2. WHEN 点击导出按钮 THEN THE System SHALL生成CSV格式的追踪记录文件
3. THE CSV文件 SHALL包含追踪ID、会话ID、用户提问、请求类型、状态、创建时间、执行时间等字段
4. THE System SHALL支持导出当前筛选条件下的所有追踪记录
5. THE 导出功能 SHALL限制单次导出记录数不超过1000条

### 需求 18: 追踪记录搜索

**用户故事**: 作为用户,我希望能搜索追踪记录,以便快速找到特定的请求链路信息。

#### 验收标准

1. THE 追踪记录列表页面 SHALL提供搜索框
2. THE 搜索功能 SHALL支持按用户提问内容模糊搜索
3. THE 搜索功能 SHALL支持按追踪ID精确搜索
4. THE 搜索功能 SHALL支持按会话ID精确搜索
5. WHEN 输入搜索关键词 THEN THE Frontend SHALL实时更新追踪记录列表

### 需求 19: 追踪记录统计

**用户故事**: 作为系统运维人员,我希望查看追踪记录的统计信息,以便了解系统使用情况和性能表现。

#### 验收标准

1. THE System SHALL提供GET /api/v1/traces/stats端点,返回追踪记录统计信息
2. THE 统计信息 SHALL包含总追踪记录数
3. THE 统计信息 SHALL包含按请求类型分组的记录数
4. THE 统计信息 SHALL包含按状态分组的记录数
5. THE 统计信息 SHALL包含平均执行时间
6. THE 统计信息 SHALL包含最近24小时的追踪记录数
7. THE 统计信息 SHALL包含最近7天的追踪记录数

### 需求 20: 追踪记录与会话关联

**用户故事**: 作为用户,我希望在会话页面查看该会话的所有追踪记录,以便了解会话中每次请求的执行细节。

#### 验收标准

1. THE 会话详情页面 SHALL显示该会话的追踪记录列表
2. THE 会话追踪记录列表 SHALL显示追踪ID、用户提问、请求类型、状态和创建时间
3. WHEN 点击会话追踪记录 THEN THE Frontend SHALL导航到追踪详情页面
4. THE 会话追踪记录列表 SHALL按创建时间升序排序
5. THE 会话追踪记录列表 SHALL支持展开/折叠显示

