# LLM 意图识别混合路由设计

## 背景

当前聊天统一入口 `/api/v1/chat/stream` 会先调用后端规则路由器，根据用户消息决定进入以下四条路径：

- `start_diagnosis`
- `continue_diagnosis`
- `clarify`
- `general_chat`

现有实现位于 `src/agent/intent_router.py`，核心特点是：

- 使用正则和少量上下文做快速分流
- 规则明确、成本低、延迟稳定
- 对结构化诊断请求和显式访问关系查询效果较好
- 对模糊报障、边界问句、方法咨询与真实报障混合场景的表达能力有限

本次设计的目标不是直接删除规则，而是在保持现有 API 分流语义不变的前提下，引入 LLM 作为低确定性场景的辅助判定器，提升入口意图识别的鲁棒性。

## 目标

- 保持现有聊天统一入口和四类路由语义不变
- 在规则低确定性的场景下引入 LLM 判定，改善模糊问句和边界问句路由质量
- 保持整体策略偏保守，优先避免误触发诊断
- 保证 LLM 异常、超时或输出非法时可安全回退到纯规则
- 支持通过配置快速切换 `rule` 与 `hybrid` 模式
- 为后续调优提供足够的日志和测试基线

## 非目标

- 本次不改造诊断执行链路、工具调用链路或诊断 Agent
- 本次不改造 `NLU.parse_user_input()` 的字段抽取逻辑
- 本次不引入新的用户可见路由类型
- 本次不直接上线纯 LLM 路由模式
- 本次不在前端增加意图识别逻辑

## 本次确认的产品约束

本设计基于以下已确认约束：

- 路由策略选择：`A`，即规则主导，LLM 仅处理规则低确定性的消息
- LLM 介入范围选择：`2`，即处理所有规则低确定性消息，包括模糊报障、方法类问句、访问关系边界句等
- 冲突处理策略：`保守`，即规则与 LLM 冲突时，优先避免误触发诊断

## 当前实现概览

### 现有入口

`src/api.py` 中的 `/api/v1/chat/stream` 当前逻辑为：

1. 读取当前会话
2. 调用 `intent_router.route_message(request.message, session=session)`
3. 根据 `IntentDecision.route` 分流到诊断、追问、澄清或通用聊天

现有入口已经具备清晰的路由边界，因此本次改造不需要改变 API 层分支结构，只需要替换路由器实现。

### 现有规则路由能力

当前规则主要依赖以下信号：

- 端点对提取结果
- IP
- 故障词
- 动作词
- 问句风格
- 工具命令
- 端口或服务名
- 访问关系问法
- 当前会话状态

规则路由的主要问题不在于架构错误，而在于它把“是否需要诊断”和“表达是否完整”压缩成了有限规则，导致边界问句只能靠不断补充正则。

## 方案比较

### 方案一：规则优先，低确定性才升级到 LLM

做法：

- 规则仍是第一层
- 只有规则判断为低确定性时，才调用 LLM 做二次判定
- LLM 失败时直接回退规则

优点：

- 改动最小
- 成本和延迟可控
- 与当前 API 接入点契合度最高
- 最符合保守上线策略

缺点：

- 仍需维护一部分强命中规则
- 路由逻辑分散在规则和 LLM 两层

### 方案二：规则提特征，LLM 统一仲裁

做法：

- 规则层不再直接返回最终路由
- 规则只产出信号、分数和上下文
- LLM 对所有消息做最终仲裁

优点：

- 结构更统一
- 未来扩展更多意图更顺

缺点：

- 改动较大
- 接入风险高
- 第一版上线成本不必要地增加

### 方案三：影子模式，先只做观测

做法：

- 线上仍按规则路由
- 后台额外运行 LLM 判定并记录对比日志
- 暂不影响真实分流

优点：

- 风险最低
- 有利于收集样本和调参

缺点：

- 不能直接改善当前用户体验
- 需要额外等待一轮观测后才能切换

## 选型结论

本次采用方案一作为主方案，并保留轻量级影子分析能力：

- 实际分流采用 `规则优先 + LLM 辅助 + 规则回退`
- 配置上支持 `rule` 与 `hybrid`
- 日志上保留规则决策、LLM 决策和最终决策，便于后续对比分析

