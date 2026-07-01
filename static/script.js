/* ── Tab navigation ──────────────────────────────────────── */
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    const tab = document.getElementById("tab-" + btn.dataset.tab);
    tab.classList.add("active");
    if (btn.dataset.tab === "insights") loadInsights();
    if (btn.dataset.tab === "history")  loadHistory();
  });
});

/* ── Chat ────────────────────────────────────────────────── */
const messages   = document.getElementById("messages");
const input      = document.getElementById("prompt-input");
const sendBtn    = document.getElementById("send-btn");
const lastTime   = document.getElementById("last-response-time");

function addMsg(tag, text, type) {
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.innerHTML = `<span class="msg-tag">${tag}</span><span class="msg-text">${escHtml(text)}</span>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function addTyping() {
  const div = document.createElement("div");
  div.className = "msg allam typing";
  div.innerHTML = `<span class="msg-tag">ALLAM</span><span class="msg-text"></span>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function escHtml(str) {
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

async function sendMessage() {
  const prompt = input.value.trim();
  if (!prompt) return;

  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;

  addMsg("YOU", prompt, "user");
  const typing = addTyping();

  try {
    const res  = await fetch("/api/chat", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ prompt }),
    });
    const data = await res.json();

    typing.remove();

    if (!res.ok) {
      addMsg("ERR", data.detail || "Something went wrong", "error");
      return;
    }

    addMsg("ALLAM", data.response, "allam");
    lastTime.textContent = `LAST RESPONSE: ${data.response_time}s`;

  } catch (e) {
    typing.remove();
    addMsg("ERR", "Could not reach the server", "error");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

sendBtn.addEventListener("click", sendMessage);

input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// auto-resize textarea
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = input.scrollHeight + "px";
});

/* ── Insights ────────────────────────────────────────────── */
async function loadInsights() {
  try {
    const res  = await fetch("/api/insights");
    const data = await res.json();

    document.getElementById("stat-total").textContent = data.total;
    document.getElementById("stat-week").textContent  = data.this_week;
    document.getElementById("stat-avg").textContent   = data.avg_time + "s";
    document.getElementById("stat-fast").textContent  = data.fastest + "s";

    // daily chart
    const chart = document.getElementById("daily-chart");
    chart.innerHTML = "";
    if (data.daily.length === 0) {
      chart.innerHTML = '<span class="no-data">no data yet</span>';
    } else {
      const max = Math.max(...data.daily.map(d => d.count), 1);
      data.daily.forEach(d => {
        const bar = document.createElement("div");
        bar.className = "d-bar";
        bar.style.height = `${(d.count / max) * 76}px`;
        bar.setAttribute("data-label", `${d.day}: ${d.count} chats`);
        chart.appendChild(bar);
      });
    }

    // recent prompts
    const rp = document.getElementById("recent-prompts");
    rp.innerHTML = "";
    if (data.recent_prompts.length === 0) {
      rp.innerHTML = '<div class="no-history">no prompts yet</div>';
    } else {
      data.recent_prompts.forEach(p => {
        const div = document.createElement("div");
        div.className = "recent-item";
        div.innerHTML = `<span>${escHtml(p.prompt)}</span><span class="r-time">${p.time}</span>`;
        rp.appendChild(div);
      });
    }

  } catch (e) {
    console.error("Could not load insights:", e);
  }
}

/* ── History ─────────────────────────────────────────────── */
async function loadHistory() {
  const list = document.getElementById("history-list");
  list.innerHTML = '<div class="no-history">loading...</div>';

  try {
    const res  = await fetch("/api/history");
    const data = await res.json();

    if (data.history.length === 0) {
      list.innerHTML = '<div class="no-history">no conversations yet</div>';
      return;
    }

    list.innerHTML = "";
    data.history.forEach(h => {
      const div = document.createElement("div");
      div.className = "hist-item";
      div.innerHTML = `
        <div class="hist-meta">
          <span>${h.created_at}</span>
          <span>${h.response_time}s response</span>
        </div>
        <div class="hist-prompt">${escHtml(h.prompt)}</div>
        <div class="hist-response">${escHtml(h.response)}</div>
      `;
      list.appendChild(div);
    });

  } catch (e) {
    list.innerHTML = '<div class="no-history">could not load history</div>';
  }
}