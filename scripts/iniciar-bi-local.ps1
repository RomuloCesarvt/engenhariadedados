param(
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Dashboard = Join-Path $Root 'dashboard'
$Runtime = Join-Path $Root '.runtime'
$BiUrl = 'http://127.0.0.1:3001'
$BiIdentityUrl = 'http://127.0.0.1:3001/api/instance'
$EngineUrl = 'http://127.0.0.1:8001/'

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

function Get-JsonResponse([string]$Url) {
  try {
    return Invoke-RestMethod -Uri $Url -TimeoutSec 2
  } catch {
    return $null
  }
}

function Test-TcpPort([int]$Port) {
  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $result = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
    if (-not $result.AsyncWaitHandle.WaitOne(1000)) { return $false }
    $client.EndConnect($result)
    return $true
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Wait-For([string]$Url, [scriptblock]$Validator, [int]$Seconds = 45) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  do {
    $response = Get-JsonResponse $Url
    if ($response -and (& $Validator $response)) { return $response }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  throw "O servico nao respondeu em $Url dentro de $Seconds segundos."
}

$engine = Get-JsonResponse $EngineUrl
if (-not ($engine -and $engine.status -eq 'ok' -and $engine.message -like '*Lead Recon Engine*')) {
  if (Test-TcpPort 8001) {
    throw 'A porta 8001 esta ocupada por outro sistema. A engine do BI nao foi substituida.'
  }

  $pythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
    (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
  ) | Where-Object { $_ -and (Test-Path $_) }

  $python = $pythonCandidates | Select-Object -First 1
  if (-not $python) {
    throw 'Python nao encontrado. Instale o Python ou ajuste scripts/iniciar-bi-local.ps1.'
  }

  Start-Process -FilePath $python `
    -ArgumentList @('-m', 'uvicorn', 'engine.api:app', '--host', '127.0.0.1', '--port', '8001') `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Runtime 'engine.out.log') `
    -RedirectStandardError (Join-Path $Runtime 'engine.err.log')

  Wait-For $EngineUrl { param($r) $r.status -eq 'ok' -and $r.message -like '*Lead Recon Engine*' } | Out-Null
}

$identity = Get-JsonResponse $BiIdentityUrl
if (-not ($identity -and $identity.appId -eq 'moura-leite-bi')) {
  if (Test-TcpPort 3001) {
    throw 'A porta 3001 esta ocupada por outro sistema. O BI Moura Leite nao foi substituido.'
  }

  $npm = Get-Command npm.cmd -ErrorAction Stop | Select-Object -ExpandProperty Source -First 1
  Start-Process -FilePath $npm `
    -ArgumentList @('run', 'dev') `
    -WorkingDirectory $Dashboard `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Runtime 'dashboard.out.log') `
    -RedirectStandardError (Join-Path $Runtime 'dashboard.err.log')

  Wait-For $BiIdentityUrl { param($r) $r.appId -eq 'moura-leite-bi' } -Seconds 60 | Out-Null
}

Write-Host "Moura Leite BI ativo em $BiUrl" -ForegroundColor Green
if (-not $NoBrowser) {
  Start-Process $BiUrl
}
