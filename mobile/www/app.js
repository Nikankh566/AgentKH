/* Agent KH — Android edition v2.
   Providers: Google Gemini / OpenAI-compatible. Key stays on-device.
   Tools run locally: notes, reminders, memory, URL fetch. */
"use strict";

const $ = id => document.getElementById(id);
const chat = $("chat"), inp = $("inp"), sendBtn = $("send");
const avatar = $("avatar"), statusEl = $("status");

/* ---------------- storage ---------------- */
const store = {
  get(k, d) { try { const v = localStorage.getItem("akh2_" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("akh2_" + k, JSON.stringify(v)); } catch (e) {} },
  del(k) { try { localStorage.removeItem("akh2_" + k); } catch (e) {} },
};

const DEF = { provider: "gemini", key: "", model: "gemini-3.5-flash",
              baseUrl: "", oaKey: "", oaModel: "", name: "" };
let settings = Object.assign({}, DEF, store.get("settings", {}));
let history = store.get("history", []);
let notes = store.get("notes", []);
let memory = store.get("memory", []);

/* ---------------- tools ---------------- */
const TOOL_DEFS_GEMINI = [{ functionDeclarations: [
  { name: "save_note", description: "Save a short note for the user",
    parameters: { type: "OBJECT", properties: { text: { type: "STRING" } }, required: ["text"] } },
  { name: "list_notes", description: "List saved notes", parameters: { type: "OBJECT", properties: {} } },
  { name: "delete_note", description: "Delete a note by its 1-based number from list_notes",
    parameters: { type: "OBJECT", properties: { n: { type: "NUMBER" } }, required: ["n"] } },
  { name: "set_reminder", description: "Set a reminder N minutes from now",
    parameters: { type: "OBJECT", properties: { minutes: { type: "NUMBER" }, text: { type: "STRING" } },
                  required: ["minutes", "text"] } },
  { name: "remember", description: "Remember a long-term fact about the user",
    parameters: { type: "OBJECT", properties: { fact: { type: "STRING" } }, required: ["fact"] } },
  { name: "fetch_url", description: "Fetch a web page, return its text (first 4000 chars)",
    parameters: { type: "OBJECT", properties: { url: { type: "STRING" } }, required: ["url"] } },
]}];

const TOOL_DEFS_OAI = [
  { type: "function", function: { name: "save_note", description: "Save a short note for the user",
    parameters: { type: "object", properties: { text: { type: "string" } }, required: ["text"] } } },
  { type: "function", function: { name: "list_notes", description: "List saved notes",
    parameters: { type: "object", properties: {} } } },
  { type: "function", function: { name: "delete_note", description: "Delete a note by its 1-based number",
    parameters: { type: "object", properties: { n: { type: "number" } }, required: ["n"] } } },
  { type: "function", function: { name: "set_reminder", description: "Set a reminder N minutes from now",
    parameters: { type: "object", properties: { minutes: { type: "number" }, text: { type: "string" } },
                  required: ["minutes", "text"] } } },
  { type: "function", function: { name: "remember", description: "Remember a long-term fact about the user",
    parameters: { type: "object", properties: { fact: { type: "string" } }, required: ["fact"] } } },
  { type: "function", function: { name: "fetch_url", description: "Fetch a web page, return its text",
    parameters: { type: "object", properties: { url: { type: "string" } }, required: ["url"] } } },
];

function toolBubble(text) {
  const d = document.createElement("div");
  d.className = "msg tool";
  d.textContent = text;
  chat.appendChild(d); scrollDown();
}

async function runTool(name, args) {
  args = args || {};
  switch (name) {
    case "save_note":
      notes.push({ t: Date.now(), text: String(args.text || "") });
      store.set("notes", notes); toolBubble("Note saved."); return "Note saved.";
    case "list_notes":
      if (!notes.length) { toolBubble("No notes yet."); return "No notes saved."; }
      { const s = notes.map((n, i) => (i + 1) + ". " + n.text).join("\n");
        toolBubble(s); return s; }
    case "delete_note": {
      const i = Math.round(Number(args.n)) - 1;
      if (!(i >= 0 && i < notes.length)) return "Invalid note number.";
      notes.splice(i, 1); store.set("notes", notes);
      toolBubble("Note deleted."); return "Note deleted.";
    }
    case "set_reminder": {
      const mins = Math.max(1, Math.round(Number(args.minutes)));
      const text = String(args.text || "Reminder");
      scheduleReminder(mins * 60000, text);
      toolBubble(`Reminder set · ${mins} min · ${text}`);
      return `Reminder set for ${mins} minutes from now.`;
    }
    case "remember":
      memory.push(String(args.fact || ""));
      store.set("memory", memory.slice(-50));
      toolBubble("Remembered."); return "Fact remembered.";
    case "fetch_url":
      try {
        const r = await fetch(String(args.url), { headers: { "User-Agent": "AgentKH-Android" } });
        const t = await r.text();
        const clean = t.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ")
          .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 4000);
        return clean || "(empty page)";
      } catch (e) { return "Fetch failed: " + e.message; }
    default: return "Unknown tool: " + name;
  }
}

