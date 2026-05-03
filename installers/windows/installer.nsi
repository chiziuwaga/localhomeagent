; Local Home Agent - NSIS Installer Script
; Build with: makensis installer.nsi

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ============================================================================
; GENERAL
; ============================================================================

!define PRODUCT_NAME "Local Home Agent"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "FixItForMe.ai"
!define PRODUCT_WEB_SITE "https://fixitforme.ai"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\LocalHomeAgent.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "LocalHomeAgent-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES\LocalHomeAgent"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show

; Request admin privileges
RequestExecutionLevel admin

; ============================================================================
; MODERN UI CONFIGURATION
; ============================================================================

!define MUI_ABORTWARNING

; Welcome page
!define MUI_WELCOMEPAGE_TITLE "Welcome to Local Home Agent Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of ${PRODUCT_NAME}.$\r$\n$\r$\nLocal Home Agent is an AI-powered smart home controller that runs entirely on your local network. No cloud required.$\r$\n$\r$\nClick Next to continue."

; Finish page
!define MUI_FINISHPAGE_RUN "$INSTDIR\LocalHomeAgent.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Local Home Agent"
!define MUI_FINISHPAGE_LINK "Visit our website"
!define MUI_FINISHPAGE_LINK_LOCATION "${PRODUCT_WEB_SITE}"

; ============================================================================
; PAGES
; ============================================================================

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ============================================================================
; LANGUAGES
; ============================================================================

!insertmacro MUI_LANGUAGE "English"

; ============================================================================
; SECTIONS
; ============================================================================

Section "Core Files (required)" SecCore
  SectionIn RO

  SetOutPath "$INSTDIR"
  SetOverwrite ifnewer

  ; Main application executable (from PyInstaller dist folder)
  File "..\..\dist\LocalHomeAgent.exe"

  ; README if exists
  File /nonfatal "..\..\README.md"

  ; Static files
  SetOutPath "$INSTDIR\static"
  File /nonfatal /r "..\..\static\*.*"

  ; Templates
  SetOutPath "$INSTDIR\templates"
  File /nonfatal /r "..\..\templates\*.*"

  ; Config directory
  SetOutPath "$INSTDIR\config"
  File /nonfatal "..\..\config\*.yaml"
  File /nonfatal "..\..\config\*.example.yaml"

  ; Create start menu shortcuts
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\LocalHomeAgent.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\uninst.exe"

  ; Create desktop shortcut
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\LocalHomeAgent.exe"

  ; Register uninstaller
  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\LocalHomeAgent.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"

  ; Calculate installed size
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd

Section "Autostart on Login" SecAutostart
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${PRODUCT_NAME}" "$INSTDIR\LocalHomeAgent.exe --minimize"
SectionEnd

; ============================================================================
; SECTION DESCRIPTIONS
; ============================================================================

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} "Core application files (required)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutostart} "Start Local Home Agent when Windows starts"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ============================================================================
; UNINSTALLER
; ============================================================================

Section Uninstall
  ; Remove files
  RMDir /r "$INSTDIR\static"
  RMDir /r "$INSTDIR\templates"
  RMDir /r "$INSTDIR\config"
  Delete "$INSTDIR\LocalHomeAgent.exe"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\uninst.exe"

  ; Remove shortcuts
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"

  ; Remove registry keys
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${PRODUCT_NAME}"

  ; Remove install directory (if empty)
  RMDir "$INSTDIR"

  SetAutoClose true
SectionEnd

; ============================================================================
; FUNCTIONS
; ============================================================================

Function .onInit
  ; Check for admin rights
  UserInfo::GetAccountType
  Pop $0
  ${If} $0 != "admin"
    MessageBox MB_ICONSTOP "Administrator rights required!"
    SetErrorLevel 740 ; ERROR_ELEVATION_REQUIRED
    Quit
  ${EndIf}
FunctionEnd
