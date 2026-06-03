/* ==============================================================================
   Trilium Knowledge Agent - Gemini Web Style 前端核心交互逻辑
   ============================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // ==========================================
    // 1. 全局状态与选择器缓存
    // ==========================================
    let currentSessionId = generateUUID();
    let currentSourcesMap = {}; // 缓存当前提问召回的来源，用于弹窗详情展示
    let isGenerating = false;
    let cachedTriliumBaseUrl = "http://localhost:8080"; // 默认 Trilium 基准网页地址

    // 常规 UI 选择器
    const chatHistory = document.getElementById("chat-history");
    const chatInput = document.getElementById("chat-input");
    const btnSend = document.getElementById("btn-send");
    const sessionDisplay = document.getElementById("session-display");
    const btnClearCurrent = document.getElementById("btn-clear-current");
    const btnThemeToggle = document.getElementById("btn-theme-toggle");
    const apiKeyInput = document.getElementById("api-key-input");
    const btnSync = document.getElementById("btn-sync");
    const btnNewChat = document.getElementById("btn-new-chat");
    const sessionHistoryList = document.getElementById("session-history-list");

    // 移动端自适应专用选择器
    const sidebar = document.querySelector(".sidebar");
    const btnSidebarToggle = document.getElementById("btn-sidebar-toggle");
    const btnSidebarClose = document.getElementById("btn-sidebar-close");
    const sidebarOverlay = document.getElementById("sidebar-overlay");

    // 系统状态监测小盘选择器
    const statusLlm = document.getElementById("status-llm");
    const statusLlmDot = document.getElementById("status-llm-dot");
    const statusVector = document.getElementById("status-vector");
    const statusVectorDot = document.getElementById("status-vector-dot");

    // 设置抽屉相关选择器
    const btnSettingsOpen = document.getElementById("btn-settings-open");
    const btnSettingsClose = document.getElementById("btn-settings-close");
    const btnSettingsCancel = document.getElementById("btn-settings-cancel");
    const btnSettingsSave = document.getElementById("btn-settings-save");
    const settingsDrawer = document.getElementById("settings-drawer");
    const settingsForm = document.getElementById("settings-form");

    // 设置表单元素选择器
    const cfgLlmType = document.getElementById("cfg-llm-type");
    const cfgLlmPath = document.getElementById("cfg-llm-path");
    const cfgApiBase = document.getElementById("cfg-api-base");
    const cfgTriliumUrl = document.getElementById("cfg-trilium-url");
    const cfgOpenaiKey = document.getElementById("cfg-openai-key");
    const cfgDeepseekKey = document.getElementById("cfg-deepseek-key");
    const cfgGeminiKey = document.getElementById("cfg-gemini-key");
    const cfgUseReranker = document.getElementById("cfg-use-reranker");
    const cfgRerankerThreshold = document.getElementById("cfg-reranker-threshold");
    const cfgSearchK = document.getElementById("cfg-search-k");
    const valRerankerThreshold = document.getElementById("val-reranker-threshold");
    const valSearchK = document.getElementById("val-search-k");

    // 切片详情预览弹窗选择器
    const previewModal = document.getElementById("preview-modal");
    const btnModalClose = document.getElementById("btn-modal-close");
    const btnModalCloseFooter = document.getElementById("btn-modal-close-footer");
    const btnModalJump = document.getElementById("btn-modal-jump");
    const previewPath = document.getElementById("preview-path");
    const previewScore = document.getElementById("preview-score");
    const previewNoteId = document.getElementById("preview-note-id");
    const previewBody = document.getElementById("preview-body");

    // ==========================================
    // 2. 初始化流程
    // ==========================================
    initTheme();
    loadApiKeyFromStorage();
    updateSessionIdDisplay();
    refreshSystemStatus();
    loadSessionHistory();

    // Markdown 解析参数高级微调
    marked.setOptions({
        breaks: true,
        highlight: function (code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        }
    });

    // ==========================================
    // 3. 事件绑定
    // ==========================================
    
    // 主题切换
    btnThemeToggle.addEventListener("click", toggleTheme);

    // 移动端自适应侧边栏控制事件绑定
    btnSidebarToggle.addEventListener("click", openSidebar);
    btnSidebarClose.addEventListener("click", closeSidebar);
    sidebarOverlay.addEventListener("click", closeSidebar);

    function openSidebar() {
        sidebar.classList.add("active");
        sidebarOverlay.classList.add("active");
        document.body.classList.add("no-scroll");
    }

    function closeSidebar() {
        sidebar.classList.remove("active");
        sidebarOverlay.classList.remove("active");
        // 只有当没有其他活跃的 Modal 或 Drawer 时才安全地移除 no-scroll 保护
        if (!settingsDrawer.classList.contains("active") && !previewModal.classList.contains("active")) {
            document.body.classList.remove("no-scroll");
        }
    }

    // 发送消息
    btnSend.addEventListener("click", handleSend);
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // 输入框自动撑高
    chatInput.addEventListener("input", () => {
        chatInput.style.height = "auto";
        chatInput.style.height = (chatInput.scrollHeight) + "px";
    });

    // 清除当前会话上下文
    btnClearCurrent.addEventListener("click", clearCurrentSessionContext);

    // 凭证变动本地自动保存
    apiKeyInput.addEventListener("input", () => {
        localStorage.setItem("trilium_agent_api_key", apiKeyInput.value.strip());
    });

    // 触发知识库同步
    btnSync.addEventListener("click", triggerKbSync);

    // 新建会话
    btnNewChat.addEventListener("click", handleNewChat);

    // 抽屉展开/收起
    btnSettingsOpen.addEventListener("click", openSettingsDrawer);
    btnSettingsClose.addEventListener("click", closeSettingsDrawer);
    btnSettingsCancel.addEventListener("click", closeSettingsDrawer);
    settingsDrawer.addEventListener("click", (e) => {
        if (e.target === settingsDrawer) closeSettingsDrawer();
    });

    // 抽屉滑动条数值映射
    cfgRerankerThreshold.addEventListener("input", (e) => {
        valRerankerThreshold.textContent = parseFloat(e.target.value).toFixed(2);
    });
    cfgSearchK.addEventListener("input", (e) => {
        valSearchK.textContent = e.target.value;
    });

    // 抽屉保存
    btnSettingsSave.addEventListener("click", saveSettings);

    // 弹窗关闭
    btnModalClose.addEventListener("click", closePreviewModal);
    btnModalCloseFooter.addEventListener("click", closePreviewModal);
    previewModal.addEventListener("click", (e) => {
        if (e.target === previewModal) closePreviewModal();
    });

    // ==========================================
    // 4. 业务逻辑方法实现
    // ==========================================

    // 获取 Auth Token
    function getAuthToken() {
        return apiKeyInput.value.trim() || localStorage.getItem("trilium_agent_api_key") || "";
    }

    // 保存 Auth Token 进输入框
    function loadApiKeyFromStorage() {
        const storedKey = localStorage.getItem("trilium_agent_api_key");
        if (storedKey) {
            apiKeyInput.value = storedKey;
        }
    }

    // 生成 UUID
    function generateUUID() {
        return 'session_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    }

    // 更新 Session ID 展示
    function updateSessionIdDisplay() {
        sessionDisplay.textContent = currentSessionId;
    }

    // Toast 弹窗通知
    function showToast(message, type = "success") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        
        let iconSvg = "";
        if (type === "success") {
            iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        } else if (type === "warning") {
            iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path></svg>`;
        } else {
            iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
        }

        toast.innerHTML = `${iconSvg}<span>${message}</span>`;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-10px)";
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // 刷新后端系统心跳状态
    async function refreshSystemStatus() {
        try {
            const token = getAuthToken();
            const response = await fetch("/api/v1/health", {
                headers: { "X-API-Key": token }
            });
            if (response.ok) {
                const data = await response.json();
                
                // 缓存后端反馈的 Trilium 地址
                if (data.trilium_base_url) {
                    cachedTriliumBaseUrl = data.trilium_base_url;
                }
                
                // 1. LLM 状态标志
                if (data.components.llm === "available") {
                    statusLlm.textContent = "已就绪";
                    statusLlmDot.className = "dot-indicator green";
                } else if (data.components.llm.includes("degraded")) {
                    statusLlm.textContent = "Mock降级";
                    statusLlmDot.className = "dot-indicator orange";
                } else {
                    statusLlm.textContent = "不可用";
                    statusLlmDot.className = "dot-indicator red";
                }

                // 2. Vector DB 状态标志
                if (data.components.vector_db === "available") {
                    statusVector.textContent = "正常";
                    statusVectorDot.className = "dot-indicator green";
                } else {
                    statusVector.textContent = "无索引";
                    statusVectorDot.className = "dot-indicator red";
                }
            } else {
                statusLlm.textContent = "未鉴权";
                statusLlmDot.className = "dot-indicator orange";
                statusVector.textContent = "未鉴权";
                statusVectorDot.className = "dot-indicator orange";
            }
        } catch (e) {
            statusLlm.textContent = "离线";
            statusLlmDot.className = "dot-indicator red";
            statusVector.textContent = "离线";
            statusVectorDot.className = "dot-indicator red";
        }
    }

    // 日夜主题切换逻辑
    function initTheme() {
        const savedTheme = localStorage.getItem("trilium_agent_theme") || "dark";
        document.documentElement.setAttribute("data-theme", savedTheme);
        updateThemeToggleButton(savedTheme);
    }

    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute("data-theme");
        const nextTheme = currentTheme === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", nextTheme);
        localStorage.setItem("trilium_agent_theme", nextTheme);
        updateThemeToggleButton(nextTheme);
    }

    function updateThemeToggleButton(theme) {
        const sunIcon = btnThemeToggle.querySelector(".sun-icon");
        const moonIcon = btnThemeToggle.querySelector(".moon-icon");
        const hlStyle = document.getElementById("hl-theme");

        if (theme === "dark") {
            sunIcon.style.display = "block";
            moonIcon.style.display = "none";
            if (hlStyle) hlStyle.href = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark-dimmed.min.css";
        } else {
            sunIcon.style.display = "none";
            moonIcon.style.display = "block";
            if (hlStyle) hlStyle.href = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";
        }
    }

    // ==========================================
    // 5. 会话历史管理
    // ==========================================

    // 加载会话历史
    async function loadSessionHistory() {
        try {
            const token = getAuthToken();
            const response = await fetch("/api/v1/sessions", {
                headers: { "X-API-Key": token }
            });
            if (!response.ok) return;

            const data = await response.json();
            const sessions = data.sessions || {};
            
            sessionHistoryList.innerHTML = "";
            const sessionIds = Object.keys(sessions);

            if (sessionIds.length === 0) {
                sessionHistoryList.innerHTML = '<div class="history-placeholder">暂无会话历史</div>';
                return;
            }

            // 倒序排列，让最新的会话出现在最上方
            sessionIds.reverse().forEach(sid => {
                const title = sessions[sid] || "空会话";
                const isActive = sid === currentSessionId;

                const item = document.createElement("div");
                item.className = `history-item ${isActive ? "active" : ""}`;
                item.setAttribute("data-sid", sid);

                item.innerHTML = `
                    <div class="item-left">
                        <svg class="chat-bubble-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                        <span class="item-title" title="${title}">${title}</span>
                    </div>
                    <button class="item-delete-btn" title="删除该会话记录">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                `;

                // 点击切换会话
                item.querySelector(".item-left").addEventListener("click", () => {
                    switchSession(sid);
                });

                // 点击删除会话
                item.querySelector(".item-delete-btn").addEventListener("click", (e) => {
                    e.stopPropagation();
                    deleteSession(sid);
                });

                sessionHistoryList.appendChild(item);
            });
        } catch (e) {
            console.error("加载会话历史异常:", e);
        }
    }

    // 切换会话
    async function switchSession(sessionId) {
        if (isGenerating) {
            showToast("正处于智能回复流生成中，请稍后再切换会话", "warning");
            return;
        }
        currentSessionId = sessionId;
        updateSessionIdDisplay();
        
        // 激活样式切换
        document.querySelectorAll(".history-item").forEach(item => {
            item.classList.toggle("active", item.getAttribute("data-sid") === sessionId);
        });

        // 移动端体验自愈：成功切换后 150ms 自动关闭侧边栏，无需手动操作
        if (window.innerWidth <= 768) {
            setTimeout(closeSidebar, 150);
        }

        // 清空主聊屏并显示加载
        chatHistory.innerHTML = '<div class="history-placeholder">⌛ 正在深度加载历史交互中...</div>';

        try {
            const token = getAuthToken();
            const response = await fetch(`/api/v1/session/${sessionId}`, {
                headers: { "X-API-Key": token }
            });
            if (!response.ok) {
                showToast("无法获取该会话历史记录", "error");
                chatHistory.innerHTML = "";
                return;
            }

            const data = await response.json();
            const history = data.history || [];

            chatHistory.innerHTML = "";

            if (history.length === 0) {
                // 如果为空会话，加载默认问候
                appendDefaultGreeting();
                return;
            }

            history.forEach(msg => {
                appendStaticMessage(msg.role, msg.content);
            });
            scrollToBottom();

        } catch (e) {
            console.error("回显会话加载出错:", e);
            showToast("拉取历史记录失败，已为您自动清屏", "error");
            chatHistory.innerHTML = "";
        }
    }

    // 删除会话
    async function deleteSession(sessionId) {
        if (isGenerating && sessionId === currentSessionId) {
            showToast("当前会话正在吐字，无法执行删除", "warning");
            return;
        }

        try {
            const token = getAuthToken();
            const response = await fetch(`/api/v1/session/${sessionId}`, {
                method: "DELETE",
                headers: { "X-API-Key": token }
            });

            if (response.ok) {
                showToast("会话记录已成功清除", "success");
                
                // 如果删除的是当前会话，触发新建会话
                if (sessionId === currentSessionId) {
                    handleNewChat();
                } else {
                    loadSessionHistory();
                }
            } else {
                showToast("删除会话失败，请检查 Auth Token 状态", "error");
            }
        } catch (e) {
            showToast("请求发生异常，无法连接后端", "error");
        }
    }

    // 新建会话行为
    function handleNewChat() {
        if (isGenerating) {
            showToast("智能回复进行中，请先等待吐字结束", "warning");
            return;
        }
        currentSessionId = generateUUID();
        updateSessionIdDisplay();
        chatHistory.innerHTML = "";
        appendDefaultGreeting();
        loadSessionHistory();
        showToast("已为您建立全新的磨砂对话视窗", "success");
    }

    // 渲染默认问候气泡
    function appendDefaultGreeting() {
        const greet = document.createElement("div");
        greet.className = "message system";
        greet.innerHTML = `
            <div class="avatar-wrapper spark-glow">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L14.8 9.2L22 12L14.8 14.8L12 22L9.2 14.8L2 12L9.2 9.2L12 2Z" fill="currentColor"/></svg>
            </div>
            <div class="message-bubble-wrapper">
                <div class="sender-name">Trilium Copilot</div>
                <div class="content">
                    你好！我是 <strong>Trilium 极客知识库小助手</strong>。
                    我已经基于前置智能意图检测、BGE 深度重排和多轮会话就绪。
                    有什么想问我的笔记内容吗？
                </div>
            </div>
        `;
        chatHistory.appendChild(greet);
    }

    // 渲染静态消息（回显历史时使用）
    function appendStaticMessage(role, content) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role === "user" ? "user" : "ai"}`;
        
        let avatarSvg = "";
        let sender = "";
        if (role === "user") {
            avatarSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
            sender = "您";
        } else {
            avatarSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L14.8 9.2L22 12L14.8 14.8L12 22L9.2 14.8L2 12L9.2 9.2L12 2Z" fill="currentColor"/></svg>`;
            sender = "Trilium Copilot";
        }

        const safeHtml = DOMPurify.sanitize(marked.parse(content));

        msgDiv.innerHTML = `
            <div class="avatar-wrapper">
                ${avatarSvg}
            </div>
            <div class="message-bubble-wrapper">
                <div class="sender-name">${sender}</div>
                <div class="content">${safeHtml}</div>
            </div>
        `;
        chatHistory.appendChild(msgDiv);
    }

    // 清空当前上下文
    async function clearCurrentSessionContext() {
        if (isGenerating) return;
        try {
            const token = getAuthToken();
            const response = await fetch(`/api/v1/session/${currentSessionId}`, {
                method: "DELETE",
                headers: { "X-API-Key": token }
            });
            if (response.ok) {
                chatHistory.innerHTML = "";
                appendDefaultGreeting();
                loadSessionHistory();
                showToast("当前多轮会话上下文已100%重置空盘", "success");
            } else {
                showToast("清除失败，请检查接口凭证", "error");
            }
        } catch (e) {
            showToast("请求异常", "error");
        }
    }

    // 触发同步作业
    async function triggerKbSync() {
        try {
            const token = getAuthToken();
            btnSync.disabled = true;
            btnSync.innerHTML = `<span class="spinner"></span><span>同步中...</span>`;
            
            const response = await fetch("/api/v1/sync", {
                method: "POST",
                headers: { "X-API-Key": token }
            });
            if (response.ok) {
                showToast("Trilium 同步任务已在后台多线程启动，请稍后刷新！", "success");
            } else {
                showToast("同步失败，请核对您的 Auth Token", "error");
            }
        } catch (e) {
            showToast("无法连通同步服务", "error");
        } finally {
            btnSync.disabled = false;
            btnSync.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-8.31l-5.67-1.25"/></svg><span>同步数据</span>`;
        }
    }

    // 自动滚动到底部
    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // ==========================================
    // 6. 流式问答 SSE 处理核心
    // ==========================================

    async function handleSend() {
        const question = chatInput.value.trim();
        if (!question || isGenerating) return;

        const token = getAuthToken();
        if (!token) {
            showToast("请在侧边栏底部填入有效的 Auth Token 后再进行交互！", "warning");
            return;
        }

        isGenerating = true;
        chatInput.value = "";
        chatInput.style.height = "auto";
        btnSend.disabled = true;

        // 1. 创建 User 气泡
        const userDiv = document.createElement("div");
        userDiv.className = "message user";
        userDiv.innerHTML = `
            <div class="avatar-wrapper">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="message-bubble-wrapper">
                <div class="sender-name">您</div>
                <div class="content">${DOMPurify.sanitize(question)}</div>
            </div>
        `;
        chatHistory.appendChild(userDiv);
        scrollToBottom();

        // 2. 建立 AI 流式骨架气泡
        const aiDiv = document.createElement("div");
        aiDiv.className = "message ai";
        aiDiv.innerHTML = `
            <div class="avatar-wrapper spark-glow">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L14.8 9.2L22 12L14.8 14.8L12 22L9.2 14.8L2 12L9.2 9.2L12 2Z" fill="currentColor"/></svg>
            </div>
            <div class="message-bubble-wrapper" style="width: 100%;">
                <div class="sender-name">Trilium Copilot</div>
                <div class="content"><span class="spinner" style="display:inline-block; vertical-align:middle; margin-right:8px;"></span>正在思考与判定检索决策...</div>
                <div class="sources-container" style="display:none;"></div>
            </div>
        `;
        chatHistory.appendChild(aiDiv);
        scrollToBottom();

        const aiContentDiv = aiDiv.querySelector(".content");
        const sourcesContainer = aiDiv.querySelector(".sources-container");

        let responseText = "";
        let sourcesReceived = [];

        try {
            // 3. 发送 Stream SSE 请求
            const response = await fetch("/api/v1/ask_stream", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": token
                },
                body: JSON.stringify({
                    question: question,
                    session_id: currentSessionId
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errMsg = errorData.detail || `状态码: ${response.status}`;
                aiContentDiv.innerHTML = `<span style="color:var(--btn-danger);">❌ 管道建立失败：${errMsg}</span>`;
                isGenerating = false;
                btnSend.disabled = false;
                return;
            }

            // 清理掉加载旋转菊花
            aiContentDiv.innerHTML = "";

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n\n");
                
                // 保留最后一行未完成的内容在 buffer 里
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const jsonStr = line.slice(6).trim();
                        if (!jsonStr) continue;

                        try {
                            const event = JSON.parse(jsonStr);
                            
                            // A. 召回来源消息
                            if (event.type === "sources") {
                                sourcesReceived = event.data || [];
                                if (sourcesReceived.length > 0) {
                                    // 渲染 Sources Badges
                                    renderSources(sourcesContainer, sourcesReceived);
                                    sourcesContainer.style.display = "flex";
                                }
                            }
                            // B. 文本分片输出
                            else if (event.type === "chunk") {
                                responseText += event.data;
                                // 正则去标，去掉可能的 <answer> 和 </answer> 标记，保证视觉完美无瑕
                                const cleanText = responseText.replace(/<\/?answer>/gi, "");
                                // 采用 Marked 编译 Markdown
                                aiContentDiv.innerHTML = DOMPurify.sanitize(marked.parse(cleanText));
                                scrollToBottom();
                            }
                            // C. 异常信息错误
                            else if (event.type === "error") {
                                aiContentDiv.innerHTML += `<div style="color:var(--btn-danger); font-weight:500; margin-top:8px;">⚠️ 问答生成流中断: ${event.data.message}</div>`;
                            }
                        } catch (err) {
                            console.error("解析 Event 行失败:", err, line);
                        }
                    }
                }
            }

            // 对渲染好的全部代码块执行 highlight
            aiContentDiv.querySelectorAll("pre code").forEach(block => {
                hljs.highlightElement(block);
            });

        } catch (e) {
            console.error("SSE 网络连接异常:", e);
            aiContentDiv.innerHTML = `<span style="color:var(--btn-danger);">❌ 无法连通后端服务，连接被拒绝或超时。</span>`;
        } finally {
            isGenerating = false;
            btnSend.disabled = false;
            // 回复结束重新加载左侧栏历史（这样新会话的第一句提问可以立刻变成标题）
            loadSessionHistory();
        }
    }

    // 渲染召回参考卡片
    function renderSources(container, sources) {
        container.innerHTML = `<div class="sources-title">参考来源 (${sources.length} 个切片)</div>`;
        const badgesWrapper = document.createElement("div");
        badgesWrapper.className = "source-badges";

        sources.forEach((doc, idx) => {
            // 给每个 source 分配唯一缓存 Key 用于弹窗详情索引
            const key = `doc_${Date.now()}_${idx}`;
            currentSourcesMap[key] = doc;

            const badge = document.createElement("div");
            badge.className = "source-badge";
            badge.setAttribute("data-doc-key", key);
            
            const shortPath = doc.path ? doc.path.split(" > ").pop() : "未知";
            badge.innerHTML = `
                <span>[${idx + 1}] ${shortPath}</span>
                <svg class="doc-link-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            `;

            // 绑定点击弹出详情查阅事件
            badge.addEventListener("click", () => {
                openPreviewModal(key);
            });

            badgesWrapper.appendChild(badge);
        });

        container.appendChild(badgesWrapper);
    }

    // ==========================================
    // 7. 切片原文详情预览弹窗交互
    // ==========================================

    function openPreviewModal(docKey) {
        const doc = currentSourcesMap[docKey];
        if (!doc) return;

        previewPath.textContent = doc.path || "无物理树状路径";
        previewScore.textContent = doc.score ? parseFloat(doc.score).toFixed(4) : "0.0000";
        previewNoteId.textContent = doc.note_id || "无";
        
        // 渲染 Markdown 内容
        previewBody.innerHTML = DOMPurify.sanitize(marked.parse(doc.content || "*无内容*"));
        
        // 针对弹窗内的 pre code 执行高亮
        previewBody.querySelectorAll("pre code").forEach(block => {
            hljs.highlightElement(block);
        });

        // 渲染一键跳转到 Trilium 的物理链接并展示，过滤尾部斜杠以保证 URL 的完美和统一
        if (doc.note_id && doc.note_id !== "无" && doc.note_id !== "note_id") {
            const cleanBaseUrl = cachedTriliumBaseUrl.replace(/\/+$/, "");
            btnModalJump.href = `${cleanBaseUrl}/#root/${doc.note_id}`;
            btnModalJump.style.display = "inline-flex";
        } else {
            btnModalJump.style.display = "none";
        }

        previewModal.classList.add("active");
        document.body.classList.add("no-scroll");
    }

    function closePreviewModal() {
        previewModal.classList.remove("active");
        // 只有当 settings 抽屉和侧边栏也关闭时才安全地移除 no-scroll
        if (!sidebar.classList.contains("active") && !settingsDrawer.classList.contains("active")) {
            document.body.classList.remove("no-scroll");
        }
    }

    // ==========================================
    // 8. 高级配置控制台 (Settings Drawer)
    // ==========================================

    async function openSettingsDrawer() {
        const token = getAuthToken();
        if (!token) {
            showToast("请先填入有效的 Auth Token 才能访问高级设置", "warning");
            return;
        }

        try {
            // 异步从后端拉取脱敏配置
            const response = await fetch("/api/v1/config", {
                headers: { "X-API-Key": token }
            });
            if (!response.ok) {
                showToast("获取后端配置失败，请核对鉴权凭证", "error");
                return;
            }

            const config = await response.json();

            // 回显配置
            cfgLlmType.value = config.llm_model_type || "ollama";
            cfgLlmPath.value = config.llm_model_path || "";
            cfgApiBase.value = config.openai_api_base || "";
            cfgTriliumUrl.value = config.trilium_base_url || "";
            
            // 秘钥回显（若是 true 则展示占位符，避免真实秘钥泄露）
            cfgOpenaiKey.value = config.openai_api_key ? "******" : "";
            cfgDeepseekKey.value = config.deepseek_api_key ? "******" : "";
            cfgGeminiKey.value = config.gemini_api_key ? "******" : "";

            // RAG 算法参数回显
            cfgUseReranker.checked = config.use_reranker;
            cfgRerankerThreshold.value = config.reranker_threshold;
            valRerankerThreshold.textContent = parseFloat(config.reranker_threshold).toFixed(2);
            
            cfgSearchK.value = config.search_k;
            valSearchK.textContent = config.search_k;

            // 打开抽屉
            settingsDrawer.classList.add("active");
            document.body.classList.add("no-scroll");

        } catch (e) {
            showToast("网络请求失败，无法连接到设置控制台", "error");
        }
    }

    function closeSettingsDrawer() {
        settingsDrawer.classList.remove("active");
        // 只有在侧边栏和 Modal 也关闭时才移除 no-scroll 保护
        if (!sidebar.classList.contains("active") && !previewModal.classList.contains("active")) {
            document.body.classList.remove("no-scroll");
        }
    }

    async function saveSettings() {
        const token = getAuthToken();
        
        // 提取修改参数
        const payload = {
            llm_model_type: cfgLlmType.value,
            llm_model_path: cfgLlmPath.value,
            openai_api_base: cfgApiBase.value,
            trilium_base_url: cfgTriliumUrl.value.trim(),
            use_reranker: cfgUseReranker.checked,
            reranker_threshold: parseFloat(cfgRerankerThreshold.value),
            search_k: parseInt(cfgSearchK.value)
        };

        // 如果用户在密钥栏写了非 "******" 的值，说明修改了，传输最新密钥
        const oKey = cfgOpenaiKey.value.trim();
        if (oKey && oKey !== "******") payload.openai_api_key = oKey;

        const dKey = cfgDeepseekKey.value.trim();
        if (dKey && dKey !== "******") payload.deepseek_api_key = dKey;

        const gKey = cfgGeminiKey.value.trim();
        if (gKey && gKey !== "******") payload.gemini_api_key = gKey;

        // 加载菊花 Loading
        btnSettingsSave.disabled = true;
        const btnText = btnSettingsSave.querySelector(".btn-text");
        const spinner = btnSettingsSave.querySelector(".spinner");
        btnText.textContent = "正在热重载大模型...";
        spinner.style.display = "block";

        try {
            const response = await fetch("/api/v1/config", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": token
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                showToast("配置保存成功！大模型已秒级热生效并持久化落盘！", "success");
                closeSettingsDrawer();
                // 刷新健康心跳监测
                refreshSystemStatus();
            } else {
                const errorData = await response.json().catch(() => ({}));
                showToast(`热重载校验失败: ${errorData.detail || "未知原因"}`, "error");
            }
        } catch (e) {
            showToast("请求发生异常，保存失败", "error");
        } finally {
            btnSettingsSave.disabled = false;
            btnText.textContent = "保存热应用";
            spinner.style.display = "none";
        }
    }
});
