// 全局状态
let currentSessionId = null;
let isWaitingForResponse = false;
let currentAssistantMessage = null;
let currentStreamingMessage = null;
let currentStreamingText = '';
let currentToolRunId = null;

const QUICK_PROMPTS = [
    {
        category: '网络故障诊断',
        items: [
            {
                title: '源到目标端口不通',
                description: '排查网络路径、防火墙、ACL 和服务监听',
                template: '请帮我分析为什么 10.0.1.10 到 10.0.2.20 的 80 端口不通。'
            },
            {
                title: '主机间网络不通',
                description: '检查连通性、路由和安全策略',
                template: '请帮我分析为什么 10.0.1.10 无法访问 10.0.2.20。'
            },
            {
                title: '服务监听异常',
                description: '确认端口监听、进程状态和主机防火墙',
                template: '请帮我检查 XX 主机上的 XX 服务是否正常监听目标端口。'
            }
        ]
    },
    {
        category: '访问关系查询',
        items: [
            {
                title: '查询系统访问关系清单',
                description: '查看某系统的上下游访问关系',
                template: '请查询 XX 系统的访问关系清单，包括源系统、目标系统、协议、端口和访问方向。'
            },
            {
                title: '查询主机访问关系',
                description: '按 IP 查看与其他资产的访问关系',
                template: '请查询 IP 为 10.0.1.10 的主机有哪些访问关系。'
            },
            {
                title: '查询两个系统是否已开通',
                description: '确认系统间是否已有访问放通记录',
                template: '请帮我查询 XX 系统到 XX 系统之间是否已经开通访问关系。'
            }
        ]
    },
    {
        category: '提单知识问答',
        items: [
            {
                title: '访问关系如何开通提单',
                description: '查看权限、流程和必填信息',
                template: '访问关系如何进行开通提单？需要哪些权限、审批节点和必填信息？'
            },
            {
                title: '提单需要准备什么',
                description: '提前准备源目地址、端口和用途说明',
                template: '开通访问关系前需要准备哪些信息，例如源 IP、目标 IP、端口、协议和用途说明？'
            },
            {
                title: '谁有权限提单',
                description: '确认申请角色和审批边界',
                template: '哪些角色有权限发起访问关系开通提单？审批边界是什么？'
            }
        ]
    }
];

// DOM 元素
const form = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const messagesContainer = document.getElementById('messages-container');
const useLLMCheckbox = document.getElementById('use-llm');
const useRAGCheckbox = document.getElementById('use-rag');
const verboseCheckbox = document.getElementById('verbose');
const welcomeMessageTemplate = document.getElementById('welcome-message-template');
const quickPromptsTemplate = document.getElementById('quick-prompts-template');
const quickPromptCardTemplate = document.getElementById('quick-prompt-card-template');

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🤖 AI 网络访问关系智能助手已加载');

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

    const restored = await restoreSession();
    if (!restored) {
        renderInitialState();
    }
});

