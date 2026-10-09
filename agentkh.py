#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent KH v2 — Coucou-style island app.
One native window living at the top of the screen: click the island to
expand chat / activity / settings. No browser needed.

Run:  python agentkh.py        (or AgentKH.exe on Windows)
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

import engine
from engine import Engine
from mochi import MochiWidget

# ---------------------------------------------------------------- palette
BG = "#0b0b0d"        # island black
PANEL = "#141417"     # panel background
CARD = "#1e1e24"      # cards
CARD2 = "#26262e"
TEXT = "#f2f2f5"
DIM = "#9a9aa5"
GREEN = "#3ddc84"
ORANGE = "#ff9f2e"
RED = "#ff6b6b"
ACCENT = "#7c6cf5"

ISLAND_W, ISLAND_H = 210, 62
PANEL_W, PANEL_H = 660, 540


def rounded(canvas, x1, y1, x2, y2, r, **kw):
    pts = []
    for (cx, cy, a0) in [(x1 + r, y1 + r, 180), (x2 - r, y1 + r, 270),
                         (x2 - r, y2 - r, 0), (x1 + r, y2 - r, 90)]:
        for i in range(13):
            a = (a0 + i * 90 / 12) * 3.14159 / 180
            import math
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return canvas.create_polygon(pts, smooth=True, **kw)


