# 데이터 수집 및 관리 지침 (Data Collection Guidelines)

본 문서는 `Anal_reports` 프로젝트의 퀀트, 매크로, 종목 분석용 데이터 수집 및 파이프라인 관리를 위한 핵심 원칙과 가이드라인을 정의합니다.
실제 구현된 스크립트 구조와 1:1로 대응하며, 신규 데이터 소스 추가 시 이 문서를 함께 업데이트해야 합니다.

---

## 1. 디렉토리 구조 (Directory Structure)

데이터의 생애 주기(수집 → 가공 → 서비스)에 따라 저장 위치를 엄격히 분리합니다.

```
Anal_reports/
├── data/
│   ├── raw/                        # 가공 전 원본 데이터 (.csv / .json)
│   │   ├── macro/
│   │   │   ├── indices/            # KOSPI, NASDAQ 등 주요 지수
│   │   │   ├── exchange_rates/     # USD/KRW, JPY/KRW, EUR/KRW
│   │   │   ├── commodities/        # WTI, Gold, Silver, Copper 등
│   │   │   └── macro_indices/      # TNX, DXY (Yahoo Finance)
│   │   ├── sentiment/
│   │   │   ├── fear_greed.json     # CNN Fear & Greed Index
│   │   │   ├── vix.csv / vkospi.csv
│   │   │   └── adrs/               # KOSPI ADR 산출 결과
│   │   ├── money_flow/
│   │   │   ├── net_purchase_foreigner_kospi.csv
│   │   │   ├── net_purchase_institutional_kospi.csv
│   │   │   ├── net_purchase_pension_kospi.csv
│   │   │   ├── market_trading_value_kospi_20y.csv
│   │   │   ├── market_trading_value_kosdaq_20y.csv
│   │   │   ├── futures_trend.csv
│   │   │   ├── market_funds_trend.csv
│   │   │   └── bitcoin.csv
│   │   └── valuation/
│   │       ├── earnings_consensus.csv
│   │       ├── dart_all_filings.csv
│   │       ├── dart_buybacks.csv
│   │       ├── dart_dividends.csv
│   │       └── dart_insiders.csv
│   │   └── stock_detail/
│   │       ├── {ticker}/ohlcv.csv          # 종목별 3년 주가·거래량
│   │       ├── {ticker}/fundamental.csv    # PER, PBR, EPS, BPS, DPS, DIV
│   │       ├── {ticker}/market_cap.csv     # 시가총액·상장주식수
│   │       ├── {ticker}/shorting.csv       # 공매도 잔고·잔고율
│   │       ├── foreign_exhaustion_kospi.csv
│   │       ├── foreign_exhaustion_kosdaq.csv
│   │       └── sector_map.csv              # KRX 업종 분류 스냅샷
│   ├── database/
│   │   └── quant_data.sqlite       # 정제된 데이터를 적재하는 SQLite DB
│   ├── config/
│   │   ├── stocks.json             # 수집 대상 종목코드 마스터
│   │   └── fixed_events.json       # 고정 경제 일정 (FOMC, 실적발표 등)
│   ├── analyst_database.json       # 애널리스트 리포트 DB (JSON)
│   └── economic_calendar.json      # 경제 캘린더 데이터
├── scripts/
│   ├── utils.py                    # 공통 경로·로깅·JSON I/O 유틸
│   ├── pipeline.py                 # ETL 전체 파이프라인 실행 진입점
│   ├── 01_collect/                 # Step 1: 수집 (Collect)
│   │   ├── 01_macro.py
│   │   ├── 02_sentiment.py
│   │   ├── 03_money_flow.py
│   │   ├── 04_valuation.py
│   │   ├── 05_breadth.py
│   │   ├── 06_stock_detail.py
│   │   ├── calendar_fetcher.py
│   │   ├── macro_fetcher.py
│   │   └── report_crawler.py
│   ├── 02_store/                   # Step 2: 정제·적재 (Store)
│   │   ├── sanitize.py
│   │   └── load_to_db.py
│   ├── 03_analyze/                 # Step 3: 분석·가공 (Analyze)
│   │   └── export_web_data.py
│   └── 04_export/                  # Step 4: 배포·출력 (Export)
│       └── exporter.py
└── web/
    ├── analyst_data.js             # 프론트엔드용 최종 JS 데이터
    └── quant_data.js               # (예정) 퀀트 지표 JS 데이터
```

---

## 2. ETL 파이프라인 흐름 (Pipeline Flow)

`scripts/pipeline.py`가 아래 순서로 단계별 스크립트를 순차 실행합니다. 각 단계에서 오류 발생 시 파이프라인이 즉시 중단됩니다.

```
[Step 1: Collect]
  report_crawler.py      → 네이버 금융 애널리스트 리포트 크롤링
  01_macro.py            → 주요 지수 / 환율 / 원자재 / FRED 데이터 수집
  02_sentiment.py        → Fear&Greed / VIX / VKOSPI / ADR 수집
  03_money_flow.py       → 외국인·기관·연기금 순매수 / 자금 흐름 수집
  04_valuation.py        → DART 공시 (자사주·배당·내부자거래) 수집
  calendar_fetcher.py    → ForexFactory 경제 캘린더 수집
  macro_fetcher.py       → FRED 추가 매크로 지표 수집
  05_breadth.py          → 미국/한국 TRIN·ADL 시장 폭 지표 수집
  06_stock_detail.py     → KOSPI200+코스닥150 종목별 상세 데이터 수집

[Step 2: Store]
  sanitize.py            → 결측치·타입 정제 (NaN, 콤마, % 제거)
  load_to_db.py          → quant_data.sqlite에 Upsert

[Step 3: Analyze]
  export_web_data.py     → DB → JS 포맷 변환 후 web/ 에 배포

[Step 4: Export]
  exporter.py            → 마크다운 리포트(MD) 및 CSV 생성 → reports/
```

