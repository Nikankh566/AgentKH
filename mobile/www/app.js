/* Agent KH — Android edition.
   Agentic chat: talks to Gemini directly with YOUR API key (stored on-device only).
   Tools run locally: notes, reminders, memory, URL fetch. */
"use strict";

const $ = id => document.getElementById(id);
const chat = $("chat"), inp = $("inp"), sendBtn = $("send"), mochi = $("mochi");
const statusEl = $("status");

/* ---------------- storage ---------------- */
const store = {
  get(k, d) { try { const v = localStorage.getItem("akh_" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("akh_" + k, JSON.stringify(v)); } catch (e) {} },
  del(k) { try { localStorage.removeItem("akh_" + k); } catch (e) {} },
};

let settings = Object.assign({ key: "", model: "gemini-3.5-flash", name: "" }, store.get("settings", {}));
let history = store.get("history", []);           // [{role, text}]
let notes = store.get("notes", []);               // [{t, text}]
let memory = store.get("memory", []);             // [facts]

/* ---------------- tools ---------------- */
const TOOLS = [{
  functionDeclarations: [
    { name: "save_note", description: "Save a short note for the user",
      parameters: { type: "OBJECT", properties: { text: { type: "STRING" } }, required: ["text"] } },
    { name: "list_notes", description: "List saved notes",
      parameters: { type: "OBJECT", properties: {} } },
    { name: "delete_note", description: "Delete a note by its number (1-based, from list_notes)",
      parameters: { type: "OBJECT", properties: { n: { type: "NUMBER" } }, required: ["n"] } },
    { name: "set_reminder", description: "Set a reminder in N minutes from now",
      parameters: { type: "OBJECT", properties: {
        minutes: { type: "NUMBER" }, text: { type: "STRING" } }, required: ["minutes", "text"] } },
    { name: "remember", description: "Remember a long-term fact about the user",
      parameters: { type: "OBJECT", properties: { fact: { type: "STRING" } }, required: ["fact"] } },
    { name: "fetch_url", description: "Fetch a web page and return its text (first 4000 chars)",
      parameters: { type: "OBJECT", properties: { url: { type: "STRING" } }, required: ["url"] } },
  ]
}];

function toolBubble(icon, text) {
  const d = document.createElement("div");
  d.className = "msg tool";
  d.textContent = icon + " " + text;
  chat.appendChild(d); scrollDown();
}

async function runTool(name, args) {
  args = args || {};
  switch (name) {
    case "save_note": {
      notes.push({ t: Date.now(), text: String(args.text || "") });
      store.set("notes", notes);
      toolBubble("📝", "Note saved.");
      return "Note saved.";
    }
    case "list_notes": {
      if (!notes.length) { toolBubble("📝", "No notes yet."); return "No notes saved."; }
      const s = notes.map((n, i) => (i + 1) + ". " + n.text).join("\n");
      toolBubble("📝", s);
      return s;
    }
    case "delete_note": {
      const i = Math.round(args.n) - 1;
      if (i < 0 || i >= notes.length) return "Invalid note number.";
      notes.splice(i, 1); store.set("notes", notes);
      toolBubble("📝", "Note deleted.");
      return "Note deleted.";
    }
    case "set_reminder": {
      const ms = Math.max(1, Math.round(args.minutes)) * 60000;
      const text = String(args.text || "Reminder");
      scheduleReminder(ms, text);
      toolBubble("⏰", `Reminder set for ${Math.round(ms / 60000)} min: ${text}`);
      return `Reminder set for ${Math.round(ms / 60000)} minutes from now.`;
    }
    case "remember": {
      memory.push(String(args.fact || ""));
      store.set("memory", memory.slice(-50));
      toolBubble("🧠", "Remembered: " + args.fact);
      return "Fact remembered.";
    }
    case "fetch_url": {
      try {
        const r = await fetch(String(args.url), { headers: { "User-Agent": "AgentKH-Android" } });
        const t = await r.text();
        const clean = t.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ")
          .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 4000);
        return clean || "(empty page)";
      } catch (e) { return "Fetch failed: " + e.message; }
    }
    default: return "Unknown tool: " + name;
  }
}

async function scheduleReminder(ms, text) {
  try {
    if (window.Capacitor && Capacitor.isPluginAvailable("LocalNotifications")) {
      const { LocalNotifications } = await import("@capacitor/local-notifications");
      await LocalNotifications.requestPermissions();
      await LocalNotifications.schedule({
        notifications: [{ id: Date.now() % 2147483647, title: "Agent KH ⏰",
          body: text, schedule: { at: new Date(Date.now() + ms) } }]
      });
      return;
    }
  } catch (e) {}
  // fallback: in-app timer
  setTimeout(() => {
    toolBubble("⏰", "Reminder: " + text);
    try { navigator.vibrate && navigator.vibrate(300); } catch (e) {}
  }, ms);
}

/* ---------------- gemini ---------------- */
function systemPrompt() {
  const mem = memory.length ? "\nThings you remember about the user:\n- " + memory.join("\n- ") : "";
  const nm = settings.name ? ` The user's name is ${settings.name}.` : "";
  return `You are Agent KH, a friendly personal AI agent on the user's Android phone.${nm}
Be warm, concise, and helpful. You can use tools: save/list/delete notes, set reminders (minutes), remember facts, fetch URLs.${mem}`;
}

