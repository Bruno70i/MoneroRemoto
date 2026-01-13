@echo off
setlocal EnableDelayedExpansion

:: ==========================================
:: 0. AUTO-ELEVACAO (Rodar como Admin Sozinho)
:: ==========================================
:: Se nao for admin, relanca pedindo permissao
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Solicitando permissao de Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Garante que estamos na pasta do arquivo .bat
cd /d "%~dp0"

:: ==========================================
:: CONFIGURACOES (SEU ID AQUI)
:: ==========================================
set NETWORK_ID=a09acf02334a8115
set MSI_FILE=ZeroTier One.msi


echo =========================================
echo   1. INSTALACAO ZEROTIER
echo =========================================
echo.

if not exist "%MSI_FILE%" (
    echo [ERRO] O arquivo "%MSI_FILE%" nao foi encontrado nesta pasta!
    echo O script e o instalador devem estar juntos.
    pause
    exit
)

echo [ETAPA 01] Verificando instalacao...
if not exist "C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" (
    echo Instalando ZeroTier... (Aguarde)
    start /wait msiexec /i "%MSI_FILE%" /quiet /qn
    timeout /t 6 /nobreak >nul
) else (
    echo [INFO] ZeroTier ja instalado.
)

:: ==========================================
:: 2. ENTRAR NA REDE
:: ==========================================
echo.
echo [ETAPA 02] Entrando na rede %NETWORK_ID%...
call "C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" join %NETWORK_ID% >nul

:: ==========================================
:: 3. LOOP DE VALIDACAO (ARQUIVO TEMPORARIO)
:: ==========================================
:CHECK_STATUS
echo.
echo ---------------------------------------------------
echo [AGUARDANDO AUTORIZACAO NO SITE]
echo Va em my.zerotier.com e autorize o dispositivo.
echo ---------------------------------------------------

:: 1. Salva a lista de redes num arquivo temporario
call "C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" listnetworks > status.tmp

:: 2. Procura SEU ID dentro do arquivo
findstr "%NETWORK_ID%" status.tmp > id_found.tmp

:: 3. Se o arquivo id_found estiver vazio, o join falhou ou ID ta errado
for %%A in (id_found.tmp) do if %%~zA==0 (
    echo [ERRO] O ID da rede nao aparece na lista. Tentando join novamente...
    call "C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" join %NETWORK_ID% >nul
    timeout /t 7 >nul
    goto CHECK_STATUS
)

:: 4. Agora verifica se tem "OK" na linha do seu ID
findstr "OK" id_found.tmp >nul
if %errorLevel% equ 0 (
    echo.
    echo [SUCESSO] Status OK detectado!
    del status.tmp
    del id_found.tmp
    goto FIREWALL
) else (
    echo [STATUS ATUAL]: ACCESS_DENIED ou REQUESTING
    type id_found.tmp
    echo.
    echo Tentando novamente em 5 segundos...
    timeout /t 5 >nul
    goto CHECK_STATUS
)

:: ==========================================
:: 4. FIREWALL
:: ==========================================
:FIREWALL
echo.
echo [ETAPA 03] Configurando Firewall...
powershell -ExecutionPolicy Bypass -Command "Get-NetConnectionProfile | Where-Object { $_.InterfaceAlias -like '*ZeroTier*' } | Set-NetConnectionProfile -NetworkCategory Private"
echo [OK] Firewall Configurado.

:: ==========================================
:: 5. FIM
:: ==========================================
echo.
echo =========================================
echo      INSTALACAO CONCLUIDA!
echo =========================================
echo Fechando em 10 segundos...
timeout /t 10