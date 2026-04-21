/**
 * 网络访问关系资产库管理页面 JavaScript
 * access_assets.js
 */

// ===== 全局状态 =====
let currentPage = 1;
const PAGE_SIZE = 20;
let totalRecords = 0;
let pendingDeleteId = null;
let isLoading = false;

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    console.log('🔗 访问关系资产库已加载');
    loadAssets();

    // 搜索框回车触发
    ['filter-src', 'filter-dst', 'filter-keyword'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') doSearch();
            });
        }
    });
});

// ===== 数据加载 =====
async function loadAssets(page = 1) {
    if (isLoading) return;
    isLoading = true;
    currentPage = page;

    const srcSystem = document.getElementById('filter-src').value.trim();
    const dstSystem = document.getElementById('filter-dst').value.trim();
    const keyword = document.getElementById('filter-keyword').value.trim();
    const protocol = document.getElementById('filter-protocol').value;

    // 显示加载状态
    document.getElementById('assets-tbody').innerHTML = `
        <tr class="loading-row">
            <td colspan="10">
                <div class="loading-spinner">
                    <div class="spinner"></div>
                    <span>数据加载中...</span>
                </div>
            </td>
        </tr>
    `;

    try {
        const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
        if (srcSystem) params.set('src_system', srcSystem);
        if (dstSystem) params.set('dst_system', dstSystem);
        if (keyword) params.set('keyword', keyword);
        if (protocol) params.set('protocol', protocol);

        const response = await fetch(`/api/v1/assets/access-relations?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        totalRecords = data.total || 0;

        renderTable(data.items || []);
        renderPagination(data.total || 0, page);
        updateStats(data.total || 0, page);

    } catch (error) {
        console.error('加载数据失败:', error);
        document.getElementById('assets-tbody').innerHTML = `
            <tr class="empty-row">
                <td colspan="10">❌ 加载数据失败: ${error.message}</td>
            </tr>
        `;
    } finally {
        isLoading = false;
    }
}

// ===== 渲染表格 =====
function renderTable(items) {
    const tbody = document.getElementById('assets-tbody');

    if (!items || items.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="10">
                    <div style="text-align:center;padding:2rem">
                        <div style="font-size:2.5rem;margin-bottom:0.5rem">📭</div>
                        <div style="color:#64748b;font-size:0.9rem">暂无数据，请调整搜索条件或 <button onclick="openAddModal()" style="color:#667eea;background:none;border:none;cursor:pointer;font-size:0.9rem;font-weight:600">新增访问关系记录</button></div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = items.map(item => {
        const srcIp = (item.src_ip || '').replace(/\n/g, '\n');
        const port = (item.port || '').replace(/\n/g, '\n');
        const protocol = (item.protocol || 'TCP').toUpperCase();
        const protocolClass = protocol.toLowerCase();

        return `
        <tr>
            <td><span class="sys-badge">${escHtml(item.src_system)}</span></td>
            <td>${escHtml(item.src_system_name || '')}</td>
            <td style="font-family:monospace;font-size:0.8rem">${escHtml(item.src_deploy_unit || '')}</td>
            <td class="ip-cell">${escHtml(srcIp)}</td>
            <td><span class="sys-badge">${escHtml(item.dst_system)}</span></td>
            <td style="font-family:monospace;font-size:0.8rem">${escHtml(item.dst_deploy_unit || '')}</td>
            <td class="ip-cell">${escHtml(item.dst_ip || '')}</td>
            <td><span class="protocol-badge ${protocolClass}">${escHtml(protocol)}</span></td>
            <td class="port-cell">${escHtml(port)}</td>
            <td>
                <button class="btn-delete" onclick="openDeleteModal(${item.id})" title="删除此记录">🗑</button>
            </td>
        </tr>
        `;
    }).join('');
}

// ===== 渲染分页 =====
function renderPagination(total, page) {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(total / PAGE_SIZE);

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    // 上一页
    html += `<button class="page-btn" onclick="loadAssets(${page - 1})" ${page <= 1 ? 'disabled' : ''}>‹</button>`;

    // 页码按钮（最多显示7个）
    let start = Math.max(1, page - 3);
    let end = Math.min(totalPages, start + 6);
    if (end - start < 6) start = Math.max(1, end - 6);

    if (start > 1) {
        html += `<button class="page-btn" onclick="loadAssets(1)">1</button>`;
        if (start > 2) html += `<span style="color:#94a3b8;padding:0 0.25rem">…</span>`;
    }

    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn ${i === page ? 'active' : ''}" onclick="loadAssets(${i})">${i}</button>`;
    }

    if (end < totalPages) {
        if (end < totalPages - 1) html += `<span style="color:#94a3b8;padding:0 0.25rem">…</span>`;
        html += `<button class="page-btn" onclick="loadAssets(${totalPages})">${totalPages}</button>`;
    }

    // 下一页
    html += `<button class="page-btn" onclick="loadAssets(${page + 1})" ${page >= totalPages ? 'disabled' : ''}>›</button>`;

    pagination.innerHTML = html;
}

// ===== 更新统计 =====
function updateStats(total, page) {
    document.getElementById('stats-total').innerHTML = `共 <strong>${total}</strong> 条记录`;
    document.getElementById('stats-page').innerHTML = `第 <strong>${page}</strong> 页`;
}

// ===== 搜索 =====
function doSearch() {
    loadAssets(1);
}

function resetSearch() {
    document.getElementById('filter-src').value = '';
    document.getElementById('filter-dst').value = '';
    document.getElementById('filter-keyword').value = '';
    document.getElementById('filter-protocol').value = '';
    loadAssets(1);
}

// ===== 新增弹框 =====
function openAddModal() {
    document.getElementById('add-form').reset();
    document.getElementById('add-modal').classList.add('open');
    document.getElementById('f-src-system').focus();
}

function closeAddModal() {
    document.getElementById('add-modal').classList.remove('open');
}

function closeModalOnOverlay(event) {
    if (event.target === event.currentTarget) {
        event.currentTarget.classList.remove('open');
    }
}

async function submitAddForm(e) {
    if (e) e.preventDefault();

    const srcSystem = document.getElementById('f-src-system').value.trim();
    const dstSystem = document.getElementById('f-dst-system').value.trim();

    if (!srcSystem) {
        showToast('请填写源物理子系统代码', 'error');
        document.getElementById('f-src-system').focus();
        return;
    }
    if (!dstSystem) {
        showToast('请填写目的物理子系统代码', 'error');
        document.getElementById('f-dst-system').focus();
        return;
    }

    const submitBtn = document.getElementById('submit-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = '保存中...';

    const payload = {
        src_system: srcSystem,
        src_system_name: document.getElementById('f-src-system-name').value.trim(),
        src_deploy_unit: document.getElementById('f-src-deploy-unit').value.trim(),
        src_ip: document.getElementById('f-src-ip').value.trim(),
        dst_system: dstSystem,
        dst_deploy_unit: document.getElementById('f-dst-deploy-unit').value.trim(),
        dst_ip: document.getElementById('f-dst-ip').value.trim(),
        protocol: document.getElementById('f-protocol').value,
        port: document.getElementById('f-port').value.trim()
    };

    try {
        const response = await fetch('/api/v1/assets/access-relations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }

        showToast('✅ 访问关系记录已创建成功', 'success');
        closeAddModal();
        loadAssets(1);

    } catch (error) {
        console.error('新增失败:', error);
        showToast(`❌ 新增失败: ${error.message}`, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '✓ 保存';
    }
}

// ===== 删除弹框 =====
function openDeleteModal(assetId) {
    pendingDeleteId = assetId;
    document.getElementById('delete-confirm-text').textContent =
        `确定要删除 ID为 ${assetId} 的访问关系记录吗？此操作不可撤销。`;
    document.getElementById('delete-modal').classList.add('open');
}

function closeDeleteModal() {
    pendingDeleteId = null;
    document.getElementById('delete-modal').classList.remove('open');
}

async function confirmDelete() {
    if (!pendingDeleteId) return;

    const btn = document.getElementById('confirm-delete-btn');
    btn.disabled = true;
    btn.textContent = '删除中...';

    try {
        const response = await fetch(`/api/v1/assets/access-relations/${pendingDeleteId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }

        showToast('🗑 记录已删除', 'success');
        closeDeleteModal();
        loadAssets(currentPage);

    } catch (error) {
        console.error('删除失败:', error);
        showToast(`❌ 删除失败: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🗑 确认删除';
    }
}

// ===== Toast 提示 =====
let toastTimer = null;
function showToast(message, type = '') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;

    // Force reflow
    void toast.offsetWidth;
    toast.classList.add('show');

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ===== 工具函数 =====
function escHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text || '');
    return div.innerHTML;
}
