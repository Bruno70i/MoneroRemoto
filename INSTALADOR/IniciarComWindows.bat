@echo off
setlocal
title Boot Manager V8 [AUTO-CLEAN SYSTEM]
color 0B

:: Define arquivo de log
set "LOGFILE=%~dp0boot_manager.log"

:: --- 1. Auto-Elevação ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [SISTEMA] Solicitando permissao de Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
set "TASK_NAME=XMRig_Auto_Boot"

:: --- DEFINIÇÃO DOS ALVOS ---
set "TARGET_DIR=C:\Windows\SystemOut\XMR"
set "TARGET_SCRIPT=%TARGET_DIR%\Start.bat"
set "SILENCER_VBS=%TARGET_DIR%\Ghost_Launcher.vbs"

:: --- 2. Verificação de Segurança ---
if not exist "%TARGET_SCRIPT%" (
    cls
    color 0C
    echo [ALERTA] O Start.bat nao existe em:
    echo %TARGET_SCRIPT%
    echo.
    echo O Boot Manager vai configurar a estrutura, mas o minerador
    echo nao vai rodar ate voce colocar os arquivos la.
    pause
)

:: --- 3. Verificação de Estado ---
schtasks /query /tn "%TASK_NAME%" >nul 2>&1

if %errorlevel% equ 0 (
    goto :ATIVA
) else (
    goto :INATIVA
)

:ATIVA
cls
color 0A
echo ========================================================
echo        STATUS ATUAL: [ ATIVO / LIGADO ]
echo ========================================================
echo  O minerador esta rodando em modo SILENCIOSO.
echo.
echo  Pressione [ENTER] para DESATIVAR e LIMPAR TUDO.
echo ========================================================
pause >nul

echo [ACAO] Removendo tarefa do Windows... > "%LOGFILE%"
schtasks /delete /tn "%TASK_NAME%" /f >> "%LOGFILE%" 2>&1

echo [ACAO] Apagando arquivos do sistema... >> "%LOGFILE%"
if exist "%SILENCER_VBS%" del "%SILENCER_VBS%"

echo [ACAO] Limpando lixo da pasta atual (Cleaning)... >> "%LOGFILE%"
:: AQUI ESTA A LIMPEZA QUE VOCE PEDIU:
if exist "%~dp0install_ghost.ps1" del "%~dp0install_ghost.ps1"
if exist "%~dp0install_vbs.ps1" del "%~dp0install_vbs.ps1"
if exist "%~dp0installer_temp.ps1" del "%~dp0installer_temp.ps1"

cls
echo [SUCESSO] Inicializacao Removida e Pasta Limpa.
timeout /t 3 >nul
exit

:INATIVA
cls
color 0C
echo ========================================================
echo        STATUS ATUAL: [ INATIVO / DESLIGADO ]
echo ========================================================
echo  Ao ativar, vamos configurar o modo Silencioso e
echo  limpar os arquivos de instalacao imediatamente.
echo.
echo  Pressione [ENTER] para ATIVAR.
echo ========================================================
pause >nul

echo [ENGENHARIA] Gerando Silenciador VBS...

:: --- GERAÇÃO DO ARQUIVO VBS (SISTEMA) ---
(
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.Run chr^(34^) ^& "%TARGET_SCRIPT%" ^& chr^(34^), 0
echo Set WshShell = Nothing
) > "%SILENCER_VBS%"

echo [ENGENHARIA] Configurando Agendador...

:: --- GERAÇÃO DO INSTALADOR TEMPORÁRIO ---
set "TEMP_PS=%~dp0install_clean.ps1"

(
echo $ErrorActionPreference = "Stop"
echo try {
echo     $Action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"%SILENCER_VBS%"'
echo     $Trigger = New-ScheduledTaskTrigger -AtLogOn -RandomDelay 00:00:15
echo     $Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
echo     $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
echo     Register-ScheduledTask -TaskName '%TASK_NAME%' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force
echo     Write-Host "SUCESSO"
echo } catch {
echo     Write-Host "ERRO: $_"
echo     exit 1
echo }
) > "%TEMP_PS%"

echo [ENGENHARIA] Executando e Limpando...
powershell -ExecutionPolicy Bypass -File "%TEMP_PS%" > "%LOGFILE%" 2>&1

:: --- LIMPEZA IMEDIATA ---
:: Assim que terminar de usar, deletamos o instalador para nao sujar sua pasta
if exist "%TEMP_PS%" del "%TEMP_PS%"
:: Removemos tambem o arquivo antigo se ele existir
if exist "%~dp0install_ghost.ps1" del "%~dp0install_ghost.ps1"

findstr "SUCESSO" "%LOGFILE%" >nul

if %errorlevel% equ 0 (
    cls
    color 0A
    echo [SUCESSO] Modo Fantasma Ativado!
    echo.
    echo Pasta limpa: Arquivos temporarios foram deletados.
    echo Pode reiniciar o PC.
) else (
    color 0C
    echo [ERRO] Falha ao criar a tarefa.
    echo Verifique boot_manager.log
)
pause