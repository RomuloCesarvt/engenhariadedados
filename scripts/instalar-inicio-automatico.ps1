# Instala (uma vez) uma tarefa do Windows que mantém o BI no ar: liga o motor (8001) e o painel (3001) ao entrar no Windows
# e confere a cada 10 minutos, religando o que tiver caído. Roda no seu usuário, sem administrador.
#
# Para instalar: clique com o botão direito neste arquivo > "Executar com o PowerShell".
# Para remover:  Unregister-ScheduledTask -TaskName 'BI Moura Leite - manter o sistema no ar' -Confirm:$false

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
$Inicio = Join-Path $PSScriptRoot 'iniciar-bi-local.ps1'
$Nome = 'BI Moura Leite - manter o sistema no ar'

$acao = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $Raiz `
  -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -NoBrowser' -f $Inicio)
$aoEntrar = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$aCada10 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 10)
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger @($aoEntrar, $aCada10) -Settings $config -Principal $principal `
  -Description 'Liga o motor (8001) e o painel (3001) do BI ao entrar no Windows e religa se caírem.' -Force | Out-Null

Write-Host "Pronto. A tarefa '$Nome' foi criada: o BI passa a ligar sozinho ao entrar no Windows e a religar se cair."
Read-Host 'Pressione Enter para fechar'
