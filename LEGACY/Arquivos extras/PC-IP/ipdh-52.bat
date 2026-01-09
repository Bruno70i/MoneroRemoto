@echo off
pushd "%~dp0"

REM Se não foi passado o parâmetro am_admin, relança com ele (modo administrador)
if not "%1"=="am_admin" (
    powershell -Command "Start-Process '%~f0' -ArgumentList 'am_admin' -Verb runAs"
    exit /b
)

:am_admin
REM Aqui já está em modo administrador!
echo Executando como administrador...

REM -- Configura IP estático --
netsh interface ip set address name="Ethernet" static 10.23.20.52 255.255.255.0 10.23.20.1

REM -- Define DNS primário --
netsh interface ip set dns name="Ethernet" static 10.23.22.223

REM -- Adiciona DNS alternativo --
netsh interface ip add dns name="Ethernet" 10.23.22.224 index=2

REM -- Reinicia a interface para aplicar configurações --
netsh interface set interface name="Ethernet" admin=disabled
netsh interface set interface name="Ethernet" admin=enabled

REM Define o servidor proxy no registro
powershell -Command "Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyServer -Value 'lyra.sede.dersa:8080'"

REM Ativa o uso de proxy
powershell -Command "Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 1"