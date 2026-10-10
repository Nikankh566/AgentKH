# -*- coding: utf-8 -*-
"""
Agent KH v4 — island desktop agent with a web UI.
Python backend (engine/tools/updater/sfx) + HTML/CSS/JS frontend via pywebview.
"""
import json
import os
import queue
import sys
import threading
import time

import webview

import engine
from engine import Engine
import updater
import sfx

ISLAND_W, ISLAND_H = 240, 90
PANEL_W, PANEL_H = 700, 650

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _alt = os.path.join(sys._MEIPASS, "web")
    if os.path.isdir(_alt):
        WEB_DIR = _alt

UI_HTML = os.path.join(WEB_DIR, "ui.html")

GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]


class ChatCallback:
    """Implements engine's callback interface; pushes JS to the UI."""

    def __init__(self, bridge):
        self.b = bridge

    def on_token(self, text):
        self.b.push("onToken(%s)" % json.dumps(text))

    def on_error(self, msg):
        self.b.push("typingOff(); onStreamEnd(); onSys(%s,'err'); "
                    "setMood('error'); setLabel('error');"
                    % json.dumps(str(msg)))

    def on_end(self):
        self.b.push("typingOff(); onStreamEnd(); setMood('happy'); "
                    "setLabel('Agent KH'); "
                    "setTimeout(()=>{if(mochi.dataset.mood==='happy')setMood('idle')},1600);")

    def on_tool_start(self, name, args):
        short = json.dumps(args)
        if len(short) > 90:
            short = short[:90] + "…"
        self.b.push("onAct(%s); setMood('working');"
                    % json.dumps("⚙️ %s %s" % (name, short)))

    def on_approval(self, name, args):
        self.b._approval_ev.clear()
        self.b.push("showApproval(%s,%s)"
                    % (json.dumps(name), json.dumps(args)))
        self.b._approval_ev.wait()          # blocks until JS decides
        d = self.b._decision
        if d == "always":
            self.b.eng.always_allow.add(name)
            return "allow"
        return d

    def on_tool_end(self, name, ok, denied):
        mark = "✓" if ok and not denied else ("⛔" if denied else "✗")
        self.b.push("onAct(%s);"
                    % json.dumps("%s %s done" % (mark, name)))


