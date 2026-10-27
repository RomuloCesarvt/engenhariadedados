@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-bi-local.ps1"
if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar o BI. Consulte os arquivos em .runtime.
  pause
)
