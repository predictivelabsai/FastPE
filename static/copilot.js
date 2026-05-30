(() => {
    const $ = (sel) => document.querySelector(sel);
    let copilotSid = null;
    let copilotStreaming = false;

    function escapeHtml(s) {
        return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function renderMd(text) {
        if (window.marked) return marked.parse(text);
        return escapeHtml(text).replace(/\n/g, "<br>");
    }

    function addBubble(role, text, agentSlug) {
        const box = $("#copilot-messages");
        if (!box) return null;
        const div = document.createElement("div");
        div.className = "msg msg-" + role;
        if (role === "assistant" && agentSlug) {
            div.innerHTML = '<div class="msg-agent"><span class="msg-agent-label">' +
                escapeHtml(agentSlug) + '</span></div>';
        }
        const bubble = document.createElement("div");
        bubble.className = "msg-bubble";
        if (text) bubble.innerHTML = renderMd(text);
        div.appendChild(bubble);
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
        return bubble;
    }

    function showThinking(bubble) {
        if (!bubble) return;
        const el = document.createElement("div");
        el.className = "copilot-thinking";
        el.textContent = "Thinking...";
        el.id = "copilot-thinking";
        bubble.parentElement.insertBefore(el, bubble);
    }

    function hideThinking() {
        const el = $("#copilot-thinking");
        if (el) el.remove();
    }

    async function initSession() {
        const page = ($("#copilot-page") || {}).value || "";
        const company = ($("#copilot-company") || {}).value || "";
        const params = new URLSearchParams({ page, company });
        try {
            const resp = await fetch("/app/copilot/session?" + params);
            const data = await resp.json();
            copilotSid = data.sid;
            if (data.messages && data.messages.length) {
                data.messages.forEach(m => addBubble(m.role, m.content, m.agent_slug));
            }
        } catch (e) {
            console.error("copilot session init failed", e);
        }
    }

    function handleEvent(raw, cb) {
        let type = null, data = "";
        for (const line of raw.split("\n")) {
            if (line.startsWith("event: ")) type = line.slice(7).trim();
            else if (line.startsWith("data: ")) data += line.slice(6);
        }
        if (!type) return;
        try { cb(type, data ? JSON.parse(data) : {}); }
        catch (e) { console.error("copilot sse parse error", raw, e); }
    }

    async function copilotSend(evt) {
        if (evt) evt.preventDefault();
        if (copilotStreaming) return;
        const ta = $("#copilot-input");
        const msg = ta.value.trim();
        if (!msg) return;

        if (!copilotSid) await initSession();

        copilotStreaming = true;
        const sendBtn = $("#copilot-send-btn");
        if (sendBtn) sendBtn.disabled = true;

        addBubble("user", msg);
        ta.value = "";

        const context = ($("#copilot-context") || {}).value || "";
        const body = new URLSearchParams({ msg, sid: copilotSid || "", context });

        let bubble = null;
        let accumulated = "";

        try {
            const resp = await fetch("/app/chat", { method: "POST", body });
            if (!resp.ok) {
                addBubble("assistant", "Error: " + resp.status);
                copilotStreaming = false;
                if (sendBtn) sendBtn.disabled = false;
                return;
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                let idx;
                while ((idx = buffer.indexOf("\n\n")) !== -1) {
                    const raw = buffer.slice(0, idx);
                    buffer = buffer.slice(idx + 2);
                    handleEvent(raw, (type, payload) => {
                        if (type === "agent_route") {
                            bubble = addBubble("assistant", "", payload.agent || payload.slug);
                            showThinking(bubble);
                        } else if (type === "token") {
                            if (!bubble) bubble = addBubble("assistant", "");
                            if (accumulated === "") hideThinking();
                            accumulated += payload.text;
                            bubble.innerHTML = renderMd(accumulated);
                            const box = $("#copilot-messages");
                            if (box) box.scrollTop = box.scrollHeight;
                        } else if (type === "session") {
                            if (payload.sid) copilotSid = payload.sid;
                        } else if (type === "done") {
                            hideThinking();
                            if (bubble) bubble.classList.remove("streaming");
                        } else if (type === "error") {
                            hideThinking();
                            if (!bubble) bubble = addBubble("assistant", "");
                            bubble.textContent = "Error: " + (payload.message || "unknown");
                        }
                    });
                }
            }
        } catch (e) {
            console.error("copilot stream error", e);
            addBubble("assistant", "Connection error");
        }

        copilotStreaming = false;
        if (sendBtn) sendBtn.disabled = false;
        accumulated = "";
    }

    window.copilotSend = copilotSend;
    window.copilotHandleKey = (ev) => {
        if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); copilotSend(ev); }
    };
    window.toggleCopilotPane = () => {
        const r = $("#right-pane");
        const app = $(".app");
        if (!r || !app) return;
        if (r.classList.contains("open")) {
            r.classList.remove("open");
            app.classList.add("pane-closed");
            const btn = $("#copilot-btn");
            if (btn) btn.classList.remove("active");
        } else {
            r.classList.add("open");
            app.classList.remove("pane-closed");
            const btn = $("#copilot-btn");
            if (btn) btn.classList.add("active");
            if (!copilotSid) initSession();
        }
    };
})();
