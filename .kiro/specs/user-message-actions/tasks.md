# Implementation Plan: User Message Actions

## Overview

本实现计划将用户消息操作功能分解为可执行的编码任务。功能包括为用户消息添加复制和编辑按钮，支持消息内容的快速复制和编辑重发。实现采用原生 JavaScript，遵循现有代码风格，确保与当前聊天系统无缝集成。

## Tasks

- [x] 1. 创建核心样式和 CSS 类
  - 在 `static/style.css` 中添加消息操作按钮的样式定义
  - 定义 `.message-actions`、`.message-action-btn`、`.message-copy-btn`、`.message-edit-btn` 样式
  - 定义编辑模式相关样式：`.edit-message-textarea`、`.edit-buttons`、`.edit-cancel-btn`、`.edit-send-btn`
  - 添加视觉反馈样式：`.success-feedback`、按钮 hover 和 focus 状态
  - _Requirements: 1.2, 1.3, 1.4_

- [x] 2. 实现剪贴板处理模块
  - [x] 2.1 创建 ClipboardHandler 类
    - 在 `static/script.js` 中实现 `ClipboardHandler` 类
    - 实现 `copyToClipboard(text)` 方法，使用 Clipboard API
    - 实现降级方案：当 Clipboard API 不可用时使用 `document.execCommand('copy')`
    - 添加错误处理和日志记录
    - _Requirements: 2.1, 2.2, 12.1_
  
  - [x] 2.2 编写 ClipboardHandler 单元测试
    - 测试 Clipboard API 成功场景
    - 测试降级方案（execCommand）
    - 测试错误处理和边界条件
    - _Requirements: 2.1, 2.2_
  
  - [x] 2.3 实现视觉反馈功能
    - 实现 `showCopyFeedback(button, duration)` 方法
    - 成功时显示 ✓ 图标，失败时显示 ✗ 图标
    - 2秒后恢复原始图标 📋
    - _Requirements: 2.3, 2.4, 2.5_

- [ ] 3. 实现编辑模式渲染模块
  - [x] 3.1 创建 EditModeRenderer 类
    - 在 `static/script.js` 中实现 `EditModeRenderer` 类
    - 实现 `createEditableTextarea(text)` 方法，创建可编辑文本框
    - 实现 `createEditButtons()` 方法，创建取消和发送按钮
    - 文本框自动调整高度，光标定位到文本末尾
    - _Requirements: 3.2, 3.5, 3.6_
  
  - [x] 3.2 实现编辑模式切换逻辑
    - 实现 `renderEditMode(messageElement, originalText)` 方法
    - 隐藏原始消息文本和操作按钮
    - 显示编辑文本框和操作按钮组
    - 设置 `data-editing="true"` 标记
    - _Requirements: 3.1, 3.3, 3.4, 3.7_
  
  - [x] 3.3 实现退出编辑模式逻辑
    - 实现 `restoreOriginalMessage(messageElement, originalText)` 方法
    - 移除编辑文本框和操作按钮组
    - 恢复原始消息文本显示
    - 恢复操作按钮可见性
    - _Requirements: 4.1, 4.6, 4.7_
  
  - [ ] 3.4 编写 EditModeRenderer 单元测试
    - 测试编辑模式 UI 正确渲染
    - 测试退出编辑模式后 DOM 恢复
    - 测试文本框自动聚焦和光标位置
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 4. 实现消息操作管理器
  - [x] 4.1 创建 MessageActionsManager 类
    - 在 `static/script.js` 中实现 `MessageActionsManager` 类
    - 实现 `createActionsContainer()` 方法，创建操作按钮容器
    - 创建复制按钮（📋 图标）和编辑按钮（✏️ 图标）
    - 添加适当的 aria-label 属性以支持可访问性
    - _Requirements: 1.1, 1.3, 1.4, 9.1, 9.2_
  
  - [x] 4.2 实现添加操作按钮逻辑
    - 实现 `addActionsToMessage(messageElement, messageText)` 方法
    - 检查是否已存在操作按钮容器，防止重复添加
    - 将操作按钮容器添加到消息内容区域
    - 绑定复制和编辑按钮的事件处理器
    - _Requirements: 1.1, 1.2, 1.5_
  
  - [ ] 4.3 实现复制操作处理
    - 实现 `handleCopy(text, button)` 方法
    - 调用 ClipboardHandler 执行复制操作
    - 显示视觉反馈
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 2.6_
  
  - [ ] 4.4 实现编辑操作处理
    - 实现 `handleEdit(messageElement, originalText)` 方法
    - 调用 EditModeRenderer 进入编辑模式
    - 确保同时只有一条消息处于编辑模式
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 6.4, 6.5_
  
  - [ ] 4.5 编写 MessageActionsManager 单元测试
    - 测试 `addActionsToMessage` 正确创建按钮容器
    - 测试按钮事件绑定
    - 测试重复添加的防护机制
    - 测试互斥编辑模式
    - _Requirements: 1.1, 1.2, 1.5, 6.4, 6.5_