---

## 3. 데이터 소스별 수집 명세 (Data Source Catalog)

### 3-1. 매크로 (01_macro.py)

| 분류 | 티커/ID | 소스 | 저장 경로 |
|------|---------|------|-----------|
| 주요 지수 | KS11, KQ11, DJI, IXIC, US500, N225, FTSE, SSEC | FinanceDataReader | `raw/macro/indices/` |
| 환율 | USD/KRW, JPY/KRW, EUR/KRW | FinanceDataReader | `raw/macro/exchange_rates/` |
| 원자재 | CL=F(WTI), GC=F(Gold), SI=F(Silver), HG=F(Copper), ZC=F(Corn), KE=F(Wheat), ZS=F(Soybean) | yfinance | `raw/macro/commodities/` |
| 채권·달러 | ^TNX(미국채 10Y), DX-Y.NYB(DXY) | yfinance | `raw/macro/macro_indices/` |
| FRED | DGS10, DGS2, WALCL, M2SL, BAMLH0A0HYM2, CPIAUCSL, UNRATE, XTEXVA01KRM667S(한국수출) | FRED API | `raw/macro/macro_indices/` |
| 퀀트 매크로 지표 | VIX, MOVE, DXY, 미국 10Y/2Y, HY OAS, CPI, 실업률, M2, Fed 총자산, 한국 수출 및 계산 팩터 | Yahoo Finance + 기존 SQLite/FRED 원천 테이블 | `raw/macro/quant_macro_indicators/` |
| 곡물 보완 | Barley, Sorghum | USDA ERS Feed Grains Yearbook All Years / FRED graph CSV | `raw/macro/grains/` |
| 주요 국가 지수 | 미국·한국·일본·중국·홍콩·대만·인도·동남아·유럽·캐나다·브라질·호주 등 28개 지수 | Yahoo Finance (`yfinance`) | `raw/macro/global_indices/` |

- 주요 국가 지수는 `macro_global_indices_daily` 통합 테이블과 `macro_global_indices_{slug}_daily` 개별 테이블로 저장
- 퀀트 매크로 지표는 `collect_quant_macro_indicators_once.py`가 수집·계산하며 아래 테이블로 저장
  - `macro_quant_market_indicators_daily`: Yahoo 기반 VIX, MOVE, DXY 일별 OHLCV
  - `macro_quant_indicators_long`: 기존 SQLite/FRED 원천 테이블을 정규화한 장기 지표(long format)
  - `macro_quant_factors_daily`: 10Y-2Y, VIX/MOVE/DXY z-score, S&P500 60일 수익률, risk-off composite 등
  - `macro_quant_factors_monthly`: CPI/M2/Fed assets/한국 수출 YoY, 실업률 12개월 변화 등
  - `macro_quant_metadata`: 시리즈 상태, 출처, 기간, 실패 사유
- FRED graph CSV가 네트워크 타임아웃이면 신규 FRED 후보(NFCI, ANFCI, T10Y3M, DFII10, T10YIE, OECD CLI 등)는 `macro_quant_metadata.status='failed'`로 기록하고 기존 원천 및 Yahoo 기반 지표만 적재
- 한국 지수 레벨은 사용자 확인 기준으로 현재 DB 값을 정본으로 사용하며, `korea_kospi_ret_60d_pct`, `korea_kosdaq_ret_60d_pct`를 퀀트 팩터에 포함
- Barley/Sorghum은 World Bank Pink Sheet 원자료가 2020-08에서 멈출 수 있으므로 임의 보간하지 않음
- USDA ERS 보완 데이터는 미국 기준 가격이며 World Bank 글로벌 USD/mt 데이터와 단위·지역 의미가 달라 별도 테이블(`macro_grains_usda_ers_*`, `macro_grains_fred_*`)로 저장
- USDA ERS 주요 시트: `FGYearbookTable09`, `FGYearbookTable10`, `FGYearbookTable13`, `FGYearbookTable14`

- 수집 시작일: `2010-01-01` (전체 히스토리 기준)
- FRED 키: 환경변수 `FRED_API_KEY` 필수

### 3-2. 심리 지표 (02_sentiment.py)

| 지표 | 소스 | 저장 파일 |
|------|------|-----------|
| CNN Fear & Greed | `fear_and_greed` 패키지 | `sentiment/fear_greed.json` |
| VIX / TRIN / MOVE / SKEW / SOX | yfinance | `sentiment/{name}.csv` |
| VKOSPI | FinanceDataReader | `sentiment/vkospi.csv` |
| KOSPI ADR | pykrx (최근 20 거래일) | `sentiment/adrs/` |
| NAVER DataLab 테마 관심도 | NAVER DataLab Search API | `sentiment/naver_datalab/naver_datalab_theme_interest_month.csv` |

- ADR 해석 기준: `≥ 120` → Overbought / `≤ 75` → Oversold / 그 외 → Neutral
- NAVER DataLab `ratio`는 절대 검색량이 아니라 조회 기간/그룹 기준 상대 지수입니다.

