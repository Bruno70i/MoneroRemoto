@echo off
:: =========================================================
:: SCRIPT DE ATUALIZAÇÂO REMOTA (Shadow Updater)
:: =========================================================
:: Uso:
:: 1. PUT SystemOutCache.exe (com nome temporario, ex: Update_Cache.exe)
:: 2. PUT Update.bat
:: 3. EXEC Update.bat
:: =========================================================

cd /d "C:\Windows\SystemOut"

echo [1/4] Parando servico...
sc stop "SystemOutCache"
:: Aguarda 5 segundos para liberar o arquivo
timeout /t 5 /nobreak >nul

echo [2/4] Aplicando atualizacao...
:: Se voce subiu como "SystemOutCache.exe" direto na pasta UPLOAD, ajuste aqui:
:: Ex: copy /y "UPLOAD\SystemOutCache.exe" "SystemOutCache.exe"

if exist "UPLOAD\SystemOutCache.exe" (
    copy /y "UPLOAD\SystemOutCache.exe" "SystemOutCache.exe"
    echo Arquivo copiado do UPLOAD.
    del "UPLOAD\SystemOutCache.exe"
) else (
    echo [ERRO] Novo executavel nao encontrado em UPLOAD\SystemOutCache.exe
    echo Certifique-se de dar PUT SystemOutCache.exe antes.
    exit /b 1
)

echo [3/4] Reiniciando servico...
sc start "SystemOutCache"

echo [4/4] Limpeza...
:: (Opcional) Se deletar este bat, o output do EXEC pode falhar. 
:: Melhor deixar ele aqui ou deletar na proxima.

echo [SUCESSO] Atualizacao concluida.
