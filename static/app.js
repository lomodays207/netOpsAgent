// 全局状态
let currentSessionId = null;
let isWaitingForResponse = false;
let currentAssistantMessage = null;

// DOM 元素
const form = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const messagesContainer = document.getElementById('messages-container');
const useLLMCheckbox = document.getElementById('use-llm');
const verboseCheckbox = document.getElementById('verbose');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('🤖 AI 网络访问关系诊断助手已加载');

    // 恢复会话（如果存在）
    restoreSession();

    // 自动调整文本框高度
    userInput.addEventListener('input', autoResizeTextarea);

    // 表单提交
    form.addEventListener('submit', handleSubmit);

    // 回车发送（Shift+Enter 换行）
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.requestSubmit();
        }
    });

    // 添加"新对话"按钮
    addNewChatButton();

    // 停止按钮
    stopBtn.addEventListener('click', stopGeneration);
});

// 恢复会话
async function restoreSession() {
    // 首先检查 URL 参数中是否有 session_id
    const urlParams = new URLSearchParams(window.location.search);
    const urlSessionId = urlParams.get('session_id');

    if (urlSessionId) {
        // 从 URL 加载会话
        console.log('📥 从 URL 加载会话:', urlSessionId);
        await loadSessionFromServer(urlSessionId);
        // 清除 URL 参数（可选，保持 URL 干净）
        window.history.replaceState({}, document.title, '/');
        return;
    }

    // 否则尝试从 localStorage 恢复
    const savedSessionId = localStorage.getItem('currentSessionId');
    const savedMessages = localStorage.getItem('chatMessages');

    if (savedSessionId && savedMessages) {
        currentSessionId = savedSessionId;

        try {
            const messages = JSON.parse(savedMessages);
            messages.forEach(msg => {
                if (msg.role === 'user') {
                    addUserMessage(msg.content, false); // false = 不保存到 localStorage
                } else if (msg.role === 'assistant') {
                    addAssistantMessage(msg.content, false);
                }
            });

            console.log('✅ 会话已恢复:', currentSessionId);
            addSystemMessage(`会话已恢复 (ID: ${currentSessionId.substring(0, 20)}...)`);
        } catch (e) {
            console.error('恢复会话失败:', e);
            clearSession();
        }
    }
}

// 从服务器加载会话
async function loadSessionFromServer(sessionId) {
    try {
        // 获取会话信息以确定类型
        const sessionsResponse = await fetch('/api/v1/sessions');
        const sessions = await sessionsResponse.json();
        const sessionInfo = sessions.find(s => s.session_id === sessionId);

        // 获取会话消息
        const response = await fetch(`/api/v1/sessions/${sessionId}/messages`);
        if (!response.ok) {
            throw new Error('会话不存在或已过期');
        }

        const messages = await response.json();

        // 设置当前会话ID
        currentSessionId = sessionId;
        saveSession();

        // 判断会话类型并保存
        // 如果任务描述包含 general_chat 或者是通用聊天消息，标记为通用聊天
        const isGeneralChat = sessionInfo &&
            (sessionInfo.task_description.includes('general_chat') ||
                !sessionInfo.task_description.includes('诊断'));

        if (isGeneralChat) {
            localStorage.setItem('sessionType', 'general');
            console.log('✅ 会话类型: 通用聊天');
        } else {
            localStorage.setItem('sessionType', 'diagnostic');
            console.log('✅ 会话类型: 诊断');
        }

        // 显示所有历史消息
        messages.forEach(msg => {
            if (msg.role === 'user') {
                addUserMessage(msg.content, false);
            } else if (msg.role === 'assistant') {
                // 检查是否有 metadata（工具调用、报告等）
                let metadata = null;
                if (msg.metadata) {
                    try {
                        metadata = typeof msg.metadata === 'string' ? JSON.parse(msg.metadata) : msg.metadata;
                    } catch (e) {
                        console.warn('Failed to parse metadata:', e);
                    }
                }

                if (metadata && metadata.tool_call) {
                    // 渲染工具调用卡片
                    const toolCall = metadata.tool_call;
                    const assistantMsg = createAssistantMessage();
                    const toolCard = createToolCallCardFromHistory(toolCall);
                    appendToAssistantMessage(toolCard, assistantMsg);
                } else if (metadata && metadata.report) {
                    // 渲染最终报告
                    const assistantMsg = createAssistantMessage();
                    const reportEl = createFinalReport(metadata.report);
                    appendToAssistantMessage(reportEl, assistantMsg);
                } else {
                    // 普通消息
                    addAssistantMessage(msg.content, false);
                }
            }
        });

        console.log('✅ 会话已从服务器加载:', sessionId);
        addSystemMessage(`会话已加载，可以继续对话 (ID: ${sessionId.substring(0, 20)}...)`);
    } catch (error) {
        console.error('加载会话失败:', error);
        addSystemMessage(`❌ 加载会话失败: ${error.message}`);
    }
}

