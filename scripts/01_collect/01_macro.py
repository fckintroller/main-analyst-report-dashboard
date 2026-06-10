import io
import logging
import os

import FinanceDataReader as fdr
import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logger = logging.getLogger(__name__)
BASE_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "macro")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


INDICES = {
    "KOSPI": "KS11",
    "KOSDAQ": "KQ11",
    "DowJones": "DJI",
    "NASDAQ": "IXIC",
    "S&P500": "US500",
    "Nikkei225": "N225",
    "FTSE100": "FTSE",
    "Shanghai": "SSEC",
}

EXCHANGE_RATES = {
    "USD_KRW": "USD/KRW",
    "JPY_KRW": "JPY/KRW",
    "EUR_KRW": "EUR/KRW",
    "USD_JPY": "USD/JPY",    # 엔/달러 — 엔 캐리 트레이드 청산 모니터링
    "USD_CNY": "USD/CNY",    # 위안/달러 — 중국 리스크 프리미엄 측정
}

COMMODITIES = {
    "WTI": "CL=F",
    "Brent": "BZ=F",         # 브렌트유 — WTI/Brent 스프레드, 글로벌 수급 차이
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Corn": "ZC=F",
    "Wheat": "KE=F",
    "Soybean": "ZS=F",
}

MACRO_YF = {
    "TNX": "^TNX",
    "DXY": "DX-Y.NYB",
    "VIX": "^VIX",           # 미국 공포지수
    "VKOSPI": "^VKOSPI",     # 한국 공포지수 (미지원 시 자동 skip)
    "EEM": "EEM",            # iShares MSCI EM — 신흥국 대표 ETF (KOSPI 상대 포지셔닝)
    "SOXX": "SOXX",          # iShares 반도체 ETF — 글로벌 반도체 사이클 측정
}

FRED_TICKERS = {
    # 금리
    "DGS2": "DGS2",                # 미국 2년물
    "DGS10": "DGS10",              # 미국 10년물
    "DGS30": "DGS30",              # 미국 30년물
    "DFII10": "DFII10",            # TIPS 10Y 실질금리 (명목금리 - 기대인플레)
    "T5YIFR": "T5YIFR",            # 5Y5Y 기대인플레 (Fed 정책 선행)
    # 유동성
    "WALCL": "WALCL",              # Fed 자산총계
    "RRPONTSYD": "RRPONTSYD",      # 역레포 잔액 (단기 달러 유동성)
    "WTREGEN": "WTREGEN",          # 재무부 일반계좌 TGA (시중 유동성 흡수/방출)
    "M2SL": "M2SL",                # 미국 M2
    # 신용 / 스프레드
    "BAMLH0A0HYM2": "BAMLH0A0HYM2",  # HY 크레딧 스프레드
    "BAMLC0A0CM": "BAMLC0A0CM",       # IG 크레딧 스프레드
    "STLFSI4": "STLFSI4",             # 세인트루이스 금융스트레스지수 (복합 18개 변수)
    "NFCI": "NFCI",                   # 시카고 Fed 금융환경지수 (복합 105개 변수)
    # 경기 선행
    "NAPM": "NAPM",                # ISM 제조업 PMI
    "ICSA": "ICSA",                # 실업급여 신규청구 (주간, 2~3개월 선행)
    "UMCSENT": "UMCSENT",          # 미시간대 소비자심리지수
    # 투자심리
    "AAIIBULL": "AAIIBULL",        # AAII 강세 비율 (주간)
    "AAIIBEAR": "AAIIBEAR",        # AAII 약세 비율 (주간)
    # 물가 / 고용
    "CPIAUCSL": "CPIAUCSL",
    "UNRATE": "UNRATE",
    # OECD 복합선행지수 (CLI, Amplitude-Adjusted)
    "KOR_CLI": "KORLOLITONOSTSAM",   # 한국 (2~3개월 발표 시차)
    "USA_CLI": "USALOLITONOSTSAM",   # 미국
    "CHN_CLI": "CHNLOLITONOSTSAM",   # 중국 (한국 수출 최대국)
    "JPN_CLI": "JPNLOLITONOSTSAM",   # 일본
    # 한국 경기 / 물가
    "KOR_IIP":  "KORPROINDMISMEI",      # 산업생산지수 (Industrial Production)
    "KOR_CPI":  "CPALTT01KRM659N",      # 소비자물가지수 YoY
    "KOR_EXPORTS": "XTEXVA01KRM667S",   # 수출 금액지수
    # OECD CLI (FRED 미러) — 경기선행지수 (Amplitude Adjusted, 월별)
    "DEU_CLI": "DEULOLITONOSTSAM",      # 독일
    "GBR_CLI": "GBRLOLITONOSTSAM",      # 영국
    "FRA_CLI": "FRALOLITONOSTSAM",      # 프랑스
    "IND_CLI": "INDLOLITONOSTSAM",      # 인도
    "BRA_CLI": "BRALOLITONOSTSAM",      # 브라질
    # 미국 실물경기
    "US_INDPRO": "INDPRO",              # 산업생산지수
    "US_RETAIL": "RSXFS",               # 소매판매 (ex-food service)
    # 미국 신용 (Credit Impulse 계산용)
    "US_TOTLL":  "TOTLL",               # 상업은행 총 대출 (billions USD, 주간)
    "US_GDP":    "GDP",                  # 명목 GDP (billions USD, 분기)
}