## 设计总览

本次引入三层组件：

- `RuleIntentRouter`
- `LLMIntentClassifier`
- `HybridIntentRouter`

其中：

- `RuleIntentRouter` 负责强确定性规则判断，并给出 `hard` 或 `soft` 级别结果
- `LLMIntentClassifier` 负责在 `soft` 场景下输出标准化 JSON 判定
- `HybridIntentRouter` 负责调用规则、决定是否升级到 LLM、进行保守合并，并产出最终 `IntentDecision`

API 层仍只消费一个统一结果对象，不感知内部细节。

## 组件设计

### 1. RuleIntentRouter

建议将当前 `src/agent/intent_router.py` 中的规则能力迁移或重构为 `RuleIntentRouter`。其职责不是简单替换名字，而是补齐“规则强弱”和“命中信号”两个输出。

建议输出模型：

```python
@dataclass
class RuleIntentResult:
    route: str
    confidence: float
    reason: str
    certainty: str  # "hard" | "soft"
    clarify_message: Optional[str] = None
    signals: Dict[str, Any] = field(default_factory=dict)
```

职责：

- 处理所有现有规则逻辑
- 区分 `hard` 与 `soft`
- 输出结构化信号，供 LLM prompt 和最终合并使用

### 2. LLMIntentClassifier

`LLMIntentClassifier` 是一个受限分类器，不是聊天助手。它只做以下事情：

- 接收当前消息、会话上下文和规则初判结果
- 通过 `LLMClient.invoke_with_json()` 获取 JSON 输出
- 将 JSON 解析为受控结构
- 对非法值、缺字段或格式错误直接视为失败

建议输出模型：

```python
@dataclass
class LLMIntentResult:
    route: str
    confidence: float
    reason: str
    clarify_message: Optional[str] = None
    needs_more_detail: bool = False
    detected_signals: Dict[str, Any] = field(default_factory=dict)
```

### 3. HybridIntentRouter

`HybridIntentRouter` 作为新的统一入口，实现以下流程：

1. 调用 `RuleIntentRouter`
2. 若结果为 `hard`，直接返回
3. 若结果为 `soft`，调用 `LLMIntentClassifier`
4. 对规则结果和 LLM 结果做保守合并
5. 输出与现有 API 完全兼容的 `IntentDecision`

建议保留与当前一致的方法签名：

```python
def route_message(self, message: str, session: Optional[Any] = None) -> IntentDecision:
    ...
```

## hard 与 soft 的判定规则

### hard 场景

以下场景不调用 LLM：

- `session.status == "waiting_user"`，直接 `continue_diagnosis`
- 明确结构化诊断请求，满足“具体端点对 + 故障现象/动作词/命令/IP”
- 明确访问关系数据查询，满足“系统标识符 + 访问关系问法 + 非知识问法”

这类场景的共同特点是路由高度明确，再调用 LLM 的收益小于成本与抖动。

### soft 场景

以下场景调用 LLM：

- 模糊报障，例如“我这边访问不通”
- 方法类问句，例如“端口不通怎么排查”
- 工具词或服务词存在，但缺少明确对象
- 已有诊断会话中，当前消息是否算续答并不明显
- 访问关系边界问句，例如“访问关系如何开权限”

这类场景的共同特点是：

- 规则能够识别出“和某类意图接近”
- 但不能高置信度判断应该直接进入哪条流程

## LLM 输入与输出契约

### 输入上下文

LLM 不需要完整长会话，只需要最小必要上下文：

- 当前消息 `message`
- `session.status`
- 是否为诊断会话
- 最近 3 到 5 条消息
- 规则初判 `route`
- 规则 `certainty`
- 规则命中的关键 `signals`

这样可以控制 token 成本，同时让 LLM 理解“当前句子是在新提问还是在追答”。

### 输出 JSON Schema

建议约定如下 JSON 结构：

```json
{
  "route": "start_diagnosis",
  "confidence": 0.87,
  "reason": "issue_report_with_partial_context",
  "clarify_message": "请补充源主机、目标主机和端口",
  "needs_more_detail": true,
  "detected_signals": {
    "has_failure": true,
    "has_question_style": false,
    "has_action_request": true,
    "has_specific_endpoints": false,
    "has_session_followup": false,
    "is_access_relation_knowledge": false
  }
}
```

