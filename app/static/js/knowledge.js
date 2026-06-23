let allDocs = [];

function loadDocs() {
    fetch('/api/documents')
        .then(r => r.json())
        .then(data => {
            allDocs = data.documents || [];
            renderDocs();
        })
        .catch(() => { document.getElementById('doc-tbody').innerHTML = '<tr><td colspan="6" style="text-align:center;color:red">加载失败</td></tr>'; });
}

function renderDocs() {
    const query = (document.getElementById('search-input').value || '').trim().toLowerCase();
    const typeFilter = document.getElementById('type-filter').value;
    let filtered = allDocs;
    if (query) filtered = filtered.filter(d => (d.title || '').toLowerCase().includes(query));
    if (typeFilter) filtered = filtered.filter(d => d.doc_type === typeFilter);
    document.getElementById('doc-count').textContent = `共 ${filtered.length} 篇`;
    const tbody = document.getElementById('doc-tbody');
    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#aaa">暂无文档</td></tr>';
        return;
    }
    tbody.innerHTML = filtered.map(d => {
        const tagClass = { '政策': 'tag-policy', '法规': 'tag-regulation', '新闻': 'tag-news', '知识': 'tag-knowledge' }[d.doc_type] || '';
        const hasChunks = (d.chunk_count || 0) > 0;
        return `<tr>
            <td><a href="#" onclick="viewDoc(${d.id});return false" style="color:#1677ff">${escapeHtml(d.title || '')}</a></td>
            <td><span class="tag ${tagClass}">${d.doc_type || '-'}</span></td>
            <td style="font-size:13px">${escapeHtml(d.source || '-')}</td>
            <td style="font-size:13px">${d.pub_date || '-'}</td>
            <td style="font-size:13px">${d.chunk_count || 0}</td>
            <td><span class="status-dot ${hasChunks ? 'green' : 'gray'}"></span>${hasChunks ? '已向量化' : '待处理'}</td>
        </tr>`;
    }).join('');
}

function searchDocs() { renderDocs(); }

function escapeHtml(t) {
    const div = document.createElement('div');
    div.textContent = t;
    return div.innerHTML;
}

function showStatus(msg, isError) {
    const el = document.getElementById('action-status');
    el.textContent = msg;
    el.style.color = isError ? '#ff4d4f' : '#52c41a';
    setTimeout(() => { el.textContent = ''; }, 5000);
}

function seedData() {
    fetch('/api/seed', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
        .then(r => r.json()).then(d => {
            showStatus(d.message || '导入完成');
            if (d.vectorized > 0) setTimeout(loadDocs, 2000);
        }).catch(e => showStatus('失败: ' + e.message, true));
}

function crawlData() {
    fetch('/api/crawl', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
        .then(r => r.json()).then(d => showStatus(d.message || '爬取完成'))
        .catch(e => showStatus('失败: ' + e.message, true));
}

function vectorizeData() {
    fetch('/api/ingest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({limit: 50}) })
        .then(r => r.json()).then(d => {
            showStatus(`向量化完成: ${d.processed} 篇`);
            setTimeout(loadDocs, 1000);
        }).catch(e => showStatus('失败: ' + e.message, true));
}

function viewDoc(id) {
    const doc = allDocs.find(d => d.id === id);
    if (doc) alert(`标题: ${doc.title}\n类型: ${doc.doc_type}\n来源: ${doc.source}\n摘要: ${doc.summary_short || '(无摘要)'}`);
}

document.addEventListener('DOMContentLoaded', loadDocs);
