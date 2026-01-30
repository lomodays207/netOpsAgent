/**
 * Chat History Page JavaScript
 * Handles fetching and displaying session list and messages
 */

// State management
let currentSessionId = null;
let currentFilter = 'all';
let sessions = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadSessions();
});

/**
 * Initialize event listeners
 */
function initializeEventListeners() {
    // Filter buttons
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Update active state
            filterButtons.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');

            // Apply filter
            currentFilter = e.target.dataset.status;
            filterSessions();
        });
    });
}

/**
 * Load sessions from API
 */
async function loadSessions() {
    const sessionsList = document.getElementById('sessions-list');

    try {
        // Show loading state
        sessionsList.innerHTML = `
            <div class="empty-state">
                <div class="loading-spinner"></div>
                <p style="margin-top: 10px;">加载中...</p>
            </div>
        `;

        // Fetch sessions
        const response = await fetch('/api/v1/sessions');
        if (!response.ok) {
            throw new Error('Failed to fetch sessions');
        }

        sessions = await response.json();

        // Display sessions
        displaySessions(sessions);

    } catch (error) {
        console.error('Error loading sessions:', error);
        sessionsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">加载失败，请刷新重试</div>
            </div>
        `;
    }
}

/**
 * Display sessions in the list
 */
function displaySessions(sessionsToDisplay) {
    const sessionsList = document.getElementById('sessions-list');

    if (sessionsToDisplay.length === 0) {
        sessionsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-text">暂无会话记录</div>
            </div>
        `;
        return;
    }

    sessionsList.innerHTML = sessionsToDisplay.map(session => `
        <div class="session-card ${session.session_id === currentSessionId ? 'active' : ''}" 
             data-session-id="${session.session_id}">
            <div onclick="selectSession('${session.session_id}')">
                <div class="session-header">
                    <div class="session-id-wrapper">
                        <span class="session-id">${truncateSessionId(session.session_id)}</span>
                        <button class="session-menu-btn" onclick="event.stopPropagation(); toggleSessionMenu('${session.session_id}', event)">⋮</button>
                        <div class="session-dropdown-menu" id="menu-${session.session_id}">
                            <button class="menu-item" onclick="event.stopPropagation(); openRenameModal('${session.session_id}', '${escapeHtml(session.task_description).replace(/'/g, "\\'")}')">
                                ✏️ 重命名
                            </button>
                            <button class="menu-item delete" onclick="event.stopPropagation(); openDeleteModal('${session.session_id}')">
                                🗑️ 删除
                            </button>
                        </div>
                    </div>
                    <span class="status-badge ${session.status}">${getStatusText(session.status)}</span>
                </div>
                <div class="session-description">${escapeHtml(session.task_description)}</div>
                <div class="session-time">
                    创建: ${formatTime(session.created_at)}<br>
                    更新: ${formatTime(session.updated_at)}
                </div>
            </div>
            <button class="continue-btn" onclick="event.stopPropagation(); continueSession('${session.session_id}')">
                💬 继续聊天
            </button>
        </div>
    `).join('');
}

/**
 * Continue a session - redirect to main page with session ID
 */
function continueSession(sessionId) {
    window.location.href = `/?session_id=${sessionId}`;
}

/**
 * Filter sessions based on current filter
 */
function filterSessions() {
    let filteredSessions = sessions;

    if (currentFilter !== 'all') {
        filteredSessions = sessions.filter(s => s.status === currentFilter);
    }

    displaySessions(filteredSessions);
}

/**
 * Select a session and load its messages
 */
async function selectSession(sessionId) {
    currentSessionId = sessionId;

    // Update active state in session list
    document.querySelectorAll('.session-card').forEach(card => {
        if (card.dataset.sessionId === sessionId) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });

    // Load messages
    await loadMessages(sessionId);
}

/**
 * Load messages for a session
 */
