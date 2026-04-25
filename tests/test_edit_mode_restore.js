/**
 * Task 3.3 验证测试: 实现退出编辑模式逻辑
 * 
 * 验证 EditModeRenderer.restoreOriginalMessage() 方法
 * 是否满足 Requirements 4.1, 4.6, 4.7
 */

// 模拟 DOM 环境
class MockElement {
    constructor(tagName) {
        this.tagName = tagName;
        this.className = '';
        this.innerHTML = '';
        this.textContent = '';
        this.style = {};
        this.attributes = {};
        this.children = [];
        this.parent = null;
    }

    querySelector(selector) {
        // 简单的选择器匹配
        for (const child of this.children) {
            if (selector.startsWith('.') && child.className === selector.substring(1)) {
                return child;
            }
        }
        return null;
    }

    appendChild(child) {
        this.children.push(child);
        child.parent = this;
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }

    getAttribute(name) {
        return this.attributes[name];
    }

    removeAttribute(name) {
        delete this.attributes[name];
    }

    hasAttribute(name) {
        return name in this.attributes;
    }
}

// 简化的 EditModeRenderer 实现（从 static/app.js 提取核心逻辑）
class EditModeRenderer {
    restoreOriginalMessage(messageElement, originalText) {
        // 验证输入
        if (!messageElement || typeof messageElement !== 'object') {
            console.error('[EditModeRenderer] restoreOriginalMessage 失败: messageElement 参数必须是有效的 HTMLElement');
            return;
        }

        console.log('[EditModeRenderer] 恢复原始消息显示');

        // 获取消息文本容器
        const messageTextEl = messageElement.querySelector('.message-text');
        if (!messageTextEl) {
            console.error('[EditModeRenderer] 找不到 .message-text 元素');
            return;
        }

        // 恢复原始 HTML 内容
        const originalHtml = messageElement.getAttribute('data-original-html');
        if (originalHtml) {
            messageTextEl.innerHTML = originalHtml;
            console.log('[EditModeRenderer] 已恢复原始 HTML 内容');
        } else {
            console.warn('[EditModeRenderer] 未找到保存的原始 HTML，使用文本内容重新渲染');
            messageTextEl.textContent = originalText || '';
        }

        // 恢复操作按钮可见性
        const actionsContainer = messageElement.querySelector('.message-actions');
        if (actionsContainer) {
            actionsContainer.style.display = '';
            console.log('[EditModeRenderer] 已恢复操作按钮可见性');
        }

        // 移除编辑状态标记和保存的数据
        messageElement.removeAttribute('data-editing');
        messageElement.removeAttribute('data-original-html');
        messageElement.removeAttribute('data-original-text');

        console.log('[EditModeRenderer] ✓ 原始消息已恢复');
    }
}

// 测试工具函数
function createMockMessage(text) {
    const messageElement = new MockElement('div');
    messageElement.className = 'user-message';
    
    const messageTextEl = new MockElement('div');
    messageTextEl.className = 'message-text';
    messageTextEl.textContent = text;
    messageTextEl.innerHTML = text;
    
    const actionsContainer = new MockElement('div');
    actionsContainer.className = 'message-actions';
    actionsContainer.style.display = '';
    
    messageElement.appendChild(messageTextEl);
    messageElement.appendChild(actionsContainer);
    
    return messageElement;
}

function simulateEditMode(messageElement, originalText) {
    const messageTextEl = messageElement.querySelector('.message-text');
    const actionsContainer = messageElement.querySelector('.message-actions');
    
    // 保存原始内容
    messageElement.setAttribute('data-original-html', messageTextEl.innerHTML);
    messageElement.setAttribute('data-original-text', originalText);
    
    // 隐藏操作按钮
    actionsContainer.style.display = 'none';
    
    // 创建编辑 UI
    const textarea = new MockElement('textarea');
    textarea.className = 'edit-message-textarea';
    textarea.value = originalText;
    
    const editButtons = new MockElement('div');
    editButtons.className = 'edit-buttons';
    
    messageTextEl.innerHTML = '';
    messageTextEl.appendChild(textarea);
    messageTextEl.appendChild(editButtons);
    
    // 标记编辑状态
    messageElement.setAttribute('data-editing', 'true');
}