// 保存会话到 localStorage
function saveSession() {
    if (currentSessionId) {
        localStorage.setItem('currentSessionId', currentSessionId);
    }
}

// 保存消息到 localStorage
function saveMessage(role, content) {
    const savedMessages = localStorage.getItem('chatMessages');
    let messages = savedMessages ? JSON.parse(savedMessages) : [];

    messages.push({ role, content, timestamp: new Date().toISOString() });

    // 限制保存的消息数量（最多100条）
    if (messages.length > 100) {
        messages = messages.slice(-100);
    }

    localStorage.setItem('chatMessages', JSON.stringify(messages));
}

// 清除会话
function clearSession() {
    currentSessionId = null;
    localStorage.removeItem('currentSessionId');
    localStorage.removeItem('chatMessages');
    localStorage.removeItem('sessionType');  // 清除会话类型
    messagesContainer.innerHTML = '';
    console.log('🗑️ 会话已清除');
}

// 添加"新对话"按钮
function addNewChatButton() {
    const header = document.querySelector('header');
    const newChatBtn = document.createElement('button');
    newChatBtn.textContent = '🆕 新对话';
    newChatBtn.className = 'new-chat-btn';
    newChatBtn.style.cssText = `
        position: absolute;
        right: 20px;
        top: 50%;
        transform: translateY(-50%);
        padding: 8px 16px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.3s ease;
    `;
    newChatBtn.addEventListener('click', () => {
        if (confirm('确定要开始新对话吗？当前对话将被清除。')) {
            clearSession();
            addSystemMessage('已开始新对话');
        }
    });
    header.style.position = 'relative';
    header.appendChild(newChatBtn);
}

// 添加系统消息
function addSystemMessage(text) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message system-message';
    messageEl.style.cssText = `
        text-align: center;
        color: #666;
        font-size: 12px;
        padding: 8px;
        margin: 8px 0;
        background: #f0f0f0;
        border-radius: 4px;
    `;
    messageEl.textContent = text;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

// 自动调整文本框高度
function autoResizeTextarea() {
    userInput.style.height = 'auto';
    userInput.style.height = userInput.scrollHeight + 'px';
}

