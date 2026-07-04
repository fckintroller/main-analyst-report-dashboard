@echo off
chcp 65001 >nul
setlocal
cd /d "C:\claude cowork\01_projects\Anal_reports"
if exist env.bat call env.bat >nul 2>nul

rem --- 수집 전 현재 월 캡처 ---
set PREV_MONTH=none
if exist "data\raw\trade_import_export\latest_trade_import_export_analysis.json" (
    for /f "delims=" %%i in ('python -X utf8 -c "import json; d=json.load(open(r'data/raw/trade_import_export/latest_trade_import_export_analysis.json',encoding='utf-8')); print(str(d.get('ecos',{{}}).get('latest',{{}}).get('month') or d.get('customs',{{}}).get('latest_month') or 'none'))"') do set PREV_MONTH=%%i
)
echo [PRE] 기존 데이터 월: %PREV_MONTH%

echo [1/4] KOSIS 무역 수집 (수출/수입/무역수지 시계열)...
python -X utf8 scripts\01_collect\collect_kr_trade_kosis.py
if %errorlevel% neq 0 echo [WARN] KOSIS 무역 수집 실패 (계속 진행)

echo [2/4] ECOS+관세청 수출입 분석 수집 (품목별 단가/물량 분해)...
python -X utf8 scripts\01_collect\collect_trade_import_export_analysis.py
if %errorlevel% neq 0 (
    echo [ERROR] 관세청 수출입 수집 실패
    exit /b 1
)

echo [3/4] 무역수지 팩터 빌드...
python -X utf8 scripts\03_analyze\build_trade_balance_kr_us_factors.py
if %errorlevel% neq 0 echo [WARN] 무역수지 팩터 실패 (계속 진행)

echo [4/4] 웹 데이터 재생성...
python -X utf8 scripts\03_analyze\export_web_data.py
if %errorlevel% neq 0 (
    echo [ERROR] 웹 데이터 재생성 실패
    exit /b 1
)

rem --- 수집 후 신규 월 확인 ---
set NEW_MONTH=none
for /f "delims=" %%i in ('python -X utf8 -c "import json; d=json.load(open(r'data/raw/trade_import_export/latest_trade_import_export_analysis.json',encoding='utf-8')); print(str(d.get('ecos',{{}}).get('latest',{{}}).get('month') or d.get('customs',{{}}).get('latest_month') or 'none'))"') do set NEW_MONTH=%%i
echo [POST] 신규 데이터 월: %NEW_MONTH%

rem --- 신규 월 감지 시 Discord 알림 ---
if not "%NEW_MONTH%"=="none" (
    if not "%NEW_MONTH%"=="%PREV_MONTH%" (
        echo [Discord] 신규 데이터 감지: %PREV_MONTH% ^-^> %NEW_MONTH%
        python -X utf8 scripts\05_notify\notify_trade_import_export.py --prev-month %PREV_MONTH% --new-month %NEW_MONTH%
        if %errorlevel% neq 0 echo [WARN] Discord 알림 전송 실패 (계속 진행)
    ) else (
        echo [Discord] 신규 데이터 없음 (%NEW_MONTH%), 알림 생략
    )
)

echo 관세청 수출입 수집 완료.
endlocal
exit /b 0
