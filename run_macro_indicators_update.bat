@echo off
chcp 65001 >nul
setlocal
cd /d "C:\claude cowork\01_projects\Anal_reports"
if exist env.bat call env.bat >nul 2>nul

echo [1/8] 매크로 원천 지표 수집 (지수/환율/원자재/FRED/ECOS)...
python -X utf8 scripts\01_collect\01_macro.py
if %errorlevel% neq 0 (
    python -X utf8 scripts\05_notify\notify_batch.py fail "매크로 지표 최신화" "1/8 01_macro 실패 (exit %errorlevel%)"
    exit /b %errorlevel%
)

echo [2/8] 글로벌 주가지수 수집...
python -X utf8 scripts\01_collect\collect_global_indices_once.py
if %errorlevel% neq 0 (
    python -X utf8 scripts\05_notify\notify_batch.py fail "매크로 지표 최신화" "2/8 global indices 실패 (exit %errorlevel%)"
    exit /b %errorlevel%
)

echo [3/9] 비철금속 지표 수집...
python -X utf8 scripts\01_collect\collect_nonferrous_metals_once.py
if %errorlevel% neq 0 (
    echo [WARN] 비철금속 지표 수집 실패 (계속 진행)
)

echo [4/9] 곡물 지표 수집...
python -X utf8 scripts\01_collect\collect_grains_once.py
if %errorlevel% neq 0 (
    echo [WARN] 곡물 지표 수집 실패 (계속 진행)
)

echo [5a/9] raw CSV -> SQLite 적재 (ADR 수집 전에 먼저 실행)...
python -X utf8 scripts\02_store\load_to_db.py
if %errorlevel% neq 0 (
    python -X utf8 scripts\05_notify\notify_batch.py fail "매크로 지표 최신화" "5/9 DB 적재 실패 (exit %errorlevel%)"
    exit /b %errorlevel%
)

echo [5b/9] ADR 일별 갱신 (DB 적재 후 최신 데이터 append + CSV sync)...
python -X utf8 scripts\01_collect\collect_adr_daily.py
if %errorlevel% neq 0 (
    echo [WARN] ADR 갱신 실패 (계속 진행)
)

echo [6/9] 퀀트 매크로 long/factor 테이블 갱신...
python -X utf8 scripts\01_collect\collect_quant_macro_indicators_once.py
if %errorlevel% neq 0 (
    python -X utf8 scripts\05_notify\notify_batch.py fail "매크로 지표 최신화" "6/9 quant macro 실패 (exit %errorlevel%)"
    exit /b %errorlevel%
)

echo [7/9] 매크로 스프레드 팩터 갱신...
python -X utf8 scripts\03_analyze\build_macro_spread_factors.py
if %errorlevel% neq 0 (
    python -X utf8 scripts\05_notify\notify_batch.py fail "매크로 지표 최신화" "7/9 macro spread 실패 (exit %errorlevel%)"
    exit /b %errorlevel%
)

echo [8/9] 시장 레짐/섹터 조정 팩터 갱신...
python -X utf8 scripts\03_analyze\build_market_regime_adjusted_signals.py
if %errorlevel% neq 0 (
    python -X utf8 scripts\05_notify\notify_batch.py fail "매크로 지표 최신화" "8/9 market regime 실패 (exit %errorlevel%)"
    exit /b %errorlevel%
)

echo [8b/9] ADR 갭 시그널 팩터 재빌드...
python -X utf8 scripts\03_analyze\build_adr_gap_signal_factors.py
if %errorlevel% neq 0 (
    echo [WARN] ADR 팩터 빌드 실패 (계속 진행)
)

echo [9/9] 웹 데이터 재생성...
python -X utf8 scripts\03_analyze\export_web_data.py
if %errorlevel% neq 0 (
    python -X utf8 scripts\05_notify\notify_batch.py fail "매크로 지표 최신화" "9/9 export 실패 (exit %errorlevel%)"
    exit /b %errorlevel%
)

python -X utf8 scripts\05_notify\notify_batch.py ok "매크로 지표 최신화 완료" "macro raw/DB/factor/web payload 갱신"
endlocal
exit /b 0
