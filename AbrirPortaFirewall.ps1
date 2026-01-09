# Verifica e cria a regra de entrada
if (-not (Get-NetFirewallRule -DisplayName "SystemOutPort In" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "SystemOutPort In" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 7722
    Write-Host "Regra de entrada 'SystemOutPort In' criada com sucesso."
} else {
    Write-Host "A regra de entrada 'SystemOutPort In' já existe. Nenhuma ação necessária."
}

# Verifica e cria a regra de saída
if (-not (Get-NetFirewallRule -DisplayName "SystemOutPort Out" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "SystemOutPort Out" -Direction Outbound -Action Allow -Protocol TCP -LocalPort 7722
    Write-Host "Regra de saída 'SystemOutPort Out' criada com sucesso."
} else {
    Write-Host "A regra de saída 'SystemOutPort Out' já existe. Nenhuma ação necessária."
}