class IslandApp:
    def __init__(self, eng):
        self.eng = eng
        self.q = queue.Queue()
        self.lang = eng.config.get("lang", "en")
        self.view = "chat"
        self.panel_open = False
        self.approval = None   # {"event", "decision", "name", "args"}
        self.worker = None

        self.root = tk.Tk()
        self.root.title("Agent KH")
        self._setup_window(self.root, ISLAND_W, ISLAND_H, top=True)
        sw = self.root.winfo_screenwidth()
        self.island_x = (sw - ISLAND_W) // 2
        self.root.geometry("+%d+%d" % (self.island_x, 6))

        self._build_island()
        self._build_panel()
        self._build_desktop_mochi()

        self.root.after(120, self._poll)
        self.root.after(500, self._greet)

    # ------------------------------------------------------------ windows
    def _setup_window(self, win, w, h, top=True):
        win.overrideredirect(True)
        if top:
            win.attributes("-topmost", True)
        # rounded look via transparent color (Windows); fallback plain
        try:
            win.configure(bg="magenta")
            win.wm_attributes("-transparentcolor", "magenta")
            self._transparent = True
        except Exception:
            win.configure(bg=BG)
            self._transparent = False

    def _panel_pos(self):
        sw = self.root.winfo_screenwidth()
        return "+%d+%d" % ((sw - PANEL_W) // 2, ISLAND_H + 14)

    # ------------------------------------------------------------ island
    def _build_island(self):
        self.canvas = tk.Canvas(self.root, width=ISLAND_W, height=ISLAND_H,
                                highlightthickness=0, bd=0,
                                bg="magenta" if self._transparent else BG)
        self.canvas.pack()
        bg = "magenta" if self._transparent else BG
        rounded(self.canvas, 2, 2, ISLAND_W - 2, ISLAND_H - 2, 30, fill=BG,
                outline="#2a2a32")
        # mini mochi on the left
        self.mini = MochiWidget(self.canvas, size=52)
        self.mini.configure(bg=BG)
        self.canvas.create_window(34, ISLAND_H // 2, window=self.mini)
        # status text
        self.status_var = tk.StringVar(value="Agent KH")
        self.status_lbl = tk.Label(self.canvas, textvariable=self.status_var,
                                   bg=BG, fg=DIM, font=("Segoe UI", 10))
        self.canvas.create_window(128, ISLAND_H // 2, window=self.status_lbl)
        self.canvas.bind("<Button-1>", lambda e: self.toggle_panel())
        self.canvas.bind("<Enter>", lambda e: self._island_hover(True))
        self.canvas.bind("<Leave>", lambda e: self._island_hover(False))
        # drag the mochi out of the island -> desktop companion (Coucou-style)
        self._drag_from = None
        self.mini.bind("<ButtonPress-1>", self._mochi_press)
        self.mini.bind("<B1-Motion>", self._mochi_drag)

    def _mochi_press(self, e):
        self._drag_from = (e.x_root, e.y_root)

    def _mochi_drag(self, e):
        if not self._drag_from:
            return
        dx = e.x_root - self._drag_from[0]
        dy = e.y_root - self._drag_from[1]
        if abs(dx) + abs(dy) > 40:
            self._drag_from = None
            self.tear_out_mochi()
        # poke counting for fun (click mochi area)
        self._poke_times = []

    def _island_hover(self, on):
        if not self.panel_open:
            self.status_var.set("Agent KH ✨" if on else "Agent KH")

    def set_island(self, text=None, mood=None):
        if text is not None:
            self.status_var.set(text)
        if mood is not None:
            self.mini.set_mood(mood)

    # ------------------------------------------------------------ panel
    def _build_panel(self):
        self.panel = tk.Toplevel(self.root)
        self._setup_window(self.panel, PANEL_W, PANEL_H, top=True)
        self.panel.geometry(self._panel_pos())
        self.panel.withdraw()

        self.pcanvas = tk.Canvas(self.panel, width=PANEL_W, height=PANEL_H,
                                 highlightthickness=0, bd=0,
                                 bg="magenta" if self._transparent else PANEL)
        self.pcanvas.pack(fill="both", expand=True)
        rounded(self.pcanvas, 2, 2, PANEL_W - 2, PANEL_H - 2, 26,
                fill=PANEL, outline="#2c2c36")

        # header icons
        hdr = tk.Frame(self.pcanvas, bg=PANEL)
        self.pcanvas.create_window(PANEL_W // 2, 30, window=hdr,
                                   width=PANEL_W - 40)
        self.hdr_buttons = {}
        for key, icon, tip in [("home", "🏠", "Activity"),
                               ("chat", "💬", "Chat"),
                               ("new", "➕", "New chat"),
                               ("settings", "⚙️", "Settings")]:
            b = tk.Button(hdr, text=icon, bg=PANEL, fg=TEXT, bd=0,
                          highlightthickness=0, relief="flat",
                          font=("Segoe UI", 14), cursor="hand2",
                          activebackground=CARD,
                          command=lambda k=key: self._header(k))
            b.pack(side="left", padx=6)
            self.hdr_buttons[key] = b
        # right side: sound + close
        rc = tk.Frame(hdr, bg=PANEL)
        rc.pack(side="right")
        self.mute_btn = tk.Button(rc, text="🔊", bg=PANEL, fg=TEXT, bd=0,
                                  highlightthickness=0, relief="flat",
                                  font=("Segoe UI", 13), cursor="hand2",
                                  activebackground=CARD,
                                  command=self._toggle_mute)
        self.mute_btn.pack(side="left", padx=4)
        tk.Button(rc, text="✕", bg=PANEL, fg=DIM, bd=0,
                  highlightthickness=0, relief="flat",
                  font=("Segoe UI", 12), cursor="hand2",
                  activebackground=CARD,
                  command=self.close_panel).pack(side="left", padx=4)
        self.muted = False

        # approval card (hidden by default)
        self.appr_frame = tk.Frame(self.pcanvas, bg=CARD, padx=14, pady=10)
        self._appr_win = self.pcanvas.create_window(
            PANEL_W // 2, 120, window=self.appr_frame, width=PANEL_W - 60,
            state="hidden")

        # content area
        self.content = tk.Frame(self.pcanvas, bg=PANEL)
        self.pcanvas.create_window(PANEL_W // 2, 330, window=self.content,
                                   width=PANEL_W - 48, height=430)

        self._build_chat_view()
        self._build_activity_view()
        self._build_settings_view()
        self.show_view("chat")

        self.panel.bind("<Escape>", lambda e: self.close_panel())

    def _header(self, key):
        if key == "new":
            self.eng.clear_history()
            self._chat_clear()
            self._notice(self.eng.T("new_chat"))
        elif key in ("home", "chat", "settings"):
            self.show_view(key)

    def toggle_panel(self):
        if self.panel_open:
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self):
        self.panel.deiconify()
        self.panel.lift()
        self.panel_open = True
        self.set_island(mood="idle")

    def close_panel(self):
        self.panel.withdraw()
        self.panel_open = False

    def show_view(self, name):
        self.view = name
        for v, f in self._views.items():
            if v == name:
                f.pack(fill="both", expand=True)
            else:
                f.pack_forget()

    def _toggle_mute(self):
        self.muted = not self.muted
        self.mute_btn.configure(text="🔇" if self.muted else "🔊")

    def _beep(self, kind="info"):
        if self.muted:
            return
        try:
            import winsound
            winsound.Beep(880 if kind == "approval" else 660, 180)
        except Exception:
            pass

    # ------------------------------------------------------------ views
    def _build_chat_view(self):
        f = tk.Frame(self.content, bg=PANEL)
        self._views = {"chat": f}
        # model pill
        top = tk.Frame(f, bg=PANEL)
        top.pack(fill="x", pady=(0, 6))
        self.model_var = tk.StringVar()
        self._refresh_model_pill()
        self.model_btn = tk.Button(top, textvariable=self.model_var,
                                   bg=CARD, fg=TEXT, bd=0, padx=12, pady=4,
                                   font=("Segoe UI", 10), cursor="hand2",
                                   activebackground=CARD2,
                                   command=self._switch_model)
        self.model_btn.pack(side="left")
        # messages
        self.chat_text = tk.Text(f, bg=PANEL, fg=TEXT, bd=0,
                                 font=("Segoe UI", 10), wrap="word",
                                 state="disabled", cursor="arrow")
        self.chat_text.pack(fill="both", expand=True, pady=(0, 6))
        self.chat_text.tag_config("user", justify="right", foreground=TEXT,
                                  background=CARD, lmargin1=120, rmargin=4,
                                  spacing1=6, spacing3=6)
        self.chat_text.tag_config("bot", foreground=TEXT, lmargin1=4,
                                  rmargin=60, spacing1=6, spacing3=6)
        self.chat_text.tag_config("dim", foreground=DIM, justify="center",
                                  spacing1=8, spacing3=8)
        self.chat_text.tag_config("err", foreground=RED, justify="center",
                                  spacing1=8, spacing3=8)
        # input row
        row = tk.Frame(f, bg=PANEL)
        row.pack(fill="x")
        self.entry = tk.Entry(row, bg=CARD, fg=TEXT, bd=0, insertbackground=TEXT,
                              font=("Segoe UI", 11), relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=9,
                        padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.send())
        send = tk.Button(row, text="↑", bg=TEXT, fg=PANEL, bd=0,
                         highlightthickness=0, relief="flat",
                         font=("Segoe UI", 13, "bold"), width=3, cursor="hand2",
                         activebackground=GREEN, command=self.send)
        send.pack(side="left", ipady=4)
        # history
        for role, content in self.eng.get_history():
            if role == "user":
                self._bubble("user", content)
            elif role == "assistant":
                self._bubble("bot", content)

    def _refresh_model_pill(self):
        cfg = self.eng.config
        if cfg.get("provider") == "custom":
            name = cfg.get("custom_model") or "custom"
        else:
            name = cfg.get("gemini_model") or "gemini"
        short = name.replace("gemini-", "")[:18]
        self.model_var.set("● " + short)

    def _switch_model(self):
        # cycle through a few known models
        cfg = self.eng.config
        if cfg.get("provider") == "custom":
            return
        order = ["gemini-3.5-flash", "gemini-3.5-flash-lite",
                 "gemini-3.7-flash", "gemini-2.5-flash"]
        cur = cfg.get("gemini_model", order[0])
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order \
            else order[0]
        cfg["gemini_model"] = nxt
        self.eng.save_config()
        self._refresh_model_pill()
        self._notice("model: " + nxt)

    def _bubble(self, who, text):
        self.chat_text.configure(state="normal")
        self.chat_text.insert("end", text.strip() + "\n", who)
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def _notice(self, text, tag="dim"):
        self.chat_text.configure(state="normal")
        self.chat_text.insert("end", text + "\n", tag)
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def _chat_clear(self):
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        self.chat_text.configure(state="disabled")

    def send(self):
        text = self.entry.get().strip()
        if not text or self.eng.busy:
            return
        self.entry.delete(0, "end")
        self._bubble("user", text)
        if not self.panel_open:
            self.open_panel()
        self.show_view("chat")
        self._stream_target = None
        self.mini.set_mood("thinking")
        self.set_island("thinking…", "thinking")
        self.worker = threading.Thread(target=self.eng.chat,
                                       args=(text, self), daemon=True)
        self.worker.start()

    # ------------------------------------------------------------ activity
    def _build_activity_view(self):
        f = tk.Frame(self.content, bg=PANEL)
        self._views["home"] = f
        tk.Label(f, text="Activity", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        self.act_text = tk.Text(f, bg=PANEL, fg=DIM, bd=0,
                                font=("Consolas", 9), wrap="word",
                                state="disabled", cursor="arrow", height=20)
        self.act_text.pack(fill="both", expand=True)
        self.act_text.tag_config("ok", foreground=GREEN)
        self.act_text.tag_config("bad", foreground=RED)
        self.act_text.tag_config("run", foreground=TEXT)

    def _activity(self, text, tag="run"):
        self.act_text.configure(state="normal")
        self.act_text.insert("end", text + "\n", tag)
        self.act_text.configure(state="disabled")
        self.act_text.see("end")

    # ------------------------------------------------------------ settings
    def _build_settings_view(self):
        f = tk.Frame(self.content, bg=PANEL)
        self._views["settings"] = f
        cfg = self.eng.config
        row = 0

        def lab(t):
            tk.Label(f, text=t, bg=PANEL, fg=DIM,
                     font=("Segoe UI", 10)).grid(row=row, column=0,
                                                 sticky="w", pady=4)

        self.var_provider = tk.StringVar(value=cfg.get("provider", "gemini"))
        self.var_key = tk.StringVar(value=cfg.get("gemini_key", ""))
        self.var_model = tk.StringVar(
            value=cfg.get("gemini_model", "gemini-3.5-flash"))
        self.var_curl = tk.StringVar(value=cfg.get("custom_base_url", ""))
        self.var_ckey = tk.StringVar(value=cfg.get("custom_key", ""))
        self.var_cmodel = tk.StringVar(value=cfg.get("custom_model", ""))
        self.var_auto = tk.BooleanVar(value=bool(cfg.get("auto_approve")))
        self.var_lang = tk.StringVar(value=cfg.get("lang", "en"))

        lab("Provider")
        ttk.Combobox(f, textvariable=self.var_provider, width=26,
                     values=["gemini", "custom"],
                     state="readonly").grid(row=row, column=1, sticky="w")
        row += 1
        lab("Gemini key")
        tk.Entry(f, textvariable=self.var_key, show="•", width=34, bg=CARD,
                 fg=TEXT, bd=0, insertbackground=TEXT).grid(row=row, column=1,
                                                            sticky="w", pady=4,
                                                            ipady=4)
        row += 1
        lab("Gemini model")
        tk.Entry(f, textvariable=self.var_model, width=34, bg=CARD, fg=TEXT,
                 bd=0, insertbackground=TEXT).grid(row=row, column=1,
                                                   sticky="w", pady=4, ipady=4)
        row += 1
        lab("Custom URL / key / model")
        cf = tk.Frame(f, bg=PANEL)
        cf.grid(row=row, column=1, sticky="w")
        for v in (self.var_curl, self.var_ckey, self.var_cmodel):
            tk.Entry(cf, textvariable=v, width=34, bg=CARD, fg=TEXT, bd=0,
                     insertbackground=TEXT).pack(pady=2, ipady=3)
        row += 1
        tk.Checkbutton(f, text="Auto-approve commands (careful!)",
                       variable=self.var_auto, bg=PANEL, fg=TEXT,
                       selectcolor=CARD, activebackground=PANEL).grid(
                           row=row, column=1, sticky="w", pady=4)
        row += 1
        lab("Language")
        ttk.Combobox(f, textvariable=self.var_lang, width=12,
                     values=["en", "fa"], state="readonly").grid(
                         row=row, column=1, sticky="w")
        row += 1
        lab("Personality (soul.md)")
        self.soul_txt = tk.Text(f, bg=CARD, fg=TEXT, bd=0, width=40, height=6,
                                font=("Segoe UI", 9), insertbackground=TEXT)
        self.soul_txt.grid(row=row, column=1, sticky="w", pady=4)
        self.soul_txt.insert("1.0", self.eng.load_soul())
        row += 1
        tk.Button(f, text="Save", bg=ACCENT, fg="white", bd=0, padx=24,
                  pady=6, font=("Segoe UI", 10, "bold"), cursor="hand2",
                  activebackground=GREEN,
                  command=self._save_settings).grid(row=row, column=1,
                                                    sticky="w", pady=10)

    def _save_settings(self):
        cfg = self.eng.config
        cfg["provider"] = self.var_provider.get()
        cfg["gemini_key"] = self.var_key.get().strip()
        cfg["gemini_model"] = self.var_model.get().strip()
        cfg["custom_base_url"] = self.var_curl.get().strip()
        cfg["custom_key"] = self.var_ckey.get().strip()
        cfg["custom_model"] = self.var_cmodel.get().strip()
        cfg["auto_approve"] = bool(self.var_auto.get())
        cfg["lang"] = self.var_lang.get()
        self.eng.save_config()
        self.eng.save_soul(self.soul_txt.get("1.0", "end").strip())
        self.lang = cfg["lang"]
        self._refresh_model_pill()
        self._notice("✓ settings saved")

    # ------------------------------------------------------------ approval
    def show_approval(self, name, args):
        for w in self.appr_frame.winfo_children():
            w.destroy()
        fa = self.lang == "fa"
        try:
            import json as _j
            detail = _j.dumps(args, ensure_ascii=False)[:220]
        except Exception:
            detail = str(args)[:220]
        tk.Label(self.appr_frame,
                 text="⚠️ " + ("Approval needed" if not fa else "اجازه لازمه"),
                 bg=CARD, fg=ORANGE,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(self.appr_frame, text=name, bg=CARD, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(self.appr_frame, text=detail, bg="#141418", fg=DIM,
                 font=("Consolas", 9), wraplength=560,
                 justify="left").pack(fill="x", pady=6)
        btns = tk.Frame(self.appr_frame, bg=CARD)
        btns.pack(fill="x")
        self._appr_result = None

        def decide(r):
            self._appr_result = r
            self.hide_approval()

        tk.Button(btns, text="✕ Deny (N)", bg=CARD2, fg=TEXT, bd=0,
                  highlightthickness=0, relief="flat", padx=14,
                  pady=7, cursor="hand2", activebackground="#3a3a44",
                  command=lambda: decide("deny")).pack(side="left", padx=4)
        tk.Button(btns, text="Always allow", bg=CARD2, fg=TEXT, bd=0,
                  highlightthickness=0, relief="flat", padx=14,
                  pady=7, cursor="hand2", activebackground="#3a3a44",
                  command=lambda: decide("always")).pack(side="left", padx=4)
        tk.Button(btns, text="✓ Allow (Y)", bg=GREEN, fg="#06281a", bd=0,
                  highlightthickness=0, relief="flat",
                  padx=18, pady=7, font=("Segoe UI", 10, "bold"),
                  cursor="hand2", activebackground="#5ce896",
                  command=lambda: decide("allow")).pack(side="left", padx=4)
        self.pcanvas.itemconfigure(self._appr_win, state="normal")
        self.root.bind("<y>", lambda e: decide("allow"))
        self.root.bind("<n>", lambda e: decide("deny"))
        if not self.panel_open:
            self.open_panel()
        self._beep("approval")
        self.mini.set_mood("approval")
        self.set_island("approval needed 👀", "approval")

    def hide_approval(self):
        self.pcanvas.itemconfigure(self._appr_win, state="hidden")
        self.root.unbind("<y>")
        self.root.unbind("<n>")

    # ------------------------------------------------------------ desktop mochi
    def _build_desktop_mochi(self):
        self.desk = tk.Toplevel(self.root)
        self.desk.overrideredirect(True)
        self.desk.attributes("-topmost", True)
        try:
            self.desk.configure(bg="magenta")
            self.desk.wm_attributes("-transparentcolor", "magenta")
            mbg = "magenta"
        except Exception:
            self.desk.configure(bg=BG)
            mbg = BG
        self.desk_mochi = MochiWidget(self.desk, size=110)
        self.desk_mochi.configure(bg=mbg)
        self.desk_mochi.pack()
        self.desk.withdraw()
        self.desk_mochi.bind("<Button-1>", self._desk_drag_start)
        self.desk_mochi.bind("<B1-Motion>", self._desk_drag)
        self.desk_mochi.bind("<Double-Button-1>", lambda e: self._mochi_home())
        self.desk_mochi.bind("<Button-3>", lambda e: self._mochi_home())

    def _desk_drag_start(self, e):
        self._ddx, self._ddy = e.x_root, e.y_root

    def _desk_drag(self, e):
        x = self.desk.winfo_x() + (e.x_root - self._ddx)
        y = self.desk.winfo_y() + (e.y_root - self._ddy)
        self.desk.geometry("+%d+%d" % (x, y))
        self._ddx, self._ddy = e.x_root, e.y_root

    def _mochi_home(self):
        self.desk.withdraw()
        self.root.deiconify()

    def tear_out_mochi(self):
        # drag the island's mochi out -> desktop companion
        self.root.withdraw()
        self.close_panel()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.desk.geometry("+%d+%d" % (sw - 160, sh // 2))
        self.desk.deiconify()

    # ------------------------------------------------------------ callbacks
    # (called from the worker thread — marshal to UI thread via queue)
    def on_token(self, text):
        self.q.put(("token", text))

    def on_tool_start(self, name, args):
        self.q.put(("tool_start", name, args))

    def on_tool_end(self, name, ok, denied):
        self.q.put(("tool_end", name, ok, denied))

    def on_approval(self, name, args):
        ev = threading.Event()
        self.q.put(("approval", name, args, ev))
        ev.wait(300)
        return getattr(self, "_appr_decision", "deny")

    def on_error(self, text):
        self.q.put(("error", text))

    def on_end(self):
        self.q.put(("end",))

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                self._handle(item)
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _handle(self, item):
        kind = item[0]
        if kind == "token":
            if self._stream_target is None:
                self.chat_text.configure(state="normal")
                self._stream_target = self.chat_text.index("end")
                self.chat_text.configure(state="disabled")
            self.chat_text.configure(state="normal")
            self.chat_text.insert("end", item[1], "bot")
            self.chat_text.configure(state="disabled")
            self.chat_text.see("end")
        elif kind == "tool_start":
            name = item[1]
            self._activity("🔧 %s …" % name)
            self.mini.set_mood("working")
            self.set_island("working…", "working")
        elif kind == "tool_end":
            name, ok, denied = item[1], item[2], item[3]
            self._activity(("✓ " if ok else "✗ ") + name,
                           "ok" if ok else "bad")
        elif kind == "approval":
            name, args, ev = item[1], item[2], item[3]
            self.show_approval(name, args)
            self._wait_approval(ev)
        elif kind == "error":
            self._notice("⚠️ " + item[1], "err")
            self.mini.set_mood("error")
            self.set_island("error", "error")
        elif kind == "end":
            self.mini.set_mood("happy")
            self.set_island("Agent KH", "happy")
            self.root.after(1500,
                            lambda: self.mini.set_mood("idle")
                            if not self.eng.busy else None)

    def _wait_approval(self, ev):
        # wait (in UI thread via after) until user decides, then release worker
        def check():
            if self._appr_result is not None:
                self._appr_decision = self._appr_result
                self._appr_result = None
                self.mini.set_mood("working")
                ev.set()
            else:
                self.root.after(100, check)
        check()

    # ------------------------------------------------------------ misc
    def _greet(self):
        cfg = self.eng.config
        key_ok = (cfg.get("custom_key") and cfg.get("custom_model")) \
            if cfg.get("provider") == "custom" else cfg.get("gemini_key")
        if not key_ok:
            self.open_panel()
            self.show_view("settings")
            self._notice("👋 Hi! I'm Agent KH ✨ — add your API key in "
                         "Settings to start.")


def main():
    eng = Engine()
    eng.connect_mcp()
    app = IslandApp(eng)
    app.root.mainloop()


if __name__ == "__main__":
    main()
