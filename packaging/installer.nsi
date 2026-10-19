Unicode True
!include "MUI2.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"

!ifndef VERSION
  !define VERSION "3.0.1"
!endif
!ifndef STAGING
  !define STAGING "..\dist\OpenCoreHelper"
!endif

Name "OpenCore Helper ${VERSION}"
OutFile "..\dist\OpenCoreHelper-${VERSION}-Setup-x64.exe"
InstallDir "$PROGRAMFILES64\SnoopyOS Company\OpenCore Helper"
InstallDirRegKey HKLM "Software\SnoopyOS Company\OpenCore Helper" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
VIProductVersion "3.0.1.0"
VIAddVersionKey "ProductName" "OpenCore Helper"
VIAddVersionKey "CompanyName" "SnoopyOS Company"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "OpenCore Helper Setup"
VIAddVersionKey "LegalCopyright" "Copyright (c) 2026 Chimpi-hackintosh"

!define MUI_ABORTWARNING
!define MUI_LANGDLL_REGISTRY_ROOT "HKLM"
!define MUI_LANGDLL_REGISTRY_KEY "Software\SnoopyOS Company\OpenCore Helper"
!define MUI_LANGDLL_REGISTRY_VALUENAME "InstallerLanguage"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "PortugueseBR"

LangString WrongArchitecture ${LANG_ENGLISH} "This edition requires Windows x64."
LangString WrongArchitecture ${LANG_PORTUGUESEBR} "Esta edição requer Windows x64."
LangString DesktopShortcut ${LANG_ENGLISH} "Desktop shortcut"
LangString DesktopShortcut ${LANG_PORTUGUESEBR} "Atalho na área de trabalho"

Function .onInit
  SetRegView 64
  SetShellVarContext all
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "$(WrongArchitecture)"
    Abort
  ${EndIf}
FunctionEnd

Section "OpenCore Helper" Core
  SectionIn RO
  SetRegView 64
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  File /r "${STAGING}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\OpenCore Helper"
  CreateShortcut "$SMPROGRAMS\OpenCore Helper\OpenCore Helper.lnk" "$INSTDIR\OpenCoreHelper.exe"
  CreateShortcut "$SMPROGRAMS\OpenCore Helper\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\SnoopyOS Company\OpenCore Helper" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\SnoopyOS Company\OpenCore Helper" "InstallerLanguage" "$LANGUAGE"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "DisplayName" "OpenCore Helper"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "Publisher" "SnoopyOS Company"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "DisplayIcon" "$INSTDIR\OpenCoreHelper.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper" "NoRepair" 1
SectionEnd

Section /o "$(DesktopShortcut)" Desktop
  SetShellVarContext all
  CreateShortcut "$DESKTOP\OpenCore Helper.lnk" "$INSTDIR\OpenCoreHelper.exe"
SectionEnd

Function un.onInit
  SetRegView 64
  SetShellVarContext all
  !insertmacro MUI_UNGETLANGUAGE
FunctionEnd

Section "Uninstall"
  SetRegView 64
  SetShellVarContext all
  Delete "$DESKTOP\OpenCore Helper.lnk"
  Delete "$SMPROGRAMS\OpenCore Helper\OpenCore Helper.lnk"
  Delete "$SMPROGRAMS\OpenCore Helper\Uninstall.lnk"
  RMDir "$SMPROGRAMS\OpenCore Helper"
  Delete "$INSTDIR\OpenCoreHelper.exe"
  Delete "$INSTDIR\settings.default.json"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  RMDir /r "$INSTDIR\lib"
  RMDir /r "$INSTDIR\locales"
  RMDir /r "$INSTDIR\licenses"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper"
  DeleteRegKey HKLM "Software\SnoopyOS Company\OpenCore Helper"
  ; User settings, logs and downloaded files in LocalAppData are preserved.
SectionEnd

