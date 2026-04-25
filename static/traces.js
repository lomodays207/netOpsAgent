const traceState = {
    page: 1,
    pageSize: 20,
    total: 0,
};

document.addEventListener('DOMContentLoaded', () => {
    initializeTraceFilters();
    loadTraceStats();
    loadTraces();
});

function debounce(fn, wait) {
    let timerId = null;
    return (...args) => {
        if (timerId) {
            clearTimeout(timerId);
        }
        timerId = window.setTimeout(() => fn(...args), wait);
    };
}

function initializeTraceFilters() {
    const debouncedReload = debounce(() => {
        traceState.page = 1;
        loadTraces();
    }, 250);

    document.getElementById('trace-search-input').addEventListener('input', debouncedReload);
    document.getElementById('trace-request-type-filter').addEventListener('change', debouncedReload);
    document.getElementById('trace-session-filter').addEventListener('input', debouncedReload);
    document.getElementById('trace-start-time').addEventListener('change', debouncedReload);
    document.getElementById('trace-end-time').addEventListener('change', debouncedReload);

    document.getElementById('refresh-traces-btn').addEventListener('click', () => {
        loadTraceStats();
        loadTraces();
    });
    document.getElementById('export-traces-btn').addEventListener('click', exportTracesCsv);
    document.getElementById('traces-prev-page').addEventListener('click', () => changeTracePage(-1));
    document.getElementById('traces-next-page').addEventListener('click', () => changeTracePage(1));
}

function buildTraceQueryParams() {
    const params = new URLSearchParams();
    params.set('page', String(traceState.page));
    params.set('page_size', String(traceState.pageSize));

    const search = document.getElementById('trace-search-input').value.trim();
    const requestType = document.getElementById('trace-request-type-filter').value;
    const sessionId = document.getElementById('trace-session-filter').value.trim();
    const startTime = document.getElementById('trace-start-time').value;
    const endTime = document.getElementById('trace-end-time').value;

    if (search) {
        params.set('query', search);
    }
    if (requestType) {
        params.set('request_type', requestType);
    }
    if (sessionId) {
        params.set('session_id', sessionId);
    }
    if (startTime) {
        params.set('start_time', new Date(startTime).toISOString());
    }
    if (endTime) {
        params.set('end_time', new Date(endTime).toISOString());
    }

    return params;
}

async function loadTraceStats() {
    try {
        const response = await fetch('/api/v1/traces/stats');
        if (!response.ok) {
            throw new Error('无法加载追踪统计');
        }

        const stats = await response.json();
        document.getElementById('trace-stats-total').textContent = String(stats.total ?? 0);
        document.getElementById('trace-stats-average').textContent = formatDuration(stats.average_total_time);
        document.getElementById('trace-stats-24h').textContent = String(stats.last_24_hours ?? 0);
        document.getElementById('trace-stats-7d').textContent = String(stats.last_7_days ?? 0);
    } catch (error) {
        console.error('Failed to load trace stats:', error);
    }
}

async function loadTraces() {
    const list = document.getElementById('traces-list');
    const emptyState = document.getElementById('traces-empty');

    emptyState.hidden = true;
    setTraceFeedback('');
    list.innerHTML = '<div class="trace-loading-card">正在加载追踪记录...</div>';

    try {
        const response = await fetch(`/api/v1/traces?${buildTraceQueryParams().toString()}`);
        if (!response.ok) {
            throw new Error('无法加载追踪记录');
        }

        const payload = await response.json();
        traceState.total = payload.total ?? 0;
        renderTracePagination();
        renderTraceList(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
        console.error('Failed to load traces:', error);
        list.innerHTML = '';
        setTraceFeedback('无法加载追踪记录', true);
        emptyState.hidden = false;
        emptyState.textContent = '无法加载追踪记录';
    }
}

function renderTraceList(items) {
    const list = document.getElementById('traces-list');
    const emptyState = document.getElementById('traces-empty');

    if (!Array.isArray(items) || items.length === 0) {
        list.innerHTML = '';
        emptyState.hidden = false;
        emptyState.textContent = '暂无追踪记录';
        return;
    }

    emptyState.hidden = true;
    list.innerHTML = items.map(trace => `
        <article class="trace-list-card" data-trace-id="${trace.trace_id}">
            <div class="trace-list-card-top">
                <div>
                    <div class="trace-id-text">${escapeHtml(trace.trace_id)}</div>
                    <div class="trace-user-input">${escapeHtml(trace.user_input || '无用户输入')}</div>
                </div>
                <div class="trace-badges">
                    <span class="trace-type-badge">${formatRequestType(trace.request_type)}</span>
                    <span class="trace-status-badge trace-status-${escapeHtml(trace.status || 'unknown')}">${formatStatus(trace.status)}</span>
                </div>
            </div>
            <div class="trace-list-card-meta">
                <span>会话: ${escapeHtml(trace.session_id || '-')}</span>
                <span>创建时间: ${formatDateTime(trace.created_at)}</span>
                <span>耗时: ${formatDuration(trace.total_time)}</span>
            </div>
        </article>
    `).join('');

    list.querySelectorAll('.trace-list-card').forEach(card => {
        card.addEventListener('click', () => {
            const traceId = card.dataset.traceId;
            window.location.href = `/static/trace_detail.html?trace_id=${traceId}`;
        });
    });
}

function renderTracePagination() {
    const pageInfo = document.getElementById('traces-page-info');
    const prevBtn = document.getElementById('traces-prev-page');
    const nextBtn = document.getElementById('traces-next-page');
    const totalPages = Math.max(1, Math.ceil(traceState.total / traceState.pageSize));

    pageInfo.textContent = `第 ${traceState.page} / ${totalPages} 页，共 ${traceState.total} 条`;
    prevBtn.disabled = traceState.page <= 1;
    nextBtn.disabled = traceState.page >= totalPages;
}

function changeTracePage(delta) {
    const nextPage = traceState.page + delta;
    const totalPages = Math.max(1, Math.ceil(traceState.total / traceState.pageSize));
    if (nextPage < 1 || nextPage > totalPages) {
        return;
    }
    traceState.page = nextPage;
    loadTraces();
}

async function exportTracesCsv() {
    setTraceFeedback('');

    try {
        const payload = {
            page: 1,
            page_size: 1000,
            session_id: document.getElementById('trace-session-filter').value.trim() || null,
            request_type: document.getElementById('trace-request-type-filter').value || null,
            start_time: normalizeDateTimeInput(document.getElementById('trace-start-time').value),
            end_time: normalizeDateTimeInput(document.getElementById('trace-end-time').value),
            query: document.getElementById('trace-search-input').value.trim() || null,
        };

        const response = await fetch('/api/v1/traces/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            throw new Error('导出追踪记录失败');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'trace_export.csv';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);
        setTraceFeedback('CSV 导出已开始');
    } catch (error) {
        console.error('Failed to export traces:', error);
        setTraceFeedback(error.message || '导出追踪记录失败', true);
    }
}

function normalizeDateTimeInput(value) {
    if (!value) {
        return null;
    }
    return new Date(value).toISOString();
}

function setTraceFeedback(message, isError = false) {
    const feedback = document.getElementById('traces-feedback');
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
