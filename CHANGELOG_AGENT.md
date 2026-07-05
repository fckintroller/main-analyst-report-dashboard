# Agent Change Log — Anal_reports

목적: Claude/Hermes/기타 AI agent가 `Anal_reports`에서 수행한 파일 변경, 생성, 검증 결과를 공유합니다.

---

## 2026-07-05 (13차) - Claude
- Task: run_monthly.bat 신규 스크립트 3종 추가
- Changed:
  - `run_monthly.bat` — [7/13] 블록에 `build_futures_flow_factors.py` 추가; [7e/13] 신규 단계로 `collect_china_macro.py` + `build_china_macro_factors.py` 추가
- Verification:
  - 파일 내용 확인: [7e/13] 단계 및 [7] 내 선물 팩터 라인 정상 삽입 확인
- Note:
  - `build_futures_flow_factors.py`: money_flow_futures_trend 데이터가 누적될수록 z-score 의미 있어짐 (현재 10행, MIN_ZSCORE_OBS=20 미충족 → NaN 정상)
  - `collect_china_macro.py`: FRED China exports는 약 2개월 lag (최신 2026-04), CSI300은 당일 데이터

## 2026-07-05 (12차) - Claude
- Task: 신규 데이터 3종 구축 (공매도 통합/선물수급 팩터/중국 경기 팩터)
- Changed:
  - **신규** `scripts/01_collect/collect_china_macro.py`
    - FRED XTEXVA01CNM667S(중국수출) + XTIMVA01CNM667S(중국수입) 수집, max=2026-04-01
    - yfinance 000300.SS(CSI300) 수집, max=2026-07-03
    - DB: macro_china_exports(196행), macro_china_imports(196행), macro_csi300_daily(1288행)
  - **신규** `scripts/03_analyze/build_china_macro_factors.py`
    - 중국 수출 YoY 12M z-score → china_export_score
    - CSI300 월간수익률 6M z-score → csi300_momentum_score
    - 평균 → china_growth_score (현재 max=2026-07-01, 수출은 2026-04까지)
    - DB: factor_china_macro_month(199행)
  - **신규** `scripts/03_analyze/build_futures_flow_factors.py`
    - money_flow_futures_trend에서 외국인 선물 순매수 20일 누적 → 60일 z-score → flow_score
    - DB: factor_futures_flow_daily(10행), factor_futures_flow_month(2행)
    - ⚠️ money_flow_futures_trend 현재 11행 (초기 상태) — 데이터 쌓이면 자동 작동
  - **수정** `scripts/03_analyze/build_factor_master_panel.py`
    - TABLE_SPECS에 "shorting"(factor_shorting_month) 추가
    - _base_monthly_panel() / _merge_monthly()에 "shorting" 추가
    - build_factor_master_panel()에 short_score = 1 - shorting_pressure_score 계산 추가
    - build_source_staleness_report() specs에 shorting 추가 (allowed_lag_days=45)
    - ordered 컬럼에 short_score, shorting_pressure_score, balance_ratio 등 추가
    - 재실행: factor_master_month 15374행 정상 (공매도 통합 확인)
  - **수정** `scripts/03_analyze/export_web_data.py`
    - _build_macro_factor_payload()에 china_macro_month / futures_flow_daily 추가
  - `web/quant_data.js` 재생성 완료
- Verified:
  - collect_china_macro.py: FRED 2종 + yfinance CSI300 정상 수집
  - build_china_macro_factors.py: 199행 적재, china_growth_score max=2026-07-01
  - build_futures_flow_factors.py: 10행 (초기 데이터 부족으로 z-score NaN — 정상)
  - build_factor_master_panel.py: 15374행, source_staleness 8행(shorting 포함)
  - export_web_data.py: quant_data.js 정상 생성 (macro_factors.china_macro_month 포함)
- 주의:
  - 선물 수급 z-score: money_flow_futures_trend가 현재 11행 (최소 20행 필요)
    → 배치가 쌓이면 자동 계산됨
  - 중국 수출 데이터: FRED XTEXVA01CNM667S max=2026-04-01 (2개월 lag)
    → 2026-05~07 기간은 CSI300 단독으로 china_growth_score 계산 중
  - factor_master_panel의 short_score는 composite_score에 미반영 (별도 참조 컬럼)

## 2026-07-05 (11차) - Claude
- Task: 회귀분석 신뢰도 개선 A~C (stale 3→0, signal_confidence low→high)
- 배경: build_regression_analysis.py의 3개 입력(credit/export/inflation)이 최신 기간에 NaN → stale_penalty 15%, confidence=low
- Changed:
  - `scripts/03_analyze/build_credit_spread_kr_factors.py`
    - [A] credit_score: BBB 데이터 lag 기간에 AA z-score fallback 적용
    - 결과: credit_score 2026-07-01 = 0.287 (기존 NULL)
  - `scripts/03_analyze/build_ppi_inflation_cycle_kr_factors.py`
    - [C] T5YIFR_PATH 상수 추가 (data/raw/macro/macro_indices/T5YIFR.csv)
    - PPI max(2026-05-01) 이후 2개월 → T5YIFR(미국 5년 기대인플레이션) 월말값으로 행 확장
    - 결과: inflation_momentum_score 2026-06-01=0.500, 2026-07-01=0.518 추가
  - `scripts/03_analyze/build_trade_balance_kr_us_factors.py`
    - [B] KOSIS max(2026-05-01) 이후 → fx/soxx proxy 평균으로 행 확장
      - proxy = 0.5*(1-won_strength_score) + 0.5*semi_momentum_score
      - factor_fx_usdkrw_month + factor_soxx_semicycle_month 사용
    - 결과: export_momentum_score 2026-06-01=0.610, 2026-07-01=0.470 추가
- Verified:
  - py_compile OK (3개 파일)
  - build_regression_analysis.py 재실행: stale_inputs=[] / stale_penalty=0.0 / signal_confidence="high"
  - export_web_data.py 재실행: quant_data.js 정상 생성
  - quant_data.js market_timing: signal_confidence="high", stale_penalty=0.0, pred_period=2026-07-01
- 주의:
  - B/C는 proxy 기반(대리변수)이므로 실제 KOSIS/ECOS 공표 시 정확도 향상
  - T5YIFR은 미국 기대인플레이션 → 한국 PPI와 방향 일치하나 레벨 차이 있음 (trend 방향 참고용)
  - 수출 proxy는 원화강세+SOXX 평균 → KOSIS 공표(7월 말)로 자동 교체됨

## 2026-07-04 (10차) - Claude
- Task: Discord 종목 추천 일별 팩터 혼합 (A방식)
- 배경: score_base_5factor가 월간 팩터 5종 평균이라 한 달 내내 순위 불변 → 사용자 피드백
- Changed:
  - `scripts/05_notify/notify_discord.py` 전면 재작성
    - `load_daily_factors()`: 3개 일별 스냅샷 CSV 로드
      - `minute_tick_snapshot.csv` → `minute_tick_score` (당일 체결강도)
      - `target_price_snapshot.csv` → `target_price_score` (타겟가격 괴리)
      - `news_sentiment_snapshot.csv` → `news_sentiment_score` (뉴스 감성)
    - `compute_daily_score()`: 가중 합산 산식
      - score_daily_adjusted = 0.60×base + 0.15×tick + 0.15×tp + 0.10×news
      - 일별 팩터 없는 종목은 해당 가중치를 base에 재배분 (정규화)
    - `get_top_candidates()`: score_daily_adjusted 기준 Top N 정렬
    - `build_stock_embed()`: "⚡ 오늘 일별 팩터" 필드 추가 (체결강도/타겟가격 표시)
    - `build_header_embed()`: 일별 반영 종목 수 표시
- Verified:
  - py_compile OK
  - 2766종목 로드, 체결강도 397종 · 타겟가격 613종 · 뉴스감성 432종 반영
  - 기존 순위(삼성전자우>롯데에너지>가온전선) → 조정 후(삼성전자우>가온전선>롯데에너지) 변동 확인
- 주의: 체결강도는 당일 장중 수집(08:55~15:45)이 선행되어야 정확. 미수집 시 해당 가중치 base에 재배분

## 2026-07-04 (9차) - Claude
- Task: 브라우저 빈 데이터 전체 점검 및 WTI/Gold 차트 복원
- Changed:
  - `scripts/03_analyze/export_web_data.py`
    - `_records_from_csv()` 수정: `Unnamed: 0` 컬럼을 `Date`로 표준화
      - WTI.csv / Gold.csv 등 pandas 인덱스 컬럼이 없는 CSV에서 발생하던 문제
      - quant_ui.js가 `createLineChart(..., "Date", "Close")` 로 날짜키 "Date"를 기대하는데 실제 컬럼이 "Unnamed: 0"이어서 차트 빈 상태
    - `_compute_derived_macro()` 섹션 12: worldbank 비철금속 데이터 → `stooq_nonferrous_metals_latest` 생성 (Aluminum/Copper/Lead/Nickel/Tin/Zinc 6종, MoM 변화율 포함)
    - `_compute_derived_macro()` 섹션 13: 글로벌 지수 일별 90일 → `global_indices_daily` 생성 (1656 rows)
- Re-ran: `python scripts/03_analyze/export_web_data.py`
- Verified (JS 직접 확인):
  - macro.WTI: 4151행, 날짜키 "Date" ✓
  - macro.Gold: 4150행, 날짜키 "Date" ✓
  - macro.DXY: 2514행 ✓
  - 차트 컨테이너별 canvas 수:
    - macro-commodity-charts: 3 (DXY/WTI/Gold)
    - macro-leading-cli-charts: 9, sentiment: 3, derived: 4, naver: 6
    - macro-rates-kor-charts: 9, dynamic: 1
    - macro-global-charts: 2 (M2/WALCL)
    - macro-industry-trends-charts: 5, monthly: 5
    - quant-sector-momentum-charts: 4
    - trade-trend-charts: 2
  - 비철금속 테이블: Aluminum 3,439$/t -6.19%, Copper 13,552$/t +0.07% 등 6종 ✓
  - 경제 지표 캘린더: 2026-07 FOMC/CPI 일정 표시 ✓
  - 회귀 분석 신호: 테이블 정상, 신뢰도 경고 표시 ✓
- 주의: 스크린샷이 chart.js 렌더링 중 timeout 발생 (JS 응답은 정상, 렌더러 busy 현상)

## 2026-07-03 (8차) - Claude
- Task: 품목별 수출 단가/물량 분해 테이블 — sub-item MoM 추가 (7차 YoY에 이어)
- Changed:
  - `scripts/01_collect/collect_trade_import_export_analysis.py`
    - `agg_customs()` sub-item YoY 블록에 MoM 계산 추가
    - `pm_month=yyyymm_add(row['month'],-1)` 전월 인덱스 → `pm_hs` 매칭
    - `export_usd_mom_pct`, `import_usd_mom_pct` 필드 주입
  - `web/quant_ui.js`
    - top_items 서브행에 MoM 컬럼(`물량 YoY` 위치 재사용) 추가, `+xx.x% MoM` 형식 + 색상 코딩
    - 수입 셀 colspan 3→2 로 축소
- Re-ran: `collect_trade_import_export_analysis.py` + `export_web_data.py`
- Verified (브라우저 확인):
  - 디램 YoY +409.1% / MoM +23.6%, 복합구조칩 +140.1% / +17.9%, 모노리식 -3.2% / +1.0%
  - 전 품목(승용차·석유·선박·통신기기·축전지·폴리에스터 등) MoM 정상 표시
- 주의: 최초 월(202407)은 전월 데이터 없어 MoM null → "–" 표시

## 2026-07-03 (7차) - Claude
- Task: 품목별 수출 단가/물량 분해 테이블 — sub-item YoY 추가
- Changed:
  - `scripts/01_collect/collect_trade_import_export_analysis.py`
    - `agg_customs()` 수정: top_items `[:3]` 제한을 YoY 계산 이후로 이동
    - group-level MoM/YoY 루프 다음에 sub-item YoY 블록 추가:
      `hs_by_month` 인덱스(월→{hs_code→item}) 구성 → 전년동월 hs_code 매칭 → `export_usd_yoy_pct`, `import_usd_yoy_pct` 필드 주입
    - `row['top_items'] = row['top_items'][:3]` 은 YoY 계산 완료 후 적용
  - `web/quant_ui.js`
    - top_items 서브행 렌더링 수정: 수출 YoY 컬럼(`금액 YoY`)에 색상 코딩 + 수입 옆에 YoY % 병기
    - 예: `└ 디램  $11.4B  +409.1%  수입 $1.1B +56.8%`
- Re-ran: `collect_trade_import_export_analysis.py` + `export_web_data.py`
- Verified (JS innerText 확인):
  - 반도체/집적회로 HS8542: 디램 +409.1%, 복합구조칩 +140.1%, 모노리식 -3.2%
  - 수입 YoY 병기 정상 (디램 수입 +56.8%, 복합구조칩 수입 +221.8%, 모노리식 수입 +21.3%)
- 주의: 1년치 데이터 없는 최초 12개월(202407~202506)은 YoY null → "–" 표시

## 2026-07-03 (6차) - Claude
- Task: 수출입 패널 4~6번 개선
- Changed:
  - `web/quant_ui.js`
    - 차트 4개 → 2개: MoM·가격지수 차트 제거. 남은 차트 1·2 높이 220→300px
    - top_items sub-item 이름 28자 초과 시 "…" truncate + `title` 속성으로 전체 이름 hover 표시
  - `web/index.html`
    - 섹션 순서 변경: 품목별 분해 ↔ ECOS 월별 테이블 스왑 → 차트→ECOS 테이블→품목별 분해 순
- Verified: node --check PASS, 브라우저 확인 (차트 2개 나란히 300px, ECOS 테이블 차트 바로 아래, 품목 맨 아래)

## 2026-07-03 (5차) - Claude
- Task: 수출입 패널 버그 3종 수정
- Changed:
  - `web/quant_ui.js`
    - `fmtUsd`: $1K 미만 → K 단위 추가 (`$262,148` → `$262K`)
    - `fmtReason`: 신규 helper — verdict.reasons 문자열 내 raw 대형숫자를 $B/$M로 치환, "(ECOS 단위 기준)" 제거
    - verdict.reasons 렌더링에 `fmtReason` 적용 (`무역수지 27,036,300,000 (ECOS 단위 기준)` → `무역수지 $27.0B`)
    - top_items 루프: 같은 name 중복 시 HS 코드 6자리(XXXX.XX) 병기 (`신차` x3 → `신차 (8703.40)` / `신차 (8703.23)` / `신차 (8703.22)`)
- Verified: node --check PASS, 브라우저 3항목 모두 정상 표시 확인

## 2026-07-03 (4차) - Claude
- Task: 수출입 스케줄러 15~20일 변경 + Discord 신규 데이터 알림 추가
- Changed:
  - `scripts/05_notify/notify_trade_import_export.py` — 신규 생성. 수출입 신규 월 감지 시 Discord embed 전송 (수출 YoY/수입 YoY/무역수지/MoM/물량 YoY + 관세청 품목 상위 3개 + 판단 근거)
  - `run_trade_import_export.bat` — 수집 전 월 캡처, 수집 후 신규 월 비교, 다를 경우 notify_trade_import_export.py 호출 추가
  - Task Scheduler `QuantTradeImportExport_Monthly15` — 삭제
  - Task Scheduler `QuantTradeImportExport_Daily15to20` — 매월 15~20일 07:00 신규 등록
- Verified:
  - py_compile OK (notify_trade_import_export.py)
  - 월 감지 Python 명령 테스트: 202605 정상 반환
  - Discord 알림 테스트 전송 (202604→202605 시뮬레이션): 전송 완료
  - schtasks query Status=Ready, Next Run=2026-07-15 07:00

## 2026-07-03 (3차) - Claude
- Task: 관세청+ECOS 수출입 자동수집 자동화
- Changed:
  - `run_monthly.bat` — [7b] 단계에 `collect_trade_import_export_analysis.py` 추가
  - `run_trade_import_export.bat` — 신규 생성 (KOSIS→관세청분석→팩터→웹데이터 4단계)
  - `logs/` 디렉토리 생성
  - Task Scheduler `QuantTradeImportExport_Monthly15` — 매월 15일 07:00 등록, Next Run: 2026-07-15
- Verified: schtasks query Status=Ready, Next Run=2026-07-15 07:00

## 2026-07-03 (2차) - Claude
- Task: 수출입 통계 탭 UI 전면 재작성 (freeze 수정 + 데이터 확장)
- Changed:
  - `web/quant_ui.js`
    - `tradeChartInstances = []` 전역 변수 추가 — 매 렌더링 시 기존 Chart 파괴 후 재생성 (renderer freeze 원인 수정)
    - 차트 3개 → 4개: ①수출/수입/무역수지 금액(라인) ②YoY 성장률-수출금액·수입금액·수출물량(바+라인 혼합) ③MoM 변화율(바) ④가격지수 YoY(라인)
    - 품목 테이블: top_items를 `<tr>` 별도 행 + `└` prefix + 좌측 border 인디케이터 (이전 div-in-td 혼용 제거)
    - ECOS 테이블: 컬럼 7→8개 (수출 MoM 추가)
    - `chartOpts` 스프레드 중복 호출 제거 — 단순 `baseOpts` 구조로 교체
- Verified: node --check PASS, 브라우저 렌더링 확인 (차트 4개, 품목 8개+서브행, ECOS 12개월), 콘솔 오류 없음

## 2026-07-03 - Claude
- Task: 수출입 통계 탭 UI 개선
- Changed:
  - `web/index.html` — 히어로 지표 3→6개(수입 YoY·수출 MoM·수출물량 YoY·ECOS최신월 추가), 추세 차트 컨테이너 추가
  - `web/quant_ui.js` — renderTradeImportExportPanel 전면 개선
    - 히어로 지표 6개, fmtPct에 +/- 부호 추가, pctColor 헬퍼
    - Chart.js 추세 차트 3개: 수출·수입 금액(라인), 수출·수입 YoY(바), 무역수지(바)
    - 품목별 테이블: top_items 서브행(좌측 인디케이터), 신호 배지 색상화, 단가 $/kg 단위 표시
    - ECOS 테이블: 월 "202605"→"2026-05" 포맷, 최신월 녹색 하이라이트 + ▲최신 배지, YoY 컬러코딩
- Verified: node --check PASS, 브라우저 렌더링 확인 (차트 3개, 품목 8개 + top_items, ECOS 12개월 테이블), 콘솔 오류 없음

## 2026-07-03 10:34 - Hermes
- Task: 사용자 요청으로 Kiwoom API 현재 프로그램 비차익거래 확인
- Changed:
  - `data/raw/kiwoom/intraday_market_flow/market_flow_20260703.csv` — 수동 확인 실행 결과 10:34 audit row 2건(KOSPI/KOSDAQ) append
  - `data/raw/kiwoom/preflight/latest_kiwoom_preflight.json` — check-only 세션 상태 확인 결과 갱신
- Created: 없음
- Verification:
  - `run_kiwoom_intraday_market_flow.bat` 수동 실행: rc=2, `--no-login` 정책하 Kiwoom collector process는 `kiwoom_not_connected`, `latest_market_flow.json` 미덮어쓰기
  - `.venv-kiwoom32/Scripts/python.exe scripts/01_collect/check_kiwoom_session.py --check-only`: `connected_keeper`, keeper heartbeat `2026-07-03T10:34:06`
  - `market_flow_20260703.csv`: 20 rows, usable program/non-arbitrage rows 0
- Caveats: keeper heartbeat는 살아 있으나 one-shot collector가 Kiwoom TR에 attach하지 못해 현재 비차익 금액은 미확인. 사용자 정책상 강제 CommConnect/relogin은 시도하지 않음.

## 2026-07-02 - Claude
- Task: ADR 팩터 6/26 stale 수정 + 오전 자동화 추가
- Root cause: `QuantDailyMarket_1610`(16:10)이 ADR 수집·팩터 빌드를 하므로 오전 조회 시 전날(6/26) 기준 데이터 표시. 오늘 16:10 로그에서 6/29~7/1 갱신 성공 확인됨.
- Changed:
  - `run_macro_indicators_update.bat` — [5a] `collect_adr_daily.py`, [8b] `build_adr_gap_signal_factors.py` 단계 추가. 08:05(`QuantMacroIndicatorsDaily_0805`)에도 ADR 최신화 수행.
  - `web/quant_data.js` — export_web_data.py 재실행, ADR 팩터 7/1까지 반영
- Verification: `MAX(date)=2026-07-01, MAX(target_domestic_date)=2026-07-02` 확인. export_web_data.py exit 0.
- Note: 수급 추천 Discord 데이터 6/26 기준은 오전 조회(16:10 이전) 시 발생하는 정상 lag. 이후 08:05부터 전날 ADR 반영됨.

## 2026-07-02 09:57 - Hermes
- Task: Kiwoom 자동화를 장중에만 켜지도록 market-hours gating 적용
- Changed:
  - `run_kiwoom_intraday_market_flow.bat`
    - 평일 09:00~15:35 외 실행 시 즉시 `[SKIP]` 후 rc=0 종료하는 가드 추가
  - `run_kiwoom_candidate_stock_flow.bat`
    - 평일 09:00~15:35 외 후보 종목 수급 수집 skip 가드 추가
  - `run_kiwoom_decision_engine.bat`
    - 평일 09:00~15:35 외 decision engine/paper log/export 실행 방지
  - `C:\claude cowork\00_context\automation_list.md`
    - 신규 `*_MarketHours_*` Task Scheduler 작업 3개와 legacy task ACL caveat 기록
  - `C:\claude cowork\00_context\work_state.md`
    - 작업 lock 기록 후 해제 예정
- Created:
  - Task Scheduler `KiwoomIntradayMarketFlow_MarketHours_10m` — 매일 09:05~15:35, 10분 반복
  - Task Scheduler `KiwoomCandidateStockFlow_MarketHours_15m` — 매일 09:10~15:35, 15분 반복
  - Task Scheduler `KiwoomDecisionEngine_MarketHours_10m` — 매일 09:12~15:35, 10분 반복
- Verification:
  - batch CRLF/guard marker verifier 통과: 3개 `.bat` 모두 CRLF 정상, `09:00-15:35`, `:SKIP_MARKET_CLOSED` 포함
  - `Get-ScheduledTask -TaskName "Kiwoom*"` 확인: 신규 `*_MarketHours_*` 3개 Ready, 중복 `KiwoomProgramNonArbBrief_10m` Disabled
  - `Start-ScheduledTask KiwoomIntradayMarketFlow_MarketHours_10m`: LastRunTime 2026-07-02 09:57:01, LastTaskResult=2
  - 실행 로그 `logs\kiwoom_intraday_market_flow_20260702_095701.log`: Kiwoom not connected → latest 미덮어쓰기, Discord notify 미실행, rc=2 정상 차단
  - automation_list 문서 verifier: 신규 task marker 3개 존재, 깨진 path split 없음
- Caveats:
  - 기존 legacy `KiwoomIntradayMarketFlow_10m`/`KiwoomCandidateStockFlow_15m`/`KiwoomDecisionEngine_10m`는 action이 `C:\claude`로 잘린 상태지만, `Register-ScheduledTask`/disable/change가 0x80070005 권한 거부되어 직접 수정·비활성화 불가. 신규 `*_MarketHours_*` 작업이 정상 action으로 대체 등록되어 있고, 배치 자체에도 장중 가드를 넣어 장외 호출은 skip됨.
  - 현재 Kiwoom OpenAPI가 미접속 상태라 실수급 수집은 다음 영웅문 연결/장중 실행에서 확인 필요.

## 2026-07-02 09:46 - Hermes
- Task: KiwoomIntradayMarketFlow_10m 작동 정지 후 Discord `미확인` 브리핑 방지 및 재실행
- Changed:
  - `scripts/01_collect/collect_kiwoom_intraday_market_flow_once.py`
    - 사용 가능한 Kiwoom 수급/프로그램 값이 하나도 없으면 `latest_market_flow.json`을 덮어쓰지 않도록 수정
    - `--fail-if-unavailable` 옵션 추가: Kiwoom 미접속/정지 상태에서는 rc=2로 종료
    - demo row는 최신 payload로 쓰지 않도록 차단
  - `scripts/05_notify/notify_program_trading_brief.py`
    - 값 없는 payload 또는 demo payload는 Discord embed 생성 전에 차단
  - `run_kiwoom_intraday_market_flow.bat`
    - collector 실행에 `--fail-if-unavailable` 추가해 알림 전에 실패 종료
  - `C:\claude cowork\00_context\automation_list.md`
    - `KiwoomIntradayMarketFlow_10m` 상태/검증 메모 갱신
- Created: 없음
- Verification:
  - `python -m py_compile scripts/01_collect/collect_kiwoom_intraday_market_flow_once.py scripts/05_notify/notify_program_trading_brief.py` 통과
  - notifier 단위 검증: 값 없는 Kiwoom payload는 `ValueError`로 차단, 값 있는 payload는 합산 비차익 `+50` embed 생성
  - `python scripts/01_collect/collect_kiwoom_intraday_market_flow_once.py --demo` 실행 시 `latest_market_flow.json` 미생성 확인
  - `cmd //c run_kiwoom_intraday_market_flow.bat` 재실행: Kiwoom not connected → latest 미덮어쓰기, Discord notify 미실행, rc=2
  - `schtasks /Run /TN KiwoomIntradayMarketFlow_10m` 재실행: 09:45:26 실행, 동일하게 알림 없이 차단됨
- Caveats: 현재 Windows 세션에서 Kiwoom OpenAPI가 연결되어 있지 않아 실수급 수집은 되지 않았음. 영웅문/키움 연결 후 다음 10분 주기 또는 수동 실행에서 실제 값 수집 필요.

## 2026-07-02 09:35 - Hermes
- Task: FRED 무역 CSV CRCRLF 줄바꿈 오염 수정
- Changed:
  - `scripts/01_collect/collect_us_korea_trade_once.py`
    - FRED CSV 다운로드 직후 `normalize_csv_text()`로 CRLF/CR 줄바꿈을 LF로 정규화
    - raw CSV 저장 시 `newline='\n'` 지정해 Windows/MSYS에서 `\r\r\n` 생성 방지
  - `data/raw/macro/trade_stats/fred_*.csv`
    - 기존 `\r\r\n` 줄바꿈을 LF로 정규화
- Created: 없음
- Verification:
  - `python -m py_compile scripts/01_collect/collect_us_korea_trade_once.py` 통과
  - `git diff --check -- scripts/01_collect/collect_us_korea_trade_once.py data/raw/macro/trade_stats/fred_*.csv` 통과 (autocrlf 경고만 존재)
  - `bad_line_endings=0` 확인
  - `npm run test` → 33 passed
- Caveats: 전체 repo에는 기존 대량 변경/미추적 파일과 tracked `node_modules` 오염이 남아 있음. 이번 수정 범위는 무역 CSV 줄바꿈 문제로 제한.

## 2026-07-01 (8) - Claude
- Task: KOSPI 60d NULL 수정 + 매크로 스코어 패널 5개 지표 추가 + 저녁 9시 자동화 등록
- Changed:
  - `scripts/03_analyze/build_market_regime_adjusted_signals.py`
    - `load_monthly_regime_inputs()` 함수에 ffill 추가 — 월 초 새 period에 이전 달 팩터 값 forward fill (korea_kospi_ret_60d_pct, us_10y_2y_spread 등 NULL 방지)
  - `web/index.html`
    - 매크로 탭 metric-strip에 5개 tile 추가: 10Y-2Y, HY스프레드, USD/KRW, VIX, 금융스트레스
  - `web/quant_ui.js`
    - 매크로 탭 렌더링 함수에 5개 지표 계산 변수 추가 (dgs2, spread10y2y, hy, usdkrw, vix, stlfsi)
    - setText 5개 + evidence-list 5개 항목 추가
  - `web/quant_data.js` — export_web_data.py 재실행으로 재생성 (7/1 행 korea_kospi_ret_60d_pct=44.35 반영)
  - Task Scheduler — `QuantMacroFactorPanel_2100` 신규 등록 (매일 21:00, run_macro_factor_panel_update.bat, StartWhenAvailable)
- Root cause: `macro_quant_factors_daily`의 korea_kospi_ret_60d_pct 최신 날짜가 6/30 → period=2026-06-01로 분류, 7/1 period에 NULL. ffill로 해결.
- Verification: python build_market_regime_adjusted_signals.py → factor_market_macro_regime_month 7/1 row korea_kospi_ret_60d_pct=44.35 확인. node --check quant_ui.js OK. quant_data.js 재생성 완료. schtasks QuantMacroFactorPanel_2100 Next Run 2026-07-02 21:00:00.
- Note: QuantMacroFactorPanelDaily(18:05)에도 동일 배치가 등록되어 있어 하루 2회 실행됨.

## 2026-07-01 (7) - Claude
- Task: Task Scheduler 3개 문제 수정
- Changed: Task Scheduler 등록 (XML 직접 방식)
  - `QuantInvestorMinuteCollector` — DaysOfWeek 비어있어 한 번도 실행 안됨 → XML 재등록 (월~금, 08:55, StartWhenAvailable, 경로 정확히 `run_investor_minute_auto.bat`) / Next Run: 2026-07-02 08:55
  - `QuantDataQualityStalenessDaily` — StartWhenAvailable 없음 → 재등록 (매일 21:20, StartWhenAvailable 추가) / Next Run: 2026-07-02 21:20
  - `QuantMonthly_0600` — TimeTrigger one-time → ScheduleByMonth 재등록 (매월 2일 06:00, 경로 수정) / Next Run: 2026-08-02 06:00
- Root cause: schtasks /create /tr로 공백 경로 등록 시 경로 잘림, PowerShell Register-ScheduledTask의 Weekly DaysOfWeek 버그 → XML 파일 직접 작성 후 schtasks /create /xml로 등록
- Verification: schtasks /query 각 작업 Status=Ready, Next Run Time 정상, XML DaysOfWeek 월~금 포함 확인

## 2026-07-01 (6) - Claude
- Task: 홈 화면 renderHomeDashboard TypeError 수정
- Changed:
  - `web/quant_ui.js`
    - line ~3274: dgs10/k60/kq60 — `!= null` 체크에서 `!= null && !== ""` + `Number()` + `isFinite()` 조합으로 강화
    - line ~3448: scoreItems `_toNum()` 헬퍼 추가, null 체크에 `!isFinite()` 추가
- Root cause: `korea_kospi_ret_60d_pct` 등이 null이 아닌 빈 문자열(`""`)로 저장됨 → `"" != null`이 true라 `.toFixed()` 호출 → TypeError
- Verification: `node --check OK` / 브라우저 `renderHomeDashboard()` 에러 없이 실행, title="WATCH 우선·조건부 진입", dgs10=4.38%, dxy=2.58 표시 확인
- Note: `korea_kospi_ret_60d_pct`는 현재 빈 문자열 → `--` 표시 (데이터 파이프라인에서 미생성). 수정 후에는 값이 들어오면 자동 표시됨.

## 2026-07-01 (5) - Claude
- Task: 분봉 수집기 Kiwoom 전용 전환 + Task Scheduler 자동화
- Changed:
  - `scripts/01_collect/collect_investor_minute.py` 전면 재작성
    - NAVER 제거, Kiwoom opt10059 단독 사용
    - `GetConnectState()==1` → CommConnect 팝업 없이 즉시 시작 (영웅문 상시 연결 대응)
    - QTimer 60초, 15:45 자동 종료 (Task Scheduler 정상 종료)
    - `--demo` 옵션만 유지 (`--no-kiwoom` 제거)
  - `run_investor_minute_auto.bat` — `--no-kiwoom` 플래그 제거
  - Task Scheduler `QuantInvestorMinuteCollector` 재등록
    - 평일(월~금) 08:55, 실행 제한 8시간
- Verification: syntax OK, 등록 확인 (State=Ready, NextRun=2026-07-02 08:55)
- Note: opt10059가 시장 코드 "0001"을 지원하지 않으면 수집 실패 로그 남김 → 첫 장중 실행 시 로그 확인 권장

## 2026-07-01 (4) - Claude
- Task: 투자자별 분봉 수집기 구현 (Kiwoom + NAVER)
- Changed:
  - `scripts/01_collect/collect_investor_minute.py` (신규)
    - Kiwoom opt10059 로 KOSPI 투자자 시도 → 실패 시 NAVER fallback
    - NAVER investorDealTrendDay.naver?sosok=01/03 스크래핑
    - QApplication + QTimer(60초) 기반 장중 자동 polling
    - `--no-kiwoom` (NAVER만), `--demo` (더미) 옵션 지원
  - `run_investor_minute.bat` (신규) — Kiwoom 모드 실행 래퍼
- Verification:
  - KOSPI 파싱: 개인=+8,401억 / 기관=+29,332억 / 외국인=-37,992억 (2026-06-30)
  - 선물 파싱: 개인=+1,195억 / 기관=+613억 / 외국인=-2,458억 (2026-06-30)
  - syntax OK, 데모 CSV 생성 확인
- Output: `data/raw/money_flow/investor_minute/investor_YYYYMMDD.csv`
- Note:
  - 단위: 억원 (순매수 누적)
  - 콜/풋 옵션 투자자별은 KRX 일별만 공개 — 분봉 원천 없어 미구현
  - 장중(09:05~15:35)에만 row 추가, 나머지는 대기

## 2026-07-01 (3) - Claude
- Task: 리스크 패널 EWS 버블 차트 자동 초기화 수정
- Root Cause:
  - `quant_ui.js` `initTabs()`에 `tab-bubble` 탭 전환 시 처리 조건 누락
  - 사이드바 "리스크" 버튼 클릭 → `initBubbleCharts()` 미호출 → 차트 미렌더링
  - `window.BUBBLE_DATA`(dates:377, buffett:377 등)는 정상이나 Chart.js 인스턴스 생성 안 됨
- Changed:
  - `web/quant_ui.js` `initTabs()` (line ~68): `targetId === "tab-bubble"` 조건 추가
    - 이미 차트 있으면 resize, 없으면 `initBubbleCharts()` 호출
- Verification:
  - `node --check` OK
  - 브라우저 JS: `bubbleChartsLength=9`, `buffettRows=377`
  - 버핏지수/실러PE/레버리지/시장집중도/M2 등 차트 정상 렌더링 확인

## 2026-07-01 (2) - Claude
- Task: 팩터 검증 IC 붕괴 경보 수정 (인코딩 오염 → 정상화)
- Root Cause:
  - `build_factor_ic_report.py`를 `-X utf8` 옵션 없이 실행 시 `FACTOR_DEFS` 한글 상수가 EUC-KR 해석됨
  - CSV(`factor_ic_summary.csv`)가 오염된 factor_label로 저장됨
  - 오염된 IC 값으로 잘못된 decay_warning=1 (valuation_score, small_cap_score) 생성
- Changed:
  - `scripts/03_analyze/export_web_data.py` `_records_from_csv()`: `encoding='utf-8-sig'` 기본값 추가 (재발 방지)
  - `scripts/03_analyze/build_factor_ic_report.py`: `-X utf8`로 재실행 → `factor_ic_summary.csv` 정상 재생성
  - `web/quant_data.js`: export 재실행으로 갱신
- Verification:
  - JS 확인: ic_summary 14개 팩터 한글 정상 (`모멘텀 복합`, `리레이팅 모멘텀` 등)
  - decay_warning=0개 (이전 오염 데이터로 인한 잘못된 경보 2개 해소)
  - 브라우저 팩터 검증 탭: 14행 정상 렌더링, 붕괴 경보 없음 확인
