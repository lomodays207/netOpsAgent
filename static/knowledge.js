/**
 * 知识库管理页面 - 重构版
 * 布局：左侧分类导航 + 顶部搜索/上传 + 卡片网格展示
 */

const API_BASE = '/api/v1';

// ----- State -----
let allDocuments = [];      // 所有文档
let currentFilter = 'all';  // 当前分类筛选
let categories = {};        // { 分类名: [doc, ...] }

// 搜索相关
let allSearchResults = [];
let currentSearchQuery = '';
let currentPage = 1;
const PAGE_SIZE = 6;
let isSearchMode = false;

// ----- 分类名称自定义映射 -----
const STORAGE_KEY_CAT_NAMES = 'kb_category_names';
let categoryNameMap = {}; // { 内部key: 自定义显示名 }

function loadCategoryNameMap() {
    try {
        const saved = localStorage.getItem(STORAGE_KEY_CAT_NAMES);
        categoryNameMap = saved ? JSON.parse(saved) : {};
    } catch { categoryNameMap = {}; }
    // 确保 Default 有默认显示名
    if (!categoryNameMap['Default']) categoryNameMap['Default'] = '其他';
}

function saveCategoryNameMap() {
    localStorage.setItem(STORAGE_KEY_CAT_NAMES, JSON.stringify(categoryNameMap));
}

/**
 * 获取分类的显示名称（优先使用自定义名称）
 */
function getCategoryDisplayName(cat) {
    return categoryNameMap[cat] || cat;
}

// ----- 分类配置 -----
const CATEGORY_COLORS = {
    'Engineering': { color: 'var(--cat-engineering)', bg: 'rgba(99,102,241,0.08)' },
    'Product': { color: 'var(--cat-product)', bg: 'rgba(249,115,22,0.08)' },
    'Design': { color: 'var(--cat-design)', bg: 'rgba(236,72,153,0.08)' },
    'HR': { color: 'var(--cat-hr)', bg: 'rgba(34,197,94,0.08)' },
    'Marketing': { color: 'var(--cat-marketing)', bg: 'rgba(234,179,8,0.08)' },
    'Ops': { color: 'var(--cat-ops)', bg: 'rgba(6,182,212,0.08)' },
    'Security': { color: 'var(--cat-security)', bg: 'rgba(239,68,68,0.08)' },
    'Default': { color: 'var(--cat-default)', bg: 'rgba(100,116,139,0.08)' },
};

/**
 * 根据文件名推断分类
 */
function inferCategory(filename) {
    const lower = (filename || '').toLowerCase();
    // 关键字匹配
    if (/network|firewall|server|api|code|dev|ops|运维|服务器|网络|端口/.test(lower)) return 'Engineering';
    if (/product|roadmap|产品/.test(lower)) return 'Product';
    if (/design|color|ui|ux|设计/.test(lower)) return 'Design';
    if (/hr|onboard|employee|人事|入职/.test(lower)) return 'HR';
    if (/market|campaign|营销/.test(lower)) return 'Marketing';
    if (/security|安全|证书|防火墙/.test(lower)) return 'Security';
    return 'Default';
}

function getCategoryStyle(category) {
    return CATEGORY_COLORS[category] || CATEGORY_COLORS['Default'];
}

// ----- DOM -----
document.addEventListener('DOMContentLoaded', () => {
    loadCategoryNameMap();
    bindEvents();
    loadDocuments();
});

function bindEvents() {
    const searchInput = document.getElementById('search-input');
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('upload-drop-zone');

    // 搜索
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const query = searchInput.value.trim();
            if (query) searchKnowledge(query);
        }
    });

    // 文件选择
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    // 拖拽上传
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    // ESC 关闭弹窗
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closePreviewModal();
            closeUploadModal();
        }
    });
}

// ===== API Calls =====