async function scheduleReminder(ms, text) {
  try {
    if (window.Capacitor && Capacitor.isPluginAvailable("LocalNotifications")) {
      const { LocalNotifications } = await import("@capacitor/local-notifications");
      await LocalNotifications.requestPermissions();
      await LocalNotifications.schedule({ notifications: [{
        id: Date.now() % 2147483647, title: "Agent KH",
        body: text, schedule: { at: new Date(Date.now() + ms) } }] });
      return;
    }
  } catch (e) {}
  setTimeout(() => { toolBubble("Reminder: " + text);
    try { navigator.vibrate && navigator.vibrate(300); } catch (e) {} }, ms);
}

/* ---------------- providers ---------------- */
function systemPrompt() {
  const mem = memory.length ? "\nKnown facts about the user:\n- " + memory.join("\n- ") : "";
  const nm = settings.name ? ` The user's name is ${settings.name}.` : "";
  return `You are Agent KH, a helpful personal AI agent on the user's Android phone.${nm}` +
    ` Be warm and concise. Tools available: save/list/delete notes, set_reminder (minutes),` +
    ` remember facts, fetch_url.${mem}`;
}

function activeCreds() {
  if (settings.provider === "openai")
    return { key: settings.oaKey, model: settings.oaModel,
             base: (settings.baseUrl || "").replace(/\/+$/, "") };
  return { key: settings.key, model: settings.model, base: "" };
}

