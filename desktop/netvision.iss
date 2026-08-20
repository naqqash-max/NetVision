; =====================================================================
; NetVision Windows Desktop Installer Script (Inno Setup)
; Instructions: Run build-installer.bat to compile this script.
;               Produces: dist\installer\NetVision-Setup.exe
; =====================================================================

[Setup]
AppName=NetVision
AppVersion=1.0.0
AppPublisher=Naqqash Abbasi
DefaultDirName={commonpf}\NetVision
DefaultGroupName=NetVision
UninstallDisplayIcon={app}\NetVision.exe
OutputDir=..\dist\installer
OutputBaseFilename=NetVision-Setup
SetupIconFile=netvision.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
CloseApplications=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; Copy all compiled binaries, databases, and assets
Source: "dist\NetVision\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "database_data,database_data\*,config.env,netvision_desktop.log"

[Icons]
; Start Menu and Desktop shortcuts
Name: "{group}\NetVision"; Filename: "{app}\NetVision.exe"
Name: "{commondesktop}\NetVision"; Filename: "{app}\NetVision.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
; Auto-launch after installation completes (requests Admin execution for raw socket pings)
Filename: "{app}\NetVision.exe"; Description: "Launch NetVision"; Flags: nowait postinstall skipifsilent shellexec

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Try to kill running processes if they exist to prevent file locking issues
  Exec('taskkill', '/f /im NetVision.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/f /im backend_app.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/f /im networking_engine_app.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Try to kill running processes before uninstalling
  Exec('taskkill', '/f /im NetVision.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/f /im backend_app.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/f /im networking_engine_app.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurUninstallStepChanged(UninstallStep: TUninstallStep);
var
  AppDataDir: String;
begin
  if UninstallStep = usPostUninstall then
  begin
    if MsgBox('Do you want to delete all NetVision application data, including your local database, configuration, and logs?', mbConfirmation, MB_YESNO) = idYes then
    begin
      AppDataDir := ExpandConstant('{localappdata}\NetVision');
      // Delete database directory and other runtime files from LocalAppData
      DelTree(AppDataDir, True, True, True);
    end;
  end;
end;
