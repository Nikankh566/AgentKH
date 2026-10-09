#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jinni — personal desktop AI agent (Persian-first)
=================================================
Runs on your own computer, controls your system (with your approval),
and talks to Gemini API or any OpenAI-compatible API.

Zero dependencies — Python 3.9+ stdlib only.

Run:   python3 agentkh.py
Then:  opens http://127.0.0.1:8765 in your browser.
"""
import html
import json
import os
import platform
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

try:
    import desktop as _desktop
except Exception:
    _desktop = None

try:
    import mcp as _mcp_mod
except Exception:
    _mcp_mod = None

if getattr(sys, "frozen", False):
    # PyInstaller exe: resources live next to the exe
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
CONFIG_PATH = os.path.join(ROOT, "config.json")
DB_PATH = os.path.join(ROOT, "agentkh.db")
SOUL_PATH = os.path.join(ROOT, "soul.md")
PORT = 8765

DEFAULT_CONFIG = {
    "provider": "gemini",            # "gemini" | "custom"
    "gemini_key": "",
    "gemini_model": "gemini-3.5-flash",
    "custom_base_url": "http://localhost:11434/v1",
    "custom_key": "",
    "custom_model": "",
    "auto_approve": False,           # auto-approve run_command/write_file (use carefully)
    "home_only": True,              # restrict file tools to the user home dir
    "mcp_servers": {},              # {"name": {"command": "...", "args": [...]}}
    "lang": "en",                   # "en" (default) | "fa"
}


STRINGS = {
    "en": {
        "need_key": "API key or model is missing — open Settings (⚙️) first.",
        "stopped": "Stopped after 8 tool steps.",
        "new_chat": "🧹 New conversation started.",
        "model_set": "🤖 Model set to: ",
        "model_cur": "Current model: ",
        "slash_help": "Commands: /new (new chat), /model <name>",
    },
    "fa": {
        "need_key": "کلید API یا مدل وارد نشده — اول از تنظیمات (⚙️) وارد کن.",
        "stopped": "بعد از ۸ مرحله متوقف شد.",
        "new_chat": "🧹 گفتگوی جدید شروع شد.",
        "model_set": "🤖 مدل شد: ",
        "model_cur": "مدل فعلی: ",
        "slash_help": "دستورات: /new (گفتگوی جدید) ، /model <name>",
    },
}


def T(key):
    lang = CONFIG.get("lang", "en") if "CONFIG" in globals() else "en"
    return STRINGS.get(lang, STRINGS["en"]).get(key, key)

GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

# ---------------------------------------------------------------- config / db

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            cfg.update(json.load(open(CONFIG_PATH, encoding="utf-8")))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    json.dump(cfg, open(CONFIG_PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT, content TEXT, ts REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS memory(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fact TEXT UNIQUE, ts REAL)""")
    return con


def load_soul():
    if os.path.exists(SOUL_PATH):
        return open(SOUL_PATH, encoding="utf-8").read()
    return "You are Jinni, a helpful personal AI agent."


# ---------------------------------------------------------------- LLM client
# One code path: OpenAI-compatible /chat/completions with tools.
# Gemini works through its OpenAI-compatible endpoint; any custom
# OpenAI-compatible API (OpenRouter, Ollama /v1, ...) works too.

def llm_config(cfg):
    if cfg.get("provider") == "custom":
        return (cfg.get("custom_base_url", "").rstrip("/"),
                cfg.get("custom_key", ""),
                cfg.get("custom_model", ""))
    return (GEMINI_OPENAI_URL, cfg.get("gemini_key", ""),
            cfg.get("gemini_model", "gemini-3.5-flash"))