- Note: IC_3m N/A는 정상 — fwd_ret_1m shift(-1)로 최근 3기간 선행수익 미확정

## 2026-07-01 (1) - Claude
- Task: 원달러 환율 매크로 팩터 패널 미표시 수정 + 자동화 확인
- Root Cause:
  - `USD_KRW.csv` 마지막 행(`2026-06-29`)이 빈 OHLCV(`Close=""`)로 수집됨
  - `latestValue()` 함수가 `Number("") === 0`을 유효값으로 반환하는 버그
  - → `usdKrw = 0` → `"₩0"` 잘못 표시
- Changed:
  - `web/quant_ui.js` line 158: `latestValue()` — 빈 문자열/null/undefined 건너뜀 방어 코드 추가
    - Before: `const value = Number(String(raw ?? "").replace(/,/g, ""))`
    - After: `if (raw === "" || raw === null || raw === undefined) continue;`
  - `scripts/03_analyze/export_web_data.py` line 12: `_records_from_csv()` — 날짜 제외 수치 컬럼 전부 NaN인 빈 행 dropna 추가
  - `web/quant_data.js`: export_web_data.py 재실행으로 갱신 (USD_KRW 마지막 행 2026-06-28 Close=1535.24)
- Verification:
  - `node --check web/quant_ui.js` → exit 0
  - `python -c "import py_compile; py_compile.compile(...)"` → OK
  - `quant_data.js` USD_KRW 마지막 행 확인: `Close: 1535.239990234375` (정상)
- Automation: `run_macro_indicators_update.bat` [9/9] 단계에 `export_web_data.py` 이미 포함 — 추가 작업 불필요
- Note: `FutureWarning: fillna incompatible dtype` — pandas 경고이나 기능 영향 없음. 차후 `df.astype(str)` 전환 고려

