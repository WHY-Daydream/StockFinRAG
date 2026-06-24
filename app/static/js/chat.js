const SESSIONS_KEY = 'finrag_sessions';
const CURRENT_KEY = 'finrag_current_session';
const MAX_SESSIONS = 50;

function getSessions() {
    try {
        return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]');
    } catch (e) {
        return [];
    }
}

function saveSessions(sessions) {
    try {
        // 限制最大会话数，防止 localStorage 溢出
        if (sessions.length > MAX_SESSIONS) {
            sessions = sessions.slice(0, MAX_SESSIONS);
        }
        localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    } catch (e) {
        // localStorage 不可用或已满，静默忽略
    }
}

function getCurrentSession() {
    try {
        return localStorage.getItem(CURRENT_KEY) || '';
    } catch (e) {
        return '';
    }
}

function setCurrentSession(id) {
    try {
        localStorage.setItem(CURRENT_KEY, id);
    } catch (e) {}
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
              style="display:flex;align-items:center;padding:4px 12px;border-radius:6px;margin-bottom:4px;
                     ${s.id === current ? 'background:#e6f4ff' : 'background:#fff'}">
          <span onclick="switchSession('${s.id}')"
                style="flex:1;cursor:pointer;font-size:13px;padding:4px 0;color:${s.id === current ? '#1677ff' : '#333'}">
            ${s.preview || '新会话'}
          </span>
          <span onclick="deleteSession('${s.id}')"
                style="cursor:pointer;font-size:12px;color:#ccc;padding:2px 6px;border-radius:4px;"
                onmouseover="this.style.color='#ff4d4f';this.style.background='#fff1f0'"
                onmouseout="this.style.color='#ccc';this.style.background='transparent'"
                title="删除会话">✕</span>
         </div>`
    ).join('');
}

function deleteSession(id) {
    let sessions = getSessions();
    sessions = sessions.filter(s => s.id !== id);
    saveSessions(sessions);
    const current = getCurrentSession();
    if (current === id) {
        if (sessions.length > 0) {
            setCurrentSession(sessions[0].id);
            loadMessages(sessions[0].id);
        } else {
            setCurrentSession('');
            clearMessages();
        }
    }
    renderSessionList();
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

function saveMessage(role, content, compliance, compliance_reason) {
    const id = getCurrentSession();
    if (!id) return;
    const sessions = getSessions();
    const idx = sessions.findIndex(s => s.id === id);
    if (idx === -1) return;
    if (!sessions[idx].messages) sessions[idx].messages = [];
    sessions[idx].messages.push({ role, content, compliance, compliance_reason });
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
                : m.compliance ? `<div class="compliance-reject">⛔ ${escapeHtml(m.compliance_reason || '合规未通过')}</div>` : '';
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

function getRecentHistory() {
    const sessions = getSessions();
    const current = getCurrentSession();
    const session = sessions.find(s => s.id === current);
    if (!session || !session.messages || session.messages.length === 0) return [];
    // 取最近 6 条（3 轮对话）
    const recent = session.messages.slice(-6);
    return recent.map(function(m) { return { role: m.role, content: m.content }; });
}

function sendQuestionStream() {
    var input = document.getElementById('question-input');
    var question = input.value.trim();
    if (!question) return;
    var container = document.getElementById('chat-messages');
    var btn = document.getElementById('send-btn');
    input.value = '';
    btn.disabled = true;

    container.innerHTML += '<div class="message message-user"><div class="bubble">' + escapeHtml(question) + '</div></div>';
    saveMessage('user', question, null);

    var STEPS = [
        { id: 'step-search',  label: '\u{1F50D} 检索知识库' },
        { id: 'step-analyze', label: '\u{1F914} AI 分析问题' },
        { id: 'step-comply',  label: '✅ 合规审核' },
    ];
    var bubbleId = 'stream-bubble';

    var stepsHtml = STEPS.map(function(s, i) {
        return '<div id="' + s.id + '" style="padding:4px 0;display:flex;align-items:center;gap:8px;opacity:' + (i===0?'1':'0.4') + '">' +
            '<span class="step-indicator ' + (i===0?'step-active':'') + '" style="width:20px;text-align:center">' +
                (i===0 ? '<span class="step-hourglass">⏳</span>' : '○') +
            '</span>' +
            '<span>' + s.label + '</span></div>';
    }).join('');

    container.innerHTML += '<div class="message message-assistant" id="loading-msg">' +
        '<div class="bubble" style="min-width:220px">' + stepsHtml +
            '<div id="' + bubbleId + '" style="margin-top:8px;padding-top:8px;border-top:1px solid #eee;min-height:20px">' +
            '</div></div></div>';
    container.scrollTop = container.scrollHeight;

    var sessionId = getCurrentSession();
    if (!sessionId) {
        sessionId = generateId();
        setCurrentSession(sessionId);
        var sessions = getSessions();
        sessions.unshift({ id: sessionId, preview: question.slice(0, 30), created: Date.now() });
        saveSessions(sessions);
        renderSessionList();
    }

    function updateStep(stepName) {
        var map = { retrieving: 0, analyzing: 1, checking: 2 };
        var idx = map[stepName];
        if (idx === undefined) return;
        if (idx > 0) {
            var prev = document.getElementById(STEPS[idx-1].id);
            if (prev) { prev.querySelector('.step-indicator').textContent = '✅'; prev.style.opacity = '0.6'; }
        }
        var cur = document.getElementById(STEPS[idx].id);
        if (cur) { cur.style.opacity = '1'; cur.querySelector('.step-indicator').innerHTML = '<span class="step-hourglass">⏳</span>'; }
        container.scrollTop = container.scrollHeight;
    }

    function finishSteps() {
        STEPS.forEach(function(s, i) {
            var el = document.getElementById(s.id);
            if (el) { el.querySelector('.step-indicator').textContent = '✅'; el.style.opacity = i < STEPS.length-1 ? '0.6' : '1'; }
        });
    }

    fetch('/api/ask/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question, session_id: sessionId, history: getRecentHistory() }),
    })
    .then(function(response) {
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var answerText = '';
        var eventType = '';

        function processChunk() {
            var lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (var l = 0; l < lines.length; l++) {
                var line = lines[l];
                if (line.startsWith('event: ')) { eventType = line.slice(7).trim(); }
                else if (line.startsWith('data: ')) {
                    var data = line.slice(6);
                    if (eventType === 'step') { updateStep(data); }
                    else if (eventType === 'token') {
                        answerText += data.replace(/\\n/g, '\n');
                        document.getElementById(bubbleId).innerHTML = marked.parse(answerText) + '<span class="stream-cursor">|</span>';
                        container.scrollTop = container.scrollHeight;
                    } else if (eventType === 'done') {
                        var result = JSON.parse(data);
                        finishSteps();
                        var complianceHtml = result.compliance === 'pass' ? '<div class="compliance-pass">✅ 合规审核通过</div>' : '<div class="compliance-reject">⛔ ' + escapeHtml(result.compliance_reason || '') + '</div>';
                        document.getElementById(bubbleId).innerHTML = marked.parse(result.answer) + complianceHtml;
                        saveMessage('assistant', result.answer || '', result.compliance || '', result.compliance_reason || '');
                        container.scrollTop = container.scrollHeight;
                    }
                }
            }
        }

        function read() {
            return reader.read().then(function(res) {
                if (res.done) return;
                buffer += decoder.decode(res.value, { stream: true });
                processChunk();
                return read();
            });
        }
        return read();
    })
    .catch(function(err) {
        var el = document.getElementById(bubbleId);
        if (el) el.innerHTML = '<div style="color:#ff4d4f">❗ 请求失败: ' + escapeHtml(err.message) + '</div>';
        finishSteps();
    })
    .finally(function() { btn.disabled = false; input.focus(); });
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

    // 进度清单：每一步完成后保留打勾，不走回头路
    const STEPS = [
        { id: 'step-search',  label: '检索知识库', icon: '🔍' },
        { id: 'step-analyze', label: 'AI 分析问题', icon: '🤔' },
        { id: 'step-comply',  label: '合规审核', icon: '✅' },
    ];
    container.innerHTML += `<div class="message message-assistant" id="loading-msg">
        <div class="bubble loading-pulse" style="min-width:220px">
            ${STEPS.map((s, i) => `
                <div id="${s.id}" style="padding:4px 0;display:flex;align-items:center;gap:8px;
                    ${i === 0 ? 'opacity:1' : 'opacity:0.4'}">
                    <span class="step-indicator ${i === 0 ? 'step-active' : ''}" style="width:20px;text-align:center">
                        ${i === 0 ? '<span class="step-hourglass">⏳</span>' : '○'}
                    </span>
                    <span>${s.icon} ${s.label}</span>
                </div>
            `).join('')}
        </div></div>`;
    container.scrollTop = container.scrollHeight;
    // 逐步骤亮起
    let currentStep = 0;
    const advanceStep = function() {
        currentStep++;
        if (currentStep < STEPS.length) {
            // 完成上一步：绿色打勾，去除动画
            const prev = document.getElementById(STEPS[currentStep - 1].id);
            if (prev) {
                prev.querySelector('.step-indicator').innerHTML = '✅';
                prev.querySelector('.step-indicator').className = 'step-indicator';
                prev.style.opacity = '0.6';
                prev.style.color = '#52c41a';
            }
            // 激活当前步：旋转 ⏳
            const cur = document.getElementById(STEPS[currentStep].id);
            if (cur) {
                cur.style.opacity = '1';
                cur.style.color = '';
                cur.querySelector('.step-indicator').className = 'step-indicator step-active';
                cur.querySelector('.step-indicator').innerHTML = '<span class="step-hourglass">⏳</span>';
            }
        }
    };
    window._loadingTimer = setInterval(advanceStep, 3500);
    // 完成后全部打勾
    window._finishSteps = function() {
        if (window._loadingTimer) { clearInterval(window._loadingTimer); window._loadingTimer = null; }
        STEPS.forEach(function(s, i) {
            const el = document.getElementById(s.id);
            if (el) {
                el.querySelector('.step-indicator').textContent = '✅';
                el.style.opacity = i < STEPS.length - 1 ? '0.6' : '1';
                el.style.color = '#52c41a';
            }
        });
    };

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
        body: JSON.stringify({ question, session_id: sessionId, history: getRecentHistory() }),
    })
    .then(r => r.json())
    .then(data => {
        if (window._finishSteps) window._finishSteps();
        const loading = document.getElementById('loading-msg');
        if (loading) loading.remove();
        const complianceHtml = data.compliance === 'pass'
            ? '<div class="compliance-pass">✅ 合规审核通过</div>'
            : `<div class="compliance-reject">⛔ ${escapeHtml(data.compliance_reason || '合规未通过')}</div>`;
        container.innerHTML += `<div class="message message-assistant"><div class="bubble">
            ${marked.parse(data.answer || '(无回答)')}${complianceHtml}</div></div>`;
        saveMessage('assistant', data.answer || '(无回答)', data.compliance || '', data.compliance_reason || '');
        container.scrollTop = container.scrollHeight;
    })
    .catch(err => {
        if (window._finishSteps) window._finishSteps();
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