def chat_completion(base_url, api_key, model, messages, tools):
    """Non-streaming call. Returns the raw assistant message dict verbatim —
    it must be echoed back unchanged (Gemini needs its thought_signature)."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "stream": False,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + api_key})
    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError("API error %s: %s" % (e.code, body))
    data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]


# ---------------------------------------------------------------- tools

def home_dir():
    return os.path.expanduser("~")


def safe_path(p):
    """Resolve p; if home_only, keep it inside the user home."""
    p = os.path.abspath(os.path.expanduser(p or "~"))
    if CONFIG.get("home_only"):
        h = os.path.abspath(home_dir())
        if not (p == h or p.startswith(h + os.sep)):
            raise PermissionError("Out of allowed area (home only): " + p)
    return p


def tool_run_command(args):
    cmd = args.get("command", "")
    cwd = safe_path(args.get("cwd") or "~")
    if not cmd.strip():
        return "empty command"
    dangerous = ["rm -rf /", "mkfs", ":(){", "dd if=", "format c:",
                 "del /f /s /q c:\\"]
    warn = any(d in cmd for d in dangerous)
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                           text=True, timeout=120)
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        if warn:
            out = "[!!] This looked dangerous; ran anyway after approval.\n" + out
        return out[-6000:] or "(no output, exit %d)" % r.returncode
    except subprocess.TimeoutExpired:
        return "command timed out after 120s"
    except Exception as e:
        return "error: %s" % e


def tool_read_file(args):
    p = safe_path(args.get("path", ""))
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            data = f.read(20000)
        if len(data) == 20000:
            data += "\n...[truncated]"
        return data
    except Exception as e:
        return "error: %s" % e


def tool_write_file(args):
    p = safe_path(args.get("path", ""))
    content = args.get("content", "")
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return "written %d chars to %s" % (len(content), p)
    except Exception as e:
        return "error: %s" % e


def tool_list_dir(args):
    p = safe_path(args.get("path") or "~")
    try:
        items = []
        for name in sorted(os.listdir(p)):
            full = os.path.join(p, name)
            items.append(("[dir] " if os.path.isdir(full) else "") + name)
        return "\n".join(items[:300]) or "(empty)"
    except Exception as e:
        return "error: %s" % e


def tool_system_info(args):
    u = platform.uname()
    return ("os: %s %s (%s)\nnode: %s\ncpu: %s\npython: %s" %
            (u.system, u.release, u.machine, u.node,
             os.cpu_count(), platform.python_version()))


def tool_fetch_url(args):
    url = args.get("url", "")
    if not url.startswith(("http://", "https://")):
        return "only http(s) URLs"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgentKH/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read(30000).decode("utf-8", "replace")
        data = re.sub(r"<script.*?</script>", " ", data, flags=re.S | re.I)
        data = re.sub(r"<style.*?</style>", " ", data, flags=re.S | re.I)
        data = re.sub(r"<[^>]+>", " ", data)
        return re.sub(r"\s+", " ", data)[:6000]
    except Exception as e:
        return "error: %s" % e


def tool_remember(args):
    fact = (args.get("fact") or "").strip()
    if not fact:
        return "empty fact"
    con = db()
    con.execute("INSERT OR IGNORE INTO memory(fact, ts) VALUES(?, ?)",
                (fact, time.time()))
    con.commit()
    con.close()
    return "remembered: " + fact


# ---- desktop (mouse & keyboard) tools: all need approval except getters ----
def _desk():
    if _desktop is None or not _desktop.available():
        raise RuntimeError(
            "Mouse/keyboard control unavailable here. "
            "On Windows it works out of the box; elsewhere: pip install pyautogui")
    return _desktop


def tool_mouse_move(a):
    _desk().move(a.get("x", 0), a.get("y", 0))
    return "mouse moved to (%s, %s)" % (a.get("x"), a.get("y"))


def tool_mouse_click(a):
    d = _desk()
    x, y = a.get("x"), a.get("y")
    d.click(a.get("button", "left"), x, y)
    at = " at (%s, %s)" % (x, y) if x is not None and y is not None else ""
    return "%s click%s" % (a.get("button", "left"), at)


def tool_mouse_dclick(a):
    d = _desk()
    x, y = a.get("x"), a.get("y")
    d.double_click(x, y)
    return "double clicked" + (" at (%s, %s)" % (x, y) if x is not None else "")


def tool_mouse_scroll(a):
    _desk().scroll(int(a.get("amount", 3)))
    return "scrolled %s" % a.get("amount", 3)


def tool_mouse_drag(a):
    _desk().drag(a.get("x1"), a.get("y1"), a.get("x2"), a.get("y2"))
    return "dragged (%s,%s)->(%s,%s)" % (a.get("x1"), a.get("y1"),
                                         a.get("x2"), a.get("y2"))


def tool_mouse_pos(a):
    x, y = _desk().pos()
    return "mouse at (%d, %d)" % (x, y)


def tool_screen_size(a):
    w, h = _desk().size()
    return "screen %dx%d" % (w, h)


def tool_type_text(a):
    t = a.get("text", "")
    if len(t) > 2000:
        raise ValueError("text too long (max 2000 chars)")
    _desk().type_text(t)
    return "typed %d chars" % len(t)


def tool_press_key(a):
    _desk().press(a.get("key", ""))
    return "pressed " + str(a.get("key"))


def tool_hotkey(a):
    keys = a.get("keys", [])
    if not isinstance(keys, list) or not keys or len(keys) > 4:
        raise ValueError("keys must be a list of 1-4 key names")
    _desk().hotkey(keys)
    return "hotkey: " + "+".join(keys)


def tool_screenshot(a):
    # returns a dict; the agent loop turns it into an image message
    return {"__image__": _desk().screenshot()}


TOOLS = [
    {"name": "run_command", "approval": True,
     "desc": "Run a shell command on the user's computer.",
     "fn": tool_run_command,
     "schema": {"type": "object", "properties": {
         "command": {"type": "string"},
         "cwd": {"type": "string"}},
         "required": ["command"]}},
    {"name": "read_file", "approval": False,
     "desc": "Read a text file.",
     "fn": tool_read_file,
     "schema": {"type": "object", "properties": {
         "path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "approval": True,
     "desc": "Write/create a text file (overwrites).",
     "fn": tool_write_file,
     "schema": {"type": "object", "properties": {
         "path": {"type": "string"},
         "content": {"type": "string"}},
         "required": ["path", "content"]}},
    {"name": "list_dir", "approval": False,
     "desc": "List files in a directory.",
     "fn": tool_list_dir,
     "schema": {"type": "object", "properties": {
         "path": {"type": "string"}}}},
    {"name": "system_info", "approval": False,
     "desc": "OS / CPU / python info.",
     "fn": tool_system_info,
     "schema": {"type": "object", "properties": {}}},
    {"name": "fetch_url", "approval": False,
     "desc": "Fetch a web page as text.",
     "fn": tool_fetch_url,
     "schema": {"type": "object", "properties": {
         "url": {"type": "string"}}, "required": ["url"]}},
    {"name": "remember", "approval": False,
     "desc": "Save a long-term fact about the user.",
     "fn": tool_remember,
     "schema": {"type": "object", "properties": {
         "fact": {"type": "string"}}, "required": ["fact"]}},
    # --- desktop control (mouse & keyboard) ---
    {"name": "mouse_move", "approval": True,
     "desc": "Move the mouse cursor to screen coordinates x,y.",
     "fn": tool_mouse_move,
     "schema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"}},
         "required": ["x", "y"]}},
    {"name": "mouse_click", "approval": True,
     "desc": "Click a mouse button (left/right/middle), optionally at x,y first.",
     "fn": tool_mouse_click,
     "schema": {"type": "object", "properties": {
         "button": {"type": "string"}, "x": {"type": "number"},
         "y": {"type": "number"}}}},
    {"name": "mouse_double_click", "approval": True,
     "desc": "Double-click, optionally at x,y first.",
     "fn": tool_mouse_dclick,
     "schema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"}}}},
    {"name": "mouse_scroll", "approval": True,
     "desc": "Scroll the mouse wheel (positive = up).",
     "fn": tool_mouse_scroll,
     "schema": {"type": "object", "properties": {
         "amount": {"type": "number"}}}},
    {"name": "mouse_drag", "approval": True,
     "desc": "Drag the mouse from (x1,y1) to (x2,y2).",
     "fn": tool_mouse_drag,
     "schema": {"type": "object", "properties": {
         "x1": {"type": "number"}, "y1": {"type": "number"},
         "x2": {"type": "number"}, "y2": {"type": "number"}},
         "required": ["x1", "y1", "x2", "y2"]}},
    {"name": "get_mouse_pos", "approval": False,
     "desc": "Get current mouse cursor coordinates.",
     "fn": tool_mouse_pos,
     "schema": {"type": "object", "properties": {}}},
    {"name": "get_screen_size", "approval": False,
     "desc": "Get screen resolution (width x height).",
     "fn": tool_screen_size,
     "schema": {"type": "object", "properties": {}}},
    {"name": "type_text", "approval": True,
     "desc": "Type text with the keyboard (as if the user typed it).",
     "fn": tool_type_text,
     "schema": {"type": "object", "properties": {
         "text": {"type": "string"}}, "required": ["text"]}},
    {"name": "press_key", "approval": True,
     "desc": "Press a key: enter, tab, esc, space, up/down/left/right, f1-f12, win, delete, backspace, home, end, pageup, pagedown...",
     "fn": tool_press_key,
     "schema": {"type": "object", "properties": {
         "key": {"type": "string"}}, "required": ["key"]}},
    {"name": "hotkey", "approval": True,
     "desc": "Press a key combination, e.g. [ctrl, s] or [win, r].",
     "fn": tool_hotkey,
     "schema": {"type": "object", "properties": {
         "keys": {"type": "array", "items": {"type": "string"}}},
         "required": ["keys"]}},
    {"name": "take_screenshot", "approval": False,
     "desc": "Capture the screen so you can SEE it (vision). Use when you need to find something visually.",
     "fn": tool_screenshot,
     "schema": {"type": "object", "properties": {}}},
]
TOOL_MAP = {t["name"]: t for t in TOOLS}

MCP_MANAGER = None


def _mcp_tool_fn(server_name, tool_name):
    def fn(args):
        if MCP_MANAGER is None:
            raise RuntimeError("MCP not connected")
        return MCP_MANAGER.call(server_name, tool_name, args or {})
    return fn


def all_tools():
    """Static tools + live MCP server tools."""
    tools = list(TOOLS)
    if MCP_MANAGER is not None:
        for d in MCP_MANAGER.tool_defs():
            sname, tname = d["_mcp"]
            tools.append({
                "name": d["name"],
                "approval": True,   # external code: always ask
                "desc": d["desc"],
                "schema": d["schema"],
                "fn": _mcp_tool_fn(sname, tname),
            })
    return tools


def tool_map():
    return {t["name"]: t for t in all_tools()}


def openai_tools():
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["desc"],
                          "parameters": t["schema"]}} for t in all_tools()]


# ---------------------------------------------------------------- agent loop

pending_decisions = {}   # call_id -> {"event": Event, "decision": bool,
                                #                "name": str, "args": dict}
decision_lock = threading.Lock()
AGENT_BUSY = {"count": 0}


def wait_decision(call_id, name="", args=None, timeout=300):
    ev = threading.Event()
    with decision_lock:
        pending_decisions[call_id] = {"event": ev, "decision": False,
                                      "name": name, "args": args or {}}
    ok = ev.wait(timeout)
    with decision_lock:
        d = pending_decisions.pop(call_id, {"decision": False})
    return ok and d["decision"]


def set_decision(call_id, approved):
    with decision_lock:
        p = pending_decisions.get(call_id)
    if p:
        p["decision"] = bool(approved)
        p["event"].set()
        return True
    return False


def build_messages(user_text):
    con = db()
    mem = [r[0] for r in con.execute(
        "SELECT fact FROM memory ORDER BY id DESC LIMIT 40")]
    hist = [(r[0], r[1]) for r in con.execute(
        "SELECT role, content FROM messages ORDER BY id DESC LIMIT 24")]
    con.close()
    hist.reverse()
    msgs = [{"role": "system",
             "content": load_soul() + (
                 "\n\nLong-term memory about the user:\n" +
                 "\n".join("- " + m for m in mem) if mem else "")}]
    for role, content in hist:
        msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": user_text})
    return msgs


def save_message(role, content):
    con = db()
    con.execute("INSERT INTO messages(role, content, ts) VALUES(?,?,?)",
                (role, content, time.time()))
    con.commit()
    con.close()


def agent_run(user_text, emit):
    """Run the agent loop. emit(kind, payload) sends SSE events."""
    AGENT_BUSY["count"] += 1
    try:
        _agent_run_inner(user_text, emit)
    finally:
        AGENT_BUSY["count"] = max(0, AGENT_BUSY["count"] - 1)


def _agent_run_inner(user_text, emit):
    base_url, api_key, model = llm_config(CONFIG)
    if not api_key or not model:
        emit("error", T("need_key"))
        return
    messages = build_messages(user_text)
    save_message("user", user_text)
    tools = openai_tools()

    for step in range(8):
        try:
            msg = chat_completion(base_url, api_key, model,
                                  messages, tools)
        except Exception as e:
            emit("error", str(e))
            return

        text = msg.get("content") or ""
        raw_calls = msg.get("tool_calls") or []
        tool_calls = []
        for tc in raw_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            tool_calls.append({"id": tc.get("id"), "name": fn.get("name"),
                               "arguments": args})

        if not tool_calls:
            # stream the final text to the UI in chunks
            for i in range(0, len(text), 24):
                emit("token", text[i:i + 24])
                time.sleep(0.01)
            if text.strip():
                save_message("assistant", text)
            emit("end", "")
            return

        messages.append(msg)  # verbatim — keeps thought_signature etc.

        for c in tool_calls:
            t = tool_map().get(c["name"])
            if not t:
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": "unknown tool"})
                continue
            emit("tool_start", {"name": c["name"], "args": c["arguments"]})
            if t["approval"] and not CONFIG.get("auto_approve"):
                emit("approval", {"call_id": c["id"], "name": c["name"],
                                  "args": c["arguments"]})
                if not wait_decision(c["id"], c["name"], c["arguments"]):
                    result = "The user DENIED this action. Do not retry; " \
                             "explain briefly and ask what to do instead."
                    emit("tool_end", {"name": c["name"], "denied": True})
                else:
                    try:
                        result = t["fn"](c["arguments"])
                    except Exception as e:
                        result = "tool error: %s" % e
                    emit("tool_end", {"name": c["name"], "denied": False})
            else:
                try:
                    result = t["fn"](c["arguments"])
                except Exception as e:
                    result = "tool error: %s" % e
                emit("tool_end", {"name": c["name"], "denied": False})
            if isinstance(result, dict) and "__image__" in result:
                # vision: attach the screenshot as an image message
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": "screenshot captured."})
                messages.append({"role": "user", "content": [
                    {"type": "text",
                     "text": "[screen image attached — look at it and continue the task]"},
                    {"type": "image_url", "image_url": {
                        "url": "data:image/png;base64," + result["__image__"]}},
                ]})
            else:
                messages.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": str(result)[:6000]})
    emit("error", T("stopped"))


# ---------------------------------------------------------------- HTTP server

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css",
        ".js": "application/javascript", ".png": "image/png",
        ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def do_GET(self):
        p = urlparse(self.path)
        if p.path in ("/", "/index.html"):
            p_path = "/index.html"
        else:
            p_path = p.path
        if p.path == "/api/config":
            cfg = dict(CONFIG)
            return self._json(cfg)
        if p.path == "/api/memory":
            con = db()
            mem = [r[0] for r in con.execute(
                "SELECT fact FROM memory ORDER BY id DESC")]
            con.close()
            return self._json({"facts": mem})
        if p.path == "/api/history":
            con = db()
            hist = [{"role": r[0], "content": r[1]} for r in con.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT 60")]
            con.close()
            hist.reverse()
            return self._json({"messages": hist})
        if p.path == "/api/soul":
            return self._json({"soul": load_soul()})
        if p.path == "/api/pending":
            with decision_lock:
                items = [{"call_id": cid, "name": v.get("name", ""),
                          "args": v.get("args", {})}
                         for cid, v in pending_decisions.items()]
            return self._json({"pending": items[0] if items else None})
        if p.path == "/api/status":
            with decision_lock:
                has_pending = bool(pending_decisions)
            return self._json({"busy": AGENT_BUSY["count"] > 0,
                               "pending": has_pending,
                               "lang": CONFIG.get("lang", "en")})
        fpath = os.path.normpath(os.path.join(
            WEB_DIR, p_path.lstrip("/")))
        if not fpath.startswith(WEB_DIR) or not os.path.isfile(fpath):
            self.send_response(404)
            self.end_headers()
            return
        ext = os.path.splitext(fpath)[1]
        data = open(fpath, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type",
                         MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/chat":
            body = self._read_json()
            text = (body.get("message") or "").strip()
            if not text:
                return self._json({"ok": False})
            if text.startswith("/"):
                return self._handle_slash(text)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            def emit(kind, payload):
                try:
                    self.wfile.write(
                        ("event: %s\ndata: %s\n\n" %
                         (kind, json.dumps(payload,
                                           ensure_ascii=False))).encode())
                    self.wfile.flush()
                except Exception:
                    pass

            try:
                agent_run(text, emit)
            except (BrokenPipeError, ConnectionResetError):
                pass
            self.close_connection = True
            return
        if p.path == "/api/decision":
            body = self._read_json()
            ok = set_decision(body.get("call_id", ""),
                              body.get("approved", False))
            return self._json({"ok": ok})
        if p.path == "/api/config":
            body = self._read_json()
            for k in DEFAULT_CONFIG:
                if k in body:
                    CONFIG[k] = body[k]
            save_config(CONFIG)
            return self._json({"ok": True})
        if p.path == "/api/soul":
            body = self._read_json()
            open(SOUL_PATH, "w", encoding="utf-8").write(
                body.get("soul", ""))
            return self._json({"ok": True})
        if p.path == "/api/clear":
            con = db()
            con.execute("DELETE FROM messages")
            con.commit()
            con.close()
            return self._json({"ok": True})
        if p.path == "/api/forget":
            body = self._read_json()
            con = db()
            con.execute("DELETE FROM memory WHERE fact=?",
                        (body.get("fact", ""),))
            con.commit()
            con.close()
            return self._json({"ok": True})
        self.send_response(404)
        self.end_headers()

    def _handle_slash(self, text):
        cmd = text.split()[0].lower()
        if cmd == "/new":
            con = db()
            con.execute("DELETE FROM messages")
            con.commit()
            con.close()
            return self._json({"ok": True, "notice": T("new_chat")})
        if cmd == "/model":
            parts = text.split(None, 1)
            if len(parts) > 1:
                if CONFIG.get("provider") == "custom":
                    CONFIG["custom_model"] = parts[1].strip()
                else:
                    CONFIG["gemini_model"] = parts[1].strip()
                save_config(CONFIG)
                return self._json({"ok": True, "notice":
                                   T("model_set") + parts[1].strip()})
            return self._json({"ok": True, "notice":
                               T("model_cur") + llm_config(CONFIG)[2]})
        return self._json({"ok": True, "notice": T("slash_help")})


CONFIG = load_config()


def main():
    global MCP_MANAGER
    db().close()
    if not os.path.exists(CONFIG_PATH):
        save_config(CONFIG)
    # connect MCP servers (if configured)
    if _mcp_mod is not None and CONFIG.get("mcp_servers"):
        try:
            MCP_MANAGER = _mcp_mod.MCPManager(CONFIG["mcp_servers"])
            MCP_MANAGER.start_all()
        except Exception as e:
            print("⚠️ MCP init failed: %s" % e)
    # launch the Coucou-style top-of-screen companion (if tkinter exists)
    comp_py = os.path.join(ROOT, "companion.py")
    try:
        import tkinter  # noqa
        if getattr(sys, "frozen", False):
            # running as exe: launch the companion exe next to us
            comp_exe = os.path.join(ROOT, "AgentKH-Companion.exe")
            if os.path.exists(comp_exe):
                subprocess.Popen([comp_exe],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            else:
                raise RuntimeError("companion exe not found")
        else:
            subprocess.Popen([sys.executable, comp_py],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        print("🟣 Companion overlay launched (top of screen).")
    except Exception as e:
        print("   (companion overlay skipped: %s)" % e)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    print("✨ Agent KH is running at %s" % url)
    print("   Press Ctrl+C to stop.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