- [ ] 5. Checkpoint - 验证核心模块功能
  - 确保所有核心类（ClipboardHandler, EditModeRenderer, MessageActionsManager）已正确实现
  - 手动测试复制和编辑模式切换功能
  - 如有问题,请向用户反馈

- [ ] 6. 实现编辑消息提交逻辑
  - [ ] 6.1 实现提交验证和处理
    - 实现 `submitEditedMessage(messageElement, newText)` 方法
    - 验证编辑后的文本非空（trim 后）
    - 如果文本为空，显示警告"消息内容不能为空"并保持编辑模式
    - 如果文本与原始相同，直接退出编辑模式不发送新消息
    - _Requirements: 4.2, 4.3, 4.4_
  
  - [ ] 6.2 集成现有消息发送系统
    - 调用现有的 `sendMessage(text)` 函数提交新消息
    - 确保新消息正确添加到聊天界面
    - 确保消息保存到 localStorage（如果适用）
    - 触发后端 API 调用（如果适用）
    - 调用 `scrollToBottom()` 滚动到最新消息
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  
  - [ ] 6.3 实现系统状态协调
    - 检查 `isWaitingForResponse` 状态
    - 当系统等待响应时，禁用发送按钮并显示提示
    - 响应完成后重新启用发送按钮
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [ ] 6.4 编写提交逻辑单元测试
    - 测试空文本验证
    - 测试相同文本处理
    - 测试与消息发送系统的集成
    - 测试系统状态协调
    - _Requirements: 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3_

- [ ] 7. 实现文本安全处理
  - [ ] 7.1 添加 XSS 防护
    - 确保使用 `textContent` 而非 `innerHTML` 设置用户文本
    - 在提交编辑消息时应用现有的 `escapeHtml()` 函数
    - 验证特殊字符（emoji、Unicode）正确处理
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ] 7.2 编写安全性测试
    - 测试包含 HTML 标签的文本不被解析
    - 测试包含 `<script>` 标签的文本被正确转义
    - 测试特殊字符和 emoji 处理
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 8. 实现键盘交互支持
  - [ ] 8.1 添加键盘事件处理
    - 在编辑文本框上监听 Escape 键，退出编辑模式
    - 在编辑文本框上监听 Ctrl+Enter（Mac 上 Cmd+Enter），提交编辑
    - 确保所有按钮支持 Tab 键导航
    - 确保按钮支持 Enter 和 Space 键触发
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  
  - [ ] 8.2 添加焦点指示器样式
    - 在 CSS 中为所有交互元素添加可见的 focus 样式
    - 确保焦点指示器符合可访问性标准
    - _Requirements: 8.5_
  
  - [ ] 8.3 编写键盘交互测试
    - 测试 Escape 键退出编辑
    - 测试 Ctrl+Enter 提交编辑
    - 测试 Tab 键导航
    - 测试 Enter/Space 键触发按钮
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 9. 实现可访问性增强
  - [ ] 9.1 添加 ARIA 标签
    - 为所有按钮添加 `aria-label` 属性
    - 为编辑文本框添加 `aria-label` 属性
    - 为编辑按钮组添加 `aria-label` 属性
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ] 9.2 添加状态变化通知
    - 使用 `aria-live` 区域通知编辑模式状态变化
    - 确保屏幕阅读器能够感知操作反馈
    - _Requirements: 9.6_
  
  - [ ] 9.3 编写可访问性测试
    - 验证所有 ARIA 标签正确设置
    - 验证状态变化通知正常工作
    - 使用自动化工具检查 WCAG 2.1 AA 合规性
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