/* ----- Gemini ----- */
async function* streamGemini(sys, msgs) {
  const c = activeCreds();
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(c.model)}:streamGenerateContent?alt=sse&key=${encodeURIComponent(c.key)}`;
  const contents = [];
  for (const m of msgs) {
    if (m.tool) { contents.push({ role: "user", parts: m.tool }); continue; }
    if (m.calls) { // assistant message that made tool calls
      const parts = [];
      if (m.text) parts.push({ text: m.text });
      for (const tc of m.calls) parts.push({ functionCall: { name: tc.name, args: tc.args } });
      contents.push({ role: "model", parts });
      continue;
    }
    contents.push({ role: m.role === "ai" ? "model" : "user", parts: [{ text: m.text }] });
  }
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ system_instruction: { parts: [{ text: sys }] }, contents, tools: TOOL_DEFS_GEMINI }) });
  if (!r.ok) throw new Error(`HTTP ${r.status} · ${(await r.text()).slice(0, 220)}`);
  yield* readSSE(r, chunk => {
    const cand = (chunk.candidates || [])[0];
    if (chunk.promptFeedback && chunk.promptFeedback.blockReason)
      throw new Error("Blocked by safety filter: " + chunk.promptFeedback.blockReason);
    if (!cand || !cand.content) return null;
    const out = { text: "", calls: [] };
    for (const p of cand.content.parts || []) {
      if (p.text) out.text += p.text;
      if (p.functionCall) out.calls.push({ name: p.functionCall.name, args: p.functionCall.args || {} });
    }
    return out;
  });
}

/* ----- OpenAI-compatible ----- */
async function* streamOpenAI(sys, msgs) {
  const c = activeCreds();
  if (!c.base) throw new Error("Base URL is empty.");
  const url = c.base + "/v1/chat/completions";
  const messages = [{ role: "system", content: sys }];
  for (const m of msgs) {
    if (m.tool) { messages.push({ role: "tool", tool_call_id: m.tool.id, content: m.tool.result }); continue; }
    if (m.calls) {
      messages.push({ role: "assistant", content: m.text || "",
        tool_calls: m.calls.map((tc, i) => ({ id: tc.id || ("call_" + i), type: "function",
          function: { name: tc.name, arguments: JSON.stringify(tc.args) } })) });
      continue;
    }
    messages.push({ role: m.role === "ai" ? "assistant" : "user", content: m.text });
  }
  const r = await fetch(url, { method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + c.key },
    body: JSON.stringify({ model: c.model, messages, tools: TOOL_DEFS_OAI, stream: true }) });
  if (!r.ok) throw new Error(`HTTP ${r.status} · ${(await r.text()).slice(0, 220)}`);
  let callBuf = {};
  yield* readSSE(r, chunk => {
    const d = (chunk.choices || [])[0];
    if (!d || !d.delta) return null;
    const out = { text: d.delta.content || "", calls: [] };
    for (const tc of d.delta.tool_calls || []) {
      const i = tc.index || 0;
      callBuf[i] = callBuf[i] || { name: "", args: "" };
      if (tc.function) {
        if (tc.function.name) callBuf[i].name += tc.function.name;
        if (tc.function.arguments) callBuf[i].args += tc.function.arguments;
      }
      if (tc.id) callBuf[i].id = tc.id;
    }
    if (d.finish_reason === "tool_calls") {
      for (const k of Object.keys(callBuf)) {
        const b = callBuf[k];
        let args = {};
        try { args = JSON.parse(b.args || "{}"); } catch (e) {}
        out.calls.push({ id: b.id, name: b.name, args });
      }
      callBuf = {};
    }
    return out;
  });
}

/* ----- SSE reader ----- */
async function* readSSE(response, pick) {
  const ct = (response.headers.get("content-type") || "").toLowerCase();
  if (ct.includes("text/html")) {
    const t = (await response.text()).slice(0, 200);
    throw new Error("Network returned a web page instead of API data (proxy/VPN?). " + t);
  }
  const reader = response.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const segs = buf.split("\n\n");
      buf = segs.pop();
      for (const s of segs) {
        const line = s.split("\n").map(l => l.trim()).find(l => l.startsWith("data:"));
        if (!line) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") return;
        let j;
        try { j = JSON.parse(data); } catch (e) { continue; }
        const out = pick(j);
        if (out) yield out;
      }
    }
  } finally { try { reader.cancel(); } catch (e) {} }
}

/* ---------------- agentic chat loop ---------------- */
async function chatTurn(userText) {
  const c = activeCreds();
  if (!c.key) { addMsg("sys", "err", "Add your API key in Settings first."); openSheet(); return; }
  if (settings.provider === "openai" && !c.model) { addMsg("sys", "err", "Set a model name in Settings."); openSheet(); return; }

  const stream = settings.provider === "openai" ? streamOpenAI : streamGemini;
  const sys = systemPrompt();
  let msgs = history.concat([{ role: "user", text: userText }]);
  let fullText = "";
  const aiDiv = addMsg("ai", "");
  setBusy(true);
  aiDiv.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';

  try {
    for (let step = 0; step < 6; step++) {
      let text = "", calls = [];
      for await (const part of stream(sys, msgs)) {
        if (part.text) { text += part.text; renderAi(aiDiv, fullText + text); }
        if (part.calls && part.calls.length) calls = calls.concat(part.calls);
      }
      fullText += text;
      if (!calls.length) break;
      // run tools
      if (settings.provider === "openai") {
        msgs.push({ role: "ai", text, calls });
        for (const tc of calls) {
          const result = await runTool(tc.name, tc.args);
          msgs.push({ tool: { id: tc.id || ("call_" + Math.random().toString(36).slice(2)), result: String(result) } });
        }
      } else {
        msgs.push({ role: "ai", text, calls });
        const fr = [];
        for (const tc of calls) {
          const result = await runTool(tc.name, tc.args);
          fr.push({ functionResponse: { name: tc.name, response: { result: String(result) } } });
        }
        msgs.push({ tool: fr });
      }
    }
  } catch (e) {
    aiDiv.innerHTML = "";
    addMsg("sys", "err", "Error: " + e.message);
    setBusy(false);
    return;
  }
  renderAi(aiDiv, fullText.trim() || "(empty response — try again)");
  history.push({ role: "user", text: userText }, { role: "ai", text: fullText });
  history = history.slice(-40);
  store.set("history", history);
  setBusy(false);
}

function setBusy(b) {
  avatar.classList.toggle("thinking", b);
  statusEl.textContent = b ? "thinking…" : "your pocket agent";
  sendBtn.disabled = b;
}

/* ---------------- connection test ---------------- */
async function testConnection(out) {
  const c = activeCreds();
  out.className = ""; out.textContent = "Testing…";
  try {
    if (!c.key) throw new Error("API key is empty.");
    if (settings.provider === "openai") {
      if (!c.base) throw new Error("Base URL is empty.");
      if (!c.model) throw new Error("Model is empty.");
      const r = await fetch(c.base + "/v1/chat/completions", { method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + c.key },
        body: JSON.stringify({ model: c.model, messages: [{ role: "user", content: "Say OK" }], max_tokens: 5 }) });
      if (!r.ok) throw new Error(`HTTP ${r.status} · ${(await r.text()).slice(0, 200)}`);
      const j = await r.json();
      const t = (((j.choices || [])[0] || {}).message || {}).content || "";
      out.className = "ok"; out.textContent = "Connected · model replied: " + t.slice(0, 80);
    } else {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(c.model)}:generateContent?key=${encodeURIComponent(c.key)}`;
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contents: [{ parts: [{ text: "Say OK" }] }] }) });
      if (!r.ok) throw new Error(`HTTP ${r.status} · ${(await r.text()).slice(0, 200)}`);
      const j = await r.json();
      if (j.promptFeedback && j.promptFeedback.blockReason)
        throw new Error("Blocked: " + j.promptFeedback.blockReason);
      const t = ((((j.candidates || [])[0] || {}).content || {}).parts || []).map(p => p.text || "").join("");
      out.className = "ok"; out.textContent = "Connected · model replied: " + t.slice(0, 80);
    }
  } catch (e) {
    out.className = "bad"; out.textContent = "Failed: " + e.message;
  }
}

