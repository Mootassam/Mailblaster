; MailBlaster installer â€” ships the official, digitally signed Python runtime (Python Software
; Foundation) with the app, so Windows Smart App Control can verify what it runs.
; Build: powershell -ExecutionPolicy Bypass -File build.ps1   (stages build_embed\ then runs ISCC)

#define MyAppName "MailBlaster"
#define MyAppVersion "3.3.0"
#define MyAppPublisher "MailBlaster"

[Setup]
; same AppId as earlier versions -> installs over them as an upgrade
AppId={{A1E9F2C4-7B3D-4A6E-9C2F-MAILBLASTER20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
LicenseFile=LICENSE.txt
OutputDir=installer_output
OutputBaseFilename=MailBlaster-Setup
Compression=lzma2/max
SolidCompression=no
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
SetupIconFile=mailblaster.ico
UninstallDisplayIcon={app}\app\mailblaster.ico
UninstallDisplayName={#MyAppName}
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: checkedonce

[InstallDelete]
; leftovers of the old PyInstaller build (3.0 and earlier)
Type: files; Name: "{app}\MailBlaster.exe"
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{autoprograms}\{#MyAppName}\{#MyAppName}.lnk"
Type: dirifempty; Name: "{autoprograms}\{#MyAppName}"
; replace program files cleanly on every upgrade
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"

[Files]
Source: "build_embed\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "build_embed\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\server.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\app\mailblaster.ico"; Comment: "Email campaigns, inbox and deliverability"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\server.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\app\mailblaster.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\server.py"""; WorkingDir: "{app}\app"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
{ Close a running MailBlaster so its files can be replaced or removed: python/pythonw started
  from the install folder, the old MailBlaster.exe, and the Cloudflare tunnel helper it started.
  Only processes whose path is inside the install or data folder are touched. }
procedure StopMailBlaster();
var
  Rc: Integer;
  Cmd, AppDir, DataDir: String;
begin
  AppDir := Lowercase(ExpandConstant('{app}'));
  DataDir := Lowercase(ExpandConstant('{localappdata}\MailBlaster'));
  Cmd := '-NoProfile -ExecutionPolicy Bypass -Command "Get-Process python,pythonw,MailBlaster,cloudflared -ErrorAction SilentlyContinue | ' +
         'Where-Object { $_.Path -and ($_.Path.ToLower().StartsWith(''' + AppDir + ''') -or $_.Path.ToLower().StartsWith(''' + DataDir + ''')) } | ' +
         'Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 900"';
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '', SW_HIDE, ewWaitUntilTerminated, Rc);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopMailBlaster();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopMailBlaster();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\MailBlaster');
    if DirExists(DataDir) and not UninstallSilent() then
      if MsgBox('Also delete your MailBlaster data?' + #13#10 + #13#10 +
                'This permanently removes your contacts, campaigns, sender accounts, inbox and settings from this computer.' + #13#10 + #13#10 +
                'Choose No to keep them (they come back if you reinstall).',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;

[UninstallDelete]
; program files only - data in %LOCALAPPDATA%\MailBlaster is removed only if the user says so
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
Type: dirifempty; Name: "{app}"