// 处理表单提交
async function handleSubmit(e) {
    e.preventDefault();

    const message = userInput.value.trim();
    if (!message || isWaitingForResponse) {
        return;
    }

    // 添加用户消息
    addUserMessage(message);

    // 清空输入框
    userInput.value = '';
    autoResizeTextarea();

    // 禁用输入并显示停止按钮
    setInputEnabled(false);
    toggleStopButton(true);

    // 添加加载指示器
    showTypingIndicator();

    try {
        // 改进的诊断请求判断逻辑
        // 使用更精确的模式匹配，避免误判
        const hasIP = /\d+\.\d+\.\d+\.\d+/.test(message);
        // 只要包含明确的诊断关键词（不仅是IP），也认为是诊断请求
        // 移除了"问题"、"故障"等通用词，保留更具体的网络术语
        // 移除了"问题"、"故障"等通用词，保留更具体的网络排查触发词
        // 关键：将 "端口" 限制为与某些操作或状态词连用，避免解释性问题误触发
        const hasDiagnosticKeywords = /(不通|无法访问|连接失败|排查|诊断|故障)/.test(message);
        // 如果包含 ping/telnet/traceroute 且伴随特定意向，或者直接包含 IP 地址（hasIP）
        const hasSpecificToolCmd = /(ping|traceroute|telnet)\s+\d+/.test(message.toLowerCase());

        const looksLikeNewDiagnosis = hasIP || hasDiagnosticKeywords || hasSpecificToolCmd;

        // 获取当前会话类型
        const sessionType = localStorage.getItem('sessionType');

        // 路由决策
        if (currentSessionId && sessionType === 'general' && !hasIP) {
            // 通用聊天会话，且没有IP地址 → 继续通用聊天（即使用户说了"不通"等词，在通用聊天里也优先保持聊天）
            console.log('📝 继续通用聊天会话');
            await generalChat(message);
        } else if (currentSessionId && !looksLikeNewDiagnosis) {
            // 有会话ID，但不像新诊断
            const isGeneralChatSession = sessionType === 'general';

            if (isGeneralChatSession) {
                // 通用聊天会话，使用 generalChat 继续
                console.log('📝 通用聊天模式');
                await generalChat(message);
            } else {
                // 诊断会话，使用 continueChat 回答问题
                console.log('🔧 继续诊断会话');
                await continueChat(message);
            }
        } else if (looksLikeNewDiagnosis) {
            // 明确的诊断请求
            console.log('🔧 检测到诊断请求');

            if (currentSessionId) {
                console.log('🔧 在现有会话中开始新诊断');
                // clearSession(); // 不再清除会话
            }
            await startNewChat(message, currentSessionId);
        } else if (!currentSessionId && !looksLikeNewDiagnosis) {
            // 没有会话ID，也不像诊断 → 默认通用聊天
            console.log('📝 新的通用聊天');
            await generalChat(message);
        } else {
            // 没有会话ID，是诊断请求
            console.log('🔧 新的诊断会话');
            await startNewChat(message);
        }
    } catch (error) {
        console.error('诊断失败:', error);
        addAssistantMessage(`抱歉，诊断过程中出错了：${error.message}`);
    } finally {
        // 只有当流完全结束或被中断后，才恢复 UI
        // 注意：如果是 processStream，它内部会等待循环结束
        if (!isWaitingForResponse) {
            hideTypingIndicator();
            setInputEnabled(true);
            toggleStopButton(false);
        }
    }
}

// 停止生成
async function stopGeneration() {
    if (!isWaitingForResponse) return;

    try {
        console.log('🛑 用户点击停止生成');
        stopBtn.disabled = true;

        // 立即标记为停止，防止后续 UI 更新
        isWaitingForResponse = false;

        // 立即触发 UI 恢复，不等待后端响应
        hideTypingIndicator();
        setInputEnabled(true);
        toggleStopButton(false);
        stopBtn.disabled = false;

        // 手工添加一条提示
        addSystemMessage('⛔ 已发送停止指令...');

        // 发送停止请求到后端（后台运行，不阻塞 UI 恢复）
        if (currentSessionId) {
            fetch(`/api/v1/sessions/${currentSessionId}/stop`, {
                method: 'POST'
            }).catch(err => console.error('发送停止指令失败:', err));
        }

    } catch (error) {
        console.error('停止生成操作失败:', error);
        stopBtn.disabled = false;
    }
}

function toggleStopButton(show) {
    if (show) {
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'flex';
    } else {
        sendBtn.style.display = 'flex';
        stopBtn.style.display = 'none';
    }
}

// 开始新诊断
async function startNewChat(description, sessionId = null) {
    const useLLM = useLLMCheckbox.checked;
    const verbose = verboseCheckbox.checked;

    console.log('🚀 开始新诊断...');

    const body = {
        description,
        use_llm: useLLM,
        verbose
    };

    if (sessionId) {
        body.session_id = sessionId;
    }

    const response = await fetch('/api/v1/diagnose/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    await processStream(response);
}

// 继续诊断（用户回答问题后）
async function continueChat(answer) {
    console.log('💬 继续诊断，会话ID:', currentSessionId);

    const response = await fetch('/api/v1/chat/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: currentSessionId,
            answer
        })
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    await processStream(response);
}

