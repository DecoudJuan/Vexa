[Setup]
AppName=Vexa
AppVersion=2.9.0
AppPublisher=Vexa
DefaultDirName={autopf}\Facturacion
DefaultGroupName=Vexa
OutputBaseFilename=FacturacionSetup
OutputDir=dist_installer
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\assets\vexa_symbol.ico
UninstallDisplayIcon={app}\Facturacion.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "dist\Facturacion\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\Vexa"; Filename: "{app}\Facturacion.exe"
Name: "{autodesktop}\Vexa"; Filename: "{app}\Facturacion.exe"

[Run]
Filename: "{app}\Facturacion.exe"; Description: "Iniciar Vexa"; Flags: postinstall nowait skipifsilent
