# -*- coding: utf-8 -*-
"""
sfx.py — tiny synthesized sound effects for Agent KH .
Windows: winsound beep melodies. Elsewhere: silent no-op.
"""
import threading


def _play(notes):
    """notes: list of (freq_hz, ms). Runs in a thread."""
    def run():
        try:
            import winsound
            for freq, ms in notes:
                winsound.Beep(freq, ms)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def greeting():
    _play([(523, 120), (659, 120), (784, 200)])


def approval():
    _play([(880, 150), (880, 150)])


def done():
    _play([(659, 120), (784, 120), (1047, 220)])


def poke():
    _play([(300, 80),])


def pop():
    _play([(600, 60), (900, 80)])


def error():
    _play([(220, 200), (180, 250)])