// 通用聊天（非诊断模式）
async function generalChat(message) {
    console.log('💬 通用聊天模式', currentSessionId ? `(继续会话: ${currentSessionId})` : '(新会话)');

    const requestBody = { message };

    // 如果有当前会话ID，包含在请求中以继续会话
    if (currentSessionId) {
        requestBody.session_id = currentSessionId;
    }

    isWaitingForResponse = true;
    try {
        const response = await fetch('/api/v1/chat/general', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // 更新会话ID（如果是新会话）
        if (!currentSessionId && data.session_id) {
            currentSessionId = data.session_id;
            saveSession();
            localStorage.setItem('sessionType', 'general'); // 明确标记为通用聊天
            console.log('新会话ID:', currentSessionId, '类型: general');
        }


        // 使用打字机效果显示响应
        await addAssistantMessageWithTyping(data.response);
    } finally {
        isWaitingForResponse = false;
    }
}

// 处理 SSE 流
async function processStream(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    isWaitingForResponse = true;

    while (true) {
        // 检查是否已被外部标记为停止
        if (!isWaitingForResponse) {
            console.log('🛑 流读取循环被中断');
            try {
                await reader.cancel();
            } catch (e) { }
            break;
        }

        const { done, value } = await reader.read();

        if (done) {
            console.log('✅ 流结束');
            break;
        }

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const event = JSON.parse(line.substring(6));
                    handleEvent(event);
                } catch (e) {
                    console.error('解析事件失败:', e, line);
                }
            } else if (line.startsWith(':')) {
                // 心跳或注释，忽略
            }
        }
    }

    isWaitingForResponse = false;
    toggleStopButton(false);
}

// 处理事件
function handleEvent(event) {
    console.log('📨 收到事件:', event.type, event);

    switch (event.type) {
        case 'start':
            handleStartEvent(event);
            break;
        case 'tool_start':
            handleToolStartEvent(event);
            break;
        case 'tool_result':
            handleToolResultEvent(event);
            break;
        case 'ask_user':
            handleAskUserEvent(event);
            break;
        case 'user_answer':
            // 用户回答已经显示过了，忽略
            break;
        case 'complete':
            handleCompleteEvent(event);
            break;
        case 'error':
            handleErrorEvent(event);
            break;
    }
}

// 处理诊断开始事件
function handleStartEvent(event) {
    currentSessionId = event.data.task_id;
    console.log('会话ID:', currentSessionId);

    currentSessionId = event.data.task_id;
    console.log('会话ID:', currentSessionId);

    // 保存会话ID到 localStorage
    saveSession();

    // 如果已经是诊断会话，不需要重复标记
    // 但如果是从通用会话转换来的，需要更新标记
    localStorage.setItem('sessionType', 'diagnostic');

    // 创建助手消息容器
    if (!currentAssistantMessage) {
        currentAssistantMessage = createAssistantMessage();
    }

    // 添加任务信息
    const taskInfo = `开始诊断任务：${currentSessionId}\n` +
        `源主机：${event.data.source}\n` +
        `目标主机：${event.data.target}\n` +
        `协议：${event.data.protocol}\n` +
        `端口：${event.data.port || 'N/A'}`;

    addTextToAssistantMessage(taskInfo);
}

// 处理工具调用开始事件
function handleToolStartEvent(event) {
    if (!currentAssistantMessage) {
        currentAssistantMessage = createAssistantMessage();
    }

    // 创建工具调用卡片
    const toolCard = createToolCallCard(event.step, event.tool, event.arguments);
    appendToAssistantMessage(toolCard);
}

// 处理工具调用结果事件
function handleToolResultEvent(event) {
    updateToolCallResult(event.step, event.tool, event.result);
}