async function loadMessages(sessionId) {
    const messagesContent = document.getElementById('messages-content');
    const messagesHeader = document.getElementById('messages-header');
    const sessionTitle = document.getElementById('session-title');
    const sessionInfo = document.getElementById('session-info');

    try {
        // Show loading state
        messagesContent.innerHTML = `
            <div class="empty-state">
                <div class="loading-spinner"></div>
                <p style="margin-top: 10px;">加载消息中...</p>
            </div>
        `;

        // Fetch messages
        const response = await fetch(`/api/v1/sessions/${sessionId}/messages`);
        if (!response.ok) {
            throw new Error('Failed to fetch messages');
        }

        const messages = await response.json();

        // Find session info
        const session = sessions.find(s => s.session_id === sessionId);

        // Update header
        messagesHeader.style.display = 'block';
        sessionTitle.textContent = truncateSessionId(sessionId);
        sessionInfo.textContent = session ? session.task_description : '';

        // Display messages
        displayMessages(messages);

    } catch (error) {
        console.error('Error loading messages:', error);
        messagesContent.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">加载消息失败</div>
            </div>
        `;
    }
}

/**
 * Display messages in the chat area
 */
function displayMessages(messages) {
    const messagesContent = document.getElementById('messages-content');
    messagesContent.innerHTML = ''; // Clear previous messages

    if (messages.length === 0) {
        messagesContent.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💬</div>
                <div class="empty-state-text">此会话暂无消息</div>
            </div>
        `;
        return;
    }

    messages.forEach(msg => {
        const messageEl = document.createElement('div');
        const messageClass = msg.role === 'user' ? 'user-message' : 'assistant-message';
        const avatar = msg.role === 'user' ? '👤' : '🤖';

        messageEl.className = `message ${messageClass}`;
        messageEl.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-text"></div>
                <div class="message-timestamp">${formatTime(msg.timestamp)}</div>
            </div>
        `;

        const textContainer = messageEl.querySelector('.message-text');

        // Handle metadata (tool calls, reports, etc.)
        let metadata = null;
        if (msg.metadata) {
            try {
                metadata = typeof msg.metadata === 'string' ? JSON.parse(msg.metadata) : msg.metadata;
            } catch (e) {
                console.warn('Failed to parse metadata:', e);
            }
        }

        if (metadata && metadata.tool_call) {
            // Render tool call
            const toolCard = createToolCallCardHtml(metadata.tool_call);
            textContainer.appendChild(toolCard);
        } else if (metadata && metadata.report) {
            // Render final report
            const reportEl = createFinalReportHtml(metadata.report);
            textContainer.appendChild(reportEl);
        } else if (metadata && metadata.context) {
            // This might be a question with context
            textContainer.innerHTML = formatMessageContent(msg.content);
        } else {
            // Normal message
            textContainer.innerHTML = formatMessageContent(msg.content);
        }

        messagesContent.appendChild(messageEl);
    });

    // Scroll to bottom
    messagesContent.scrollTop = messagesContent.scrollHeight;
}

/**
 * Create tool call card element (used in history)
 */
function createToolCallCardHtml(toolCall) {
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
    const output = result.stdout || result.data || result.error || '执行完成';
    resultEl.textContent = `结果：\n${output}`;
    resultEl.className = `tool-result ${result.success ? 'success' : 'error'}`;

    return card;
}

/**
 * Create final report element (used in history)
 */
function createFinalReportHtml(report) {
    const template = document.getElementById('report-template');
    const reportEl = template.content.cloneNode(true);

    reportEl.querySelector('.root-cause').textContent = report.root_cause;
    reportEl.querySelector('.confidence').textContent = `${(report.confidence * 100).toFixed(1)}%`;

    const suggestionsUl = reportEl.querySelector('.suggestions');
    if (report.fix_suggestions && report.fix_suggestions.length > 0) {
        report.fix_suggestions.forEach(suggestion => {
            const li = document.createElement('li');
            li.textContent = suggestion;
            suggestionsUl.appendChild(li);
        });
    } else {
        suggestionsUl.innerHTML = '<li>暂无建议</li>';
    }

    return reportEl;
}

/**
 * Format tool name for display
 */
function formatToolName(toolName) {
    const nameMap = {
        'execute_command': '命令执行',
        'query_cmdb': 'CMDB 查询',
        'ask_user': '询问用户'
    };
    return nameMap[toolName] || toolName;
}

/**
 * Format message content (handle line breaks, code blocks, etc.)
 */
function formatMessageContent(content) {
    // Escape HTML
    let formatted = escapeHtml(content);

    // Convert line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    // Simple code block detection (wrapped in ```)
    formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    // Inline code (wrapped in `)
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

    return formatted;
}

/**
 * Truncate session ID for display
 */
function truncateSessionId(sessionId) {
    if (sessionId.length > 30) {
        return sessionId.substring(0, 27) + '...';
    }
    return sessionId;
}

/**
 * Get status text in Chinese
 */
function getStatusText(status) {
    const statusMap = {
        'active': '进行中',
        'completed': '已完成',
        'waiting_user': '等待回复',
        'error': '错误'
    };
    return statusMap[status] || status;
}

/**
 * Format timestamp
 */
function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    // Less than 1 minute
    if (diff < 60000) {
        return '刚刚';
    }

    // Less than 1 hour
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes}分钟前`;
    }

    // Less than 1 day
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours}小时前`;
    }

    // Less than 7 days
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days}天前`;
    }

    // Format as date
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');

    // Same year, don't show year
    if (year === now.getFullYear()) {
        return `${month}-${day} ${hour}:${minute}`;
    }

    return `${year}-${month}-${day} ${hour}:${minute}`;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 会话菜单和模态框功能
 */

// 当前操作的会话ID
let currentOperationSessionId = null;

/**
 * 切换会话菜单显示/隐藏
 */
function toggleSessionMenu(sessionId, event) {
    event.stopPropagation();
    const menu = document.getElementById(`menu-${sessionId}`);
    const allMenus = document.querySelectorAll('.session-dropdown-menu');

    // 关闭其他菜单
    allMenus.forEach(m => {
        if (m.id !== `menu-${sessionId}`) {
            m.classList.remove('show');
        }
    });

    // 切换当前菜单
    menu.classList.toggle('show');
}

/**
 * 关闭所有菜单
 */
function closeAllMenus() {
    const allMenus = document.querySelectorAll('.session-dropdown-menu');
    allMenus.forEach(m => m.classList.remove('show'));
}

/**
 * 打开重命名模态框
 */
function openRenameModal(sessionId, currentName) {
    closeAllMenus();
    currentOperationSessionId = sessionId;
    const modal = document.getElementById('renameModal');
    const input = document.getElementById('renameInput');
    input.value = currentName;
    modal.classList.add('show');
    // 聚焦并选中文本
    setTimeout(() => {
        input.focus();
        input.select();
    }, 100);
}

/**
 * 关闭重命名模态框
 */
function closeRenameModal() {
    const modal = document.getElementById('renameModal');
    modal.classList.remove('show');
    currentOperationSessionId = null;
}

/**
 * 确认重命名
 */
async function confirmRename() {
    const newName = document.getElementById('renameInput').value.trim();

    if (!newName) {
        alert('会话名称不能为空');
        return;
    }

    if (!currentOperationSessionId) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/sessions/${currentOperationSessionId}/rename`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_name: newName })
        });

        if (!response.ok) {
            throw new Error('重命名失败');
        }

        // 更新本地数据
        const session = sessions.find(s => s.session_id === currentOperationSessionId);
        if (session) {
            session.task_description = newName;
        }

        // 重新渲染列表
        filterSessions();

        // 如果当前查看的是这个会话，更新标题
        if (currentSessionId === currentOperationSessionId) {
            const sessionInfo = document.getElementById('session-info');
            if (sessionInfo) {
                sessionInfo.textContent = newName;
            }
        }

        closeRenameModal();

    } catch (error) {
        console.error('重命名会话失败:', error);
        alert('重命名失败，请重试');
    }
}

