# -*- coding: utf-8 -*-
"""
desktop.py — mouse & keyboard control for Agent KH.
Prefers pyautogui (pip install pyautogui) when available (cross-platform);
falls back to Win32 ctypes on Windows (zero dependencies);
otherwise reports unsupported.

Every action here is gated by Agent KH's approval UI — nothing runs
without the user's explicit Allow.
"""
import platform

_backend_name = None
_pg = None
_win32 = None


class Win32Backend:
    """Windows mouse/keyboard via ctypes (no dependencies)."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.u32 = ctypes.windll.user32
        # mouse_event flags
        self.M_LEFTDOWN, self.M_LEFTUP = 0x0002, 0x0004
        self.M_RIGHTDOWN, self.M_RIGHTUP = 0x0008, 0x0010
        self.M_MIDDLEDOWN, self.M_MIDDLEUP = 0x0020, 0x0040
        self.M_WHEEL = 0x0800
        self.VK = {
            "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
            "space": 0x20, "backspace": 0x08, "delete": 0x2E,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
            "insert": 0x2D, "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
            "win": 0x5B, "capslock": 0x14, "numlock": 0x90,
            "printscreen": 0x2C, "pause": 0x13,
        }
        for i in range(1, 13):
            self.VK["f%d" % i] = 0x6F + i

    # -- mouse --
    def size(self):
        return (self.u32.GetSystemMetrics(0), self.u32.GetSystemMetrics(1))

    def pos(self):
        pt = self.wintypes.POINT()
        self.u32.GetCursorPos(self.ctypes.byref(pt))
        return (pt.x, pt.y)

    def move(self, x, y):
        self.u32.SetCursorPos(int(x), int(y))

    def _click(self, down, up):
        self.u32.mouse_event(down, 0, 0, 0, 0)
        self.u32.mouse_event(up, 0, 0, 0, 0)

    def click(self, button="left"):
        m = {"left": (self.M_LEFTDOWN, self.M_LEFTUP),
             "right": (self.M_RIGHTDOWN, self.M_RIGHTUP),
             "middle": (self.M_MIDDLEDOWN, self.M_MIDDLEUP)}[button]
        self._click(*m)

    def double_click(self, button="left"):
        self.click(button)
        self.click(button)

    def scroll(self, amount):
        self.u32.mouse_event(self.M_WHEEL, 0, 0, int(amount) * 120, 0)

    # -- keyboard --
    def _vk_press(self, vk):
        self.u32.keybd_event(vk, 0, 0, 0)
        self.u32.keybd_event(vk, 0, 0x0002, 0)  # KEYEVENTF_KEYUP

    def press(self, key):
        vk = self.VK.get(key.strip().lower())
        if vk is None:
            raise ValueError("unknown key: %s" % key)
        self._vk_press(vk)

    def hotkey(self, keys):
        vks = []
        for k in keys:
            vk = self.VK.get(k.strip().lower())
            if vk is None:
                raise ValueError("unknown key: %s" % k)
            vks.append(vk)
        for vk in vks:
            self.u32.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks):
            self.u32.keybd_event(vk, 0, 0x0002, 0)

    def type_text(self, text):
        # SendInput with KEYEVENTF_UNICODE per character — layout independent.
        # NB: INPUT must be the real 40-byte Win64 layout (union!), else
        # SendInput silently fails.
        ctypes = self.ctypes

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32),
                        ("mouseData", ctypes.c_uint32),
                        ("dwFlags", ctypes.c_uint32),
                        ("time", ctypes.c_uint32),
                        ("dwExtraInfo", ctypes.c_void_p)]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_uint16),
                        ("wScan", ctypes.c_uint16),
                        ("dwFlags", ctypes.c_uint32),
                        ("time", ctypes.c_uint32),
                        ("dwExtraInfo", ctypes.c_void_p)]

        class _UNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_uint32), ("u", _UNION)]

        assert ctypes.sizeof(INPUT) == 40, \
            "INPUT layout wrong: %d" % ctypes.sizeof(INPUT)
        KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x0004, 0x0002
        for ch in text:
            for down in (True, False):
                ki = KEYBDINPUT(
                    wVk=0, wScan=ord(ch),
                    dwFlags=KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if not down else 0),
                    time=0, dwExtraInfo=None)
                inp = INPUT(type=1, u=_UNION(ki=ki))
                if self.u32.SendInput(1, ctypes.byref(inp),
                                      ctypes.sizeof(INPUT)) != 1:
                    raise RuntimeError("SendInput failed")


def _init():
    global _backend_name, _pg, _win32
    if _backend_name is not None:
        return _backend_name
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        _pg = pyautogui
        _backend_name = "pyautogui"
        return _backend_name
    except Exception:
        pass
    if platform.system() == "Windows":
        try:
            _win32 = Win32Backend()
            _backend_name = "win32"
            return _backend_name
        except Exception:
            pass
    _backend_name = "none"
    return _backend_name


def available():
    return _init() != "none"


def backend_name():
    _init()
    return _backend_name


def _need():
    b = _init()
    if b == "none":
        raise RuntimeError(
            "Mouse/keyboard control is not available on this system. "
            "Install pyautogui:  pip install pyautogui")
    return b


def size():
    b = _need()
    return _pg.size() if b == "pyautogui" else _win32.size()


def pos():
    b = _need()
    p = _pg.position() if b == "pyautogui" else _win32.pos()
    return (int(p[0]), int(p[1]))


def move(x, y):
    b = _need()
    if b == "pyautogui":
        _pg.moveTo(int(x), int(y), duration=0.15)
    else:
        _win32.move(x, y)


def click(button="left", x=None, y=None):
    b = _need()
    button = (button or "left").lower()
    if button not in ("left", "right", "middle"):
        raise ValueError("button must be left/right/middle")
    if x is not None and y is not None:
        move(x, y)
    if b == "pyautogui":
        _pg.click(button=button)
    else:
        _win32.click(button)


def double_click(x=None, y=None):
    b = _need()
    if x is not None and y is not None:
        move(x, y)
    if b == "pyautogui":
        _pg.doubleClick()
    else:
        _win32.double_click()


def scroll(amount):
    b = _need()
    if b == "pyautogui":
        _pg.scroll(int(amount) * 3)
    else:
        _win32.scroll(amount)


def drag(x1, y1, x2, y2):
    b = _need()
    if b == "pyautogui":
        _pg.moveTo(int(x1), int(y1), duration=0.15)
        _pg.dragTo(int(x2), int(y2), duration=0.4, button="left")
    else:
        _win32.move(x1, y1)
        _win32.u32.mouse_event(_win32.M_LEFTDOWN, 0, 0, 0, 0)
        _win32.move(x2, y2)
        _win32.u32.mouse_event(_win32.M_LEFTUP, 0, 0, 0, 0)


def type_text(text):
    b = _need()
    if b == "pyautogui":
        _pg.typewrite(text, interval=0.02)
    else:
        _win32.type_text(text)


def press(key):
    b = _need()
    if b == "pyautogui":
        _pg.press(key.strip().lower())
    else:
        _win32.press(key)


def hotkey(keys):
    b = _need()
    keys = [k.strip().lower() for k in keys]
    if b == "pyautogui":
        _pg.hotkey(*keys)
    else:
        _win32.hotkey(keys)


def screenshot(max_width=1600):
    """Capture the screen; returns base64 PNG. Needs Pillow + a display."""
    try:
        from PIL import ImageGrab
    except ImportError:
        raise RuntimeError("Screenshot needs Pillow: pip install pillow")
    import io
    import base64
    try:
        img = ImageGrab.grab()
    except Exception as e:
        raise RuntimeError("Cannot capture screen: %s" % e)
    if img.width > max_width:
        img = img.resize((max_width,
                          int(img.height * max_width / img.width)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()
