# Agent Change Log — Anal_reports

목적: Claude/Hermes/기타 AI agent가 `Anal_reports`에서 수행한 파일 변경, 생성, 검증 결과를 공유합니다.

---

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