async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/knowledge/list`);
        const data = await response.json();
        if (response.ok) {
            allDocuments = data.documents || [];
            buildCategories();
            renderSidebar();
            renderContent();
        } else {
            showToast(data.detail || '加载文档列表失败', 'error');
        }
    } catch (error) {
        console.error('加载文档列表错误:', error);
        showToast('加载文档列表失败', 'error');
    }
}

async function uploadFile(file) {
    if (!file.name.endsWith('.txt')) {
        showToast('仅支持 TXT 格式文件', 'error');
        return;
    }
    showLoading(true);
    try {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_BASE}/knowledge/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (response.ok) {
            showToast(`上传成功！文档已分割为 ${data.chunks} 个知识块`, 'success');
            closeUploadModal();
            loadDocuments();
        } else {
            showToast(data.detail || '上传失败', 'error');
        }
    } catch (error) {
        console.error('上传错误:', error);
        showToast('上传失败，请检查网络连接', 'error');
    } finally {
        showLoading(false);
        document.getElementById('file-input').value = '';
    }
}

async function deleteDocument(docId, filename) {
    if (!confirm(`确定要删除文档 "${filename}" 吗？\n\n删除后无法恢复。`)) return;
    showLoading(true);
    try {
        const response = await fetch(`${API_BASE}/knowledge/${docId}`, { method: 'DELETE' });
        const data = await response.json();
        if (response.ok) {
            showToast(`文档已删除，移除了 ${data.deleted_chunks} 个知识块`, 'success');
            loadDocuments();
        } else {
            showToast(data.detail || '删除失败', 'error');
        }
    } catch (error) {
        console.error('删除错误:', error);
        showToast('删除失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function searchKnowledge(query) {
    const searchInput = document.getElementById('search-input');
    searchInput.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/knowledge/search?query=${encodeURIComponent(query)}&top_k=20`);
        const data = await response.json();
        if (response.ok) {
            allSearchResults = data.results || [];
            currentSearchQuery = data.query;
            currentPage = 1;
            isSearchMode = true;
            renderContent();
        } else {
            showToast(data.detail || '搜索失败', 'error');
        }
    } catch (error) {
        console.error('搜索错误:', error);
        showToast('搜索失败', 'error');
    } finally {
        searchInput.disabled = false;
    }
}

async function previewDocument(docId, filename) {
    const overlay = document.getElementById('preview-modal-overlay');
    const filenameEl = document.getElementById('preview-filename');
    const fileSizeEl = document.getElementById('preview-file-size');
    const contentEl = document.getElementById('preview-content');
    const loadingEl = document.getElementById('preview-loading');

    filenameEl.textContent = filename;
    fileSizeEl.textContent = '';
    contentEl.textContent = '';
    loadingEl.classList.remove('hidden');
    overlay.classList.remove('hidden');

    try {
        const response = await fetch(`${API_BASE}/knowledge/${docId}/content`);
        const data = await response.json();
        if (response.ok) {
            contentEl.textContent = data.content;
            fileSizeEl.textContent = formatFileSize(data.size);
        } else {
            contentEl.textContent = `加载失败: ${data.detail || '未知错误'}`;
        }
    } catch (error) {
        console.error('预览文档错误:', error);
        contentEl.textContent = '加载失败，请检查网络连接';
    } finally {
        loadingEl.classList.add('hidden');
    }
}

// ===== Rendering =====

function buildCategories() {
    categories = {};
    allDocuments.forEach(doc => {
        const cat = inferCategory(doc.filename);
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push(doc);
    });
}

function renderSidebar() {
    // All count
    document.getElementById('nav-count-all').textContent = allDocuments.length;

    // Categories
    const navCats = document.getElementById('nav-categories');
    navCats.innerHTML = '';

    const sortedCats = Object.keys(categories).sort();
    sortedCats.forEach(cat => {
        const count = categories[cat].length;
        const style = getCategoryStyle(cat);
        const displayName = getCategoryDisplayName(cat);
        const li = document.createElement('li');
        li.className = 'sidebar-nav-item' + (currentFilter === cat ? ' active' : '');
        li.setAttribute('data-filter', cat);
        li.onclick = function (e) {
            if (e.target.closest('.cat-edit-btn') || e.target.closest('.cat-edit-input')) return;
            filterByCategory(cat, this);
        };
        li.innerHTML = `
            <span class="nav-left">
                <span class="category-dot" style="background:${style.color}"></span>
                <span class="cat-name-text">${escapeHtml(displayName)}</span>
                <button class="cat-edit-btn" onclick="startEditCategory(event, '${cat}')" title="修改分类名称">✏️</button>
            </span>
            <span class="nav-count">${count}</span>
        `;
        navCats.appendChild(li);
    });
}

/**
 * 开始编辑分类名称（inline 编辑模式）
 */