// 恢复会话
async function restoreSession() {
    // 首先检查 URL 参数中是否有 session_id
    const urlParams = new URLSearchParams(window.location.search);
    const urlSessionId = urlParams.get('session_id');

    if (urlSessionId) {
        // 从 URL 加载会话
        console.log('📥 从 URL 加载会话:', urlSessionId);
        const restored = await loadSessionFromServer(urlSessionId);
        // 清除 URL 参数（可选，保持 URL 干净）
        window.history.replaceState({}, document.title, '/');
        return restored;
    }

    // 否则尝试从 localStorage 恢复
    const savedSessionId = localStorage.getItem('currentSessionId');
    const savedMessages = localStorage.getItem('chatMessages');

    if (!savedSessionId || !savedMessages) {
        return false;
    }

    currentSessionId = savedSessionId;
    messagesContainer.innerHTML = '';

    try {
        const messages = JSON.parse(savedMessages);
        if (!Array.isArray(messages) || messages.length === 0) {
            clearSession();
            return false;
        }

        messages.forEach(msg => {
            if (msg.role === 'user') {
                addUserMessage(msg.content, false); // false = 不保存到 localStorage
            } else if (msg.role === 'assistant') {
                addAssistantMessage(msg.content, false);
            }
        });

        console.log('✅ 会话已恢复:', currentSessionId);
        addSystemMessage(`会话已恢复 (ID: ${currentSessionId.substring(0, 20)}...)`);
        return true;
    } catch (e) {
        console.error('恢复会话失败:', e);
        clearSession();
        return false;
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

        messagesContainer.innerHTML = '';

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
        return true;
    } catch (error) {
        console.error('加载会话失败:', error);
        clearSession();
        return false;
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
    currentAssistantMessage = null;
    currentToolRunId = null;
    isWaitingForResponse = false;
    resetStreamingAssistantMessage();
    localStorage.removeItem('currentSessionId');
    localStorage.removeItem('chatMessages');
    localStorage.removeItem('sessionType');  // 清除会话类型
    messagesContainer.innerHTML = '';
    console.log('🗑️ 会话已清除');
}

function renderInitialState() {
    messagesContainer.innerHTML = '';
    messagesContainer.appendChild(createWelcomeMessage());
    showQuickPrompts();
    scrollToBottom();
}

function createWelcomeMessage() {
    return welcomeMessageTemplate.content.cloneNode(true).firstElementChild;
}

function renderQuickPrompts() {
    if (!Array.isArray(QUICK_PROMPTS) || QUICK_PROMPTS.length === 0) {
        return null;
    }

    const fragment = quickPromptsTemplate.content.cloneNode(true);
    const section = fragment.querySelector('#quick-prompts-section');
    const groupsContainer = fragment.querySelector('.quick-prompt-groups');

    QUICK_PROMPTS.forEach(group => {
        const items = Array.isArray(group.items) ? group.items : [];
        const validItems = items.filter(item => item.template);
        if (validItems.length === 0) {
            return;
        }

        const groupEl = document.createElement('section');
        groupEl.className = 'quick-prompt-group';

        const titleEl = document.createElement('h3');
        titleEl.className = 'quick-prompt-group-title';
        titleEl.textContent = group.category;

        const cardsEl = document.createElement('div');
        cardsEl.className = 'quick-prompt-card-list';

        validItems.forEach(item => {
            const cardFragment = quickPromptCardTemplate.content.cloneNode(true);
            const card = cardFragment.querySelector('.quick-prompt-card');
            card.querySelector('.quick-prompt-card-title').textContent = item.title;
            card.querySelector('.quick-prompt-card-description').textContent = item.description;
            card.addEventListener('click', () => fillPromptTemplate(item.template));
            cardsEl.appendChild(card);
        });

        groupEl.appendChild(titleEl);
        groupEl.appendChild(cardsEl);
        groupsContainer.appendChild(groupEl);
    });

    return groupsContainer.childElementCount > 0 ? section : null;
}

function showQuickPrompts() {
    hideQuickPrompts();
    const section = renderQuickPrompts();
    if (section) {
        messagesContainer.appendChild(section);
    }
}

function hideQuickPrompts() {
    const section = document.getElementById('quick-prompts-section');
    if (section) {
        section.remove();
    }
}

function fillPromptTemplate(template) {
    userInput.value = template;
    autoResizeTextarea();
    userInput.focus();
}

function startNewChat() {
    clearSession();
    userInput.value = '';
    autoResizeTextarea();
    setInputEnabled(true);
    toggleStopButton(false);
    stopBtn.disabled = false;
    renderInitialState();
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
            startNewChat();
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

    hideQuickPrompts();
    addUserMessage(message);
    userInput.value = '';
    autoResizeTextarea();

    setInputEnabled(false);
    toggleStopButton(true);
    showTypingIndicator();

    try {
        await submitMessage(message);
    } catch (error) {
        console.error('Failed to submit message:', error);
        addAssistantMessage(`Request failed: ${error.message}`);
    } finally {
        if (!isWaitingForResponse) {
            hideTypingIndicator();
            setInputEnabled(true);
            toggleStopButton(false);
        }
    }
}

async function submitMessage(message) {
    const useLLM = useLLMCheckbox.checked;
    const verbose = verboseCheckbox.checked;
    const useRAG = useRAGCheckbox ? useRAGCheckbox.checked : true;

    const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            session_id: currentSessionId,
            use_llm: useLLM,
            verbose,
            use_rag: useRAG
        })
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    await processStream(response);
}