class Bridge:
    """pywebview js_api: methods JS can call."""

    def __init__(self):
        self.eng = Engine()
        self.window = None
        self._js = queue.Queue()
        self._approval_ev = threading.Event()
        self._decision = "deny"
        self.muted = False

    # ---------------------------------------------------------- js -> py
    def push(self, code):
        self._js.put(code)

    def poll(self):
        items = []
        while True:
            try:
                items.append(self._js.get_nowait())
            except queue.Empty:
                break
        return items

    def send_message(self, text):
        threading.Thread(target=self._run_chat, args=(text,),
                         daemon=True).start()

    def _run_chat(self, text):
        try:
            self.eng.chat(text, ChatCallback(self))
        except Exception as e:
            self.push("onSys(%s,'err')" % json.dumps(str(e)))

    def decide(self, decision):
        self._decision = decision if decision in (
            "allow", "always", "deny") else "deny"
        self._approval_ev.set()

    def get_config(self):
        cfg = dict(self.eng.config)
        mcp = cfg.get("mcp_servers") or {}
        cfg["mcp_servers"] = [{"name": k, "cmd": v}
                              for k, v in mcp.items()]
        return cfg

    def save_config(self, cfg):
        c = self.eng.config
        c["provider"] = cfg.get("provider", "gemini")
        c["gemini_key"] = (cfg.get("gemini_key") or "").strip()
        c["gemini_model"] = (cfg.get("gemini_model") or "").strip()
        custom = cfg.get("custom") or {}
        c["custom_base_url"] = (custom.get("url") or "").strip()
        c["custom_key"] = (custom.get("key") or "").strip()
        c["custom_model"] = (custom.get("model") or "").strip()
        c["auto_approve"] = bool(cfg.get("auto_approve"))
        c["lang"] = cfg.get("lang", "en")
        mcp = {}
        for s in cfg.get("mcp_servers") or []:
            if s.get("name") and s.get("cmd"):
                mcp[s["name"]] = s["cmd"]
        c["mcp_servers"] = mcp
        self.eng.save_config()
        soul = cfg.get("soul")
        if soul is not None:
            self.eng.save_soul(soul)
        # refresh model pill
        self.push("document.getElementById('model-pill').textContent = %s;"
                  % json.dumps("⚪ " + c["gemini_model"].replace(
                      "gemini-", "")))

    def get_soul(self):
        return self.eng.load_soul()

    def get_version(self):
        return updater.VERSION

    def switch_model(self):
        cur = self.eng.config.get("gemini_model", GEMINI_MODELS[0])
        try:
            nxt = GEMINI_MODELS[(GEMINI_MODELS.index(cur) + 1)
                                % len(GEMINI_MODELS)]
        except ValueError:
            nxt = GEMINI_MODELS[0]
        self.eng.config["gemini_model"] = nxt
        self.eng.save_config()
        self.push("document.getElementById('model-pill').textContent = %s; "
                  "onSys(%s);"
                  % (json.dumps("⚪ " + nxt.replace("gemini-", "")),
                     json.dumps("model: " + nxt)))

    def clear_history(self):
        self.eng.clear_history()

    def set_muted(self, m):
        self.muted = bool(m)

    def save_theme(self, color):
        self.eng.config["theme"] = color
        self.eng.save_config()

    def sound(self, name):
        if not self.muted:
            fn = getattr(sfx, name, None)
            if fn:
                fn()

    def resize(self, w, h):
        if self.window:
            try:
                sw = self.window.screen.width
                self.window.resize(int(w), int(h))
                self.window.move((sw - int(w)) // 2, 0)
            except Exception:
                pass

    def check_updates(self):
        updater.check_in_background(self._on_update_found)

    def _on_update_found(self, tag, assets):
        self.push("showUpdate(%s)" % json.dumps(tag))
        self._update_assets = assets
        self._update_tag = tag

    def do_update(self):
        assets = getattr(self, "_update_assets", {})
        tag = getattr(self, "_update_tag", "")
        url = assets.get("AgentKH-Setup.exe")
        if not url:
            for n, u in assets.items():
                if n.lower().endswith(".exe"):
                    url = u
                    break
        if not url:
            self.push("updateProg('No installer found in this release.')")
            return
        threading.Thread(target=self._download_update,
                         args=(url, tag), daemon=True).start()

    def _download_update(self, url, tag):
        import tempfile
        dest = os.path.join(tempfile.gettempdir(),
                            "AgentKH-Setup-%s.exe" % tag.replace(".", "_"))

        def prog(done, total):
            pct = int(done * 100 / total) if total else 0
            self.push("updateProg(%s)" % json.dumps("Downloading… %d%%" % pct))
        try:
            updater.download(url, dest, progress=prog)
        except Exception as e:
            self.push("updateProg(%s)" % json.dumps("Download failed: %s" % e))
            return
        self.push("updateProg('Installing… see you in a moment! 👋')")
        time.sleep(0.6)
        # quit the webview, then run the installer
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass
        updater.install_setup_exe(dest)

    def boot_done(self):
        threading.Timer(12.0, self.check_updates).start()

    def quit_app(self):
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass
        os._exit(0)


def main():
    bridge = Bridge()
    with open(UI_HTML, encoding="utf-8") as f:
        html = f.read()
    win = webview.create_window(
        "Agent KH",
        html=html,
        width=ISLAND_W, height=ISLAND_H,
        frameless=True,
        transparent=True,
        on_top=True,
        resizable=False,
        focus=False,
        js_api=bridge,
    )
    bridge.window = win
    # top-center
    try:
        sw = win.screen.width
    except Exception:
        sw = 1280
    win.move((sw - ISLAND_W) // 2, 0)
    # JS polls for pushed events
    webview.start(debug=False)


if __name__ == "__main__":
    main()