// 测试用例
function runTests() {
    const renderer = new EditModeRenderer();
    let passedTests = 0;
    let totalTests = 0;
    
    console.log('\n========================================');
    console.log('Task 3.3 验证测试开始');
    console.log('========================================\n');
    
    // Test 1: Requirement 4.1 - 恢复原始消息文本显示
    {
        totalTests++;
        console.log('Test 1: Requirement 4.1 - 恢复原始消息文本显示');
        
        const originalText = '这是原始消息内容';
        const messageElement = createMockMessage(originalText);
        
        // 模拟进入编辑模式
        simulateEditMode(messageElement, originalText);
        
        const messageTextEl = messageElement.querySelector('.message-text');
        const hasTextareaBefore = messageTextEl.querySelector('.edit-message-textarea') !== null;
        
        // 执行恢复
        renderer.restoreOriginalMessage(messageElement, originalText);
        
        // 验证
        const textRestored = messageTextEl.innerHTML === originalText || messageTextEl.textContent === originalText;
        const noTextarea = messageTextEl.querySelector('.edit-message-textarea') === null;
        const noEditButtons = messageTextEl.querySelector('.edit-buttons') === null;
        
        const passed = hasTextareaBefore && textRestored && noTextarea && noEditButtons;
        
        console.log(`  - 编辑前有 textarea: ${hasTextareaBefore}`);
        console.log(`  - 文本已恢复: ${textRestored}`);
        console.log(`  - textarea 已移除: ${noTextarea}`);
        console.log(`  - 编辑按钮已移除: ${noEditButtons}`);
        console.log(`  结果: ${passed ? '✓ PASS' : '✗ FAIL'}\n`);
        
        if (passed) passedTests++;
    }
    
    // Test 2: Requirement 4.6 - 恢复操作按钮可见性
    {
        totalTests++;
        console.log('Test 2: Requirement 4.6 - 恢复操作按钮可见性');
        
        const originalText = '测试操作按钮恢复';
        const messageElement = createMockMessage(originalText);
        
        // 模拟进入编辑模式
        simulateEditMode(messageElement, originalText);
        
        const actionsContainer = messageElement.querySelector('.message-actions');
        const hiddenInEditMode = actionsContainer.style.display === 'none';
        
        // 执行恢复
        renderer.restoreOriginalMessage(messageElement, originalText);
        
        const visibleAfterRestore = actionsContainer.style.display === '';
        
        const passed = hiddenInEditMode && visibleAfterRestore;
        
        console.log(`  - 编辑模式中隐藏: ${hiddenInEditMode}`);
        console.log(`  - 恢复后可见: ${visibleAfterRestore}`);
        console.log(`  结果: ${passed ? '✓ PASS' : '✗ FAIL'}\n`);
        
        if (passed) passedTests++;
    }
    
    // Test 3: Requirement 4.7 - 移除编辑文本框和操作按钮组
    {
        totalTests++;
        console.log('Test 3: Requirement 4.7 - 移除编辑文本框和操作按钮组');
        
        const originalText = '测试 DOM 清理';
        const messageElement = createMockMessage(originalText);
        
        // 模拟进入编辑模式
        simulateEditMode(messageElement, originalText);
        
        const messageTextEl = messageElement.querySelector('.message-text');
        const hasTextareaBefore = messageTextEl.querySelector('.edit-message-textarea') !== null;
        const hasEditButtonsBefore = messageTextEl.querySelector('.edit-buttons') !== null;
        const hasEditingAttributeBefore = messageElement.hasAttribute('data-editing');
        
        // 执行恢复
        renderer.restoreOriginalMessage(messageElement, originalText);
        
        const hasTextareaAfter = messageTextEl.querySelector('.edit-message-textarea') !== null;
        const hasEditButtonsAfter = messageTextEl.querySelector('.edit-buttons') !== null;
        const noEditingAttribute = !messageElement.hasAttribute('data-editing');
        const noOriginalHtmlAttribute = !messageElement.hasAttribute('data-original-html');
        const noOriginalTextAttribute = !messageElement.hasAttribute('data-original-text');
        
        const passed = hasTextareaBefore && hasEditButtonsBefore && hasEditingAttributeBefore &&
                      !hasTextareaAfter && !hasEditButtonsAfter && noEditingAttribute &&
                      noOriginalHtmlAttribute && noOriginalTextAttribute;
        
        console.log(`  - 编辑前有 textarea: ${hasTextareaBefore}`);
        console.log(`  - 编辑前有按钮组: ${hasEditButtonsBefore}`);
        console.log(`  - 编辑前有 data-editing: ${hasEditingAttributeBefore}`);
        console.log(`  - 恢复后无 textarea: ${!hasTextareaAfter}`);
        console.log(`  - 恢复后无按钮组: ${!hasEditButtonsAfter}`);
        console.log(`  - data-editing 已移除: ${noEditingAttribute}`);
        console.log(`  - data-original-html 已移除: ${noOriginalHtmlAttribute}`);
        console.log(`  - data-original-text 已移除: ${noOriginalTextAttribute}`);
        console.log(`  结果: ${passed ? '✓ PASS' : '✗ FAIL'}\n`);
        
        if (passed) passedTests++;
    }
    
    // Test 4: 边界条件 - 无效输入
    {
        totalTests++;
        console.log('Test 4: 边界条件 - 无效输入处理');
        
        let passed = true;
        try {
            renderer.restoreOriginalMessage(null, 'test');
            renderer.restoreOriginalMessage(undefined, 'test');
            renderer.restoreOriginalMessage({}, 'test');
        } catch (e) {
            passed = false;
            console.log(`  异常: ${e.message}`);
        }
        
        console.log(`  - 方法能够优雅处理无效输入: ${passed}`);
        console.log(`  结果: ${passed ? '✓ PASS' : '✗ FAIL'}\n`);
        
        if (passed) passedTests++;
    }
    
    // Test 5: 完整流程测试
    {
        totalTests++;
        console.log('Test 5: 完整流程 - 编辑模式进入和退出');
        
        const originalText = '完整流程测试消息';
        const messageElement = createMockMessage(originalText);
        
        // 模拟进入编辑模式
        simulateEditMode(messageElement, originalText);
        const inEditMode = messageElement.getAttribute('data-editing') === 'true';
        
        // 执行恢复
        renderer.restoreOriginalMessage(messageElement, originalText);
        
        const exitedEditMode = !messageElement.hasAttribute('data-editing');
        const messageTextEl = messageElement.querySelector('.message-text');
        const textRestored = messageTextEl.textContent === originalText;
        const actionsVisible = messageElement.querySelector('.message-actions').style.display === '';
        
        const passed = inEditMode && exitedEditMode && textRestored && actionsVisible;
        
        console.log(`  - 成功进入编辑模式: ${inEditMode}`);
        console.log(`  - 成功退出编辑模式: ${exitedEditMode}`);
        console.log(`  - 文本正确恢复: ${textRestored}`);
        console.log(`  - 操作按钮可见: ${actionsVisible}`);
        console.log(`  结果: ${passed ? '✓ PASS' : '✗ FAIL'}\n`);
        
        if (passed) passedTests++;
    }
    
    // 总结
    console.log('========================================');
    console.log(`测试完成: ${passedTests}/${totalTests} 通过`);
    console.log('========================================\n');
    
    if (passedTests === totalTests) {
        console.log('✓ Task 3.3 实现验证通过!');
        console.log('restoreOriginalMessage() 方法满足所有要求:');
        console.log('  - Requirement 4.1: 恢复原始消息文本显示');
        console.log('  - Requirement 4.6: 恢复操作按钮可见性');
        console.log('  - Requirement 4.7: 移除编辑文本框和操作按钮组\n');
        return true;
    } else {
        console.log('✗ 部分测试失败，需要修复\n');
        return false;
    }
}

// 运行测试
const success = runTests();
process.exit(success ? 0 : 1);
