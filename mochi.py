# -*- coding: utf-8 -*-
"""
mochi.py — Mochi, the Agent KH island character (tkinter Canvas).
A soft white squircle with big eyes that follow your cursor, blinks,
breathes, and shows emotes: idle / thinking / working / approval /
happy / sleeping / dizzy / error.
"""
import math
import random
import tkinter as tk

BODY = "#fdfbf6"
BODY_SHADE = "#efe9dd"
BLUSH = "#f3aebe"
EYE = "#20222a"
BADGE = "#ff9f2e"


def squircle_points(cx, cy, w, h, n=4, steps=48):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        x = cx + (w / 2) * math.copysign(abs(c) ** (2 / n), c)
        y = cy + (h / 2) * math.copysign(abs(s) ** (2 / n), s)
        pts += [x, y]
    return pts


class MochiWidget(tk.Canvas):
    def __init__(self, master, size=110, **kw):
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(master, width=size, height=int(size * 0.82), **kw)
        self.size = size
        self.mood = "idle"
        self._blink = 0          # frames remaining of blink
        self._blink_in = 200     # frames until next blink
        self._t = 0
        self._poke_shake = 0
        self._jump = 0
        self._dizzy_until = 0
        self._eye_dx = 0
        self._eye_dy = 0
        self.configure(bg=self.master.cget("bg") if master else "#000000")
        self.after(50, self._tick)

    # ------------------------------------------------------------- public
    def set_mood(self, mood):
        self.mood = mood
        if mood == "happy":
            self._jump = 14
        if mood == "dizzy":
            self._dizzy_until = self._t + 60

    def poke(self):
        self._poke_shake = 12

    # ------------------------------------------------------------- drawing
    def _tick(self):
        self._t += 1
        self._blink_in -= 1
        if self._blink_in <= 0:
            self._blink = 5
            self._blink_in = random.randint(140, 260)
        if self._blink > 0:
            self._blink -= 1
        # ease eye offset toward cursor
        try:
            px = self.winfo_pointerx() - self.winfo_rootx() - self.size / 2
            py = self.winfo_pointery() - self.winfo_rooty() - self.size * 0.41
            tx = max(-7, min(7, px / 22))
            ty = max(-5, min(5, py / 22))
        except Exception:
            tx, ty = 0, 0
        self._eye_dx += (tx - self._eye_dx) * 0.25
        self._eye_dy += (ty - self._eye_dy) * 0.25
        self._draw()
        self.after(50, self._tick)

    def _draw(self):
        self.delete("all")
        W, H = self.size, int(self.size * 0.82)
        cx, cy = W / 2, H / 2 + 2

        # breathing + jump + shake offsets
        breathe = math.sin(self._t * 0.09) * 1.6
        oy = -self._jump * 0.6 if self._jump else 0
        if self._jump:
            self._jump -= 1
        ox = 0
        if self._poke_shake:
            ox = math.sin(self._poke_shake * 1.7) * 4
            self._poke_shake -= 1

        bw, bh = W * 0.78, H * 0.66 + breathe
        # soft shadow
        self.create_oval(cx - bw * 0.42, cy + bh * 0.5 - 4 + oy,
                         cx + bw * 0.42, cy + bh * 0.5 + 4 + oy,
                         fill="#000000", stipple="gray25", outline="")
        # body
        self.create_polygon(squircle_points(cx + ox, cy + oy, bw, bh),
                            fill=BODY, outline=BODY_SHADE, smooth=True)
        # blush
        for sx in (-1, 1):
            self.create_oval(cx + sx * bw * 0.30 - 9 + ox,
                             cy + bh * 0.16 - 6 + oy,
                             cx + sx * bw * 0.30 + 9 + ox,
                             cy + bh * 0.16 + 6 + oy,
                             fill=BLUSH, outline="")

        ex = bw * 0.17
        ey = cy - bh * 0.06 + oy
        mood = self.mood

        if mood == "sleeping":
            for sx in (-1, 1):
                x = cx + sx * ex + ox
                self.create_line(x - 7, ey, x + 7, ey, fill=EYE, width=3,
                                 capstyle="round")
            # "z"
            self.create_text(cx + bw * 0.42, cy - bh * 0.42, text="z",
                             fill="#8a8fa3", font=("Arial", 11, "bold"))
            return

        if mood == "dizzy" or self._t < self._dizzy_until:
            for sx in (-1, 1):
                x = cx + sx * ex + ox
                self.create_line(x - 6, ey - 6, x + 6, ey + 6, fill=EYE,
                                 width=3, capstyle="round")
                self.create_line(x - 6, ey + 6, x + 6, ey - 6, fill=EYE,
                                 width=3, capstyle="round")
            return

        # eyes
        if self._blink > 0:
            for sx in (-1, 1):
                x = cx + sx * ex + ox
                self.create_line(x - 7, ey, x + 7, ey, fill=EYE, width=3.5,
                                 capstyle="round")
        elif mood == "happy":
            for sx in (-1, 1):
                x = cx + sx * ex + ox
                self.create_arc(x - 8, ey - 4, x + 8, ey + 10,
                                start=180, extent=180, style="arc",
                                outline=EYE, width=3.5)
        elif mood == "error":
            for sx in (-1, 1):
                x = cx + sx * ex + ox
                self.create_line(x - 7, ey + 4, x + 7, ey - 4, fill=EYE,
                                 width=3, capstyle="round")
        else:
            edx, edy = self._eye_dx, self._eye_dy
            if mood == "thinking":
                edx, edy = 4, -4
            for sx in (-1, 1):
                x = cx + sx * ex + ox + edx
                y = ey + edy
                self.create_oval(x - 6.5, y - 9, x + 6.5, y + 9, fill=EYE,
                                 outline="")
                self.create_oval(x + 1, y - 6, x + 4.5, y - 2.5,
                                 fill="white", outline="")

        # approval badge
        if mood == "approval":
            bx, by = cx + bw * 0.38 + ox, cy - bh * 0.42 + oy
            self.create_oval(bx - 13, by - 13, bx + 13, by + 13,
                             fill=BADGE, outline="white", width=2)
            self.create_text(bx, by, text="!", fill="white",
                             font=("Arial", 14, "bold"))
