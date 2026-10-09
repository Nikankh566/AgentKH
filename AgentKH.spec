# -*- mode: python ; coding: utf-8 -*-
# Agent KH — PyInstaller build spec (Windows)
# Build on Windows:  pip install pyinstaller  &&  pyinstaller AgentKH.spec
# Output: dist/AgentKH/  (AgentKH.exe + AgentKH-Companion.exe + web/ + soul.md)

block_cipher = None

a_server = Analysis(
    ['agentkh.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web'), ('soul.md', '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz_server = PYZ(a_server.pure, a_server.zipped_data, cipher=block_cipher)
exe_server = EXE(
    pyz_server, a_server.scripts, [],
    exclude_binaries=True,
    name='AgentKH',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # console window so you can see status/logs
    icon=None,
)

a_comp = Analysis(
    ['companion.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz_comp = PYZ(a_comp.pure, a_comp.zipped_data, cipher=block_cipher)
exe_comp = EXE(
    pyz_comp, a_comp.scripts, [],
    exclude_binaries=True,
    name='AgentKH-Companion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no console for the overlay mascot
    icon=None,
)

coll = COLLECT(
    exe_server, a_server.binaries, a_server.zipfiles, a_server.datas,
    exe_comp, a_comp.binaries, a_comp.zipfiles, a_comp.datas,
    strip=False,
    upx=True,
    name='AgentKH',
)