## 2026-06-30 (4) - Claude
- Task: UI 2차 개선 — Jobs/Musk 피드백 10개 항목 전체 적용
- Changed:
  - `web/index.html`:
    - [#8] 다크모드 카드 대비: bg #040608→#030712, card-bg #080c12→#0f172a, border #101620→#1e293b. 배경과 카드가 이제 눈에 보임
    - [#4] stock-why-box: font-size 0.72rem→0.83rem, color text-sub→text-main, bg 불투명도 개선. 모바일 0.68rem→0.78rem
    - [#5] 상태바 레짐 배지를 full-height strip으로: padding 12px, font-size 1rem/weight 800, 배경색이 Risk-ON/OFF에 따라 full strip으로 강조
    - [#1] 타입 스케일 4단계 CSS 변수 추가 (--fs-xs/sm/base/lg), body 기본 font-size var(--fs-sm)
  - `web/quant_ui.js`:
    - [#3] 모든 progress bar 높이: 5px/4px/6px → 12px/10px/10px
    - [#2] PER/PBR/ROE 섹터 맥락 색상: sector_relative_per/pbr 기반 green/yellow/red 자동 적용 + "↓싸다/↑비싸다" 미니 레이블. ROE 15%이상=green, 8%이상=yellow. "재무 상세 ▾" 0.75rem/text-main으로 가시성 향상
    - [#2/#10] details에 onclick="event.stopPropagation()" 추가 — 행 클릭 모달과 충돌 해소
    - [#9] IC경보 액션 텍스트 추가: "→ IC 약화 팩터 포함 종목 비중 축소 권장. 팩터 심사표에서 IC 복원 여부 확인."
    - [#7] 뉴스 헤드라인에서 언론사 이름 제거 (officeLabel 표시 삭제) — 의미없는 정보 제거
    - [#6] 차트 캔버스 높이 250px→280px
    - [#5] 상태바 레짐 배지 스타일 full-strip 방식으로 업데이트
- Verify: `node --check web/quant_ui.js` → PASS

## 2026-06-30 (3) - Claude
- Task: UI 피드백 8개 항목 수정 (가독성 개선)
- Changed:
  - `web/quant_ui.js`:
    - [Fix#2] 상태바 날짜 포맷 "06. 30. (화)" → "6.30(화)" 간결화
    - [Fix#8] 홈탭 IC경보 패널에 "IC<0.05=예측력 약화" 기준 설명 추가
    - [Fix#3] 선물 매매동향 차트 날짜 오름차순 정렬 보장 + 날짜 포맷 "YYYYMMDD" → "MM/DD"
    - [Fix#4] KOSPI/KOSDAQ 투자자별 순매수 차트 제목에 "(단위: 억원)" 추가
    - [Fix#5] 종목 테이블 가치/퀄리티 컬럼: PER/PBR/ROE 3개 우선 표시, 나머지 6개는 <details> 호버로 접기
    - [Fix#6] 뉴스 감성 Top10에서 이름 없는 종목 "005387 005387" → "종목명 미상 005387"
    - [Fix#7] 부정 감성 Top10 항목 5개 미만 시 "시장 분위기 양호" 인사이트 메시지 추가
    - [Fix#1] 홈탭 하단 공백 채우기: 최신 헤드라인 8개 미리보기 + 매크로 스코어 5개 패널 렌더링
  - `web/index.html`: 홈탭 하단 2열 그리드 추가 (home-headlines-preview, home-macro-scores)
- Verify: `node --check web/quant_ui.js` → PASS
- Note: renderHomeDashboard에서 `lr` 변수는 함수 상단에서 이미 선언됨. 부정 인사이트 div는 renderNewsSentiment 재실행 시 중복 방지 고려 필요 (새로고침마다 DOM 재생성이므로 실제 중복 없음)

## 2026-06-30 (2) - Claude
- Task: 주가 지표 탭 고객예탁금/신용잔고 중복 차트 제거 + 단위 수정
- Changed:
  - `web/quant_ui.js`: macro-index-charts에서 "고객예탁금 및 신용잔고" 차트 제거(중복), macro-index-futures-charts의 차트만 남김 / 기간 20→120일 확장 / 단위 만원→조원(억원÷10,000)으로 수정 / tooltip 단위 표기 추가
- Verification: 브라우저 검증 - 고객예탁금 ~130조원 / 신용잔고 ~40조원 정상 표시. node --check OK
- 주의: `_customerDeposit` 원시 단위는 억원. 조원 표시 = /10,000

## 2026-06-30 - Claude
- Task: UI 8개 개선사항 일괄 적용 (Steve Jobs/Elon Musk 피드백 반영)
- Changed:
  - `web/index.html`: ① CSS 색상 팔레트 확장(--c-green/yellow/red/blue/purple/grey 시맨틱 변수 추가) ② H1 헤더 제거→compact 상태바(레짐배지·KOSPI 60d·미 10Y·날짜·테마토글) ③ 홈 탭 HTML 신규 추가(레짐배너+Top5+IC경보+뉴스스냅샷) ④ reports sub-nav 초기 hidden ⑤ data-card에 overflow:hidden + canvas max-width 차트오버플로 CSS픽스
  - `web/quant_ui.js`: ⑥ renderStatusBar() 상태바 초기화 ⑦ renderHomeDashboard() 홈 대시보드(레짐 color-coded, Top5 진행바+색상, IC경보 팩터구조 반영) ⑧ switchTab() 헬퍼 함수 ⑨ 종합매력도 점수 1.6rem 볼드+진행바로 시각적 강조(개선 #6) ⑩ 헤드라인 피드 다중 ticker 뱃지 렌더링
  - `scripts/03_analyze/export_news_data.py`: 헤드라인 article_id 중복 제거 - 동일 기사가 여러 종목에 반복 수록되던 문제 해결, related 배열로 관련종목 목록 포함
  - `web/news_data.js`: 중복 제거 재생성 (8,097건 → 6,115건 고유 기사)
- Verification:
  - `node --check web/quant_ui.js` → 문법 오류 없음
  - `python -X utf8 scripts/03_analyze/export_news_data.py` → 432행/6,115헤드라인/669.5KB 정상
  - 브라우저 검증: 홈탭(레짐배너Risk-OFF/Top5이엔에프테크놀로지89점/IC경보4/6/뉴스52긍정) 정상, 매크로차트오버플로 해결, 종목분석 점수진행바 표시, 헤드라인 다중ticker 그룹핑 확인
- 주의사항:
  - IC 경보는 `regression.factor_ic.factors` flat 배열 구조 사용 (기존 시계열 구조 아님)
  - 뉴스 article_id 없는 row는 `_notitle_{ticker}_{date}_{title[:30]}` 키로 처리
  - 홈탭 "전체 보기 →" 버튼은 switchTab('analysis')/switchTab('news') 호출

---

## 2026-06-30 18:05 - Hermes
- Task: 직전 산출물인 2025년 이후 KOSPI 주간 거래대금 그래프를 Discord 보고 채널로 전송.
- Changed:
  - `CHANGELOG_AGENT.md`: Discord 전송 결과 기록.
- Created: 없음.
- Verification:
  - 기존 산출물 존재 확인: PNG/HTML/CSV 모두 존재, PNG 182,816 bytes, HTML 2,827 bytes, CSV 10,717 bytes.
  - Discord webhook POST 실행 → HTTP 200, `DISCORD_POST_OK True`.
- Caveats:
  - 전송에는 PNG 그래프를 첨부했고, 로컬 HTML/CSV 경로는 Discord 외부에서 직접 열 수 없는 로컬 파일이므로 메시지에는 핵심 요약과 그래프 이미지를 포함함.

---

## 2026-06-30 17:53 - Hermes
- Task: 2025년 이후 KOSPI 거래대금을 주간 단위로 집계하고 그래프/CSV 산출.
- Changed: 없음. 프로젝트 원천/DB/웹 산출물은 수정하지 않음.
- Created:
  - `C:/claude cowork/02_outputs/2026-06-30_17-53-13_kospi_weekly_trading_value_since_2025.png`
  - `C:/claude cowork/02_outputs/2026-06-30_17-53-13_kospi_weekly_trading_value_since_2025.html`
  - `C:/claude cowork/02_outputs/2026-06-30_17-53-13_kospi_weekly_trading_value_since_2025.csv`
  - `C:/claude cowork/02_outputs/2026-06-30_17-53-13_kospi_weekly_trading_value_since_2025_daily_source.csv`
- Verification:
  - `FinanceDataReader.DataReader('KS11', '2025-01-01', '2026-06-30')` → daily 362행, weekly 79행, 범위 2025-01-02~2026-06-30.
  - CSV 재개방 검증 → 79행, `amount_sum_trillion_krw` 결측 없음, 최근 5주 요약 출력 OK.
  - PNG 재개방 검증 → 2384x1232, 제목/축/범례/막대/이동평균/KOSPI 선 정상 렌더링 확인.
- Caveats: 최신 주(2026-06-29~2026-06-30)는 화요일까지 2거래일만 포함된 진행 중 주간임.

---

## 2026-06-30 11:10 - Hermes
- Task: Kiwoom OpenAPI Discord 수동 실행 명령 추가, 데모 실행의 `latest_*` 보호, 실행 결과 검증 메시지 명확화.
- Changed:
  - `scripts/05_notify/hermes_bot.py`: `!run kiwoom` job 추가, Kiwoom 실행 결과를 `실접속`/`데모`/`실패`로 판정해 Discord embed 제목/필드에 표시.
  - `scripts/01_collect/collect_kiwoom_portfolio_once.py`: `--demo` 실행은 타임스탬프 파일만 쓰고 `latest_*`를 덮어쓰지 않도록 변경, stdout JSON에 `connected`/`mode`/`result_class` 추가.
  - `scripts/01_collect/run_kiwoom_portfolio_supervised.py`: collector 출력/종료코드 기반 `KIWOOM_VERIFY: 실접속|데모|실패` 검증 라인 출력 및 검증 불명확 시 실패 처리.
  - `tests/test_kiwoom_portfolio_collector.py`, `tests/test_kiwoom_supervised_runner.py`: latest 보호 및 결과 분류 회귀 테스트 추가.
  - `data.md`: Kiwoom demo/latest 동작 및 Discord 실행 명세 보강.
  - `C:/claude cowork/00_context/work_state.md`: 작업 lock 기록/해제.
- Created: 없음.
- Verification:
  - `python -m py_compile scripts/01_collect/collect_kiwoom_portfolio_once.py scripts/01_collect/run_kiwoom_portfolio_supervised.py scripts/05_notify/hermes_bot.py` → OK.
  - `python -m pytest tests/test_kiwoom_portfolio_collector.py tests/test_kiwoom_supervised_runner.py -q` → 9 passed.
  - `npm run test` → 28 passed.
- Caveats:
  - 실제 `!run kiwoom` Discord 전송/실계좌 접속은 봇 실행 세션 및 Kiwoom 로그인 UI가 필요하므로 이번 검증은 코드 경로/분류 로직/테스트 기준입니다.

---

## 2026-06-30 11:01 - Hermes
- Task: 섹터 상대가치 팩터의 DART 다중연도/period 중복 처리 수정 상태를 검증하고 `QuantAllFactorsDaily` 전체 팩터 자동화 경로를 재검증.
- Changed:
  - `data/raw/factors/sector_relative_value_month.csv`: 전체 팩터 재빌드 과정에서 최신 산출물 재생성.
  - `data/database/quant_data.sqlite`: 전체 팩터 재빌드 과정에서 factor 계열 및 `factor_sector_relative_value_month` 재적재.
  - `web/quant_data.js`: `export_web_data.py` 재실행으로 웹 대시보드 데이터 재생성.
  - `C:/claude cowork/00_context/work_state.md`: 작업 lock 해제.
- Created:
  - `logs/all_factor_update_20260630_105856.log`: 전체 팩터 재검증 로그.
  - 전체 팩터 빌더 실행 중 생성된 SQLite 백업 파일들(`data/database/backups/quant_data_20260630_*`).
- Verification:
  - `python -m pytest tests/test_sector_relative_value_factors.py -q` → 12 passed.
  - `python -X utf8 scripts/03_analyze/run_all_factor_builders.py` → `ALL_FACTOR_UPDATE_STATUS=OK`, 로그 `logs/all_factor_update_20260630_105856.log`.
  - `schtasks.exe //Run //TN QuantAllFactorsDaily` 후 조회 → Last Run Time 2026-06-30 11:02:28 / Last Result 0.
  - SQLite 검증: `factor_sector_relative_value_month` 14,136행 / ticker-period 중복 0 / 395종목 / 2023-06-01~2026-06-01, `factor_sector_relative_value_catalog` 27행 / factor_name 중복 0.
  - `npm run test` → 28 passed.
- Caveats:
  - `export_web_data.py`의 pandas `fillna("")` FutureWarning 및 macro release duplicate warning(CPIAUCSL, UNRATE)은 기존 경고로 남아 있으나 전체 실행 실패 원인은 아님.

---

## 2026-06-30 09:51 - Hermes
- Task: Kiwoom OpenAPI 실계좌 스냅샷 접속 시도 후 금일 장중 수급/시황 분석.
- Changed:
  - `C:/claude cowork/00_context/work_state.md`: 작업 lock 기록 및 해제.
- Created: 없음.
- Verification:
  - `./run_kiwoom_portfolio_once.bat --trade-date 20260630` 실행 시 180초 로그인 대기로 timeout; `data/raw/kiwoom/*20260630*` 신규 파일 없음 확인.
  - 기존 latest Kiwoom raw 확인: `latest_portfolio_snapshot.json`은 2026-06-29 23:41 데모 모드/connected=false, holdings 3/trades 1.
  - Naver Finance 장중 데이터 직접 조회 성공: 2026-06-30 09:51 기준 KOSPI 8,287.36(-1.28%), KOSDAQ 920.03(-0.06%), KOSPI 외국인 -10,952억/기관 +4,635억, KOSDAQ 외국인 -2,113억/기관 +472억.
- Caveats:
  - 실제 Kiwoom 계좌 조회는 데스크톱 Kiwoom 로그인/인증 완료가 필요해 이번 터미널 세션에서는 실계좌 최신 스냅샷을 생성하지 못함. 분석에는 Naver 장중 수급과 프로젝트 latest/demo Kiwoom raw를 구분해 사용.

---

## [2026-06-30] Claude — 뉴스 & 리서치 패널 구현

**변경 파일**
- `web/index.html` — tab-news 섹션 전면 교체, nav-sub-news 서브탭(감성현황/최신헤드라인) 추가, news_data.js 스크립트 로드
- `web/quant_ui.js` — switchSubTab에 news-sentiment/news-headlines 핸들러 추가, renderNewsSentiment/renderNewsSentimentTable/renderNewsHeadlinesFeed 함수 구현
- `web/news_data.js` (신규) — 432종목 감성 스냅샷 + 최신 2000건 헤드라인 export
- `scripts/03_analyze/export_news_data.py` (신규) — news_data.js 생성 스크립트

**구현 내용**
- 감성 현황 탭: 요약 카드(커버리지/긍정52/부정3/중립377/8097건), 긍정Top10·부정Top10 테이블, 전체 감성 랭킹(검색+필터)
- 최신 헤드라인 피드: 최근 14일, 날짜별 그룹핑, 종목명/코드/헤드라인 검색, 100/200/500건 표시 선택
- 언론사명 매핑(연합뉴스, 매일경제, 한국경제 등 30여개)
- 감성점수 바 시각화(0~100), 긍정/부정 비율 표시

**검증**
- `node --check quant_ui.js` OK
- 브라우저 확인: 감성 대시보드 정상 렌더링, 헤드라인 피드 날짜별 그룹 표시
- 검색 테스트: "삼성" → 256건 필터링 정상
- NEWS_DATA 로드: 432종목, 2000헤드라인, 395종목명 포함

**주의사항**
- news_data.js는 `python scripts/03_analyze/export_news_data.py`로 재생성 (run_daily_news.bat에 추가 권장)
- factor_master_month.csv의 name 컬럼이 비어있어 sector 컬럼에서 회사명을 대체 로드함

---

## 2026-06-29 22:50 - Hermes
- Task: `kiwoom-dashboard`의 Kiwoom OpenAPI 계좌/매매일지 조회 로직을 Anal_reports 수집 파이프라인 형태로 이식하고 실제 실행 환경을 32bit Python으로 보정.
- Created:
  - `scripts/01_collect/collect_kiwoom_portfolio_once.py`: `opw00018` 보유/계좌평가, `opt10170` 당일매매일지 수집 후 `data/raw/kiwoom/latest_*` 및 타임스탬프 원천 파일 저장. 실제 주문/DB 쓰기 없음.
  - `tests/test_kiwoom_portfolio_collector.py`: 숫자 파서, 계좌 필터, fake Kiwoom 수집, demo 파일 저장 테스트.
  - `run_kiwoom_portfolio_once.bat`: 32bit `.venv-kiwoom32`로 Kiwoom collector 실행.
  - `data/raw/kiwoom/latest_portfolio_snapshot.json`, `latest_holdings.csv`, `latest_account_summary.csv`, `latest_trades.csv` 및 demo 타임스탬프 파일.
- Changed:
  - `data.md`: Kiwoom 계좌 스냅샷 원천 데이터 명세 추가.
  - `C:/claude cowork/00_context/index.md`: Kiwoom 수집 스크립트/출력 위치 등록.
  - `C:/claude cowork/00_context/work_state.md`: 작업 lock 기록 후 해제.
- Verification:
  - 32bit Python 설치 확인: `C:/Users/fckin/AppData/Local/Programs/Python/Python311-32/python.exe`, `('32bit', 'WindowsPE')`.
  - `.venv-kiwoom32` 생성 후 `pandas==2.0.3`, `pykiwoom`, `PyQt5`, `pytest` 설치 완료.
  - `python -m py_compile scripts/01_collect/collect_kiwoom_portfolio_once.py tests/test_kiwoom_portfolio_collector.py` 성공.
  - `.venv-kiwoom32/Scripts/python.exe -m pytest tests/test_kiwoom_portfolio_collector.py -q` → 4 passed.
  - `run_kiwoom_portfolio_once.bat --demo` → holdings 3 / trades 1 / total_asset 13,643,445원, latest 파일 생성 확인.
  - 실제 실행 시 64bit Python의 `QAxWidget.OnReceiveTrData` 오류는 해소됨. 32bit 실행은 `키움증권 서버 로그인 시작` 이후 로그인 대기 상태로 진입.
- Caveats:
  - 실제 Kiwoom 수집은 Windows 데스크톱 로그인 세션에서 Kiwoom 로그인/인증을 완료해야 계좌 조회로 진행됩니다. 현재 백그라운드 실행 세션 `proc_e222e3417ad8`이 로그인 대기 중입니다.
  - 기존 작업으로 이미 dirty 상태였던 `requirements.txt`, 대량 raw/DB/web 산출물은 건드리지 않음.

## 2026-06-29 — DART 재무 2025+2024 수집 완료 + 팩터 재빌드 (Claude)

### 변경 파일
- `data/raw/valuation/dart_finstate/finstate_all.csv` — 201,026행 (2025: 2,598종목 / 2024: 2,547종목)
- `scripts/03_analyze/build_sector_relative_value_factors.py` — 버그 수정: 다중 연도 수집 시 period 인덱스 중복으로 발생하는 `ValueError: The truth value of a Series is ambiguous` 수정 (`groupby(level=0).first()`로 최신 bsns_year 우선 단일화)
- `data/raw/factors/sector_relative_value_month.csv` — 28,225행 재빌드
- `data/database/quant_data.sqlite` — factor_piotroski_snapshot 2,601행 / factor_sector_relative_value_month 28,225행 / factor_master_month 15,374행 재적재
- `web/quant_data.js` — 재생성 완료

### 검증 결과
- `build_piotroski_factors.py` 종료코드 0 / 2,601종목 F-Score 산출
- `build_sector_relative_value_factors.py` 종료코드 0 / 28,225행 / 395종목
- `build_factor_master_panel.py` 종료코드 0 / 15,374행 / 432종목 / 2026-06 최신
- `export_web_data.py` 종료코드 0 / stock_attractiveness 5,323행 / quant_data.js 재생성

### 주의사항
- `FutureWarning: Setting an item of incompatible dtype` 다수 출력 — 동작 무관, 향후 pandas 버전업 시 export_web_data.py `df.fillna("")` 수정 필요

---

## 2026-06-29 19:15 - Hermes
- Task: Discord 명령이 Hermes memory에 저장되지 않는 문제를 프로젝트 영속 저장소로 대체.
- Created:
  - `scripts/00_ops/log_discord_command.py`: Discord/Gateway 명령을 SQLite, markdown log, inbox, JSONL에 저장하고 status를 갱신하는 CLI/API.
  - `tests/test_discord_command_logger.py`: add/update/list pending 동작 테스트.
  - `docs/discord_command_logging.md`: 운영법과 상태값/사용 예시.
  - `C:/claude cowork/00_context/discord_command_log.md`, `discord_inbox.md`, `discord_command_log.jsonl`: 실제 영속 로그 파일 초기화.
- Changed:
  - `package.json`: `npm run test`에 `log_discord_command.py` py_compile과 `test_discord_command_logger.py` 포함.
- Data:
  - SQLite table `discord_command_log` 생성.
  - 현재 CLI 명령을 bootstrap record `#1`로 기록.
- Verification:
  - RED: 신규 테스트는 스크립트 부재로 실패 확인.
  - GREEN: `python -m pytest tests/test_discord_command_logger.py -q` → 3 passed.
  - 이후 `npm run test`와 ad-hoc verifier 실행.

## 2026-06-29 13:42 - Hermes
- Task: Quant 자동화 미실행/오류 상태 재점검 및 자동화 레지스트리 최신화.
- Findings:
  - `QuantDartFinstate_0200`: 사용자 화면의 “미실행”과 달리 실제 Task Scheduler는 2026-06-29 02:00 실행, `LastTaskResult=0`, 다음 2026-07-06 02:00.
  - `QuantConsensusRevisionWeeklyFull`: 2026-06-29 07:00 실행, `LastTaskResult=0`, 다음 2026-07-06 07:00.
  - `QuantAllFactorsDaily`: 2026-06-28 18:20 실행 로그 확인, `LastTaskResult=0`; 기존 `rc=?`는 상태 표시/레지스트리 stale 이슈.
  - `QuantCheckCollection_2100`: 이전 `LastTaskResult=9009`는 배치/PATH 계열 오류로 확인. 배치 보강 후 수동 실행 및 `Start-ScheduledTask` 모두 `LastTaskResult=0`.
  - `QuantMonthly_0600`: 실제 trigger가 “매월 1일”이 아니라 one-time `2026-07-02 06:00`으로 등록되어 있음. Task Scheduler 수정은 현재 세션 권한 거부(`0x80070005`)로 미적용.
- Changed:
  - `run_check_collection.bat`: CRLF 유지, `setlocal/endlocal`, quiet `env.bat`, `python -X utf8`, 명시 `exit /b 0` 보강.
  - `run_all_factor_update.bat`: `chcp 65001 >nul`, quiet `env.bat`, 명시 `exit /b 0` 보강.
  - `C:/claude cowork/00_context/automation_list.md`: 11개 Quant 작업의 실제 LastRun/LastTaskResult/NextRun 최신화 및 Monthly trigger caveat 기록.
  - `C:/claude cowork/00_context/work_state.md`: 작업 lock 기록.
- Verification:
  - `powershell Get-ScheduledTask/Get-ScheduledTaskInfo`: 11개 Quant task 상태 조회.
  - `cmd.exe /c run_check_collection.bat`: `ok=17 warn=1 fail=0`, Discord 전송 `6/6`, exit 0.
  - `Start-ScheduledTask QuantCheckCollection_2100` 후 `LastTaskResult=0` 확인.
  - `python -m py_compile scripts/05_notify/check_collection.py scripts/03_analyze/run_all_factor_builders.py` 성공.
  - `npm run test`: `25 passed in 1.06s`.
  - CRLF verifier: 두 배치 모두 bare LF 0, `chcp`, `exit /b 0` 확인.
  - Ad-hoc verifier: 자동화 레지스트리/lock/배치 marker 확인 PASS.
- Caveats:
  - Claude가 DART 재무/DB/web 산출물을 lock 중이라 DB-writing 작업(DART/월간/전체팩터 재실행)은 추가 수동 실행하지 않음.
  - `QuantMonthly_0600`의 스케줄러 trigger 수정은 권한 거부로 남음. 관리자 권한 터미널 또는 Task Scheduler GUI에서 월간 1일 06:00 recurring trigger로 재등록 필요.

## 2026-06-29 08:20 - Hermes
- Task: GitHub Actions `Daily ETL + Deploy`의 `Install Dependencies` 실패 원인 수정.
- Changed:
  - `requirements.txt`: PyPI 배포명 오기 `FinanceDataReader` → `finance-datareader`로 수정. Python import명 `FinanceDataReader`는 그대로 유지.
- Created:
  - 없음.
- Verification:
  - `python -m pip install -r requirements.txt` 성공. `finance-datareader installed: 0.9.202`, `import FinanceDataReader: OK` 확인.
  - `npm run test` 성공: `25 passed in 1.13s`.
- Caveats:
  - 현재 Claude가 `data/database/quant_data.sqlite`, `web/quant_data.js` 등을 lock 중이라 DB/웹 산출물은 수정하지 않음.
  - 커밋/푸시는 사용자 명시 지시가 없어 수행하지 않음.

## 2026-06-28 23:18 - Hermes
- Task: 실시간/준실시간 분봉 확인이 가능해질 때까지 페이퍼 트레이딩 시작 중지.
- Actions:
  - `QuantPaperTradingDaily_1Week`, `QuantPaperTradingDaily_4Week` 비활성화(Disabled).
  - Paper DB tables는 0 rows 상태 유지 확인.
  - 현재 `QuantMinuteTick_1540`는 15:30 1회 수집이며 장중 실시간 monitor가 아님을 확인.
- Created:
  - `docs/paper_trading_realtime_readiness_plan.md`: 5분 polling 기반 장중 watchlist/position 감시 구현 작업 목록, 신규 스크립트/배치/스케줄러/웹/검증 계획 정리.
- Registry:
  - `C:/claude cowork/00_context/automation_list.md`에서 1주/4주 paper tasks 상태를 Disabled로 반영.
- Verification:
  - Task Scheduler Disabled 상태, paper table zero counts, 계획서/레지스트리/changelog marker를 ad-hoc verifier로 확인.

## 2026-06-28 23:05 - Hermes
- Task: 페이퍼 트레이딩 예약작업을 백그라운드 운영에 맞게 보강.
- Changed scheduler settings:
  - `QuantPaperTradingDaily_1Week`
  - `QuantPaperTradingDaily_4Week`
  - `StartWhenAvailable=True`, `MultipleInstances=IgnoreNew`, `ExecutionTimeLimit=PT2H`, 배터리 중단 방지.
- Verification:
  - PowerShell `Get-ScheduledTask`로 두 작업 settings/action/workdir/next run 확인.
  - Ad-hoc verifier 실행.

## 2026-06-28 23:00 - Hermes
- Task: 1주 페이퍼 트레이딩을 진행 상태로 유지하고, 이어서 4주 후속 운영을 계획/예약 등록.
- Created:
  - `docs/paper_trading_4week_plan.md`: 1주 드라이런 목적, 4주 운영 기간, WATCH/BUY/REJECT 규칙, 평가 항목, 한계/다음 단계 정리.
- Automation:
  - 기존 `QuantPaperTradingDaily_1Week`: 2026-06-29~2026-07-05 매일 09:05 유지.
  - 신규 `QuantPaperTradingDaily_4Week`: 2026-07-06~2026-08-02 매일 09:05 등록. Action=`run_paper_trading_daily.bat`, workdir 프로젝트 루트, 실주문 없음.
- Registry:
  - `C:/claude cowork/00_context/automation_list.md`에 4주 작업 추가.
- Verification:
  - PowerShell `Get-ScheduledTask/Get-ScheduledTaskInfo`로 두 작업 action/workdir/start/end/next run 확인.
  - Ad-hoc verifier로 계획서/레지스트리/changelog/스케줄러 상태 확인.

## 2026-06-28 23:55 - Claude
- Task: 실전 백테스트 탭 "최근 리밸런싱 종목" 테이블 UI 정리 (티커→종목명 통합)
- Changed:
  - `web/quant_ui.js`: `renderPracticalBacktestSelections` 함수 수정
    - `ticker` 코드 컬럼 제거
    - `name` 종목명 컬럼에 티커 코드를 회색 소자(`<small>`)로 통합 표시
    - `sector` 컬럼에서 종목명과 동일한 값이면 "—"로 표시 (중복 제거)
- Verification:
  - 브라우저 실전 백테스트 탭 → 최근 리밸런싱 종목 테이블: 종목명+코드 소자 정상 표시, 섹터 중복 "—" 처리 확인 ✅

## 2026-06-28 22:46 - Hermes
- Task: 페이퍼 트레이딩 1차 데이터 쌓기 방식을 즉시 매수에서 WATCH 우선으로 변경하고 오늘 검증용 매수 기록 초기화.
- Changed:
  - `scripts/04_trade/paper_trading_engine.py`: 신규 후보는 기본 `WATCH`; `BUY_PULLBACK_FILLED`/`BUY_BREAKOUT_FILLED` 조건 충족 시만 가상 매수; `REJECT_OVEREXTENDED`, `REJECT_LOW_LIQUIDITY`, `WATCH_FLOW_CONFIRM`, `WATCH_BREAKOUT`, `WATCH_PULLBACK` reason 기록.
  - `tests/test_paper_trading_engine.py`: WATCH 기본 동작, 눌림목 BUY, 돌파 BUY, 과열 REJECT, 동일일 재실행 idempotency 테스트로 갱신.
  - `C:/claude cowork/00_context/automation_list.md`: `QuantPaperTradingDaily_1Week` 시작 시각을 2026-06-29 09:05로 변경.
- Reset:
  - 오늘 검증용 paper tables/CSV/JSON 초기화 완료: `paper_account_daily`, `paper_positions`, `paper_orders`, `paper_decisions`, `paper_trades` 모두 0 rows.
  - `export_web_data.py` 재실행 후 `web/quant_data.js`의 `paper_trading` payload도 빈 상태 반영.
- Automation:
  - `QuantPaperTradingDaily_1Week`: 2026-06-29~2026-07-05 매일 09:05, 동시호가 종료 후 시작, 실제 주문 없음.
- Verification:
  - RED: 신규 WATCH/BUY/REJECT tests → 기존 즉시매수 로직에서 5 failures 확인.
  - GREEN: `python -m pytest tests/test_paper_trading_engine.py -q` → 7 passed.
  - 이후 canonical/web/scheduler/ad-hoc 검증 실행.

## 2026-06-28 22:24 - Hermes
- Task: 1주일 페이퍼 트레이딩 시작
- Created:
  - `scripts/04_trade/paper_trading_engine.py`: 팩터 마스터 최신월 + 데이터 신뢰도 기반 가상 매수/보유/청산 엔진. 실제 주문 없음.
  - `tests/test_paper_trading_engine.py`: 후보 필터, 가상 매수, 가격 결측 거부 테스트.
  - `run_paper_trading_daily.bat`: paper engine → web export → `npm run test`.
- Changed:
  - `scripts/03_analyze/export_web_data.py`: `paper_trading` payload 추가.
  - `web/index.html`, `web/quant_ui.js`: 종목분석 > 모의투자 탭/렌더러 추가.
  - `package.json`: paper trading engine/test를 canonical `npm run test`에 포함.
  - `C:/claude cowork/00_context/automation_list.md`: `QuantPaperTradingDaily_1Week` 등록 정보 추가.
- Run result:
  - 최초 수동 paper run: BUY 5건, open_positions=5, initial_cash=10,000,000, equity=9,996,132.80, cumulative_return=-0.0387% (수수료/슬리피지 반영).
  - 산출물: `data/raw/paper_trading/*.csv`, `paper_summary.json`, SQLite `paper_*` 테이블.
- Automation:
  - `QuantPaperTradingDaily_1Week`: 2026-06-29~2026-07-05 매일 18:45, action=`run_paper_trading_daily.bat`, workdir 프로젝트 루트.
  - 수동 `Start-ScheduledTask` 실행 완료, LastTaskResult=0.
  - 동일일 재실행 idempotent 보정 후 paper table reset→재실행, scheduler 재검증 LastTaskResult=0.
- Verification:
  - RED 확인: 신규 test가 `paper_trading_engine.py` 없음으로 실패.
  - GREEN: `python -m pytest tests/test_paper_trading_engine.py -q` → 3 passed.
  - `python ...paper_trading_engine.py && python ...export_web_data.py && npm run test` → 22 passed.
  - Task Scheduler 수동 실행 → LastTaskResult=0.
- Caveats:
  - 현재는 자체 페이퍼 트레이딩이며 증권사 모의계좌/실주문 API 미사용.
  - 가격은 최신 factor master의 월간 close를 사용하므로 장중 실시간 체결 시뮬레이션이 아니라 장후/스윙형 모의투자.

## 2026-06-28 21:35 - Hermes
- Task: 월간 팩터/매크로가 6/1에 멈춘 것처럼 보이는 원인 점검
- Findings:
  - `factor_*_month` 계열의 `2026-06-01`은 미갱신이 아니라 월간 period bucket을 월초 날짜로 표준화한 6월 데이터 표기.
  - 일간 매크로/시장 원천은 `macro_quant_indicators_long`, `macro_global_indices_daily` 기준 2026-06-26까지 갱신됨.
  - `macro_quant_factors_monthly`는 2026-06-30까지 생성됨.
  - 일부 공식 월간 지표(PPI/무역/미국 월간 FRED)는 원천 공표 지연으로 2026-05 또는 2026-04가 최신인 것이 정상 범위.
  - `QuantMonthly_0600`은 다음 실행일이 2026-07-02라 아직 실행된 적 없었고, WorkingDirectory가 비어 있었음.
- Changed:
  - `run_monthly.bat`: CRLF, `chcp 65001`, `setlocal/endlocal`, `env.bat` 출력 suppress, 성공 `exit /b 0` 보강.
  - `QuantMonthly_0600`: 배치 직접 실행 + `WorkingDirectory=C:\claude cowork_projects\Anal_reports`로 재등록.
  - `C:\claude cowork _contextutomation_list.md` 갱신.
- Verification:
  - DB freshness scan: 주요 월간 팩터 max period 2026-06-01, factor master max period 2026-06, daily macro/source max date 2026-06-26, quant monthly factors max date 2026-06-30.
  - Task Scheduler check: `QuantMonthly_0600` Ready, NextRun=2026-07-02 06:00, action/workdir 정상.
  - 별도 ad-hoc verifier로 배치 CRLF/마커, 자동화 목록 row, Task Scheduler 상태 확인 예정/완료.
- Caveat:
  - 월간 전체 파이프라인은 다음 월간 트리거 대기 상태이며, 장시간 DART/전체 수집을 포함하므로 이번 점검에서는 원인 확인과 예약작업 보정 중심으로 처리.

## 2026-06-28 23:05 — 월간 팩터 staleness latest_date 영업일 표기 수정

**변경 파일**
- `scripts/03_analyze/build_factor_master_panel.py` — `build_source_staleness_report` 내 `_month` 팩터 `latest_date` 계산 수정

**수정 내용**
- `period` 컬럼 기반 팩터(`momentum/flow/valuation/sector_value`)는 기존에 `2026-06-01`(월 첫날)을 그대로 `latest_date`로 표시
- 수정 후: `min(해당 월 마지막 영업일, 오늘)` → 현재 월이면 오늘(2026-06-28) 표시

**검증**
- `factor_source_staleness.csv`: momentum/flow/valuation/sector_value 모두 `latest_date=2026-06-28`, `age_days=0.0` ✅
- `export_web_data.py` 재실행 → `quant_data.js` 재생성 완료

**주의**
- 다음 달 run_monthly 실행 전까지 월말 영업일이 아직 안 지난 경우 `as_of`(오늘)로 표시됨
- 7월 이후에는 `2026-07-마지막영업일` 형태로 자동 갱신됨

---

## 2026-06-28 21:35 — run_monthly.bat 미자동화 수집 5종 추가 + DART 재무제표 전용 배치

**변경 파일**
- `run_monthly.bat` (5개 단계 추가)
- `run_dart_finstate.bat` (신규)

**추가된 단계 (run_monthly.bat)**
- `[2b/13]` collect_naver_datalab_once.py — DataLab 섹터/테마 검색 트렌드
- `[3b/13]` collect_barley_sorghum_supplements_once.py — 보리/수수 보조 데이터
- `[5b/13]` collect_shorting_balance_once.py — 공매도 잔고 월말 집계
- `[7c/13]` collect_dart_insider_trading_once.py — 내부자 거래 (임원/주요주주 소유보고)
- `[7d/13]` collect_us_korea_trade_once.py — 미한 무역통계 (FRED)

**신규 배치: run_dart_finstate.bat**
- DART 재무제표 432종목 수집 (~30-60분) → 팩터 재빌드 → export
- 별도 실행 필요 (소요시간이 길어 run_monthly와 분리)
- 스케줄러 QuantDartFinstate_0200 등록은 사용자 직접 진행 필요

**완전 자동화 현황 (추가 후)**
- 일간: 글로벌지수·ADR·외국인소진율·고객예탁금 / 분봉 / 뉴스·리포트 / 컨센서스리비전
- 월간(QuantMonthly_0600 자동 실행): KRX스냅샷 + 섹터ETF + 매크로 + DataLab + 곡물/비철/보리수수 + 수급 + 공매도잔고 + 팩터빌드 + PPI/무역 + 내부자거래 + 미한무역 + ADR + 컨센서스 + DART공시 + IC리포트 + export
- 4주1회(등록 필요): DART 재무제표 (run_dart_finstate.bat)

---

## 2026-06-28 21:10 — run_monthly.bat KRX 스냅샷 수집 단계 추가

**변경 파일**
- `scripts/01_collect/collect_krx_market_snapshot.py` (신규 — scratch 스크립트 정식화)
- `run_monthly.bat` (0단계 추가)

**변경 내용**
- `collect_krx_market_snapshot.py`: scratch/collect_krx_market_snapshot_20260605.py를 정식 스크립트로 이동
  - 최근 영업일 자동 감지 (KS11 기준)
  - KOSPI/KOSDAQ: ohlcv, fundamental, market_cap, foreign_exhaustion 4종 CSV 저장
  - ticker_names CSV 저장
  - 실패 시 계속 진행 (개별 FAIL 출력)
- `run_monthly.bat` 0단계 삽입: `[0/13] KRX 시장 스냅샷 수집`

**검증**
- `python -c "import py_compile; py_compile.compile('scripts/01_collect/collect_krx_market_snapshot.py')"` 통과

---

## 2026-06-28 21:00 — stock_attractiveness 최신화 (KRX 스냅샷 수집 + 웹 데이터 재생성)

**변경 파일**
- `data/raw/stock_market_snapshot/kospi_market_cap_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/kospi_fundamental_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/kospi_ohlcv_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/kospi_foreign_exhaustion_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/kosdaq_market_cap_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/kosdaq_fundamental_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/kosdaq_ohlcv_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/kosdaq_foreign_exhaustion_by_ticker_20260626.csv` (신규)
- `data/raw/stock_market_snapshot/ticker_names_20260626.csv` (신규)
- `web/quant_data.js` (재생성)

**실행 내용**
1. run_monthly.bat 파이프라인: 1~12단계 (팩터 빌드) 완료
   - factor_master_month: 15374 rows / 432 tickers / 37 periods (max 2026-06)
   - IC 리포트: 14팩터, decay_warning=2개 (valuation/small_cap)
2. KRX 스냅샷 수집 (scratch/collect_krx_market_snapshot_20260605.py 재활용):
   - 최신 영업일: 20260626 (KOSPI 946, KOSDAQ 1822, ticker_names 2768)
3. export_web_data.py 재실행 → quant_data.js 재생성

**검증 결과**
- `as_of`: 2026-06-05 → **2026-06-26** 업데이트 ✅
- stock_attractiveness: 2,770 종목 최신 팩터 반영

**주의사항**
- KRX 스냅샷 수집 스크립트가 run_monthly.bat에 미포함 — 월간 실행 시 수동으로 먼저 실행 필요
- 로그 인코딩 오류(CP949 환경)로 배치 출력이 깨지나 실행 자체는 정상

---

## 2026-06-28 20:30 — 데이터 신선도 수정 (yfinance v2 파싱 + TNX→DGS10 + CLI 라벨)

**변경 파일**
- `scripts/03_analyze/export_web_data.py`
- `web/quant_ui.js`
- `web/quant_data.js` (재생성)

**수정 내용**

1. **yfinance v2 3행 헤더 파싱 수정** (`export_web_data.py`)
   - 신규: `_is_yfinance_v2_csv()` — 파일 첫 줄이 `Price,`로 시작하면 yfinance v2 감지
   - 신규: `_records_from_yfinance_v2_csv()` — header=None 읽기 후 행1 컬럼명 적용, 행4+를 데이터로
   - `macro_files` 루프에서 yfinance v2 CSV 분기 처리 추가
   - `_compute_derived_macro._load()` 함수도 동일 방식으로 수정
   - 영향 파일: `DXY.csv`, `VIX.csv`, `SOXX.csv`, `EEM.csv`, `TNX.csv` (3행 헤더)

2. **TNX → DGS10 대체** (`quant_ui.js`)
   - 차트: `macroData.TNX` → `macroData.DGS10 || macroData.TNX` fallback
   - 스코어카드: `tnx = latestValue(macro.DGS10, "DGS10") ?? latestValue(macro.TNX, "Close")`
   - DGS10 최신: 2026-06-25 (TNX는 2026-06-18에서 끊김)

3. **OECD CLI 갱신 중단 라벨** (`quant_ui.js`)
   - CLI 차트 렌더링 직전 `insertAdjacentHTML("beforebegin", ...)` 로 주황색 안내 삽입
   - 문구: "⚠️ OECD CLI: FRED 원천 갱신 중단 (2024-01-01 이후 업데이트 없음). 최신 경기 동향은 BSI / CCSI / PMI 등 대체지표를 참고하세요."

**검증 결과**
- DXY: 2514 rows, 마지막 날짜 2026-06-26 ✅ (이전: "Ticker" 오류)
- VIX: 2515 rows, 마지막 날짜 2026-06-26 ✅
- DGS10: 12127 rows, 마지막 2026-06-25, 값 4.4 ✅
- SOXX/EEM 상대강도: 121 rows 복구 ✅ (이전: _load 예외로 0 rows)
- CLI 라벨: 주황색 텍스트 정상 표시 ✅
- CLI 차트: 9개 그려짐 ✅

**주의사항**
- OECD CLI 데이터는 2024-01-01 이후 FRED 원천 미갱신 상태 유지. 데이터 자체는 삭제하지 않음.
- TNX.csv는 allowlist에 유지 (fallback용). 수집 스크립트 점검은 별도 작업.

---

## 2026-06-28 18:03 - Hermes
- Task: 원천 데이터 수집 자동화 실패 상태 점검 및 조치
- Problem:
  - `QuantDailyMarket_1610`, `QuantDailyNews_1700`, `QuantMinuteTick_1540` LastTaskResult가 각각 1/1/255였음.
  - 배치 파일이 LF-only 상태였고 Task Scheduler action이 `cmd.exe /c ...` + 빈 working directory라 경로/인코딩 취약성이 있었음.
- Changed:
  - `run_daily_market.bat`, `run_daily_news.bat`, `run_collect_minute_tick.bat`: CRLF로 재작성, `chcp 65001`, `setlocal/endlocal`, 명시적 `exit /b 0`, env 로딩 stderr/stdout suppress, 단계별 errorlevel 처리 보강.
  - 세 Windows Task Scheduler 작업을 배치 파일 직접 실행 + `WorkingDirectory=C:\claude cowork_projects\Anal_reports`로 재등록.
  - `C:\claude cowork _contextutomation_list.md` 갱신.
- Verification:
  - 세 작업 순차 `Start-ScheduledTask` 실행 완료.
  - `QuantDailyMarket_1610`: LastTaskResult=0, LastRun=2026-06-28 17:49:48.
  - `QuantDailyNews_1700`: LastTaskResult=0, LastRun=2026-06-28 17:57:03.
  - `QuantMinuteTick_1540`: LastTaskResult=0, LastRun=2026-06-28 18:00:58.
  - `npm run test` → 18 passed.
  - DB/file spot check: market funds/kr_adl/kr_trin mtimes 갱신, news sentiment 432 rows, minute tick 57 rows, ADR 33184 rows, foreign exhaustion 2768 rows.
  - scoped `git diff --check` for the three bat files passed.
- Caveats:
  - 2026-06-28은 일요일이라 분봉 원천은 0/395 신규 수집이 정상일 수 있음. 기존 2026-06-24 분봉 히스토리 57종목으로 팩터/웹 export는 성공.

## 2026-06-28 17:34 - Hermes
- Task: 최신 데이터 기준 전체 팩터 재빌드 및 데이터 업데이트 후 자동 팩터 업데이트 등록
- Changed/Created:
  - `scripts/03_analyze/run_all_factor_builders.py`: 전체 `build_*factor*.py` 실행 후 팩터 마스터, IC 리포트, 웹 export를 순차 실행하는 오케스트레이터 추가.
  - `run_all_factor_update.bat`: 전체 팩터 업데이트 + `npm run test` 배치 추가.
  - `scripts/03_analyze/build_dart_event_signal_factors.py`: legacy DART 이벤트 파일에 `event_type`이 없을 때 `report_nm`으로 재분류하고, aggregate CSV를 ticker로 오인하지 않도록 수정.
  - `package.json`: canonical test의 py_compile 대상에 신규 오케스트레이터와 DART 이벤트 팩터 빌더 포함.
  - Windows Task Scheduler `QuantAllFactorsDaily`: 매일 18:20 등록.
  - `C:\claude cowork _contextutomation_list.md`: 자동화 목록 갱신.
- Outputs:
  - 전체 팩터 재빌드 완료: `ALL_FACTOR_UPDATE_STATUS=OK`
  - `factor_master_month`: 15,374 rows, latest 2026-06, 432 tickers
  - `factor_data_quality_month`: 15,374 rows
  - `factor_source_staleness`: 7 rows
  - `factor_adr_gap_signal_daily`: 33,168 rows
  - `factor_dart_event_signal_month`: 5,499 rows
  - `factor_disclosure_event_month`: 23,166 rows
  - `factor_consensus_revision_snapshot`: 620 rows
  - `factor_ic_summary`: 14 rows
- Verification:
  - `python -X utf8 scripts/03_analyze/run_all_factor_builders.py` → OK, log `logs/all_factor_update_20260628_172824.log`
  - `QuantAllFactorsDaily` 수동 실행 → LastTaskResult=0
  - `npm run test` → 18 passed
  - DB spot check row counts/latest period 통과
- Caveats:
  - Windows Scheduler 조회 기준 `QuantDailyMarket_1610`, `QuantDailyNews_1700`, `QuantMinuteTick_1540`의 LastResult가 각각 1/1/255로 남아 있어 원천 수집 자동화의 일부 실패는 별도 점검 필요. 전체 팩터 업데이트 자동화 자체는 성공.

## 2026-06-28 17:10 - Hermes
- Task: 데이터 신뢰도/스테일니스 대시보드 웹 가시성 수정
- Changed:
  - `web/index.html`: 퀀트 사이드바에 `데이터 신뢰도` 전용 서브탭 추가, 전용 대시보드 패널 추가
  - `web/quant_ui.js`: `renderDataQualityDashboard()` 추가, 탭 전환 시 전용 대시보드 렌더링 연결
- Verification:
  - `npm run test` → 18 passed
  - `node --check web/quant_ui.js` 및 scoped `git diff --check` 통과
  - Puppeteer: 퀀트 메뉴에 `데이터 신뢰도` 버튼 표시, 전용 패널 active, cards 5/source rows 7/stock rows 50, payload source 7/quality 432, page errors 0
  - Task Scheduler `QuantDataQualityStalenessDaily` 확인: Ready, LastResult=0, NextRun=2026-06-28 21:20
- Note:
  - 기존에는 팩터 마스터 패널 하단에만 붙어 있어 사용자가 별도 대시보드로 찾기 어려웠음. 이제 퀀트 → 데이터 신뢰도 전용 탭에서 바로 확인 가능.

## 2026-06-28 16:56 - Hermes
- Task: 데이터 신뢰도/스테일니스 대시보드 및 종목 스코어 품질 페널티 반영
- Changed/Created:
  - `scripts/03_analyze/build_factor_master_panel.py`: 최신일자 지연, 스냅샷 노후화, 종목별 결측률, source failure, stale penalty, `data_quality_penalty`, `factor_coverage_score`, `usable_for_trading_flag` 확장. 뉴스 3일 초과 stale 시 감성 점수 영향 축소, 분봉 당일 데이터 미존재 시 minute 사용 금지, 목표주가 스냅샷 노후 시 신뢰도 하향 규칙 추가.
  - `scripts/03_analyze/export_web_data.py`: `factor_source_staleness` 및 품질 요약 payload export.
  - `web/index.html`, `web/quant_ui.js`: 팩터 마스터 패널에 데이터 신뢰도/스테일니스 대시보드 추가.
  - `tests/test_factor_master_panel.py`: source staleness, data quality penalty, export payload 테스트 추가.
  - `run_data_quality_staleness.bat`: 품질 대시보드 갱신 배치 추가.
  - Windows Task Scheduler `QuantDataQualityStalenessDaily`: 매일 21:20 등록.
  - `C:\claude cowork _contextutomation_list.md`: 자동화 목록 갱신.
- Outputs:
  - `factor_master_month`: 15,374 rows, latest 2026-06 432 tickers
  - `factor_data_quality_month`: 15,374 rows
  - `factor_source_staleness`: 7 rows
  - latest quality summary: avg_data_quality_penalty 0.1473, usable_for_trading 376/432, source_failure_rows 251, stale_factor_rows 159
- Verification:
  - `npm run test` → 18 passed
  - `node --check web/quant_ui.js` 통과
  - DB row/source staleness spot check 통과
  - Puppeteer: 팩터 마스터 탭 cards 6/source rows 7/quality rows 30/health rows 7/page errors 0
  - `QuantDataQualityStalenessDaily` 수동 실행 LastTaskResult=0
- Caveats:
  - 2026-06-28은 일요일 기준이라 분봉 최신일 2026-06-24는 당일 데이터 미존재로 source failure 처리됩니다. 거래일 장중/장후 수집이 정상화되면 자동으로 해소됩니다.

## 2026-06-28 16:10 - Claude
- Task: 포지션 사이징 레이어 + 팩터 IC 붕괴 경보 구축
- 수정 파일:
  - `scripts/03_analyze/build_factor_ic_report.py`: [신규] 14개 팩터 Spearman IC 자동 검증. monthly 37기간, summary 14팩터. decay_warning: valuation_score(IC_3m=-0.053), small_cap_score(IC_3m=-0.155)
  - `scripts/03_analyze/export_web_data.py`: `_build_factor_master_payload()` return dict에 `ic_summary`/`ic_monthly` 추가
  - `web/index.html`: 종목분석 nav에 "포지션 사이징" sub-tab 추가, `sub-analysis-position-sizing` 콘텐츠 div 추가, 팩터 심사표에 `fv-ic-decay` 섹션+앵커 추가
  - `web/quant_ui.js`: `renderPositionSizing()` 추가 (계좌설정 입력→손절가/제안비중 자동계산, 섹터집중도 경고), `renderFactorIcDecay()` 추가 (IC 붕괴 경보 테이블), switchSubTab 핸들러+DOMContentLoaded 호출 추가
  - `run_monthly.bat`: `[12b/13]` 팩터 IC 리포트 빌드 단계 추가
  - `web/quant_data.js`: export_web_data.py 재실행으로 재생성 (ic_summary 14행/ic_monthly 37행 포함)
- 검증 명령:
  - `node --check web/quant_ui.js`
  - 브라우저: `renderPositionSizing()` → Top20 테이블 20행/요약카드 4개. 대신증권(003540) 30,000원→손절 27,600원(-8%)/비중 12.5%(625만원)
  - `renderFactorIcDecay()` → 14행, valuation_score/small_cap_score ⚠️ 붕괴 표시
- 결과: ic_summary 14팩터 검증, decay 2건 경보, 포지션 사이징 Top20 정상 계산
- 주의: 포지션 사이징은 `stock_attractiveness.rows`(2770행) 기반이므로 유니버스 필터 별도 미적용. price 필드는 월간 종가 기준

## 2026-06-28 15:40 - Claude
- Task: Web UI 진입 타이밍 시나리오 4종 표시 추가
- 수정 파일:
  - `web/quant_ui.js`: `STOCK_SCENARIOS`에 4개 추가, `ENTRY_TIMING_KEYS` Set 정의, `renderScenarioToggles` 수정 (구분선+배지), `scenarioFactorKeys` 매핑 추가
  - `web/index.html`: `stock-filter-sort` + `action-candidate-sort` select에 진입 타이밍 optgroup + 4개 option 추가
  - `scripts/03_analyze/export_web_data.py`: `compact_factor_profile`에 7개 신규 팩터 키 추가 (news_sentiment/minute_tick/insider_signal/target_price/shorting_pressure/shareholder_return_event)
  - `web/quant_data.js`: export_web_data.py 재실행으로 재생성
- 검증:
  - `node --check quant_ui.js` 통과
  - quant_data.js factor_profile 신규 키 16종 확인 (news_sentiment 432/minute_tick 57/insider_signal 396/target_price 1853/shorting_pressure 250/shareholder_return_event 429)
  - 브라우저 검증: "단타/스윙 진입 타이밍" 구분선 표시, 눌림목 반등 클릭 → "진입 타이밍" 배지 + 설명 + 팩터 태그 렌더링, 1위 에스티큐브(052020) 49.9점 표시
- 주의: 진입 타이밍 4개 시나리오는 별도 백테스트 요약 없음 (해당 안내 문구 자동 표시됨)

## 2026-06-28 15:03 - Claude
- Task: 단타/스윙 진입 타이밍 시나리오 4종 추가
- 수정 파일: `scripts/03_analyze/export_web_data.py`
  1. **table_specs 5종 추가** (신규 팩터 테이블 로드):
     - `factor_consensus_revision_snapshot`: target_price_score, revision_acceleration_score
     - `factor_minute_tick_snapshot`: minute_tick_score, buy_print_ratio_30m
     - `factor_news_sentiment_snapshot`: news_sentiment_score
     - `factor_insider_trading_month`: insider_signal_score
     - `factor_disclosure_event_snapshot`: shareholder_return/dilution_risk/governance_risk_score
  2. **rec 신규 필드 9개** (stock_attractiveness rows에 추가):
     - news_sentiment_score, minute_tick_score, buy_print_ratio_30m
     - insider_signal_score, target_price_score, strong_swing_candidate_flag
     - shareholder_return_event_score, dilution_risk_score, governance_risk_score
  3. **신규 시나리오 4종**:
     - `pullback_rebound_score`: 눌림목 반등 (momentum×0.3 + meanrev×0.3 + flow×0.2 + news×0.1 + tick×0.1)
     - `breakout_continuation_score`: 신고가 돌파 (momentum×0.35 + flow×0.25 + liquidity×0.15 + tick×0.15 + news×0.1)
     - `short_squeeze_candidate_score`: 쇼트스퀴즈 (shorting×0.35 + mom×0.25 + news×0.15 + flag×0.15 + tick×0.1)
     - `turnaround_recovery_score`: 실적 턴어라운드 (earnings×0.3 + tp_score×0.25 + valuation×0.2 + insider×0.15 + buyback×0.1)
- export_web_data.py 재실행 → `web/quant_data.js` 재생성
- 검증 결과:
  - pullback_rebound: non-null 433종목, 0.292~0.755
  - breakout_continuation: non-null 433종목, 0.245~0.772
  - short_squeeze_candidate: non-null 2770종목, 0.000~0.761
  - turnaround_recovery: non-null 945종목, -0.145~1.000
- 주의:
  - minute_tick_score는 관심종목 57개만 커버 → 비관심종목은 가중평균에서 제외됨
  - turnaround 음수(-0.14)는 valuation_score 기존 범위(-1.0~1.0) 특성으로 정상
  - UI 통합(4개 시나리오를 웹 대시보드에 표시)은 별도 작업 필요

## 2026-06-28 14:46 - Claude
- Task: ㊺ 공시 이벤트 품질 팩터 수집 완료 + 팩터 빌드 완료 (v2 — per-ticker 전략)
- 전략 변경:
  - 기존: `kind_detail` bulk 수집 → DART 3개월 제한으로 전량 0건 실패
  - 신규: per-ticker `dart.list(corp=ticker, kind='B')` + `dart.list(corp=ticker, kind='I')`
    - kind='B' (주요사항보고서): buyback/seasoned_eq/cb/bw + report_nm 키워드 필터
    - kind='I' (거래소공시): max_shareholder/unfair_disc + report_nm 키워드 필터
- 수정 파일:
  - `scripts/01_collect/collect_dart_disclosure_events.py` — 전면 재작성 (per-ticker 전략)
    - `collect_bulk_events()` 제거 (broken)
    - `collect_major_events()` 추가 (kind='B' per-ticker)
    - `collect_governance_events()` 수정 (kind='I' per-ticker, 기존: no-kind-filter)
    - `--skip-major`, `--skip-governance` 플래그
  - `scripts/03_analyze/build_disclosure_event_factors.py` — `discover_tickers()` 6자리 숫자 필터 추가 (비표준 ticker 제외)
- 수집 결과 (DB: dart_disclosure_events 1031행):
  - major events (kind='B', 432종목): buyback 291건 / seasoned_eq 205건 / cb 151건 / bw 35건
  - governance (kind='I', 432종목): max_shareholder 158건 / unfair_disc 191건
- 팩터 빌드 결과:
  - factor_disclosure_event_month: 23,166행 / 429종목 / 2022-01 ~ 2026-06
  - factor_disclosure_event_snapshot: 429종목 (2026-06-01)
  - 5개 팩터 non-null: 각 429종목 full coverage
- 검증: `pytest tests/test_disclosure_event_factors.py -v` → **13/13 passed** ✓
- 주의:
  - 배당결정/capex/contract는 kind='B'에 해당 종목 없음 (향후 kind='I' 등으로 보완 가능)
  - 비표준 ticker (000155, 0009K0, 00680K 등 우선주)는 DART에서 "could not find" → 정상 스킵
  - governance (kind='I') per-ticker 재실행 시 ~9분 / major (kind='B') per-ticker ~7분 소요

## 2026-06-28 13:00 - Claude
- Task: ㊺ 공시 이벤트 품질 팩터 신규 구축 (스크립트 작성)
- 생성 파일:
  - `scripts/01_collect/collect_dart_disclosure_events.py` — OpenDART DS005 bulk 수집 (A001/A003/A004/A005/A009/A013/A014/A022/A042/A043) + governance 키워드 per-ticker
  - `scripts/03_analyze/build_disclosure_event_factors.py` — 5 factor scores (rolling 12m → cross-section percentile)
  - `tests/test_disclosure_event_factors.py` — 12개 pytest 테스트
- 수정 파일:
  - `run_monthly.bat`: 스텝 11b 추가 (collect --skip-governance + build)
  - `00_context/index_factor.md`: ㊺ 추가
- 출력 DB 테이블 (수집 후 생성):
  - `dart_disclosure_events` — 원본 공시 이벤트 (rcept_no PK)
  - `factor_disclosure_event_month` — 종목×월간 5 scores
  - `factor_disclosure_event_snapshot` — 최신 단면
  - `factor_disclosure_event_catalog` — 팩터 메타
- 5 factor scores:
  - `shareholder_return_event_score` (A001/A003/A004/A005)
  - `dilution_risk_score` (A009/A013/A014)
  - `capex_growth_event_score` (A022)
  - `contract_win_event_score` (A042/A043)
  - `governance_risk_score` (최대주주변경/불성실공시/감사의견이슈 키워드)
- 검증:
  - py_compile 3개 파일 통과 ✓
  - 수집 실행: `python scripts/01_collect/collect_dart_disclosure_events.py` (초기 실행 ~15분)
  - 팩터 빌드: `python scripts/03_analyze/build_disclosure_event_factors.py`
  - 테스트: `pytest tests/test_disclosure_event_factors.py -v` (수집 후)
- 주의:
  - `governance` 수집 (per-ticker 432종목 × DART API)은 --skip-governance 없이 실행 시 ~2-3분 추가 소요
  - 초기 bulk 수집 (2022~현재, 10 event types × 5년 = 50 API 호출)은 약 5-10분 소요
  - `dart_disclosure_events` 테이블은 upsert 방식이므로 재실행 시 중복 없이 갱신

## 2026-06-28 12:40 - Claude
- Task: run_hermes_bot.bat 실행 불가 진단 및 수정
- Root Cause:
  1. `\HermesBotDiscord` + `\Anal_reports_HermesBot` 두 Task가 동시에 7:47에 실행 → Discord 토큰 충돌 → 양쪽 255 실패
  2. Task Scheduler `cmd.exe /c "경로에 공백\run_hermes_bot.bat"` — cmd가 공백 있는 따옴표 경로 파싱 실패
- Fixed:
  - `\HermesBotDiscord` Task 삭제 (중복 제거)
  - `\Anal_reports_HermesBot` Task 재등록: cmd.exe 래퍼 제거 → Python 직접 실행
    - Program: `C:\Users\fckin\AppData\Local\Programs\Python\Python311\python.exe`
    - Arguments: `-X utf8 scripts\05_notify\hermes_bot.py`
    - WorkingDirectory: `C:\claude cowork\01_projects\Anal_reports`
  - `run_hermes_bot.bat`: `python` → 전체 경로로 변경 (수동 실행 안정성)
- Verification:
  - `schtasks /run /tn "\Anal_reports_HermesBot"` → PID 6780 실행 중, lock 생성, Discord Gateway 연결 ✓
- 주의사항:
  - 재시작 루프(`goto loop`)가 Task Scheduler 방식에서는 없음 — 봇 crash 시 자동 재시작 안됨
  - 필요 시 run_hermes_bot.bat 더블클릭으로 재시작 루프 포함 수동 실행 가능

## 2026-06-28 11:55 - Claude
- Task: collect_kr_trade_kosis.py — KOR_EXPORTS.csv 자동 동기화 추가
- Changed:
  - `scripts/01_collect/collect_kr_trade_kosis.py`:
    - 상수 추가: `MACRO_INDICES_DIR = PROJECT_ROOT / "data/raw/macro/macro_indices"`
    - 함수 추가: `sync_kor_exports_csv(df)` — korea_exports_total 시리즈를 KOR_EXPORTS.csv에 동기화
      - ECOS 천불 × 1000 → USD 변환 후 기록
      - 기존 CSV 보존 (1980~1999 FRED 데이터 유지), 2000~ 이후 ECOS 값으로 덮어쓰기
      - 헤더 `DATE,XTEXVA01KRM667S` 유지
    - `main()`: `save_to_db()` 후 `sync_kor_exports_csv()` 호출 추가
- Verification:
  - `py_compile` 통과 ✓
  - 스크립트 실행: 951행 DB 갱신, KOR_EXPORTS.csv 0행 추가(기존과 동일 max=2026-05-01) ✓
  - CSV 최종: 558줄(헤더+557행), max=2026-05-01, 값=87,821,386,000 USD ✓
- 주의사항:
  - FRED vs ECOS 소숫값 차이 발생 가능 (예: 2026-04 85,811,990,000→85,830,054,000, ~0.02%). 정상 (원천 차이)
  - 2000년 이전 데이터(1980~1999)는 ECOS가 조회하지 않으므로 기존 FRED 값 유지

## 2026-06-28 11:45 - Claude
- Task: KOR_EXPORTS.csv 헤더 복원 및 대시보드 PPI·무역수지 최종 검증
- Changed:
  - `data/raw/macro/macro_indices/KOR_EXPORTS.csv`: 첫 행에 `DATE,XTEXVA01KRM667S` 헤더 복원
    - 원인: 이전 fix_kor_exports.py가 DATE 헤더 행을 데이터로 오인하여 제거 → pd.read_csv가 첫 데이터행을 컬럼명으로 사용하는 버그
    - 수정: `"DATE,XTEXVA01KRM667S\n" + 기존내용` prepend
  - `web/quant_data.js`: export_web_data.py 재실행으로 재생성
- Verification (JavaScript 직접 확인):
  - `KOR_EXPORTS`: 557행, first={"DATE":"1980-01-01","XTEXVA01KRM667S":1321292000}, last={"DATE":"2026-05-01","XTEXVA01KRM667S":87821386000} ✓
  - `KOR_PPI`: 197행, first={"date":"2010-01-01","value":93.87}, last={"date":"2026-05-01","value":129.82} ✓
  - KOR_EXPORTS YoY: +51.93% (2025-05: 57.8B → 2026-05: 87.8B USD) ✓
  - KOR_PPI YoY: +8.51% (2025-05: 119.64 → 2026-05: 129.82) ✓
  - 스코어카드 "한국 수출 YoY +51.9% → Risk On" 화면 표시 확인 ✓
- 주의사항:
  - KOR_EXPORTS.csv 헤더는 `DATE,XTEXVA01KRM667S` (FRED 원본 컬럼명). 향후 스크립트로 덮어쓸 때 반드시 헤더 유지 필요
  - collect_kr_trade_kosis.py는 SQLite에만 쓰고 KOR_EXPORTS.csv는 갱신 안 함 → 월간 배치 시 CSV 수동 동기화 또는 스크립트에 CSV 쓰기 추가 검토 필요

## 2026-06-28 11:20 - Claude
- Task: PPI·무역수지 구조적 lag 개선 (ECOS StatisticSearch 전환)
- Changed/Created:
  - `scripts/01_collect/collect_kr_ppi_ecos_full.py`: stat_code `021Y026` → `404Y014` (*AA 총지수) 수정
    - 이전: 021Y022~021Y027 모두 INFO-200 오류 (코드 없음)
    - 수정: 404Y014 = 4.1.1.1. 생산자물가지수(기본분류), *AA = 총지수 (2020=100) ← 정상 동작 확인
  - `scripts/01_collect/collect_kr_trade_kosis.py`: KOSIS API → ECOS 901Y118 전면 교체
    - 이전: KOSIS (DT_1R1001A2 등) — 미검증으로 항상 빈 응답
    - 수정: ECOS 901Y118 T002(수출금액), T004(수입금액) — 천불 단위, max=2026-05
    - 파생: korea_trade_balance 시리즈 자동 생성
  - `scripts/03_analyze/build_trade_balance_kr_us_factors.py`: 원천 데이터 우선순위 추가
    - ECOS primary (1개월 lag) → FRED OECD fallback (2개월 lag)
    - `_load_ecos_trade()`, `_load_kr_exports()`, `_load_kr_imports()` 함수 추가
  - `run_monthly.bat`: [7b/13] 단계 추가 — PPI·무역 수집 → 팩터 빌드 자동화
  - `data/database/quant_data.sqlite`:
    - `macro_macro_indices_kor_ppi`: 317행 upserted, max=2026-05-01
    - `macro_trade_kr_kosis_monthly`: 951행 신규 적재 (3 series × 317개월)
    - `factor_ppi_inflation_cycle_kr_month`: 317행, max=2026-05-01 (YoY=8.5% inflation_surge)
    - `factor_trade_balance_kr_us_month`: 497행, max=2026-05-01 (이전 2026-04-01 → 1개월 개선)
  - `web/quant_data.js`: 재생성 완료 (77.6MB)
- Verification:
  - `py_compile` 3개 파일 통과 ✓
  - PPI 스크립트 실행: 317행, max=2026-05-01 ✓
  - 무역 스크립트 실행: 951행, max=2026-05-01 ✓
  - 팩터 빌더: ECOS primary 자동 선택 확인 ✓
  - export_web_data.py: 77,638,515 bytes 11:18 ✓
- 개선 결과:
  - PPI: 구조적 lag 1개월 유지 (발표일 약 22일/다음월 → 불가피). 단, 전체 이력 백필 가능해져 스케줄러 중단 시 공백 자동 복구
  - 무역수지: FRED 2개월 lag → ECOS 1개월 lag (1개월 단축). 2026-04→2026-05로 최신화
- 주의사항:
  - 901Y118 단위: 천불(千弗)=천 달러 → build_trade_balance에서 ×1000하여 USD 단위 통일
  - 901Y118/T004 수입 확인: StatisticItemList에 T004=수입금액 명시됨
  - KOSIS 테이블 IDs(DT_1R1001A2 등)는 미검증. 현재 ECOS로 전환했으므로 KOSIS는 fallback도 없음
  - run_monthly.bat 스텝 번호: 기존 13스텝에 7b 삽입, 번호 재부여 불필요 (순서만 중요)

## 2026-06-28 11:05 - Claude
- Task: 데이터 공백 전체 재점검 및 Task Scheduler 수정
- Changed/Created:
  - `env.bat`: Python PATH 추가 (`C:\Users\fckin\AppData\Local\Programs\Python\Python311`)
  - `run_check_collection.bat`: `call env.bat` 추가 (Python PATH 상속)
  - Task Scheduler 4건 수정: cmd.exe 래퍼로 변경 (경로 공백 오류 해결)
    - QuantDailyMarket_1610 / QuantDailyNews_1700 / QuantMinuteTick_1540 / QuantCheckCollection_2100
  - `data/database/quant_data.sqlite`:
    - `valuation_kospi_fundamental_history`: 06-26까지 업데이트 (729→744행, pykrx PBR 컬럼으로 NaN 보완)
    - `valuation_kospi_pbr_percentile`: 06-26 스냅샷 갱신 (PBR=2.39, 0.7%ile)
  - `web/quant_data.js`: export_web_data.py 재실행으로 재생성 (77.6MB)
- Verification:
  - valuation_kospi_fundamental_history: max=2026-06-26, 744행 ✓
  - valuation_kospi_pbr_percentile: date=2026-06-26, PBR=2.39 ✓
  - quant_data.js: 77,638,515 bytes, 10:54:59 갱신 ✓
- 주의사항:
  - 일간 데이터(KOSPI/SP500/섹터ETF 등)는 Yahoo Finance 지연으로 06-26 기준 유지. 오늘 16:10 QuantDailyMarket_1610 자동 실행 시 06-27 데이터 수집 예정
  - KOSPI PBR 06-05→06-26 갱신 시 계산 방식이 다름: 기존 kospi_pbr 컬럼(시총가중평균, 06-05까지) + pykrx PBR 컬럼(06-06~06-26). 이력 연속성 확인 필요
  - 구조적 lag: PPI(06-05), 무역수지(04-01)는 원천 발표 일정 문제로 수집 불가 상태 정상

## 2026-06-28 09:55 - Hermes
- Task: 주가 지표 패널 고객예탁금/신용잔고 결측 보강 및 자동화
- Changed/Created:
  - `scripts/01_collect/collect_market_funds_once.py`: Naver Finance 고객예탁금/신용잔고 경량 수집기 추가
  - `scripts/03_analyze/export_web_data.py`: `market_funds_trend`를 `date`, `customer_deposit`, `credit_balance` 등 표준 alias로 export
  - `web/quant_ui.js`: 주가 지표/선물 섹션의 고객예탁금·신용잔고 차트를 표준 alias 기반으로 렌더링하도록 수정
  - `run_daily_market.bat`: 매일 시장 데이터 자동화에 고객예탁금/신용잔고 경량 수집 단계 추가
  - `package.json`: `npm run test` py_compile 대상에 `collect_market_funds_once.py` 추가
  - `C:\claude cowork _contextutomation_list.md`: QuantDailyMarket_1610 자동화 설명 갱신
- Verification:
  - `python scripts/01_collect/collect_market_funds_once.py` → `market_funds_trend.csv` 20 rows, latest 26.06.24
  - `python scripts/03_analyze/export_web_data.py` → `web/quant_data.js` 재생성
  - `node --check web/quant_ui.js` 통과
  - `npm run test` → 17 passed
  - Puppeteer 로컬 렌더링 검증: 주가 지표 탭 canvas 11개, 고객예탁금 차트 2개 표시, `market_funds_trend` 20 rows, latest customer_deposit/credit_balance present, page errors 0
- Caveat:
  - Naver 원천의 최신 고객예탁금/신용잔고는 2026-06-24로, 휴일/공시 지연에 따라 거래일보다 늦게 업데이트될 수 있음.

## 2026-06-28 09:00 - Hermes
- Task: 컨센서스 리비전 팩터 재확인 및 자동화
- Changed/Created:
  - `run_consensus_revision.bat`: 빠른 일간 누적/빌드/팩터마스터/웹 export/npm test 배치
  - `run_consensus_revision_full.bat`: Naver Finance 전체 스냅샷 수집 포함 주간 전체 배치
  - Windows Task Scheduler:
    - `QuantConsensusRevisionDaily` 매일 08:20, 빠른 누적/빌드
    - `QuantConsensusRevisionWeeklyFull` 매주 월요일 07:00, 전체 Naver 수집 포함
- Verification:
  - `QuantConsensusRevisionDaily` 수동 실행 성공, LastTaskResult=0
  - `factor_consensus_revision_snapshot` 620 rows / snapshot_date 2026-06-28
  - `factor_consensus_revision_catalog` 9 rows
  - `analyst_target_price_history.csv` 620 rows / 620 tickers / 2026-06-28
  - `factor_master_month.csv` 및 `web/quant_data.js` 후속 갱신 완료
  - `npm run test` → 17 passed
- Caveat:
  - 최초 이력일이라 1m/3m 리비전과 스윙/함정 플래그는 아직 대부분 비활성입니다. 일간/주간 누적 후 활성화됩니다.
  - 전체 Naver 수집은 시간이 길 수 있어 주간 07:00으로 분리하고, 일간 08:20은 기존 최신 스냅샷을 날짜별 이력으로 빠르게 누적합니다.

## 2026-06-28 08:12 - Hermes
- Task: 종합 팩터 마스터 패널 / Factor Data Mart 마무리 및 월간 배치 연결
- Changed:
  - `run_monthly.bat`: `build_factor_master_panel.py`를 컨센서스 리비전 이후, 웹 데이터 재생성 전에 실행하도록 13단계 배치로 정리
  - `C:\claude cowork _context\work_state.md`: 완료 기록 추가 및 이전 완료 항목 active lock 정리
  - `CHANGELOG_AGENT.md`: 본 항목 추가
- Created/Updated Outputs:
  - `data/raw/factors/factor_master_month.csv`
  - `data/raw/factors/factor_health_report.csv`
  - `data/raw/factors/factor_data_quality_month.csv`
  - `data/raw/factors/factor_master_catalog.csv`
  - SQLite: `factor_master_month`, `factor_health_report`, `factor_data_quality_month`, `factor_master_catalog`
  - DB backup: `data/database/backups/quant_data_20260628_081112_before_factor_master_phase1.sqlite`
- Verification:
  - `python -m py_compile scripts/03_analyze/build_factor_master_panel.py` 통과
  - `python -m pytest tests/test_factor_master_panel.py -q` → 4 passed
  - `python scripts/03_analyze/build_factor_master_panel.py` → `factor_master_month` 15,374 rows / 432 tickers / 2023-06~2026-06, `factor_health_report` 7 rows, `factor_data_quality_month` 15,374 rows
- Caveats:
  - `name`/`market`는 현재 표준 `stock_master` 테이블 부재로 일부 결측입니다. 추후 종목명 마스터를 정규화하면 자동 보강 가능합니다.
  - `macro_regime_score`는 1단계에서 종목 공통 중립값 0.5로 반영했습니다. 시장 레짐 테이블의 월별 값을 연결하는 2단계 고도화 여지가 있습니다.

## 2026-06-28 08:02 - Hermes
- Task: 컨센서스 리비전 팩터 신규 구축 및 목표주가/EPS 컨센서스 증분 누적화
- Changed:
  - `run_monthly.bat`: 월간 배치에 목표주가 증분 누적 및 컨센서스 리비전 팩터 빌드 단계 추가
  - `data.md`: 컨센서스 리비전 데이터/테이블 명세 추가
  - `C:\claude cowork _context\work_state.md`: lock 해제 및 완료 기록
  - `C:\claude cowork _context\index.md`: 신규 파일/테이블 색인 추가
  - `C:\claude cowork _context\index_factor.md`: ㊹ 컨센서스 리비전 팩터 명세 추가
- Created:
  - `scripts/01_collect/collect_analyst_target_price_incremental.py`
  - `scripts/03_analyze/build_consensus_revision_factors.py`
  - `tests/test_consensus_revision_factors.py`
  - `data/raw/valuation/analyst_target_price_history.csv`
  - `data/raw/factors/consensus_revision_snapshot.csv`
  - `data/raw/factors/consensus_revision_factor_catalog.csv`
  - DB backup: `data/database/backups/quant_data_20260628_080118_before_consensus_revision.sqlite`
- Verification:
  - `python -m py_compile scripts/01_collect/collect_analyst_target_price_incremental.py scripts/03_analyze/build_consensus_revision_factors.py scripts/03_analyze/export_web_data.py` 통과
  - `python -m pytest tests/test_consensus_revision_factors.py tests/test_target_price_factors.py -q` → 12 passed
  - `python scripts/01_collect/collect_analyst_target_price_incremental.py --use-existing-latest` → snapshot 620 / history 620 / target_price 618 / forward_eps 611
  - `python scripts/03_analyze/build_consensus_revision_factors.py` → `factor_consensus_revision_snapshot` 620 rows, `factor_consensus_revision_catalog` 9 rows 적재
  - DB spot check: `factor_consensus_revision_snapshot` 620 rows, `factor_consensus_revision_catalog` 9 rows
- Caveats:
  - 최초 누적일이라 `eps_revision_1m`, `target_price_revision_1m`, 3개월 리비전과 가속 점수는 대부분 NaN입니다. 향후 일/주간 누적 후 유의미하게 채워집니다.
  - `estimate_dispersion`은 애널리스트별 개별 추정치 분산이 아니라 최근 3개월 목표주가 변동계수 프록시입니다.

## 2026-06-27 22:35 - Hermes
- Task: 1단계 팩터 마스터/헬스/신선도 패널 구축
- Changed:
  - `C:\claude cowork\00_context\work_state.md`: Hermes lock 해제 및 완료 기록 추가
  - `C:\claude cowork\00_context\index.md`: 신규 스크립트/테스트/산출물 색인 추가
  - `C:\claude cowork\00_context\index_factor.md`: 팩터 마스터 패널 1단계 명세 추가
  - `data.md`: 신규 팩터 마스터 산출 테이블/CSV 명세 추가
- Created:
  - `.hermes/plans/2026-06-27_2223-factor-master-phase1.md`
  - `scripts/03_analyze/build_factor_master_panel.py`
  - `tests/test_factor_master_panel.py`
  - `data/raw/factors/factor_master_month.csv`
  - `data/raw/factors/factor_health_report.csv`
  - `data/raw/factors/factor_data_quality_month.csv`
  - `data/raw/factors/factor_master_catalog.csv`
  - DB backup: `data/database/backups/quant_data_20260627_223513_before_factor_master_phase1.sqlite`
- Verification:
  - `python -m py_compile scripts/03_analyze/build_factor_master_panel.py` 통과
  - `python -m pytest tests/test_factor_master_panel.py -q` → 4 passed
  - `python scripts/03_analyze/build_factor_master_panel.py` → `factor_master_month` 15,374 rows / 432 tickers / 2023-06~2026-06, `factor_health_report` 7 rows, `factor_data_quality_month` 15,374 rows, `factor_master_catalog` 7 rows
  - CSV 존재/크기 확인: master 8,570,300 bytes, health 964 bytes, quality 609,275 bytes, catalog 901 bytes
- Caveats:
  - 1단계는 기존 월간/스냅샷 팩터 통합 및 품질 점수화까지 완료. UI 노출과 2단계 매매 시나리오 점수(`pullback_rebound_score`, `breakout_continuation_score` 등)는 다음 단계 작업.
  - `name` 컬럼은 현재 DB에 표준 `stock_master` 테이블이 없어 결측으로 유지. 종목명 매핑은 향후 `ticker_names_*` 또는 웹 export 기준 테이블과 연결 필요.

## 2026-06-27 21:20 - Claude
- Task: run_hermes_bot.bat 중복 실행 방지 구현
- Changed:
  - `scripts/05_notify/hermes_bot.py`: 시작 시 `%TEMP%\hermes_bot_quant.lock`에 PID 기록, atexit으로 종료 시 삭제
  - `run_hermes_bot.bat`: LF→CRLF 수정(CMD 파서 오류 해결), 한국어 REM 제거(CP949 인코딩 충돌), PID 기반 중복 체크 로직 복원
- Verify: `tasklist /fi "PID eq <PID>" /fo csv | find "python"` → FOUND (차단 동작 확인)
- Note: PowerShell `&`로 bat 직접 실행 시 CRLF 처리 이슈 있음 → 반드시 더블클릭 또는 `cmd /k` 방식으로 실행

---

## 2026-06-27 20:58 - Hermes
- Task: 수집된 전체 데이터 최신성 재확인, 미최신 항목 업데이트 시도, 자동화 목록 점검
- Changed:
  - `web/quant_data.js` 재생성 (`export_web_data.py` 실행)
  - `C:\claude cowork\00_context\work_state.md` lock 완료/검증 결과 기록
  - `CHANGELOG_AGENT.md` 본 항목 추가
- Created: 없음
- Verification:
  - DB spot check: KOSPI/KOSDAQ/S&P500/NASDAQ/USD-KRW/quant daily/ADR gap/외국인 소진율 모두 `2026-06-26`까지 확인
  - 뉴스 감성 `factor_news_sentiment_snapshot`: 432 rows, max `2026-06-27`
  - 월간 주요 팩터(PER/PBR, 수급, 가격모멘텀, ROE, 섹터ETF): max `2026-06-01`로 월간 주기 정상
  - `check_collection.run_checks()` → ok=18, warn=0, fail=0 / total=18
  - `python -m py_compile scripts/05_notify/check_collection.py scripts/01_collect/collect_minute_tick_once.py scripts/03_analyze/build_minute_tick_factors.py scripts/03_analyze/export_web_data.py` 통과
  - `node --check web/quant_data.js` 통과
  - `pytest tests/test_api_collector_fallbacks.py tests/test_news_sentiment_factors.py tests/test_minute_tick_factors.py -q` → 15 passed, 1 warning
  - Task Scheduler XML 확인: `QuantDailyMarket_1610`, `QuantDailyNews_1700`, `QuantMinuteTick_1540`, `QuantMonthly_0600`, `QuantCheckCollection_2100`, `Anal_reports_Discord_Notify_0850`, Hermes Discord bot/watcher 등록 확인
- Caveats:
  - `collect_minute_tick_once.py`는 2026-06-27 토요일 20:55 실행 시 395/395 종목 모두 “데이터 없음”으로 신규 분봉 미수집. 기존 최신 분봉 팩터는 `2026-06-24` 유지. Naver 분별시세가 당일 장중/장마감 직후 중심이라 다음 거래일 15:30 예약(`QuantMinuteTick_1540`)으로 갱신 필요.
  - `npm run test`는 `package.json`에 기본 실패 스크립트(`echo "Error: no test specified" && exit 1`)가 설정되어 있어 실패가 정상 동작이며, 실제 검증은 py_compile/node --check/focused pytest로 대체.

## 2026-06-27 20:45 - Claude
- Task: hermes_bot `!t c/h` 명령을 실제 AI 실행으로 재설계
- 문제: 기존 `!t c/h`는 tasks_queue.md에만 기록하고 AI가 실제 실행 안 함
- 수정 내용 (`scripts/05_notify/hermes_bot.py`):
  - `HERMES_EXE` 경로 상수 추가 (`C:\Users\fckin\AppData\Local\hermes\...`)
  - `_run_ai(target, task)` 비동기 함수: `claude -p` / `hermes -z` 실행 후 출력 반환
  - `_send_chunks()`: Discord 1800자 청크 분할 전송
  - `cmd_task()` 전면 재작성: "작업 중..." embed → AI 실행 → 결과 전송
  - tasks_queue.md 기록은 이력용으로 유지
  - `!help` 상단에 "AI 실행" 섹션 추가
- 검증:
  - `hermes -z "지금 몇 시야?"` → 즉시 응답 확인
  - `claude -p "지금 몇 시야?"` → 즉시 응답 확인
  - py_compile OK, 봇 PID 10600으로 재시작 완료
- 사용법:
  ```
  !t c 현재 나스닥 시황 조사해줘  →  claude -p 실행 → Discord 결과
  !t h check_collection.py 실행해줘  →  hermes -z 실행 → Discord 결과
  ```
- 주의: `claude -p` 복잡한 코딩 작업은 5분 타임아웃 (파일 수정 포함 대규모 작업은 Claude Code 세션 직접 권장)

## 2026-06-27 20:30 - Claude
- Task: hermes_bot에 `!run` 명령 추가 — Discord에서 배치 직접 실행
- 수정 내용:
  - `scripts/05_notify/hermes_bot.py`:
    - import: `asyncio`, `subprocess`, `time` 추가
    - `RUN_JOBS` dict: 6개 job 정의 (daily_market / daily_news / monthly / minute / check / report)
    - `_running` dict: 중복 실행 방지용 job 추적
    - `!run <job>` 명령: 비동기 subprocess 실행, 시작/완료 embed 전송, 1시간 타임아웃
    - `!status` 명령: 현재 실행 중인 job 목록
    - `!help` 업데이트: 배치 실행 섹션 추가
  - `run_hermes_bot.bat`: 봇 다운 시 5초 후 자동 재시작 루프 추가
- Task Scheduler: `Anal_reports_HermesBot` 로그인 시 자동 시작 등록
- 검증: `py_compile` OK, PID 17228으로 봇 실행 중
- 사용법:
  ```
  !run daily_market   → run_daily_market.bat 실행
  !run daily_news     → run_daily_news.bat 실행
  !run monthly        → run_monthly.bat 실행
  !run minute         → run_collect_minute_tick.bat 실행
  !run check          → check_collection.py 실행
  !run report         → report_crawler.py 실행
  !status             → 실행 중인 job 목록
  ```
- 주의사항: 봇이 실행 중인 PC에서만 동작. 재부팅 후 Task Scheduler가 자동 재시작.

## 2026-06-27 20:10 - Claude
- Task: 리포트 수집 재확인 및 자동화 등록
- 문제 진단:
  - `report_crawler.py`의 이중 필터(`analyst_id == "external_analyst"` + `target_price == "미정"`)로 인해 유효 종목 리포트 3개 중 1개만 수집되던 상황
  - `collect_analyst_target_price_once.py`가 `run_monthly.bat`에 미등록
  - `report_crawler.py`가 어떤 배치에도 미등록 (마지막 수집: 2026-05-25)
- 수정 내용:
  - `scripts/01_collect/report_crawler.py`: 이중 필터 제거, `firm` 필드 new_entry에 추가
  - `run_daily_news.bat`: Step 0 추가 — `report_crawler.py` (daily, soft-fail)
  - `run_monthly.bat`: Step 9/10 추가 — `collect_analyst_target_price_once.py`
- 실행 결과:
  - `python -X utf8 scripts\01_collect\report_crawler.py` → 3개 신규 수집 (SK하이닉스/삼성전자/삼성중공업, 6/25~6/26)
  - `analyst_database.json` reports: 39 → 42개, 최신 2026-06-26
- 검증: `data/analyst_database.json` 최근 5개 확인 완료
- 주의사항: `valid_stocks` (57개 등록 종목)에 없는 종목 리포트는 여전히 수집 안됨. 확장 필요 시 `analysts[].targets` 배열에 종목명 추가

## 2026-06-27 19:15 - Claude
- Task: 6월 5일 이후 누락 데이터 전체 재수집·DB 적재·웹 데이터 재생성
- Scripts run (all succeeded):
  - `scripts/01_collect/collect_global_indices_once.py` → 해외지수 raw CSV 갱신 (→ 2026-06-26)
  - `scripts/01_collect/collect_sector_etf_once.py` → 섹터ETF raw CSV 갱신
  - `scripts/01_collect/collect_quant_macro_indicators_once.py` → 퀀트 매크로 지표 갱신
  - `scripts/01_collect/collect_grains_once.py` → 곡물 가격 갱신
  - `scripts/01_collect/collect_nonferrous_metals_once.py` → 비철금속 갱신 (stooq 빈 DataFrame guard 수정)
  - `scripts/01_collect/05_breadth.py` → 시장 폭 지표 갱신
  - `scripts/01_collect/collect_stock_news_once.py` → 뉴스 헤드라인 432/432 수집
  - `scripts/01_collect/collect_stock_investor_trend_once.py --overwrite` → 432종목 (기존 파일 존재로 0 collected, 스킵)
  - `scripts/02_store/load_to_db.py` → 3,300개 CSV → SQLite 마이그레이션 완료 (19:10:46)
  - `scripts/03_analyze/build_news_sentiment_factors.py` → 뉴스 감성 팩터 재산출
  - `scripts/03_analyze/export_web_data.py` → web/quant_data.js 재생성
- Verification: load_to_db 3,300 CSV 완료; export_web_data JS 파일 내보내기 완료
- Caveats:
  - `stooq_grains_latest.csv`, `stooq_nonferrous_metals_latest.csv` — stooq 스크래핑 빈 응답으로 headerless (정상, 해당 소스 불안정)
  - `collect_pytrends.py` — pandas `Length mismatch` 오류 (API 형식 변경 추정), 건너뜀
  - `collect_stock_investor_trend_once.py` — 기존 파일 존재로 모두 스킵됨 (파일 생성은 이전 실행에서 완료된 것으로 판단)

## 2026-06-27 22:30 - Claude
- Task: !task 명령어 담당자 구분 추가 (h=Hermes, c=Claude) + bat 파일 인코딩 오류 수정.
- Modified:
  - `scripts/05_notify/hermes_bot.py` — !task h/c 구분 파싱, add_task에 assignee 파라미터 추가, !tasks 목록 🤖/🧠 아이콘 표시, !help 업데이트
  - `run_hermes_watcher.bat` — chcp/한글 제거, `python -X utf8` 플래그로 대체 (cp949 파싱 오류 수정)
  - `run_hermes_bot.bat` — 동일하게 인코딩 수정
- Verification: 봇 재시작 후 !task h / !task c 양쪽 동작 확인
- Caveats: tasks_queue.md 항목 형식이 `- [ ] [Hermes] 내용` / `- [ ] [Claude] 내용`으로 변경됨

## 2026-06-27 22:00 - Claude
- Task: Discord 웹훅 봇 시스템 전체 구축 — 퀀트 브리핑(08:50), Hermes 감시봇, Hermes 명령봇, 데이터 수집 확인봇(21:00).
- Created:
  - `C:\claude cowork\05_skills\discord-webhook\discord_webhook.py` — CLI 유틸(--text/--stock/--news/--alert/--embed-json), 3회 재시도+지수백오프
  - `C:\claude cowork\05_skills\discord-webhook\config.json` — webhook_url / report_webhook_url / collect_webhook_url 3채널 등록
  - `scripts/05_notify/notify_discord.py` — quant_data.js 파싱(40MB), B유니버스 Top5 + 뉴스감성 8embed 전송; NaN/Inf 정제(_clean_row)
  - `scripts/05_notify/changelog_watcher.py` — CHANGELOG_AGENT.md 폴링(20s), 새 항목 감지 → report_webhook_url 전송
  - `scripts/05_notify/hermes_bot.py` — Discord Bot(!task/!tasks/!done/!clear), tasks_queue.md 파일큐 관리
  - `scripts/05_notify/check_collection.py` — DB 핵심 테이블 최신날짜 점검(18개 항목, 5카테고리), collect_webhook_url 전송
  - `run_notify.bat`, `run_hermes_watcher.bat`, `run_hermes_bot.bat`, `run_check_collection.bat`
  - `C:\claude cowork\00_context\tasks_queue.md`
- Modified:
  - `scripts/pipeline.py` — 5단계 Discord 알림(notify_discord.py) 추가
- Verification:
  - `python scripts/05_notify/notify_discord.py` → 8/8 embed 전송 성공 (HTTP 204)
  - `python scripts/05_notify/changelog_watcher.py` → CHANGELOG 감지 + Discord 전송 확인
  - `python scripts/05_notify/check_collection.py` → 6/6 embed 전송 성공 (ok=1 warn=0 fail=17; 미적재 테이블은 "데이터 없음" 정상 표시)
  - Task Scheduler: QuantNotifyDiscord_0850 (매일 08:50), QuantCheckCollection_2100 (매일 21:00) — State: Ready 확인
- Caveats:
  - hermes_bot.py는 bot_token 미설정 시 실행 불가; Discord Developer Portal에서 발급 후 config.json의 bot_token에 입력 필요
  - check_collection.py의 fail=17은 DB에 아직 없는 테이블(해외지수 일별, 월간팩터 일부 등)로 정상; 수집 스크립트 추가 후 자동 해소
  - notify_discord.py 파싱: web/quant_data.js (40MB) 전체 메모리 로드 방식 — 서버 메모리 부족 시 스트리밍 파서로 교체 필요

## 2026-06-27 17:53 - Hermes
- Task: 문제 API 동작 여부를 실제 호출로 점검하고 우선순위 1 수정사항 적용.
- Changed:
  - `scripts/01_collect/01_macro.py` — Yahoo/FDR에서 404 또는 not found가 확인된 `^VKOSPI`, `NAPM`, `AAIIBULL`, `AAIIBEAR`를 자동 수집 대상에서 제외하고 주석으로 재도입 조건 명시.
  - `scripts/01_collect/02_sentiment.py` — `.env` 자동 로드 추가; Yahoo TRIN 심볼을 `^TRIN`에서 동작 확인된 `TRIN`으로 교체; VKOSPI 실패는 warning 처리; KOSPI ADR을 현재 pykrx 함수 `get_market_price_change_by_ticker` 기반으로 재구현.
  - `scripts/01_collect/03_money_flow.py` — `.env` 자동 로드 추가; 공매도 수집을 현재 pykrx 함수 `get_shorting_volume_by_ticker`/`get_shorting_value_by_ticker` 조합으로 교체; `pd.read_html(StringIO(...))`로 pandas FutureWarning 제거.
  - `scripts/02_store/load_to_db.py` — 0 byte/headerless CSV를 error가 아닌 warning 후 skip 처리.
- Created:
  - `tests/test_api_collector_fallbacks.py` — 문제 API 회귀 테스트 5개 추가.
- Verification:
  - API/env 점검: FRED observations, ECOS KeyStatisticList, DART list API(`013` no-data 정상 응답), NAVER DataLab, KOSIS search, KRX 로그인 모두 실제 호출 OK(키 값 미노출).
  - 실제 API probe: Yahoo `TRIN` 5 rows, `^TRIN` 0 rows, `^VKOSPI` 0 rows; FDR `FRED:ICSA` 2,425 rows max 2026-06-20, `FRED:UMCSENT` 557 rows max 2026-05-01, `FRED:NAPM`/`AAIIBULL`/`AAIIBEAR` not found.
  - 실제 KRX/pykrx probe: `.env` 로드 후 KRX 로그인 성공; KOSPI ADR temp JSON 생성 성공; 공매도 temp CSV 생성 성공(45,307 bytes).
  - `python -m pytest tests/test_api_collector_fallbacks.py -q` → 5 passed, 1 pykrx DeprecationWarning.
  - `python -m py_compile scripts/01_collect/01_macro.py scripts/01_collect/02_sentiment.py scripts/01_collect/03_money_flow.py scripts/02_store/load_to_db.py` → 통과.
- Caveats:
  - VKOSPI는 현재 Yahoo/FDR 모두 404라 별도 KRX/네이버/공식 대체 소스 조사가 필요.
  - NAPM/AAII Bull/Bear는 현재 FRED/FDR 심볼로 조회 불가. 공식/대체 소스 확정 전까지 자동 수집 대상에서 제외.
  - KRX 로그인은 `.env`의 `KRX_ID`/`KRX_PW`에 의존하며 값은 기록하지 않음.

## 2026-06-27 17:40 - Hermes
- Task: 사용자 요청에 따라 6월 중 업데이트가 안 된 자료를 재수집/재적재하고 웹 퀀트 데이터 재생성.
- Changed:
  - `data/raw/macro/indices`, `exchange_rates`, `commodities`, `macro_indices` — FinanceDataReader/Yahoo/FRED 기반 주요 지수·환율·원자재·매크로 CSV 갱신.
  - `data/raw/macro/trade_stats`, `release_history`, ECOS/OECD CLI 관련 raw — 가능한 범위에서 재수집.
  - `data/raw/sentiment`, `data/raw/money_flow` — Fear & Greed, VIX/MOVE/SKEW/SOX, 수급/자금흐름 일부 갱신.
  - `data/database/quant_data.sqlite` — raw CSV 재적재 및 주요 파생 팩터 재계산.
  - `web/quant_data.js` — 최신 DB 기준 재생성.
  - Python 실행 환경에 누락 패키지 설치: `pandas`, `numpy`, `finance-datareader`, `pykrx`, `yfinance`, `pytest` 등.
- Created:
  - DB 백업: `data/database/backups/quant_data_20260627_1710_before_june_refresh.sqlite`.
  - 실행 로그: `logs/june_refresh_20260627_1720.log`, `logs/june_refresh_20260627_1740_resume.log`.
- Verification:
  - Ad-hoc work_state 검증: `C:\Users\fckin\AppData\Local\Temp\hermes-verify-9t57v3ou.py` 실행 후 삭제, active Hermes lock row 1개 확인.
  - 수집/처리 단계: 주요 collect/build/export 단계 rc=0. 단, `03_money_flow.py`의 장시간 Naver 20년 KOSPI/KOSDAQ history 루프는 kill 후 targeted 수급 업데이트로 재개.
  - DB spot check: `macro_indices_KOSPI` 4,057 rows max `2026-06-26`; `macro_macro_indices_DGS10` 12,127 rows max `2026-06-25`; `factor_credit_spread_kr_month`, `factor_fx_usdkrw_month`, `factor_commodity_momentum_month` max `2026-06-01`; `web/quant_data.js` 51,733,410 bytes.
  - Syntax: `python -m py_compile scripts/03_analyze/export_web_data.py scripts/02_store/load_to_db.py`, `node --check web/quant_ui.js`, `node --check web/quant_data.js` → 통과.
  - Focused tests: `python -m pytest tests/test_macro_search_sentiment_factors.py tests/test_ppi_inflation_cycle_kr_factors.py tests/test_trade_balance_kr_us_factors.py tests/test_credit_spread_kr_factors.py tests/test_fx_usdkrw_factors.py tests/test_commodity_momentum_factors.py -q` → 63 passed.
- Caveats:
  - Yahoo/FRED 일부 심볼은 원천 미지원/404로 실패: `^VKOSPI`, `^TRIN`, `NAPM`, `AAIIBULL`, `AAIIBEAR`.
  - pykrx 현 버전에서 `get_market_price_change_indicator`, `get_market_short_selling_by_ticker` API가 없어 KOSPI ADR/공매도 일부는 실패.
  - `fred_barley_sorghum_monthly.csv`는 빈 파일이라 load_to_db에서 스킵성 오류 기록. 기존 주의사항처럼 Barley/Sorghum 원자료 정체 가능.
  - FRED/공식 월간 지표는 발표 지연 때문에 CPI/무역 등 일부 최신 max date가 2026-04~2026-05에 머뭄.

## 2026-06-27 - Claude
- Task: Discord 웹훅 유틸리티 신규 스킬 생성
- Created:
  - `C:\claude cowork\05_skills\discord-webhook\discord_webhook.py` — CLI 유틸. 텍스트/주식알림/뉴스요약/알림카드/커스텀Embed 모드 지원. 3회 재시도+지수백오프.
  - `C:\claude cowork\05_skills\discord-webhook\SKILL.md` — 사용 가이드 (옵션표, Anal_reports 연동 예시 포함)
- Verification:
  - `python -m py_compile discord_webhook.py` → 통과
- Caveats:
  - `config.json`(웹훅 URL 포함)은 `.gitignore`에 추가 권장
  - 대량 전송 시 Discord rate limit(초당 5건) 주의 — 루프에 `time.sleep(0.5)` 추가

## 2026-06-24 19:32 - Hermes
- Task: 사용자 요청에 따라 `3번` 실전형 월간 리밸런싱 TopN 백테스트를 구축하고 웹 대시보드에 `실전 백테스트` 탭으로 연결.
- Created:
  - `scripts/03_analyze/build_practical_topn_backtest.py` — 월말 신호 → 다음 달 수익률 구조의 동일가중 Top20/30/50 월간 리밸런싱 NAV 백테스트. A/B/C/D 유니버스, 0%/0.3%/0.6% 비용률, turnover, hit ratio, MDD, CAGR, 벤치마크 대비 초과수익률 산출.
  - `tests/test_practical_topn_backtest.py` — NAV/MDD/CAGR, turnover 비용 차감, summary metric, universe label 테스트.
  - `C:\claude cowork\02_outputs\2026-06-24_19-36-46_practical_topn_backtest\` — `summary_practical_topn.csv` 270 rows, `monthly_practical_topn_returns.csv` 9,720 rows, `monthly_practical_topn_selections.csv` 323,994 rows, `coverage_by_period.csv` 37 rows, `panel_snapshot_used.csv`, `metadata.json`, `report.md`.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — 최신 `_practical_topn_backtest` 산출물을 `window.QUANT_DATA.practical_topn_backtest` payload로 export. summary/monthly/latest selections/coverage 포함.
  - `web/index.html` — `퀀트 분석` 하위 메뉴에 `실전 백테스트` 독립 탭 추가. 유니버스/시나리오/TopN/비용률 필터, NAV 차트, 성과표, 최근 리밸런싱 종목 영역 배치.
  - `web/quant_ui.js` — `renderPracticalBacktest()` 및 NAV Chart.js 렌더링, 필터 연동, 성과 카드/표/최근 종목 렌더링 추가.
  - `web/quant_data.js` — `practical_topn_backtest` payload 반영(summary 270, monthly 9,720, latest selections 3,000, coverage 37, as_of 2026-06).
- Verification:
  - `python -m py_compile scripts/03_analyze/build_practical_topn_backtest.py scripts/03_analyze/export_web_data.py` → 통과.
  - `pytest tests/test_practical_topn_backtest.py -q` → 4 passed.
  - `python scripts/03_analyze/build_practical_topn_backtest.py` → output rows: summary 270 / monthly 9,720 / selections 323,994 / coverage 37 / period 2023-06~2026-06.
  - `python scripts/03_analyze/export_web_data.py` → `practical_topn=270,9720` 확인 및 `web/quant_data.js` 재생성.
  - Node payload probe → summary 270 / monthly 9,720 / latest 3,000 / coverage 37 / as_of 2026-06 / B 유니버스와 0.3% 비용 payload 존재.
  - `node --check web/quant_ui.js`, `git diff --check` → 통과.
  - Puppeteer 로컬 검증(`http://127.0.0.1:8765/`) → 실전 백테스트 탭 active, 카드 4개, 성과표 15행, 최근 리밸런싱 30행, 유니버스 옵션 6개, 시나리오 옵션 5개, NAV 차트 dataset 2개, pageErrors 0.
- Caveats:
  - 공식 KOSPI200/KOSDAQ150 구성 이력이 아니라 월별 시총 proxy를 사용합니다. 일부 재무/컨센서스 팩터의 실제 공시 가능 시차는 아직 보수 조정되지 않았으므로 결과는 실전 검증용 1차 근사치입니다.
  - 거래비용은 단순 `turnover × cost_rate` 모델이며, 호가충격/거래정지/체결 가능성은 아직 반영하지 않았습니다.

## 2026-06-24 19:18 - Hermes
- Task: 사용자 요청에 따라 `오늘의 후보`를 `종목분석` 하위 독립 탭으로 분리.
- Modified:
  - `web/index.html` — `종목분석` 하위 메뉴에 `오늘의 후보` 탭을 추가하고, 기존 `종목 시장 매력도` 내부의 후보군 카드 섹션을 제거. 독립 탭에는 유니버스/시가총액/업종/기준 시나리오 필터와 후보 카드 영역을 배치.
  - `web/quant_ui.js` — `renderStockActionCandidatesTab()` 독립 렌더러, 후보 탭 sector filter 초기화, 하위 탭 전환 시 렌더링, 후보 카드 `보기` 버튼의 종목 상세 탭 이동 로직 추가. 기존 종목 매력도 렌더링에서는 후보 카드 갱신 호출 제거.
- Verification:
  - `node --check web/quant_ui.js` → 통과.
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - `git diff --check` → 통과.
  - Puppeteer 로컬 검증(`http://127.0.0.1:8765/index.html`) → 종목분석 하위 메뉴 2개(`종목 시장 매력도`, `오늘의 후보`), 후보 독립 탭 active, 후보 카드 4개/후보 20개, 업종 옵션 25개, 기존 종목 시장 매력도 탭 내 후보 컨테이너 없음, `보기` 클릭 시 종목 시장 매력도 탭으로 이동 및 검색 1행 렌더링, pageErrors 0.
- Caveats:
  - 이번 변경은 웹 UI 구조/렌더링 로직만 변경했으며 `web/quant_data.js` 재생성이나 SQLite/원천 데이터 변경은 수행하지 않음.

## 2026-06-24 19:08 - Hermes
- Task: 사용자 요청 `2번 진행`에 따라 종목 시장 매력도 화면을 실전 의사결정용 `오늘의 후보군` 섹션으로 확장.
- Modified:
  - `web/index.html` — 팩터 시나리오/TopN 백테스트 아래에 `오늘의 후보군` 카드 영역 추가.
  - `web/quant_ui.js` — 현재 유니버스/검색/시총/업종/퀵필터 기준의 표시 종목을 `매수 후보`, `관찰 후보`, `급등 추격 주의`, `저평가 회복 후보`로 자동 분류하고 각 후보의 점수·순위·3M 수익률·리스크 플래그를 표시.
- Verification:
  - `node --check web/quant_ui.js` → 통과.
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - Puppeteer 로컬 검증(`http://127.0.0.1:8765/index.html`) → `#stock-action-candidates` 카드 4개, 분류 후보 20개, 종목 테이블 300행 렌더링 확인. Page error 없음.
- Caveats:
  - 이번 변경은 웹 UI 분류/표시 로직만 변경했으며 `web/quant_data.js` 재생성이나 SQLite/원천 데이터 변경은 수행하지 않음.

## 2026-06-24 19:05 - Hermes
- Task: Git 작업상태 정리. 이전 작업에서 생성됐지만 미추적 상태였던 정식 팩터/테스트/raw 산출물은 커밋 대상으로 편입하고, 임시 로그/덤프 파일은 사용자 승인 후 삭제.
- Changed:
  - `scripts/01_collect/collect_us_korea_trade_once.py` — 프로젝트 `.env`의 `FRED_API_KEY`를 안전 로드해 FRED API observations를 우선 사용하고 graph CSV를 fallback으로 사용하는 변경분 정식 반영.
  - `docs_cache/opendartreader_corp_codes_20260609.pkl` → `docs_cache/opendartreader_corp_codes_20260619.pkl` 교체 반영.
- Created/Staged:
  - 신규 팩터 builder 14개: ADR gap, commodity momentum, KR credit spread, foreign exhaustion, USD/KRW FX, macro search sentiment, market breadth, market money flow, market valuation level, KR PPI inflation cycle, SOXX semicyle, KR/US trade balance, KR yield curve, regression analysis.
  - 신규 테스트 13개: 위 팩터군별 테스트 파일.
  - `data/raw/macro/trade_stats/` FRED 원천 CSV/요약/metadata 13개.
- Removed:
  - 임시/로그 파일 `error.log`, `logs_investor_trend_collect.out`, `scratch_dart_collect_log2.txt`, 잘못 생성된 `CUsersfckinAppDataLocalTempcatalogs_dump.txt`.
- Verification:
  - `python -m py_compile ...` 신규/변경 분석 스크립트 전체 통과.
  - `pytest tests/test_adr_gap_signal_factors.py ... tests/test_yield_curve_kr_factors.py -q` → 123 passed.
  - raw `trade_stats`: long 4,112 rows(1947-01-01~2026-04-01), monthly 3,478 rows(1957-01-01~2026-04-01), quarterly 634 rows(1947-01-01~2026-01-01), metadata 8 rows 확인.
  - SQLite 주요 테이블 확인: `macro_trade_us_korea_fred` 4,112 rows, `factor_trade_balance_kr_us_month` 832 rows, `factor_yield_curve_kr_month` 198 rows, `factor_soxx_semicycle_month` 121 rows 등.
- Caveats:
  - 이번 작업은 기존 미정리 산출물의 Git 정리/커밋 편입이며 신규 데이터 수집 또는 DB 재적재는 수행하지 않음.

## 2026-06-19 21:00 - Hermes
- Task: 사용자의 추가 검증 요청에 따라 ROE/품질 fallback 변경분을 독립 리뷰·정적 점검·회귀 검증.
- Findings/Fixes:
  - 독립 리뷰에서 explicit ticker 재수집 시 기존 DART rows와 중복될 수 있는 위험을 지적해 `collect_dart_finstate_once.py`를 보강.
  - `run(..., skip_existing=True)`가 명시 ticker에도 기존 보유 ticker를 skip하도록 수정하고, 저장 전 `_dedupe_records()`로 `(ticker, bsns_year, period, sj_div, account_id)` 중복을 마지막 수집값 기준 제거.
  - SQLite snapshot table 동적 이름은 `[A-Za-z0-9_]` allowlist 검증 후 quoted identifier로 조회하도록 보강.
  - `export_web_data.py`의 DART fallback map 생성은 결측 컬럼에서 scalar fallback이 아닌 `out.index` 정렬 Series fallback을 쓰도록 보강.
- Verification:
  - Static scan added lines → hardcoded secret/shell injection/eval/exec/pickle/obvious SQL injection 없음.
  - Independent review 1차 → duplicate explicit ticker refresh, scalar fallback map 위험 지적.
  - Independent review 2차/3차 → blocking issue 없음.
  - `_dedupe_records([])` → `(0, 0)`, ticker 없는 partial row 유지, full-key duplicate는 마지막 값 유지 확인.
  - `python -m py_compile scripts/01_collect/collect_dart_finstate_once.py scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/export_web_data.py` → 통과; `web/quant_data.js` 재생성.
  - DART raw duplicate key check → 71,906 rows, duplicate keys 0, 1,856 tickers.
  - Payload probe → stock_attractiveness 2,770 rows, ROE/roe_score 1,803, B 350/B ROE 331, FCF 1,544, BS품질 1,853.
  - `node --check web/quant_data.js` → 통과.
  - Puppeteer 로컬 검증 → rows 2,770, B 350, ROE 1,803, B ROE 331, FCF/BS/CF/이익안정 표시, 삼성전자 ROE 값, pageErrors 0.
  - `pytest tests/test_sector_relative_value_factors.py tests/test_valuation_per_pbr_factors.py tests/test_roe_trend_factors.py tests/test_piotroski_factors.py -q` → 37 passed.

## 2026-06-19 20:49 - Hermes
- Task: 사용자가 지적한 `ROE` 미반영 문제 확인 및 보강.
- Cause:
  - 웹 `stock_attractiveness`의 `roe`/`roe_score`는 기존 `factor_roe_trend_month` 최신 월간 패널만 참조해 전체 2,770개 중 387개, B 350개 중 304개만 노출되고 있었음.
  - DART raw에는 `net_income`/`total_equity`로 최신 ROE 계산 가능한 종목이 1,777개 이상 있었지만 export fallback에 ROE가 포함되지 않았음.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — DART 품질 fallback에서 `dart_roe = net_income / total_equity`, `dart_roe_score = sector 내 최신 DART ROE percentile` 계산 후 기존 ROE 패널 결측 시 fallback 적용.
  - `web/quant_data.js` — 재생성.
  - `data.md`, `00_context/index.md`, `00_context/work_state.md` — ROE 커버리지/검증 결과 반영.
- Verification:
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/export_web_data.py` → 통과.
  - Payload probe → 전체 2,770개 중 `roe`/`roe_score` 1,803개, B 350개 중 331개.
  - 기존 B 결측 샘플 `322000`, `229640`, `267270`, `004800`, `103590`에서 ROE/ROE score 값 확인.
  - `node --check web/quant_data.js` → 통과.
  - Puppeteer 로컬 검증 → stock_attractiveness 2,770, B 350, ROE 1,803/B ROE 331, body ROE 표시, pageErrors 0.
  - `pytest tests/test_sector_relative_value_factors.py tests/test_valuation_per_pbr_factors.py tests/test_roe_trend_factors.py -q` → 25 passed.
- Caveat:
  - DART fallback ROE는 최신 연간 snapshot 기반이고, 기존 `factor_roe_trend_month` ROE는 월간 패널 기반입니다. 기존 월간 ROE가 있으면 우선 사용하고, 없을 때만 DART 최신 ROE를 사용합니다.

## 2026-06-19 20:37 - Hermes
- Task: Claude가 확장 수집한 DART 재무제표 산출물을 확인하고, 종목 시장 매력도 화면의 `FCF/자산`, `BS품질`, `CF품질`, `이익안정` 결측을 추가 보강.
- Modified:
  - `data/raw/valuation/dart_finstate/finstate_all.csv` — Claude 수집분 + Hermes resume 결과 반영; 71,906 rows / 1,856 tickers / `capex` 4,942 rows.
  - `scripts/01_collect/collect_dart_finstate_once.py` — Claude 변경 확인: 전체 상장 스냅샷 기반 유니버스, 기존 ticker skip, 중간 저장 빈도 10, socket timeout, corp_code 예외 처리.
  - `scripts/03_analyze/export_web_data.py` — `stock_attractiveness` 생성 시 `factor_sector_relative_value_month` 결측 종목에 대해 DART raw 최신 품질 스냅샷을 fallback으로 병합.
  - `web/quant_data.js` — 재생성; 품질 필드 커버리지 확대.
  - `data.md`, `00_context/index.md`, `00_context/work_state.md` — 커버리지/백업/검증 결과 기록.
- Created:
  - `data/database/backups/quant_data_20260619_2038_before_quality_coverage_resume.sqlite` — 재가공 전 SQLite 백업.
- Verification:
  - `python -m py_compile scripts/01_collect/collect_dart_finstate_once.py scripts/03_analyze/build_sector_relative_value_factors.py scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/build_sector_relative_value_factors.py` → factor table 14,136 rows / 395 tickers / catalog 27 rows 유지; 기존 월간 가치/ROE 패널 기준 non-null 수치 유지.
  - `python scripts/03_analyze/export_web_data.py` → `stock_attractiveness DART 품질 fallback: 1855 tickers`, `stock_attractiveness: 2770 rows loaded`.
  - Payload probe → 전체 2,770개 중 `fcf_to_assets` 1,544 / `balance_sheet_quality_score` 1,853 / `cashflow_quality_score` 1,758 / `earnings_stability_score` 1,850 / `financial_quality_score` 1,808 / fallback 1,467.
  - B 기본 유니버스 350개 중 FCF 278 / BS품질 332 / CF품질 299 / 이익안정 331.
  - `node --check web/quant_ui.js`, `node --check web/quant_data.js` → 통과.
  - `pytest tests/test_sector_relative_value_factors.py tests/test_valuation_per_pbr_factors.py tests/test_roe_trend_factors.py tests/test_piotroski_factors.py -q` → 37 passed.
  - Puppeteer 로컬 검증 → stock_attractiveness 2,770 rows, B 350, FCF/BS/CF/이익안정 커버리지 확인, `FCF`/`왜 선정됐나` 표시, pageErrors 0.
- Caveats:
  - DART API 일부 종목에서 무응답/hang이 발생해 1차 추가 수집은 1,856 tickers까지 반영. 미수집/조회불가 종목은 임의 보간하지 않음.
  - SQLite 월간 팩터 테이블은 가치/ROE 월간 패널 매칭 가능한 395 tickers 기준이라 행수는 유지되며, 웹 결측 보강은 `stock_attractiveness` export fallback으로 별도 적용.
  - 로컬 export 중 pandas FutureWarning/날짜 parse UserWarning은 기존 경고이며 산출물 생성과 검증은 성공.

## 2026-06-18 21:54 - Hermes
- Task: 종목 시장 매력도 표의 가로 스크롤/잘림 문제와 수치 표기 누락감을 개선.
- Modified:
  - `web/index.html` — `#stock-attractiveness-table` 전용 compact/fixed layout CSS 추가; stock table wrapper를 세로 스크롤만 허용하도록 변경; 컬럼을 8개에서 5개로 재구성.
  - `web/quant_ui.js` — 영업이익 최근/올해/내년을 한 컬럼에 묶고 `억` 단위 표시; 레짐 점수를 시총/거래 컬럼으로 병합; DIV/ROE/부채/FCF는 `%` 형식으로 표시; 품질 점수 결측은 `데이터없음`으로 명확히 표시; `왜 선정됐나` 박스 폭/줄바꿈 개선.
- Created:
  - `scratch/verify_stock_table_compact_20260618.js` — Puppeteer compact table 검증 스크립트.
- Verification:
  - `node --check web/quant_ui.js`, `node --check web/quant_data.js`, `node --check scratch/verify_stock_table_compact_20260618.js` → 통과.
  - Puppeteer 920px viewport → headers 5개, row columns 5개, table wrapper `scrollWidth == clientWidth`로 가로 스크롤 없음, 영업이익 `억` 단위/배당률 `%`/품질 결측 `데이터없음`/레짐/왜 선정됐나 표시, pageErrors 0.
  - Git commit/push: `1926077` (`Compact stock attractiveness table`) → `main` push 완료.
  - GitHub Actions: Deploy Web Dashboard run `27760908023` → success.
  - Live Pages probe → root `stock-table-wrap`/`가치/퀄리티`/`영업이익`, `quant_ui.js` `fmtOpProfit`/`fmtPctNumber`/`stock-why-box`/`colspan="5"` 마커 확인.

## 2026-06-18 21:29 - Hermes
- Task: 종목 시장 매력도 데이터 유니버스를 명확화하고, 개발 우선순위 `B 유지 + A 별도 플래그`를 웹에 적용.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — `stock_attractiveness.universe` 메타 추가; `kosdaq150_proxy`, `project_universe_b`, `all_listed_screenable`, `universe_tags` 필드 추가.
  - `web/index.html` — 시장 필터를 유니버스 필터로 변경하고 기본값을 `B 기본: KOSPI200 + KOSDAQ150`으로 설정; 유니버스 정의 카드 추가.
  - `web/quant_ui.js` — B/A/C 유니버스 필터 로직, 기본 B 기준 랭킹/섹터순위, 유니버스 요약 렌더링 추가.
  - `web/quant_data.js` — 재생성; universe counts 포함.
- Created:
  - `scratch/verify_stock_universe_20260618.js` — Puppeteer 유니버스 필터/렌더링 검증 스크립트.
- Verification:
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/export_web_data.py` → `stock_attractiveness: 2770 rows loaded`, `web/quant_data.js` 생성 완료.
  - payload probe → `universe.default=B_KOSPI200_KOSDAQ150`, all 2,770 / A KOSPI200 proxy 200 / B default 350 / KOSDAQ150 proxy 150 / C screenable 898.
  - `node --check web/quant_ui.js`, `node --check web/quant_data.js`, `node --check scratch/verify_stock_universe_20260618.js` → 통과.
  - Puppeteer → 기본 선택 B, count `350개`, A 필터 `200개`, C 필터 `898개`, 유니버스 정의/개발 우선순위 문구/배지/삼성전자 검색/왜 선정됐나 유지, pageErrors 0.
  - Git commit/push: `31646f9` (`Add stock universe definitions`) → `main` push 완료.
  - GitHub Actions: Deploy Web Dashboard run `27759567932` → success.
  - Live Pages probe → root `유니버스 정의`/`B 기본: KOSPI200 + KOSDAQ150`/`개발 우선순위는`, `quant_data.js` universe counts, `quant_ui.js` 필터 함수 마커 확인.
- Caveats:
  - A/B는 공식 지수 구성원이 아니라 현재 snapshot의 시가총액 proxy 기준.
  - C screenable은 1차 필터(시총 1,000억원 이상, 거래대금/평균거래대금 10억원 이상, 가격 데이터 존재)이며 상폐/관리종목 공식 플래그는 아직 별도 수집 필요.

## 2026-06-18 20:14 - Hermes
- Task: 종목 시장 매력도 웹 대시보드에서 단순 랭킹보다 “왜 이 종목인가”를 설명하도록 UI/데이터를 개선.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — `stock_attractiveness.rows`에 1/3/6개월 수익률, 거래회전/평균거래대금, 외국인·기관 수급 변화, RSI/평균회귀, 공매도 잔고 변화, `factor_profile`, `risk_flags` 추가.
  - `web/index.html` — 종목 시장 매력도 탭에 `랭킹 해석 가이드`, `섹터별 상위 종목` 섹션 추가.
  - `web/quant_ui.js` — 전체 순위/섹터 내 순위, 시나리오별 핵심 팩터 breakdown, 최근 3개월 변화, 리스크 플래그, 섹터별 상위 카드 렌더링 추가.
  - `web/quant_data.js` — 재생성; `stock_attractiveness` 2,770개 종목 중 `factor_profile` 2,742개, `risk_flags` 2,770개 포함.
- Created:
  - `scratch/verify_stock_ranking_explain_20260618.js` — Puppeteer 검증 스크립트.
- Verification:
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/export_web_data.py` → `stock_attractiveness: 2770 rows loaded`, `web/quant_data.js` 생성 완료.
  - payload probe → rows 2,770 / factor_profile 보유 2,742 / risk_flags 필드 2,770; 삼성전자 샘플에서 PER·섹터상대가치·ROE profile 및 최근 3개월 변동 리스크 확인.
  - `node --check web/quant_ui.js`, `node --check web/quant_data.js`, `node --check scratch/verify_stock_ranking_explain_20260618.js` → 통과.
  - Puppeteer → 종목시장매력도 rows 300, `왜 선정됐나`, 랭킹 해석 가이드, 섹터별 상위 종목, 섹터 내 순위, 최근 3개월 변화, 리스크 플래그 표시; B 가치+퀄리티 전환 및 삼성전자 검색 후 설명 유지; pageErrors 0.
  - Git commit/push: `cd5589f` (`Add stock ranking explanation UI`) → GitHub Actions Deploy Web Dashboard run `27755694572` completed success.
  - Live URL `https://fckintroller.github.io/main-analyst-report-dashboard/` → HTTP 200; root HTML에 `랭킹 해석 가이드`/`섹터별 상위 종목`, `quant_data.js`에 `factor_profile`/`risk_flags`/`foreign_net_ratio_change`, `quant_ui.js`에 `buildWhyHtml`/`renderStockRankingInsights`/`왜 선정됐나` 마커 확인.
- Caveats:
  - 최근 3개월 변화는 현재 payload 기준 3개월 가격수익률/모멘텀 맥락 표시이며, 월별 리밸런싱 NAV가 아님.
  - `risk_flags`는 투자 경고가 아니라 데이터 기반 점검 포인트로 해석.

## 2026-06-18 19:22 - Hermes
- Task: TopN/분위수 팩터 백테스트 결과를 웹 대시보드의 기존 팩터 심사표 탭에 통합.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — 최신 `*_factor_topn_quintile_backtest` 산출물을 읽어 `window.QUANT_DATA.factor_validation.topn_quintile` payload로 export.
  - `web/index.html` — 팩터 심사표에 `실전 TopN / 5분위 백테스트` 섹션, 수익기간/TopN 필터, 주의문구 추가.
  - `web/quant_ui.js` — TopN 상위 팩터 및 Q1-Q5 스프레드 테이블 렌더러 추가.
  - `web/quant_data.js` — 재생성; TopN/분위수 payload 포함.
  - `00_context/index.md`, `00_context/work_state.md` — 웹/검증 스크립트 인덱스 및 작업 상태 갱신.
- Created:
  - `scratch/verify_factor_topn_quintile_dashboard_20260618.js` — Puppeteer payload/UI 검증 스크립트.
- Verification:
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/export_web_data.py` → `factor_validation: summary=135 / current_top=450 / topn_quintile=216,72`, `web/quant_data.js` 생성 완료.
  - payload probe → `topnSummary=216`, `quintileSummary=360`, `quintileSpread=72`, `tqCurrent=720`, `tqCoverage=888`, `tqAsOf=2026-06`.
  - `node --check web/quant_ui.js` 및 `node --check scratch/verify_factor_topn_quintile_dashboard_20260618.js` → 통과.
  - `node scratch/verify_factor_topn_quintile_dashboard_20260618.js` → TopN rows 12, Q1-Q5 rows 12, 필터 변경 후 rows 12/12, 주의문구 표시, pageErrors 0.
  - Git commit/push: `aa75fa8` (`Add TopN quintile dashboard view`) → GitHub Actions Deploy Web Dashboard run `27753076863` completed success.
  - Live URL `https://fckintroller.github.io/main-analyst-report-dashboard/` → HTTP 200; `quant_data.js`에 `topn_quintile`/`quintile_spread`, `quant_ui.js`에 `renderFactorTopnQuintile`, root HTML에 `실전 TopN` 마커 확인.
- Caveats:
  - 기존 백테스트와 동일하게 실제 KRX KOSPI200 구성종목이 아닌 월별 시가총액 상위 200개 프록시 기준.
  - 3/6개월 forward return은 중첩 표본이며 거래비용·세금·슬리피지 미반영.

## 2026-06-18 18:48 - Hermes
- Task: OLS 대신 TopN/분위수 기반 팩터 검증 백테스트를 실행.
- Created:
  - `C:/claude cowork/02_outputs/2026-06-18_18-43-21_factor_topn_quintile_backtest/run_factor_topn_quintile_backtest.py`
  - `C:/claude cowork/02_outputs/2026-06-18_18-43-21_factor_topn_quintile_backtest/summary_topn_by_score.csv`
  - `C:\claude cowork\02_outputs\2026-06-18_18-43-21_factor_topn_quintile_backtest\monthly_portfolio_returns.csv`
  - `C:\claude cowork\02_outputs\2026-06-18_18-43-21_factor_topn_quintile_backtest\monthly_topn_selections.csv`
  - `C:\claude cowork\02_outputs\2026-06-18_18-43-21_factor_topn_quintile_backtest\summary_quintile_by_score.csv`
  - `C:\claude cowork\02_outputs\2026-06-18_18-43-21_factor_topn_quintile_backtest\monthly_quintile_returns.csv`
  - `C:\claude cowork\02_outputs\2026-06-18_18-43-21_factor_topn_quintile_backtest\quintile_spread_summary.csv`
  - `C:\claude cowork\02_outputs\2026-06-18_18-43-21_factor_topn_quintile_backtest\coverage_by_period.csv`
  - `C:\claude cowork\02_outputs\2026-06-18_18-43-21_factor_topn_quintile_backtest\current_top30_by_score.csv`
  - `C:/claude cowork/02_outputs/2026-06-18_18-43-21_factor_topn_quintile_backtest/panel_snapshot_used.csv`
  - `C:/claude cowork/02_outputs/2026-06-18_18-43-21_factor_topn_quintile_backtest/report.md`
- Verification:
  - `python C:/claude cowork/02_outputs/2026-06-18_18-43-21_factor_topn_quintile_backtest/run_factor_topn_quintile_backtest.py` → panel 15,374행, KOSPI200 프록시 7,400행(2023-06~2026-06), TopN summary 216행, monthly returns 6,966행, selections 232,200행, quintile summary 360행, monthly quintile 11,610행, current Top30 720행.
  - `python -m py_compile ...run_factor_topn_quintile_backtest.py` → 통과.
  - CSV 행수 검증: coverage 888행, current_top30 720행, monthly_portfolio_returns 6,966행, monthly_quintile_returns 11,610행, monthly_topn_selections 232,200행, panel_snapshot_used 7,400행, quintile_spread 72행, summary_quintile 360행, summary_topn 216행.
- Caveats:
  - 실제 KRX KOSPI200 구성종목이 아니라 월별 시가총액 상위 200개 프록시를 사용.
  - 3/6개월 forward return은 중첩 수익률이라 실제 월간 리밸런싱 NAV로 해석하면 안 됨.
  - 거래비용/세금/슬리피지 미반영.
  - 2026-06 최신 `roe_quality`는 동일 점수 199개로 `current_top30_by_score.csv` 순위 해석력이 낮음.

## 2026-06-17 21:46 - Hermes
- Task: ㊳ Balance Sheet Quality, ㊴ Cash Flow Quality, ㊵ Earnings Stability를 섹터 상대 가치품질 팩터와 B 가치+퀄리티 웹 시나리오에 추가.
- Modified:
  - `scripts/01_collect/collect_dart_finstate_once.py` — DART finstate 수집 계정에 현금성자산, 매출, 영업이익, 이자비용, 순이익 variants 추가.
  - `scripts/03_analyze/build_sector_relative_value_factors.py` — `debt_to_equity`, `net_debt_to_ebitda`, `interest_coverage`, `current_ratio`, `equity_impairment_flag`, `balance_sheet_quality_score`; `operating_cashflow_positive`, `fcf_margin`, `fcf_yield`, `accrual_ratio`, `cash_conversion`, `cashflow_quality_score`; `revenue_yoy_stability`, `op_margin_volatility`, `net_loss_count`, `roe_volatility`, `earnings_stability_score` 생성. 산식별 주석/해석을 코드에 추가하고 `value_quality_score`에 ㊳/㊴/㊵ 반영.
  - `tests/test_sector_relative_value_factors.py` — ㊳/㊴/㊵ 방향성 및 catalog 매핑 테스트 추가.
  - `data/raw/valuation/dart_finstate/finstate_all.csv` — 재수집/보강.
  - `data/raw/factors/sector_relative_value_month.csv`, `data/raw/factors/sector_relative_value_catalog.csv`, `data/database/quant_data.sqlite` — 재생성/재적재; catalog 27행.
  - `scripts/03_analyze/export_web_data.py` — stock_attractiveness export에 ㊳/㊴/㊵ 세부 필드 및 점수 추가, B 가치+퀄리티 가중치에 반영.
  - `web/quant_data.js`, `web/quant_ui.js` — B 가치+퀄리티 설명에 ㊳/㊴/㊵ 추가, 종목 표에 `BS품질`/`CF품질`/`이익안정` 표시.
  - `scratch/verify_quality_3840_stock_scenarios_20260617.js` — Puppeteer payload/UI 검증 추가.
  - `data.md`, `00_context/index.md`, `00_context/index_factor.md`, `00_context/work_state.md` — 커버리지/검증/락 상태 반영.
- Verification:
  - `pytest tests/test_sector_relative_value_factors.py -q` → 11 passed.
  - `python -m py_compile scripts/01_collect/collect_dart_finstate_once.py scripts/03_analyze/build_sector_relative_value_factors.py scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/build_sector_relative_value_factors.py` → monthly 14,136행/395종목, catalog 27행.
  - `python scripts/03_analyze/export_web_data.py` → `stock_attractiveness: 2770 rows loaded`, `web/quant_data.js` 생성 완료.
  - `node --check web/quant_ui.js` / `node --check web/quant_data.js` → 통과.
  - `pytest tests/test_sector_relative_value_factors.py tests/test_valuation_per_pbr_factors.py tests/test_roe_trend_factors.py tests/test_piotroski_factors.py -q` → 37 passed.
  - SQLite non-null: `balance_sheet_quality_score` 14,052 / `cashflow_quality_score` 12,910 / `earnings_stability_score` 14,015; 세부 필드 `debt_to_equity` 12,730, `net_debt_to_ebitda` 10,582, `interest_coverage` 8,076, `current_ratio` 13,238, `fcf_yield` 12,420, `cash_conversion` 9,300 등.
  - `node scratch/verify_quality_3840_stock_scenarios_20260617.js` → rows 2,770, ㊳/㊴/㊵ enriched 353, B 가치+퀄리티 설명/`BS품질`/`CF품질`/`이익안정` UI 표시 확인.
  - Git commit/push: `1271a5e` (`Add balance sheet cash flow quality factors`) → GitHub Actions Deploy Web Dashboard run `27690187592` completed success.
  - Live URL `https://fckintroller.github.io/main-analyst-report-dashboard/` → HTTP 200; `quant_data.js`에 `balance_sheet_quality_score`, `cashflow_quality_score`, `earnings_stability_score`, `debt_to_equity`, `fcf_yield`, `scenario_b_value_quality` 마커 존재 확인.
- Caveats:
  - DART finstate 수집 전체 재실행은 600초 제한에 걸려 기존 raw에 추가 계정만 resume 수집해 병합했다. 결과 raw/SQLite는 재생성·검증 완료.
  - ㊳/㊴/㊵은 DART 최신 연간 스냅샷과 월간 ROE 패널을 ticker 기준으로 붙인다. 웹 전체 2,770개 중 세 품질 점수 동시 노출은 353개이며, 결측 종목은 기존 가치/ROE/실적 기반으로 fallback된다.

## 2026-06-17 19:29 - Hermes
- Task: B 가치+퀄리티/섹터 상대 가치품질 팩터에 부채비율·FCF를 붙이고 웹 종목 매력도에 노출.
- Modified:
  - `scripts/01_collect/collect_dart_finstate_once.py` — DART finstate 수집 계정에 `capex` 추가, 괄호 음수 파싱 보강, 과거 컬럼 부재 시 안전 처리.
  - `scripts/03_analyze/build_sector_relative_value_factors.py` — DART 최신 연간 재무제표 스냅샷에서 `debt_ratio`, `debt_to_assets`, `fcf`, `fcf_to_assets`, `debt_ratio_score`, `fcf_to_assets_score`, `financial_quality_score`, `quality_source` 생성; `value_quality_score`에 저부채/FCF 품질 반영.
  - `tests/test_sector_relative_value_factors.py` — 부채비율·FCF 품질 방향성과 결측 재무품질 fallback 테스트 추가.
  - `data/raw/valuation/dart_finstate/finstate_all.csv` — 재수집; 12,830행/379종목, `capex` 1,091행 포함.
  - `data/raw/factors/sector_relative_value_month.csv`, `data/raw/factors/sector_relative_value_catalog.csv` — 재생성; monthly 14,136행, catalog 10행.
  - `data/database/quant_data.sqlite` — `factor_sector_relative_value_month`/catalog 재적재. 사전 백업: `data/database/backups/quant_data_20260617_192517_before_debt_fcf.sqlite`.
  - `scripts/03_analyze/export_web_data.py` — stock_attractiveness export에 debt/FCF/financial_quality 필드 추가.
  - `web/quant_data.js` — 재생성; stock_attractiveness 2,770행, debt/FCF 동시 노출 315행.
  - `web/quant_ui.js` — B 가치+퀄리티 설명을 부채비율·FCF 포함으로 갱신하고 종목 표에 부채/FCF·자산 표시.
  - `scratch/verify_debt_fcf_stock_scenarios_20260617.js` — Puppeteer payload/UI 검증 추가.
  - `data.md`, `00_context/index.md`, `00_context/index_factor.md`, `00_context/work_state.md` — 커버리지/검증/락 상태 반영.
- Verification:
  - `python scripts/01_collect/collect_dart_finstate_once.py` → 완료; DART raw 12,830행/379종목, `capex` 1,091행.
  - `python scripts/03_analyze/build_sector_relative_value_factors.py` → monthly 14,136행/395종목, catalog 10행; non-null debt_ratio 12,730 / fcf_to_assets 11,976 / financial_quality_score 13,539 / value_quality_score 14,124.
  - `python scripts/03_analyze/export_web_data.py` → `stock_attractiveness: 2770 rows loaded`, `web/quant_data.js` 생성 완료.
  - `python -m py_compile scripts/01_collect/collect_dart_finstate_once.py scripts/03_analyze/build_sector_relative_value_factors.py scripts/03_analyze/export_web_data.py` → 통과.
  - `node --check web/quant_ui.js` / `node --check web/quant_data.js` / `node --check scratch/verify_debt_fcf_stock_scenarios_20260617.js` → 통과.
  - `pytest tests/test_sector_relative_value_factors.py tests/test_valuation_per_pbr_factors.py tests/test_roe_trend_factors.py tests/test_piotroski_factors.py -q` → 34 passed.
  - `node scratch/verify_debt_fcf_stock_scenarios_20260617.js` → rows 2,770, enriched 315, quality_source 존재, B 가치+퀄리티 UI와 부채/FCF 표시 확인.
  - Git commit/push: `27f2abd` (`Add debt and FCF quality factors`) → GitHub Actions Deploy Web Dashboard run `27682919371` completed success.
  - Live URL `https://fckintroller.github.io/main-analyst-report-dashboard/` → HTTP 200; `quant_data.js`에 `debt_ratio`, `fcf_to_assets`, `financial_quality_score`, `quality_source`, `scenario_b_value_quality` 마커 존재 확인.
- Caveats:
  - 부채비율·FCF는 DART 최신 연간 스냅샷을 월간 패널에 ticker 기준으로 붙인 값입니다.
  - 웹 전체 2,770개 종목 중 debt/FCF 동시 노출은 DART 상세 수집·월간 팩터 매칭 가능한 315개입니다. 나머지는 기존 가치/ROE/실적 기반 점수로 fallback됩니다.
  - export 중 pandas `FutureWarning`/날짜 parse `UserWarning`, 로컬 브라우저 검증 중 favicon 404는 기존 경고이며 산출물 생성/검증은 성공.

---

## 2026-06-17 18:53 - Hermes
- Task: 종목 시장 매력도 화면에 A/B/C/D 투자 시나리오 점수와 UI 선택 흐름을 마무리 검증.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — `factor_sector_relative_value_month` 결합, A 단기 모멘텀/B 가치+퀄리티/C 저평가 반등/D 대형 안정 가중 점수 산식 추가.
  - `web/index.html` — 종목 시장 매력도 정렬 기준에 A/B/C/D 시나리오 옵션 추가.
  - `web/quant_ui.js` — `STOCK_SCENARIOS`에 A/B/C/D 설명 추가; 정렬 드롭다운 변경 시 시나리오 카드 설명이 즉시 동기화되도록 렌더링 순서 수정.
  - `web/quant_data.js` — 재생성; `stock_attractiveness.rows` 2,770개, 기준일 2026-06-05, A/B/C/D 점수 포함.
  - `scratch/verify_stock_scenarios_20260617.js` — Puppeteer 기반 payload/드롭다운/시나리오 카드/정렬 검증 스크립트 추가.
  - `00_context/index.md`, `00_context/work_state.md` — 신규 검증 스크립트 및 lock 완료 상태 반영.
- Verification:
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - `python scripts/03_analyze/export_web_data.py` → `stock_attractiveness: 2770 rows loaded`, `web/quant_data.js` 생성 완료.
  - `node --check web/quant_ui.js` / `node --check web/quant_data.js` / `node --check scratch/verify_stock_scenarios_20260617.js` → 통과.
  - `node scratch/verify_stock_scenarios_20260617.js` → A/B/C/D 모두 payload count 2,770, 드롭다운/카드 라벨 존재, 시나리오별 상위 5개 UI 점수 내림차순 검증 통과.
- Caveats:
  - A/B 시나리오 상위권은 여러 종목이 100점으로 동점이어서 순위는 동일 점수 내 원자료/기존 정렬 순서 영향을 받을 수 있음.
  - export 중 pandas `FutureWarning`/날짜 parse `UserWarning`은 기존 경고이며 JS 생성과 검증은 성공.

---

## 2026-06-16 21:52 - Hermes
- Task: 팩터 심사표 현재 Top30의 `원값`이 1로 뭉개져 보이는 UX 문제 개선.
- Modified:
  - `web/index.html` — 정렬기준 라벨을 `방향점수/원값`에서 `표준점수/기준값`으로 변경하고, 표준점수·기준값 의미 설명문 추가.
  - `web/quant_ui.js` — 표준점수는 0~100점으로 표시; 기준값은 팩터별 해석 단위로 표시(모멘텀 점수, 섹터 PER/PBR 대비 배수, z-score 등); `해석` 컬럼 추가.
  - `scratch/verify_factor_validation_tab_20260616.js` — 모멘텀 기준값 표시(`모멘텀 xx.x점`)와 해석 컬럼 검증 추가; raw 정렬 검증이 빈 배열로 통과하지 않도록 보강.
  - `00_context/index.md`, `00_context/work_state.md` — 변경/lock 상태 갱신.
- Verification:
  - `node --check web/quant_ui.js` → 통과.
  - `node --check scratch/verify_factor_validation_tab_20260616.js` → 통과.
  - `node scratch/verify_factor_validation_tab_20260616.js` → 삼성전자/005930 검색 true, score/raw asc/desc 정렬 true, momentumDisplayOk true.
- Note:
  - `③ 가격·거래량 모멘텀`의 실제 raw는 1.000/0.963/0.918처럼 차이가 있었으나 기존 3자리 숫자 표시와 `원값` 명칭 때문에 모두 1처럼 보였음. 이제 `모멘텀 100.0점`, `모멘텀 96.3점`처럼 기준이 드러남.

---

## 2026-06-16 21:30 - Claude
- Task: UI/UX 개선 7종 (버그 수정 + 사용성 향상)
- Modified:
  - `web/quant_ui.js`
    - **B2** DOMContentLoaded에 `renderRegressionPanel()` 추가; `renderDartTable()` / `renderEpsTable()` 유령 호출 제거 (함수 정의는 유지)
    - **B4/D1** 종목 매력도 테이블 `<tr>` onclick → `openStockModal(row.name)` 연결; cursor:pointer + hover 스타일 추가
    - **D5** `initTabs` + `switchSubTab` 양쪽에 `window.scrollTo({top:0,behavior:'smooth'})` 추가 — 탭/서브탭 전환 시 자동 최상단 이동
    - **D9** `renderRegressionPanel()` 기준일 표시에 2개월 이상 미갱신 시 ⚠ 주황 경고 추가
    - **D6** `renderSectorMap()` 등락률 강도에 따라 background rgba opacity 계단 적용 (0.35~1.0); 폰트 크기/굵기도 연동
  - `web/index.html`
    - **D4** 모바일 하단 nav에 "종목" (fa-ranking-star, btn-tab-analysis) 추가 → 5개 항목으로 확장
    - **D2** 매크로&시장 서브탭 사이드바에 구분선 + 그룹 레이블 추가: "시장 데이터" / "분석 모델" 섹션 분리
    - **D8** 팩터 심사표 탭 상단에 앵커 바로가기 네비 추가 (요약·TopN·현재Top30·상관관계·커버리지); 각 섹션 `data-card`에 `id=fv-*` 앵커 삽입
- Verification:
  - `node --check web/quant_ui.js` → OK
  - HTML ID 중복 없음; 앵커 fv-summary→fv-topn→fv-current→fv-corr→fv-coverage 순서 확인
- Caveats:
  - `openStockModal`은 app.js의 analyst DB 기준으로 검색 → 종목명이 analyst_data.js에 없으면 모달 내용이 비어 보일 수 있음 (연결은 되지만 데이터 없음)
  - `renderDartTable` / `renderEpsTable` 함수는 남겨 뒀음 (HTML에 타깃 없지만 향후 연결 가능)

---

## 2026-06-16 21:20 - Hermes
- Task: 팩터 심사표 현재 Top30 테이블 검색/정렬 보완.
- Modified:
  - `web/index.html` — 현재 Top30 영역에 `정렬기준(순위/방향점수/원값)`과 `정렬방향(오름차순/내림차순)` select 추가.
  - `web/quant_ui.js` — 팩터 선택에 `전체 팩터` 옵션 추가; 종목명/섹터/팩터명/6자리 보정 종목코드 검색 지원; 방향점수·원값 정렬 로직 추가.
  - `scratch/verify_factor_validation_tab_20260616.js` — 삼성전자/005930 검색 및 방향점수·원값 정렬 검증 assertion 추가.
  - `00_context/index.md`, `00_context/work_state.md` — 변경/lock 상태 갱신.
- Verification:
  - `node --check web/quant_ui.js` → 통과.
  - `node --check scratch/verify_factor_validation_tab_20260616.js` → 통과.
  - `node scratch/verify_factor_validation_tab_20260616.js` → 삼성전자 이름 검색 true, 005930 코드 검색 true, score/raw asc/desc 정렬 검증 true.
- Note:
  - 검색이 안 보였던 주된 이유는 기존 기본 팩터가 `㉑ 소형주 점수`로 고정되어 있었고, 검색 대상도 선택 팩터 Top30 안으로 제한됐기 때문. 이제 `전체 팩터` 기본값에서 삼성전자가 `③ 가격·거래량 모멘텀` 후보로 검색됨.

---

## 2026-06-16 21:10 - Claude
- Task: 탭 재배치 — 회귀 분석 신호·매크로 스코어카드·섹터 모멘텀을 매크로&시장 탭으로 이동, 섹터 히트맵 탭 삭제
- Modified:
  - `web/index.html` — 퀀트 사이드바에서 매크로스코어카드·섹터모멘텀·섹터히트맵 서브탭 제거; 매크로 사이드바에 매크로스코어카드·섹터모멘텀·회귀분석신호 서브탭 추가; `#sub-macro-scorecard` / `#sub-macro-sector-momentum` / `#sub-macro-regression` 콘텐츠 블록 추가; `#tab-analysis`에서 구 `regression-insight-panel` 인라인 블록 제거; `#tab-quant`에서 `sub-quant-heatmap` / `sub-quant-scorecard` / `sub-quant-sector-momentum` 제거.
  - `web/quant_ui.js` — `switchSubTab()` 내 `quant-sector-momentum` → `macro-sector-momentum` 변경, `macro-scorecard`·`macro-regression` 핸들러 추가; `renderStockAttractiveness()`에서 `renderRegressionPanel()` 호출 제거; `renderRegressionPanel()` 내 `display:none` 토글 로직 제거.
- Verification:
  - `node --check web/quant_ui.js` → OK
  - Python ID 중복 검사 → 중복 없음, 9개 핵심 ID 모두 확인
  - HTTP 서버 `http://localhost:8000/index.html` → 200 OK
- Caveats:
  - `renderRegimeCard()` / `renderScorecard()`는 초기 로드 시 DOMContentLoaded에서 이미 실행됨. 매크로 탭 최초 진입 시 `macro-scorecard` sub-tab이 자동으로 선택되지 않으면 클릭해야 렌더링됨.

---

## 2026-06-16 20:53 - Hermes
- Task: LOCK 해제 후 팩터 심사표를 기존 웹 대시보드의 퀀트 탭 하위 `팩터 심사표` 탭으로 통합.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — `_build_factor_validation()` 추가, 독립 검증 CSV 산출물(`02_outputs/*_factor_validation_dashboard`)을 `window.QUANT_DATA.factor_validation` payload로 export.
  - `web/index.html` — 퀀트 사이드바에 `팩터 심사표` 서브탭 추가, 요약 카드/TopN/현재 Top30/상관관계/커버리지 컨테이너 추가.
  - `web/quant_ui.js` — `renderFactorValidation*()` 렌더러 추가, 탭 전환 시 렌더링 연결.
  - `web/quant_data.js` — 재생성; `factor_validation` 포함(summary 135행, current_top 450행, correlation 15개, coverage 37행, as_of 2026-06-01).
  - `00_context/index.md`, `00_context/work_state.md` — 파일 인덱스/협업 상태 갱신.
- Created:
  - `scratch/verify_factor_validation_tab_20260616.js` — Puppeteer 기반 웹 탭 payload/DOM 검증 스크립트.
- Verification:
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과.
  - `node --check web/quant_ui.js` → 통과.
  - `python scripts/03_analyze/export_web_data.py` → `factor_validation: summary=135 / current_top=450` 로드 및 `web/quant_data.js` 생성 완료.
  - `node scratch/verify_factor_validation_tab_20260616.js` → payload/DOM 검증 통과: cards 4, summaryRows 15, topRows 15, currentRows 30, corrRows 15, coverageRows 12.
- Caveats:
  - 팩터 검증 수익률은 거래비용 미반영.
  - Puppeteer 검증 중 favicon 404는 기존 정적 리소스 부재로 무시 처리, 기능 오류 아님.

---

## 2026-06-16 - Claude
- Task: 회귀 분석 3종 구축 (시나리오 1 Fama-MacBeth, 2 시장타이밍, 3 레짐인터랙션) + 종목 매력도 탭 대시보드 업데이트
- Created:
  - `scripts/03_analyze/build_regression_analysis.py` — 시나리오 2(KOSPI 시장타이밍 OLS+Ridge: base 178M R²=0.091, full 115M R²=0.149), 시나리오 1(Fama-MacBeth 36기간 395종목; flow_score t=2.15 유의), 시나리오 3(레짐 인터랙션 risk_on/off/other) 수행 후 DB 5개 테이블 저장.
- Modified:
  - `scripts/03_analyze/export_web_data.py` — `_build_regression_summary()`, `_inject_regime_scores()` 함수 추가; `regression` 키를 quant_data에 포함, stock_attractiveness rows에 `regime_adj_score` 주입.
  - `web/quant_data.js` — 재생성 (regression 섹션, regime_adj_score 432종목 포함).
  - `web/index.html` — 회귀 분석 인사이트 패널(#regression-insight-panel) 추가; 테이블 헤더에 `레짐 점수` 열 추가; sort select에 `레짐 조정 점수` 옵션 추가.
  - `web/quant_ui.js` — `renderRegressionPanel()` 함수 신규 추가(시장타이밍 신호 게이지, 팩터 기여도 바차트, FM IC 바차트, 레짐별 팩터 IC 교차표); `STOCK_SCENARIOS`에 `regime_adj_score` 시나리오 추가; 테이블 행에 `레짐조정` 컬럼 추가; `renderStockAttractiveness()`에 `renderRegressionPanel()` 호출 연결.
- DB 신규 테이블:
  - `regression_market_timing` — 팩터별 OLS/Ridge 계수·t-stat·현재값 (18행: base/full×9팩터)
  - `regression_factor_ic` — Fama-MacBeth IC·t-stat·IR (6팩터)
  - `regression_regime_ic` — 레짐별 팩터 IC (3레짐×6팩터=18행)
  - `regression_regime_adj_scores` — 종목별 레짐 조정 점수 (432행)
  - `regression_meta` — 전체 JSON 직렬화 결과 캐시
- 주요 결과:
  - 시장 타이밍: signal=neutral, 예측 KOSPI 수익률=+2.19% (2026-04 예측), R²=9.1%
  - 팩터 IC 유의: flow_score(외국인/기관 수급) t=2.15 (p<0.05) → 가장 강한 단기 알파 신호
  - 현재 레짐: neutral/other
  - Top 레짐조정 종목: LG디스플레이·SK케미칼·이수시스템·LG화학·삼성 (상위권)
- 검증:
  - `python build_regression_analysis.py` → 정상 실행, DB 5개 테이블 생성
  - export_web_data 실행 → quant_data.js 재생성 (regression 키 + regime_adj_score 확인)
  - JS 괄호 균형 체크: {} () [] 모두 0 (정상)
  - HTTP 200 서버 응답 확인
- 주의사항:
  - FM 패널이 37개월로 짧아 IC t-stat 신뢰 구간 넓음 (flow_score만 유의, 나머지 참고용)
  - 시장 타이밍 R²=9.1% (base) — 낮은 설명력, 방향 신호로만 활용 권장
  - pred_period=2026-03-01: PPI·무역수지가 2026-04 종료라 최신 완성 X는 2026-03 시점
  - 레짐 기간 분포: risk_on 10개월, risk_off 1개월, other 1개월 (37M 중) — risk_off 구간 너무 짧아 해당 회귀 결과 통계적으로 불안정
  - scipy/scikit-learn/statsmodels 패키지 필요 (pip install 완료)

---

## 2026-06-16 - Hermes
- Task: 사용자 요청 PER/PBR 섹터 비교 팩터 1·2·3·5·6 구축 — 섹터상대 PER, 섹터상대 PBR, PBR/ROE 조정, 가치+품질 점수, 섹터 자체 과거 밸류 z-score.
- Created:
  - `scripts/03_analyze/build_sector_relative_value_factors.py` — ① `factor_valuation_per_pbr_month`와 ⑮ `factor_roe_trend_month`를 결합해 `sector_relative_per`, `sector_relative_pbr`, `pbr_to_roe`, `pbr_roe_residual_sector`, `pbr_roe_adjusted_score`, `value_quality_score`, `sector_value_zscore` 생성.
  - `tests/test_sector_relative_value_factors.py` — 섹터 중앙값 기준, 소형 섹터 NaN, PBR/ROE 조정 방향성, 섹터 z-score, catalog 요청번호 매핑 검증.
  - `data/raw/factors/sector_relative_value_month.csv` — 14,136행, 395종목, 2023-06~2026-06.
  - `data/raw/factors/sector_relative_value_catalog.csv` — 7행.
- DB 신규 테이블 (백업: `data/database/backups/quant_data_20260616_1940_before_sector_relative_value.sqlite`):
  - `factor_sector_relative_value_month` — 14,136 rows, 395 tickers, 2023-06-01~2026-06-01.
  - `factor_sector_relative_value_catalog` — 7 rows.
- Verification:
  - `python -m py_compile scripts/03_analyze/build_sector_relative_value_factors.py` → 통과.
  - `python scripts/03_analyze/build_sector_relative_value_factors.py` → 적재 완료; non-null `sector_relative_per` 10,202 / `sector_relative_pbr` 13,407 / `pbr_roe_adjusted_score` 10,092 / `value_quality_score` 14,015 / `sector_value_zscore` 9,586.
  - `pytest tests/test_sector_relative_value_factors.py -q` → 6 passed.
  - `pytest tests/test_sector_relative_value_factors.py tests/test_valuation_per_pbr_factors.py tests/test_roe_trend_factors.py -q` → 20 passed.
- Updated:
  - `00_context/index_factor.md` — ㊲ 요약/상세 섹션 추가, 기준일 2026-06-16.
  - `00_context/index.md` — 신규 raw CSV, 스크립트, 테스트, DB 테이블, 백업 항목 추가.
  - `data.md` — 2026-06-16 구축 기록/검증/caveat 추가.
  - `00_context/work_state.md` — lock 등록/해제 및 완료 기록.
- Caveats:
  - 섹터 내 표본 5종목 미만이면 섹터 상대/잔차 지표는 NaN.
  - ROE≤0 구간은 PBR/ROE 조정 지표 NaN.
  - 현재 월간 패널에는 부채비율·FCF 원천이 없어 `value_quality_score`는 저평가+ROE 품질 중심의 1차 후보군. 부채/FCF까지 포함하려면 DART 재무제표 기반 확장 필요.

## 2026-06-15 (2) - Claude
- Task: 신규 퀀트 팩터 4종 구축 — ㉝글로벌 반도체 사이클(SOXX), ㉞한국 국채 수익률곡선(Level/Slope/Curvature), ㉟한국 PPI 인플레이션 사이클(OECD CLI 대체), ㊱원자재(구리·원유) 모멘텀 (모두 기존 raw 데이터 재활용, 신규 수집 없음)
- Created:
  - `scripts/03_analyze/build_soxx_semicycle_factors.py` — `macro_macro_indices_soxx`(yfinance, 일별 2016-06~2026-06, 상단 2행 yfinance 메타헤더 `.iloc[2:]` 제거) → 월말 리샘플, soxx_ret_1m/3m + 6M z-score + 3년 롤링 백분위 + semi_momentum_score/semi_cycle_regime/semi_rally_accel_flag
  - `tests/test_soxx_semicycle_factors.py` — 12 passed
  - `scripts/03_analyze/build_yield_curve_kr_factors.py` — `macro_macro_indices_kor_gov1y/5y/10y/30y`(ECOS, 일별 2010-01~2026-06; 30y는 2012-09~) → 월말 리샘플, yield_level/yield_slope_10y1y/yield_curvature + 6M z-score + 3년 롤링 백분위 + curve_regime/curve_inversion_flag
  - `tests/test_yield_curve_kr_factors.py` — 11 passed
  - `scripts/03_analyze/build_ppi_inflation_cycle_kr_factors.py` — `macro_macro_indices_kor_ppi`(ECOS, 월간 2010-01~2026-04) → kor_ppi_mom/yoy/yoy_chg3m + 12M z-score + 3년 롤링 백분위 + inflation_momentum_score/inflation_cycle_regime/inflation_accel_flag
  - `tests/test_ppi_inflation_cycle_kr_factors.py` — 12 passed
  - `scripts/03_analyze/build_commodity_momentum_factors.py` — `macro_commodities_copper/wti/brent`(yfinance, 일별 2009-12~2026-06, 4,138행/시리즈) → 월말 리샘플, copper/brent_ret_3m + 6M z-score + 3년 롤링 백분위 + commodity_cycle_score/cyclical_demand_regime/commodity_surge_flag
  - `tests/test_commodity_momentum_factors.py` — 12 passed
- DB 신규 테이블 (백업: `data/database/quant_data_20260615_211610_before_4newfactors_soxx_yc_ppi_commodity.sqlite`):
  - `factor_soxx_semicycle_month` (121개월, 2016-06~2026-06) / `factor_soxx_semicycle_catalog` (9행) — 2026-06 기준 soxx_close=602.72, soxx_ret_zscore_6m=-0.44, semi_momentum_score=0.427, semi_cycle_regime=strong_up, semi_rally_accel_flag=0
  - `factor_yield_curve_kr_month` (198개월, 2010-01~2026-06) / `factor_yield_curve_kr_catalog` (13행) — 2026-06 기준 yield_slope_10y1y=1.015, yield_slope_pctile_3y=1.0, curve_regime=steep, curve_inversion_flag=0
  - `factor_ppi_inflation_cycle_kr_month` (196개월, 2010-01~2026-04) / `factor_ppi_inflation_cycle_kr_catalog` (9행) — 2026-04 기준 kor_ppi_yoy=6.90%, kor_ppi_yoy_zscore_12m=2.61, inflation_cycle_regime=inflation_surge, inflation_accel_flag=1
  - `factor_commodity_momentum_month` (199개월, 2009-12~2026-06) / `factor_commodity_momentum_catalog` (12행) — 2026-06 기준 copper_pctile_3y=0.81, brent_pctile_3y=0.03, cyclical_demand_regime=neutral, commodity_surge_flag=0
- Verification: `pytest -q` → **308개 중 307 passed, 1 failed (기존 이슈, 본 작업과 무관 — `test_stock_detail_pipeline.py::test_export_to_web_includes_stock_detail_ticker_series_and_snapshots`, `export_web_data.py`의 `stock_detail` payload 미포함 이슈, Hermes의 이전 export_web_data 변경에 의함)**
- 주의사항:
  1. **OECD CLI 대체**: 사용자가 처음 선택한 후보는 "한국 OECD 선행지수(CLI) 경기싸이클"이었으나, `macro_macro_indices_kor_cli`(KORLOLITONOSTSAM)·`macro_macro_indices_usa_cli`(USALOLITONOSTSAM) 모두 FRED/OECD에서 **2024-01 이후 갱신이 전역적으로 중단된 죽은 시계열**임을 확인 → 동일한 "경기/물가 사이클" 취지의 ㉟한국 PPI 인플레이션 사이클로 대체 (사용자에게 사전 통지함).
  2. `factor_yield_curve_kr_month`의 `kor_gov30y`는 2012-09 이전 NaN (임의 보간 없음, 30y 채권 발행 이전 구간).
  3. `factor_ppi_inflation_cycle_kr_month`은 2026-04까지(ECOS 최신), 다른 신규 3종은 2026-06까지 — period 범위가 서로 다름에 주의.
  4. `factor_commodity_momentum_month`의 `brent_close`는 2026-03(118.35)~2026-04(114.01)에 급등 후 2026-05~06 급락(92~94) — yfinance 원천 데이터 그대로이며 임의 보정 없음. `brent_pctile_3y=0.03`(2026-06)은 이 급락 이후 3년 최저권을 반영.
  5. PPI 팩터(㉟)는 ZSCORE_WINDOW=12/MIN_ZSCORE_OBS=6 (YoY 시리즈 특성), 나머지 3종은 표준값 ZSCORE_WINDOW=6/MIN_ZSCORE_OBS=3 사용.
- Updated:
  - `00_context/index_factor.md` — 요약표에 ㉝~㊱ 4행 추가, ㉝~㊱ 상세 섹션 4개 신설, 팩터 결합 가이드(반도체/금리민감/원가압박/시클리컬 섹터 비중 조절 4행 추가)·레짐 조건부 필터링(㉝~㊱ 4줄 추가)·섹터 로테이션(글로벌 사이클 확인 행 추가)·데이터 소스 요약(㉝~㊱ 4행 추가)·종합 팩터 스코어 레짐 오버레이에 ㉝㉞㉟㊱ 추가
  - `00_context/index.md` — `index_factor.md` 설명 "36개 팩터 패밀리(①~㊱)"로 갱신, `scripts/03_analyze`/`tests` 섹션에 신규 파일 8개 항목 추가, SQLite DB 명세에 2026-06-15 신규 테이블 4쌍 블록 추가
- 다음 후보: 현재 식별된 우선순위 후보 모두 소진 — 추가 팩터 발굴은 신규 데이터 수집 또는 기존 raw 테이블 재조사 필요

## 2026-06-15 - Hermes
- Task: 웹 대시보드 `종목분석` 탭을 검색 가능한 `종목 시장 매력도` 화면으로 개편.
- Changed:
  - `scripts/03_analyze/export_web_data.py` — `stock_attractiveness` payload 생성 추가. 최신 KRX market snapshot, `earnings_consensus`, 최신 팩터 테이블을 ticker 단위로 결합하고 KOSPI 시총 상위 200 proxy 플래그/시가총액 구간/주요 팩터 조합 점수를 export.
  - `web/index.html` — `종목분석` 하위탭 `종목 시장 매력도` 추가, 종목명/코드 검색, 시장/KOSPI200 proxy/시가총액/업종/정렬/퀵필터 UI 및 회귀분석 시나리오 토글 영역 추가.
  - `web/quant_ui.js` — `renderStockAttractiveness()` 신규 구현. 종목명·최근가치지표·최근 영익·올해예상·내년예상·시총/거래·선택 시나리오 점수 테이블 렌더링, 퀵필터 및 시나리오 설명 토글 지원.
  - `web/quant_data.js` — `python scripts/03_analyze/export_web_data.py`로 재생성. `stock_attractiveness.rows` 2,770개, 기준일 2026-06-05, KOSPI200 proxy 200개 포함.
- Verification:
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과
  - `node --check web/quant_ui.js` / `node --check web/quant_data.js` → 통과
  - `python scripts/03_analyze/export_web_data.py` → 완료, `stock_attractiveness: 2770 rows loaded`
  - Node DOM mock 렌더링 검증: 삼성전자 검색 + KOSPI200 proxy 필터 결과 2개 렌더링, 시나리오 토글 HTML 생성 확인.
- Caveats:
  - 실제 KOSPI200 공식 구성종목 파일이 아니라 현재 프로젝트 제약에 맞춰 KOSPI 시가총액 상위 200 proxy를 사용.
  - Browser automation은 로컬 Chrome DevToolsActivePort 오류로 직접 콘솔 검증 불가. 대신 `node --check`와 DOM mock 렌더링으로 대체 검증.
  - export 중 pandas `FutureWarning`은 기존 fillna dtype 경고로, 파일 생성/렌더링 검증에는 영향 없음.

## 2026-06-11 (2) - Claude
- Task: 신규 퀀트 팩터 2종 구축 — ㉚한미 무역수지/수출입, ㉜원/달러 환율 모멘텀 (둘 다 기존 raw 데이터 재활용, 신규 수집 없음)
- Created:
  - `scripts/03_analyze/build_trade_balance_kr_us_factors.py` — `macro_trade_us_korea_monthly`(long format, series_id별 월별값 1957-01~2026-04) → series_id(XTEXVA01KRM667S/XTIMVA01KRM667S/EXPKR/IMPKR) pivot, korea_trade_balance/us_korea_trade_balance, korea_exports_yoy(+12M z-score) + export_momentum_score/export_cycle_regime(2x2 분면)
  - `tests/test_trade_balance_kr_us_factors.py` — 10 passed
  - `scripts/03_analyze/build_fx_usdkrw_factors.py` — `macro_exchange_rates_usd_krw`(yfinance, 일별 2009-12-31~2026-06, 4,288행) → 월말 리샘플, usd_krw_ret_1m/3m + 6M z-score + 3년 롤링 백분위 + won_strength_score/fx_regime/rapid_depreciation_flag
  - `tests/test_fx_usdkrw_factors.py` — 12 passed
- DB 신규 테이블 (백업: `data/database/backups/quant_data_20260611_before_fx_trade.sqlite`):
  - `factor_trade_balance_kr_us_month` (832개월, 1957-01~2026-04) / `factor_trade_balance_kr_us_catalog` (12행) — 2026-03(최신 확정월) 기준 korea_exports_yoy≈+47.9%, export_cycle_regime=expansion, export_momentum_score≈0.88
  - `factor_fx_usdkrw_month` (199개월, 2009-12~2026-06) / `factor_fx_usdkrw_catalog` (8행) — 2026-06 기준 usd_krw_close=1537.98, usd_krw_zscore_6m=1.31, won_strength_score≈0.28, fx_regime=won_very_weak, rapid_depreciation_flag=1 (원화 약세 가속)
- Verification: `pytest tests/ -q` → **246개 중 245 passed, 1 failed (기존 이슈, 본 작업과 무관 — `test_stock_detail_pipeline.py::test_export_to_web_includes_stock_detail_ticker_series_and_snapshots`, Hermes export_web_data.py `include_stock_detail=False` 변경에 의함)**
- 주의사항:
  1. `factor_trade_balance_kr_us_month` 마지막 행(2026-04)은 `korea_exports`/`korea_imports`(XTEXVA/XTIMVA, FRED 갱신 지연)가 아직 미수신이라 NaN — `korea_exports_yoy`/`export_cycle_regime`도 연쇄 NaN/unknown. 임의 보간 없음.
  2. `korea_exports_yoy_z12m`은 12M 롤링(min_periods=6) — 1957-01~1957-06 구간은 NaN.
  3. `factor_fx_usdkrw_month`의 `usd_krw_pctile_3y`/`fx_regime`은 36개월 롤링(min_periods=12) 기준 — 2009-12~2011-11 구간은 NaN/unknown. `usd_krw_close` 절대 레벨은 장기 우상향 추세이므로 레벨 자체를 risk-on/off로 단순 해석 금지, 반드시 3년 롤링 상대 평가(`fx_regime`) 사용.
  4. 빌드 스크립트 실행 순서상 `build_fx_usdkrw_factors.py`를 DB 백업 전에 1회 실행했으나 `to_sql(if_exists="replace")` 멱등 연산이라 데이터 손실 없음(이후 백업 정상 생성, 트레이드밸런스 적재는 백업 이후 수행).
- Updated: `00_context/index_factor.md` (요약표 ㉚㉜ 추가, ㉚㉜ 상세 섹션 신설, 팩터 결합 가이드/레짐 필터링/데이터소스 요약에 ㉚㉜ 반영, 종합 팩터 스코어 레짐 오버레이에 ㉚㉜ 추가), `00_context/index.md` (신규 스크립트/테스트/DB 테이블 항목 추가, index_factor.md 설명 "32개 팩터 패밀리"로 갱신)
- 다음 후보: 현재 식별된 우선순위 후보 모두 소진 (㉚㉛㉜ 완료) — 추가 팩터 발굴은 신규 데이터 수집 또는 기존 raw 테이블 재조사 필요

## 2026-06-11 - Claude
- Task: 신규 퀀트 팩터 1종 구축 — ㉛한국 신용스프레드 (회사채 AA-/BBB- vs 국고3y, 기존 raw 데이터 재활용, 신규 수집 없음)
- Created:
  - `scripts/03_analyze/build_credit_spread_kr_factors.py` — `macro_macro_indices_kor_corp_aa/bbb/kor_gov3y`(ECOS, 일별 2010-01-04~2026-06-05, 4,058행/시리즈) → 월말 리샘플, aa_spread/bbb_spread/bbb_aa_spread + 6M z-score + 3년 롤링 백분위 + credit_score/credit_regime/spread_widening_flag
  - `tests/test_credit_spread_kr_factors.py` — 11 passed
- DB 신규 테이블 (백업: `data/database/backups/quant_data_20260611_before_creditspread.sqlite`):
  - `factor_credit_spread_kr_month` (198개월, 2010-01~2026-06) / `factor_credit_spread_kr_catalog` (14행) — 2026-06 기준 bbb_aa_spread=5.806%p, credit_regime=tight, credit_score≈0.52 (국내 신용 환경 비교적 안정)
- Verification: `pytest tests/ -q` → **224개 중 223 passed, 1 failed (기존 이슈, 본 작업과 무관 — `test_stock_detail_pipeline.py::test_export_to_web_includes_stock_detail_ticker_series_and_snapshots`, Hermes export_web_data.py `include_stock_detail=False` 변경에 의함)**
- 주의사항:
  1. AA-/BBB- 모두 "3년물" 고시금리 기준 — 실제 발행사 스프레드와 괴리 가능 (ECOS 고시금리 특성)
  2. `bbb_aa_spread_pctile_3y`는 36개월 롤링 — 2010-01~2012-12 구간은 min_periods=12 미만이라 NaN
  3. ⑭(macro_spread, 미국 HY 기반)와 역할 분담: ⑭=글로벌 신용 사이클, ㉛=국내 신용 사이클. 두 지표 동반 risk-off 전환 시 신호 강도 ↑
- Updated: `00_context/index_factor.md` (요약표 ㉛ 추가, ㉛ 상세 섹션 신설, 팩터 결합 가이드/레짐 필터링/데이터소스 요약에 ㉛ 반영, 종합 팩터 스코어 레짐 오버레이에 ㉛ 추가, 기준일 2026-06-11), `00_context/index.md` (신규 스크립트/테스트/DB 테이블 항목 추가)
- 다음 후보 (이번에 함께 발견, 미작업): ㉚한미 무역수지(`macro_trade_us_korea_monthly`, 3,478행, 1957~2026 — Hermes 2026-06-10 수집, 미가공), ㉜원/달러 환율 모멘텀(`macro_exchange_rates_usd_krw`, 4,288행, 2009~2026 일별, 미가공)

## 2026-06-10 21:41 - Hermes
- Task: `trade_stats` 미국/한국 무역 통계 FRED 수집·SQLite 적재
- Changed:
  - `scripts/01_collect/collect_us_korea_trade_once.py` — FRED graph CSV timeout 대응: 프로젝트 `.env`의 `FRED_API_KEY`를 읽어 FRED observations API를 우선 사용하고, 실패 시 graph CSV fallback을 시도하도록 보강(키 값 미노출)
  - `data/database/quant_data.sqlite` — `macro_trade_*` 테이블 12개 적재/갱신
  - `data.md`, `00_context/index.md`, `00_context/work_state.md` — 수집 결과/테이블/lock 기록 갱신
- Created:
  - `data/raw/macro/trade_stats/fred_{BOPTEXP,BOPTIMP,EXPGS,IMPGS,EXPKR,IMPKR,XTEXVA01KRM667S,XTIMVA01KRM667S}.csv`
  - `data/raw/macro/trade_stats/us_korea_trade_fred_long.csv` — 4,112 rows
  - `data/raw/macro/trade_stats/us_korea_trade_fred_monthly.csv` — 3,478 rows
  - `data/raw/macro/trade_stats/us_trade_fred_quarterly_nipa.csv` — 634 rows
  - `data/raw/macro/trade_stats/us_korea_trade_fred_metadata.csv` — 8 rows, all success
  - `data/raw/macro/trade_stats/us_korea_trade_collection_summary.json`
  - DB backups: `data/database/quant_data.sqlite.backup_trade_stats_20260610_212826`, `data/database/quant_data.sqlite.backup_trade_stats_20260610_214100`
- Verification:
  - `python -m py_compile scripts/01_collect/collect_us_korea_trade_once.py` → 통과
  - `python scripts/01_collect/collect_us_korea_trade_once.py` → success_count=8, failed=[]
  - SQLite 검증: `macro_trade_us_korea_fred` 4,112 rows(1947-01-01~2026-04-01), `macro_trade_us_korea_monthly` 3,478 rows(1957-01-01~2026-04-01), `macro_trade_us_quarterly_nipa` 634 rows(1947-01-01~2026-01-01), `macro_trade_us_korea_metadata` 8 rows
- Caveats:
  - 1차 실행은 FRED graph CSV endpoint read timeout으로 600초 timeout 종료. DB 적재 전 중단되어 raw/DB trade 테이블은 생성되지 않았고, 백업 파일만 남음.
  - 월간 BoP/양자 통계와 분기 NIPA 통계는 단위·빈도·계절조정이 다르므로 metadata 기준으로 분리 사용 필요.

## 2026-06-10 (4) - Claude
- Task: 신규 팩터 3종 구축 — ㉗시장 수급 동향(투자자별 순매수) ㉘시장 밸류에이션 레벨(KOSPI PBR percentile) ㉙거시 검색 트렌드 심리(Google Trends) (모두 기존 raw 데이터 재활용, 신규 수집 없음)
- Created:
  - `scripts/03_analyze/build_market_money_flow_factors.py` — `money_flow_market_trading_value_{kospi,kosdaq}_20y` 일별(2006-06~2026-06) → 월간 집계, 외국인/기관계/연기금 순매수 백분위 → flow_score/flow_regime
  - `scripts/03_analyze/build_market_valuation_level_factors.py` — `valuation_kospi_fundamental_history`(일별 PBR, 2023-06~2026-06) 월간 집계 + `valuation_kospi_pbr_percentile`(스냅샷 10년 percentile) → pbr_pctile_3y/10y, valuation_regime
  - `scripts/03_analyze/build_macro_search_sentiment_factors.py` — `sentiment_pytrends_*`(15개 키워드, 주간 2021-05~2026-05) → 키워드별 자체-기간 백분위, 거시불안/리테일관심/테마 점수 산출
  - `tests/test_market_money_flow_factors.py` — 7 passed
  - `tests/test_market_valuation_level_factors.py` — 7 passed
  - `tests/test_macro_search_sentiment_factors.py` — 6 passed
- DB 신규 테이블 (백업: `data/database/quant_data_20260610_211807_before_3newfactors3.sqlite`):
  - `factor_market_money_flow_month` (482행, KOSPI 241+KOSDAQ 241, 2006-06~2026-06) / `factor_market_money_flow_catalog` (9행) — 최근월(2026-06) flow_regime: KOSPI=neutral, KOSDAQ=strong_inflow
  - `factor_market_valuation_level_month` (37개월, 2023-06~2026-06) / `factor_market_valuation_level_catalog` (5행) — 2026-06 pbr_pctile_10y=0.936(10년래 93.6%ile) → valuation_regime=very_expensive
  - `factor_macro_search_sentiment_month` (61개월, 2021-05~2026-05) / `factor_macro_search_sentiment_catalog` (9행) — 최근월(2026-05) anxiety_level=high, interest_level=very_high
- 검증: `pytest tests/ -q` → **213개 중 212 passed, 1 failed (기존 이슈, 본 작업과 무관)**
- 주의사항:
  1. **㉗ 백분위(foreign_net_pctile 등)는 전체 기간(2006-06~2026-06, 약 240개월) 기준** — 과거 시점 분석 시 look-ahead 주의, 최근 추세 판단 위주로 사용 권장
  2. **㉘ pbr_pctile_3y는 표본 37개월(2023-06~)로 짧음** — 상대 추세 참고용. `pbr_pctile_10y`는 `valuation_kospi_pbr_percentile` 단일 스냅샷(2026-06-05)에서만 제공되는 절대 레벨 보조치로 시계열이 아니며, 해당 월(2026-06) 외에는 NaN
  3. **㉙ pytrends `trend_score`는 키워드별 검색 배치 정규화 기준이 달라 키워드 간 절대값 비교 불가** — 반드시 "키워드 자체 기간 내 백분위"로만 사용. 백분위는 전체 샘플(2021-05~2026-05, 약 60개월) 기준으로 look-ahead 주의
  4. **테스트 1건 실패(`test_stock_detail_pipeline.py::test_export_to_web_includes_stock_detail_ticker_series_and_snapshots`)는 Hermes의 `export_web_data.py`(`include_stock_detail=False`) 변경으로 인한 기존 이슈이며 본 작업의 변경사항과 무관** (이전 (3) 항목과 동일 이슈, 누적 미해결)
  5. 콘솔 출력 한글 깨짐은 cp949/utf-8 터미널 인코딩 차이일 뿐 DB 저장값에는 영향 없음 (기존 스크립트와 동일한 현상)
- Updated: `00_context/index_factor.md` (㉗㉘㉙ 요약표/상세섹션 추가, 팩터 결합 가이드·섹터 로테이션·데이터 소스 요약 갱신, "26개"→"29개 팩터 패밀리"), `00_context/index.md` (신규 스크립트/테스트/DB 테이블/백업파일 등록)

## 2026-06-10 20:13 - Hermes
- Task: `web/quant_data.js`에 누락된 `sentiment` 데이터를 선별 포함하도록 웹 export 수정 및 대시보드 렌더링 재검증
- Changed:
  - `scripts/03_analyze/export_web_data.py` — 웹 UI가 쓰는 macro 키만 allowlist로 export, NAVER DataLab/pytrends/시장폭/레짐 조정 sentiment 포함, 대용량 `stock_detail`은 기본 제외(`include_stock_detail=False`)로 유지
  - `web/quant_data.js` — 재생성 완료. top-level keys: `macro`, `money_flow`, `sentiment`, `valuation`; sentiment 40 keys 포함
- Created (local, gitignored):
  - `scratch/verify_dashboard_tabs_20260610.js` — Puppeteer 렌더링 검증 스크립트
- Verification:
  - `python scripts/03_analyze/export_web_data.py` → 완료, `web/quant_data.js` 34,208,120 bytes 생성
  - JS 데이터 probe: sectorRows 2,310 / themeRows 396 / regimeRows 2,310 / pytrends_AI_daily 93 / pytrends_주식_monthly 262
  - `python -m py_compile scripts/03_analyze/export_web_data.py` → 통과
  - `node scratch/verify_dashboard_tabs_20260610.js` → `quant-sector-momentum` canvas 4/4 visible, `macro-industry` canvas 10/10 visible, macro/quant 주요 서브탭 렌더링 확인
- Caveats:
  - 브라우저 콘솔 404 1건은 `/favicon.ico`로 기능 영향 없음
  - export 중 pandas `FutureWarning` 및 빈 `fred_barley_sorghum_monthly.csv` warning은 기존 데이터/타입 경고이며 이번 렌더링 차단 요인은 아님

## 2026-06-10 (3) - Claude
- Task: 신규 팩터 3종 구축 — ㉔외국인 보유비중/한도소진율 ㉕시장 폭(ADL/TRIN) ㉖ADR 오버나잇 갭 시그널 (모두 기존 raw 데이터 재활용, 신규 수집 없음)
- Created:
  - `scripts/03_analyze/build_foreign_exhaustion_factors.py` — `stock_market_snapshot_{kospi,kosdaq}_foreign_exhaustion_by_ticker_20260605` 기반 외국인 지분율/한도소진율 횡단면 백분위 + foreign_room_score(매수여력)
  - `scripts/03_analyze/build_market_breadth_factors.py` — `sentiment_kr_adl`/`sentiment_kr_trin` 일별→월간 집계, ADL 추세 백분위 + TRIN 백분위 → breadth_score/breadth_regime
  - `scripts/03_analyze/build_adr_gap_signal_factors.py` — `valuation_adrs_*`(8개 대형주 ADR) 일별 등락률 → gap_bucket, `stock_detail_{ticker}_ohlcv`와 조인해 realized_gap_pct(실현 갭) 산출
  - `tests/test_foreign_exhaustion_factors.py` — 8 passed
  - `tests/test_market_breadth_factors.py` — 7 passed
  - `tests/test_adr_gap_signal_factors.py` — 8 passed
- DB 신규 테이블 (백업: `data/database/quant_data_20260610_202303_before_3newfactors2.sqlite`):
  - `factor_foreign_exhaustion_snapshot` (2,770행, snapshot_date=2026-06-05) / `factor_foreign_exhaustion_catalog` (7행) — room_bucket: very_high 2515 / high 184 / mid 48 / low 17 / very_low 6
  - `factor_market_breadth_month` (25행, 2024-06~2026-06) / `factor_market_breadth_catalog` (9행) — 최근월(2026-06) breadth_score=0.76(bullish)
  - `factor_adr_gap_signal_daily` (33,048행, 8종목, 2009-12~2026-06) / `factor_adr_gap_signal_catalog` (7행)
- 검증: `pytest tests/ -q` → **193개 중 192 passed, 1 failed (기존 이슈, 본 작업과 무관)**
- 주의사항:
  1. **㉔ 외국인 보유비중/한도소진율은 단일 시점 스냅샷**(2026-06-05) → 시계열 백테스트 불가, 횡단면 스크리닝 전용. 대부분 종목은 외국인 한도가 100%(=상장주식수)라 `foreign_room_score`가 매우 높게 나옴(very_high 2,515종목) — 규제업종(KEPCO·통신·금융 등) 일부만 한도 제약 존재
  2. **㉕ 시장 폭은 표본 25개월(2024-06~)로 짧음** — 백분위는 전체 샘플 기준 상대 추세 참고용, 절대 임계값으로 과신 금지
  3. **㉖ ADR 갭 시그널은 8종목 한정**(KB금융·신한지주·우리금융지주·POSCO홀딩스·KT·SK텔레콤·한국전력·LG디스플레이, 쿠팡은 국내 동일종목 없어 제외) → 종합 팩터 스코어에는 미포함, 해당 종목 단타 시 보조지표로만 사용. `adr_ret_1d_pct`↔`realized_gap_pct` 상관계수 약 +0.25(n=4,480)로 방향성 참고는 가능하나 단독 신호로는 약함
  4. **테스트 1건 실패(`test_stock_detail_pipeline.py::test_export_to_web_includes_stock_detail_ticker_series_and_snapshots`)는 Hermes의 `export_web_data.py`(`include_stock_detail=False`) 변경으로 인한 기존 이슈이며 본 작업의 변경사항과 무관**
  5. 콘솔 출력 한글 깨짐은 cp949/utf-8 터미널 인코딩 차이일 뿐 DB 저장값에는 영향 없음 (기존 스크립트와 동일한 현상)
- Updated: `00_context/index_factor.md` (㉔㉕㉖ 요약표/상세섹션 추가, 팩터 결합 가이드·섹터 로테이션·데이터 소스 요약 갱신, "23개"→"26개 팩터 패밀리"), `00_context/index.md` (신규 스크립트/테스트/DB 테이블/백업파일 등록)

## 2026-06-10 (2) - Claude
- Task: 신규 팩터 3종 구축 — ㉑사이즈(시가총액) ㉒배당수익률 ㉓유동성/거래회전율 (모두 기존 raw 데이터 재활용, 신규 수집 없음)
- Created:
  - `scripts/03_analyze/build_size_factors.py` — `stock_detail_{ticker}_market_cap` 기반 월말 시가총액 → log_market_cap, 횡단면 백분위, 3개월 시총 변화율 → small_cap_score
  - `scripts/03_analyze/build_dividend_yield_factors.py` — `stock_market_snapshot_{kospi,kosdaq}_fundamental_by_ticker_20260605`(DIV/DPS) → 배당지급 종목 대상 백분위 점수 + 섹터 내 백분위 + 버킷
  - `scripts/03_analyze/build_liquidity_turnover_factors.py` — `stock_detail_{ticker}_market_cap` 기반 월평균 거래대금/시총(회전율 proxy) + 자기 12개월 z-score → 횡단면 백분위 평균 → liquidity_score
  - `tests/test_size_factors.py` — 8 passed
  - `tests/test_dividend_yield_factors.py` — 9 passed
  - `tests/test_liquidity_turnover_factors.py` — 8 passed
- DB 신규 테이블 (백업: `data/database/quant_data_20260610_193119_before_3newfactors.sqlite`):
  - `factor_size_month` (14,171행, 395종목, 2023-06~2026-06) / `factor_size_catalog` (6행) — 최신월(2026-06) 버킷: small 119 / mid 118 / micro 78 / large 60 / mega 20
  - `factor_dividend_yield_snapshot` (2,721행, snapshot_date=2026-06-05, 배당지급 1,337종목) / `factor_dividend_yield_catalog` (7행) — 버킷: no_dividend 1384 / low 269 / very_high 268 / high 267 / very_low 267 / mid 266
  - `factor_liquidity_turnover_month` (14,171행, 395종목, 2023-06~2026-06) / `factor_liquidity_turnover_catalog` (6행) — 최신월(2026-06) 버킷: neutral 119 / low 105 / high 88 / very_high 47 / very_low 36
- 검증: `pytest tests/ -q` → **170 passed** (신규 25개 포함, pykrx deprecation warning 1건은 기존 이슈로 무관)
- 주의사항:
  1. `stock_detail_*_market_cap` 테이블은 396개 존재하나 60행 미만 1종목 제외 → 395종목만 ㉑㉓에 포함 (다른 OHLCV 기반 팩터의 종목 수 432와 차이 있음)
  2. **㉒ 배당수익률은 단일 시점 펀더멘털 스냅샷**(2026-06-05) → 시계열 백테스트 불가, 횡단면 스크리닝 전용. 배당 미지급(DIV=0) 종목은 `dividend_bucket="no_dividend"`로 분리, 백분위 계산에서 제외(스큐 방지)
  3. 콘솔 출력 한글 깨짐은 cp949/utf-8 터미널 인코딩 차이일 뿐 DB 저장값에는 영향 없음 (기존 스크립트와 동일한 현상)
- Updated: `00_context/index_factor.md` (㉑㉒㉓ 요약표/상세섹션 추가, 팩터 결합 가이드·데이터 소스 요약 갱신, "20개"→"23개 팩터 패밀리"), `00_context/index.md` (신규 스크립트/테스트/DB 테이블/백업파일 등록)

## 2026-06-10 (1) - Claude
- Task: 신규 팩터 4종 구축 — ⑰기술적 평균회귀(RSI/볼린저밴드/이격도) ⑱갭 트레이딩 신호 ⑲실적 모멘텀(어닝 가속도) ⑳섹터 ETF 자금흐름 (모두 기존 raw 데이터 재활용, 신규 수집 없음)
- Created:
  - `scripts/03_analyze/build_technical_meanrev_factors.py` — `stock_detail_{ticker}_ohlcv` 기반 RSI(14, Wilder)/볼린저밴드 %B(20일,2σ)/이격도(20·60일) → meanrev_score
  - `scripts/03_analyze/build_gap_trading_factors.py` — 시가 갭률/방향/버킷 + 60일 갭메움률 + 거래량 비율 → gap_signal_score
  - `scripts/03_analyze/build_earnings_momentum_factors.py` — `data/raw/valuation/earnings_consensus.csv` 파싱, YoY/QoQ 성장률(±300% 클립) + 흑자전환 플래그 → earnings_momentum_score
  - `scripts/03_analyze/build_sector_etf_flow_factors.py` — `data/raw/sector_etf/{sector}_{ticker}.csv`(19개) 월간 리샘플, 수익률/거래대금 Z-score 횡단면 백분위 → money_flow_score
  - `tests/test_technical_meanrev_factors.py` — 8 passed
  - `tests/test_gap_trading_factors.py` — 8 passed
  - `tests/test_earnings_momentum_factors.py` — 11 passed
  - `tests/test_sector_etf_flow_factors.py` — 8 passed
- DB 신규 테이블 (백업: `data/database/quant_data_20260610_191040_before_4newfactors.sqlite`):
  - `factor_technical_meanrev_snapshot` (431행, 최신 영업일 2026-06-02~05) / `factor_technical_meanrev_catalog` (6행)
  - `factor_gap_trading_snapshot` (431행) / `factor_gap_trading_catalog` (7행) — gap_down 128 / gap_up 113 / flat 90 / gap_down_strong 73 / gap_up_strong 27
  - `factor_earnings_momentum_snapshot` (2,732/2,742행, snapshot_date=2026-06-03, latest_quarter 2026.03 다수) / `factor_earnings_momentum_catalog` (8행)
  - `factor_sector_etf_flow_month` (1,487행, 2019-01~2026-06, 19개 섹터) / `factor_sector_etf_flow_catalog` (7행)
- 검증: `pytest tests/ -q` → **145 passed** (신규 35개 포함, pykrx deprecation warning 1건은 기존 이슈로 무관)
- 주의사항:
  1. **흑자전환(턴어라운드)**: 전기 ≤0 → 당기 >0 인 경우 `*_yoy`/`*_qoq` 성장률은 NaN (수학적으로 정의 불가), 대신 `op_turnaround_flag`/`net_turnaround_flag=1`로 표시. 임의 보간 금지.
  2. **⑲ 실적 모멘텀은 단일 시점 컨센서스 스냅샷**(2026-06-03) → 시계열 백테스트 불가, 횡단면 스크리닝 전용
  3. **섹터 ETF 19개**: `securities`와 `securities2`가 별도 그룹으로 존재 (18개 아님)
  4. 콘솔 출력 한글 깨짐은 cp949/utf-8 터미널 인코딩 차이일 뿐 DB 저장값에는 영향 없음 (기존 스크립트와 동일한 현상)
- Updated: `00_context/index_factor.md` (⑰⑱⑲⑳ 요약표/상세섹션 추가, 팩터 결합 가이드·데이터 소스 요약 갱신, 기준일 2026-06-10), `00_context/index.md` (신규 스크립트/테스트/DB 테이블/백업파일 등록)

## 2026-06-09 (9) - Claude
- Task: 신규 팩터 구축 — ⑯Piotroski F-Score (재무 품질)
- Created:
  - `scripts/01_collect/collect_dart_finstate_once.py` — DART 연간 사업보고서 수집 (BS/IS/CF 11개 계정, IS/CIS 통합 검색, CFS→OFS 폴백)
  - `scripts/03_analyze/build_piotroski_factors.py` — 9개 기준 F-Score 산출 (0~9 정수, 섹터 백분위, 버킷 분류)
  - `tests/test_piotroski_factors.py` — 12 passed
  - `data/raw/valuation/dart_finstate/finstate_all.csv` — 11,739행, 379종목
- DB 신규 테이블:
  - `factor_piotroski_snapshot` (379행, f_score 0~9, f_score_norm/sector_pct, F1~F9 개별 플래그)
  - `factor_piotroski_catalog` (13행)
- 검증: `pytest tests/test_piotroski_factors.py -v` → 12 passed
  - `python -c "import sqlite3; import pandas as pd; conn=sqlite3.connect('data/database/quant_data.sqlite'); print(pd.read_sql('SELECT f_bucket, COUNT(*) as n FROM factor_piotroski_snapshot GROUP BY f_bucket', conn))"`
- 수정 이슈:
  1. `_extract_account()` — IS/CIS 통합 검색: `divs = [sj_div, "CIS"] if sj_div == "IS" else [sj_div]`
  2. `test_full_positive_score` mock 데이터 AT_c=AT_p 동치 문제 → revenue_current 500,000→520,000으로 수정 (F9=1 보장)
- 주의사항: F-Score는 연간 사업보고서 기반 → 분기 업데이트 불가, 신규 상장 종목·지주사 일부 계정 누락 가능
- Updated: `00_context/index_factor.md` (⑯ 섹터 추가, 팩터 결합 가이드 갱신, 데이터 소스표 갱신)

## 2026-06-09 (8) - Claude
- Task: 신규 팩터 2종 구축 — ⑭매크로 스프레드 신호 / ⑮ROE 트렌드
- Created:
  - `scripts/03_analyze/build_macro_spread_factors.py` — 장단기 스프레드(한국/미국) + HY 크레딧 + VIX → macro_risk_score (월간)
  - `scripts/03_analyze/build_roe_trend_factors.py` — EPS/BPS 기반 implied TTM ROE + 추세 점수 (스냅샷+시계열)
  - `tests/test_macro_spread_factors.py` — 8 passed
  - `tests/test_roe_trend_factors.py` — 8 passed
- DB 신규 테이블:
  - `factor_macro_spread_month` (558행, 1993-01~2026-06, macro_risk_score 0~1)
  - `factor_macro_spread_catalog` (12행)
  - `factor_roe_trend_snapshot` (388행, roe_composite_score 0~1)
  - `factor_roe_trend_month` (14,059행, 백테스트용 월간 시계열)
  - `factor_roe_trend_catalog` (8행)
- 검증: `pytest tests/test_macro_spread_factors.py tests/test_roe_trend_factors.py` → 16 passed
- 수정 이슈: `_load_monthly()` resample 후 reset_index() 시 컬럼명 "date"를 "period"로 명시 필요
  → `monthly.index.name = "period"` 로 수정
- Updated: `00_context/index_factor.md` (⑭⑮ 섹터 추가, 팩터 결합 가이드 업데이트)

## 2026-06-09 (7) - Claude
- Task: 신규 팩터 2종 구축 — ⑫밸류에이션 복합(Value Composite) / ⑬52주 신고가+볼륨 서프라이즈(Price Quality)
- Created:
  - `scripts/03_analyze/build_value_composite_factors.py` — ①PER/PBR 백분위(35%) + ⑥선행PER(40%) + ⑩PEG(25%) 복합 점수
  - `scripts/03_analyze/build_price_quality_factors.py` — 52주 신고가 근접도 + 볼륨 서프라이즈 스냅샷
  - `tests/test_value_composite_factors.py` — 8 passed
  - `tests/test_price_quality_factors.py` — 7 passed
- DB 신규 테이블:
  - `factor_value_composite_snapshot` (395행, valuation_score 0~1, value_bucket 5단계)
  - `factor_value_composite_catalog` (5행)
  - `factor_price_quality_snapshot` (431행, high_52w_proximity, volume_surge_20d, price_quality_score)
  - `factor_price_quality_catalog` (5행)
- 검증: `pytest tests/test_value_composite_factors.py tests/test_price_quality_factors.py` → 15 passed
- 주의: valuation_score(factor_valuation_per_pbr_month)는 [-0.9, 0.9] 범위라 직접 사용 불가
  → per_percentile_sector, pbr_percentile_sector를 역산해 0~1 trailing_score 재계산함
- Updated: `00_context/index_factor.md` (⑫⑬ 섹터 추가, 팩터 결합 가이드 업데이트)

## 2026-06-09 (6) - Claude
- Task: 3개 신규 팩터 구축 — ①목표주가 괴리율 / ②PEG / ③공매도 잔고
- Created (수집기):
  - `scripts/01_collect/collect_analyst_target_price_once.py` — Naver Finance coinfo 페이지 목표주가/투자의견 스크래핑
  - `scripts/01_collect/collect_shorting_balance_once.py` — pykrx KRX 공매도 잔고 시계열 수집
- Created (팩터 빌더):
  - `scripts/03_analyze/build_target_price_factors.py` — 목표주가 괴리율 팩터
  - `scripts/03_analyze/build_peg_factors.py` — PEG 팩터
  - `scripts/03_analyze/build_shorting_factors.py` — 공매도 잔고 팩터
- Created (테스트):
  - `tests/test_target_price_factors.py` — 6 passed
  - `tests/test_peg_factors.py` — 7 passed
  - `tests/test_shorting_factors.py` — 6 passed
- DB 신규 테이블 (완료된 것):
  - `factor_target_price_snapshot` (620행, TP 618종목, 목표주가 괴리율·투자의견 종합)
  - `factor_target_price_catalog` (4행)
  - `factor_peg_snapshot` (2707행, PEG 산출 472종목)
  - `factor_peg_catalog` (4행)
  - `factor_shorting_month` — 공매도 수집 완료 후 적재 예정
  - `factor_shorting_catalog` (5행) — 공매도 수집 완료 후 적재 예정
- Raw 데이터 수집 완료:
  - `data/raw/valuation/analyst_target_price.csv` (620행, 목표주가 618종목)
  - `data/raw/factors/peg_snapshot.csv` (2707행)
  - `data/raw/factors/peg_factor_catalog.csv`
  - `data/raw/factors/target_price_snapshot.csv`
  - `data/raw/factors/target_price_factor_catalog.csv`
  - `data/raw/factors/shorting_balance_monthly.csv` — 수집 진행 중
- Verification:
  - `python -m pytest tests/test_peg_factors.py tests/test_target_price_factors.py tests/test_shorting_factors.py -v` → **19 passed**
  - PEG: 472종목 산출 (forward_per > 0 & eps_growth > 0 조건)
  - 목표주가: 618종목 (KOSPI 대형주 중심, 커버리지 제한)
- Caveats:
  - **목표주가 K/L 코드 주의**: ticker에 K/L suffix 붙은 우선주·파생 계열이 상승여력 상위에 노출됨. 실 활용 시 `[A-Z][0-9]{5}` 정규주식 코드 필터 권장
  - **공매도 pykrx 컬럼명 버그**: 초기 수집 시 `비율` 대신 `비중`으로 반환돼 0건 수집. `collect_shorting_balance_once.py` 수정 후 재수집 중
  - 목표주가는 수집 시점(2026-06-09) 기준 스냅샷 — 오래된 리포트 목표가 포함 가능
  - 공매도 KRX 세션 1시간 제한 (수집 중 만료 시 재실행 필요)

---

## 2026-06-09 (5) - Claude
- Task: `index_factor.md` 신규 생성 (팩터 전체 인덱스 문서)
- Created:
  - `C:\claude cowork\00_context\index_factor.md` — 8개 팩터 패밀리 전체 명세
- Modified:
  - `C:\claude cowork\00_context\index.md` — `index_factor.md` 파일 항목 추가
- 문서 내용:
  - 팩터 요약 현황 테이블 (8개 패밀리, 상태/테이블명/행수/기간/커버리지)
  - ①후행PER/PBR 밸류에이션, ②수급모멘텀, ③가격·거래량모멘텀 상세 컬럼 명세
  - ④DART 공시이벤트 (⚠️ 사용금지, 사유 3가지, 해금 기준 명시)
  - ⑤매크로 캘린더 서프라이즈, ⑥선행PER, ⑦시장·매크로 레짐, ⑧레짐 조정 섹터 관심도 상세
  - 팩터 결합 가이드 (종목 단면 분석 / 레짐 조건부 필터링 / 섹터 로테이션)
  - 공통 규칙 (점수 범위 0~1, 버킷 순서, NaN 처리 원칙, period 포맷)
- Verification:
  - 파일 생성 확인: `C:\claude cowork\00_context\index_factor.md`
  - index.md 업데이트 확인
- Caveats:
  - index.md의 폴더 크기/수정시각 메타데이터는 자동 갱신되지 않으므로 index_factor.md 행은 크기 `—` 기재

---

## 2026-06-09 (4) - Claude
- Task: 선행(Forward) PER 밸류에이션 팩터 신규 구축
- Created:
  - `scripts/03_analyze/build_forward_per_factors.py` — 컨센서스 EPS 파싱 + 섹터 내 선행PER 백분위 + 종합 점수
  - `tests/test_forward_per_factors.py` — 6개 단위 테스트 (all pass)
  - `data/raw/factors/forward_per_snapshot.csv` (2,707행)
  - `data/raw/factors/forward_per_factor_catalog.csv` (4행)
- DB 신규 테이블:
  - `factor_forward_per_snapshot` (2,707행, 651종목 forward_per 보유, 29섹터)
  - `factor_forward_per_catalog` (4행)
- 팩터 구성:
  - `forward_per` = 현재 종가 / 선행EPS (컨센서스 연간 예상 기준)
  - `per_discount_vs_trailing` = forward_per / trailing_per - 1 (음수 = 이익 성장)
  - `eps_growth_expected` = forward_eps / trailing_eps - 1
  - `forward_per_sector_pct` = 섹터 내 선행PER 백분위 (낮을수록 저평가)
  - `forward_valuation_score` / `forward_valuation_bucket` — 종합 점수/버킷
- Verification:
  - `python -m pytest tests/test_forward_per_factors.py -v` → **6 passed**
  - 삼성전자: forward_per=7.63x (trailing 49.81x), 섹터내 14%→deep_value
  - 현대차: forward_per=17.65x (trailing 8.39x, +110%), 섹터내 63%→expensive (EPS 역성장)
  - DB 백업: `quant_data_20260609_201257_before_forward_per_factors.sqlite`
- Caveats:
  - 스냅샷 단면 데이터 — 시계열 backtest 불가 (컨센서스 2026-06-05 수집 기준)
  - forward_per 산출 가능 종목: 651/2707 (애널리스트 커버리지 제한)
  - 컨센서스 EPS는 낙관 편향 존재 (실적 발표 전 하향 조정 경향)
  - LG에너지솔루션(373220)은 trailing EPS 음수로 per_discount 계산 제외됨

---

## 2026-06-09 (3) - Claude
- Task: KOSPI 시총 상위 10종목 퀀트 팩터 분석 리포트 생성
- Created:
  - `output/` 폴더 신규 생성
  - `output/kospi_top10_factor_analysis.txt` (332행) — 밸류에이션/모멘텀/수급 3팩터 종합 분석
  - `scripts/make_top10_report.py` — 리포트 생성 스크립트 (재실행 가능)
- 분석 내용:
  - 시총 상위 10종목 (삼성전자~HD현대중공업) × 3팩터 × 2026-06-01 기준
  - 종합 요약 테이블 + 종목별 상세 (백분위 바, 점수, 버킷, 방향 신호 포함)
  - 종합 신호: WATCH 3종목(삼성전자우/SK스퀘어/LG에너지솔루션), CAUTION 7종목
  - DART 공시 이벤트 팩터(④)는 factor_not_ready 격리 이유로 의도적 제외
- Caveats:
  - 밸류에이션 점수가 전체적으로 낮은 것은 최근 급등으로 PER/PBR이 역사적 고점 수준임을 반영
  - HD현대중공업(329180) flow_direction이 '?' 출력 — flow_direction='flat'이 FLOW_LABEL 미등록, 스크립트에서 처리 불필요(neutral 확인됨)

---

## 2026-06-09 (2) - Claude
- Task: DART 공시 이벤트 신호 팩터 → `factor_not_ready/` 격리 및 실제 분석 사용 금지 명시
- Created:
  - `data/raw/factors/factor_not_ready/` 폴더 신규 생성
- Moved:
  - `data/raw/factors/dart_event_signal_month.csv` → `data/raw/factors/factor_not_ready/dart_event_signal_month.csv`
  - `data/raw/factors/dart_event_signal_factor_catalog.csv` → `data/raw/factors/factor_not_ready/dart_event_signal_factor_catalog.csv`
- Modified:
  - `scripts/03_analyze/build_dart_event_signal_factors.py`: `OUTPUT_DIR` → `factor_not_ready/` 하위로 변경, docstring에 사용 금지 사유 3가지 및 준비 기준 명시
  - `00_context/index.md`: `factor_not_ready/` 섹션 신설(⚠️ 미완성 사유·준비 기준 표), DB 테이블·스크립트·테스트 항목에 **⚠️ 실제 분석 사용 금지** 표시 추가
- Verification:
  - `python -m pytest tests/test_dart_event_signal_factors.py -v` → **5 passed**
  - `data/raw/factors/` 내 dart 파일 잔류 없음 확인
  - DB 테이블 `factor_dart_event_signal_month` / `factor_dart_event_signal_catalog` 는 기존 그대로 유지 (참조 전용)
- Caveats:
  - DB 테이블은 이름 변경 없이 유지 — 참조용으로만 남고 실제 분석 파이프라인에서 제외해야 함
  - 사용 해금 기준: 최소 36개월 이력 확보 + 내부자 매수/매도 방향 분리 수집 후 `data/raw/factors/`로 이동

---

## 2026-06-09 - Claude
- Task: 밸류에이션 PER/PBR 팩터 — 시장 전체 단면 비교 → 섹터(업종) 내 비교 전환
- Modified:
  - `scripts/03_analyze/build_valuation_per_pbr_factors.py`
    - `SECTOR_MAP_PATH` 상수 추가 (`data/raw/stock_detail/sector_map.csv`)
    - `MIN_CROSS_SECTION=30` → `MIN_SECTOR_CROSS_SECTION=5` (섹터 내 최소 종목 기준)
    - `load_sector_map()` 함수 추가 (ticker→업종명 매핑)
    - `add_cross_sectional_factors()`: `groupby("period")` → `groupby(["period","sector"])`,
      컬럼명 `per_percentile_cross`/`pbr_percentile_cross` → `per_percentile_sector`/`pbr_percentile_sector`
    - `add_valuation_score()`: 위 컬럼명 변경 반영
    - `build_factor_catalog()`: 설명 "시장 전체에서" → "같은 섹터(업종) 내에서" 수정
    - `build_outputs()`: sector_map 로드 후 monthly에 left join 추가
  - `tests/test_valuation_per_pbr_factors.py`
    - `test_cross_sectional_percentile_returns_nan_when_sector_too_small` 리네임+수정
    - `test_cross_sectional_percentile_sector_relative` 신규 추가 (섹터간 독립 산출 검증)
    - `test_valuation_score_prefers_cheap_over_expensive`: 컬럼명 변경 반영
- Verification:
  - `python -m pytest tests/test_valuation_per_pbr_factors.py -v` → **6 passed**
  - `build_valuation_per_pbr_factors.py` 재실행: 14,136행, 395종목, 2023-06~2026-06
  - 2026-06-01 기준 섹터 24개 확인, NaN 분해: PER 자체 결측 97건 / 섹터 내 종목 5개 미만 17건
  - DB 백업: `quant_data_20260609_192814_before_valuation_sector_refactor.sqlite`
- Caveats:
  - `sector_map.csv`는 실행 당일 스냅샷 — 역사적 섹터 재분류를 반영하지 않음
  - 섹터 내 종목 수 5개 미만인 소형 섹터는 `per_percentile_sector`/`pbr_percentile_sector` NaN 처리됨

---

## 2026-06-08 22:30 - Claude
- Task: 5대 퀀트 팩터 후보군 신규 구축 중 ② 수급 모멘텀(외국인/기관 순매수 추세) 가공·적재 완료
  (사용자 지시: "수집 파이프라인까지 전부 새로 구축" — 이로써 ①②③④⑤ 5종 전부 완료)
- Created — ② 수급 모멘텀 (외국인/기관 순매수 비율 추세):
  - `scripts/01_collect/collect_stock_investor_trend_once.py` — 종목별 투자자 매매동향(외국인/기관 순매수, 보유비율) 수집
  - `scripts/03_analyze/build_investor_flow_momentum_factors.py`, `tests/test_investor_flow_momentum_factors.py` (5/5 pass)
  - DB: `factor_investor_flow_momentum_month`(5,553행, 432종목, 2025-06~2026-06), `factor_investor_flow_momentum_catalog`(6행)
- Verification (SQL, factor_investor_flow_momentum_month 기준):
  - 최신월(2026-06-01) `flow_bucket`×`flow_direction` 분포: strong_inflow/net_buying 128, strong_outflow/net_selling 105,
    inflow/net_buying 67, outflow/net_selling 51 — 방향·점수·버킷이 정합적으로 일치
  - `flow_score` 상위 종목(023160, 099320, 103140, 229640, 456160)이 모두 strong_inflow/net_buying으로 표기됨을 확인
  - catalog 6행 모두 정상 적재: foreign_net_ratio, foreign_net_ratio_change, zscore_own_6m, percentile_cross,
    foreign_ratio_pct/_change, flow_score/flow_bucket/flow_direction
  - 행/종목 sanity: 432종목 × 5,553행, 기간 2025-06-01~2026-06-01 (build 결과와 일치)
- Caveats:
  - **DB 백업 누락**: 본 스크립트 실행 전 `quant_data_*_before_investor_flow_momentum_factors.sqlite` 백업을 생성하지 못함
    (직전 백업은 21:54 `..._before_dart_event_signal_factors.sqlite`). 다만 이 실행은 `factor_investor_flow_momentum_month`/
    `factor_investor_flow_momentum_catalog` 두 테이블만 `if_exists="replace"`로 적재하는 멱등(idempotent) 연산이라
    기존 데이터 손실 위험은 없음 — 향후 재실행 시에는 사전 백업 절차를 준수할 것
  - 자기과거 z-score(`foreign_net_ratio_zscore_own_6m`)는 6개월 미만 구간에서 N/A 유지 (임의 보간 없음)
- 전체 테스트: `python -m pytest tests/ -q` → **41 passed** (신규 5개 포함, 기존 회귀 없음)

---

## 2026-06-08 22:00 - Claude
- Task: 5대 퀀트 팩터 후보군 신규 구축 (수집→가공→적재) 중 ①③④⑤ 완료
  (사용자 지시: "수집 파이프라인까지 전부 새로 구축")
- Backup:
  - `data/database/backups/quant_data_20260608_210037_before_valuation_per_pbr_factors.sqlite`
  - `data/database/backups/quant_data_20260608_210328_before_stock_price_momentum_factors.sqlite`
  - `data/database/backups/quant_data_20260608_214818_before_calendar_macro_release_shift_factors.sqlite`
  - `data/database/backups/quant_data_20260608_215402_before_dart_event_signal_factors.sqlite`
- Created — ① 밸류에이션 (PER/PBR 모멘텀):
  - `scripts/03_analyze/build_valuation_per_pbr_factors.py`, `tests/test_valuation_per_pbr_factors.py`
  - DB: `factor_valuation_per_pbr_month`(14,136행), `factor_valuation_per_pbr_catalog`(5행)
- Created — ③ 종목 가격·거래량 모멘텀:
  - `scripts/01_collect/...`(OHLCV 기반), `scripts/03_analyze/build_stock_price_momentum_factors.py`, `tests/test_stock_price_momentum_factors.py`
  - DB: `factor_stock_price_momentum_month`(15,374행), `factor_stock_price_momentum_catalog`(5행)
- Created — ④ DART 공시 이벤트 신호:
  - `scripts/01_collect/collect_dart_event_history_once.py` — 종목별 12개월 공시 이력(자사주/배당/임원·주요주주 지분변동) 수집,
    OpenDartReader는 내부 타임아웃이 없어 데몬스레드 `_call_with_timeout()` 래퍼로 행(hang) 방지
  - `scripts/03_analyze/build_dart_event_signal_factors.py`, `tests/test_dart_event_signal_factors.py` (5/5 pass)
  - 출력: `data/raw/valuation/dart_events/{ticker}.csv`(423종목), `data/raw/factors/dart_event_signal_month.csv`
  - DB: `factor_dart_event_signal_month`(5,499행, 423종목, 2025-06~2026-06), `factor_dart_event_signal_catalog`(4행)
- Created — ⑤ 캘린더 서프라이즈 → "발표치 추세-이탈(release shift)"로 정직하게 재정의:
  - `scripts/01_collect/collect_macro_release_history_once.py` — FRED 공식 API로 PAYEMS/CPIAUCSL/FEDFUNDS/UNRATE/ICSA 5개 시리즈 수집
  - `scripts/03_analyze/build_calendar_macro_release_shift_factors.py`, `tests/test_calendar_macro_release_shift_factors.py` (5/5 pass)
  - DB: `factor_macro_release_shift_period`(1,499행, 2011-06~2026-05), `factor_macro_release_shift_catalog`(3행)
- Verification:
  - 신규 테스트 4개 파일 전부 통과 (밸류에이션 5, 종목모멘텀 5, 캘린더release_shift 5, DART이벤트 5)
  - DART 이벤트 분포: insider 11,871 / dividend 974 / buyback 690건, 버킷 분포 quiet 3,257 / normal 1,671 / elevated 450 / high 121
  - 캘린더release_shift: 최근 CPI 발표가 "large_positive_shift"(z=2.07)로 정상 탐지
- Caveats (데이터 무결성 — "절대 임의 보간 금지" 준수):
  - **캘린더 서프라이즈는 forecast 시계열을 무료로 구할 수 없어 계산 불가** → "컨센서스 대비 서프라이즈"가 아니라
    "발표치 자체의 자기과거 추세 대비 이탈도(proxy)"로 투명하게 재정의했고, catalog `interpretation`에도 그 한계를 명시함
  - DART "임원·주요주주 소유상황보고"는 매수/매도 방향을 구분하지 않는 단순 신고 건수 →
    "내부자 매수 시그널"이 아니라 "신고 활동의 활발함"으로만 해석하도록 catalog에 명시
  - DART 수집: 432종목 중 423종목 성공 (9종목은 "could not find 'XXXXXX'" — 우선주 등 코드 추정, error.log 기록)
  - DART/release_shift 모두 historical이 약 12~15개월/시리즈로 짧음 → 자기과거 z-score 윈도우를 6~24개월로 보수적으로 설정,
    표준편차 0이거나 관측치 부족 구간은 N/A 유지 (임의 보간 없음)

---

## 2026-06-06 00:25 - Claude
- Task: 섹터 ETF 수집 + KOSPI ex-반도체 정확 계산
- Created:
  - `scripts/01_collect/collect_sector_etf_once.py` — 19개 섹터 ETF pykrx 수집
  - `scripts/03_analyze/build_kospi_ex_semi.py` — KOSPI ex-반도체 일별 계산 (직접 종목 시총 기반)
  - `data/raw/sector_etf/` — 19개 ETF CSV (semiconductor~steel 등)
  - `data/raw/factors/kospi_ex_semiconductor_daily.csv` — 4,042행 (2010-01-04~2026-06-05)
- Verification:
  - 검증 항등식 오차: 3.47e-18 (기계 정밀도, 완벽)
  - ETF 19개 성공/0 스킵: 대부분 2019~2026 (1,822행), 신규 ETF(방산/조선/원자력)는 상장 이후
  - 반도체 비중 이력: 2010년 15% → 2017년 26% → 2021년 28% → 2026년 43% (실제 비중 반영)
  - 2026-06-05: 반도체 비중 54.7%, KOSPI -5.54%, 반도체 -7.79%, ex-반도체 -2.83%
- Caveats:
  - KRX 반도체 지수(5044)는 2022년 이전 삼성전자·SK하이닉스 미포함 → 직접 종목 시총 방식 사용
  - 삼성전자+SK하이닉스+삼성전자우 합산 = 반도체 시총의 ~90% 커버 (나머지 ~10% 소외)
  - logging `%,.0f` 포맷 오류(표시만 문제, 데이터 저장 정상) → 차후 수정 필요
  - 방산(2023.07~), 조선(2022.09~), 원자력(2023.10~), 뷰티(2024.04~)는 역사 짧음 — 모델링 시 패딩 필요

---

## 2026-06-05 22:35 - Claude
- Task: 38개 팩터 통합 카탈로그 작성 및 저장
- Created:
  - `data/raw/factors/factor_catalog_master.csv` — 38개 팩터, 9개 패밀리, 컬럼 13개
    (factor_id, factor_family, family_description, question, factor_name, source_file, source_column, value_range, interpretation, signal_direction, update_frequency, preferred_use, note)
  - `scratch/build_factor_catalog_master.py` — 카탈로그 생성 스크립트
- Verification:
  - 38개 팩터 저장 확인, 9개 패밀리 구분
  - 기존 18개 (naver DataLab 9 + regime 9) + 신규 20개 (kor_macro 5 + kospi_positioning 6 + global_cycle 5 + naver_theme 4)
  - utf-8-sig 인코딩으로 Excel 호환
- Caveats:
  - F19~F38 신규 팩터는 카탈로그만 작성 — 실제 계산 스크립트 미구현 (별도 작업 필요)
  - F24 (foreign_net_buy_3m_zscore): 날짜 파싱 이슈로 계산값 검증 필요

---

## 2026-06-05 22:10 - Claude
- Task: 데이터 전수 검토 후 고가치 미활용 데이터 4종 대시보드 추가
- Changed:
  - `scripts/03_analyze/export_web_data.py` — data/raw/factors/ 로딩 추가 (regime, regime_adjusted, factor_catalog)
  - `web/index.html` — 선물/고객예탁금 섹션, 비철금속 테이블, Regime 카드(regime-card) 추가
  - `web/quant_ui.js` — renderRegimeCard 신규, renderMacroChart에 선물/예탁금/비철금속 렌더링, 섹터 모멘텀에 Regime-Adjusted 차트 추가
  - `web/quant_data.js` — export 재실행 (295MB→301MB, factors 3종 추가)
- Verification:
  - quant_data.js: "factors", "market_macro_regime", "regime_adjusted_sector", "stooq_nonferrous" 키 확인
  - JS/PY 문법 오류 없음
  - KOSPI PBR: 7.38배 (93.6%ile, 395종목)
- Caveats:
  - Regime 카드는 월별 갱신 (당월 latest만 표시)
  - 선물/고객예탁금 차트는 컬럼명이 한글 인코딩 — 인덱스 기반 접근 사용

---

## 2026-06-05 21:58 - Hermes
- Task: 시장/매크로 regime 기반 NAVER DataLab 관심도 신호 조정 팩터 생성
- Backup:
  - `data/database/backups/quant_data_20260605_215512_before_regime_adjusted_signals.sqlite` (현재 시간 기준 백업)
- Created:
  - `scripts/03_analyze/build_market_regime_adjusted_signals.py`
  - `tests/test_market_regime_adjusted_signals.py`
  - `data/raw/factors/market_macro_regime_month.csv`
  - `data/raw/factors/regime_adjusted_sector_interest_month.csv`
  - `data/raw/factors/regime_adjusted_factor_catalog.csv`
- SQLite:
  - `factor_market_macro_regime_month`: 558 rows, 1980-01-01~2026-06-01, 4 regimes
  - `factor_regime_adjusted_sector_interest_month`: 2,310 rows, 35 sectors, 2021-01-01~2026-06-01
  - `factor_regime_adjusted_catalog`: 9 rows, 2 families
- Verification:
  - TDD RED: 신규 테스트 3개가 스크립트 부재로 실패 확인
  - GREEN: `pytest tests/test_market_regime_adjusted_signals.py -q` → 3 passed
  - Full suite: `pytest tests/ -q` → 16 passed, 1 warning
- Caveat: 규칙 기반 regime-aware 후보 팩터이며 예측모델/백테스트 성과가 아님

---

## 2026-06-05 21:40 - Claude
- Task: index.md 재검토 후 섹터 모멘텀 대시보드 추가 및 index.md 업데이트
- Changed:
  - `scripts/03_analyze/export_web_data.py` — stock_market_snapshot 최신 날짜 파일 로딩 추가
  - `web/index.html` — 퀀트 탭에 "섹터 모멘텀" 서브탭 추가
  - `web/quant_ui.js` — renderSectorMomentumCharts 신규 함수 (35섹터 anchor_relative_ratio 랭킹, 1M/3M 모멘텀 산점도, 12M Z-Score)
  - `web/quant_data.js` — export_web_data.py 재실행 (stock_market_snapshot + 신규 naver_datalab 파일 포함)
  - `00_context/index.md` — 신규 스크립트/CSV 파일 명세 추가 (ECOS KOR_* 20종, CLI 5국, pytrends 30종, NAVER DataLab 6종)
- Verification:
  - quant_data.js: 276MB→295MB (stock_market_snapshot 2,770종목 포함)
  - kospi_fundamental_by_ticker, KOR_CALL_RATE 키 quant_data.js 포함 확인
  - JS/PY 문법 오류 없음
- Caveats:
  - 섹터 모멘텀 차트는 anchor_relative_ratio 기준 — 값이 1 미만이면 시장 평균 이하 관심도
  - stock_market_snapshot은 quant_data.js 크기 증가 유발 (295MB), 필요 시 별도 JS 파일 분리 고려

---

## 2026-06-05 21:24 - Hermes
- Task: NAVER DataLab 섹터 관심도 모델링 전 1차 가공 팩터 후보군 제작
- Changed:
  - `data/database/quant_data.sqlite` — features/catalog/classified 테이블 3개 적재
  - `data.md` — 섹터 관심도 1차 가공 팩터 후보군 섹션 추가
- Created:
  - `scripts/03_analyze/build_naver_datalab_sector_features.py` — 3개 질문별 팩터 후보군 생성
  - `tests/test_naver_datalab_sector_features.py` — features/catalog/classified TDD 테스트
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_features_month.csv` — 2,310 rows
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_factor_catalog.csv` — 9 rows, 3 families
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_classified_month.csv` — 6,930 rows
  - `data/database/backups/quant_data_20260605_211500_before_naver_sector_features.sqlite`
- Verification:
  - SQLite `sentiment_naver_datalab_sector_interest_month_features`: 2,310 rows, 35 sectors, 2021-01-01~2026-06-01
  - SQLite `sentiment_naver_datalab_sector_interest_factor_catalog`: 9 factor candidates, 3 families
  - SQLite `sentiment_naver_datalab_sector_interest_month_classified`: 6,930 rows, 35 sectors, 3 families
  - `pytest tests/ -q` → 13 passed, 1 warning
- Caveats:
  - 모델 예측 결과가 아니라 모델링 전 1차 가공/팩터 후보군
  - NAVER DataLab ratio와 anchor 보정값은 절대 검색량이 아님

---

## 2026-06-05 21:02 - Hermes
- Task: NAVER DataLab 전체 섹터 관심도 확장 수집 및 SQLite 적재
- Changed:
  - `scripts/01_collect/collect_naver_datalab_once.py` — `--universe sector`, 35개 섹터 keyword universe, `market_anchor` 포함 chunking, anchor 대비 factor 계산 추가
  - `tests/test_naver_datalab_collector.py` — 섹터 universe/anchor chunk/factor 계산 테스트 추가
  - `data/database/quant_data.sqlite` — NAVER 섹터 raw/factor 테이블 2개 적재
  - `data.md` — 섹터 DataLab 수집 기록 추가
- Created:
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_month.csv`
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_factor_month.csv`
  - `data/database/backups/quant_data_20260605_210215_before_naver_sector_datalab.sqlite`
- Verification:
  - NAVER DataLab API 월별 수집 성공: raw 2,904 rows, 36 groups(anchor 포함), 2021-01-01~2026-06-01
  - factor 테이블: 2,310 rows, 35 sector groups, 2021-01-01~2026-06-01
  - SQLite `sentiment_naver_datalab_sector_interest_month_raw`: 2,904 rows
  - SQLite `sentiment_naver_datalab_sector_interest_month_factor`: 2,310 rows
  - `pytest tests/ -q` → 10 passed, 1 warning
- Caveats:
  - NAVER DataLab ratio는 절대 검색량이 아닌 요청별 상대 지수
  - `market_anchor` 보정은 chunk 간 비교를 위한 근사 정규화이며 절대 검색량 복원이 아님

---

## 2026-06-05 21:10 - Claude
- Task: 대시보드 신규 데이터 섹션 추가 (한국금리/CLI9국/pytrends/NAVER DataLab)
- Changed:
  - `scripts/03_analyze/export_web_data.py` — pytrends+NAVER DataLab sentiment 로딩, KOR BBB-스프레드·장단기금리차 파생지표 추가
  - `web/index.html` — 한국금리 섹션, NAVER DataLab 카드, 산업분석 탭 내용 추가
  - `web/quant_ui.js` — 한국금리 9개 차트, OECD CLI 4→9개국, NAVER DataLab 렌더링, renderIndustryCharts 신규 함수
  - `web/quant_data.js` — export_web_data.py 재실행으로 재생성
- Verification:
  - export_web_data.py 문법 OK, quant_ui.js 문법 OK
  - 신규 macro 키: KOR_BASE_RATE, KOR_CALL_RATE, KOR_CD91, KOR_GOV3Y/5Y/10Y, KOR_CORP_AA/BBB, kor_corp_spread_bbb(198행), kor_yield_spread(198행)
  - 신규 sentiment 키 33개 (pytrends 30 + naver 3)
  - OECD CLI: BRA/DEU/FRA/GBR/IND 추가로 9개국 완성
- Caveats:
  - quant_ui.js의 pytrends 키명은 파일명 기반(한글 포함) — 브라우저에서 정상 동작 여부 확인 필요
  - NAVER DataLab sentiment 키: `naver_naver_datalab_theme_interest_month` (naver_ prefix 중복 발생 가능, 필요 시 수정)

---

## 2026-06-05 20:45 - Claude
- Task: pytrends 주 1회(월요일) 실행 제한 적용
- Changed:
  - `scripts/01_collect/collect_pytrends.py` — 월요일 가드 추가, `--force` 인자로 우회 가능
  - `scripts/pipeline.py` — collect 단계에 `collect_pytrends.py` 등록
- Verification:
  - 목요일 실행 → `[Trends] 오늘은 월요일이 아님 (weekday=4) — 스킵` 정상 출력
  - `--force` 실행 → 즉시 수집 시작 정상 확인
- Caveats: 없음

---

## 2026-06-05 20:40 - Claude
- Task: OECD CLI + pytrends 수집 구현
- Changed:
  - `scripts/01_collect/01_macro.py` — FRED_TICKERS에 DEU/GBR/FRA/IND/BRA CLI 5개 추가
  - `scripts/01_collect/collect_oecd_cli_once.py` — OECD 직접 API 히스토리 부재 확인, FRED 기반으로 전환
  - `requirements.txt` — pytrends, python-dotenv 추가
- Created:
  - `scripts/01_collect/collect_pytrends.py` — Google Trends 15개 키워드 월별/일별 수집
  - `data/raw/macro/macro_indices/DEU_CLI.csv` (529행), `GBR_CLI.csv` (529행), `FRA_CLI.csv` (529행), `IND_CLI.csv` (358행), `BRA_CLI.csv` (421행)
  - `data/raw/sentiment/pytrends_{keyword}_monthly.csv` x15 (262행, 5년)
  - `data/raw/sentiment/pytrends_{keyword}_daily.csv` x15 (93행, 90일)
- Verification:
  - FRED OECD CLI 5개국 전부 OK (358~529행)
  - pytrends 15개 키워드 성공 15/0 실패
- Caveats:
  - OECD 직접 API(sdmx.oecd.org DF_CLI v4.1)는 전체 히스토리 미제공 — FRED 미러 사용
  - pytrends Google 요청 제한으로 주 1회 실행 권장
  - KOSIS_API_KEY Hermes 등록 완료 — KOSIS 수집 스크립트 별도 필요

---

## 2026-06-05 19:52 - Hermes
- Task: 확보된 KRX/DART/ECOS API 기반 퀀트 데이터 수집, SQLite 적재, 웹 데이터 재생성
- Changed:
  - `scripts/01_collect/03_money_flow.py` — `time` import 누락 보정
  - `data.md` — 2026-06-05 API 수집 기록 추가
  - `web/quant_data.js` — DB 기반 웹 퀀트 데이터 재생성
  - `data/database/quant_data.sqlite` — raw CSV 555개 재적재 및 신규 스냅샷 테이블 포함
- Created:
  - `data/database/backups/quant_data_20260605_193436_before_api_collection.sqlite`
  - `data/raw/stock_market_snapshot/*.csv`
  - `scratch/run_api_quant_collection_20260605.py`
  - `scratch/run_api_quant_collection_targeted_20260605.py`
  - `scratch/run_api_quant_collection_remaining_20260605.py`
  - `scratch/collect_krx_market_snapshot_20260605.py`
- Verification:
  - KRX 로그인 성공 후 KOSPI 948종목, KOSDAQ 1,822종목 스냅샷 수집
  - DART 당일 공시 709 rows, 접수일 20260605 적재 확인
  - KOSPI/KOSDAQ 20년 수급 각 4,933 rows, 2006-06-01~2026-06-05 확인
  - KOSPI PBR/PER 이력 4,042 rows, 2010-01-04~2026-06-05 확인
  - `load_to_db.py`: CSV 555개 SQLite 적재, DB 전체 628 tables 확인
  - `export_web_data.py`: `web/quant_data.js` 재생성 완료
- Caveats:
  - FRED 신규 후보 일부 timeout은 `macro_quant_metadata.status='failed'`로 보존
  - `fred_barley_sorghum_monthly.csv` 빈 파일은 DB 적재 실패/제외됨
  - 396종목 장기 상세 수집은 공매도 잔고 API 병목으로 중단하고 전종목 일별 스냅샷으로 대체

---

## 2026-06-05 20:05 - Claude
- Task: ECOS API 확장 — KeyStatisticList 확장 + StatisticSearch 역사 시계열 수집
- Changed:
  - `scripts/01_collect/01_macro.py` — ECOS_KEY_STAT_MAP 6개→18개 (콜금리, KORIBOR3M, 국고채5Y/10Y, CPI, PPI, 산업생산, 실업률, BSI, 수출물가, 외환보유액 추가)
- Created:
  - `scripts/01_collect/collect_ecos_history_once.py` — StatisticSearch 기반 역사 시계열 1회 수집 (18개 지표)
  - `scratch/ecos_api_research_20260605.md` — API 코드 조사 결과 임시 저장
- Verification:
  - StatisticSearch 정상 작동 확인 (이전 메모리와 달리 현재 사용 가능)
  - 18개 지표 수집 성공, KOR_ 파일 24개 (기존 포함) raw/macro/macro_indices/ 저장
  - 금리 시계열(일별): 4,058행 2010-01-04 ~ 2026-06-05
  - 기준금리(월별): 198행 2010-01-01 ~ 2026-06-01
  - PPI(월별): 196행 2010-01-01 ~ 2026-04-01
  - 외환보유액(월별): 197행 2010-01-01 ~ 2026-05-01
- Caveats:
  - KOR_M2: StatisticSearch는 2004년 이전 데이터만 제공 → 01_macro.py KeyStatisticList 누적 방식 유지
  - KOR_CPI, KOR_IIP, KOR_CLI: 기존 FRED 수집분 존재, ECOS 버전은 별도 파일로 공존
  - collect_ecos_history_once.py는 1회성 수집용 — 매일 증분은 01_macro.py fetch_ecos_data()가 담당

---

## 2026-06-05 19:17 - Claude
- Task: KRX OpenAPI 연결 확인 및 인증 정보 등록
- Changed:
  - `.env` — KRX_ID, KRX_PW 추가 (값 미기록)
- Verification:
  - pykrx 1.2.8 KRX 로그인 성공 (세션 유효 2026-06-05 20:15까지)
  - KOSPI 지수 OHLCV: 정상 수신 (2026-06-04 종가 8,639.41)
  - KOSPI 외국인/기관/연기금 매매동향: 정상 수신
  - 005930 공매도 잔고: 정상 수신
- Caveats:
  - pykrx 1.2.8부터 KRX 회원 로그인 필수 (기존 무인증 스크래핑 불가)
  - 세션 토큰은 발급 후 ~1시간 유효 (pykrx가 내부 자동 갱신)
  - KRX_ID/KRX_PW는 `.env` 단일 정본에서만 관리

---

## 2026-06-04 23:20:03 - Hermes
- Task: Claude/Hermes 동시 협업 규칙 적용
- Created:
  - `C:\claude cowork\00_context\collaboration.md`
  - `C:\claude cowork\00_context\work_state.md`
  - `C:\claude cowork\00_context\claude_start_prompt.md`
  - `C:\claude cowork\01_projects\Anal_reports\AGENTS.md`
  - `C:\claude cowork\01_projects\Anal_reports\CHANGELOG_AGENT.md`
- Changed:
  - `C:\claude cowork\00_context\AGENTS.md`
  - `C:\claude cowork\00_context\index.md`
- Verification:
  - 파일 생성 완료
  - 00_context/AGENTS.md에 협업 규칙 링크 추가
  - 00_context/index.md에 Multi-Agent Collaboration Files 섹션 추가
- Caveats:
  - API 키 값은 기록하지 않음
  - `.env`를 API 키 단일 정본으로 지정

## 2026-06-05 20:12 - Hermes
- Task: KOSIS OpenAPI 키를 프로젝트 `.env` 정본에 등록하고 통합검색 API 연결을 검증
- Changed: `.env`, `CHANGELOG_AGENT.md`, `00_context/work_state.md`
- Created: 없음
- Verification: KOSIS statisticsSearch.do 호출 성공; status=200, 검색 결과 토큰 5건 확인
- Caveats: API 키 원문은 로그/문서에 기록하지 않음.
## 2026-06-05 20:25 - Hermes
- Task: FRED API 키를 프로젝트 `.env` 정본에 등록하고 FRED 공식 API 연결을 검증
- Changed: `.env`, `CHANGELOG_AGENT.md`, `00_context/work_state.md`
- Created: 없음
- Verification: FRED series/observations(DGS10) 호출; status=200, observations=1, result=success
- Caveats: API 키 원문은 로그/문서에 기록하지 않음. DB/raw 데이터는 수정하지 않음.
## 2026-06-05 20:38 - Hermes
- Task: NAVER DataLab API 인증 정보를 프로젝트 `.env` 정본에 등록하고 연결을 검증
- Changed: `.env`, `CHANGELOG_AGENT.md`, `00_context/work_state.md`
- Created: 없음
- Verification: NAVER DataLab search 호출; status=200, results=1, data_points=6, result=success
- Caveats: Client ID/Secret 원문은 로그/문서에 기록하지 않음. DB/raw 데이터는 수정하지 않음.

## 2026-06-05 20:50 - Hermes
- Task: NAVER DataLab 테마/섹터 검색 관심도 수집 기능 구현, raw 수집, SQLite 단일 테이블 적재
- Changed:
  - `scripts/01_collect/collect_naver_datalab_once.py`
  - `tests/test_naver_datalab_collector.py`
  - `data.md`
  - `C:\claude cowork\00_context\index.md`
  - `C:\claude cowork\00_context\work_state.md`
  - `data/database/quant_data.sqlite`
  - `CHANGELOG_AGENT.md`
- Created:
  - `data/raw/sentiment/naver_datalab/naver_datalab_theme_interest_month.csv`
  - `data/database/backups/quant_data_20260605_204900_before_naver_datalab.sqlite`
  - `scratch/naver_datalab_verify_20260605.py`
- Verification:
  - TDD RED: 신규 테스트가 `collect_naver_datalab_once.py` 부재로 실패 확인
  - TDD GREEN: `pytest tests/test_naver_datalab_collector.py -q` → 4 passed
  - 실제 수집: NAVER DataLab 월별 396 rows, 2021-01-01~2026-06-01, 6 groups 저장
  - SQLite: `sentiment_naver_datalab_theme_interest_month` 396 rows, 2021-01-01~2026-06-01, 6 groups 적재
  - 전체 테스트: `pytest tests/ -q` → 7 passed, 1 warning
- Caveats:
  - NAVER DataLab ratio는 절대 검색량이 아니라 기간/그룹 기준 상대 지수
  - NAVER DataLab Search API의 keyword group 제한 때문에 5개 그룹 단위로 분할 호출
  - Client ID/Secret 원문은 로그/문서에 기록하지 않음

## 2026-06-24 20:22 - Claude
- Task: ㊶ 분봉(1분 단위) 체결강도/단기모멘텀 팩터 신규 구축 — 퀀트 데이터 공백 보강 1단계(분봉/호가)
- Changed:
  - `00_context/index.md`
  - `00_context/index_factor.md`
  - `00_context/work_state.md`
  - `CHANGELOG_AGENT.md`
- Created:
  - `scripts/01_collect/collect_minute_tick_once.py` — Naver Finance `sise_time.naver`(분별시세) 페이지에서 1분 단위 체결가/매도호가/매수호가/누적거래량/분당거래량 수집 (관심종목 `data/config/stocks.json` 57종목, requests.Session+UA, 3회 재시도+지수백오프)
  - `scripts/03_analyze/build_minute_tick_factors.py` — 매수/매도 체결(aggressor) 분류 기반 체결강도·단기모멘텀·거래량가속 팩터 산출
  - `tests/test_minute_tick_factors.py` — 5개 단위테스트 (체결강도 계산, 거래량가속 감지, 최신 거래일만 사용, 빈 디렉토리 처리, 점수 범위)
  - `data/raw/intraday/{ticker}_minute_history.csv` × 57개 종목
  - `data/raw/factors/minute_tick_snapshot.csv`, `data/raw/factors/minute_tick_factor_catalog.csv`
  - `data/database/quant_data_20260624_202144_before_minute_tick_factor.sqlite` (백업)
- DB 테이블: `factor_minute_tick_snapshot` (57행), `factor_minute_tick_catalog` (8행)
- Verification:
  - 수집: 57/57 종목 성공, 종목당 357~381행 (당일 09:00~15:30 1분 단위)
  - `pytest tests/test_minute_tick_factors.py -q` → 5 passed
  - `pytest -q` (전체) → 327 passed, 1 failed (기존 `test_stock_detail_pipeline.py` 1건은 본 작업과 무관한 기존 `export_web_data.py` 이슈로 격리 실행에서도 동일 재현 확인)
  - 매수체결강도 상위: 삼성전자(005930) minute_tick_score 0.91 등 확인
- Caveats:
  - Naver `sise_time.naver`는 **당일 분봉만** 제공 — 과거 일자 조회 불가. 매 거래일 실행해 `{ticker}_minute_history.csv`에 누적해야 시계열이 쌓이며, 현재는 수집 1일차라 자기 과거 비교(z-score 등) 불가, 횡단면 스크리닝 전용 스냅샷.
  - 관심종목(`stocks.json`, 57종목) 한정 — 퀀트 유니버스(395종목) 전체 미커버. 확장 시 동일 스크립트의 universe 로딩만 교체하면 됨.
  - `thistime` 파라미터는 반드시 `YYYYMMDDHHMMSS` 전체 포맷 필요(시각만 넘기면 빈 테이블 반환됨) — 수집 스크립트는 당일 날짜+"153000"으로 고정.
  - 호가창 잔량(원장 깊이)은 이 소스에서 제공하지 않음 — 매도/매수는 최우선 호가 1단계만 포함.

## 2026-06-24 20:34 - Claude
- Task: ㊷ 내부자 매매 신호(방향분리) 팩터 신규 구축 — 퀀트 데이터 공백 보강 2단계, ④ DART 이벤트 신호의 "매수/매도 방향 미분리" 사유 해결
- Changed:
  - `00_context/index.md`
  - `00_context/index_factor.md`
  - `00_context/work_state.md`
  - `CHANGELOG_AGENT.md`
- Created:
  - `scripts/01_collect/collect_dart_insider_trading_once.py` — OpenDartReader `major_shareholders_exec()` (임원ㆍ주요주주 소유보고)로 종목별 증감수량(부호: 양수=취득/매수, 음수=처분/매도) 수집, 432종목, 3회 재시도+30초 타임아웃 스레드 래퍼(기존 dart_event_history 패턴 재사용)
  - `scripts/03_analyze/build_insider_trading_factors.py` — 월별 매수/매도 수량·건수 분리 집계, 자기과거 6개월 z-score, 횡단면 백분위, 종합 점수/버킷
  - `tests/test_insider_trading_factors.py` — 5개 단위테스트 (월별 매수/매도 분리, 방향 분류, z-score 최소이력, 빈 디렉토리, 점수 범위)
  - `data/raw/valuation/dart_insider_trading/{ticker}.csv` × 423개 (396 데이터 보유, 27 이력없음)
  - `data/raw/factors/insider_trading_month.csv`, `data/raw/factors/insider_trading_factor_catalog.csv`
  - `data/database/quant_data_20260624_203348_before_insider_trading_factor.sqlite` (백업)
- DB 테이블: `factor_insider_trading_month` (2,843행/396종목), `factor_insider_trading_catalog` (8행)
- Verification:
  - 수집: 432종목 중 396 수집(매수/매도 분리 확인, 예: 005930 2,608건 중 매수 2,554/매도 52), 27 이력없음, 9 실패(DART status 013 무응답 등)
  - `pytest tests/test_insider_trading_factors.py -q` → 5 passed
  - `pytest -q` (전체) → 332 passed, 1 failed (기존 `test_stock_detail_pipeline.py` 1건, 본 작업과 무관 — 격리 재현 확인된 사전 이슈)
  - 최신월(2026-06) 강한 매수 상위 10종목 점수 0.81~0.92 분포 확인
- Caveats:
  - 이력 약 24개월(2024-06~2026-06) — ④ 사용해금 기준(36개월)에는 아직 못 미침. 다만 매수/매도 방향 분리는 완전히 해결되어 ④와 달리 **사용 가능**으로 표시.
  - 당월 보고가 없는 종목/월은 0건이 아니라 활동없음(no_activity)으로만 표시, 임의 보간 없음.
  - 임원·주요주주의 보고 사유가 전부 "시장 매수/매도"는 아님(스톡옵션 행사, 상속, 선임 시 일괄 보유주식 신고 등 포함) — 1차 근사 신호로 한정.

## 2026-06-24 20:45 - Claude
- Task: ㊸ 종목별 뉴스 헤드라인 감성(키워드 1차 근사) 팩터 신규 구축 — 퀀트 데이터 공백 보강 3단계
- Changed:
  - `00_context/index.md`
  - `00_context/index_factor.md`
  - `00_context/work_state.md`
  - `CHANGELOG_AGENT.md`
- Created:
  - `scripts/01_collect/collect_stock_news_once.py` — Naver Finance 종목 메인페이지(item/main.naver, UTF-8 인코딩 — 다른 페이지 대부분 EUC-KR과 다름) "뉴스공시" 섹션에서 종목당 최근 ~10건 헤드라인(제목+날짜) 수집, 432종목, dedup append 누적 저장
  - `scripts/03_analyze/build_news_sentiment_factors.py` — 금융 긍정/부정 키워드 사전(각 26~28개)으로 제목 단위 극성 판정, 종목별 집계 점수/버킷 산출
  - `tests/test_news_sentiment_factors.py` — 5개 단위테스트 (키워드 매칭, 집계, 빈 디렉토리, 점수/버킷 계산, 버킷 임계값)
  - `data/raw/news/{ticker}_headlines_history.csv` × 432개
  - `data/raw/factors/news_sentiment_snapshot.csv`, `data/raw/factors/news_sentiment_factor_catalog.csv`
  - `data/database/quant_data_20260624_204520_before_news_sentiment_factor.sqlite` (백업)
- DB 테이블: `factor_news_sentiment_snapshot` (432행), `factor_news_sentiment_catalog` (6행)
- Verification:
  - 수집: 432/432 종목 성공 (종목당 최대 10건 헤드라인)
  - `pytest tests/test_news_sentiment_factors.py -q` → 5 passed
  - `pytest -q` (전체) → 337 passed, 1 failed (기존 `test_stock_detail_pipeline.py` 1건, 본 작업과 무관한 사전 이슈)
  - 긍정 감성 상위 종목 점수 0.70~0.75 확인 (005290, 005935, 028300, 240810 등 strong_positive)
- Caveats:
  - **키워드 매칭 기반 1차 근사** — 본문 미반영, 제목만 분석, ML 감성모델 아님. 반어법/문맥 오판 가능.
  - Naver 뉴스공시 섹션은 종목당 최근 ~10건만 노출, 과거 페이지네이션 없음 → 매 거래일 수집해 누적해야 시계열(추세/z-score) 확보 가능. 현재는 1일차 스냅샷.
  - 헤드라인이 "..."로 잘려 키워드 누락 가능 — recall 제한적.
  - `item/main.naver`는 UTF-8 인코딩 — 본 프로젝트의 다른 Naver Finance 수집 스크립트 대부분이 EUC-KR을 가정하므로 재사용 시 주의 필요(코드 주석에 명시).

## 2026-06-27 18:00 - Hermes
- Task: [테스트] CHANGELOG 감시봇 동작 확인
- Verification: changelog_watcher.py → Discord 전송 테스트
## 2026-06-29 19:40 - Hermes
- Task: 매크로 팩터 패널 업데이트 불가 원인 확인 및 전용 자동화 구성.
- Root cause: `QuantMacroFactorsDaily` 작업 부재, `build_macro_spread_factors.py`가 raw CSV를 내보내지 않아 웹 payload로 직접 노출되지 않음, `QuantAllFactorsDaily`는 06/29 `build_sector_relative_value_factors.py` 실패로 전체 갱신 경로가 불안정.
- Changes: `run_macro_factor_panel_update.bat` 추가, `build_macro_spread_factors.py` raw CSV export 추가, `export_web_data.py` `macro_factors` payload 추가, `web/quant_ui.js` 매크로 팩터 최신값 표시 추가, `QuantMacroFactorPanelDaily` 매일 18:05 등록.
- Verification: 수동 배치 exit 0, Start-ScheduledTask LastTaskResult=0.
## 2026-06-29 20:38 - Hermes
- Task: 매크로 팩터 패널 내 원천 지표 최신화/자동화.
- Root cause: `QuantMacroFactorPanelDaily`는 macro factor payload 위주였고, 웹에서 직접 쓰는 원천 지표(DXY/VIX/WTI/Gold/Copper/TNX/글로벌 지수 등)는 `01_macro.py`/global indices/load/export 경로가 매일 묶여 있지 않아 일부가 2026-06-26에 머물렀음.
- Changes: `run_macro_indicators_update.bat` 추가, `QuantMacroIndicatorsDaily_0805` 매일 08:05 등록.
- Caveat: `collect_grains_once.py`는 300초 timeout으로 일일 자동화에서 제외하고 별도 수동 점검 필요.
- Verification: 01_macro/global/nonferrous/load/quant/export 실행, scheduler Start-ScheduledTask LastTaskResult=0.
## 2026-06-29 20:55 - Hermes
- Task: 곡물 지표 collector timeout 원인 조사 및 자동화 복귀.
- Root cause: `collect_grains_once.py` 끝부분 FRED 보완 3개 시리즈(`PBARLUSDM`, `WPU01220101`, `WPU01220501`)가 네트워크 read timeout을 반복했고, 기존 설정이 120초 timeout × 3회 retry라 최악 18분 이상 대기해 300초 검증/일일 배치 한도를 넘김.
- Secondary issue: FRED/Stooq 결과가 비어 있으면 CSV가 header 없는 5-byte 파일로 남아 `load_to_db.py`에서 empty/headerless skip을 유발.
- Changes: FRED 보완 timeout을 15초 × 1회로 제한, 빈 FRED/Stooq 결과도 schema 있는 CSV로 저장, `run_macro_indicators_update.bat`에 grains 단계 포함, `package.json` py_compile 대상에 collector 추가.
- Verification: focused collector run exit 0, Task Scheduler `QuantMacroIndicatorsDaily_0805` Start-ScheduledTask LastTaskResult=0.
