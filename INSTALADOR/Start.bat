@echo off
:: --- ETAPA 1: Elevação de Privilégios (Admin) ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando permissoes de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: --- ETAPA 2: Definição de Contexto (O Pulo do Gato) ---
:: Forçamos o Windows a olhar para a pasta correta antes de chamar o comando.
:: Isso garante que o config.json e o WinRing0x64 sejam encontrados.
cd /d "C:\Windows\SystemOut\XMR\"

:: --- ETAPA 3: Execução ---
:: Agora que estamos na pasta certa, chamamos o disparador original
call start.cmd