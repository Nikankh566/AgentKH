; Agent KH — NSIS installer script (Windows setup wizard)
; Build: makensis installer.nsi   (run from the folder containing dist\AgentKH\)
; Output: AgentKH-Setup.exe

!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "Agent KH"
OutFile "AgentKH-Setup.exe"
InstallDir "$LOCALAPPDATA\AgentKH"
RequestExecutionLevel user
Unicode True

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  ; files built by PyInstaller (dist\AgentKH\*)
  File /r "dist\AgentKH\*.*"

  ; Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\Agent KH"
  CreateShortcut "$SMPROGRAMS\Agent KH\Agent KH.lnk" "$INSTDIR\AgentKH.exe" "" "$INSTDIR\AgentKH.exe"

  ; auto-start with Windows
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AgentKH" '"$INSTDIR\AgentKH.exe"'

  ; uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentKH" "DisplayName" "Agent KH"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentKH" "UninstallString" "$INSTDIR\Uninstall.exe"

  ; after a silent update, relaunch the app
  ${If} ${Silent}
    Exec '"$INSTDIR\AgentKH.exe"'
  ${EndIf}
SectionEnd

Section "Uninstall"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentKH"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AgentKH"
  RMDir /r "$SMPROGRAMS\Agent KH"
  RMDir /r "$INSTDIR"
SectionEnd