### 3-3. 자금 흐름 (03_money_flow.py)

| 분류 | 대상 | 소스 | 저장 파일 |
|------|------|------|-----------|
| 당일 순매수 | 외국인·기관합계·연기금 (KOSPI) | pykrx | `net_purchase_{type}_kospi.csv` |
| 20년 매매동향 | KOSPI / KOSDAQ | pykrx | `market_trading_value_{market}_20y.csv` |
| 선물 동향 | - | - | `futures_trend.csv` |
| 고객예탁금 | - | - | `market_funds_trend.csv` |
| 비트코인 | BTC-USD | yfinance | `bitcoin.csv` |

- pykrx 호출은 영업일 기준 최신 거래일(`get_latest_business_day()`)로 자동 조정

### 3-4. 밸류에이션·공시 (04_valuation.py)

| 분류 | 소스 | 저장 파일 |
|------|------|-----------|
| 당일 전체 공시 | DART API (`OpenDartReader`) | `dart_all_filings.csv` |
| 자사주 취득·소각 | DART (report_nm 필터링) | `dart_buybacks.csv` |
| 배당 공시 | DART (report_nm 필터링) | `dart_dividends.csv` |
| 내부자 거래 | DART (report_nm 필터링) | `dart_insiders.csv` |
| 어닝 컨센서스 | - | `earnings_consensus.csv` |

- DART 키: 프로젝트 루트 `.env` 또는 환경변수 `DART_API_KEY` 사용. 미설정 시 공시 수집 스킵 후 경고 로그 기록
- `04_valuation.py`는 `.env`를 자동 로드하며 DART 당일 공시를 `dart_all_filings.csv`, 자사주/배당/지분변동 필터 CSV로 저장

### 3-4-1. 종목별 상세 데이터 (06_stock_detail.py)

| 분류 | 대상 | 소스 | 저장 파일 |
|------|------|------|-----------|
| 주가·거래량 | KOSPI200 + 코스닥150 | pykrx | `stock_detail/{ticker}/ohlcv.csv` |
| 밸류에이션 | 동일 | pykrx | `stock_detail/{ticker}/fundamental.csv` |
| 시가총액 | 동일 | pykrx | `stock_detail/{ticker}/market_cap.csv` |
| 공매도 잔고 | 동일 | pykrx | `stock_detail/{ticker}/shorting.csv` |
| 외국인 한도소진율 | KOSPI / KOSDAQ 전체 | pykrx | `stock_detail/foreign_exhaustion_{market}.csv` |
| 업종 분류 | KOSPI / KOSDAQ 전체 | pykrx | `stock_detail/sector_map.csv` |

- 기본 수집 기간: 최근 3년
- 유니버스: KOSPI200 + 코스닥150. 지수 구성종목 API가 실패하면 각 시장 시가총액 상위 종목으로 폴백
- 실행 시간: 약 8~15분 예상. 장중 반복 실행보다는 야간 Batch 또는 수동 정밀 업데이트에 적합
- 웹 배포: `export_web_data.py`가 `web/quant_data.js`의 `stock_detail.tickers` 및 `stock_detail.snapshots`에 포함
- DB 적재: `load_to_db.py`가 중첩 경로를 반영해 `stock_detail_{ticker}_{dataset}` 형태의 테이블명으로 적재

### 3-5. 애널리스트 리포트 (report_crawler.py)

- 대상: 네이버 금융 리서치 센터
- 중복 방지: 리포트 고유 ID 기반 중복 체크
- 저장: `data/analyst_database.json` (JSON 누적 DB)

### 3-6. 경제 캘린더 (calendar_fetcher.py)

- 소스: ForexFactory + `data/config/fixed_events.json` (고정 일정 병합)
- 저장: `data/economic_calendar.json`
- 필터: High Impact 이벤트 우선 표시

---

## 4. 수집 주기 및 스케줄링 (Frequency & Scheduling)

| 구분 | 대상 | 주기 | 실행 스크립트 |
|------|------|------|--------------|
| 야간 Batch | 전체 파이프라인 | 매일 장 마감 후 (20:00~24:00) | `pipeline.py` |
| 장중 실시간 | 주가 지수, 프로그램 매매, 원자재 | 10~30분 단위 (09:00~15:30) | (별도 intraday 스크립트 예정) |

> Windows 스케줄러 등록: `register_scheduler.bat` 참고
> 전체 파이프라인 수동 실행: `run_pipeline.bat`

---

## 5. 크롤링 및 API 통신 원칙 (Crawling & API Rules)

- **Rate Limiting**: `time.sleep()` 또는 커넥션 풀 조절로 과도한 요청 방지. pykrx 연속 호출 간 최소 `0.5s` 딜레이 적용
- **세션 재사용**: `requests.Session()` + `User-Agent` 헤더 명시 (네이버 금융 크롤링 시)
- **Retry 정책**: 네트워크 오류·타임아웃 시 최소 3회 지수 백오프(Exponential Backoff) 재시도
- **환경변수 의존 API**: `DART_API_KEY`, `FRED_API_KEY` 미설정 시 해당 모듈만 스킵, 파이프라인 전체는 계속 진행
- **예외 로깅**: 실패한 티커·URL은 `error.log`에 기록, 건너뛰고 다음 항목 처리

---

## 6. 데이터 전처리 및 포맷팅 (Preprocessing)

