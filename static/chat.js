/* PEHero — chat client (SSE streaming, 3-pane interactions). */

(() => {
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => Array.from(document.querySelectorAll(sel));

    let currentSessionId = getSidFromURL();
    let currentAgentSlug = null;
    let streaming = false;

    // Agent-prompt lookup table — embedded by the server in a <script id="agent-prompts-data">.
    const AGENT_PROMPTS = readJsonScript("agent-prompts-data") || {};
    const AGENT_NAMES = readJsonScript("agent-names-data") || {};
    const I18N = readJsonScript("i18n-data") || {};

    function readJsonScript(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        try { return JSON.parse(el.textContent); }
        catch (e) { console.warn("bad JSON in #" + id, e); return null; }
    }

    // ── URL session id ─────────────────────────────────────────────
    function getSidFromURL() {
        const p = new URLSearchParams(window.location.search);
        return p.get("sid") || "";
    }
    function setSid(sid) {
        currentSessionId = sid;
        const u = new URL(window.location);
        u.searchParams.set("sid", sid);
        history.replaceState(null, "", u);
    }

    // ── Message rendering ─────────────────────────────────────────
    function addBubble(role, text, agentSlug) {
        const wrap = document.createElement("div");
        wrap.className = `msg msg-${role}`;
        if (role === "assistant" && agentSlug) {
            const hdr = document.createElement("div");
            hdr.className = "msg-agent";
            const nice = AGENT_NAMES[agentSlug] || agentSlug;
            hdr.innerHTML = `<span class="msg-agent-icon">◆</span><span class="msg-agent-label">${nice}</span>`;
            wrap.appendChild(hdr);
        }
        const bubble = document.createElement("div");
        bubble.className = "msg-bubble";
        bubble.textContent = text;
        wrap.appendChild(bubble);
        $("#messages").appendChild(wrap);
        scrollMessagesBottom();
        return bubble;
    }

    function appendToolLog(bubble, name, args) {
        let log = bubble.parentElement.querySelector(".tool-log");
        if (!log) {
            log = document.createElement("div");
            log.className = "tool-log";
            bubble.parentElement.appendChild(log);
        }
        const step = document.createElement("div");
        step.className = "tool-step";
        const argStr = args ? JSON.stringify(args).slice(0, 140) : "";
        step.innerHTML = `→ <span class="tool-name">${name}</span> <span class="tool-args">${argStr}</span>`;
        log.appendChild(step);
    }

    function scrollMessagesBottom() {
        const m = $("#messages");
        m.scrollTop = m.scrollHeight;
    }

    function renderMarkdownLite(text) {
        if (window.marked) return marked.parse(text);
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>");
    }

    // ── CSV copy / download for tables ───────────────────────────
    function tableToCSV(table) {
        const rows = [];
        table.querySelectorAll("tr").forEach(tr => {
            const cells = [];
            tr.querySelectorAll("th, td").forEach(td => {
                cells.push('"' + td.textContent.trim().replace(/"/g, '""') + '"');
            });
            rows.push(cells.join(","));
        });
        return rows.join("\n");
    }

    function enhanceTables(container) {
        if (!container) return;
        container.querySelectorAll("table").forEach(table => {
            if (table.dataset.enhanced) return;
            table.dataset.enhanced = "1";
            const toolbar = document.createElement("div");
            toolbar.className = "table-toolbar";
            const copyBtn = document.createElement("button");
            copyBtn.textContent = I18N.copy_csv || "Copy CSV";
            copyBtn.className = "table-action-btn";
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(tableToCSV(table)).then(() => {
                    copyBtn.textContent = I18N.copied || "Copied!";
                    setTimeout(() => { copyBtn.textContent = I18N.copy_csv || "Copy CSV"; }, 1500);
                });
            };
            const dlBtn = document.createElement("button");
            dlBtn.textContent = I18N.download_csv || "Download CSV";
            dlBtn.className = "table-action-btn";
            dlBtn.onclick = () => {
                const blob = new Blob([tableToCSV(table)], { type: "text/csv" });
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "pehero-data.csv";
                a.click();
                URL.revokeObjectURL(a.href);
            };
            toolbar.appendChild(copyBtn);
            toolbar.appendChild(dlBtn);
            table.parentNode.insertBefore(toolbar, table);
        });
    }

    // ── Thinking indicator (timer + rotating tool name) ────────────
    let thinker = null;
    function showThinking(bubble) {
        if (!bubble) return;
        thinker = {
            started: Date.now(),
            tool: null,
            el: document.createElement("div"),
            timerId: null,
        };
        thinker.el.className = "thinking-indicator";
        thinker.el.innerHTML = `<span class="dot"></span><span class="label">${I18N.thinking || "Thinking… "}<span class="secs">0s</span></span>`;
        bubble.parentElement.insertBefore(thinker.el, bubble);
        thinker.timerId = setInterval(updateThinking, 500);
    }
    function updateThinking() {
        if (!thinker) return;
        const secs = Math.floor((Date.now() - thinker.started) / 1000);
        const thinkText = I18N.thinking || "Thinking… ";
        const callText = I18N.calling || "calling ";
        const label = thinker.tool
            ? `${thinkText}<span class="secs">${secs}s</span> · ${callText}<code>${thinker.tool}</code>`
            : `${thinkText}<span class="secs">${secs}s</span>`;
        thinker.el.querySelector(".label").innerHTML = label;
    }
    function setThinkingTool(name) {
        if (!thinker) return;
        thinker.tool = name;
        updateThinking();
    }
    function hideThinking() {
        if (!thinker) return;
        clearInterval(thinker.timerId);
        if (thinker.el && thinker.el.parentElement) thinker.el.parentElement.removeChild(thinker.el);
        thinker = null;
    }

    // ── Sample cards (Gemini-style) ──────────────────────────────
    window.updateSampleCards = (slug) => {
        const row = $("#sample-cards-row");
        const label = $("#sample-cards-label");
        if (!row) return;
        let prompts = (slug && AGENT_PROMPTS[slug]) || [];
        if (!prompts.length) {
            prompts = [
                "triage: DR VET veterinary clinic, €3.8M revenue, Vilnius",
                "lbo: 5-year model for Kardiolita at 12% rev growth",
                "ltm: what are the financials of DR VET?",
                "memo: draft the IC memo for Kardiolita",
                "vdr: audit the data room for Northway",
                "crm: top 10 LPs to reach out to for Fund V",
            ];
        }
        row.innerHTML = "";
        prompts.slice(0, 6).forEach(p => {
            const b = document.createElement("button");
            b.className = "sample-card";
            b.title = p;
            b.innerHTML = `<span class="sample-card-text"></span>`;
            b.querySelector(".sample-card-text").textContent = p;
            b.onclick = () => { fillChat(p); sendMessage(null); };
            row.appendChild(b);
        });
        if (label) {
            label.innerHTML = slug && AGENT_NAMES[slug]
                ? `<span class="sample-cards-label">${I18N.try_with || "Try with "}${AGENT_NAMES[slug]}</span>`
                : `<span class="sample-cards-label">${I18N.try_prompt || "Try a prompt"}</span>`;
        }
    };

    // Update sample cards when the user types a prefix like "lbo:"
    window.onInputChange = (ta) => {
        const v = (ta.value || "").trim().toLowerCase();
        const m = v.match(/^(\w{2,10}):/);
        if (!m) return;
        const prefix = m[1] + ":";
        // find slug with this prefix
        for (const slug of Object.keys(AGENT_PROMPTS)) {
            const first = (AGENT_PROMPTS[slug][0] || "").toLowerCase();
            if (first.startsWith(prefix)) { updateSampleCards(slug); return; }
        }
    };

    // ── Memo → PDF (opens in new tab) ──────────────────────────────
    const MEMO_AGENTS = new Set(["investor_memo", "deal_teaser", "lp_update", "outreach_email", "loi_writer"]);

    async function renderMemoPdf(markdown, title) {
        const body = new URLSearchParams({ markdown, title: title || "IC memo" });
        const r = await fetch("/app/memo-pdf/render", { method: "POST", body });
        if (!r.ok) throw new Error("render failed " + r.status);
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        window.open(data.file_url, "_blank");
        return data;
    }

    window.renderMemoPdf = renderMemoPdf;

    const AGENT_TITLES = {
        investor_memo: "IC Memo", deal_teaser: "Teaser", lp_update: "LP Update",
        outreach_email: "Outreach Email", loi_writer: "Letter of Intent",
    };

    function maybeAppendMemoPreviewButton(bubble, text, agentSlug) {
        if (!bubble || !text) return;
        if (!MEMO_AGENTS.has(agentSlug)) return;
        const looksMemo = text.length > 400 && /(^|\n)##?\s+\w/.test(text);
        if (!looksMemo) return;
        const existing = bubble.parentElement.querySelector(".memo-preview-row");
        if (existing) return;
        const docTitle = AGENT_TITLES[agentSlug] || "Document";
        const row = document.createElement("div");
        row.className = "memo-preview-row";
        row.innerHTML = `
            <button class="memo-preview-btn">${I18N.preview_pdf || "📄 Preview PDF"}</button>
            <button class="memo-download-btn" style="display:none">${I18N.download_pdf || "⬇ Download PDF"}</button>`;
        bubble.parentElement.appendChild(row);
        const previewBtn = row.querySelector(".memo-preview-btn");
        const dlBtn = row.querySelector(".memo-download-btn");
        previewBtn.onclick = async () => {
            previewBtn.disabled = true; previewBtn.textContent = I18N.rendering || "Rendering…";
            try {
                const data = await renderMemoPdf(text, docTitle);
                previewBtn.textContent = I18N.open_pdf || "✓ Open PDF";
                dlBtn.style.display = "inline-flex";
                dlBtn.onclick = () => {
                    const a = document.createElement("a");
                    a.href = data.file_url;
                    a.download = docTitle.replace(/\s+/g, "-").toLowerCase() + ".pdf";
                    a.click();
                };
            } catch (e) {
                previewBtn.textContent = I18N.render_failed || "Render failed";
                console.error(e);
            }
        };
    }

    // ── Inline artifacts (render tables/citations in chat bubble) ──
    function showArtifactInline(bubble, payload) {
        if (!bubble) return;
        const card = document.createElement("div");
        card.className = "artifact-inline";
        const title = payload.title || "";
        const subtitle = payload.subtitle || "";
        const kind = payload.kind || "note";
        let header = "";
        if (title) header += `<h4 class="artifact-inline-title">${escapeHtml(title)}</h4>`;
        if (subtitle) header += `<div class="artifact-inline-sub">${escapeHtml(subtitle)}</div>`;
        card.innerHTML = `${header}<div class="artifact-inline-body">${renderArtifactHTML(payload)}</div>`;
        bubble.parentElement.appendChild(card);
        enhanceTables(card);
        scrollMessagesBottom();
    }

    function renderArtifactHTML(p) {
        if (p.kind === "table" && Array.isArray(p.rows)) {
            if (!p.rows.length) return `<p><em>${I18N.no_rows || "No rows."}</em></p>`;
            const cols = p.columns || Object.keys(p.rows[0]);
            const head = "<tr>" + cols.map(c => `<th>${escapeHtml(c)}</th>`).join("") + "</tr>";
            const body = p.rows.map(r => "<tr>" + cols.map(c => `<td>${formatCell(r[c])}</td>`).join("") + "</tr>").join("");
            return `<table class="artifact-table">${head}${body}</table>`;
        }
        if (p.kind === "citations" && Array.isArray(p.items)) {
            return p.items.map(it => `
                <div style="margin-bottom:.6rem;">
                    <div style="color:var(--ink); font-size:.8rem; font-weight:500;">${escapeHtml(it.title || "")}</div>
                    <div style="color:var(--ink-dim); font-size:.68rem; font-family:'JetBrains Mono',monospace;">${escapeHtml(it.doc_type || "")}${it.url ? ` · <a href="${escapeHtml(it.url)}" target="_blank">link</a>` : ""} · score ${(it.score||0).toFixed(2)}</div>
                    <div style="color:var(--ink-muted); font-size:.75rem; margin-top:.25rem;">${escapeHtml(it.snippet || "").replace(/\n/g,"<br>")}</div>
                </div>
            `).join("");
        }
        if (p.body_md) {
            return renderMarkdownLite(p.body_md);
        }
        return `<pre>${escapeHtml(JSON.stringify(p, null, 2))}</pre>`;
    }

    function formatCell(v) {
        if (v === null || v === undefined) return "—";
        if (typeof v === "number") return v.toLocaleString();
        if (typeof v === "object") return JSON.stringify(v);
        return String(v);
    }

    // ── "Should we do that?" follow-up button ─────────────────────
    function maybeAppendFollowUp(bubble, text) {
        if (!bubble || !text) return;
        const m = text.match(/\*?\*?Next step\*?\*?[\s]*[—–:-][\s]*([^\n]+)/i);
        if (!m) return;
        const action = m[1].trim().replace(/\*+$/, "");
        const row = document.createElement("div");
        row.className = "followup-row";
        row.innerHTML = `
            <div class="followup-prompt">${escapeHtml(action)}</div>
            <button class="followup-btn followup-yes">${I18N.yes_do || "Yes, do that"}</button>
            <button class="followup-btn followup-no">${I18N.no_thanks || "No thanks"}</button>
        `;
        bubble.parentElement.appendChild(row);
        row.querySelector(".followup-yes").onclick = () => {
            row.remove();
            fillChat("Yes — do that: " + action);
            sendMessage(null);
        };
        row.querySelector(".followup-no").onclick = () => row.remove();
    }

    function escapeHtml(s) {
        return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // ── SSE send ──────────────────────────────────────────────────
    async function sendMessage(evt) {
        if (evt) evt.preventDefault();
        if (streaming) return;
        const ta = $("#chat-input");
        const msg = ta.value.trim();
        if (!msg) return;

        streaming = true;
        $("#send-btn").disabled = true;

        const wh = $("#welcome-hero");
        if (wh) wh.style.display = "none";

        addBubble("user", msg);
        ta.value = "";
        ta.style.height = "";

        const body = new URLSearchParams({ msg, sid: currentSessionId || "" });

        const resp = await fetch("/app/chat", { method: "POST", body });
        if (!resp.ok) {
            addBubble("assistant", (I18N.error_prefix || "Error: ") + resp.status);
            streaming = false; $("#send-btn").disabled = false;
            return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let bubble = null;
        let accumulated = "";

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
                        const nice = payload.agent || AGENT_NAMES[payload.slug] || payload.slug;
                        $("#current-agent-label").textContent = nice;
                        currentAgentSlug = payload.slug;
                        updateSampleCards(payload.slug);
                        bubble = addBubble("assistant", "", payload.slug);
                        bubble.classList.add("streaming");
                        showThinking(bubble);
                    } else if (type === "token") {
                        if (!bubble) bubble = addBubble("assistant", "", "");
                        if (accumulated === "") hideThinking();
                        accumulated += payload.text;
                        bubble.innerHTML = renderMarkdownLite(accumulated);
                        scrollMessagesBottom();
                    } else if (type === "tool_start") {
                        setThinkingTool(payload.name);
                        appendToolLog(bubble || addBubble("assistant", "", ""), payload.name, payload.args);
                    } else if (type === "tool_end") {
                        // update thinker with "(done)" flavor; leaving tool name as-is
                    } else if (type === "artifact_show") {
                        showArtifactInline(bubble, payload);
                    } else if (type === "error") {
                        hideThinking();
                        if (!bubble) bubble = addBubble("assistant", "", "");
                        bubble.textContent = (I18N.error_prefix || "Error: ") + (payload.message || "unknown");
                    } else if (type === "session") {
                        if (payload.sid) setSid(payload.sid);
                    } else if (type === "done") {
                        hideThinking();
                        if (bubble) bubble.classList.remove("streaming");
                        enhanceTables(bubble);
                        maybeAppendFollowUp(bubble, accumulated);
                        maybeAppendMemoPreviewButton(bubble, accumulated, payload.slug || currentAgentSlug);
                    }
                });
            }
        }
        streaming = false; $("#send-btn").disabled = false;
    }

    function handleEvent(raw, cb) {
        let type = null; let data = "";
        for (const line of raw.split("\n")) {
            if (line.startsWith("event: ")) type = line.slice(7).trim();
            else if (line.startsWith("data: ")) data += line.slice(6);
        }
        if (!type) return;
        try { cb(type, data ? JSON.parse(data) : {}); }
        catch (e) { console.error("bad sse line", raw, e); }
    }

    // ── News panel ────────────────────────────────────────────────
    function timeAgo(isoStr) {
        const d = new Date(isoStr);
        const now = new Date();
        const diffMs = now - d;
        const mins = Math.floor(diffMs / 60000);
        if (mins < 1) return I18N.news_just_now || "just now";
        if (mins < 60) return (I18N.news_min_ago || "{n}m ago").replace("{n}", mins);
        const hours = Math.floor(mins / 60);
        if (hours < 24) return (I18N.news_hour_ago || "{n}h ago").replace("{n}", hours);
        const days = Math.floor(hours / 24);
        return (I18N.news_day_ago || "{n}d ago").replace("{n}", days);
    }

    async function loadNews() {
        const body = $("#news-body");
        const loading = $("#news-loading");
        if (!body) return;

        try {
            const resp = await fetch("/app/news");
            if (!resp.ok) throw new Error(resp.status);
            const articles = await resp.json();

            if (loading) loading.style.display = "none";
            body.style.display = "block";

            if (!articles.length) {
                body.innerHTML = `<p class="news-empty">${I18N.news_empty || "No news available"}</p>`;
                return;
            }

            const sub = $("#news-subtitle");
            if (sub) sub.textContent = articles.length + " articles";

            body.innerHTML = articles.map(a => `
                <a href="${escapeHtml(a.url)}" target="_blank" rel="noopener" class="news-item">
                    <div class="news-item-header">
                        <span class="news-source">${escapeHtml(a.icon || a.source)}</span>
                        <span class="news-time">${timeAgo(a.published)}</span>
                    </div>
                    <div class="news-item-title">${escapeHtml(a.title)}</div>
                    ${a.summary ? `<div class="news-item-summary">${escapeHtml(a.summary).slice(0, 120)}</div>` : ""}
                </a>
            `).join("");
        } catch (e) {
            console.error("news load failed", e);
            if (loading) loading.innerHTML = `<p class="news-empty">${I18N.news_empty || "No news available"}</p>`;
        }
    }

    // Load news on page load, refresh every 5 minutes
    loadNews();
    setInterval(loadNews, 300000);

    // ── UI helpers ────────────────────────────────────────────────
    window.toggleLeftPane = () => {
        $(".left-pane").classList.toggle("open");
        $(".left-overlay").classList.toggle("visible");
    };
    window.toggleNewsPane = () => {
        const r = $("#right-pane");
        const app = $(".app");
        if (r.classList.contains("open")) {
            r.classList.remove("open");
            app.classList.add("pane-closed");
            const nb = $("#news-btn");
            if (nb) nb.classList.remove("active");
        } else {
            r.classList.add("open");
            app.classList.remove("pane-closed");
            const nb = $("#news-btn");
            if (nb) nb.classList.add("active");
        }
    };
    // Pipeline deal-detail page uses the right pane for deal brief
    window.toggleArtifactPane = window.toggleNewsPane;
    window.toggleGroup = (id) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle("open");
        const btn = document.getElementById("btn-" + id);
        if (btn) btn.classList.toggle("open");
    };
    window.handleKey = (ev) => {
        if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); sendMessage(ev); }
    };
    window.autoResize = (el) => {
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 240) + "px";
    };
    window.fillChat = (text) => {
        const ta = $("#chat-input");
        ta.value = text;
        ta.focus();
        autoResize(ta);
        onInputChange(ta);
    };
    window.newChat = () => { window.location.href = "/app"; };
    window.showSignIn = () => { $("#signin-overlay").classList.add("visible"); $("#signin-email").focus(); };
    window.doSignIn = async () => {
        const email = $("#signin-email").value.trim();
        if (!email) return;
        const r = await fetch("/app/auth/signin", { method: "POST", body: new URLSearchParams({ email }) });
        if (r.ok) window.location.reload();
    };
    window.setLang = async (code) => {
        const r = await fetch("/app/config", {
            method: "POST",
            body: new URLSearchParams({ lang: code }),
        });
        if (r.ok) window.location.reload();
    };
    window.toggleLangDropdown = (ev) => {
        ev.stopPropagation();
        const menu = document.getElementById("lang-dd-menu");
        if (menu) menu.classList.toggle("open");
    };
    document.addEventListener("click", () => {
        const menu = document.getElementById("lang-dd-menu");
        if (menu) menu.classList.remove("open");
    });
    window.setCurrency = async (code) => {
        const r = await fetch("/app/config", {
            method: "POST",
            body: new URLSearchParams({ currency: code }),
        });
        if (r.ok) {
            document.querySelectorAll(".cfg-chip").forEach(el => {
                el.classList.toggle("active", el.textContent.trim().endsWith(code));
            });
            window.location.reload();
        }
    };
    window.signOut = async () => {
        await fetch("/app/auth/signout", { method: "POST" });
        window.location.reload();
    };

    // ── Copy / share chat ──────────────────────────────────────────
    window.copyChat = () => {
        const msgs = document.querySelectorAll(".msg");
        const lines = [];
        msgs.forEach(m => {
            const role = m.classList.contains("msg-user") ? (I18N.you || "You") : (I18N.pehero || "PEHero");
            const bubble = m.querySelector(".msg-bubble");
            if (bubble) lines.push(`${role}: ${bubble.textContent.trim()}`);
        });
        const text = lines.join("\n\n");
        navigator.clipboard.writeText(text).then(() => {
            const btn = document.getElementById("copy-chat-btn");
            if (btn) { btn.textContent = I18N.copied || "Copied!"; setTimeout(() => { btn.textContent = I18N.copy_chat || "Copy chat"; }, 1500); }
        });
    };
    window.shareChat = async () => {
        const btn = document.getElementById("share-chat-btn");
        if (!currentSessionId) {
            if (btn) { btn.textContent = I18N.no_session || "No session"; setTimeout(() => { btn.textContent = I18N.share || "Share"; }, 1500); }
            return;
        }
        try {
            const r = await fetch("/app/share", {
                method: "POST",
                body: new URLSearchParams({ sid: currentSessionId }),
            });
            const data = await r.json();
            if (data.ok && data.url) {
                const url = window.location.origin + data.url;
                await navigator.clipboard.writeText(url);
                if (btn) { btn.textContent = I18N.link_copied || "Link copied!"; setTimeout(() => { btn.textContent = I18N.share || "Share"; }, 1500); }
            } else {
                if (btn) { btn.textContent = I18N.error || "Error"; setTimeout(() => { btn.textContent = I18N.share || "Share"; }, 1500); }
            }
        } catch (e) {
            console.error("share failed", e);
            if (btn) { btn.textContent = I18N.error || "Error"; setTimeout(() => { btn.textContent = I18N.share || "Share"; }, 1500); }
        }
    };

    // Enhance any pre-rendered tables on page load
    document.querySelectorAll(".msg-bubble").forEach(b => enhanceTables(b));

    window.sendMessage = sendMessage;
    window.renderMarkdownLite = renderMarkdownLite;
    window.enhanceTables = enhanceTables;
})();
