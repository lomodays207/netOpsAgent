# Chat Page Label Corrections Bugfix Design

## Overview

聊天页面的快速提示（Quick Prompts）功能中，三个类别标签的命名不够准确，未能清晰反映其功能范围。本次修正通过更新 `static/app.js` 中 `QUICK_PROMPTS` 数组的 `category` 字段值，提升标签的描述性和用户理解度。

**修正策略**：直接修改数据源中的类别名称，无需改动渲染逻辑或样式。

**影响范围**：仅影响快速提示区域的类别标题显示，不影响点击交互、模板填充等功能。

## Glossary

- **Bug_Condition (C)**: 类别标签不准确的条件 - 当 category 字段为 "故障诊断"、"访问关系" 或 "权限提单" 时
- **Property (P)**: 期望的正确行为 - 类别标签应准确反映功能范围（"网络故障诊断"、"访问关系查询"、"提单知识问答"）
- **Preservation**: 必须保持不变的行为 - 点击卡片填充模板、提示项内容、渲染逻辑、其他聊天功能
- **QUICK_PROMPTS**: `static/app.js` 第 9-70 行定义的快速提示数据数组，包含 category 和 items 字段
- **renderQuickPrompts**: `static/app.js` 第 292-334 行的渲染函数，读取 `group.category` 并显示为类别标题
- **category**: 每个快速提示组的分类标签，通过 `titleEl.textContent = group.category` 直接显示在 UI 上

## Bug Details

### Bug Condition

当用户访问聊天页面时，快速提示区域显示的三个类别标签不够准确，未能清晰传达其功能范围。`renderQuickPrompts` 函数直接读取 `QUICK_PROMPTS` 数组中的 `category` 字段并显示，因此问题根源在于数据源中的标签命名。

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type QuickPromptGroup
  OUTPUT: boolean
  
  RETURN input.category IN ['故障诊断', '访问关系', '权限提单']
END FUNCTION
```

### Examples

**示例 1 - 第一个类别**:
- **输入**: 用户访问 `static/index.html`，页面加载 `QUICK_PROMPTS[0]`
- **当前错误行为**: 类别标题显示 "故障诊断"（未明确是网络相关）
- **期望正确行为**: 类别标题显示 "网络故障诊断"（明确诊断范围）

**示例 2 - 第二个类别**:
- **输入**: 用户查看快速提示区域，页面渲染 `QUICK_PROMPTS[1]`
- **当前错误行为**: 类别标题显示 "访问关系"（未明确是查询功能）
- **期望正确行为**: 类别标题显示 "访问关系查询"（强调查询功能）

**示例 3 - 第三个类别**:
- **输入**: 用户查看快速提示区域，页面渲染 `QUICK_PROMPTS[2]`
- **当前错误行为**: 类别标题显示 "权限提单"（未准确反映知识问答性质）
- **期望正确行为**: 类别标题显示 "提单知识问答"（准确描述为知识问答类型）

**边缘情况 - 类别下的提示项**:
- **输入**: 用户点击 "源到目标端口不通" 卡片
- **期望行为**: 无论类别名称如何修改，点击后应正常填充模板文本到输入框

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 点击任何快速提示卡片时，对应的模板文本必须正确填入输入框（`fillPromptTemplate` 功能）
- 每个类别下的具体提示项（title、description、template）内容必须保持不变
- 快速提示的渲染逻辑（`renderQuickPrompts` 函数）和样式（CSS）必须保持不变
- 聊天页面的其他功能（发送消息、查看历史、知识库检索等）必须正常工作

**Scope:**
所有不涉及类别标签显示的功能应完全不受此修复影响。这包括：
- 用户与快速提示卡片的交互（点击、hover 效果）
- 模板文本的填充逻辑
- 快速提示区域的显示/隐藏逻辑
- 页面的其他 UI 组件和功能

## Hypothesized Root Cause

基于代码分析，根本原因已明确：

1. **数据源命名不准确**: `static/app.js` 第 12、30、50 行的 `category` 字段使用了简化的标签名称
   - 第 12 行：`category: '故障诊断'` - 未明确是网络故障诊断
   - 第 30 行：`category: '访问关系'` - 未明确是查询功能
   - 第 50 行：`category: '权限提单'` - 未准确反映知识问答性质

2. **直接显示机制**: `renderQuickPrompts` 函数（第 314 行）直接使用 `titleEl.textContent = group.category`，不做任何转换或映射

3. **无验证机制**: 代码中没有对 category 字段的命名规范进行验证或提示

**结论**: 这是一个纯数据问题，不涉及逻辑错误或渲染 bug。修复只需更新数据源中的字符串值。

## Correctness Properties

Property 1: Bug Condition - 类别标签准确性

_For any_ 快速提示组，当其 category 字段为旧的不准确标签（"故障诊断"、"访问关系"、"权限提单"）时，修复后的代码 SHALL 在 UI 上显示准确的新标签（"网络故障诊断"、"访问关系查询"、"提单知识问答"），使用户能够清晰理解每个类别的功能范围。

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - 非标签功能保持不变

_For any_ 用户与快速提示功能的交互（点击卡片、查看提示项内容、页面渲染），修复后的代码 SHALL 产生与原代码完全相同的行为，保持所有非标签显示的功能（模板填充、交互逻辑、样式渲染）不变。

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

修复方案非常直接，只需修改一个文件中的三个字符串值。

**File**: `static/app.js`

**Function/Section**: `QUICK_PROMPTS` 数组定义（第 9-70 行）

**Specific Changes**:

1. **第一个类别标签修正**（第 12 行）:
   - **当前值**: `category: '故障诊断'`
   - **修改为**: `category: '网络故障诊断'`
   - **理由**: 明确诊断范围为网络相关，避免与其他类型故障混淆

2. **第二个类别标签修正**（第 30 行）:
   - **当前值**: `category: '访问关系'`
   - **修改为**: `category: '访问关系查询'`
   - **理由**: 强调查询功能，明确这是查询类操作而非配置类操作

3. **第三个类别标签修正**（第 50 行）:
   - **当前值**: `category: '权限提单'`
   - **修改为**: `category: '提单知识问答'`
   - **理由**: 准确反映这是关于提单的知识问答，而非实际提单操作

4. **无需修改渲染逻辑**:
   - `renderQuickPrompts` 函数（第 292-334 行）无需修改
   - 直接读取 `group.category` 的机制已经正确

5. **无需修改样式**:
   - CSS 样式文件无需修改
   - 新标签长度适中，不会导致布局问题

## Testing Strategy

### Validation Approach

测试策略采用两阶段方法：首先在未修复代码上验证 bug 存在，然后验证修复后标签正确且功能保持不变。

### Exploratory Bug Condition Checking

**Goal**: 在实施修复前，在未修复代码上确认 bug 存在，验证当前显示的标签确实不准确。

**Test Plan**: 在浏览器中打开聊天页面，检查快速提示区域显示的三个类别标题，确认它们与需求文档中描述的错误行为一致。

**Test Cases**:
1. **第一个类别显示测试**: 访问 `/static/index.html`，确认第一个类别显示为 "故障诊断"（将在修复后失败）
2. **第二个类别显示测试**: 查看快速提示区域，确认第二个类别显示为 "访问关系"（将在修复后失败）
3. **第三个类别显示测试**: 查看快速提示区域，确认第三个类别显示为 "权限提单"（将在修复后失败）
4. **标签长度测试**: 确认当前标签长度较短，可能导致用户理解不清（将在修复后改善）

**Expected Counterexamples**:
- 类别标题显示不够准确，未能清晰传达功能范围
- 可能的用户困惑：不清楚 "故障诊断" 是否包含非网络故障，"访问关系" 是查询还是配置，"权限提单" 是操作还是咨询

### Fix Checking

**Goal**: 验证修复后，所有类别标签都显示为准确的新名称。

**Pseudocode:**
```
FOR ALL group IN QUICK_PROMPTS WHERE isBugCondition(group) DO
  renderedTitle := renderQuickPrompts_fixed(group).categoryTitle
  ASSERT (group.originalCategory = '故障诊断' → renderedTitle = '网络故障诊断') AND
         (group.originalCategory = '访问关系' → renderedTitle = '访问关系查询') AND
         (group.originalCategory = '权限提单' → renderedTitle = '提单知识问答')
