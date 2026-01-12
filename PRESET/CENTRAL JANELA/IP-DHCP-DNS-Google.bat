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


REM Configura a interface para obter IP automaticamente via DHCP
netsh interface ip set address name="Ethernet" source=dhcp

REM Define o DNS preferencial
netsh interface ip set dns name="Ethernet" static 8.8.8.8

REM Adiciona o DNS alternativo
netsh interface ip add dns name="Ethernet" 8.8.4.4 index=2

REM -- Reinicia a interface para aplicar configurações --
netsh interface set interface name="Ethernet" admin=disabled
netsh interface set interface name="Ethernet" admin=enabled

REM desativa o uso de proxy
powershell -WindowStyle Hidden -Command "Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 0"