约束要求：

- `route` 只能是四个既有值之一
- `confidence` 必须是 `0.0` 到 `1.0`
- `reason` 必须是短字符串，便于日志分析
- `clarify_message` 只在 `clarify` 场景下生效
- `needs_more_detail` 和 `detected_signals` 仅作为后处理依据，不直接决定最终路由

## Prompt 设计

### System Prompt 原则

LLM 的 system prompt 必须明确它是“路由分类器”，不是“回答用户问题的助手”。核心约束如下：

- 只能在四类路由中选择一个
- 信息不足时优先 `clarify`
- 不要激进地把模糊报障直接转为诊断
- 方法咨询、知识问答、访问关系知识问题优先 `general_chat`
- 只有在诊断对象和上下文较明确时，才给 `start_diagnosis`
- 只有在当前消息明显是诊断会话追答时，才给 `continue_diagnosis`
- 只输出 JSON，不输出解释性文本

### User Prompt 内容

建议 prompt 中传入：

- 当前用户消息
- 会话状态
- 最近消息摘要
- 规则初判
- 规则信号
- 路由定义说明

这样模型是在“规则辅助上下文”中做判定，而不是脱离现有系统另起一套语义。

## 保守合并策略

最终路由不直接等于 LLM 输出，而是由 `HybridIntentRouter` 合并得出。

### 接受阈值

建议阈值：

- `INTENT_LLM_MIN_CONFIDENCE = 0.80`
- `INTENT_LLM_DIAGNOSIS_MIN_CONFIDENCE = 0.85`

解释：

- 对 `general_chat` 与 `clarify` 的接受门槛略低
- 对 `start_diagnosis` 与 `continue_diagnosis` 的接受门槛更高

### 保守规则

建议合并时遵守以下规则：

- 只要缺少明确对象，LLM 即使建议 `start_diagnosis`，也降级为 `clarify`
- 规则与 LLM 冲突时，优先避免误触发诊断
- `start_diagnosis` 与 `clarify` 冲突时，优先 `clarify`
- `start_diagnosis` 与 `general_chat` 冲突时：
  - 若规则信号显示更像方法咨询，则优先 `general_chat`
  - 若规则信号显示更像报障但信息不足，则优先 `clarify`
- `general_chat` 与 `clarify` 冲突时：
  - 若存在明显报障信号，则优先 `clarify`
  - 否则优先 `general_chat`

### 回退规则

以下情况直接回退规则结果：

- LLM 请求异常
- 超时
- 认证失败
- 输出不是合法 JSON
- JSON 缺关键字段
- `route` 不在允许枚举中
- `confidence` 低于接受阈值

## API 接入设计

### 路由器构建方式

当前 `src/api.py` 中使用全局实例：

```python
intent_router = IntentRouter()
```

建议改为工厂函数：

```python
intent_router = build_intent_router()
```

工厂根据配置返回：

- `RuleIntentRouter`
- `HybridIntentRouter`

### API 层变更范围

`/api/v1/chat/stream` 的主体分流逻辑不变，继续只依赖：

```python
decision = intent_router.route_message(request.message, session=session)
```

这样可以把所有变化封装在路由器内部，避免 API 层承担新的复杂度。

## 配置设计

建议新增以下环境变量：

- `INTENT_ROUTER_MODE=rule|hybrid`
- `INTENT_LLM_MIN_CONFIDENCE=0.80`
- `INTENT_LLM_DIAGNOSIS_MIN_CONFIDENCE=0.85`
- `INTENT_LOG_DECISIONS=true|false`

### 配置行为

- 默认值建议为 `rule`
- 开发和测试环境可启用 `hybrid`
- 当 `INTENT_ROUTER_MODE=hybrid` 但 `LLMClient` 初始化失败时：
  - 启动不应整体失败
  - 自动降级为 `rule`
  - 日志中记录一次告警

## 日志与观测设计

为便于后续调优，需要记录结构化决策日志。建议字段：

