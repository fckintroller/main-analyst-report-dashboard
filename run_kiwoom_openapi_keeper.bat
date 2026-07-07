@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

set "KIWOOM_PY=%~dp0.venv-kiwoom32\Scripts\python.exe"
if not exist "%KIWOOM_PY%" (
  echo [ERROR] 32bit Kiwoom Python venv not found: %KIWOOM_PY%
  exit /b 1
)
if exist env.bat call env.bat >nul 2>nul
if not exist "logs" mkdir "logs"
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_STAMP=%%I"
set "LOG_FILE=%~dp0logs\kiwoom_openapi_keeper_!RUN_STAMP!.log"

set "FORCE_GUARD="
set "DRY_RUN=0"
set "KEEPER_UNTIL=1545"
for %%A in (%*) do (
  if /I "%%~A"=="--force" set "FORCE_GUARD=--force"
  if /I "%%~A"=="--dry-run" set "DRY_RUN=1"
  if /I "%%~A"=="--24h" set "KEEPER_UNTIL=2359"
  if /I "%%~A"=="--until-midnight" set "KEEPER_UNTIL=2359"
  if /I "%%~A"=="--market-hours" set "KEEPER_UNTIL=1545"
)

echo [START] %DATE% %TIME% Kiwoom OpenAPI keeper %* > "!LOG_FILE!"
if "!DRY_RUN!"=="1" (
  echo [DRY-RUN] Running keeper demo only; no Kiwoom login/COM call. >> "!LOG_FILE!"
  "%KIWOOM_PY%" scripts\01_collect\kiwoom_openapi_keeper.py --demo --demo-loops 1 --heartbeat-seconds 0.1 >> "!LOG_FILE!" 2>&1
  set "RC=!ERRORLEVEL!"
  type "!LOG_FILE!"
  exit /b !RC!
)

python -X utf8 scripts\01_collect\kiwoom_launch_guard.py --ttl-minutes 25 --once-per-day --reason openapi_keeper !FORCE_GUARD! >> "!LOG_FILE!" 2>&1
set "GUARD_RC=!ERRORLEVEL!"
if "!GUARD_RC!"=="10" (
  echo [SKIP] %DATE% %TIME% Kiwoom keeper launch suppressed by daily guard; not restarting existing/previous session. >> "!LOG_FILE!"
  type "!LOG_FILE!"
  exit /b 0
)
if not "!GUARD_RC!"=="0" (
  echo [END] %DATE% %TIME% Kiwoom keeper guard failed rc=!GUARD_RC! >> "!LOG_FILE!"
  type "!LOG_FILE!"
  exit /b !GUARD_RC!
)

"%KIWOOM_PY%" scripts\01_collect\kiwoom_openapi_keeper.py --until !KEEPER_UNTIL! --heartbeat-seconds 60 %* >> "!LOG_FILE!" 2>&1
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
  echo [END] %DATE% %TIME% Kiwoom OpenAPI keeper FAILED rc=!RC! >> "!LOG_FILE!"
  type "!LOG_FILE!"
  exit /b !RC!
)

echo [END] %DATE% %TIME% Kiwoom OpenAPI keeper OK >> "!LOG_FILE!"
type "!LOG_FILE!"
exit /b 0
