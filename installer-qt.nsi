; Agent KH Qt — NSIS installer script (Windows setup wizard)
; No WebView2 needed: bundles its own Chromium via QtWebEngine.
; Build: makensis /DOUTFILE=AgentKH-Qt-Setup.exe /DAPPTITLE="Agent KH Qt" installer-qt.nsi
;        (run from the folder containing dist\AgentKH\)

!include "MUI2.nsh"
!include "LogicLib.nsh"

!ifndef OUTFILE
  !define OUTFILE "AgentKH-Setup.exe"
!endif
!ifndef APPTITLE
  !define APPTITLE "Agent KH Qt"
!endif

Name "${APPTITLE}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\AgentKH-Qt"
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
  File /r "dist\AgentKH-Qt\*.*"

  ; Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\${APPTITLE}"
  CreateShortcut "$SMPROGRAMS\${APPTITLE}\${APPTITLE}.lnk" "$INSTDIR\AgentKH-Qt.exe" "" "$INSTDIR\AgentKH-Qt.exe"

  ; auto-start with Windows
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AgentKHQt" '"$INSTDIR\AgentKH-Qt.exe"'

  ; uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentKH" "DisplayName" "Agent KH Qt"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentKH" "UninstallString" "$INSTDIR\Uninstall.exe"

  ; after a silent update, relaunch the app
  ${If} ${Silent}
    Exec '"$INSTDIR\AgentKH-Qt.exe"'
  ${EndIf}
SectionEnd

Section "Uninstall"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentKH"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AgentKHQt"
  RMDir /r "$SMPROGRAMS\${APPTITLE}"
  RMDir /r "$INSTDIR"
SectionEnd