function startEditCategory(event, cat) {
    event.stopPropagation();
    const li = event.target.closest('.sidebar-nav-item');
    const nameSpan = li.querySelector('.cat-name-text');
    const editBtn = li.querySelector('.cat-edit-btn');
    const currentName = getCategoryDisplayName(cat);

    // 隐藏显示元素
    nameSpan.classList.add('hidden');
    editBtn.classList.add('hidden');

    // 创建输入框
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'cat-edit-input';
    input.value = currentName;
    input.maxLength = 20;
    nameSpan.parentElement.insertBefore(input, nameSpan.nextSibling);
    input.focus();
    input.select();

    function confirmEdit() {
        const newName = input.value.trim();
        if (newName && newName !== currentName) {
            categoryNameMap[cat] = newName;
            saveCategoryNameMap();
            showToast(`分类已重命名为「${newName}」`, 'success');
        }
        cancelEdit();
        renderSidebar();
        renderContent();
    }

    function cancelEdit() {
        input.remove();
        nameSpan.classList.remove('hidden');
        editBtn.classList.remove('hidden');
    }

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); confirmEdit(); }
        if (e.key === 'Escape') { e.preventDefault(); cancelEdit(); }
    });
    input.addEventListener('blur', () => {
        // 延时以允许点击确认
        setTimeout(confirmEdit, 150);
    });
}