- [ ] 10. Checkpoint - 验证完整功能
  - 手动测试所有功能：复制、编辑、取消、提交
  - 测试键盘交互和可访问性
  - 如有问题，请向用户反馈

- [ ] 11. 集成到现有消息系统
  - [x] 11.1 修改 addUserMessage 函数
    - 在 `static/script.js` 中找到 `addUserMessage` 函数
    - 在函数末尾添加调用 `messageActionsManager.addActionsToMessage()`
    - 确保新消息和历史消息都能正确添加操作按钮
    - _Requirements: 1.1_
  
  - [ ] 11.2 处理历史消息加载
    - 确保从 localStorage 加载的历史消息也能添加操作按钮
    - 在消息加载完成后批量添加操作按钮
    - _Requirements: 1.1_
  
  - [ ] 11.3 编写集成测试
    - 测试新消息添加操作按钮
    - 测试历史消息加载操作按钮
    - 测试与现有消息发送流程的集成
    - _Requirements: 1.1, 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 12. 性能优化
  - [ ] 12.1 实现事件委托
    - 在 messagesContainer 上使用事件委托监听按钮点击
    - 移除单个按钮的事件监听器绑定
    - 通过 event.target 判断点击的按钮类型
    - _Requirements: 11.1_
  
  - [ ] 12.2 优化 DOM 操作
    - 使用 DocumentFragment 批量创建按钮元素
    - 减少 reflow 和 repaint 次数
    - _Requirements: 11.2_
  
  - [ ] 12.3 添加内存管理
    - 确保退出编辑模式时清理事件监听器
    - 避免闭包导致的内存泄漏
    - _Requirements: 11.3_
  
  - [ ] 12.4 编写性能测试
    - 测试大量消息（1000+）时的性能
    - 测试操作响应时间（应 < 100ms）
    - 测试内存使用情况
    - _Requirements: 11.1, 11.2, 11.3, 11.5_

- [ ] 14. 错误处理和边界条件
  - [ ] 14.1 添加全面的错误处理
    - 在所有关键操作中添加 try-catch 块
    - 记录错误到控制台，提供调试信息
    - 确保错误不会破坏聊天界面
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [ ] 14.2 处理边界条件
    - 处理空字符串和纯空白字符
    - 处理超长文本（10,000+ 字符）
    - 处理特殊字符和 emoji
    - _Requirements: 4.3, 7.5_
  
  - [ ] 14.3 编写错误处理测试
    - 测试各种错误场景的恢复
    - 测试边界条件处理
    - 测试错误日志记录
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 15. 浏览器兼容性测试
  - [ ] 15.1 桌面浏览器测试
    - 在 Chrome、Firefox、Safari、Edge 上测试所有功能
    - 验证剪贴板 API 和降级方案
    - 验证 CSS 样式在不同浏览器中的一致性
    - _Requirements: 12.6_
  - [ ] 16.1 完整功能验证
    - 验证所有需求的验收标准都已满足
    - 进行端到端的用户场景测试
    - 确认无遗留 bug 或问题
  
  - [ ] 16.2 代码审查和清理
    - 移除调试代码和 console.log 语句
    - 确保代码符合项目编码规范
    - 添加必要的代码注释
  
  - [ ] 16.3 更新文档
    - 更新 README 或相关文档，说明新功能
    - 添加使用说明和截图（如需要）
    - 记录已知限制和未来改进方向

- [ ] 17. Final Checkpoint - 确保所有测试通过
  - 运行所有单元测试和集成测试
  - 确认测试覆盖率达到 80% 以上
  - 如有测试失败，修复问题后重新验证
  - 向用户确认功能已完成并可以部署

## Notes

- 任务标记 `*` 的为可选测试任务，可根据项目进度和优先级决定是否执行
- 每个任务都明确引用了相关的需求编号，便于追溯和验证
- Checkpoint 任务用于阶段性验证，确保增量开发的质量
- 所有实现使用原生 JavaScript，无需引入额外框架或库
- 代码应遵循项目现有的编码风格和命名约定
- 优先保证核心功能（复制、编辑）的稳定性，然后再优化性能和可访问性
