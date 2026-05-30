// --- Utility: UUID Generator ---
function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// --- State Management ---
let sessionId = localStorage.getItem('trilium_session_id');
if (!sessionId) {
    sessionId = uuidv4();
    localStorage.setItem('trilium_session_id', sessionId);
}
document.getElementById('session-display').innerText = sessionId.substring(0, 8);

function getApiKey() {
    return document.getElementById('api-key-input').value;
}

// --- UI Components ---
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const toastContainer = document.getElementById('toast-container');

// Markdown Configuration
marked.setOptions({
    gfm: true,
    breaks: true,
    headerIds: false,
    mangle: false
});

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = type === 'error' ? '⚠️' : '✅';
    toast.innerHTML = `
        <div style="font-size: 1.2rem;">${icon}</div>
        <div style="flex:1;">
            <div style="font-weight:600; font-size:0.9rem; margin-bottom:4px;">${type === 'error' ? '错误' : '成功'}</div>
            <div style="font-size:0.85rem; color:var(--text-muted);">${message}</div>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// --- Status Polling ---
async function fetchStatus() {
    try {
        const res = await fetch('/api/v1/health');
        const data = await res.json();
        
        const updateBadge = (id, status) => {
            const el = document.getElementById(id);
            el.className = 'badge';
            if (status === 'available') {
                el.classList.add('success');
                el.innerText = '在线';
            } else if (status === 'degraded' || status === 'degraded (mocked)' || status === 'basic_fallback' || status === 'pending_initialization') {
                el.classList.add('warning');
                el.innerText = '降级/等待';
            } else if (status === 'advanced_cross_encoder') {
                el.classList.add('success');
                el.innerText = '高级重排';
            } else {
                el.classList.add('danger');
                el.innerText = '离线';
            }
        };

        updateBadge('status-llm', data.components.llm);
        updateBadge('status-vector', data.components.vector_db);
        updateBadge('status-reranker', data.components.reranker);

    } catch (e) {
        document.querySelectorAll('.badge').forEach(el => {
            el.className = 'badge danger';
            el.innerText = '失联';
        });
    }
}
// Initial poll and set interval
fetchStatus();
setInterval(fetchStatus, 10000);

// --- Chat Logic ---

function appendMessage(role, contentHtml, isRaw = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    
    const avatarSvg = role === 'user' 
        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';
    if (isRaw) {
        contentDiv.innerHTML = DOMPurify.sanitize(marked.parse(contentHtml));
    } else {
        contentDiv.appendChild(contentHtml); // Handle DOM nodes (like thought process)
    }

    msgDiv.innerHTML = `<div class="avatar">${avatarSvg}</div>`;
    msgDiv.appendChild(contentDiv);
    
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return contentDiv;
}

function appendTyping() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system typing';
    msgDiv.innerHTML = `
        <div class="avatar"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg></div>
        <div class="content" style="padding: 12px 20px;">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return msgDiv;
}

function buildThoughtProcess(sources) {
    if (!sources || sources.length === 0) return '';
    
    let sourceHtml = sources.map(s => {
        let title = s.title || '无标题文档';
        let score = s.score !== undefined ? `<span style="opacity:0.5; margin-left:4px;">[Score: ${s.score.toFixed(3)}]</span>` : '';
        return `<a href="#" class="source-item" title="${s.content.substring(0, 100)}...">📄 ${title} ${score}</a>`;
    }).join('');

    return `
        <div class="thought-process">
            <div class="thought-header" onclick="this.nextElementSibling.classList.toggle('open')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
                思考过程: 混合检索出 ${sources.length} 篇相关文档
            </div>
            <div class="thought-content">
                <div style="margin-bottom: 8px;">根据语义和关键字，从知识库中锁定以下参考资料:</div>
                <div class="sources">${sourceHtml}</div>
            </div>
        </div>
    `;
}

async function handleSend() {
    const question = chatInput.value.trim();
    if (!question) return;

    // UI Updates
    chatInput.value = '';
    chatInput.style.height = 'auto';
    btnSend.disabled = true;
    
    appendMessage('user', question, true);
    const typingIndicator = appendTyping();

    try {
        const res = await fetch('/api/v1/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': getApiKey()
            },
            body: JSON.stringify({ question, session_id: sessionId })
        });

        typingIndicator.remove();

        const data = await res.json();
        
        if (!res.ok) {
            let errorMsg = data.detail || '发生未知错误';
            if (data.error_code) {
                errorMsg = `[${data.error_code}] ${errorMsg}`;
            }
            showToast(errorMsg, 'error');
            appendMessage('system', `⚠️ **抱歉，处理失败**\n\n\`\`\`text\n${errorMsg}\n\`\`\``, true);
            return;
        }

        const container = document.createElement('div');
        // Thought process
        if (data.sources && data.sources.length > 0) {
            container.innerHTML += buildThoughtProcess(data.sources);
        }
        // Answer
        const answerDiv = document.createElement('div');
        answerDiv.innerHTML = DOMPurify.sanitize(marked.parse(data.answer));
        container.appendChild(answerDiv);

        appendMessage('system', container, false);

    } catch (e) {
        typingIndicator.remove();
        showToast('网络连接失败，无法连接到后端服务器', 'error');
    } finally {
        btnSend.disabled = false;
        chatInput.focus();
    }
}

// --- Event Listeners ---

chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

btnSend.addEventListener('click', handleSend);

document.getElementById('btn-clear').addEventListener('click', async () => {
    try {
        await fetch(`/api/v1/session/${sessionId}`, {
            method: 'DELETE',
            headers: { 'X-API-Key': getApiKey() }
        });
        
        // Refresh session
        sessionId = uuidv4();
        localStorage.setItem('trilium_session_id', sessionId);
        document.getElementById('session-display').innerText = sessionId.substring(0, 8);
        
        // Clear UI
        const msgs = document.querySelectorAll('.message:not(:first-child)');
        msgs.forEach(m => m.remove());
        
        showToast('会话上下文已清空，并已为您分配全新的 Session ID');
    } catch (e) {
        showToast('清除会话失败', 'error');
    }
});

document.getElementById('btn-sync').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    const oldText = btn.innerHTML;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-8.31l-5.67-1.25"/></svg> 同步触发中...`;
    
    try {
        const res = await fetch('/api/v1/sync', {
            method: 'POST',
            headers: { 'X-API-Key': getApiKey() }
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || '同步失败');
        
        showToast(data.message, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setTimeout(() => {
            btn.innerHTML = oldText;
            btn.disabled = false;
        }, 1500);
    }
});

// Add spin animation dynamically for the sync button
const style = document.createElement('style');
style.textContent = `
    @keyframes spin { 100% { transform: rotate(360deg); } }
    .spin { animation: spin 1s linear infinite; }
`;
document.head.appendChild(style);