function renderContent() {
    const grid = document.getElementById('card-grid');
    const titleEl = document.getElementById('content-title');
    const countEl = document.getElementById('result-count');
    const emptyEl = document.getElementById('empty-state');
    const clearBtn = document.getElementById('clear-search-btn');

    grid.innerHTML = '';
    emptyEl.classList.add('hidden');

    if (isSearchMode) {
        // 搜索结果模式
        clearBtn.classList.remove('hidden');
        titleEl.textContent = `搜索: "${currentSearchQuery}"`;

        if (allSearchResults.length === 0) {
            countEl.textContent = '未找到相关结果';
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">💭</div>
                    <p>未找到与「${escapeHtml(currentSearchQuery)}」相关的内容</p>
                    <p>请尝试其他关键词</p>
                </div>`;
            return;
        }

        const total = allSearchResults.length;
        const totalPages = Math.ceil(total / PAGE_SIZE);
        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;
        const start = (currentPage - 1) * PAGE_SIZE;
        const end = Math.min(start + PAGE_SIZE, total);
        const pageResults = allSearchResults.slice(start, end);

        countEl.textContent = `找到 ${total} 个相关结果（第 ${start + 1}-${end} 条）`;

        pageResults.forEach(result => {
            const scorePercent = Math.round(result.relevance_score * 100);
            const scoreColor = scorePercent >= 70 ? '#16a34a' : scorePercent >= 40 ? '#f97316' : '#ef4444';
            const cat = inferCategory(result.filename);
            const style = getCategoryStyle(cat);

            const card = document.createElement('div');
            card.className = 'doc-card';
            card.onclick = (e) => {
                if (e.target.closest('.card-actions')) return;
                if (result.doc_id) {
                    previewDocument(result.doc_id, result.filename);
                }
            };

            card.innerHTML = `
                ${result.doc_id ? `<div class="card-actions">
                    <button class="card-action-btn" onclick="previewDocument('${result.doc_id}', '${escapeHtml(result.filename)}')" title="预览">👁️</button>
                </div>` : ''}
                <span class="search-result-badge">
                    相关度 ${scorePercent}%
                    <span class="score-bar-mini"><span class="score-bar-mini-fill" style="width:${scorePercent}%;background:${scoreColor};"></span></span>
                </span>
                <span class="card-category" style="background:${style.bg};color:${style.color}">
                    <span class="cat-dot" style="background:${style.color}"></span>
                    ${escapeHtml(getCategoryDisplayName(cat))}
                </span>
                <div class="card-title">${escapeHtml(result.filename)}</div>
                <div class="card-summary">${escapeHtml(result.text)}</div>
                <div class="card-footer">
                    <span class="footer-item">📄 ${escapeHtml(result.filename)}</span>
                </div>
            `;
            grid.appendChild(card);
        });

        // 分页
        if (totalPages > 1) {
            grid.insertAdjacentHTML('beforeend', renderPagination(totalPages));
        }

    } else {
        // 文档列表模式
        clearBtn.classList.add('hidden');

        let docs = allDocuments;
        if (currentFilter !== 'all') {
            docs = categories[currentFilter] || [];
            titleEl.textContent = getCategoryDisplayName(currentFilter);
        } else {
            titleEl.textContent = '全部文档';
        }

        countEl.textContent = `共 ${docs.length} 个文档`;

        if (docs.length === 0) {
            emptyEl.classList.remove('hidden');
            return;
        }

        docs.forEach(doc => {
            const cat = inferCategory(doc.filename);
            const style = getCategoryStyle(cat);
            const readMin = Math.max(1, Math.round((doc.chunk_count || 1) * 1.5));
            const uploadDate = formatDate(doc.upload_time);
            // 生成一个摘要文本（基于文件名）
            const summary = generateSummary(doc.filename, doc.chunk_count);

            const card = document.createElement('div');
            card.className = 'doc-card';
            card.onclick = (e) => {
                // 如果点击的是操作按钮区域，不触发预览
                if (e.target.closest('.card-actions')) return;
                previewDocument(doc.doc_id, doc.filename);
            };

            card.innerHTML = `
                <div class="card-actions">
                    <button class="card-action-btn" onclick="previewDocument('${doc.doc_id}', '${escapeHtml(doc.filename)}')" title="预览">👁️</button>
                    <button class="card-action-btn delete-action" onclick="deleteDocument('${doc.doc_id}', '${escapeHtml(doc.filename)}')" title="删除">🗑️</button>
                </div>
                <span class="card-category" style="background:${style.bg};color:${style.color}">
                    <span class="cat-dot" style="background:${style.color}"></span>
                    ${escapeHtml(getCategoryDisplayName(cat))}
                </span>
                <div class="card-title">${escapeHtml(doc.filename)}</div>
                <div class="card-summary">${escapeHtml(summary)}</div>
                <div class="card-footer">
                    <span class="footer-item">📦 ${doc.chunk_count} 个知识块</span>
                    <span class="footer-item">⏱ ${readMin} 分钟</span>
                    <span class="footer-item">${uploadDate}</span>
                </div>
            `;
            grid.appendChild(card);
        });
    }
}

/**
 * 根据文件名生成简短摘要描述
 */
function generateSummary(filename, chunkCount) {
    const name = (filename || '').replace(/\.[^.]+$/, '');
    return `此文档包含 ${chunkCount || 0} 个知识块的内容，来源于 "${name}"。上传后可通过搜索和 AI 对话进行知识检索。`;
}

// ===== Sidebar Filter =====

function filterByCategory(category, el) {
    // 退出搜索模式
    isSearchMode = false;
    allSearchResults = [];
    currentSearchQuery = '';
    document.getElementById('search-input').value = '';

    currentFilter = category;

    // 更新侧栏高亮
    document.querySelectorAll('.sidebar-nav-item').forEach(item => item.classList.remove('active'));
    if (el) el.classList.add('active');

    renderContent();
}

// ===== Search =====

function clearSearchResults() {
    isSearchMode = false;
    allSearchResults = [];
    currentSearchQuery = '';
    currentPage = 1;
    document.getElementById('search-input').value = '';
    renderContent();
}

// ===== Pagination =====

function renderPagination(totalPages) {
    let html = '<div class="pagination">';

    html += `<button class="page-btn ${currentPage <= 1 ? 'disabled' : ''}"
        onclick="goToPage(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}>‹</button>`;

    const maxVisible = 5;
    let startP = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endP = Math.min(totalPages, startP + maxVisible - 1);
    if (endP - startP + 1 < maxVisible) startP = Math.max(1, endP - maxVisible + 1);

    if (startP > 1) {
        html += `<button class="page-btn" onclick="goToPage(1)">1</button>`;
        if (startP > 2) html += '<span class="page-ellipsis">...</span>';
    }
    for (let i = startP; i <= endP; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }
    if (endP < totalPages) {
        if (endP < totalPages - 1) html += '<span class="page-ellipsis">...</span>';
        html += `<button class="page-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }

    html += `<button class="page-btn ${currentPage >= totalPages ? 'disabled' : ''}"
        onclick="goToPage(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}>›</button>`;

    html += '</div>';
    return html;
}

function goToPage(page) {
    const totalPages = Math.ceil(allSearchResults.length / PAGE_SIZE);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderContent();
    document.querySelector('.content-area').scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== Modals =====

function openUploadModal() {
    document.getElementById('upload-modal-overlay').classList.remove('hidden');
}

function closeUploadModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('upload-modal-overlay').classList.add('hidden');
}

function closePreviewModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('preview-modal-overlay').classList.add('hidden');
}

// ===== Utilities =====

function showLoading(show) {
    const el = document.getElementById('loading-overlay');
    if (show) el.classList.remove('hidden');
    else el.classList.add('hidden');
}

function showToast(message, type = 'info') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function formatDate(isoString) {
    if (!isoString) return '';
    try {
        const d = new Date(isoString);
        return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
    } catch {
        return isoString;
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
