[Setup]
AppName=Görsel Dönüştürücü
AppVersion=1.0
DefaultDirName={pf}\Görsel Dönüştürücü
DefaultGroupName=Görsel Dönüştürücü
OutputDir=installer
OutputBaseFilename=GorselDonusturucu_Setup
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\app.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Görsel Dönüştürücü"; Filename: "{app}\app.exe"
Name: "{commondesktop}\Görsel Dönüştürücü"; Filename: "{app}\app.exe"

[Run]
Filename: "{app}\app.exe"; Description: "Programı şimdi çalıştır"; Flags: nowait postinstall skipifsilent 