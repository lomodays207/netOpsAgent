// 全局状态
let currentSessionId = null;
let isWaitingForResponse = false;
let currentAssistantMessage = null;
let currentStreamingMessage = null;
let currentStreamingText = '';
let currentToolRunId = null;

/**
 * @typedef {Object} EvidenceSource
 * @property {string} id - 文档唯一标识
 * @property {string} filename - 文件名
 * @property {number} relevance_score - 相关度评分 (0-1)
 * @property {string} preview - 预览文本（前200字符）
 * @property {Object} [metadata] - 元数据（可选）
 * @property {string} [metadata.source] - 来源路径
 * @property {string} [metadata.created_at] - 创建时间
 * @property {number} [metadata.file_size] - 文件大小
 */

/**
 * @typedef {Object} DocumentDetail
 * @property {string} id - 文档唯一标识
 * @property {string} filename - 文件名
 * @property {string} content - 完整内容
 * @property {Object} [metadata] - 元数据
 * @property {string} [metadata.source] - 来源路径
 * @property {string} [metadata.created_at] - 创建时间
 * @property {number} [metadata.file_size] - 文件大小
 */

/**
 * @typedef {Object} ChatMessage
 * @property {string} role - 消息角色 ('user' | 'assistant')
 * @property {string} content - 消息内容
 * @property {string} timestamp - 时间戳
 * @property {EvidenceSource[]} [evidenceSources] - 证据来源列表（可选）
 */

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
    addTraceCenterButton();

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
                addAssistantMessageWithEvidence(msg.content, msg.evidenceSources, false);
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
function saveMessage(role, content, evidenceSources = null) {
    const savedMessages = localStorage.getItem('chatMessages');
    let messages = savedMessages ? JSON.parse(savedMessages) : [];

    const message = { 
        role, 
        content, 
        timestamp: new Date().toISOString()
    };
    
    // 如果有证据来源，添加到消息对象中
    if (evidenceSources && Array.isArray(evidenceSources) && evidenceSources.length > 0) {
        message.evidenceSources = evidenceSources;
    }

    messages.push(message);

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

function addTraceCenterButton() {
    const header = document.querySelector('header');
    const traceBtn = document.createElement('button');
    traceBtn.textContent = '追踪记录';
    traceBtn.className = 'trace-nav-btn';
    traceBtn.addEventListener('click', () => {
        window.location.href = '/static/traces.html';
    });
    header.style.position = 'relative';
    header.appendChild(traceBtn);
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
        case 'evidence_sources':
            handleEvidenceSourcesEvent(event);
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
            // 提取证据来源（如果存在）
            const evidenceSources = currentStreamingMessage?.evidenceSources || null;
            saveMessage('assistant', currentStreamingText, evidenceSources);
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

function handleEvidenceSourcesEvent(event) {
    console.log('📚 收到证据来源事件:', event);
    
    // 确保有证据来源数据
    if (!event.sources || !Array.isArray(event.sources) || event.sources.length === 0) {
        console.warn('证据来源事件没有有效的sources数据');
        return;
    }
    
    // 如果当前没有助手消息，创建一个
    if (!currentStreamingMessage && !currentAssistantMessage) {
        currentStreamingMessage = createAssistantMessage();
    }
    
    // 获取当前消息元素
    const messageEl = currentStreamingMessage || currentAssistantMessage;
    if (!messageEl) {
        console.warn('无法找到当前消息元素来附加证据来源');
        return;
    }
    
    // 渲染证据来源面板
    const evidencePanel = renderEvidenceSourcePanel(event.sources);
    if (evidencePanel) {
        // 将证据面板添加到消息内容中
        const messageContent = messageEl.querySelector('.message-content');
        if (messageContent) {
            messageContent.appendChild(evidencePanel);
            scrollToBottom();
            console.log('✅ 证据来源面板已渲染');
        }
    }
    
    // 将证据来源关联到当前消息对象（用于持久化）
    // 注意：这里我们将证据来源存储在消息元素的数据属性中
    // 在保存消息时需要提取这些数据
    if (messageEl) {
        messageEl.evidenceSources = event.sources;
    }
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

    // 添加操作按钮（复制、编辑）
    messageActionsManager.addActionsToMessage(messageEl, text);

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

/**
 * 添加带证据来源的助手消息（用于历史消息恢复）
 * @param {string} text - 消息文本
 * @param {EvidenceSource[]} evidenceSources - 证据来源列表
 * @param {boolean} shouldSave - 是否保存到localStorage
 * @returns {HTMLElement} 消息元素
 */
function addAssistantMessageWithEvidence(text, evidenceSources, shouldSave = true) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant-message';
    messageEl.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-text">${marked.parse(text)}</div>
        </div>
    `;
    messagesContainer.appendChild(messageEl);
    
    // 如果有证据来源，渲染证据面板
    if (evidenceSources && Array.isArray(evidenceSources) && evidenceSources.length > 0) {
        const evidencePanel = renderEvidenceSourcePanel(evidenceSources);
        if (evidencePanel) {
            const messageContent = messageEl.querySelector('.message-content');
            messageContent.appendChild(evidencePanel);
        }
        // 存储证据来源到元素上（用于后续可能的操作）
        messageEl.evidenceSources = evidenceSources;
    }
    
    scrollToBottom();

    // 保存到 localStorage
    if (shouldSave) {
        saveMessage('assistant', text, evidenceSources);
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

/**
 * 渲染证据来源面板
 * @param {EvidenceSource[]} sources - 证据来源列表
 * @returns {DocumentFragment} 证据来源面板DOM片段
 */
function renderEvidenceSourcePanel(sources) {
    if (!Array.isArray(sources) || sources.length === 0) {
        return null;
    }

    // 按相关度评分从高到低排序
    const sortedSources = [...sources].sort((a, b) => b.relevance_score - a.relevance_score);

    const template = document.getElementById('evidence-sources-template');
    const panel = template.content.cloneNode(true);

    // 设置证据来源数量
    const countEl = panel.querySelector('.evidence-count');
    countEl.textContent = `(${sortedSources.length})`;

    // 渲染证据卡片列表
    const listEl = panel.querySelector('.evidence-list');
    sortedSources.forEach(source => {
        const card = renderEvidenceCard(source);
        listEl.appendChild(card);
    });

    return panel;
}

/**
 * 渲染单个证据卡片
 * @param {EvidenceSource} source - 证据来源对象
 * @returns {DocumentFragment} 证据卡片DOM片段
 */
function renderEvidenceCard(source) {
    const template = document.getElementById('evidence-card-template');
    const card = template.content.cloneNode(true);

    const cardEl = card.querySelector('.evidence-card');
    cardEl.setAttribute('data-doc-id', source.id);

    // 设置文件名
    const filenameEl = card.querySelector('.evidence-filename');
    filenameEl.textContent = source.filename;

    // 设置相关度评分徽章
    const scoreBadgeEl = card.querySelector('.evidence-score-badge');
    const scorePercent = Math.round(source.relevance_score * 100);
    scoreBadgeEl.textContent = `${scorePercent}%`;

    // 根据评分范围设置颜色类
    if (source.relevance_score > 0.7) {
        cardEl.classList.add('score-high');
    } else if (source.relevance_score >= 0.4) {
        cardEl.classList.add('score-medium');
    } else {
        cardEl.classList.add('score-low');
    }

    // 设置相关度评分进度条
    const scoreFillEl = card.querySelector('.evidence-score-fill');
    scoreFillEl.style.width = `${scorePercent}%`;

    // 设置预览文本
    const previewEl = card.querySelector('.evidence-preview');
    previewEl.textContent = source.preview;

    // 添加点击事件
    cardEl.addEventListener('click', () => {
        showDocumentPreview(source.id);
    });

    return card;
}

/**
 * 显示文档预览模态框
 * @param {string} docId - 文档ID
 */
async function showDocumentPreview(docId) {
    // Task 10.2: Log evidence card click
    console.log('[MONITORING] 证据卡片点击, 文档ID:', docId);
    
    const template = document.getElementById('document-preview-modal-template');
    const modal = template.content.cloneNode(true);
    const modalEl = modal.querySelector('.modal-overlay');

    // 添加到页面
    document.body.appendChild(modalEl);

    const closeBtn = modalEl.querySelector('.modal-close-btn');
    const loadingEl = modalEl.querySelector('.modal-loading');
    const contentEl = modalEl.querySelector('.modal-content-text');
    const errorEl = modalEl.querySelector('.modal-error');

    // 关闭按钮事件
    const closeModal = () => {
        modalEl.remove();
    };

    closeBtn.addEventListener('click', closeModal);
    modalEl.addEventListener('click', (e) => {
        if (e.target === modalEl) {
            closeModal();
        }
    });

    // 显示加载指示器
    loadingEl.style.display = 'flex';
    contentEl.style.display = 'none';
    errorEl.style.display = 'none';

    try {
        // Task 10.2: Track document preview load time
        const loadStartTime = performance.now();
        
        // 发送GET请求获取文档内容
        const response = await fetch(`/api/v1/knowledge/document/${docId}`);

        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('文档不存在');
            } else if (response.status === 429) {
                throw new Error('请求过于频繁，请稍后重试');
            } else {
                throw new Error('无法加载文档内容');
            }
        }

        const data = await response.json();

        if (data.status === 'success' && data.data) {
            const doc = data.data;

            // 设置标题
            const titleEl = modalEl.querySelector('.modal-title');
            titleEl.textContent = doc.filename;

            // 设置内容（HTML转义）
            contentEl.textContent = doc.content;

            // 显示内容
            loadingEl.style.display = 'none';
            contentEl.style.display = 'block';
            
            // Task 10.2: Log document preview load time
            const loadTime = performance.now() - loadStartTime;
            console.log(`[MONITORING] 文档预览加载时间: ${loadTime.toFixed(2)}ms, 文档ID: ${docId}`);
        } else {
            throw new Error(data.message || '无法加载文档内容');
        }
    } catch (error) {
        console.error('加载文档失败:', error);

        // 显示错误信息
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.textContent = error.message || '请求超时，请重试';
    }
}

// ============================================================================
// EditModeRenderer - 编辑模式渲染类
// ============================================================================

/**
 * EditModeRenderer 类
 * 负责渲染和管理编辑模式的 UI 状态
 * 
 * 功能：
 * - 创建可编辑文本框
 * - 创建编辑操作按钮组（取消、发送）
 * - 管理编辑模式和普通模式之间的 DOM 切换
 * - 处理文本框的自动聚焦和尺寸调整
 * 
 * Requirements: 3.2, 3.5, 3.6
 */
class EditModeRenderer {
    /**
     * 创建可编辑文本框
     * @param {string} text - 初始文本内容
     * @returns {HTMLTextAreaElement} 文本框元素
     * 
     * 功能：
     * - 创建 textarea 元素并设置初始文本
     * - 自动调整高度以适应内容
     * - 设置适当的样式类和属性
     * 
     * Requirements: 3.2, 3.5, 3.6
     */
    createEditableTextarea(text) {
        // 验证输入
        if (typeof text !== 'string') {
            console.error('[EditModeRenderer] createEditableTextarea 失败: text 参数必须是字符串');
            text = '';
        }

        console.log('[EditModeRenderer] 创建可编辑文本框');

        // 创建 textarea 元素
        const textarea = document.createElement('textarea');
        textarea.className = 'edit-message-textarea';
        textarea.value = text;
        
        // 设置可访问性属性
        textarea.setAttribute('aria-label', '编辑消息内容');
        
        // 自动调整高度
        // 计算所需行数（基于文本长度和换行符）
        const lineCount = text.split('\n').length;
        const estimatedRows = Math.max(3, Math.min(lineCount + 1, 10)); // 最少3行，最多10行
        textarea.rows = estimatedRows;

        // 添加输入事件监听器，实时调整高度
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        });

        console.log('[EditModeRenderer] ✓ 文本框创建成功，初始行数:', estimatedRows);

        return textarea;
    }

    /**
     * 创建编辑操作按钮组（取消、发送）
     * @returns {HTMLElement} 按钮组容器
     * 
     * 功能：
     * - 创建包含取消和发送按钮的容器
     * - 设置按钮文本、样式和可访问性属性
     * - 按钮事件处理由调用者绑定
     * 
     * Requirements: 3.2, 3.5, 3.6
     */
    createEditButtons() {
        console.log('[EditModeRenderer] 创建编辑按钮组');

        // 创建按钮组容器
        const buttonsContainer = document.createElement('div');
        buttonsContainer.className = 'edit-buttons';

        // 创建取消按钮
        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'edit-cancel-btn';
        cancelButton.textContent = '取消';
        cancelButton.setAttribute('aria-label', '取消编辑');

        // 创建发送按钮
        const sendButton = document.createElement('button');
        sendButton.type = 'button';
        sendButton.className = 'edit-send-btn';
        sendButton.textContent = '发送';
        sendButton.setAttribute('aria-label', '发送编辑后的消息');

        // 添加按钮到容器
        buttonsContainer.appendChild(cancelButton);
        buttonsContainer.appendChild(sendButton);

        console.log('[EditModeRenderer] ✓ 按钮组创建成功');

        return buttonsContainer;
    }

    /**
     * 渲染编辑模式 UI
     * @param {HTMLElement} messageElement - 消息元素
     * @param {string} originalText - 原始文本
     * @returns {Object} 包含 textarea 和按钮的对象 { textarea, cancelButton, sendButton }
     * 
     * 功能：
     * - 隐藏原始消息文本和操作按钮
     * - 显示编辑文本框和操作按钮组
     * - 设置 data-editing="true" 标记
     * - 文本框获得焦点且光标位于文本末尾
     * 
     * Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
     */
    renderEditMode(messageElement, originalText) {
        // 验证输入
        if (!messageElement || !(messageElement instanceof HTMLElement)) {
            console.error('[EditModeRenderer] renderEditMode 失败: messageElement 参数必须是有效的 HTMLElement');
            return null;
        }

        if (typeof originalText !== 'string') {
            console.error('[EditModeRenderer] renderEditMode 失败: originalText 参数必须是字符串');
            return null;
        }

        console.log('[EditModeRenderer] 渲染编辑模式');

        // 获取消息文本容器
        const messageTextEl = messageElement.querySelector('.message-text');
        if (!messageTextEl) {
            console.error('[EditModeRenderer] 找不到 .message-text 元素');
            return null;
        }

        // 隐藏操作按钮
        const actionsContainer = messageElement.querySelector('.message-actions');
        if (actionsContainer) {
            actionsContainer.style.display = 'none';
            console.log('[EditModeRenderer] 已隐藏操作按钮');
        }

        // 保存原始 HTML 内容（用于恢复）
        messageElement.setAttribute('data-original-html', messageTextEl.innerHTML);
        messageElement.setAttribute('data-original-text', originalText);

        // 创建编辑文本框
        const textarea = this.createEditableTextarea(originalText);

        // 创建编辑按钮组
        const buttonsContainer = this.createEditButtons();
        const cancelButton = buttonsContainer.querySelector('.edit-cancel-btn');
        const sendButton = buttonsContainer.querySelector('.edit-send-btn');

        // 清空消息文本容器并添加编辑 UI
        messageTextEl.innerHTML = '';
        messageTextEl.appendChild(textarea);
        messageTextEl.appendChild(buttonsContainer);

        // 标记编辑状态
        messageElement.setAttribute('data-editing', 'true');

        // 聚焦文本框并将光标移到末尾
        // 使用 setTimeout 确保 DOM 更新完成后再聚焦
        setTimeout(() => {
            textarea.focus();
            // 将光标移到文本末尾
            const textLength = textarea.value.length;
            textarea.setSelectionRange(textLength, textLength);
            console.log('[EditModeRenderer] ✓ 文本框已聚焦，光标位于末尾');
        }, 0);

        console.log('[EditModeRenderer] ✓ 编辑模式渲染完成');

        // 返回关键元素供调用者使用
        return {
            textarea,
            cancelButton,
            sendButton
        };
    }

    /**
     * 恢复原始消息显示
     * @param {HTMLElement} messageElement - 消息元素
     * @param {string} originalText - 原始文本
     * 
     * 功能：
     * - 移除编辑文本框和操作按钮组
     * - 恢复原始消息文本显示
     * - 恢复操作按钮可见性
     * - 移除 data-editing 标记
     * 
     * Requirements: 4.1, 4.6, 4.7
     */
    restoreOriginalMessage(messageElement, originalText) {
        // 验证输入
        if (!messageElement || !(messageElement instanceof HTMLElement)) {
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
            // 如果没有保存的 HTML，使用文本内容重新渲染
            console.warn('[EditModeRenderer] 未找到保存的原始 HTML，使用文本内容重新渲染');
            messageTextEl.innerHTML = marked.parse(originalText || '');
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

// ============================================================================
// ClipboardHandler - 剪贴板操作处理类
// ============================================================================

// ============================================================================
// MessageActionsManager - 消息操作管理器类
// ============================================================================

/**
 * MessageActionsManager 类
 * 管理用户消息的操作按钮（复制、编辑）的创建、事件绑定和状态管理
 * 
 * 功能：
 * - 为用户消息添加操作按钮
 * - 创建操作按钮容器（复制、编辑）
 * - 处理复制和编辑操作
 * - 管理编辑模式的状态切换
 * 
 * Requirements: 1.1, 1.3, 1.4, 9.1, 9.2
 */
class MessageActionsManager {
    constructor() {
        // 初始化依赖的处理器
        this.clipboardHandler = new ClipboardHandler();
        this.editModeRenderer = new EditModeRenderer();
        
        // 设置事件委托
        this.setupEventDelegation();
        
        console.log('[MessageActionsManager] 初始化完成');
    }

    /**
     * 设置事件委托
     * 在 messagesContainer 上监听所有按钮点击事件，而不是为每个按钮单独绑定
     * 
     * 功能：
     * - 使用事件委托优化性能
     * - 通过 event.target 判断点击的按钮类型
     * - 自动处理动态添加的按钮
     * 
     * Requirements: 11.1
     */
    setupEventDelegation() {
        if (!messagesContainer) {
            console.error('[MessageActionsManager] messagesContainer 未定义，无法设置事件委托');
            return;
        }

        messagesContainer.addEventListener('click', (event) => {
            const target = event.target;
            
            // 检查是否点击了复制按钮
            if (target.classList.contains('message-copy-btn')) {
                const messageElement = target.closest('.user-message');
                if (messageElement) {
                    const messageText = messageElement.getAttribute('data-message-text');
                    if (messageText) {
                        this.handleCopy(messageText, target);
                    }
                }
            }
            
            // 检查是否点击了编辑按钮
            else if (target.classList.contains('message-edit-btn')) {
                const messageElement = target.closest('.user-message');
                if (messageElement) {
                    const messageText = messageElement.getAttribute('data-message-text');
                    if (messageText) {
                        this.handleEdit(messageElement, messageText);
                    }
                }
            }
        });

        console.log('[MessageActionsManager] ✓ 事件委托已设置');
    }

    /**
     * 创建操作按钮容器
     * @returns {HTMLElement} 包含复制和编辑按钮的容器元素
     * 
     * 功能：
     * - 创建包含复制和编辑按钮的容器
     * - 设置按钮图标、标题和可访问性属性
     * - 按钮事件处理由 addActionsToMessage 方法绑定
     * 
     * Requirements: 1.1, 1.3, 1.4, 9.1, 9.2
     */
    createActionsContainer() {
        console.log('[MessageActionsManager] 创建操作按钮容器');

        // 创建容器元素
        const container = document.createElement('div');
        container.className = 'message-actions';

        // 创建复制按钮
        const copyButton = document.createElement('button');
        copyButton.type = 'button';
        copyButton.className = 'message-action-btn message-copy-btn';
        copyButton.textContent = '📋';
        copyButton.title = '复制消息';
        copyButton.setAttribute('aria-label', '复制消息');

        // 创建编辑按钮
        const editButton = document.createElement('button');
        editButton.type = 'button';
        editButton.className = 'message-action-btn message-edit-btn';
        editButton.textContent = '✏️';
        editButton.title = '编辑消息';
        editButton.setAttribute('aria-label', '编辑消息');

        // 添加按钮到容器
        container.appendChild(copyButton);
        container.appendChild(editButton);

        console.log('[MessageActionsManager] ✓ 操作按钮容器创建成功');

        return container;
    }

    /**
     * 为用户消息添加操作按钮
     * @param {HTMLElement} messageElement - 用户消息的 DOM 元素
     * @param {string} messageText - 消息的原始文本内容
     * 
     * 功能：
     * - 检查是否已存在操作按钮容器，防止重复添加
     * - 将操作按钮容器添加到消息内容区域
     * - 使用事件委托处理按钮点击（不再单独绑定事件）
     * - 将消息文本存储为 data 属性供事件委托使用
     * 
     * Requirements: 1.1, 1.2, 1.5, 11.1
     */
    addActionsToMessage(messageElement, messageText) {
        // 验证输入
        if (!messageElement || !(messageElement instanceof HTMLElement)) {
            console.error('[MessageActionsManager] addActionsToMessage 失败: messageElement 参数必须是有效的 HTMLElement');
            return;
        }

        if (typeof messageText !== 'string') {
            console.error('[MessageActionsManager] addActionsToMessage 失败: messageText 参数必须是字符串');
            return;
        }

        console.log('[MessageActionsManager] 为消息添加操作按钮');

        // 检查是否已存在操作按钮容器（防止重复添加）
        const existingActions = messageElement.querySelector('.message-actions');
        if (existingActions) {
            console.log('[MessageActionsManager] 操作按钮已存在，跳过添加');
            return;
        }

        // 获取消息内容容器
        const messageContent = messageElement.querySelector('.message-content');
        if (!messageContent) {
            console.error('[MessageActionsManager] 找不到 .message-content 元素');
            return;
        }

        // 将消息文本存储为 data 属性，供事件委托使用
        messageElement.setAttribute('data-message-text', messageText);

        // 创建操作按钮容器（不再绑定单独的事件监听器）
        const actionsContainer = this.createActionsContainer();

        // 将操作按钮容器添加到消息内容区域
        messageContent.appendChild(actionsContainer);

        console.log('[MessageActionsManager] ✓ 操作按钮已添加到消息（使用事件委托）');
    }

    /**
     * 处理复制操作
     * @param {string} text - 要复制的文本
     * @param {HTMLElement} button - 复制按钮元素
     * 
     * 功能：
     * - 调用 ClipboardHandler 执行复制操作
     * - 显示视觉反馈（成功或失败）
     * - 全面的错误处理和日志记录
     * 
     * Requirements: 2.1, 2.3, 2.4, 2.5, 2.6, 12.1, 12.5
     */
    async handleCopy(text, button) {
        console.log('[MessageActionsManager] 处理复制操作');

        try {
            // 验证输入
            if (typeof text !== 'string') {
                throw new Error('text 参数必须是字符串');
            }
            
            if (!button || !(button instanceof HTMLElement)) {
                throw new Error('button 参数必须是有效的 HTMLElement');
            }

            // 执行复制操作
            const success = await this.clipboardHandler.copyToClipboard(text);

            // 设置反馈类型
            if (success) {
                button.setAttribute('data-feedback', 'success');
            } else {
                button.setAttribute('data-feedback', 'error');
            }

            // 显示视觉反馈
            this.clipboardHandler.showCopyFeedback(button, 2000);

            console.log('[MessageActionsManager] ✓ 复制操作完成，结果:', success ? '成功' : '失败');
        } catch (error) {
            console.error('[MessageActionsManager] 复制操作异常:', error);
            
            // 确保按钮存在再设置反馈
            if (button && button instanceof HTMLElement) {
                button.setAttribute('data-feedback', 'error');
                this.clipboardHandler.showCopyFeedback(button, 2000);
            }
        }
    }

    /**
     * 处理编辑操作
     * @param {HTMLElement} messageElement - 消息元素
     * @param {string} originalText - 原始消息文本
     * 
     * 功能：
     * - 调用 EditModeRenderer 进入编辑模式
     * - 确保同时只有一条消息处于编辑模式
     * - 绑定取消和发送按钮的事件处理器
     * - 全面的错误处理和恢复机制
     * 
     * Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 6.4, 6.5, 12.2, 12.3, 12.4
     */
    handleEdit(messageElement, originalText) {
        console.log('[MessageActionsManager] 处理编辑操作');

        try {
            // 验证输入
            if (!messageElement || !(messageElement instanceof HTMLElement)) {
                throw new Error('messageElement 参数必须是有效的 HTMLElement');
            }
            
            if (typeof originalText !== 'string') {
                throw new Error('originalText 参数必须是字符串');
            }

            // 确保同时只有一条消息处于编辑模式
            // 查找当前正在编辑的消息
            const currentlyEditing = document.querySelector('[data-editing="true"]');
            if (currentlyEditing && currentlyEditing !== messageElement) {
                console.log('[MessageActionsManager] 退出其他消息的编辑模式');
                const originalTextAttr = currentlyEditing.getAttribute('data-original-text');
                this.editModeRenderer.restoreOriginalMessage(currentlyEditing, originalTextAttr || '');
            }

            // 进入编辑模式
            const editElements = this.editModeRenderer.renderEditMode(messageElement, originalText);
            
            if (!editElements) {
                throw new Error('进入编辑模式失败：renderEditMode 返回 null');
            }

            const { textarea, cancelButton, sendButton } = editElements;

            // 验证返回的元素
            if (!textarea || !cancelButton || !sendButton) {
                throw new Error('编辑模式元素不完整');
            }

            // 绑定取消按钮事件
            cancelButton.addEventListener('click', () => {
                this.exitEditMode(messageElement, originalText);
            });

            // 绑定发送按钮事件
            sendButton.addEventListener('click', () => {
                const newText = textarea.value;
                this.submitEditedMessage(messageElement, newText);
            });

            // 绑定键盘事件
            // Escape 键退出编辑模式
            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    this.exitEditMode(messageElement, originalText);
                }
                // Ctrl+Enter (或 Cmd+Enter) 提交编辑
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    const newText = textarea.value;
                    this.submitEditedMessage(messageElement, newText);
                }
            });

            console.log('[MessageActionsManager] ✓ 编辑模式已激活');
        } catch (error) {
            console.error('[MessageActionsManager] 编辑操作失败:', error);
            
            // 尝试恢复原始消息显示
            try {
                if (messageElement && originalText) {
                    this.editModeRenderer.restoreOriginalMessage(messageElement, originalText);
                }
            } catch (restoreError) {
                console.error('[MessageActionsManager] 恢复原始消息失败:', restoreError);
            }
        }
    }

    /**
     * 退出编辑模式
     * @param {HTMLElement} messageElement - 消息元素
     * @param {string} originalText - 原始消息文本
     * 
     * 功能：
     * - 调用 EditModeRenderer 恢复原始消息显示
     * - 移除编辑状态标记
     * - 错误处理和日志记录
     * 
     * Requirements: 4.1, 4.6, 4.7, 12.3, 12.4
     */
    exitEditMode(messageElement, originalText) {
        console.log('[MessageActionsManager] 退出编辑模式');
        
        try {
            // 验证输入
            if (!messageElement || !(messageElement instanceof HTMLElement)) {
                throw new Error('messageElement 参数必须是有效的 HTMLElement');
            }
            
            this.editModeRenderer.restoreOriginalMessage(messageElement, originalText);
            console.log('[MessageActionsManager] ✓ 已退出编辑模式');
        } catch (error) {
            console.error('[MessageActionsManager] 退出编辑模式失败:', error);
        }
    }

    /**
     * 提交编辑后的消息
     * @param {HTMLElement} messageElement - 消息元素
     * @param {string} newText - 编辑后的文本
     * 
     * 功能：
     * - 验证编辑后的文本非空（trim 后）
     * - 如果文本为空，显示警告并保持编辑模式
     * - 如果文本与原始相同，直接退出编辑模式
     * - 如果文本有效且不同，退出编辑模式并提交新消息
     * - 全面的错误处理和边界条件检查
     * 
     * Requirements: 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 12.1, 12.2, 12.3, 12.4, 12.5, 14.1, 14.2
     */
    submitEditedMessage(messageElement, newText) {
        console.log('[MessageActionsManager] 提交编辑后的消息');

        try {
            // 验证输入
            if (!messageElement || !(messageElement instanceof HTMLElement)) {
                throw new Error('messageElement 参数必须是有效的 HTMLElement');
            }
            
            if (typeof newText !== 'string') {
                throw new Error('newText 参数必须是字符串');
            }

            const trimmedText = newText.trim();
            
            // 边界条件：文本为空
            if (trimmedText.length === 0) {
                // 文本为空，显示警告
                alert('消息内容不能为空');
                console.log('[MessageActionsManager] 提交失败: 消息内容为空');
                return;
            }

            // 边界条件：文本过长（10,000 字符限制）
            if (trimmedText.length > 10000) {
                alert('消息内容过长，请限制在 10,000 字符以内');
                console.log('[MessageActionsManager] 提交失败: 消息内容过长 (' + trimmedText.length + ' 字符)');
                return;
            }

            // 获取原始文本
            const originalText = messageElement.getAttribute('data-original-text') || '';

            // 边界条件：文本与原始相同
            if (trimmedText === originalText.trim()) {
                // 文本与原始相同，直接退出编辑模式
                console.log('[MessageActionsManager] 文本未修改，直接退出编辑模式');
                this.exitEditMode(messageElement, originalText);
                return;
            }

            // 检查系统状态
            if (typeof isWaitingForResponse !== 'undefined' && isWaitingForResponse) {
                alert('请等待当前响应完成');
                console.log('[MessageActionsManager] 提交失败: 系统正在等待响应');
                return;
            }

            // 检查必要的全局变量是否存在
            if (typeof userInput === 'undefined' || typeof form === 'undefined') {
                throw new Error('必要的全局变量 (userInput, form) 未定义');
            }

            // 退出编辑模式
            this.exitEditMode(messageElement, originalText);

            // 提交新消息（通过现有的消息发送系统）
            console.log('[MessageActionsManager] 提交新消息:', trimmedText);
            
            // 模拟用户输入并提交
            userInput.value = trimmedText;
            form.requestSubmit();

            console.log('[MessageActionsManager] ✓ 编辑后的消息已提交');
        } catch (error) {
            console.error('[MessageActionsManager] 提交编辑消息失败:', error);
            alert('提交消息时发生错误，请重试');
            
            // 尝试保持编辑模式，让用户可以重试
            // 不执行 exitEditMode，保留用户的编辑内容
        }
    }
}

/**
 * ClipboardHandler 类
 * 封装剪贴板操作，提供统一的复制接口和错误处理
 * 
 * 功能：
 * - 使用现代 Clipboard API 复制文本
 * - 降级方案：当 Clipboard API 不可用时使用 document.execCommand('copy')
 * - 提供详细的错误处理和日志记录
 * 
 * Requirements: 2.1, 2.2, 12.1
 */
class ClipboardHandler {
    /**
     * 复制文本到剪贴板
     * @param {string} text - 要复制的文本
     * @returns {Promise<boolean>} 复制是否成功
     */
    async copyToClipboard(text) {
        // 验证输入
        if (typeof text !== 'string') {
            console.error('[ClipboardHandler] 复制失败: 文本参数必须是字符串');
            return false;
        }

        if (text.length === 0) {
            console.warn('[ClipboardHandler] 复制失败: 文本内容为空');
            return false;
        }

        try {
            // 优先使用现代 Clipboard API
            if (navigator.clipboard && navigator.clipboard.writeText) {
                console.log('[ClipboardHandler] 使用 Clipboard API 复制文本');
                await navigator.clipboard.writeText(text);
                console.log('[ClipboardHandler] ✓ 复制成功 (Clipboard API)');
                return true;
            } else {
                // 降级方案：使用 document.execCommand
                console.log('[ClipboardHandler] Clipboard API 不可用，使用降级方案');
                return this._copyUsingExecCommand(text);
            }
        } catch (error) {
            // Clipboard API 失败，尝试降级方案
            console.warn('[ClipboardHandler] Clipboard API 失败:', error.message);
            console.log('[ClipboardHandler] 尝试降级方案 (execCommand)');
            return this._copyUsingExecCommand(text);
        }
    }

    /**
     * 使用 document.execCommand('copy') 降级方案复制文本
     * @private
     * @param {string} text - 要复制的文本
     * @returns {boolean} 复制是否成功
     */
    _copyUsingExecCommand(text) {
        let textarea = null;
        
        try {
            // 创建临时 textarea 元素
            textarea = document.createElement('textarea');
            
            // 设置样式使其不可见但仍可选中
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.top = '-9999px';
            textarea.style.left = '-9999px';
            textarea.style.opacity = '0';
            textarea.setAttribute('readonly', '');
            
            // 添加到 DOM
            document.body.appendChild(textarea);
            
            // 选中文本
            textarea.select();
            textarea.setSelectionRange(0, text.length);
            
            // 执行复制命令
            const success = document.execCommand('copy');
            
            if (success) {
                console.log('[ClipboardHandler] ✓ 复制成功 (execCommand)');
                return true;
            } else {
                console.error('[ClipboardHandler] ✗ execCommand 返回 false');
                return false;
            }
        } catch (error) {
            console.error('[ClipboardHandler] ✗ execCommand 执行失败:', error.message);
            return false;
        } finally {
            // 清理临时元素
            if (textarea && textarea.parentNode) {
                document.body.removeChild(textarea);
            }
        }
    }

    /**
     * 显示复制操作的视觉反馈
     * @param {HTMLElement} button - 按钮元素
     * @param {number} duration - 反馈持续时间（毫秒），默认 2000ms
     * 
     * 功能：
     * - 成功时显示 ✓ 图标
     * - 失败时显示 ✗ 图标
     * - 指定时间后恢复原始图标 📋
     * 
     * Requirements: 2.3, 2.4, 2.5
     */
    showCopyFeedback(button, duration = 2000) {
        // 验证输入
        if (!button || !(button instanceof HTMLElement)) {
            console.error('[ClipboardHandler] showCopyFeedback 失败: button 参数必须是有效的 HTMLElement');
            return;
        }

        if (typeof duration !== 'number' || duration < 0) {
            console.warn('[ClipboardHandler] duration 参数无效，使用默认值 2000ms');
            duration = 2000;
        }

        // 保存原始图标
        const originalIcon = button.textContent;
        
        // 根据原始图标判断操作结果
        // 如果当前已经是反馈图标，说明正在显示反馈，不重复处理
        if (originalIcon === '✓' || originalIcon === '✗') {
            console.log('[ClipboardHandler] 正在显示反馈，跳过重复操作');
            return;
        }

        // 检查按钮的 data 属性来确定显示成功还是失败图标
        // 这个方法本身不判断成功失败，由调用者通过 data-feedback 属性指定
        const feedbackType = button.getAttribute('data-feedback') || 'success';
        
        if (feedbackType === 'success') {
            // 显示成功图标
            button.textContent = '✓';
            button.classList.add('success-feedback');
            console.log('[ClipboardHandler] 显示成功反馈 ✓');
        } else {
            // 显示失败图标
            button.textContent = '✗';
            button.classList.add('error-feedback');
            console.log('[ClipboardHandler] 显示失败反馈 ✗');
        }

        // 设置定时器恢复原始状态
        setTimeout(() => {
            button.textContent = originalIcon;
            button.classList.remove('success-feedback', 'error-feedback');
            button.removeAttribute('data-feedback');
            console.log('[ClipboardHandler] 恢复原始图标:', originalIcon);
        }, duration);
    }
}

// ============================================================================
// 全局实例初始化
// ============================================================================

/**
 * 全局 MessageActionsManager 实例
 * 用于为所有用户消息添加操作按钮（复制、编辑）
 */
const messageActionsManager = new MessageActionsManager();