// 处理询问用户事件
function handleAskUserEvent(event) {
    // 结束当前助手消息
    currentAssistantMessage = null;

    // 创建问题消息
    const questionEl = createQuestionMessage(event.question);
    messagesContainer.appendChild(questionEl);
    scrollToBottom();

    console.log('❓ LLM 询问用户:', event.question);
}

// 处理诊断完成事件
function handleCompleteEvent(event) {
    // 结束当前助手消息
    currentAssistantMessage = null;

    // 创建最终报告
    const reportEl = createFinalReport(event.report);
    const assistantMsg = createAssistantMessage();
    appendToAssistantMessage(reportEl, assistantMsg);

    // 不重置会话，保持对话记忆
    // currentSessionId 保持不变，下次输入会继续对话

    console.log('🎉 诊断完成！会话保持活跃，可以继续对话');
}

// 处理错误事件
function handleErrorEvent(event) {
    currentAssistantMessage = null;
    addAssistantMessage(`❌ 错误：${event.message}`);
    currentSessionId = null;
}

// UI 辅助函数

function addUserMessage(text, shouldSave = true) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message user-message';
    messageEl.innerHTML = `
        <div class="message-avatar">👤</div>
        <div class="message-content">
            <div class="message-text">${escapeHtml(text)}</div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();

    // 保存到 localStorage
    if (shouldSave) {
        saveMessage('user', text);
    }
}

function addAssistantMessage(text, shouldSave = true) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant-message';
    messageEl.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-text">${escapeHtml(text)}</div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();

    // 保存到 localStorage
    if (shouldSave) {
        saveMessage('assistant', text);
    }

    return messageEl;
}

// 添加带打字机效果的助手消息
async function addAssistantMessageWithTyping(text, shouldSave = true) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant-message';
    messageEl.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-text"></div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);

    const textEl = messageEl.querySelector('.message-text');

    // 打字机效果：逐字显示
    const chars = text.split('');
    let currentText = '';

    for (let i = 0; i < chars.length; i++) {
        // 检查是否已停止
        if (!isWaitingForResponse) break;

        currentText += chars[i];
        textEl.textContent = currentText;
        scrollToBottom();

        // 控制打字速度
        const delay = chars[i].match(/[\u4e00-\u9fa5]/) ? 30 : 20;
        await new Promise(resolve => setTimeout(resolve, delay));
    }

    // 保存到 localStorage
    if (shouldSave) {
        saveMessage('assistant', text);
    }

    return messageEl;
}

function createAssistantMessage() {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant-message';
    messageEl.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-text"></div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
    return messageEl;
}

function addTextToAssistantMessage(text) {
    if (!currentAssistantMessage) {
        currentAssistantMessage = createAssistantMessage();
    }

    const textEl = currentAssistantMessage.querySelector('.message-text');
    const p = document.createElement('p');
    p.style.whiteSpace = 'pre-wrap';
    p.textContent = text;
    textEl.appendChild(p);
    scrollToBottom();
}

function appendToAssistantMessage(element, msgElement = null) {
    const message = msgElement || currentAssistantMessage;
    if (!message) {
        return;
    }

    const textEl = message.querySelector('.message-text');
    textEl.appendChild(element);
    scrollToBottom();
}

function showTypingIndicator() {
    const template = document.getElementById('loading-template');
    const indicator = template.content.cloneNode(true);
    const indicatorEl = indicator.querySelector('.message');
    indicatorEl.id = 'typing-indicator';
    messagesContainer.appendChild(indicator);
    scrollToBottom();
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function createToolCallCard(step, toolName, args) {
    const template = document.getElementById('tool-call-template');
    const card = template.content.cloneNode(true);

    const toolCard = card.querySelector('.tool-call-card');
    toolCard.id = `tool-${step}`;

    card.querySelector('.tool-name').textContent = formatToolName(toolName);
    card.querySelector('.tool-status').textContent = '执行中...';
    card.querySelector('.tool-status').className = 'tool-status running';

    const argsText = JSON.stringify(args, null, 2);
    card.querySelector('.tool-arguments').textContent = `参数：\n${argsText}`;

    return card;
}

/**
 * 从历史记录创建工具调用卡片（已完成的状态）
 */
function createToolCallCardFromHistory(toolCall) {
    const template = document.getElementById('tool-call-template');
    const card = template.content.cloneNode(true);
    const result = toolCall.result || {};

    card.querySelector('.tool-name').textContent = formatToolName(toolCall.name);

    const statusEl = card.querySelector('.tool-status');
    if (result.success) {
        statusEl.textContent = '完成';
        statusEl.className = 'tool-status success';
    } else {
        statusEl.textContent = '失败';
        statusEl.className = 'tool-status error';
    }

    const argsText = JSON.stringify(toolCall.arguments, null, 2);
    card.querySelector('.tool-arguments').textContent = `参数：\n${argsText}`;

    const resultEl = card.querySelector('.tool-result');
    let output = '';

    if (result.stdout) output += `标准输出：\n${result.stdout}\n`;
    if (result.stderr) output += `错误输出：\n${result.stderr}\n`;
    if (result.error) output += `执行错误：\n${result.error}\n`;
    if (!output) output = result.data || '执行完成';

    resultEl.textContent = output;
    resultEl.className = `tool-result ${result.success ? 'success' : 'error'}`;

    return card;
}

function updateToolCallResult(step, toolName, result) {
    const toolCard = document.getElementById(`tool-${step}`);
    if (!toolCard) {
        console.warn('找不到工具卡片:', step);
        return;
    }

    const statusEl = toolCard.querySelector('.tool-status');
    const resultEl = toolCard.querySelector('.tool-result');

    if (result.success) {
        statusEl.textContent = '完成';
        statusEl.className = 'tool-status success';

        let output = '';
        if (result.stdout) output += `标准输出：\n${result.stdout}\n`;
        if (result.stderr) output += `错误输出：\n${result.stderr}\n`;
        if (!output) output = result.data || '执行成功';

        resultEl.textContent = output;
        resultEl.className = 'tool-result success';
    } else {
        statusEl.textContent = '失败';
        statusEl.className = 'tool-status error';

        let errorOutput = '';
        if (result.stderr) errorOutput += `错误输出：\n${result.stderr}\n`;
        if (result.stdout) errorOutput += `标准输出：\n${result.stdout}\n`;
        if (result.error) errorOutput += `执行错误：\n${result.error}\n`;
        if (!errorOutput) errorOutput = '执行失败';

        resultEl.textContent = errorOutput;
        resultEl.className = 'tool-result error';
    }

    scrollToBottom();
}

function createQuestionMessage(question) {
    const template = document.getElementById('question-template');
    const msg = template.content.cloneNode(true);
    msg.querySelector('.question-text').textContent = question;
    return msg;
}

function createFinalReport(report) {
    const template = document.getElementById('report-template');
    const reportEl = template.content.cloneNode(true);

    reportEl.querySelector('.root-cause').textContent = report.root_cause;
    reportEl.querySelector('.confidence').textContent = `${report.confidence.toFixed(1)}%`;

    const suggestionsUl = reportEl.querySelector('.suggestions');
    if (report.suggestions && report.suggestions.length > 0) {
        report.suggestions.forEach(suggestion => {
            const li = document.createElement('li');
            li.textContent = suggestion;
            suggestionsUl.appendChild(li);
        });
    } else {
        suggestionsUl.innerHTML = '<li>暂无建议</li>';
    }

    return reportEl;
}

function setInputEnabled(enabled) {
    userInput.disabled = !enabled;
    sendBtn.disabled = !enabled;

    if (enabled) {
        userInput.focus();
    }
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatToolName(toolName) {
    const nameMap = {
        'execute_command': '🖥️ 执行命令',
        'query_cmdb': '📊 查询 CMDB',
        'ask_user': '❓ 询问用户'
    };
    return nameMap[toolName] || toolName;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
