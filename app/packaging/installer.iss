[Setup]
AppName=Facturación
AppVersion=2.1.0
AppPublisher=ADHER-NEO
DefaultDirName={autopf}\Facturacion
DefaultGroupName=Facturación
OutputBaseFilename=FacturacionSetup
OutputDir=dist_installer
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Facturacion.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "dist\Facturacion\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\Facturación"; Filename: "{app}\Facturacion.exe"
Name: "{autodesktop}\Facturación"; Filename: "{app}\Facturacion.exe"

[Run]
Filename: "{app}\Facturacion.exe"; Description: "Iniciar Facturación"; Flags: postinstall nowait skipifsilent