- `session_id`
- `message`
- `rule_route`
- `rule_certainty`
- `rule_reason`
- `llm_route`
- `llm_confidence`
- `llm_reason`
- `final_route`
- `fallback_reason`
- `latency_ms`

### 日志用途

这些日志至少要能回答以下问题：

- 哪些消息最容易触发规则升级到 LLM
- 规则与 LLM 最常见的冲突模式是什么
- LLM 是否把过多模糊问句推成诊断
- 混合模式相对纯规则增加了多少延迟
- 哪类问句最需要进一步补样本或调 prompt

## 测试设计

### 1. 单元测试

建议新增以下测试文件：

- `tests/unit/agent/test_rule_intent_router.py`
- `tests/unit/agent/test_llm_intent_router.py`
- `tests/unit/agent/test_hybrid_intent_router.py`

重点覆盖：

- `hard` 场景不调用 LLM
- `soft` 场景会调用 LLM
- LLM 非法 JSON 时回退规则
- LLM 超时或异常时回退规则
- LLM 低置信度时回退规则
- 冲突时按保守策略合并

### 2. API 测试

补充 `/api/v1/chat/stream` 的注入测试，验证：

- `rule` 模式下行为与当前一致
- `hybrid` 模式下可正确走到四类下游分支
- 降级为 `rule` 时用户无感知失败

### 3. 回归样本集

建议准备固定问句集，至少覆盖以下四类：

- 明确诊断请求
- 模糊报障
- 方法咨询
- 访问关系数据查询与访问关系知识问法边界

这组样本用于：

- 调整 prompt
- 调整阈值
- 验证混合路由不会引入明显回归

## 灰度上线策略

建议按以下顺序推进：

1. 先实现 `rule` 与 `hybrid` 双模式
2. 默认保持 `rule`
3. 在开发环境开启 `hybrid`
4. 观察日志中的规则与 LLM 差异
5. 在测试环境或小流量环境开启 `hybrid`
6. 确认误判率、延迟和稳定性后，再考虑将默认切为 `hybrid`

这样即使 LLM 效果不理想，也可以通过配置快速回退到纯规则。

## 风险与应对

### 风险一：延迟增加

`soft` 场景引入一次额外 LLM 调用，可能增加首包时间。

应对：

- 只在 `soft` 场景调用
- 只传最近 3 到 5 条消息
- 使用轻量 prompt 和较低温度

### 风险二：误触发诊断

LLM 可能把模糊报障或方法咨询误判为真实诊断请求。

应对：

- 使用更高的诊断类接受阈值
- 保守合并时优先 `clarify`
- 对缺少明确对象的诊断建议强制降级

### 风险三：模型输出不稳定

不同模型或不同时间的输出可能存在轻微波动。

应对：

- 强制 JSON 输出
- 用受控 schema 校验
- 非法输出统一回退规则

### 风险四：后续维护成本上升

如果规则、prompt、阈值和日志没有边界，混合路由容易失控。

应对：

- 规则只负责 `hard/soft` 初判
- LLM 只负责受限分类
- 合并策略集中在 `HybridIntentRouter`
- 所有阈值都走配置

## 验收标准

- 保持现有四类路由语义和 API 分流结构不变
- `hard` 场景不会额外触发 LLM 调用
- `soft` 场景可通过 LLM 做二次判定
- LLM 失败时可以无缝回退规则
- 混合模式可通过配置开启和关闭
- 日志可清晰看出规则结果、LLM 结果和最终结果
- 至少具备单测、API 测试和固定样本回归集

## 实施建议

建议按以下顺序进入实现：

1. 抽取现有规则为 `RuleIntentRouter`
2. 实现 `LLMIntentClassifier` 及其 schema 校验
3. 实现 `HybridIntentRouter`
4. 在 `src/api.py` 中用工厂函数接入
5. 补充日志和配置
6. 补测试
7. 开发环境验证后再切换配置

## 结论

本设计采用“规则主导、LLM 辅助、保守合并、失败回退”的混合意图识别方案。该方案在不改变现有聊天入口与下游诊断链路的前提下，为低确定性问句提供更好的判定能力，并通过配置、日志和测试控制上线风险。
