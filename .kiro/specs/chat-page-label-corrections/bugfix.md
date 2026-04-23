# Bugfix Requirements Document

## Introduction

聊天页面的快速提示（Quick Prompts）功能中，三个类别标签的命名不够准确，未能清晰反映其功能范围。本次修正旨在提升标签的描述性和用户理解度，使用户能够更准确地识别每个类别的用途。

**影响范围**: 聊天页面前端界面（`static/app.js` 中的 `QUICK_PROMPTS` 数组）

**修正内容**:
- "故障诊断" → "网络故障诊断"（明确诊断范围为网络相关）
- "访问关系" → "访问关系查询"（强调查询功能）
- "权限提单" → "提单知识问答"（准确描述为知识问答类型）

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 用户查看聊天页面的快速提示区域 THEN 第一个类别显示为 "故障诊断"，未明确指出是网络故障诊断

1.2 WHEN 用户查看聊天页面的快速提示区域 THEN 第二个类别显示为 "访问关系"，未明确指出是查询功能

1.3 WHEN 用户查看聊天页面的快速提示区域 THEN 第三个类别显示为 "权限提单"，未准确反映其为知识问答性质

### Expected Behavior (Correct)

2.1 WHEN 用户查看聊天页面的快速提示区域 THEN 第一个类别 SHALL 显示为 "网络故障诊断"，明确诊断范围

2.2 WHEN 用户查看聊天页面的快速提示区域 THEN 第二个类别 SHALL 显示为 "访问关系查询"，明确查询功能

2.3 WHEN 用户查看聊天页面的快速提示区域 THEN 第三个类别 SHALL 显示为 "提单知识问答"，准确反映知识问答性质

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 用户点击任何快速提示卡片 THEN 系统 SHALL CONTINUE TO 将对应的模板文本填入输入框

3.2 WHEN 用户查看快速提示区域 THEN 每个类别下的具体提示项（title、description、template）SHALL CONTINUE TO 保持不变

3.3 WHEN 用户与聊天页面的其他功能交互（发送消息、查看历史等）THEN 这些功能 SHALL CONTINUE TO 正常工作

3.4 WHEN 页面加载快速提示组件 THEN 渲染逻辑和样式 SHALL CONTINUE TO 保持一致

## Bug Condition Derivation

### Bug Condition Function

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type QuickPromptCategory
  OUTPUT: boolean
  
  // 返回 true 当类别标签不准确时
  RETURN (X.category = "故障诊断") OR 
         (X.category = "访问关系") OR 
         (X.category = "权限提单")
END FUNCTION
```

### Property Specification - Fix Checking

```pascal
// Property: Fix Checking - 类别标签准确性
FOR ALL X WHERE isBugCondition(X) DO
  result ← renderQuickPrompts'(X)
  ASSERT (X.category = "故障诊断" → result.displayedCategory = "网络故障诊断") AND
         (X.category = "访问关系" → result.displayedCategory = "访问关系查询") AND
         (X.category = "权限提单" → result.displayedCategory = "提单知识问答")
END FOR
```

### Preservation Goal

```pascal
// Property: Preservation Checking - 非标签功能保持不变
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT renderQuickPrompts(X) = renderQuickPrompts'(X)
END FOR

// 具体保持不变的行为：
// 1. 点击卡片填充模板的功能
// 2. 每个类别下的具体提示项内容
// 3. 快速提示的渲染逻辑和样式
// 4. 其他聊天页面功能
```

### Counterexample

**具体示例**:
- **输入**: 用户访问聊天页面 `static/index.html`
- **当前错误行为**: 
  - 第一个类别显示 "故障诊断"
  - 第二个类别显示 "访问关系"
  - 第三个类别显示 "权限提单"
- **期望正确行为**:
  - 第一个类别显示 "网络故障诊断"
  - 第二个类别显示 "访问关系查询"
  - 第三个类别显示 "提单知识问答"

**代码位置**: `static/app.js` 第 9-58 行的 `QUICK_PROMPTS` 数组定义
