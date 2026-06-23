const SESSIONS_KEY = 'finrag_sessions';
const CURRENT_KEY = 'finrag_current_session';

function getSessions() {
    return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]');
}

function saveSessions(sessions) {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

function getCurrentSession() {
    return localStorage.getItem(CURRENT_KEY) || '';
}

function setCurrentSession(id) {
    localStorage.setItem(CURRENT_KEY, id);
}

function generateId() {
    return 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4);
}

function renderSessionList() {
    const list = document.getElementById('session-list');
    const sessions = getSessions();
    const current = getCurrentSession();
    if (sessions.length === 0) {
        list.innerHTML = '<div style="color:#aaa;font-size:13px;padding:8px;text-align:center">暂无历史会话</div>';
        return;
    }
    list.innerHTML = sessions.map(s =>
        `<div class="session-item ${s.id === current ? 'active' : ''}"
              onclick="switchSession('${s.id}')"
              style="padding:8px 12px;border-radius:6px;cursor:pointer;font-size:13px;margin-bottom:4px;
                     ${s.id === current ? 'background:#e6f4ff;color:#1677ff' : 'background:#fff'}">
          ${s.preview || '新会话'}
         </div>`
    ).join('');
}

function switchSession(id) {
    setCurrentSession(id);
    renderSessionList();
    loadMessages(id);
}

function newSession() {
    const id = generateId();
    setCurrentSession(id);
    const sessions = getSessions();
    sessions.unshift({ id, preview: '新会话', created: Date.now() });
    saveSessions(sessions);
    renderSessionList();
    clearMessages();
}

function saveMessage(role, content, compliance) {
    const id = getCurrentSession();
    if (!id) return;
    const sessions = getSessions();
    const idx = sessions.findIndex(s => s.id === id);
    if (idx === -1) return;
    if (!sessions[idx].messages) sessions[idx].messages = [];
    sessions[idx].messages.push({ role, content, compliance });
    sessions[idx].preview = content.slice(0, 30) + (content.length > 30 ? '...' : '');
    saveSessions(sessions);
}

function loadMessages(sessionId) {
    const container = document.getElementById('chat-messages');
    const sessions = getSessions();
    const session = sessions.find(s => s.id === sessionId);
    container.innerHTML = '';
    if (!session || !session.messages || session.messages.length === 0) {
        container.innerHTML = '<div class="message message-assistant"><div class="bubble">👋 你好！请提出你的金融相关问题。</div></div>';
        return;
    }
    session.messages.forEach(m => {
        if (m.role === 'user') {
            container.innerHTML += `<div class="message message-user"><div class="bubble">${escapeHtml(m.content)}</div></div>`;
        } else {
            const complianceHtml = m.compliance === 'pass'
                ? '<div class="compliance-pass">✅ 合规审核通过</div>'
                : m.compliance ? `<div class="compliance-reject">⛔ ${escapeHtml(m.compliance)}</div>` : '';
            container.innerHTML += `<div class="message message-assistant"><div class="bubble">${marked.parse(m.content)}${complianceHtml}</div></div>`;
        }
    });
    container.scrollTop = container.scrollHeight;
}

function clearMessages() {
    const container = document.getElementById('chat-messages');
    container.innerHTML = '<div class="message message-assistant"><div class="bubble">👋 你好！请提出你的金融相关问题。</div></div>';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sendQuestion() {
    const input = document.getElementById('question-input');
    const question = input.value.trim();
    if (!question) return;

    const container = document.getElementById('chat-messages');
    const btn = document.getElementById('send-btn');
    input.value = '';
    btn.disabled = true;

    container.innerHTML += `<div class="message message-user"><div class="bubble">${escapeHtml(question)}</div></div>`;
    saveMessage('user', question, null);

    container.innerHTML += `<div class="message message-assistant" id="loading-msg">
        <div class="bubble">⏳ 正在检索分析...</div></div>`;
    container.scrollTop = container.scrollHeight;

    let sessionId = getCurrentSession();
    if (!sessionId) {
        sessionId = generateId();
        setCurrentSession(sessionId);
        const sessions = getSessions();
        sessions.unshift({ id: sessionId, preview: question.slice(0, 30), created: Date.now() });
        saveSessions(sessions);
        renderSessionList();
    }

    fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: sessionId }),
    })
    .then(r => r.json())
    .then(data => {
        const loading = document.getElementById('loading-msg');
        if (loading) loading.remove();
        const complianceHtml = data.compliance === 'pass'
            ? '<div class="compliance-pass">✅ 合规审核通过</div>'
            : `<div class="compliance-reject">⛔ ${escapeHtml(data.compliance_reason || '合规未通过')}</div>`;
        container.innerHTML += `<div class="message message-assistant"><div class="bubble">
            ${marked.parse(data.answer || '(无回答)')}${complianceHtml}</div></div>`;
        saveMessage('assistant', data.answer || '(无回答)', data.compliance || '');
        container.scrollTop = container.scrollHeight;
    })
    .catch(err => {
        const loading = document.getElementById('loading-msg');
        if (loading) loading.remove();
        container.innerHTML += `<div class="message message-assistant"><div class="bubble">❌ 请求失败：${escapeHtml(err.message)}</div></div>`;
        container.scrollTop = container.scrollHeight;
    })
    .finally(() => { btn.disabled = false; input.focus(); });
}

document.addEventListener('DOMContentLoaded', function() {
    renderSessionList();
    const current = getCurrentSession();
    if (current) loadMessages(current);
});