/**
 * 打开删除确认对话框
 */
function openDeleteModal(sessionId) {
    closeAllMenus();
    currentOperationSessionId = sessionId;
    const modal = document.getElementById('deleteModal');
    modal.classList.add('show');
}

/**
 * 关闭删除确认对话框
 */
function closeDeleteModal() {
    const modal = document.getElementById('deleteModal');
    modal.classList.remove('show');
    currentOperationSessionId = null;
}

/**
 * 确认删除
 */
async function confirmDelete() {
    if (!currentOperationSessionId) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/sessions/${currentOperationSessionId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('删除失败');
        }

        // 从本地数据中删除
        sessions = sessions.filter(s => s.session_id !== currentOperationSessionId);

        // 如果删除的是当前查看的会话，清空消息区域
        if (currentSessionId === currentOperationSessionId) {
            currentSessionId = null;
            const messagesContent = document.getElementById('messages-content');
            const messagesHeader = document.getElementById('messages-header');
            messagesHeader.style.display = 'none';
            messagesContent.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">💬</div>
                    <div class="empty-state-text">选择一个会话查看聊天记录</div>
                </div>
            `;
        }

        // 重新渲染列表
        filterSessions();

        closeDeleteModal();

    } catch (error) {
        console.error('删除会话失败:', error);
        alert('删除失败，请重试');
    }
}

// 点击页面其他区域关闭菜单和模态框
document.addEventListener('click', (event) => {
    // 关闭所有菜单
    if (!event.target.closest('.session-menu-btn') && !event.target.closest('.session-dropdown-menu')) {
        closeAllMenus();
    }

    // 点击遮罩层关闭模态框
    if (event.target.classList.contains('modal-overlay')) {
        closeRenameModal();
        closeDeleteModal();
    }
});

// 按 ESC 键关闭模态框
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeRenameModal();
        closeDeleteModal();
    }
});

// 回车键确认重命名
document.getElementById('renameInput')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        confirmRename();
    }
});

/**
 * Auto-refresh sessions (optional, can be enabled)
 */
function enableAutoRefresh(intervalMs = 30000) {
    setInterval(() => {
        loadSessions();
        if (currentSessionId) {
            loadMessages(currentSessionId);
        }
    }, intervalMs);
}

// Uncomment to enable auto-refresh every 30 seconds
// enableAutoRefresh();
