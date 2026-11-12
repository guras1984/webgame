#define AppName "KJ Patch Downloader"
#define AppVersion "1.1.0"
#define AppPublisher "KJ TOOL"
#define AppExeName "KJ Patch Downloader.exe"

[Setup]
AppId={{C52B34AB-F35E-4E5F-9B87-1AAE758B9423}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\KJ TOOL\KJ Patch Downloader
DefaultGroupName=KJ TOOL\KJ Patch Downloader
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\..\..\dist
OutputBaseFilename=KJ-Patch-Downloader-Setup
SetupIconFile=..\assets\KJ-TOOL.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 아이콘:"; Flags: checkedonce

[Files]
Source: "..\..\..\..\dist\KJ Patch Downloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\KJ TOOL\KJ Patch Downloader"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\KJ Patch Downloader"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "KJ Patch Downloader 실행"; Flags: postinstall nowait skipifsilent
