"""
Agent KH — Qt edition (no WebView2 needed).

Same Python backend (engine.py) and same web UI (web/ui.html) as the
pywebview build, but the window is a PyQt6 QWebEngineView with its own
bundled Chromium. Nothing to install: no WebView2 runtime required.

The JS side talks to Python through QWebChannel. A tiny compatibility shim
at the top of web/ui.html maps `window.pywebview.api.*` onto the channel,
so the UI code is unchanged.
"""

import json
import os
import queue
import sys
import threading

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentkh import Bridge, ChatCallback  # noqa: E402
import updater  # noqa: E402

ISLAND_W, ISLAND_H = 240, 90
PANEL_W, PANEL_H = 700, 650
UI_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "ui.html")


class QtBridge(QObject):
    """Exposes the pywebview Bridge to JS through QWebChannel."""

    def __init__(self, bridge, window):
        super().__init__()
        self.b = bridge
        self.win = window
        self.b._is_qt = True  # updater picks the Qt installer
        # Bridge.window is used by set_pinned/resize/do_update — give it a shim
        self.b.window = _WindowShim(window)

    # -- helpers ---------------------------------------------------------
    def _ok(self, value=True):
        return value

    # -- channel API (mirrors Bridge) ------------------------------------
    @pyqtSlot(result="QVariant")
    def poll(self):
        return self.b.poll()

    @pyqtSlot(str, result="QVariant")
    def send_message(self, text):
        self.b.send_message(text)
        return True

    @pyqtSlot(str, result="QVariant")
    def decide(self, decision):
        self.b.decide(decision)
        return True

    @pyqtSlot(result="QVariant")
    def get_config(self):
        return self.b.get_config()

    @pyqtSlot("QVariantMap", result="QVariant")
    def save_config(self, cfg):
        self.b.save_config(dict(cfg))
        return True

    @pyqtSlot(result="QVariant")
    def get_soul(self):
        return self.b.get_soul()

    @pyqtSlot(result="QVariant")
    def get_version(self):
        return self.b.get_version()

    @pyqtSlot(result="QVariant")
    def switch_model(self):
        self.b.switch_model()
        return True

    @pyqtSlot(result="QVariant")
    def clear_history(self):
        self.b.clear_history()
        return True

    @pyqtSlot(bool, result="QVariant")
    def set_muted(self, m):
        self.b.set_muted(m)
        return True

    @pyqtSlot(str, result="QVariant")
    def save_theme(self, color):
        self.b.save_theme(color)
        return True

    @pyqtSlot(str, result="QVariant")
    def save_mochi_color(self, color):
        self.b.save_mochi_color(color)
        return True

    @pyqtSlot(bool, result="QVariant")
    def set_pinned(self, p):
        self.b.set_pinned(p)
        return True

    @pyqtSlot(str, result="QVariant")
    def snooze_reminder(self, text):
        self.b.snooze_reminder(text)
        return True

    @pyqtSlot(str, result="QVariant")
    def sound(self, name):
        self.b.sound(name)
        return True

    @pyqtSlot(float, float, result="QVariant")
    def resize(self, w, h):
        self.b.resize(int(w), int(h))
        return True

    @pyqtSlot(result="QVariant")
    def check_updates(self):
        self.b.check_updates()
        return True

    @pyqtSlot(result="QVariant")
    def do_update(self):
        self.b.do_update()
        return True

    @pyqtSlot(result="QVariant")
    def boot_done(self):
        self.b.boot_done()
        return True


class _WindowShim:
    """Duck-typed stand-in for pywebview's window used by Bridge."""

    def __init__(self, qwin):
        self._qwin = qwin

    @property
    def screen(self):
        class S:
            width = 1280
        try:
            s = self._qwin.screen()
            if s:
                S.width = s.size().width()
        except Exception:
            pass
        return S()

    def resize(self, w, h):
        QTimer.singleShot(0, lambda: self._qwin.resize(int(w), int(h)))

    def move(self, x, y):
        QTimer.singleShot(0, lambda: self._qwin.move(int(x), int(y)))

    def destroy(self):
        QTimer.singleShot(0, self._qwin.close)

    def __setattr__(self, name, value):
        if name == "on_top":
            try:
                self._qwin.set_pinned(bool(value))
            except Exception:
                pass
        else:
            object.__setattr__(self, name, value)


class IslandWindow(QWidget):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self._drag_pos = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar button
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        self.view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        # allow the page to reach the local file + qrc resources
        settings = self.view.settings()

        self.channel = QWebChannel(self.view.page())
        self.qt_bridge = QtBridge(bridge, self)
        self.channel.registerObject("bridge", self.qt_bridge)
        self.view.page().setWebChannel(self.channel)

        layout.addWidget(self.view)

        with open(UI_HTML, encoding="utf-8") as f:
            html = f.read()
        self.view.setHtml(html, QUrl.fromLocalFile(UI_HTML))

        self.resize(ISLAND_W, ISLAND_H)
        # top-center
        try:
            sw = self.screen().size().width()
        except Exception:
            sw = 1280
        self.move((sw - ISLAND_W) // 2, 0)

    # -- pin ---------------------------------------------------------------
    def set_pinned(self, pinned):
        flags = self.windowFlags()
        if pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()


def main():
    # Chromium bundled with QtWebEngine — no system WebView2 needed.
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                          "--disable-gpu --disable-software-rasterizer")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    bridge = Bridge()
    win = IslandWindow(bridge)
    win.show()

    # keep the JS poll loop fed even though QtBridge.poll is pull-based —
    # nothing needed here; ui.html polls on its own timer.
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
