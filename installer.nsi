; NSIS Installer Script for Local Home Agent (F4.6.8)
; Nullsoft Scriptable Install System configuration
; Compile with: makensis installer.nsi

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; --- General Definitions ---
!define APPNAME "LocalHomeAgent"
!define COMPANYNAME "FixItForMe.ai"
!define DESCRIPTION "AI-powered local home assistant with smart device control"
!define VERSIONMAJOR 1
!define VERSIONMINOR 0
!define VERSIONBUILD 0
!define HELPURL "https://github.com/Fix-It-For-Me-AI/local-home-agent"
!define UPDATEURL "https://github.com/Fix-It-For-Me-AI/local-home-agent/releases"
!define ABOUTURL "https://fixitforme.ai"

; Installer attributes
Name "${APPNAME}"
OutFile "LocalHomeAgent-Setup-${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}.exe"
InstallDir "$PROGRAMFILES64\${APPNAME}"
InstallDirRegKey HKLM "Software\${APPNAME}" "InstallDir"
RequestExecutionLevel admin

; Version information
VIProductVersion "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}.0"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "CompanyName" "${COMPANYNAME}"
VIAddVersionKey "LegalCopyright" "© 2025 ${COMPANYNAME}"
VIAddVersionKey "FileDescription" "${DESCRIPTION}"
VIAddVersionKey "FileVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
VIAddVersionKey "ProductVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"

; --- MUI Configuration ---
!define MUI_ABORTWARNING
!define MUI_ICON "static\favicon.ico"
!define MUI_UNICON "static\favicon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "static\installer-banner.bmp"

; Welcome page
!insertmacro MUI_PAGE_WELCOME

; License page
!insertmacro MUI_PAGE_LICENSE "LICENSE"

; Components page
!insertmacro MUI_PAGE_COMPONENTS

; Directory page
!insertmacro MUI_PAGE_DIRECTORY

; Install files page
!insertmacro MUI_PAGE_INSTFILES

; Finish page with options
!define MUI_FINISHPAGE_RUN "$INSTDIR\LocalHomeAgent.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Local Home Agent"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.md"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

; --- Installer Sections ---

Section "Core Application (required)" SecCore
    SectionIn RO ; Read-only, required
    
    SetOutPath "$INSTDIR"
    
    ; Copy main executable and files
    File "dist\LocalHomeAgent.exe"
    File "README.md"
    File "LICENSE"
    File "requirements.txt"
    
    ; Copy templates
    SetOutPath "$INSTDIR\templates"
    File /r "templates\*.*"
    
    ; Copy static files
    SetOutPath "$INSTDIR\static"
    File /r "static\*.*"
    
    ; Copy config
    SetOutPath "$INSTDIR\config"
    File /nonfatal "config\*.*"
    
    ; Create models directory
    CreateDirectory "$INSTDIR\models"
    
    ; Create data directory for user data
    CreateDirectory "$APPDATA\${APPNAME}"
    CreateDirectory "$APPDATA\${APPNAME}\logs"
    CreateDirectory "$APPDATA\${APPNAME}\data"
    
    ; Write installation info to registry
    WriteRegStr HKLM "Software\${APPNAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\${APPNAME}" "Version" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Add to Add/Remove Programs
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "DisplayName" "${APPNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "QuietUninstallString" "$\"$INSTDIR\Uninstall.exe$\" /S"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "InstallLocation" "$\"$INSTDIR$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "DisplayIcon" "$\"$INSTDIR\LocalHomeAgent.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "Publisher" "${COMPANYNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "HelpLink" "${HELPURL}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "URLUpdateInfo" "${UPDATEURL}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "URLInfoAbout" "${ABOUTURL}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "VersionMajor" ${VERSIONMAJOR}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "VersionMinor" ${VERSIONMINOR}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "NoRepair" 1
    
    ; Get installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
                     "EstimatedSize" "$0"
SectionEnd

Section "Start Menu Shortcuts" SecStartMenu
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\LocalHomeAgent.exe" \
                   "" "$INSTDIR\LocalHomeAgent.exe" 0
    CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe" \
                   "" "$INSTDIR\Uninstall.exe" 0
    CreateShortcut "$SMPROGRAMS\${APPNAME}\README.lnk" "$INSTDIR\README.md"
SectionEnd

Section "Desktop Shortcut" SecDesktop
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\LocalHomeAgent.exe" \
                   "" "$INSTDIR\LocalHomeAgent.exe" 0
SectionEnd

Section "Auto-Start with Windows" SecAutoStart
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" \
                     "${APPNAME}" "$\"$INSTDIR\LocalHomeAgent.exe$\" --minimized"
SectionEnd

Section /o "LLM Runtime (llama.cpp)" SecLLM
    ; Download and install llama.cpp runtime
    SetOutPath "$INSTDIR\llm"
    
    ; Note: In production, download from GitHub releases
    ; NSISdl::download "https://github.com/ggerganov/llama.cpp/releases/..." "$INSTDIR\llm\llama.dll"
    
    ; Create placeholder config
    FileOpen $0 "$INSTDIR\config\llm_runtime.json" w
    FileWrite $0 '{"runtime": "llama.cpp", "model": "llama-3.2-3b"}'
    FileClose $0
SectionEnd

; --- Section Descriptions ---
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} "Core application files (required)"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Create Start Menu shortcuts"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create Desktop shortcut"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecAutoStart} "Start automatically when Windows starts"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecLLM} "Install local LLM runtime for offline AI (requires 4GB+ RAM)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; --- Uninstaller Section (F4.6.10) ---
Section "Uninstall"
    ; Stop running instance
    ExecWait 'taskkill /F /IM LocalHomeAgent.exe'
    
    ; Remove auto-start entry
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APPNAME}"
    
    ; Remove files
    Delete "$INSTDIR\LocalHomeAgent.exe"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\LICENSE"
    Delete "$INSTDIR\requirements.txt"
    Delete "$INSTDIR\Uninstall.exe"
    
    ; Remove directories
    RMDir /r "$INSTDIR\templates"
    RMDir /r "$INSTDIR\static"
    RMDir /r "$INSTDIR\config"
    RMDir /r "$INSTDIR\models"
    RMDir /r "$INSTDIR\llm"
    RMDir "$INSTDIR"
    
    ; Remove shortcuts
    Delete "$DESKTOP\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\Uninstall.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\README.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"
    
    ; Remove registry entries
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
    DeleteRegKey HKLM "Software\${APPNAME}"
    
    ; Ask about user data
    MessageBox MB_YESNO "Remove user data and settings?" IDNO SkipUserData
        RMDir /r "$APPDATA\${APPNAME}"
    SkipUserData:
SectionEnd

; --- Callbacks ---
Function .onInit
    ; Check for Windows version
    ${If} ${AtLeastWin10}
        ; OK
    ${Else}
        MessageBox MB_OK|MB_ICONSTOP "This application requires Windows 10 or later."
        Abort
    ${EndIf}
    
    ; Check for previous installation
    ReadRegStr $0 HKLM "Software\${APPNAME}" "InstallDir"
    ${If} $0 != ""
        MessageBox MB_YESNO "A previous installation was found at $0. Would you like to uninstall it first?" IDNO SkipUninstall
            ExecWait '"$0\Uninstall.exe" /S'
        SkipUninstall:
    ${EndIf}
FunctionEnd

Function un.onInit
    MessageBox MB_YESNO "Are you sure you want to uninstall ${APPNAME}?" IDYES +2
        Abort
FunctionEnd
