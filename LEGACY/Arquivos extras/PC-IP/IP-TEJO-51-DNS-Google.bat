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
netsh interface ipv4 set address name="Ethernet" static 192.168.15.51 255.255.255.0 192.168.15.1 1

REM -- Define DNS primário --
netsh interface ipv4 set dns name="Ethernet" static 8.8.8.8

REM -- Adiciona DNS alternativo --
netsh interface ipv4 add dnsserver name="Ethernet" address=8.8.4.4 index=2

REM -- Reinicia a interface para aplicar configurações --
netsh interface set interface name="Ethernet" admin=disabled
netsh interface set interface name="Ethernet" admin=enabled

REM -- Desativa proxy --:
powershell -WindowStyle Hidden -Command ^
 "Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 0"
