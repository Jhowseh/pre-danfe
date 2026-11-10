#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\PreDANFE"
#endif

[Setup]
AppId={{B18B7613-6761-43F7-B1D1-E857794C4388}
AppName=Pré-DANFE SysPDV
AppVersion={#AppVersion}
AppPublisher=PBtec - Soluções em Automação
AppCopyright=© PBtec - Soluções em Automação
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\PreDANFE
DefaultGroupName=Pré-DANFE
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=PreDANFE-Instalador-{#AppVersion}
SetupIconFile=resources\predanfe.ico
UninstallDisplayIcon={app}\PreDANFE.exe
UninstallDisplayName=Pré-DANFE SysPDV
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
Name: "{app}\pdf"; Permissions: users-modify

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\PreDanfe\config.ini"; DestDir: "{app}"; Flags: external skipifsourcedoesntexist onlyifdoesntexist uninsneveruninstall

[INI]
Filename: "{app}\config.ini"; Section: "saida"; Key: "pasta_pdf"; String: "pdf"; Flags: createkeyifdoesntexist

[Icons]
Name: "{autoprograms}\Pré-DANFE"; Filename: "{app}\PreDANFE.exe"
Name: "{autoprograms}\Pré-DANFE Automático"; Filename: "{app}\PreDANFE-Automatico.exe"
Name: "{autoprograms}\Manual do Pré-DANFE"; Filename: "{app}\Manual-PreDANFE.pdf"
Name: "{autodesktop}\Pré-DANFE"; Filename: "{app}\PreDANFE.exe"; Tasks: desktopicon

[Run]
Filename: "{sys}\icacls.exe"; Parameters: """{app}\config.ini"" /grant *S-1-5-32-545:M"; Flags: runhidden
Filename: "{app}\PreDANFE-Automatico.exe"; Description: "Abrir o Pré-DANFE Automático"; Flags: nowait postinstall skipifsilent runasoriginaluser unchecked
Filename: "{app}\PreDANFE.exe"; Description: "Abrir o Pré-DANFE"; Flags: nowait postinstall skipifsilent runasoriginaluser
