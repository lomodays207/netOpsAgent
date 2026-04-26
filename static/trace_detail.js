document.addEventListener('DOMContentLoaded', () => {
    const traceId = new URLSearchParams(window.location.search).get('trace_id');
    if (!traceId) {
        showTraceDetailError('无法加载追踪详情');
        return;
    }
    loadTraceDetail(traceId);
});

async function loadTraceDetail(traceId) {
    try {
        const response = await fetch(`/api/v1/traces/${traceId}`);
        if (!response.ok) {
            throw new Error('无法加载追踪详情');
        }

        const payload = await response.json();
        renderTraceOverview(payload.trace || {});
        renderReasoningSteps(payload.reasoning_steps || []);
        renderToolCalls(payload.tool_calls || []);
        renderFinalAnswer(payload.trace?.final_answer || '');
        setTraceDetailFeedback('');
    } catch (error) {
        console.error('Failed to load trace detail:', error);
        showTraceDetailError(error.message || '无法加载追踪详情');
    }
}

function renderTraceOverview(trace) {
    const overview = document.getElementById('trace-overview');
    overview.innerHTML = `
        <div class="trace-overview-grid">
            <div>
                <span class="trace-stat-label">Trace ID</span>
                <strong class="trace-overview-primary">${escapeHtml(trace.trace_id || '-')}</strong>
            </div>
            <div>
                <span class="trace-stat-label">会话 ID</span>
                <strong>${escapeHtml(trace.session_id || '-')}</strong>
            </div>
            <div>
                <span class="trace-stat-label">请求类型</span>
                <strong>${formatRequestType(trace.request_type)}</strong>
            </div>
            <div>
                <span class="trace-stat-label">状态</span>
                <strong>${formatStatus(trace.status)}</strong>
            </div>
            <div>
                <span class="trace-stat-label">创建时间</span>
                <strong>${formatDateTime(trace.created_at)}</strong>
            </div>
            <div>
                <span class="trace-stat-label">完成时间</span>
                <strong>${formatDateTime(trace.completed_at)}</strong>
            </div>
            <div>
                <span class="trace-stat-label">耗时</span>
                <strong>${formatDuration(trace.total_time)}</strong>
            </div>
            <div>
                <span class="trace-stat-label">用户输入</span>
                <strong>${escapeHtml(trace.user_input || '-')}</strong>
            </div>
        </div>
    `;
}

function renderReasoningSteps(steps) {
    const container = document.getElementById('reasoning-steps-list');
    if (!Array.isArray(steps) || steps.length === 0) {
        container.innerHTML = '<div class="trace-empty-state">暂无推理步骤</div>';
        return;
    }

    container.innerHTML = steps.map(step => `
        <article class="trace-timeline-item">
            <div class="trace-timeline-step">#${escapeHtml(String(step.step_number ?? '-'))}</div>
            <div class="trace-timeline-content">
                <div class="trace-timeline-meta">${formatDateTime(step.timestamp || step.created_at)}</div>
                <pre>${escapeHtml(step.reasoning_content || '')}</pre>
            </div>
        </article>
    `).join('');
}

function renderToolCalls(toolCalls) {
    const container = document.getElementById('tool-calls-list');
    if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
        container.innerHTML = '<div class="trace-empty-state">暂无工具调用</div>';
        return;
    }

    container.innerHTML = toolCalls.map(toolCall => `
        <article class="trace-tool-call-card">
            <div class="trace-tool-call-head">
                <strong>${escapeHtml(toolCall.tool_name || '-')}</strong>
                <span>${formatToolStatus(toolCall.status)}</span>
            </div>
            <div class="trace-tool-call-meta">
                <span>步骤: #${escapeHtml(String(toolCall.step_number ?? '-'))}</span>
                <span>开始: ${formatDateTime(toolCall.started_at)}</span>
                <span>结束: ${formatDateTime(toolCall.completed_at)}</span>
                <span>耗时: ${formatDuration(toolCall.duration)}</span>
            </div>
            <div class="trace-tool-call-body">
                <div>
                    <div class="trace-json-label">Arguments</div>
                    <pre>${escapeHtml(formatJsonBlock(toolCall.arguments))}</pre>
                </div>
                <div>
                    <div class="trace-json-label">Result</div>
                    <pre>${escapeHtml(formatJsonBlock(toolCall.result))}</pre>
                </div>
            </div>
        </article>
    `).join('');
}

function renderFinalAnswer(finalAnswer) {
    const el = document.getElementById('final-answer');
    el.textContent = finalAnswer || '暂无最终回答';
}

function showTraceDetailError(message) {
    document.getElementById('trace-overview').innerHTML = '<div class="trace-empty-state">无法加载追踪详情</div>';
    document.getElementById('reasoning-steps-list').innerHTML = '';
    document.getElementById('tool-calls-list').innerHTML = '';
    document.getElementById('final-answer').textContent = '-';
    setTraceDetailFeedback(message || '无法加载追踪详情', true);
}

function setTraceDetailFeedback(message, isError = false) {
    const feedback = document.getElementById('trace-detail-feedback');
    if (!message) {
        feedback.hidden = true;
        feedback.textContent = '';
        feedback.className = 'trace-feedback-strip';
        return;
    }

    feedback.hidden = false;
    feedback.textContent = message;
    feedback.className = isError ? 'trace-feedback-strip is-error' : 'trace-feedback-strip is-success';
}

function formatJsonBlock(value) {
    if (value === null || value === undefined || value === '') {
        return '-';
    }
    if (typeof value === 'string') {
        try {
            return JSON.stringify(JSON.parse(value), null, 2);
        } catch (error) {
            return value;
        }
    }
    return JSON.stringify(value, null, 2);
}

function formatRequestType(requestType) {
    if (requestType === 'diagnosis') {
        return '诊断';
    }
    if (requestType === 'general_chat') {
        return '通用聊天';
    }
    return requestType || '未知类型';
}

function formatStatus(status) {
    const mapping = {
        running: '运行中',
        completed: '已完成',
        failed: '失败',
        interrupted: '已中断',
    };
    return mapping[status] || (status || '未知');
}

function formatToolStatus(status) {
    const mapping = {
        running: '运行中',
        success: '成功',
        failed: '失败',
    };
    return mapping[status] || (status || '未知');
}

function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) {
        return '-';
    }
    const value = Number(seconds);
    if (value < 1) {
        return `${Math.round(value * 1000)} ms`;
    }
    return `${value.toFixed(2)} s`;
}

function formatDateTime(value) {
    if (!value) {
        return '-';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString('zh-CN', { hour12: false });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
