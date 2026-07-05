@echo off
chcp 65001 >nul
setlocal
cd /d "C:\claude cowork\01_projects\Anal_reports"
if exist env.bat call env.bat >nul 2>nul

echo [0/13] KRX 시장 스냅샷 수집 (시가총액/기초지표/종목명)...
python -X utf8 scripts\01_collect\collect_krx_market_snapshot.py
if %errorlevel% neq 0 echo [WARN] KRX 스냅샷 수집 실패 (계속 진행)

echo [1/13] 섹터 ETF 수집...
python -X utf8 scripts\01_collect\collect_sector_etf_once.py
if %errorlevel% neq 0 echo [WARN] 섹터 ETF 실패 (계속 진행)

echo [2/13] 퀀트 매크로 지표 수집...
python -X utf8 scripts\01_collect\collect_quant_macro_indicators_once.py
if %errorlevel% neq 0 echo [WARN] 퀀트 매크로 실패 (계속 진행)

echo [2b/13] Naver DataLab 검색 트렌드 수집 (섹터/테마 관심도)...
python -X utf8 scripts\01_collect\collect_naver_datalab_once.py
if %errorlevel% neq 0 echo [WARN] DataLab 수집 실패 (계속 진행)

echo [3/13] 곡물 가격 수집...
python -X utf8 scripts\01_collect\collect_grains_once.py
if %errorlevel% neq 0 echo [WARN] 곡물 실패 (계속 진행)

echo [3b/13] 곡물 보조 (보리/수수) 수집...
python -X utf8 scripts\01_collect\collect_barley_sorghum_supplements_once.py
if %errorlevel% neq 0 echo [WARN] 보리/수수 수집 실패 (계속 진행)

echo [4/13] 비철금속 수집...
python -X utf8 scripts\01_collect\collect_nonferrous_metals_once.py
if %errorlevel% neq 0 echo [WARN] 비철금속 실패 (계속 진행)

echo [5/13] 투자자 수급 수집 (432종목)...
python -X utf8 scripts\01_collect\collect_stock_investor_trend_once.py --overwrite
if %errorlevel% neq 0 echo [WARN] 투자자 수급 실패 (계속 진행)

echo [5b/13] 공매도 잔고 수집 (월말 집계)...
python -X utf8 scripts\01_collect\collect_shorting_balance_once.py
if %errorlevel% neq 0 echo [WARN] 공매도 잔고 수집 실패 (계속 진행)

echo [6/13] DB 적재...
python -X utf8 scripts\02_store\load_to_db.py
if %errorlevel% neq 0 (
    echo [ERROR] DB 적재 실패 (exit %errorlevel%)
    exit /b %errorlevel%
)

echo [7/13] 월간 팩터 빌드...
python -X utf8 scripts\03_analyze\build_valuation_per_pbr_factors.py
python -X utf8 scripts\03_analyze\build_investor_flow_momentum_factors.py
python -X utf8 scripts\03_analyze\build_stock_price_momentum_factors.py
python -X utf8 scripts\03_analyze\build_roe_trend_factors.py
python -X utf8 scripts\03_analyze\build_macro_spread_factors.py
python -X utf8 scripts\03_analyze\build_credit_spread_kr_factors.py
python -X utf8 scripts\03_analyze\build_sector_etf_flow_factors.py
python -X utf8 scripts\03_analyze\build_futures_flow_factors.py
if %errorlevel% neq 0 echo [WARN] 선물 수급 팩터 빌드 실패 (계속 진행)

