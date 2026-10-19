#define MyAppName "SIGM — Sistema de Gestão de Membros"
#define MyAppVersion "2.1.3"
#define MyAppPublisher "William Lima"
#define MyAppExeName "SIGM.exe"
#define MySetupName "SIGM_Setup_2.1.3_Web"

[Setup]
AppId={{A5C32D13-59B0-4B2C-9C5B-3F2C5E8C3D10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName}
VersionInfoProductName={#MyAppName}
DefaultDirName={autopf}\SIGM
DefaultGroupName=SIGM
AllowNoIcons=yes
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename={#MySetupName}
SetupIconFile=..\assets\icones\sigm.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[InstallDelete]
; Atualizando sobre o SIGM desktop: remove so as bibliotecas antigas do programa.
; Os dados do usuario ficam em %LOCALAPPDATA%\SIGM e nunca sao tocados.
Type: filesandordirs; Name: "{app}\_internal"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\SIGM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SIGM"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SIGM"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o SIGM agora"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    MsgBox(
      'Os dados do SIGM foram preservados para permitir reinstalação ou recuperação.'#13#10#13#10 +
      'Pasta de dados: %LOCALAPPDATA%\SIGM',
      mbInformation,
      MB_OK
    );
  end;
end;