def fetch_fdr_data(category_name, targets_dict, start_date="2010-01-01"):
    save_path = os.path.join(BASE_DIR, category_name)
    ensure_dir(save_path)
    logger.info("[MACRO] collecting %s data", category_name)

    for name, ticker in targets_dict.items():
        try:
            df = fdr.DataReader(ticker, start_date)
            if not df.empty:
                df.to_csv(os.path.join(save_path, f"{name}.csv"))
                logger.info(" - %s (%s) collected: %s rows", name, ticker, len(df))
        except Exception as e:
            logger.error(" - %s (%s) failed: %s", name, ticker, e)


def fetch_yf_macro():
    save_path = os.path.join(BASE_DIR, "macro_indices")
    ensure_dir(save_path)
    logger.info("[MACRO] collecting Yahoo Finance macro data")

    for name, ticker in MACRO_YF.items():
        try:
            df = yf.download(ticker, period="10y", progress=False)
            if not df.empty:
                df.to_csv(os.path.join(save_path, f"{name}.csv"))
                logger.info(" - %s (%s) collected: %s rows", name, ticker, len(df))
        except Exception as e:
            logger.error(" - %s (%s) failed: %s", name, ticker, e)


def fetch_fred_yields():
    save_path = os.path.join(BASE_DIR, "macro_indices")
    ensure_dir(save_path)
    logger.info("[MACRO] collecting FRED macro data")

    for name, ticker in FRED_TICKERS.items():
        try:
            df = fdr.DataReader(f"FRED:{ticker}")
            if not df.empty:
                df.to_csv(os.path.join(save_path, f"{name}.csv"))
                logger.info(" - %s collected: %s rows", name, len(df))
        except Exception as e:
            logger.error(" - %s failed: %s", name, e)


# ECOS KeyStatisticList 매핑
# StatisticSearch는 별도 서비스 신청 필요 → KeyStatisticList(100대 지표) 활용
# KEYSTAT_NAME 부분 매칭 → {저장 파일명}
ECOS_KEY_STAT_MAP = {
    # 금리
    "기준금리":               "KOR_BASE_RATE", # 한국은행 기준금리 %
    "콜금리(익일물)":          "KOR_CALL_RATE", # 콜금리(1일) %
    "KORIBOR(3":              "KOR_KORIBOR3M", # KORIBOR 3개월 %
    "국고채수익률(3년)":       "KOR_GOV3Y",    # %
    "국고채수익률(5년)":       "KOR_GOV5Y",    # %
    "국고채수익률(10":         "KOR_GOV10Y",   # %
    "회사채수익률(3년,AA-)":   "KOR_CORP_AA",  # %
    "CD":                     "KOR_CD91",      # CD금리(91일) %
    # 통화·유동성
    "M2(광의통화":            "KOR_M2",        # 십억원
    # 물가
    "소비자물가지수":          "KOR_CPI",       # 지수 (2020=100)
    "생산자물가지수":          "KOR_PPI",       # 지수 (2020=100)
    # 실물·고용
    "산업생산지수":            "KOR_IIP",       # 지수
    "실업률":                  "KOR_UNEMPLOYMENT", # %
    # 심리
    "소비자심리지수":          "KOR_CCSI",      # 지수 (100 기준)
    "기업심리지수":            "KOR_BSI",       # 지수 (100 기준)
    # 대외
    "수출물가지수변화":        "KOR_EXPORT_PRICE", # 지수
    "외환보유액":              "KOR_FX_RESERVES",  # 백만달러
}


