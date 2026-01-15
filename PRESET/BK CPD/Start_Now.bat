@echo off
title XMRig Launcher [Auto-Admin & Smart Path]
color 0A

:: --- ETAPA 1: Hybrid Launcher (VBS Injection) ---
:: Verifica se ja estamos rodando em modo oculto/admin
if "%~1"=="__HIDDEN__" goto :PAYLOAD

:: Se nao, cria um VBS temporario para reiniciar este BAT como Admin e Oculto
set "VBS_SCRIPT=%TEMP%\starter-%RANDOM%.vbs"
echo Set UAC = CreateObject^("Shell.Application"^) > "%VBS_SCRIPT%"
echo UAC.ShellExecute "cmd.exe", "/c ""%~f0"" __HIDDEN__", "", "runas", 0 >> "%VBS_SCRIPT%"

:: Executa o VBS e sai (Isso fecha a janela preta inicial)
cscript //nologo "%VBS_SCRIPT%"
del "%VBS_SCRIPT%"
exit /b

:PAYLOAD
:: --- ETAPA 2: Lógica Principal (Hidden Mode) ---
:: Garante que estamos na pasta correta
cd /d "%~dp0"

:: --- ETAPA 2: Lógica de Localização (Smart Path) ---
:: Define as variaveis de caminho
set "CURRENT_DIR=%~dp0"
set "FALLBACK_DIR=C:\Windows\SystemOut\XMR\"

echo [ENGENHARIA] Verificando localizacao do minerador...

:: Verifica se o xmrig.exe esta na pasta onde o script esta (Prioridade 1)
if exist "%CURRENT_DIR%xmrig.exe" (
    echo [INFO] Minerador encontrado na pasta local.
    cd /d "%CURRENT_DIR%"
    goto :EXECUTE
)

:: Se nao achou, verifica na pasta do sistema (Prioridade 2)
if exist "%FALLBACK_DIR%xmrig.exe" (
    echo [INFO] Minerador nao encontrado localmente. Buscando em SystemOut...
    cd /d "%FALLBACK_DIR%"
    goto :EXECUTE
)

:: Se nao achou em lugar nenhum
cls
color 0C
echo ========================================================
echo [ERRO CRITICO] O arquivo 'xmrig.exe' nao foi encontrado!
echo ========================================================
echo Locais verificados:
echo 1. %CURRENT_DIR%
echo 2. %FALLBACK_DIR%
echo.
pause
exit

:EXECUTE
:: --- ETAPA 3: Execução ---
cls
echo [SISTEMA] Iniciando XMRig com privilegios de Administrador...
echo [CONFIG]  Lendo config.json automaticamente...
echo.

:: Executa direto (sem precisar do start.cmd).
:: O comando 'pause' abaixo segura a janela caso o minerador feche por erro.
xmrig.exe
pause