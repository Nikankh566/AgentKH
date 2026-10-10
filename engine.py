#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py — Agent KH core: config, LLM client, tools, agent loop.
UI-agnostic: the caller runs AgentEngine.chat() in a worker thread and
receives events through callbacks.

Callbacks (all called from the worker thread):
  on_token(text)                 — streamed reply chunk
  on_tool_start(name, args)      — a tool is about to run
  on_tool_end(name, ok, denied)  — tool finished
  on_approval(name, args)        — MUST return "allow" | "deny" | "always"
  on_error(text)
  on_end()
"""
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

try:
    import desktop as _desktop
except Exception:
    _desktop = None

try:
    import mcp as _mcp_mod
except Exception:
    _mcp_mod = None

if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
DB_PATH = os.path.join(ROOT, "agentkh.db")
SOUL_PATH = os.path.join(ROOT, "soul.md")

DEFAULT_CONFIG = {
    "provider": "gemini",            # "gemini" | "custom"
    "gemini_key": "",
    "gemini_model": "gemini-3.5-flash",
    "custom_base_url": "http://localhost:11434/v1",
    "custom_key": "",
    "custom_model": "",
    "auto_approve": False,
    "home_only": True,
    "mcp_servers": {},
    "lang": "en",                   # "en" (default) | "fa"
    "theme": "#7c6cf5",
}

STRINGS = {
    "en": {
        "need_key": "Add your API key in Settings first.",
        "stopped": "Stopped after 8 tool steps.",
        "new_chat": "New conversation started.",
    },
    "fa": {
        "need_key": "اول کلید API رو توی تنظیمات وارد کن.",
        "stopped": "بعد از ۸ مرحله متوقف شد.",
        "new_chat": "گفتگوی جدید شروع شد.",
    },
}


class Engine:
    def __init__(self):
        self.config = self.load_config()
        self.lock = threading.Lock()
        self.mcp = None
        self.always_allow = set()
        self._busy = False

    # ------------------------------------------------------------ config
    def load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(CONFIG_PATH):
            try:
                cfg.update(json.load(open(CONFIG_PATH, encoding="utf-8")))
            except Exception:
                pass
        return cfg

    def save_config(self):
        with self.lock:
            json.dump(self.config, open(CONFIG_PATH, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)

    def T(self, key):
        lang = self.config.get("lang", "en")
        return STRINGS.get(lang, STRINGS["en"]).get(key, key)

    def connect_mcp(self):
        if _mcp_mod is None or not self.config.get("mcp_servers"):
            return
        try:
            self.mcp = _mcp_mod.MCPManager(self.config["mcp_servers"])
            self.mcp.start_all()
        except Exception as e:
            print("MCP init failed: %s" % e)

    # ------------------------------------------------------------ db
    def db(self):
        con = sqlite3.connect(DB_PATH)
        con.execute("""CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT, content TEXT, ts REAL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS memory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT UNIQUE, ts REAL)""")
        return con

    def load_soul(self):
        if os.path.exists(SOUL_PATH):
            return open(SOUL_PATH, encoding="utf-8").read()
        return "You are Agent KH, a helpful personal AI agent."

    def save_soul(self, text):
        open(SOUL_PATH, "w", encoding="utf-8").write(text)

    def get_history(self, limit=60):
        con = self.db()
        rows = [(r[0], r[1]) for r in con.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,))]
        con.close()
        rows.reverse()
        return rows

    def clear_history(self):
        con = self.db()
        con.execute("DELETE FROM messages")
        con.commit()
        con.close()

    # ------------------------------------------------------------ llm
    def llm_config(self):
        cfg = self.config
        if cfg.get("provider") == "custom":
            return (cfg.get("custom_base_url", "").rstrip("/"),
                    cfg.get("custom_key", ""),
                    cfg.get("custom_model", ""))
        return ("https://generativelanguage.googleapis.com/v1beta/openai",
                cfg.get("gemini_key", ""),
                cfg.get("gemini_model", "gemini-3.5-flash"))

    def chat_completion(self, base_url, api_key, model, messages, tools):
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {"model": model, "messages": messages, "tools": tools,
                   "tool_choice": "auto", "stream": False}
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

    # ------------------------------------------------------------ tools
    def home_dir(self):
        return os.path.expanduser("~")

    def safe_path(self, p):
        p = os.path.abspath(os.path.expanduser(p or "~"))
        if self.config.get("home_only"):
            h = os.path.abspath(self.home_dir())
            if not (p == h or p.startswith(h + os.sep)):
                raise PermissionError("Out of allowed area (home only): " + p)
        return p

    # -- tool implementations (methods so they can use self) --
    def tool_run_command(self, args):
        cmd = args.get("command", "")
        cwd = self.safe_path(args.get("cwd") or "~")
        if not cmd.strip():
            return "empty command"
        try:
            r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                               text=True, timeout=120)
            out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr)
                                      if r.stderr else "")
            return out[-6000:] or "(no output, exit %d)" % r.returncode
        except subprocess.TimeoutExpired:
            return "command timed out after 120s"
        except Exception as e:
            return "error: %s" % e

    def tool_read_file(self, args):
        p = self.safe_path(args.get("path", ""))
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                data = f.read(20000)
            return data + ("\n...[truncated]" if len(data) == 20000 else "")
        except Exception as e:
            return "error: %s" % e

    def tool_write_file(self, args):
        p = self.safe_path(args.get("path", ""))
        content = args.get("content", "")
        try:
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return "written %d chars to %s" % (len(content), p)
        except Exception as e:
            return "error: %s" % e

    def tool_list_dir(self, args):
        p = self.safe_path(args.get("path") or "~")
        try:
            items = []
            for name in sorted(os.listdir(p)):
                full = os.path.join(p, name)
                items.append(("[dir] " if os.path.isdir(full) else "") + name)
            return "\n".join(items[:300]) or "(empty)"
        except Exception as e:
            return "error: %s" % e

    def tool_system_info(self, args):
        u = platform.uname()
        return ("os: %s %s (%s)\nnode: %s\ncpu: %s\npython: %s" %
                (u.system, u.release, u.machine, u.node,
                 os.cpu_count(), platform.python_version()))

    def tool_fetch_url(self, args):
        url = args.get("url", "")
        if not url.startswith(("http://", "https://")):
            return "only http(s) URLs"
        try:
            req = urllib.request.Request(url,
                                         headers={"User-Agent": "AgentKH/2.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read(30000).decode("utf-8", "replace")
            data = re.sub(r"<script.*?</script>", " ", data, flags=re.S | re.I)
            data = re.sub(r"<style.*?</style>", " ", data, flags=re.S | re.I)
            data = re.sub(r"<[^>]+>", " ", data)
            return re.sub(r"\s+", " ", data)[:6000]
        except Exception as e:
            return "error: %s" % e

    def tool_remember(self, args):
        fact = (args.get("fact") or "").strip()
        if not fact:
            return "empty fact"
        con = self.db()
        con.execute("INSERT OR IGNORE INTO memory(fact, ts) VALUES(?, ?)",
                    (fact, time.time()))
        con.commit()
        con.close()
        return "remembered: " + fact

    def _desk(self):
        if _desktop is None or not _desktop.available():
            raise RuntimeError("Mouse/keyboard unavailable on this machine.")
        return _desktop

    def tool_mouse_move(self, a):
        self._desk().move(a.get("x", 0), a.get("y", 0))
        return "mouse moved to (%s, %s)" % (a.get("x"), a.get("y"))

    def tool_mouse_click(self, a):
        d = self._desk()
        x, y = a.get("x"), a.get("y")
        d.click(a.get("button", "left"), x, y)
        at = " at (%s, %s)" % (x, y) if x is not None and y is not None else ""
        return "%s click%s" % (a.get("button", "left"), at)

    def tool_mouse_dclick(self, a):
        d = self._desk()
        x, y = a.get("x"), a.get("y")
        d.double_click(x, y)
        return "double clicked" + (" at (%s, %s)" % (x, y)
                                   if x is not None else "")

    def tool_mouse_scroll(self, a):
        self._desk().scroll(int(a.get("amount", 3)))
        return "scrolled %s" % a.get("amount", 3)

    def tool_mouse_drag(self, a):
        self._desk().drag(a.get("x1"), a.get("y1"), a.get("x2"), a.get("y2"))
        return "dragged (%s,%s)->(%s,%s)" % (a.get("x1"), a.get("y1"),
                                             a.get("x2"), a.get("y2"))

    def tool_mouse_pos(self, a):
        x, y = self._desk().pos()
        return "mouse at (%d, %d)" % (x, y)

    def tool_screen_size(self, a):
        w, h = self._desk().size()
        return "screen %dx%d" % (w, h)

    def tool_type_text(self, a):
        t = a.get("text", "")
        if len(t) > 2000:
            raise ValueError("text too long (max 2000 chars)")
        self._desk().type_text(t)
        return "typed %d chars" % len(t)

    def tool_press_key(self, a):
        self._desk().press(a.get("key", ""))
        return "pressed " + str(a.get("key"))

    def tool_hotkey(self, a):
        keys = a.get("keys", [])
        if not isinstance(keys, list) or not keys or len(keys) > 4:
            raise ValueError("keys must be a list of 1-4 key names")
        self._desk().hotkey(keys)
        return "hotkey: " + "+".join(keys)

    def tool_screenshot(self, a):
        return {"__image__": self._desk().screenshot()}

    def tool_defs(self):
        T = self  # shorthand
        tools = [
            ("run_command", True, "Run a shell command on the user's computer.",
             T.tool_run_command, {"type": "object", "properties": {
                 "command": {"type": "string"}, "cwd": {"type": "string"}},
                 "required": ["command"]}),
            ("read_file", False, "Read a text file.",
             T.tool_read_file, {"type": "object", "properties": {
                 "path": {"type": "string"}}, "required": ["path"]}),
            ("write_file", True, "Write/create a text file (overwrites).",
             T.tool_write_file, {"type": "object", "properties": {
                 "path": {"type": "string"}, "content": {"type": "string"}},
                 "required": ["path", "content"]}),
            ("list_dir", False, "List files in a directory.",
             T.tool_list_dir, {"type": "object", "properties": {
                 "path": {"type": "string"}}}),
            ("system_info", False, "OS / CPU / python info.",
             T.tool_system_info, {"type": "object", "properties": {}}),
            ("fetch_url", False, "Fetch a web page as text.",
             T.tool_fetch_url, {"type": "object", "properties": {
                 "url": {"type": "string"}}, "required": ["url"]}),
            ("remember", False, "Save a long-term fact about the user.",
             T.tool_remember, {"type": "object", "properties": {
                 "fact": {"type": "string"}}, "required": ["fact"]}),
            ("mouse_move", True, "Move the mouse cursor to x,y.",
             T.tool_mouse_move, {"type": "object", "properties": {
                 "x": {"type": "number"}, "y": {"type": "number"}},
                 "required": ["x", "y"]}),
            ("mouse_click", True,
             "Click left/right/middle button, optionally at x,y first.",
             T.tool_mouse_click, {"type": "object", "properties": {
                 "button": {"type": "string"}, "x": {"type": "number"},
                 "y": {"type": "number"}}}),
            ("mouse_double_click", True, "Double-click, optionally at x,y.",
             T.tool_mouse_dclick, {"type": "object", "properties": {
                 "x": {"type": "number"}, "y": {"type": "number"}}}),
            ("mouse_scroll", True, "Scroll the mouse wheel (positive = up).",
             T.tool_mouse_scroll, {"type": "object", "properties": {
                 "amount": {"type": "number"}}}),
            ("mouse_drag", True, "Drag the mouse from (x1,y1) to (x2,y2).",
             T.tool_mouse_drag, {"type": "object", "properties": {
                 "x1": {"type": "number"}, "y1": {"type": "number"},
                 "x2": {"type": "number"}, "y2": {"type": "number"}},
                 "required": ["x1", "y1", "x2", "y2"]}),
            ("get_mouse_pos", False, "Get current mouse coordinates.",
             T.tool_mouse_pos, {"type": "object", "properties": {}}),
            ("get_screen_size", False, "Get screen resolution.",
             T.tool_screen_size, {"type": "object", "properties": {}}),
            ("type_text", True, "Type text with the keyboard.",
             T.tool_type_text, {"type": "object", "properties": {
                 "text": {"type": "string"}}, "required": ["text"]}),
            ("press_key", True,
             "Press a key: enter, tab, esc, space, arrows, f1-f12, win, ...",
             T.tool_press_key, {"type": "object", "properties": {
                 "key": {"type": "string"}}, "required": ["key"]}),
            ("hotkey", True, "Press a key combo, e.g. [ctrl, s].",
             T.tool_hotkey, {"type": "object", "properties": {
                 "keys": {"type": "array", "items": {"type": "string"}}},
                 "required": ["keys"]}),
            ("take_screenshot", False,
             "Capture the screen so you can SEE it (vision).",
             T.tool_screenshot, {"type": "object", "properties": {}}),
        ]
        out = [{"name": n, "approval": ap, "desc": d, "fn": fn,
                "schema": s} for (n, ap, d, fn, s) in tools]
        if self.mcp is not None:
            for md in self.mcp.tool_defs():
                sname, tname = md["_mcp"]
                out.append({"name": md["name"], "approval": True,
                            "desc": md["desc"], "schema": md["schema"],
                            "fn": self._mcp_fn(sname, tname)})
        return out

    def _mcp_fn(self, server_name, tool_name):
        def fn(args):
            return self.mcp.call(server_name, tool_name, args or {})
        return fn

    def openai_tools(self):
        return [{"type": "function",
                 "function": {"name": t["name"], "description": t["desc"],
                              "parameters": t["schema"]}}
                for t in self.tool_defs()]

    # ------------------------------------------------------------ agent loop
    def build_messages(self, user_text):
        con = self.db()
        mem = [r[0] for r in con.execute(
            "SELECT fact FROM memory ORDER BY id DESC LIMIT 40")]
        hist = [(r[0], r[1]) for r in con.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT 24")]
        con.close()
        hist.reverse()
        msgs = [{"role": "system",
                 "content": self.load_soul() + (
                     "\n\nLong-term memory about the user:\n" +
                     "\n".join("- " + m for m in mem) if mem else "")}]
        for role, content in hist:
            msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def save_message(self, role, content):
        con = self.db()
        con.execute("INSERT INTO messages(role, content, ts) VALUES(?,?,?)",
                    (role, content, time.time()))
        con.commit()
        con.close()

    @property
    def busy(self):
        return self._busy

    def chat(self, user_text, cb):
        """Blocking agent turn. Run in a worker thread."""
        self._busy = True
        try:
            self._chat_inner(user_text, cb)
        finally:
            self._busy = False

    def _chat_inner(self, user_text, cb):
        base_url, api_key, model = self.llm_config()
        if not api_key or not model:
            cb.on_error(self.T("need_key"))
            cb.on_end()
            return
        messages = self.build_messages(user_text)
        self.save_message("user", user_text)
        tools = self.openai_tools()
        tmap = {t["name"]: t for t in self.tool_defs()}

        for step in range(8):
            try:
                msg = self.chat_completion(base_url, api_key, model,
                                           messages, tools)
            except Exception as e:
                cb.on_error(str(e))
                cb.on_end()
                return

            text = msg.get("content") or ""
            tool_calls = []
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                tool_calls.append({"id": tc.get("id"),
                                   "name": fn.get("name"),
                                   "arguments": args})

            if not tool_calls:
                for i in range(0, len(text), 24):
                    cb.on_token(text[i:i + 24])
                    time.sleep(0.008)
                if text.strip():
                    self.save_message("assistant", text)
                cb.on_end()
                return

            messages.append(msg)  # verbatim (keeps thought_signature)

            for c in tool_calls:
                t = tmap.get(c["name"])
                if not t:
                    messages.append({"role": "tool",
                                     "tool_call_id": c["id"],
                                     "content": "unknown tool"})
                    continue
                cb.on_tool_start(c["name"], c["arguments"])
                denied = False
                if (t["approval"] and not self.config.get("auto_approve")
                        and c["name"] not in self.always_allow):
                    decision = cb.on_approval(c["name"], c["arguments"])
                    if decision == "always":
                        self.always_allow.add(c["name"])
                    elif decision != "allow":
                        denied = True
                if denied:
                    result = ("The user DENIED this action. Do not retry; "
                              "explain briefly and ask what to do instead.")
                else:
                    try:
                        result = t["fn"](c["arguments"])
                    except Exception as e:
                        result = "tool error: %s" % e
                cb.on_tool_end(c["name"], not denied, denied)
                if isinstance(result, dict) and "__image__" in result:
                    messages.append({"role": "tool",
                                     "tool_call_id": c["id"],
                                     "content": "screenshot captured."})
                    messages.append({"role": "user", "content": [
                        {"type": "text", "text":
                         "[screen image attached — look at it and continue]"},
                        {"type": "image_url", "image_url": {
                            "url": "data:image/png;base64," +
                                   result["__image__"]}},
                    ]})
                else:
                    messages.append({"role": "tool", "tool_call_id": c["id"],
                                     "content": str(result)[:6000]})

        cb.on_error(self.T("stopped"))
        cb.on_end()
