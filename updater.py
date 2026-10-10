# -*- coding: utf-8 -*-
"""
updater.py — Agent KH self-updater.
Checks GitHub releases for a newer version, downloads the installer,
and relaunches it — all from inside the island.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request

REPO = "Nikankh566/AgentKH"
VERSION = "5.3.0"


def _ver_tuple(v):
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_newer(tag, current=VERSION):
    try:
        return _ver_tuple(tag) > _ver_tuple(current)
    except Exception:
        return False


def check_latest(timeout=15):
    """Return (tag_name, assets{name: url}) or (None, {}) on failure."""
    url = "https://api.github.com/repos/%s/releases/latest" % REPO
    req = urllib.request.Request(url, headers={"User-Agent": "AgentKH"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        assets = {a["name"]: a["browser_download_url"]
                   for a in data.get("assets", [])}
        return data.get("tag_name"), assets
    except Exception:
        return None, {}


def download(url, dest, progress=None):
    """Download with optional progress(bytes_done, total)."""
    req = urllib.request.Request(url, headers={"User-Agent": "AgentKH"})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    return dest


def install_setup_exe(path):
    """Quit this app, then run the NSIS installer silently."""
    import time
    bat = os.path.join(tempfile.gettempdir(), "akh_update.bat")
    with open(bat, "w") as f:
        f.write('@echo off\n'
                'timeout /t 3 /nobreak >nul\n'
                'start "" "%s" /S\n'
                'del "%%~f0"\n' % path)
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", bat],
                         creationflags=getattr(subprocess,
                                               "DETACHED_PROCESS", 0))
    else:
        subprocess.Popen(["sh", bat])
    time.sleep(0.5)
    sys.exit(0)


def check_in_background(callback):
    """callback(tag, assets) — called in a worker thread."""
    def run():
        tag, assets = check_latest()
        if tag and is_newer(tag):
            callback(tag, assets)
    threading.Thread(target=run, daemon=True).start()
