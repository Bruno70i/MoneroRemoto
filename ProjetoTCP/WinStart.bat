@echo off
:: Verifica se o arquivo está sendo executado com privilégios administrativos
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

:: Se não tiver privilégios administrativos, solicita elevação
if '%errorlevel%' NEQ '0' (
    echo Solicitando privilégios administrativos...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    set params = %*:"=""
    echo UAC.ShellExecute "cmd.exe", "/c %~s0 %params%", "", "runas", 1 >> "%temp%\getadmin.vbs"

    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
pushd "%CD%"
CD /D "%~dp0"

:: Executa o script PowerShell com privilégios administrativos
powershell -ExecutionPolicy Bypass -Command "& { $taskName = 'SystemOutCache'; $taskExists = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue; if (-not $taskExists) { schtasks /create /tn 'SystemOutCache' /tr 'C:\Windows\SystemOut\SystemOutCache.exe' /sc onstart /ru SYSTEM /rl HIGHEST; if ($?) { Write-Host 'Tarefa ''$taskName'' criada com sucesso.' } else { Write-Host 'Falha ao criar a tarefa ''$taskName''. Verifique os erros.' } } else { Write-Host 'A tarefa ''$taskName'' já existe. Nenhuma ação necessária.' } }"