// ????
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
    console.log('Received event:', event.type, event);

    switch (event.type) {
        case 'start':
            handleStartEvent(event);
            break;
        case 'rag_start':
            handleRagStartEvent(event);
            break;
        case 'rag_result':
            handleRagResultEvent(event);
            break;
        case 'rag_error':
            handleRagErrorEvent(event);
            break;
        case 'tool_start':
            handleToolStartEvent(event);
            break;
        case 'tool_result':
            handleToolResultEvent(event);
            break;
        case 'content':
            handleContentEvent(event);
            break;
        case 'ask_user':
            handleAskUserEvent(event);
            break;
        case 'user_answer':
            break;
        case 'complete':
            handleCompleteEvent(event);
            break;
        case 'error':
            handleErrorEvent(event);
            break;
    }
}

// ????????
function handleStartEvent(event) {
    if (!event.data) {
        if (event.session_id) {
            currentSessionId = event.session_id;
            saveSession();
            localStorage.setItem('sessionType', 'general');
            currentAssistantMessage = null;
            currentToolRunId = `run-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        }
        return;
    }

    currentSessionId = event.data.task_id;
    saveSession();
    localStorage.setItem('sessionType', 'diagnostic');
    resetStreamingAssistantMessage();
    currentAssistantMessage = createAssistantMessage();
    currentToolRunId = `run-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const taskInfo = `Task ID: ${currentSessionId}\n` +
        `Source: ${event.data.source}\n` +
        `Target: ${event.data.target}\n` +
        `Protocol: ${event.data.protocol}\n` +
        `Port: ${event.data.port || 'N/A'}`;

    addTextToAssistantMessage(taskInfo);
}

// ??????????
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
    console.log('🔧 工具执行结果:', event);
    // 优先使用 result 中的 execution_time，如果没有则使用事件级别的
    const executionTime = event.result?.execution_time ?? event.execution_time;
    console.log('⏱️ 执行时间:', executionTime);
    updateToolCallResult(event.step, event.tool, event.result, executionTime);
}

// 处理询问用户事件
function handleAskUserEvent(event) {
    resetStreamingAssistantMessage();
    currentAssistantMessage = null;

    const questionEl = createQuestionMessage(event.question);
    messagesContainer.appendChild(questionEl);
    scrollToBottom();

    console.log('LLM question:', event.question);
}

// ????????
function handleCompleteEvent(event) {
    if (!event.report) {
        if (currentStreamingText) {
            saveMessage('assistant', currentStreamingText);
        }
        resetStreamingAssistantMessage();
        currentAssistantMessage = null;

        if (event.session_id) {
            currentSessionId = event.session_id;
            saveSession();
        }

        if (event.rag_used) {
            console.log('RAG applied');
        }
        return;
    }

    currentAssistantMessage = null;

    const reportEl = createFinalReport(event.report);
    const assistantMsg = createAssistantMessage();
    appendToAssistantMessage(reportEl, assistantMsg);
}

function handleRagStartEvent(event) {
    addSystemMessage('[RAG] ' + (event.message || 'Searching knowledge base...'));
}

function handleRagResultEvent(event) {
    if (event.count > 0) {
        const sources = event.sources ? event.sources.join(', ') : 'knowledge base';
        addSystemMessage(`[RAG] Found ${event.count} result(s) from: ${sources}`);
    } else {
        addSystemMessage('[RAG] No relevant knowledge found.');
    }
}

function handleRagErrorEvent(event) {
    addSystemMessage('[RAG] ' + (event.message || 'Knowledge retrieval failed.'));
}

function handleContentEvent(event) {
    if (!currentStreamingMessage) {
        currentStreamingMessage = createAssistantMessage();
        hideTypingIndicator();
    }

    currentStreamingText += event.text || '';
    const textEl = currentStreamingMessage.querySelector('.message-text');
    textEl.innerHTML = marked.parse(currentStreamingText);
    scrollToBottom();
}

function resetStreamingAssistantMessage() {
    currentStreamingMessage = null;
    currentStreamingText = '';
}

// ??????
function handleErrorEvent(event) {
    resetStreamingAssistantMessage();
    currentAssistantMessage = null;
    addAssistantMessage(`Error: ${event.message}`);
    currentSessionId = null;
}

// UI ????

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
            <div class="message-text">${marked.parse(text)}</div>
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
        textEl.innerHTML = marked.parse(currentText);
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

    if (!currentToolRunId) {
        currentToolRunId = `run-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
    const uniqueId = `tool-${currentToolRunId}-${step}`;

    const toolCard = card.querySelector('.tool-call-card');
    toolCard.id = uniqueId;
    toolCard.classList.add('status-running');

    // 设置工具名称
    card.querySelector('.tool-name').textContent = formatToolName(toolName);

    // 设置状态图标（运行中）
    const statusIcon = card.querySelector('.tool-status-icon');
    statusIcon.textContent = '⏳';
    statusIcon.className = 'tool-status-icon running';

    // 执行时间初始为空
    card.querySelector('.tool-time').textContent = '';

    // 设置参数
    const argsText = JSON.stringify(args, null, 2);
    card.querySelector('.tool-arguments').textContent = argsText;

    // 结果初始为空
    card.querySelector('.tool-result').textContent = '等待执行结果...';

    // 添加点击事件处理折叠/展开
    const header = card.querySelector('.tool-header');
    header.addEventListener('click', () => {
        const actualCard = document.getElementById(uniqueId);
        if (actualCard) {
            actualCard.classList.toggle('collapsed');
        }
    });

    return card;
}

function attachAccessRelationExport(toolCard, toolName, result) {
    const actionsEl = toolCard.querySelector('.tool-actions');
    if (!actionsEl) {
        return;
    }

    actionsEl.innerHTML = '';
    actionsEl.hidden = true;

    if (toolName !== 'query_access_relations' || !result || !result.success) {
        return;
    }

    const items = Array.isArray(result.items) ? result.items : [];
    if (items.length === 0) {
        return;
    }

    const exportBtn = document.createElement('button');
    exportBtn.type = 'button';
    exportBtn.className = 'tool-export-btn';
    exportBtn.textContent = '导出 CSV';
    exportBtn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        downloadAccessRelationsCsv(items);
    });

    actionsEl.appendChild(exportBtn);
    actionsEl.hidden = false;
}

/**
 * 从历史记录创建工具调用卡片（已完成的状态）
 */
function createToolCallCardFromHistory(toolCall) {
    const template = document.getElementById('tool-call-template');
    const card = template.content.cloneNode(true);
    const result = toolCall.result || {};

    const toolCard = card.querySelector('.tool-call-card');
    const toolNameEl = card.querySelector('.tool-name');
    const statusIcon = card.querySelector('.tool-status-icon');
    const timeEl = card.querySelector('.tool-time');

    // 设置工具名称
    toolNameEl.textContent = formatToolName(toolCall.name);

    // 设置执行时间
    if (toolCall.execution_time !== undefined && toolCall.execution_time !== null) {
        timeEl.textContent = `${toolCall.execution_time}ms`;
    }

    // 设置状态和图标
    if (result.success) {
        toolCard.classList.add('status-success');
        toolCard.classList.remove('collapsed'); // 历史记录默认展开，用户可以选择折叠
        statusIcon.textContent = '✓';
        statusIcon.className = 'tool-status-icon success';
    } else {
        toolCard.classList.add('status-error');
        toolCard.classList.remove('collapsed'); // 历史记录默认展开
        statusIcon.textContent = '✗';
        statusIcon.className = 'tool-status-icon error';
    }

    // 设置参数
    const argsText = JSON.stringify(toolCall.arguments, null, 2);
    card.querySelector('.tool-arguments').textContent = argsText;

    // 设置结果
    const resultEl = card.querySelector('.tool-result');
    let output = '';

    if (result.stdout) output += `标准输出：\n${result.stdout}\n`;
    if (result.stderr) output += `错误输出：\n${result.stderr}\n`;
    if (result.error) output += `执行错误：\n${result.error}\n`;
    if (!output) output = result.data || '执行完成';

    resultEl.textContent = output;
    resultEl.className = `tool-result ${result.success ? 'success' : 'error'}`;
    attachAccessRelationExport(toolCard, toolCall.name, result);

    // 添加点击事件处理折叠/展开
    const header = card.querySelector('.tool-header');
    // 生成唯一ID（使用时间戳和随机数）
    const uniqueId = `tool-history-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    toolCard.id = uniqueId;

    header.addEventListener('click', () => {
        const actualCard = document.getElementById(uniqueId);
        if (actualCard) {
            actualCard.classList.toggle('collapsed');
        }
    });

    return card;
}

function updateToolCallResult(step, toolName, result, executionTime) {
    console.log('📝 更新工具卡片 - step:', step, 'executionTime:', executionTime);

    const toolCard = document.getElementById(`tool-${currentToolRunId}-${step}`);
    if (!toolCard) {
        console.warn('找不到工具卡片:', `tool-${currentToolRunId}-${step}`);
        return;
    }

    const statusIcon = toolCard.querySelector('.tool-status-icon');
    const resultEl = toolCard.querySelector('.tool-result');
    const timeEl = toolCard.querySelector('.tool-time');

    // 更新执行时间
    if (executionTime !== undefined && executionTime !== null) {
        timeEl.textContent = `${executionTime}ms`;
        console.log('✅ 已更新执行时间:', timeEl.textContent);
    } else {
        console.warn('⚠️ 执行时间为空:', executionTime);
    }

    // 根据结果更新状态
    if (result.success) {
        // 成功状态：绿色
        toolCard.classList.remove('status-running', 'status-error');
        toolCard.classList.add('status-success');

        statusIcon.textContent = '✓';
        statusIcon.className = 'tool-status-icon success';

        let output = '';
        if (result.stdout) output += `标准输出：\n${result.stdout}\n`;
        if (result.stderr) output += `错误输出：\n${result.stderr}\n`;
        if (!output) output = result.data || '执行成功';

        resultEl.textContent = output;
        resultEl.className = 'tool-result success';
    } else {
        // 失败状态：红色
        toolCard.classList.remove('status-running', 'status-success');
        toolCard.classList.add('status-error');

        statusIcon.textContent = '✗';
        statusIcon.className = 'tool-status-icon error';

        let errorOutput = '';
        if (result.stderr) errorOutput += `错误输出：\n${result.stderr}\n`;
        if (result.stdout) errorOutput += `标准输出：\n${result.stdout}\n`;
        if (result.error) errorOutput += `执行错误：\n${result.error}\n`;
        if (!errorOutput) errorOutput = '执行失败';

        resultEl.textContent = errorOutput;
        resultEl.className = 'tool-result error';
    }

    attachAccessRelationExport(toolCard, toolName, result);
    scrollToBottom();
}

function downloadAccessRelationsCsv(items) {
    if (!Array.isArray(items) || items.length === 0) {
        return;
    }

    const columns = [
        { key: 'src_system', title: '源系统' },
        { key: 'src_system_name', title: '源系统名称' },
        { key: 'src_deploy_unit', title: '源部署单元' },
        { key: 'src_ip', title: '源IP' },
        { key: 'dst_system', title: '目标系统' },
        { key: 'dst_deploy_unit', title: '目标部署单元' },
        { key: 'dst_ip', title: '目标IP' },
        { key: 'protocol', title: '协议' },
        { key: 'port', title: '端口' }
    ];
    const headerRow = columns.map((column) => escapeCsvValue(column.title)).join(',');
    const dataRows = items.map((item) => columns
        .map((column) => escapeCsvValue(item?.[column.key] ?? ''))
        .join(','));
    const csvContent = `\uFEFF${[headerRow, ...dataRows].join('\r\n')}`;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = `access-relations-${formatExportTimestamp(new Date())}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();

    setTimeout(() => URL.revokeObjectURL(url), 0);
}

function escapeCsvValue(value) {
    const normalized = String(value ?? '')
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n');
    const escaped = normalized.replace(/"/g, '""');

    if (/[",\n]/.test(normalized)) {
        return `"${escaped}"`;
    }

    return escaped;
}

function formatExportTimestamp(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `${year}${month}${day}-${hours}${minutes}${seconds}`;
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

    reportEl.querySelector('.root-cause').innerHTML = marked.parse(report.root_cause);
    reportEl.querySelector('.confidence').textContent = `${report.confidence.toFixed(1)}%`;

    const suggestionsUl = reportEl.querySelector('.suggestions');
    if (report.suggestions && report.suggestions.length > 0) {
        report.suggestions.forEach(suggestion => {
            const li = document.createElement('li');
            li.innerHTML = marked.parseInline(suggestion); // 使用 parseInline 避免包裹 <p>
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