`scripts/02_store/sanitize.py`에서 수행하는 표준화 규칙:

- **결측치**: `N/A`, `-`, `0` 중 맥락에 맞는 기본값으로 대치하여 프론트엔드 렌더링 오류 방지
- **숫자 포맷**: 콤마(`,`) 포함 문자열, `%` 기호 부착 데이터 → 순수 Float/Int로 변환하거나 분리 관리
- **날짜 포맷**: 모든 날짜는 `YYYY-MM-DD` (ISO 8601) 표준으로 통일. pykrx 반환값은 `pd.to_datetime().dt.strftime("%Y-%m-%d")` 적용
- **메타데이터 포함**: 거시경제 지표에는 통화 단위(원/달러), 측정 기준(%, bp), 갱신 타임스탬프를 함께 기록

---

## 7. 배포 및 백업 (Deployment & Backup)

- **무결성 검증**: `export_web_data.py` 실행 전, 필수 컬럼 누락 여부 자동 검증
- **일일 백업**: `raw/` 데이터 덮어쓰기 전 `backup_raw_YYYYMMDD_HHMMSS/` 형태로 스냅샷 보관 (예: `backup_raw_20260602_231924`)
- **웹 배포 경로**: `web/analyst_data.js`, `web/quant_data.js` (프론트엔드에서 직접 import)
- **외부 백업**: `scripts/utils.py`의 `OUTPUTS_DIR` (`../../02_outputs`) 경로로 추가 복사

---

## 8. 데이터 신뢰성 원칙 (Core Compliance)

- **임의 추측 금지**: 데이터 누락·오류 시 임의 값으로 보정하지 않음. 있는 그대로 반영하거나 `N/A` 처리
- **필수 검증 단계**: 수집 데이터는 DB 적재 또는 프론트엔드 렌더링 전 유효성(크기·타입·범위) 검증을 반드시 통과해야 함

---

## 9. 최적화 및 확장성 (Optimization & Scalability)

- **병렬 수집**: 대량 종목 크롤링 시 `ThreadPoolExecutor` 또는 `asyncio` 활용 (단, 대상 서버 Rate Limit 준수)
- **증분 업데이트**: 마지막 수집 일자 이후 신규·변동분만 Upsert하여 전체 재다운로드 방지
- **DB 확장 경로**: 현재 SQLite(`quant_data.sqlite`) → 데이터 증가 시 PostgreSQL 전환 가능하도록 DAO 계층 모듈화 설계
- **파티셔닝·인덱싱**: 시계열 데이터는 연도·월별 분할 저장, `종목코드`·`날짜` 컬럼에 인덱스 필수

---

## 10. 공통 유틸리티 (utils.py 인터페이스)

`scripts/utils.py`에 정의된 공통 함수 및 경로 상수:

```python
# 경로 상수
BASE_DIR    # scripts/
ROOT_DIR    # Anal_reports/
DATA_DIR    # data/
CONFIG_DIR  # data/config/
DB_PATH     # data/analyst_database.json
WEB_DIR     # web/
REPORTS_DIR # reports/

# 공통 함수
load_json(file_path, default=None)   # JSON 파일 로드 (파일 없으면 default 반환)
save_json(file_path, data)           # JSON 저장 (상위 디렉토리 자동 생성)
load_db()                            # analyst_database.json 전체 로드
logger                               # 표준 로거 인스턴스 (모든 스크립트 공유)
```

파이프라인 내 모든 스크립트는 직접 경로를 하드코딩하지 않고 `utils.py`의 상수를 참조해야 합니다.

---

## 11. 환경 변수 및 의존 패키지 (Environment & Dependencies)

### 필수 환경 변수

| 변수명 | 용도 | 미설정 시 동작 |
|--------|------|---------------|
| `DART_API_KEY` | DART 공시 수집 | 공시 수집 스킵, 경고 로그 |
| `FRED_API_KEY` | FRED 매크로 지표 수집 | FRED 수집 스킵, 경고 로그 |
| `ECOS_API_KEY` | 한국은행 ECOS 지표 수집 | ECOS 지표 수집 스킵 |
| `KOSIS_API_KEY` | KOSIS 국가통계 수집 | KOSIS 수집 스킵 |
| `KRX_ID`, `KRX_PW` | pykrx KRX 인증 수집 | 인증 필요 KRX 상세 수집 제한 |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | NAVER DataLab 검색 관심도 수집 | NAVER DataLab 수집 스킵 |

### 주요 의존 패키지 (`requirements.txt`)

| 패키지 | 용도 |
|--------|------|
| `FinanceDataReader` | 국내외 지수·환율 수집 |
| `yfinance` | 원자재·글로벌 매크로 수집 |
| `pykrx` | 국내 투자자 매매동향·ADR |
| `OpenDartReader` | DART 공시 수집 |
| `fear_and_greed` | CNN Fear & Greed Index |
| `pandas` | 데이터프레임 처리 |

---

## 12. 플랫 데이터 구조 원칙 (Flat Data Convention)

프론트엔드 대시보드 및 Pandas DataFrame에서 별도 변환 없이 바로 렌더링할 수 있도록:

- 중첩(Nested) JSON 구조 지양 → 1차원 Flat 테이블 형태로 가공하여 `web/` 에 배포
- 배열 형태 데이터는 `{ labels: [...], values: [...] }` 형태로 직렬화
- 숫자만 저장하지 않고 단위(원, 달러, %, bp) 및 `last_updated` 타임스탬프를 메타데이터로 포함


