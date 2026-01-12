@echo off
setlocal
title SystemOut Install

:: 1. VERIFICAR PRIVILÉGIOS DE ADMINISTRADOR
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Solicitando permissoes de Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo [1/4] Aplicando Exclusao no Windows Defender...
powershell.exe -NoProfile -NonInteractive -Command "Add-MpPreference -ExclusionPath 'C:\Windows\SystemOut'" >nul 2>&1
echo      Exclusao aplicada em C:\Windows\SystemOut

echo.
echo [2/4] Preparando Arquivos...
:: Parar servico antes de mexer nos arquivos
echo      Parando servico antigo (se houver)...
sc stop SystemOutCache >nul 2>&1
timeout /t 2 /nobreak >nul

:: Verifica se existe o ZIP para extrair (caso o usuario use o metodo ZIP)
if exist "%~dp0SystemOut.zip" (
    echo      Extraindo SystemOut.zip para C:\Windows...
    powershell -command "Expand-Archive -Path '%~dp0SystemOut.zip' -DestinationPath 'C:\Windows' -Force"
    timeout /t 2 /nobreak >nul
) else (
    echo      [AVISO] SystemOut.zip nao encontrado. Pulando extracao.
    echo      (Certifique-se que o SystemOutCache.exe ja esta no local ou sera instalado agora)
)

echo.
echo [3/4] Instalando o Agente...

:: Copia e instala o executável
if exist "C:\Windows\SystemOut\SystemOutCache.exe" (
    echo      Executavel encontrado em C:\Windows\SystemOut. Instalando com Privilegios Admin...
    timeout /t 1 /nobreak >nul
    powershell -Command "Start-Process 'C:\Windows\SystemOut\SystemOutCache.exe' -Verb RunAs -Wait"
) else if exist "%~dp0SystemOutCache.exe" (
    echo      Executavel encontrado na pasta local. Instalando...
    powershell -Command "Start-Process '%~dp0SystemOutCache.exe' -Verb RunAs -Wait"
) else (
    echo      [ERROR] SystemOutCache.exe nao encontrado apos extracao!
    echo      Verifique se o ZIP contem a pasta 'SystemOut' na raiz.
    dir "C:\Windows\SystemOut"
)

echo.
echo.
echo [4/4] Iniciando Servico SystemOut...
:: Inicia o Servico do Agente
sc start SystemOutCache >nul 2>&1

echo.
echo ========================================================
echo   INSTALACAO E INICIALIZACAO CONCLUIDAS
echo ========================================================
echo   Fechando em 5 segundos...
timeout /t 5 /nobreak >nul
