@echo off
chcp 65001 > nul
echo ===================================================
echo 대한민국 베스트 애널리스트 대시보드 자동화 스케줄러 등록
echo ===================================================
echo.
echo 매일 밤 21:00에 최신 리포트를 수집하고
echo 실시간 주가 데이터와 함께 대시보드를 갱신하는
echo 백그라운드 작업을 윈도우 작업 스케줄러에 등록합니다.
echo.

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=python"

:: 실행할 배치 스크립트 임시 생성
set "RUNNER_SCRIPT=%PROJECT_DIR%run_automation.bat"
echo @echo off > "%RUNNER_SCRIPT%"
echo cd /d "%PROJECT_DIR%scripts" >> "%RUNNER_SCRIPT%"
echo echo [ETL] 파이프라인 일괄 실행 중... >> "%RUNNER_SCRIPT%"
echo %PYTHON_EXE% pipeline.py >> "%RUNNER_SCRIPT%"
echo exit >> "%RUNNER_SCRIPT%"

:: 기존 작업이 있다면 삭제
schtasks /delete /tn "AnalystDashboardUpdate" /f > nul 2>&1

:: 작업 스케줄러에 등록
schtasks /create /tn "AnalystDashboardUpdate" /tr "\"%RUNNER_SCRIPT%\"" /sc daily /st 21:00 /f

echo.
if %errorlevel% equ 0 (
    echo [성공] 매일 21:00 자동 업데이트 스케줄이 정상적으로 등록되었습니다.
    echo 시스템을 종료하지 않는 한, 21시마다 백그라운드에서 실행됩니다.
) else (
    echo [실패] 스케줄러 등록에 실패했습니다. 관리자 권한으로 실행해 보세요.
)
echo.
pause