---

## 13. 2026-06-05 API 기반 퀀트 데이터 수집 기록

- 실행 agent: Hermes
- 사용한 확보 API/인증: `.env`의 KRX_ID/KRX_PW, DART_API_KEY, ECOS_API_KEY, KOSIS_API_KEY, FRED_API_KEY, NAVER_CLIENT_ID/NAVER_CLIENT_SECRET (값 미기록)
- DB 백업: `data/database/backups/quant_data_20260605_193436_before_api_collection.sqlite`
- 신규 raw 폴더: `data/raw/stock_market_snapshot/`
- 신규/갱신 raw 주요 파일:
  - `stock_market_snapshot/kospi_ohlcv_by_ticker_20260605.csv` — KOSPI 948종목
  - `stock_market_snapshot/kosdaq_ohlcv_by_ticker_20260605.csv` — KOSDAQ 1,822종목
  - `stock_market_snapshot/*_fundamental_by_ticker_20260605.csv` — PER/PBR/EPS 등 스냅샷
  - `stock_market_snapshot/*_market_cap_by_ticker_20260605.csv` — 시총/상장주식수 스냅샷
  - `stock_market_snapshot/*_foreign_exhaustion_by_ticker_20260605.csv` — 외국인 한도소진율
  - `stock_market_snapshot/ticker_names_20260605.csv` — KOSPI/KOSDAQ 2,770종목명
- SQLite 적재:
  - `load_to_db.py` 실행 결과 CSV 555개 적재
  - 전체 테이블 수 628개 확인
- 검증 요약:
  - DART 당일 공시: `valuation_dart_all_filings` 709 rows, 접수일 20260605
  - KOSPI/KOSDAQ 20년 수급: 각 4,933 rows, 2006-06-01~2026-06-05
  - KOSPI PBR/PER 이력: 4,042 rows, 2010-01-04~2026-06-05
  - 퀀트 daily factor: 51,801 rows, 1980-01-02~2026-06-05
  - 퀀트 monthly factor: 2,445 rows, 1981-01-31~2026-05-31
- Caveats:
  - FRED graph CSV 신규 후보 일부는 timeout으로 `macro_quant_metadata.status='failed'` 기록. 기존 DB/Yahoo 기반 팩터는 정상 적재.
  - `data/raw/macro/grains/fred_barley_sorghum_monthly.csv`는 빈 파일이라 DB 적재에서 제외됨.
  - `06_stock_detail.py` 전체 396종목 상세 수집은 공매도 잔고 API 속도/오류로 중단하고, 대신 KRX 전종목 스냅샷 수집으로 대체.

---

## 14. 2026-06-05 NAVER DataLab 테마 관심도 수집 기록

- 실행 agent: Hermes
- 사용한 인증: `.env`의 NAVER_CLIENT_ID/NAVER_CLIENT_SECRET (값 미기록)
- 수집 스크립트: `scripts/01_collect/collect_naver_datalab_once.py`
- 테스트: `tests/test_naver_datalab_collector.py`
- 검증 스크립트: `scratch/naver_datalab_verify_20260605.py`
- DB 백업: `data/database/backups/quant_data_20260605_204900_before_naver_datalab.sqlite`
- raw 파일: `data/raw/sentiment/naver_datalab/naver_datalab_theme_interest_month.csv`
- SQLite 테이블: `sentiment_naver_datalab_theme_interest_month`
- 수집 범위: 2021-01-01~2026-06-01, 월별
- 수집 그룹: 6개 (`battery_theme`, `power_grid_theme`, `renewable_theme`, `defense_theme`, `semiconductor_theme`, `market_index`)
- 검증 요약:
  - raw rows: 396
  - SQLite rows: 396
  - 기간: 2021-01-01~2026-06-01
  - 테스트: `pytest tests/ -q` → 7 passed, 1 warning
- Caveats:
  - NAVER DataLab `ratio`는 절대 검색량이 아니라 요청 기간/그룹 기준 상대 지수입니다.
  - NAVER DataLab Search API는 1회 요청당 keyword group 제한이 있어 스크립트가 5개 그룹 단위로 분할 호출합니다.

---

## 15. 2026-06-05 NAVER DataLab 전체 섹터 관심도 수집 기록

- 실행 agent: Hermes
- 사용한 인증: `.env`의 NAVER_CLIENT_ID/NAVER_CLIENT_SECRET (값 미기록)
- 수집 스크립트: `scripts/01_collect/collect_naver_datalab_once.py`
- 실행 명령: `python scripts/01_collect/collect_naver_datalab_once.py --universe sector --time-unit month --start-date 2021-01-01 --end-date 2026-06-05`
- 테스트: `pytest tests/ -q` → 10 passed, 1 warning
- DB 백업: `data/database/backups/quant_data_20260605_210215_before_naver_sector_datalab.sqlite`
- raw 파일:
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_month.csv`
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_factor_month.csv`
- SQLite 테이블:
  - `sentiment_naver_datalab_sector_interest_month_raw`
  - `sentiment_naver_datalab_sector_interest_month_factor`
