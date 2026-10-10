# -*- mode: python ; coding: utf-8 -*-
# Agent KH v5 — Qt edition PyInstaller build spec (Windows)
# No WebView2 needed: PyQt6 bundles its own Chromium (QtWebEngine).
# Build on Windows:  pip install pyinstaller pyqt6 pyqt6-webengine pillow
#                    pyinstaller AgentKH-Qt.spec
# Output: dist/AgentKH-Qt/AgentKH-Qt.exe

block_cipher = None

a = Analysis(
    ['agentkh_qt.py'],
    pathex=[],
    binaries=[],
    datas=[('soul.md', '.'), ('docs/media/icon.png', 'docs/media'), ('web', 'web')],
    hiddenimports=['agentkh', 'engine', 'desktop', 'mcp', 'sfx', 'updater',
                   'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
                   'PyQt6.QtWebChannel'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='AgentKH-Qt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,   # UPX breaks Qt DLLs — keep off
    console=False,
    icon='docs/media/icon.ico',
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    name='AgentKH-Qt',
)
