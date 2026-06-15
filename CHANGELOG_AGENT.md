# Agent Change Log — Anal_reports

목적: Claude/Hermes/기타 AI agent가 `Anal_reports`에서 수행한 파일 변경, 생성, 검증 결과를 공유합니다.

---

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