- 수집 범위: 2021-01-01~2026-06-01, 월별
- 수집 섹터: 35개 (`semiconductor`, `battery`, `auto`, `shipbuilding`, `steel`, `chemical`, `refinery`, `construction`, `bank`, `securities`, `insurance`, `internet`, `game`, `media_entertainment`, `bio_pharma`, `medical_device`, `food_beverage`, `retail`, `cosmetics`, `apparel`, `telecom`, `utility_power`, `machinery`, `defense`, `airline_transport`, `shipping`, `display`, `it_parts`, `power_equipment`, `robot`, `ai_software`, `nuclear`, `renewable`, `holding_company`, `reit_realestate`)
- 검증 요약:
  - raw CSV/DB rows: 2,904 rows, 36 groups(anchor 포함), 2021-01-01~2026-06-01
  - factor CSV/DB rows: 2,310 rows, 35 sector groups, 2021-01-01~2026-06-01
  - factor 컬럼: `anchor_ratio`, `anchor_relative_ratio`, `momentum_1p`, `momentum_3p`, `zscore_12p`
- Caveats:
  - NAVER DataLab `ratio`는 절대 검색량이 아니라 요청별 상대 지수입니다.
  - 전체 섹터 비교 가능성을 높이기 위해 각 요청 chunk에 `market_anchor`(`코스피|코스닥|주식`)를 포함하고, factor 테이블에는 같은 chunk의 anchor 대비 상대강도를 저장했습니다.
  - anchor 보정은 검색량 절대값 복원이 아니라 chunk 간 비교를 위한 근사 정규화입니다.


---

## 16. 2026-06-05 NAVER DataLab 섹터 관심도 1차 가공 팩터 후보군

- 실행 agent: Hermes
- 목적: 모델링 전 단계에서 NAVER DataLab 검색 관심도 상대지수를 3개 질문별 팩터 후보군으로 분류
  1. 같은 섹터 안에서 관심도가 최근 강해졌는가? → `same_sector_recent_strength`
  2. 시장 전체 검색 관심도 대비 특정 섹터가 강한가? → `market_relative_strength`
  3. 전체 섹터 중 현재 관심도 순위가 높은가? → `cross_sector_current_rank`
