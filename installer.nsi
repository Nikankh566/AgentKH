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
