#ifndef BuildVersion
  #define BuildVersion "0.2.1"
#endif
#ifndef ProductId
  #define ProductId "MixCut.Desktop"
#endif
#ifndef SetupName
  #define SetupName "MixCut-Setup"
#endif
#ifndef StatePath
  #define StatePath "{localappdata}\MixCut"
#endif
[Setup]
AppId={#ProductId}
AppName=MixCut
AppVersion={#BuildVersion}
DefaultDirName={localappdata}\Programs\MixCut
DefaultGroupName=MixCut
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename={#SetupName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\MixCut.exe
AppMutex=Local\MixCut.Desktop.Running,Local\MixCut.Desktop.Cleanup
CloseApplications=no
RestartApplications=no
SetupLogging=no
UninstallLogging=no

[Files]
Source: "..\dist\MixCut\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MixCut"; Filename: "{app}\MixCut.exe"
Name: "{group}\一键卸载 MixCut"; Filename: "{uninstallexe}"
Name: "{app}\一键卸载 MixCut"; Filename: "{uninstallexe}"

[INI]
Filename: "{app}\mixcut-install.ini"; Section: "MixCut"; Key: "Uninstaller"; String: "{uninstallexe}"; Flags: uninsdeleteentry uninsdeletesectionifempty

Filename: "{app}\mixcut-install.ini"; Section: "MixCut"; Key: "ProductId"; String: "{#ProductId}"; Flags: uninsdeleteentry uninsdeletesectionifempty

; This file belongs exclusively to the installer. Use an exact path, never
; a wildcard that could delete user files placed in the install directory.
[UninstallDelete]
Type: files; Name: "{app}\mixcut-install.ini"

[Messages]
SetupWindowTitle=安装 - %1
UninstallAppFullTitle=卸载 %1
UninstallAppTitle=卸载
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonCancel=取消
ButtonFinish=完成
WelcomeLabel1=欢迎安装 [name]
WelcomeLabel2=此程序将安装 [name/ver]，并提供一键卸载与缓存清理。%n%n请先关闭正在运行的 MixCut。
SelectDirLabel3=MixCut 将安装到以下位置。
ReadyLabel1=已准备好安装 MixCut。
FinishedHeadingLabel=MixCut 安装完成
FinishedLabelNoIcons=安装已完成。打开安装目录中的 MixCut.exe 即可使用。
ConfirmUninstall=是否卸载 MixCut 并清理已记录的程序缓存？%n%n原始素材、导出视频和项目组合历史会保留。
UninstalledAll=MixCut 已卸载，已记录的程序缓存已清理。

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := not CheckForMutexes('Local\MixCut.Desktop.Running');
  if not Result and not UninstallSilent then
    MsgBox('请先关闭所有 MixCut 窗口，再重新卸载。', mbError, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Params: String;
begin
  if CurUninstallStep = usUninstall then begin
    { AppMutex has already been checked. Creating this earlier in
      InitializeUninstall makes the uninstaller detect its own cleanup mutex. }
    CreateMutex('Local\MixCut.Desktop.Cleanup');
    { Block new app launches, then recheck in case one started while the user
      was confirming the uninstall. Never remove files while an app is running. }
    if CheckForMutexes('Local\MixCut.Desktop.Running') then begin
      Log('MixCut started before cleanup; uninstall aborted before deleting files.');
      if not UninstallSilent then
        MsgBox('请先关闭所有 MixCut 窗口，再重新卸载。', mbError, MB_OK);
      Abort;
    end;
    Params := '--cleanup-uninstall --state-directory "' + ExpandConstant('{#StatePath}') + '"';
    if UninstallSilent then Params := Params + ' --silent-cleanup';
    if not Exec(ExpandConstant('{app}\MixCut.exe'), Params,
      ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then begin
      if not UninstallSilent then MsgBox('无法启动缓存清理。请重新安装 MixCut 后重试卸载。', mbError, MB_OK);
      Abort;
    end;
    if ResultCode <> 0 then begin
      if not UninstallSilent then MsgBox('缓存未清理完成，卸载已停止。请处理占用文件或磁盘连接问题后重试。', mbError, MB_OK);
      Abort;
    end;
  end;
end;


