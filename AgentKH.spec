# -*- mode: python ; coding: utf-8 -*-
# Agent KH v2 — PyInstaller build spec (Windows)
# Build on Windows:  pip install pyinstaller  &&  pyinstaller AgentKH.spec
# Output: dist/AgentKH/AgentKH.exe  (single island app, no browser needed)

block_cipher = None

a = Analysis(
    ['agentkh.py'],
    pathex=[],
    binaries=[],
    datas=[('soul.md', '.'), ('docs/media/icon.png', 'docs/media'), ('web', 'web')],
    hiddenimports=[],
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
    name='AgentKH',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # windowed: the island IS the UI
    icon='docs/media/icon.ico',
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=True,
    name='AgentKH',
)
