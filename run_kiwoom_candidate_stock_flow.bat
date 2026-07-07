@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

set "KIWOOM_PY=%~dp0.venv-kiwoom32\Scripts\python.exe"
if not exist "%KIWOOM_PY%" (
  echo [ERROR] 32bit Kiwoom Python venv not found: %KIWOOM_PY%
  exit /b 1
)

if not exist "logs" mkdir "logs"
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_STAMP=%%I"
set "LOG_FILE=%~dp0logs\kiwoom_candidate_stock_flow_!RUN_STAMP!.log"

echo [START] %DATE% %TIME% Kiwoom candidate stock flow > "!LOG_FILE!"
for /f %%I in ('powershell.exe -NoProfile -Command "(Get-Date).DayOfWeek"') do set "DOW=%%I"
for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format HHmm"') do set "NOW_HHMM=%%I"
if /I "!DOW!"=="Saturday" goto SKIP_MARKET_CLOSED
if /I "!DOW!"=="Sunday" goto SKIP_MARKET_CLOSED
if !NOW_HHMM! LSS 0900 goto SKIP_MARKET_CLOSED
if !NOW_HHMM! GTR 1535 goto SKIP_MARKET_CLOSED

"%KIWOOM_PY%" scripts\01_collect\collect_kiwoom_candidate_stock_flow_once.py --no-login --fail-if-unavailable --max-tickers 80 --max-watch 40 %* >> "!LOG_FILE!" 2>&1
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
  echo [END] %DATE% %TIME% Kiwoom candidate stock flow FAILED rc=!RC! >> "!LOG_FILE!"
  type "!LOG_FILE!"
  exit /b !RC!
)

echo [END] %DATE% %TIME% Kiwoom candidate stock flow OK >> "!LOG_FILE!"
type "!LOG_FILE!"
exit /b 0

:SKIP_MARKET_CLOSED
echo [SKIP] %DATE% %TIME% market closed; Kiwoom candidate stock flow is market-hours only 09:00-15:35 KST, weekdays. >> "!LOG_FILE!"
type "!LOG_FILE!"
exit /b 0
