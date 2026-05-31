/* PE Hero Training game — SSE chat client */

function streamGame(msg) {
    const messages = document.getElementById("messages");
    const formData = new FormData();
    formData.append("msg", msg);

    fetch("/app/training/chat", { method: "POST", body: formData })
        .then(r => r.body.getReader())
        .then(reader => {
            const decoder = new TextDecoder();
            let agentDiv = null;
            let bubble = null;
            let accumulated = "";

            function read() {
                reader.read().then(({ done, value }) => {
                    if (done) return;
                    const text = decoder.decode(value, { stream: true });
                    const lines = text.split("\n");
                    let eventName = "";
                    for (const line of lines) {
                        if (line.startsWith("event: ")) {
                            eventName = line.slice(7);
                        } else if (line.startsWith("data: ")) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                if (eventName === "token") {
                                    if (!agentDiv) {
                                        agentDiv = document.createElement("div");
                                        agentDiv.className = "msg agent";
                                        bubble = document.createElement("div");
                                        bubble.className = "msg-bubble";
                                        agentDiv.appendChild(bubble);
                                        messages.appendChild(agentDiv);
                                    }
                                    accumulated += data.text;
                                    if (window.marked) {
                                        bubble.innerHTML = marked.parse(accumulated);
                                    } else {
                                        bubble.textContent = accumulated;
                                    }
                                    messages.scrollTop = messages.scrollHeight;
                                } else if (eventName === "tool_start") {
                                    const thinking = document.createElement("div");
                                    thinking.className = "thinking-line";
                                    thinking.id = "game-thinking";
                                    thinking.innerHTML = '<span class="thinking-dot"></span> Coach V is thinking...';
                                    messages.appendChild(thinking);
                                    messages.scrollTop = messages.scrollHeight;
                                } else if (eventName === "tool_end") {
                                    const th = document.getElementById("game-thinking");
                                    if (th) th.remove();
                                }
                            } catch (e) { /* skip malformed */ }
                        }
                    }
                    read();
                });
            }
            read();
        });
}

document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("training-form");
    const input = document.getElementById("training-input");
    const messages = document.getElementById("messages");

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        const msg = input.value.trim();
        if (!msg) return;
        input.value = "";

        const msgDiv = document.createElement("div");
        msgDiv.className = "msg user";
        msgDiv.innerHTML = '<div class="msg-bubble">' + msg.replace(/</g, "&lt;") + "</div>";
        messages.appendChild(msgDiv);
        messages.scrollTop = messages.scrollHeight;

        streamGame(msg);
    });

    // Auto-start: show character select
    streamGame("start");
});
