; Agent KH — NSIS installer script (Windows setup wizard)
; Build: makensis /DOUTFILE=AgentKH-Setup.exe /DAPPTITLE="Agent KH" installer.nsi
;        (run from the folder containing dist\AgentKH\)

!include "MUI2.nsh"
!include "LogicLib.nsh"

!ifndef OUTFILE
  !define OUTFILE "AgentKH-Setup.exe"
!endif
!ifndef APPTITLE
  !define APPTITLE "Agent KH"
!endif

Name "${APPTITLE}"
OutFile "${OUTFILE}"
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
  ; WebView2 runtime check — pywebview needs it to open its window
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C573A9A29B}" "pv"
  ${If} $0 == ""
    MessageBox MB_OK|MB_ICONEXCLAMATION "Agent KH needs the Microsoft Edge WebView2 Runtime to run.$\n$\nPlease install it (free) from:$\nhttps://developer.microsoft.com/microsoft-edge/webview2/$\n(choose 'Evergreen Standalone Installer')$\n$\nThe installation will continue, but Agent KH won't start until WebView2 is installed."
  ${EndIf}

  SetOutPath "$INSTDIR"
  ; files built by PyInstaller (dist\AgentKH\*)
  File /r "dist\AgentKH\*.*"

  ; Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\${APPTITLE}"
  CreateShortcut "$SMPROGRAMS\${APPTITLE}\${APPTITLE}.lnk" "$INSTDIR\AgentKH.exe" "" "$INSTDIR\AgentKH.exe"

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
  RMDir /r "$SMPROGRAMS\${APPTITLE}"
  RMDir /r "$INSTDIR"
SectionEnd
