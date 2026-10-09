@echo off
REM Agent KH — build Windows executables
REM Requires: Python 3.9+ and pip
echo [*] Installing PyInstaller...
pip install pyinstaller >nul 2>&1
echo [*] Building AgentKH.exe + AgentKH-Companion.exe ...
pyinstaller AgentKH.spec
echo.
echo [OK] Done! Files are in dist\AgentKH\
echo      Run dist\AgentKH\AgentKH.exe to start.
pause