def fetch_ecos_data():
    """ECOS KeyStatisticList로 한국 핵심 지표 수집 (API키 필요, StatisticSearch 불필요).
    매일 실행 시 최신값을 CSV에 누적 → 시계열 이력이 쌓임.
    """
    ecos_key = os.environ.get("ECOS_API_KEY")
    if not ecos_key:
        logger.info("[MACRO] ECOS_API_KEY 미설정 — ECOS 한국 지표 건너뜀")
        return

    url = f"https://ecos.bok.or.kr/api/KeyStatisticList/{ecos_key}/json/kr/1/100/"
    try:
        rows = requests.get(url, timeout=15).json() \
                       .get("KeyStatisticList", {}).get("row", [])
    except Exception as e:
        logger.error("[MACRO] ECOS KeyStatisticList 수집 실패: %s", e)
        return

    if not rows:
        logger.warning("[MACRO] ECOS: 반환 데이터 없음")
        return

    save_path = os.path.join(BASE_DIR, "macro_indices")
    ensure_dir(save_path)

    for partial_name, out_name in ECOS_KEY_STAT_MAP.items():
        matched = next(
            (r for r in rows if partial_name in r.get("KEYSTAT_NAME", "")), None
        )
        if not matched:
            logger.warning(" - ECOS %s: '%s' 매칭 실패", out_name, partial_name)
            continue

        val_str = matched.get("DATA_VALUE", "")
        cycle   = matched.get("CYCLE", "")
        try:
            val = float(val_str.replace(",", ""))
        except ValueError:
            continue

        # CYCLE → YYYY-MM-01 (YYYYMMDD 또는 YYYYMM 모두 처리)
        if len(cycle) >= 6:
            date_str = f"{cycle[:4]}-{cycle[4:6]}-01"
        else:
            continue

        csv_path = os.path.join(save_path, f"{out_name}.csv")

        # 기존 CSV 로드 (없으면 빈 DataFrame)
        if os.path.exists(csv_path):
            try:
                existing = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            except Exception:
                existing = pd.DataFrame(columns=["value"])
        else:
            existing = pd.DataFrame(columns=["value"])

        # 해당 날짜 데이터가 없을 때만 추가
        try:
            existing_dates = existing.index.strftime("%Y-%m-%d").tolist()
        except AttributeError:
            existing_dates = [str(d)[:10] for d in existing.index]
        if date_str not in existing_dates:
            new_row = pd.DataFrame(
                {"value": [val]},
                index=pd.DatetimeIndex([date_str], name="date")
            )
            updated = pd.concat([existing, new_row]).sort_index()
            updated.to_csv(csv_path)
            logger.info(" - ECOS %s: %s = %.4f (신규 저장)", out_name, date_str, val)
        else:
            logger.info(" - ECOS %s: %s = %.4f (기존 유지)", out_name, date_str, val)


def run():
    logger.info("=== 01. Macro collection started ===")
    ensure_dir(BASE_DIR)
    fetch_fdr_data("indices", INDICES)
    fetch_fdr_data("exchange_rates", EXCHANGE_RATES)
    fetch_fdr_data("commodities", COMMODITIES)
    fetch_yf_macro()
    fetch_fred_yields()   # KOR_CLI, USA_CLI, CHN_CLI, JPN_CLI 포함
    fetch_ecos_data()     # ECOS_API_KEY 설정 시 한국 채권/M2/CCSI 수집
    logger.info("=== 01. Macro collection finished ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