echo [7b/13] PPI/무역 최신 데이터 수집 (ECOS/KOSIS, 1개월 lag)...
python -X utf8 scripts\01_collect\collect_kr_ppi_ecos_full.py
if %errorlevel% neq 0 echo [WARN] PPI 수집 실패 (계속 진행)
python -X utf8 scripts\01_collect\collect_kr_trade_kosis.py
if %errorlevel% neq 0 echo [WARN] 무역 수집 실패 (계속 진행)
python -X utf8 scripts\01_collect\collect_trade_import_export_analysis.py
if %errorlevel% neq 0 echo [WARN] 관세청 수출입 분석 수집 실패 (계속 진행)
python -X utf8 scripts\03_analyze\build_ppi_inflation_cycle_kr_factors.py
if %errorlevel% neq 0 echo [WARN] PPI 팩터 빌드 실패 (계속 진행)
python -X utf8 scripts\03_analyze\build_trade_balance_kr_us_factors.py
if %errorlevel% neq 0 echo [WARN] 무역수지 팩터 빌드 실패 (계속 진행)

echo [7c/13] DART 내부자 거래 수집 (임원/주요주주 소유보고, ~3분)...
python -X utf8 scripts\01_collect\collect_dart_insider_trading_once.py
if %errorlevel% neq 0 echo [WARN] 내부자 거래 수집 실패 (계속 진행)

echo [7d/13] 미한 무역통계 수집 (FRED, 수출입/무역수지)...
python -X utf8 scripts\01_collect\collect_us_korea_trade_once.py
if %errorlevel% neq 0 echo [WARN] 미한 무역통계 수집 실패 (계속 진행)

echo [7e/13] 중국 매크로 수집 + 팩터 빌드 (FRED 수출입 + CSI300)...
python -X utf8 scripts\01_collect\collect_china_macro.py
if %errorlevel% neq 0 echo [WARN] 중국 매크로 수집 실패 (계속 진행)
python -X utf8 scripts\03_analyze\build_china_macro_factors.py
if %errorlevel% neq 0 echo [WARN] 중국 성장 팩터 빌드 실패 (계속 진행)

echo [8/13] ADR 갱신 + 일별 팩터 빌드...
python -X utf8 scripts\01_collect\collect_adr_daily.py
python -X utf8 scripts\03_analyze\build_adr_gap_signal_factors.py

echo [9/13] 애널리스트 목표주가 컨센서스 수집 (전종목, 최신 호환 파일)...
python -X utf8 scripts\01_collect\collect_analyst_target_price_once.py
if %errorlevel% neq 0 echo [WARN] 목표주가 수집 실패 (계속 진행)

echo [10/13] 애널리스트 목표주가/EPS 컨센서스 증분 누적...
python -X utf8 scripts\01_collect\collect_analyst_target_price_incremental.py --use-existing-latest
if %errorlevel% neq 0 echo [WARN] 목표주가 증분 누적 실패 (계속 진행)

echo [11/13] 컨센서스 리비전 팩터 빌드...
python -X utf8 scripts\03_analyze\build_consensus_revision_factors.py
if %errorlevel% neq 0 echo [WARN] 컨센서스 리비전 팩터 실패 (계속 진행)

echo [11b/13] DART 공시 이벤트 수집+팩터 빌드 (per-ticker kind=B+I, ~17분)...
python -X utf8 scripts\01_collect\collect_dart_disclosure_events.py
if %errorlevel% neq 0 echo [WARN] 공시 이벤트 수집 실패 (계속 진행)
python -X utf8 scripts\03_analyze\build_disclosure_event_factors.py
if %errorlevel% neq 0 echo [WARN] 공시 이벤트 팩터 빌드 실패 (계속 진행)

echo [12/13] 팩터 마스터 패널 빌드...
python -X utf8 scripts\03_analyze\build_factor_master_panel.py
if %errorlevel% neq 0 echo [WARN] 팩터 마스터 패널 실패 (계속 진행)

echo [12b/13] 팩터 IC 검증 리포트 빌드...
python -X utf8 scripts\03_analyze\build_factor_ic_report.py
if %errorlevel% neq 0 echo [WARN] 팩터 IC 리포트 실패 (계속 진행)

echo [13/13] 웹 데이터 재생성...
python -X utf8 scripts\03_analyze\export_web_data.py

echo 월간 파이프라인 완료.
endlocal
exit /b 0