async function* streamGemini(messages) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${settings.model}:streamGenerateContent?alt=sse&key=${settings.key}`;
  const contents = messages.map(m => {
    if (m._parts) return { role: "user", parts: m._parts };
    return { role: m.role === "ai" ? "model" : "user", parts: [{ text: m.text }] };
  });
  const body = {
    system_instruction: { parts: [{ text: systemPrompt() }] },
    contents,
    tools: TOOLS,
  };
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body) });
  if (!r.ok) {
    const t = await r.text();
    throw new Error("API error " + r.status + ": " + t.slice(0, 200));
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      const line = p.trim().split("\n").find(l => l.startsWith("data:"));
      if (!line) continue;
      try { yield JSON.parse(line.slice(5).trim()); } catch (e) {}
    }
  }
}

async function chatTurn(userText) {
  // agentic loop: model may call tools, we run them, feed results back
  let messages = history.concat([{ role: "user", text: userText }]);
  let fullText = "";
  const aiDiv = addMsg("ai", "");
  mochi.classList.add("thinking");
  statusEl.textContent = "thinking…";
  aiDiv.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';

  for (let step = 0; step < 5; step++) {
    let toolCalls = [];
    let text = "";
    try {
      for await (const chunk of streamGemini(messages)) {
        const cand = (chunk.candidates || [])[0];
        if (!cand) continue;
        for (const part of cand.content.parts || []) {
          if (part.text) { text += part.text; renderAi(aiDiv, fullText + text); }
          if (part.functionCall) toolCalls.push(part.functionCall);
        }
      }
    } catch (e) {
      aiDiv.textContent = "⚠️ " + e.message;
      mochi.classList.remove("thinking"); statusEl.textContent = "your pocket agent ✨";
      return;
    }
    fullText += text;
    if (!toolCalls.length) break;
    // run tools, append results as user-role function responses
    const parts = [];
    for (const tc of toolCalls) {
      const result = await runTool(tc.name, tc.args);
      parts.push({ functionResponse: { name: tc.name, response: { result } } });
    }
    messages.push({ role: "ai", text: fullText || "(calling tools…)" });
    messages.push({ role: "user", text: "[tool results]", _fr: parts });
    // rebuild real API messages from tool results
    messages = toApiMessages(messages, parts);
  }
  renderAi(aiDiv, fullText || "(no response)");
  history.push({ role: "user", text: userText }, { role: "ai", text: fullText });
  history = history.slice(-40);
  store.set("history", history);
  mochi.classList.remove("thinking"); statusEl.textContent = "your pocket agent ✨";
}

// convert our log into Gemini contents, splicing function responses properly
function toApiMessages(messages, lastParts) {
  const out = [];
  for (const m of messages) {
    if (m._fr) { out.push({ role: "user", _parts: m._fr }); continue; }
    out.push({ role: m.role, text: m.text });
  }
  return out;
}

/* ---------------- ui ---------------- */
function scrollDown() { chat.scrollTop = chat.scrollHeight; }

function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function md(t) {
  // tiny markdown: code blocks, inline code, bold, line breaks
  let h = esc(t);
  h = h.replace(/```([\s\S]*?)```/g, (m, c) => "<pre>" + c + "</pre>");
  h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
  h = h.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  h = h.replace(/\n/g, "<br>");
  return h;
}

function addMsg(role, text) {
  $("welcome") && $("welcome").remove();
  const d = document.createElement("div");
  d.className = "msg " + role;
  d.innerHTML = role === "ai" ? md(text) : esc(text);
  chat.appendChild(d); scrollDown();
  return d;
}

function renderAi(div, text) { div.innerHTML = md(text); scrollDown(); }

function send() {
  const t = inp.value.trim();
  if (!t) return;
  if (!settings.key) {
    addMsg("sys", "⚠️ Add your Gemini API key in ⚙️ Settings first.");
    openSheet();
    return;
  }
  inp.value = ""; inp.style.height = "auto";
  addMsg("user", t);
  sendBtn.disabled = true;
  chatTurn(t).finally(() => { sendBtn.disabled = false; });
}

sendBtn.onclick = send;
inp.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
inp.addEventListener("input", () => {
  inp.style.height = "auto";
  inp.style.height = Math.min(inp.scrollHeight, 110) + "px";
});

/* ---------------- settings ---------------- */
const sheet = $("sheet");
function openSheet() {
  $("apikey").value = settings.key || "";
  $("model").value = settings.model;
  $("username").value = settings.name || "";
  updateKeyStat();
  sheet.classList.add("open");
}
function closeSheet() { sheet.classList.remove("open"); }
function updateKeyStat() {
  const el = $("keystat");
  if ((settings.key || "").startsWith("AIza") && settings.key.length > 20) {
    el.textContent = "✓ key looks valid"; el.className = "ok";
  } else if (settings.key) {
    el.textContent = "⚠ key looks short — check it"; el.className = "";
  } else { el.textContent = "Get a free key: aistudio.google.com/apikey"; el.className = ""; }
}
$("btn-settings").onclick = openSheet;
$("btn-close").onclick = closeSheet;
sheet.addEventListener("click", e => { if (e.target === sheet) closeSheet(); });
$("apikey").addEventListener("input", e => {
  settings.key = e.target.value.trim(); updateKeyStat();
});
$("btn-save").onclick = () => {
  settings.key = $("apikey").value.trim();
  settings.model = $("model").value;
  settings.name = $("username").value.trim();
  store.set("settings", settings);
  updateKeyStat();
  addMsg("sys", "✅ Settings saved.");
  closeSheet();
};
$("btn-clear").onclick = () => {
  history = []; store.del("history");
  chat.innerHTML = "";
  addMsg("sys", "🗑 Chat history cleared.");
};

/* ---------------- boot ---------------- */
(function boot() {
  if (!settings.key) setTimeout(openSheet, 600);
  // restore history
  $("welcome") && history.length && $("welcome").remove();
  for (const m of history.slice(-20)) addMsg(m.role, m.text);
  if (history.length) addMsg("sys", "👋 Welcome back!");
})();
