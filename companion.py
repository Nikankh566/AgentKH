# -*- coding: utf-8 -*-
"""
companion.py — Coucou-style always-on-top overlay mascot for Agent KH.
Lives at the top of the screen, shows Agent KH's mood, pops Allow/Deny
cards when the agent needs approval, and opens the chat on click.

Run:  python companion.py        (or auto-launched by agentkh.py)
"""
import json
import threading
import urllib.request
import webbrowser

API = "http://127.0.0.1:8765"

try:
    import tkinter as tk
except ImportError:
    raise SystemExit("tkinter is required for the companion overlay.")

CHAT_URL = API + "/"


def api_get(path, timeout=4):
    try:
        with urllib.request.urlopen(API + path, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def api_post(path, obj, timeout=8):
    try:
        req = urllib.request.Request(
            API + path, data=json.dumps(obj).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


class Companion:
    W, H = 150, 132

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", "magenta")
            self.bg = "magenta"
        except Exception:
            self.bg = "#14172e"
        sw = self.root.winfo_screenwidth()
        self.root.geometry("+%d+0" % (sw // 2 - self.W // 2, ))
        self.root.configure(bg=self.bg)

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                bg=self.bg, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.mood = "idle"
        self.lang = "en"
        self._blink_open = True
        self._bounce_phase = 0
        self._shown_approval = None
        self._approval_win = None
        self._drag = None

        self._draw()
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._dragto)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", self._menu)

        self.root.after(180, self._animate)
        self.root.after(1200, self._poll)
        self.root.after(600, self._follow_mouse)

    # ---------------- drawing ----------------
    def _draw(self):
        c = self.canvas
        c.delete("all")
        cx, cy, rx, ry = 75, 62, 44, 40
        # shadow
        c.create_oval(cx - 26, 112, cx + 26, 120, fill="#000000", stipple="gray50",
                      outline="", tags="shadow")
        # body
        body = {"idle": "#7c6cff", "busy": "#4ad6ff",
                "pending": "#ffb84d", "offline": "#5a63ad"}[self.mood]
        c.create_oval(cx - rx, cy - ry, cx + rx, cy + ry,
                      fill=body, outline="", tags="body")
        # blush
        c.create_oval(38, 72, 50, 82, fill="#ff9db0", outline="", tags="blush")
        c.create_oval(100, 72, 112, 82, fill="#ff9db0", outline="", tags="blush")
        # eyes
        for ex in (58, 92):
            c.create_oval(ex - 11, 47, ex + 11, 69, fill="white",
                          outline="", tags="eye")
        self.pupils = []
        for ex in (58, 92):
            p = c.create_oval(ex - 5, 53, ex + 5, 63, fill="#14172e",
                              outline="", tags="pupil")
            self.pupils.append((p, ex, 58))
            c.create_oval(ex + 1, 54, ex + 4, 57, fill="white",
                          outline="", tags="pupil")
        # mouth
        if self.mood == "pending":
            c.create_text(cx, 92, text="؟!", font=("Tahoma", 14, "bold"),
                          fill="#3d2b00", tags="mouth")
        else:
            c.create_arc(60, 78, 90, 96, start=200, extent=140,
                         outline="#14172e", width=3, style="arc", tags="mouth")
        # status dot
        dot = {"idle": "#3ddc84", "busy": "#4ad6ff",
               "pending": "#ffb84d", "offline": "#ff6b6b"}[self.mood]
        c.create_oval(8, 8, 18, 18, fill=dot, outline="", tags="dot")

    # ---------------- animation ----------------
    def _animate(self):
        c = self.canvas
        import random
        # blink
        if random.random() < 0.06:
            self._blink_open = not self._blink_open
            h = 22 if self._blink_open else 3
            for p, ex, ey in self.pupils:
                c.coords(p, ex - 5, ey - h // 2, ex + 5, ey + h // 2)
        # bounce when busy
        if self.mood == "busy":
            self._bounce_phase += 1
            dy = -8 if (self._bounce_phase // 6) % 2 else 0
            c.move("body", 0, dy - getattr(self, "_last_dy", 0))
            c.move("eye", 0, dy - getattr(self, "_last_dy", 0))
            c.move("pupil", 0, dy - getattr(self, "_last_dy", 0))
            c.move("blush", 0, dy - getattr(self, "_last_dy", 0))
            c.move("mouth", 0, dy - getattr(self, "_last_dy", 0))
            self._last_dy = dy
        elif getattr(self, "_last_dy", 0):
            for tag in ("body", "eye", "pupil", "blush", "mouth"):
                c.move(tag, 0, -self._last_dy)
            self._last_dy = 0
        self.root.after(180, self._animate)

    def _follow_mouse(self):
        try:
            mx, my = self.root.winfo_pointerx(), self.root.winfo_pointery()
            wx = self.root.winfo_rootx() + 75
            wy = self.root.winfo_rooty() + 58
            dx = max(-4, min(4, (mx - wx) // 18))
            dy = max(-3, min(3, (my - wy) // 18))
            for p, ex, ey in self.pupils:
                self.canvas.coords(p, ex - 5 + dx, ey - 5 + dy,
                                   ex + 5 + dx, ey + 5 + dy)
        except Exception:
            pass
        self.root.after(120, self._follow_mouse)

    # ---------------- interaction ----------------
    def _press(self, e):
        self._drag = (e.x_root, e.y_root,
                      self.root.winfo_x(), self.root.winfo_y(), False)

    def _dragto(self, e):
        if not self._drag:
            return
        x0, y0, wx, wy, moved = self._drag
        if abs(e.x_root - x0) + abs(e.y_root - y0) > 6:
            moved = True
        self._drag = (x0, y0, wx, wy, moved)
        if moved:
            self.root.geometry("+%d+%d" % (wx + e.x_root - x0,
                                           max(0, wy + e.y_root - y0)))

    def _release(self, e):
        if self._drag and not self._drag[4]:
            webbrowser.open(CHAT_URL)
        self._drag = None

    def _menu(self, e):
        fa = self.lang == "fa"
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="💬 " + ("باز کردن چت" if fa else "Open chat"),
                      command=lambda: webbrowser.open(CHAT_URL))
        m.add_separator()
        m.add_command(label="❌ " + ("خروج" if fa else "Quit"),
                      command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    # ---------------- backend polling ----------------
    def _poll(self):
        def work():
            st = api_get("/api/status") or {}
            self.root.after(0, self._apply_status, st)
            if st.get("pending"):
                p = api_get("/api/pending") or {}
                self.root.after(0, self._show_approval, p.get("pending"))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(1200, self._poll)

    def _apply_status(self, st):
        if not st:
            mood = "offline"
        elif st.get("pending"):
            mood = "pending"
        elif st.get("busy"):
            mood = "busy"
        else:
            mood = "idle"
        self.lang = st.get("lang", "en") if st else "en"
        if mood != self.mood:
            self.mood = mood
            self._draw()

    def _close_approval_win(self):
        try:
            if self._approval_win is not None:
                self._approval_win.destroy()
        except Exception:
            pass
        self._approval_win = None

    def _show_approval(self, pending):
        if not pending:
            self._shown_approval = None
            self._close_approval_win()
            return
        cid = pending.get("call_id")
        if cid == self._shown_approval:
            return
        self._close_approval_win()
        self._shown_approval = cid
        name = pending.get("name", "?")
        args = pending.get("args", {})
        try:
            detail = json.dumps(args, ensure_ascii=False)[:220]
        except Exception:
            detail = str(args)[:220]
        fa = self.lang == "fa"

        win = tk.Toplevel(self.root)
        self._approval_win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#2a2340", bd=1, relief="solid")
        x = self.root.winfo_x() - 90
        y = self.root.winfo_y() + self.H + 6
        win.geometry("+%d+%d" % (max(0, x), y))

        tk.Label(win, text="⚠️ " + ("اجازه لازمه" if fa else "Approval needed"),
                 bg="#2a2340", fg="#ffb84d",
                 font=("Tahoma", 11, "bold")).pack(padx=12, pady=(8, 2))
        tk.Label(win, text=name, bg="#2a2340", fg="#eef1ff",
                 font=("Tahoma", 11, "bold")).pack(padx=12)
        tk.Label(win, text=detail, bg="#14172e", fg="#9aa3c7",
                 font=("Tahoma", 9), wraplength=260, justify="left"
                 ).pack(padx=12, pady=6, fill="x")

        btns = tk.Frame(win, bg="#2a2340")
        btns.pack(padx=12, pady=(0, 10), fill="x")

        def decide(ok):
            api_post("/api/decision",
                     {"call_id": cid, "approved": ok})
            self._shown_approval = None
            self._close_approval_win()

        tk.Button(btns, text="✅ " + ("اجازه" if fa else "Allow"), bg="#3ddc84",
                  fg="#06281a", font=("Tahoma", 10, "bold"),
                  command=lambda: decide(True)).pack(side="left",
                                                     expand=True, fill="x",
                                                     padx=(0, 4))
        tk.Button(btns, text="❌ " + ("نه" if fa else "Deny"), bg="#ff6b6b",
                  fg="#3d0a0a", font=("Tahoma", 10, "bold"),
                  command=lambda: decide(False)).pack(side="left",
                                                      expand=True, fill="x",
                                                      padx=(4, 0))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Companion().run()