END FOR
```

### Preservation Checking

**Goal**: 验证修复后，所有非标签显示的功能行为与原代码完全一致。

**Pseudocode:**
```
FOR ALL interaction WHERE NOT affectsCategoryLabel(interaction) DO
  ASSERT behavior_original(interaction) = behavior_fixed(interaction)
END FOR
```

**Testing Approach**: 手动测试和视觉回归测试相结合，因为：
- 这是一个纯 UI 文本修改，不涉及复杂逻辑
- 主要验证点是视觉显示和交互行为
- 可以通过截图对比快速验证标签变化
- 功能保持性可以通过点击测试快速确认

**Test Plan**: 在修复前记录原有行为（截图、交互测试），修复后对比验证。

**Test Cases**:
1. **模板填充保持测试**: 点击每个类别下的卡片，验证模板文本正确填入输入框（与修复前行为一致）
2. **提示项内容保持测试**: 验证每个卡片的 title 和 description 内容未改变
3. **渲染逻辑保持测试**: 验证快速提示区域的布局、样式、动画效果未改变
4. **其他功能保持测试**: 验证发送消息、查看历史、知识库检索等功能正常工作

### Unit Tests

由于这是一个纯数据修改，传统单元测试的价值有限，但可以考虑：

- **数据结构验证测试**: 验证 `QUICK_PROMPTS` 数组结构完整（每个 group 有 category 和 items）
- **标签命名规范测试**: 验证新的 category 值符合命名规范（非空、长度合理、无特殊字符）
- **渲染输出测试**: 使用 JSDOM 或类似工具，验证 `renderQuickPrompts` 输出的 HTML 包含正确的类别标题

### Property-Based Tests

对于此类简单的文本修改，属性测试的适用性有限，但可以考虑：

- **标签一致性属性**: 对于任意 `QUICK_PROMPTS` 配置，`renderQuickPrompts` 输出的类别标题应与输入的 `category` 字段完全一致
- **功能保持性属性**: 对于任意有效的快速提示配置，修改 category 字段不应影响 items 的渲染和点击行为

### Integration Tests

- **端到端页面加载测试**: 在浏览器中加载 `/static/index.html`，验证快速提示区域正确显示三个新标签
- **用户交互流程测试**: 模拟用户查看快速提示 → 点击卡片 → 填充模板 → 发送消息的完整流程，验证功能正常
- **跨浏览器兼容性测试**: 在 Chrome、Firefox、Safari 等浏览器中验证标签显示一致
- **响应式布局测试**: 在不同屏幕尺寸下验证新标签不会导致布局问题（标签长度增加可能影响移动端显示）