- 가공 스크립트: `scripts/03_analyze/build_naver_datalab_sector_features.py`
- 테스트: `tests/test_naver_datalab_sector_features.py`
- 실행 명령: `python scripts/03_analyze/build_naver_datalab_sector_features.py`
- 테스트 결과: `pytest tests/ -q` → 13 passed, 1 warning
- DB 백업: `data/database/backups/quant_data_20260605_211500_before_naver_sector_features.sqlite`
- 입력 테이블/파일:
  - `sentiment_naver_datalab_sector_interest_month_factor`
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_factor_month.csv`
- 출력 raw 파일:
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_features_month.csv`
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_factor_catalog.csv`
  - `data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_classified_month.csv`
- SQLite 테이블:
  - `sentiment_naver_datalab_sector_interest_month_features` — 2,310 rows, 35 sectors, 2021-01-01~2026-06-01
  - `sentiment_naver_datalab_sector_interest_factor_catalog` — 9 factor candidates, 3 factor families
  - `sentiment_naver_datalab_sector_interest_month_classified` — 6,930 rows, 35 sectors × 66 months × 3 families
- 주요 feature 컬럼:
  - 품질: `low_anchor_flag`, `saturation_flag`, `anchor_saturation_flag`, `zero_ratio_flag`, `missing_flag`, `data_quality_score`
  - 섹터 내부 강화: `ratio_momentum_1m`, `ratio_momentum_3m`, `ratio_momentum_6m`, `ratio_zscore_12m`, `ratio_zscore_24m`, `recent_strength_score`, `recent_strength_bucket`
  - 시장 대비 강도: `anchor_relative_ratio_winsorized`, `anchor_relative_momentum_1m`, `anchor_relative_momentum_3m`, `anchor_relative_momentum_6m`, `anchor_relative_zscore_12m`, `anchor_relative_zscore_24m`, `market_relative_score`, `market_relative_bucket`
  - 섹터 내 순위: `relative_rank`, `relative_rank_pct`, `relative_zscore_cross_sectional`, `top_20pct_flag`, `bottom_20pct_flag`, `cross_sector_rank_score`, `cross_sector_rank_bucket`
- 최신월(2026-06-01) classified bucket 요약:
  - `cross_sector_current_rank`: bottom 7, middle 20, top 8
  - `market_relative_strength`: weak 34, insufficient_history 1
  - `same_sector_recent_strength`: cooling 1, neutral 7, recovering 10, weakening 16, insufficient_history 1
- Caveats:
  - 본 테이블은 모델 예측 결과가 아니라 모델링 전 1차 가공/팩터 후보군입니다.
  - NAVER DataLab ratio는 절대 검색량이 아니며, anchor 보정값도 절대 검색량 복원이 아닙니다.
  - `market_relative_strength`와 `cross_sector_current_rank`는 `market_anchor` 보정의 한계를 갖습니다.
  - 월별 66개 포인트 기반이므로 12m/24m rolling 지표는 초기 구간에서 `insufficient_history`가 발생합니다.


---

## 17. 2026-06-05 시장/매크로 regime 기반 관심도 신호 조정 팩터

- 실행 agent: Hermes
- 목적: NAVER DataLab 섹터 관심도 신호를 시장/매크로 regime으로 할인/가중하여 모델링 전 후보 팩터를 생성
- 백업: `data/database/backups/quant_data_20260605_215512_before_regime_adjusted_signals.sqlite`
- 가공 스크립트: `scripts/03_analyze/build_market_regime_adjusted_signals.py`
- 테스트: `tests/test_market_regime_adjusted_signals.py`
- 실행 명령: `python scripts/03_analyze/build_market_regime_adjusted_signals.py`
- 테스트 결과: `pytest tests/ -q` → 16 passed, 1 warning
- 입력 테이블:
  - `sentiment_naver_datalab_sector_interest_month_features`
  - `macro_quant_factors_daily`
  - `macro_quant_factors_monthly`
- 출력 CSV:
  - `data/raw/factors/market_macro_regime_month.csv`
  - `data/raw/factors/regime_adjusted_sector_interest_month.csv`
  - `data/raw/factors/regime_adjusted_factor_catalog.csv`
- SQLite 테이블:
  - `factor_market_macro_regime_month` — 558 rows, 1980-01-01~2026-06-01, 4 regimes
  - `factor_regime_adjusted_sector_interest_month` — 2,310 rows, 35 sectors, 2021-01-01~2026-06-01, 5 buckets
  - `factor_regime_adjusted_catalog` — 9 rows, 2 factor families
- market regime 분포:
  - neutral 388개월
  - risk_on 87개월
  - risk_off 47개월
  - dollar_pressure 36개월
- 최신월(2026-06-01) regime: `neutral`
- 최신월 상위 조정 관심도 후보:
  - `auto` 0.9657 (`very_strong`)
  - `internet` 0.9200 (`very_strong`)
  - `semiconductor` 0.8114 (`strong`)
  - `steel` 0.7943 (`strong`)
  - `battery` 0.7914 (`strong`)
  - `retail` 0.7457 (`strong`)
- Caveats:
  - 본 테이블은 예측모델 결과가 아니라 모델링 전 regime-aware factor 후보군입니다.
  - `regime_adjusted_interest_score`는 검색 관심도 점수를 risk-off/달러압박에서는 할인하고, risk-on/growth/export 환경에서는 일부 가중한 규칙 기반 점수입니다.
  - 최신월 `neutral` regime에서는 growth/export/risk 할인 가중이 적용되지 않았으므로 관심도 원신호의 상대순위 영향이 큽니다.

---

## 18. 2026-06-10 미국/한국 무역 통계 수집·DB 적재

- 실행 agent: Hermes
- 목적: 미국 글로벌 무역, 미국-한국 양자 교역, 한국 수출입 장기 시계열을 FRED 기반으로 보강
- 수집 스크립트: `scripts/01_collect/collect_us_korea_trade_once.py`
- 실행 명령: `python scripts/01_collect/collect_us_korea_trade_once.py`
- DB 백업:
  - `data/database/quant_data.sqlite.backup_trade_stats_20260610_214100` — 성공 적재 직전 백업
  - `data/database/quant_data.sqlite.backup_trade_stats_20260610_212826` — graph CSV timeout으로 중단된 1차 시도 직전 백업
- raw 파일:
  - 개별 FRED series CSV 8개: `fred_BOPTEXP.csv`, `fred_BOPTIMP.csv`, `fred_EXPGS.csv`, `fred_IMPGS.csv`, `fred_EXPKR.csv`, `fred_IMPKR.csv`, `fred_XTEXVA01KRM667S.csv`, `fred_XTIMVA01KRM667S.csv`
  - 통합/파생 CSV: `us_korea_trade_fred_long.csv`, `us_korea_trade_fred_monthly.csv`, `us_trade_fred_quarterly_nipa.csv`, `us_korea_trade_fred_metadata.csv`
  - 요약 JSON: `us_korea_trade_collection_summary.json`
- SQLite 테이블:
  - `macro_trade_us_korea_fred` — 4,112 rows, 1947-01-01~2026-04-01
  - `macro_trade_us_korea_monthly` — 3,478 rows, 1957-01-01~2026-04-01
  - `macro_trade_us_quarterly_nipa` — 634 rows, 1947-01-01~2026-01-01
  - `macro_trade_us_korea_metadata` — 8 rows, all success
  - 개별 series 테이블: `macro_trade_boptexp`, `macro_trade_boptimp`, `macro_trade_expgs`, `macro_trade_impgs`, `macro_trade_expkr`, `macro_trade_impkr`, `macro_trade_xtexva01krm667s`, `macro_trade_xtimva01krm667s`
- 시리즈 범위:
  - `BOPTEXP`/`BOPTIMP`: 1992-01-01~2026-04-01, 각 412 rows
  - `EXPGS`/`IMPGS`: 1947-01-01~2026-01-01, 각 317 rows
  - `EXPKR`/`IMPKR`: 1985-01-01~2026-04-01, 각 496 rows
  - `XTEXVA01KRM667S`/`XTIMVA01KRM667S`: 1957-01-01~2026-03-01, 각 831 rows
- Caveats:
  - FRED graph CSV endpoint는 현재 환경에서 read timeout이 발생해, 프로젝트 `.env`의 `FRED_API_KEY`를 사용하는 FRED observations API fallback으로 성공 수집했습니다. 키 값은 문서/로그에 기록하지 않았습니다.
  - 월간 BoP/양자 통계와 분기 NIPA 통계는 단위·계절조정·빈도가 다르므로 metadata를 기준으로 분리 사용해야 합니다.

---

## 19. 2026-06-16 섹터 상대 PER/PBR·ROE 조정 팩터 구축

- 실행 agent: Hermes
- 목적: 사용자 요청 팩터 1·2·3·5·6 구현 후 2026-06-17에 부채비율·FCF 품질, ㊳ Balance Sheet Quality, ㊴ Cash Flow Quality, ㊵ Earnings Stability를 추가 반영
  1. `sector_relative_per` — 종목 PER / 동일 섹터 PER 중위값
  2. `sector_relative_pbr` — 종목 PBR / 동일 섹터 PBR 중위값
  3. `pbr_to_roe`, `pbr_roe_residual_sector`, `pbr_roe_adjusted_score` — ROE 대비 PBR 조정
  5. `value_quality_score` — 저PER·저PBR·ROE수준·ROE대비PBR·저부채·FCF·BS/CF/이익안정성 합성
  6. `sector_value_zscore` — 섹터 PER/PBR 중위값의 자기 과거 대비 위치
  debt/FCF. `debt_ratio`, `fcf_to_assets`, `financial_quality_score` — DART 최신 연간 재무제표 기반 재무건전성·현금창출 품질
  ㊳ `balance_sheet_quality_score` — debt_to_equity, net_debt_to_ebitda, interest_coverage, current_ratio, equity_impairment_flag 합성
  ㊴ `cashflow_quality_score` — operating_cashflow_positive, fcf_margin, fcf_yield, accrual_ratio, cash_conversion 합성
  ㊵ `earnings_stability_score` — 매출 YoY 안정성, 영업이익률 변동성, 적자 횟수, ROE 변동성 합성
- 원천: 기존 `factor_valuation_per_pbr_month`, `factor_roe_trend_month` + `data/raw/valuation/dart_finstate/finstate_all.csv`(CAPEX 계정 추가 수집)
- DB 백업:
  - `data/database/backups/quant_data_20260616_1940_before_sector_relative_value.sqlite`
  - `data/database/backups/quant_data_20260617_192517_before_debt_fcf.sqlite`
- 가공 스크립트: `scripts/03_analyze/build_sector_relative_value_factors.py`
- 수집 스크립트 보강: `scripts/01_collect/collect_dart_finstate_once.py` — `capex`, 현금성자산, 매출, 영업이익, 이자비용, 순이익 계정 및 괄호 음수 파싱 추가
- 테스트: `tests/test_sector_relative_value_factors.py`
- 실행 명령:
  - `python scripts/01_collect/collect_dart_finstate_once.py`
  - `python scripts/03_analyze/build_sector_relative_value_factors.py`
- 출력 CSV:
  - `data/raw/factors/sector_relative_value_month.csv`
  - `data/raw/factors/sector_relative_value_catalog.csv`
- SQLite 테이블:
  - `factor_sector_relative_value_month` — 14,136 rows, 395 tickers, 2023-06-01~2026-06-01
  - `factor_sector_relative_value_catalog` — 27 rows
- 검증 요약:
  - non-null `sector_relative_per`: 10,202
  - non-null `sector_relative_pbr`: 13,407
  - non-null `pbr_roe_adjusted_score`: 10,092
  - non-null `debt_ratio`: 12,730
  - non-null `fcf_to_assets`: 11,976
  - non-null `financial_quality_score`: 13,539
  - non-null `balance_sheet_quality_score`: 14,052
  - non-null `cashflow_quality_score`: 12,910
  - non-null `earnings_stability_score`: 14,015
  - non-null `value_quality_score`: 14,124
  - non-null `sector_value_zscore`: 9,586
  - DART finstate raw: 2026-06-19 보강 후 71,906 rows / 1,856 tickers / `capex` 4,942 rows
  - DB 월간 팩터 패널은 기존 가치/ROE 월간 패널 기준이라 14,136 rows / 395 tickers 유지
  - 웹 `stock_attractiveness`는 DART raw fallback을 추가 적용해 전체 2,770개 중 `roe`/`roe_score` 1,803개, `fcf_to_assets` 1,544개, `balance_sheet_quality_score` 1,853개, `cashflow_quality_score` 1,758개, `earnings_stability_score` 1,850개 노출
  - 기본 B 유니버스 350개 중 `roe`/`roe_score` 331개, `fcf_to_assets` 278개, `balance_sheet_quality_score` 332개, `cashflow_quality_score` 299개, `earnings_stability_score` 331개 노출
  - `python -m py_compile scripts/01_collect/collect_dart_finstate_once.py scripts/03_analyze/build_sector_relative_value_factors.py scripts/03_analyze/export_web_data.py` → 통과
  - `pytest tests/test_sector_relative_value_factors.py tests/test_valuation_per_pbr_factors.py tests/test_roe_trend_factors.py tests/test_piotroski_factors.py -q` → 37 passed
  - Puppeteer 로컬 검증 → stock_attractiveness 2,770 rows, B 350, ROE 1,803/B ROE 331, FCF 1,544 / BS 1,853 / CF 1,758 / 이익안정 1,850, fallback 1,467, pageErrors 0
- Caveats:
  - 섹터 내 표본 5종목 미만이면 섹터 상대/잔차 지표를 NaN 처리합니다.
  - ROE≤0 구간은 PBR/ROE 조정 지표를 NaN 처리합니다.
  - DART 수집은 일부 종목에서 API 무응답/hang이 발생해 1차 보강은 1,856종목까지 반영했습니다. 미수집/조회불가 종목은 임의 보간하지 않습니다.
  - DB 월간 팩터 패널은 가치/ROE 월간 패널 매칭 가능한 395종목 기준이며, 웹 결측 보강은 DART raw fallback으로 별도 적용됩니다.