/* ---------------- ui ---------------- */
function scrollDown() { chat.scrollTop = chat.scrollHeight; }
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function md(t) {
  let h = esc(t);
  h = h.replace(/```([\s\S]*?)```/g, (m, c) => "<pre>" + c + "</pre>");
  h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
  h = h.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  const urlRe = /(^|\s)(https?:\/\/[^\s<]+)/g;
  h = h.replace(urlRe, '$1<a href="$2" target="_blank">$2</a>');
  h = h.replace(/\n/g, "<br>");
  return h;
}
function addMsg(role, cls, text) {
  if (arguments.length === 2) { text = cls; cls = ""; }
  const w = $("welcome"); if (w) w.remove();
  const d = document.createElement("div");
  d.className = "msg " + role + (cls ? " " + cls : "");
  d.innerHTML = role === "ai" ? md(text) : esc(text);
  chat.appendChild(d); scrollDown();
  return d;
}
function renderAi(div, text) { div.innerHTML = md(text); scrollDown(); }

function send() {
  const t = inp.value.trim();
  if (!t || sendBtn.disabled) return;
  inp.value = ""; inp.style.height = "auto";
  addMsg("user", t);
  chatTurn(t);
}
sendBtn.onclick = send;
inp.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
inp.addEventListener("input", () => {
  inp.style.height = "auto";
  inp.style.height = Math.min(inp.scrollHeight, 120) + "px";
});

/* ---------------- settings ---------------- */
const sheet = $("sheet");
function openSheet() { syncSettingsUI(); sheet.classList.add("open"); }
function closeSheet() { sheet.classList.remove("open"); }

function syncSettingsUI() {
  document.querySelectorAll("#provseg button").forEach(b =>
    b.classList.toggle("on", b.dataset.p === settings.provider));
  $("f-gemini").style.display = settings.provider === "gemini" ? "" : "none";
  $("f-openai").style.display = settings.provider === "openai" ? "" : "none";
  $("apikey").value = settings.key || "";
  $("model").value = settings.model;
  $("baseurl").value = settings.baseUrl || "";
  $("oapikey").value = settings.oaKey || "";
  $("oamodel").value = settings.oaModel || "";
  $("username").value = settings.name || "";
  $("testout").className = ""; $("testout").textContent = "";
  updateKeyStat();
}
function updateKeyStat() {
  const el = $("keystat");
  if (settings.provider !== "gemini") { el.className = ""; el.textContent = ""; return; }
  const k = $("apikey").value.trim();
  if (k.length > 20) { el.textContent = "Key length looks OK"; el.className = "ok"; }
  else if (k) { el.textContent = "Key looks short — double-check it"; el.className = "bad"; }
  else { el.textContent = "Free key: aistudio.google.com/apikey"; el.className = ""; }
}
document.querySelectorAll("#provseg button").forEach(b =>
  b.onclick = () => { settings.provider = b.dataset.p; syncSettingsUI(); });
$("apikey").addEventListener("input", updateKeyStat);
$("btn-settings").onclick = openSheet;
$("welcome-settings").onclick = openSheet;
$("btn-close").onclick = closeSheet;
sheet.addEventListener("click", e => { if (e.target === sheet) closeSheet(); });
$("btn-test").onclick = () => {
  // read current field values first
  readFields();
  testConnection($("testout"));
};
function readFields() {
  settings.key = $("apikey").value.trim();
  settings.model = $("model").value;
  settings.baseUrl = $("baseurl").value.trim();
  settings.oaKey = $("oapikey").value.trim();
  settings.oaModel = $("oamodel").value.trim();
  settings.name = $("username").value.trim();
}
$("btn-save").onclick = () => {
  readFields();
  store.set("settings", settings);
  updateKeyStat();
  addMsg("sys", "ok", "Settings saved.");
  closeSheet();
};
$("btn-clear").onclick = () => {
  history = []; store.del("history");
  chat.innerHTML = "";
  addMsg("sys", "", "Chat history cleared.");
};

/* ---------------- boot ---------------- */
(function boot() {
  const w = $("welcome"); if (w && history.length) w.remove();
  for (const m of history.slice(-20)) addMsg(m.role, m.text);
  if (history.length) addMsg("sys", "", "Welcome back.");
  const c = activeCreds();
  if (!c.key) setTimeout(openSheet, 700);
})();
