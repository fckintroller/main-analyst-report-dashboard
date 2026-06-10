"""
06_stock_detail.py — KOSPI 200 + 코스닥 150 종목별 상세 데이터 수집

수집 데이터 (pykrx):
  1. OHLCV           — 주가·거래량 시계열 (수정주가)
  2. Fundamental     — PER, PBR, EPS, BPS, DPS, DIV (배당수익률)
  3. MarketCap       — 시가총액·상장주식수 시계열
  4. NetPurchase     — 외국인·기관·개인 순매수 시계열
  5. Shorting        — 공매도 잔고·잔고율 시계열
  6. ForeignExhaust  — 외국인 한도소진율 (당일 스냅샷)
  7. SectorMap       — KRX 업종 분류 (당일 스냅샷)

저장 경로:
  data/raw/stock_detail/{ticker}/ohlcv.csv
  data/raw/stock_detail/{ticker}/fundamental.csv
  data/raw/stock_detail/{ticker}/market_cap.csv
  data/raw/stock_detail/{ticker}/net_purchase.csv
  data/raw/stock_detail/{ticker}/shorting.csv
  data/raw/stock_detail/foreign_exhaustion.csv   (전종목 스냅샷)
  data/raw/stock_detail/sector_map.csv           (전종목 섹터)

실행 시간 참고:
  - KOSPI200+코스닥150 = 약 350 종목
  - 종목당 5개 API 호출 × 0.3s 딜레이 ≈ 약 8~15분 소요
"""

import datetime
import logging
import os
import sys
import time

import pandas as pd
import FinanceDataReader as fdr
from pykrx import stock

logger = logging.getLogger(__name__)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "stock_detail")
PYKRX_DETAIL_AVAILABLE = True

# 수집 기간 설정
LOOKBACK_YEARS = 3          # OHLCV/Fundamental/MarketCap/NetPurchase/Shorting 기간
API_DELAY      = 0.3        # 호출 간 딜레이 (초)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def today_str():
    return datetime.date.today().strftime("%Y%m%d")


def start_str():
    d = datetime.date.today() - datetime.timedelta(days=LOOKBACK_YEARS * 365)
    return d.strftime("%Y%m%d")


def save_csv(df: pd.DataFrame, path: str):
    if df is None or df.empty:
        return False
    df.fillna("", inplace=True)
    ensure_dir(os.path.dirname(path))
    df.to_csv(path, encoding="utf-8-sig")
    return True


# ─────────────────────────────────────────────
# 유니버스 구성: KOSPI 200 + 코스닥 150
# ─────────────────────────────────────────────
def build_universe(date: str) -> dict[str, str]:
    """
    Returns {ticker: name} for KOSPI200 + 코스닥150.
    Falls back to KOSPI top-200 / KOSDAQ top-150 by market cap if index
    constituent API is unavailable.
    """
    global PYKRX_DETAIL_AVAILABLE
    universe = {}
    use_pykrx = bool(os.environ.get("KRX_ID") and os.environ.get("KRX_PW"))
    if not use_pykrx:
        PYKRX_DETAIL_AVAILABLE = False
        logger.warning("KRX_ID/KRX_PW 미설정 — pykrx 상세 API를 건너뛰고 FinanceDataReader 폴백을 사용합니다.")

    # ── KOSPI 200 구성종목 (KRX 지수 코드: 1028)
    if use_pykrx:
        try:
            tickers_k200 = stock.get_index_portfolio_deposit_file("1028")
            for t in tickers_k200:
                name = stock.get_market_ticker_name(t)
                universe[t] = name
            logger.info(" - KOSPI 200: %d 종목", len(tickers_k200))
        except Exception as e:
            logger.warning(" - KOSPI 200 구성종목 조회 실패, 시총 상위 200 폴백: %s", e)
            try:
                df_cap = stock.get_market_cap_by_ticker(date, market="KOSPI")
                top200 = df_cap.nlargest(200, "시가총액")
                for t in top200.index:
                    universe[t] = stock.get_market_ticker_name(t)
                logger.info(" - KOSPI 시총 상위 200: %d 종목", len(top200))
            except Exception as e2:
                logger.error(" - KOSPI 폴백도 실패: %s", e2)
                PYKRX_DETAIL_AVAILABLE = False

    if not universe:
        try:
            listing = fdr.StockListing("KOSPI")
            if "Marcap" in listing.columns:
                listing = listing.sort_values("Marcap", ascending=False).head(200)
            else:
                listing = listing.head(200)
            for _, row in listing.iterrows():
                ticker = str(row["Code"]).zfill(6)
                universe[ticker] = str(row.get("Name", ticker))
            logger.info(" - KOSPI FinanceDataReader 폴백: %d 종목", len(listing))
        except Exception as e3:
            logger.error(" - KOSPI FinanceDataReader 폴백도 실패: %s", e3)

    # ── 코스닥 150 구성종목 (KRX 지수 코드: 2203)
    try:
        tickers_kq150 = stock.get_index_portfolio_deposit_file("2203")
        for t in tickers_kq150:
            name = stock.get_market_ticker_name(t)
            universe[t] = name
        logger.info(" - 코스닥 150: %d 종목", len(tickers_kq150))
    except Exception as e:
        logger.warning(" - 코스닥 150 구성종목 조회 실패, 시총 상위 150 폴백: %s", e)
        try:
            df_cap = stock.get_market_cap_by_ticker(date, market="KOSDAQ")
            top150 = df_cap.nlargest(150, "시가총액")
            for t in top150.index:
                universe[t] = stock.get_market_ticker_name(t)
            logger.info(" - 코스닥 시총 상위 150: %d 종목", len(top150))
        except Exception as e2:
            logger.error(" - 코스닥 폴백도 실패: %s", e2)
            PYKRX_DETAIL_AVAILABLE = False

    has_kosdaq = False
    try:
        listing = fdr.StockListing("KOSDAQ")
        if "Marcap" in listing.columns:
            listing = listing.sort_values("Marcap", ascending=False).head(150)
        else:
            listing = listing.head(150)
        added = 0
        for _, row in listing.iterrows():
            ticker = str(row["Code"]).zfill(6)
            if ticker not in universe:
                universe[ticker] = str(row.get("Name", ticker))
                added += 1
        has_kosdaq = added > 0
        if added:
            logger.info(" - 코스닥 FinanceDataReader 폴백: %d 종목", added)
    except Exception as e3:
        if not has_kosdaq:
            logger.error(" - 코스닥 FinanceDataReader 폴백도 실패: %s", e3)

    return universe


# ─────────────────────────────────────────────
# 1. OHLCV (수정주가 포함)
# ─────────────────────────────────────────────
def fetch_ohlcv(ticker: str, from_date: str, to_date: str) -> bool:
    try:
        df = stock.get_market_ohlcv_by_date(from_date, to_date, ticker, adjusted=True)
        path = os.path.join(BASE_DIR, ticker, "ohlcv.csv")
        return save_csv(df, path)
    except Exception as e:
        logger.debug(" [%s] pykrx OHLCV 실패, FinanceDataReader 폴백 시도: %s", ticker, e)
        try:
            start = f"{from_date[:4]}-{from_date[4:6]}-{from_date[6:]}"
            end = f"{to_date[:4]}-{to_date[4:6]}-{to_date[6:]}"
            df = fdr.DataReader(ticker, start, end)
            path = os.path.join(BASE_DIR, ticker, "ohlcv.csv")
            return save_csv(df, path)
        except Exception as e2:
            logger.debug(" [%s] FDR OHLCV도 실패: %s", ticker, e2)
            return False


# ─────────────────────────────────────────────
# 2. Fundamental (PER, PBR, EPS, BPS, DPS, DIV)
# ─────────────────────────────────────────────
def fetch_fundamental(ticker: str, from_date: str, to_date: str) -> bool:
    try:
        df = stock.get_market_fundamental_by_date(from_date, to_date, ticker)
        path = os.path.join(BASE_DIR, ticker, "fundamental.csv")
        return save_csv(df, path)
    except Exception as e:
        logger.debug(" [%s] Fundamental 실패: %s", ticker, e)
        return False


# ─────────────────────────────────────────────
# 3. 시가총액 시계열
# ─────────────────────────────────────────────
def fetch_market_cap(ticker: str, from_date: str, to_date: str) -> bool:
    try:
        df = stock.get_market_cap_by_date(from_date, to_date, ticker)
        path = os.path.join(BASE_DIR, ticker, "market_cap.csv")
        return save_csv(df, path)
    except Exception as e:
        logger.debug(" [%s] MarketCap 실패: %s", ticker, e)
        return False


# ─────────────────────────────────────────────
# 4. 투자자별 순매수 (외국인 / 기관 / 개인)
# ─────────────────────────────────────────────
def fetch_net_purchase(ticker: str, from_date: str, to_date: str) -> bool:
    try:
        rows = []
        for investor in ["외국인합계", "기관합계", "개인"]:
            df = stock.get_market_trading_value_and_volume_by_ticker(
                from_date, to_date, "ALL", investor
            )
            if ticker not in df.index:
                continue
            row = df.loc[ticker].copy()
            row.name = investor
            rows.append(row)
            time.sleep(API_DELAY)

        if not rows:
            return False

        result = pd.DataFrame(rows)
        result.index.name = "investor"
        path = os.path.join(BASE_DIR, ticker, "net_purchase.csv")
        return save_csv(result, path)
    except Exception as e:
        logger.debug(" [%s] NetPurchase 실패: %s", ticker, e)
        return False


# ─────────────────────────────────────────────
# 5. 공매도 잔고 시계열
# ─────────────────────────────────────────────
def fetch_shorting(ticker: str, from_date: str, to_date: str) -> bool:
    try:
        df = stock.get_shorting_balance_by_date(from_date, to_date, ticker)
        path = os.path.join(BASE_DIR, ticker, "shorting.csv")
        return save_csv(df, path)
    except Exception as e:
        logger.debug(" [%s] Shorting 실패: %s", ticker, e)
        return False


# ─────────────────────────────────────────────
# 6. 외국인 한도소진율 (전종목 스냅샷, 1회)
# ─────────────────────────────────────────────
def fetch_foreign_exhaustion(date: str):
    logger.info("[SNAPSHOT] 외국인 한도소진율 수집 ...")
    for market in ["KOSPI", "KOSDAQ"]:
        try:
            df = stock.get_exhaustion_rates_of_foreign_investment_by_ticker(date, market=market)
            path = os.path.join(BASE_DIR, f"foreign_exhaustion_{market.lower()}.csv")
            if save_csv(df, path):
                logger.info(" - %s 외국인 한도소진율: %d 종목", market, len(df))
        except Exception as e:
            logger.warning(" - %s 외국인 한도소진율 실패: %s", market, e)
        time.sleep(API_DELAY)


# ─────────────────────────────────────────────
# 7. 섹터 분류 (전종목 스냅샷, 1회)
# ─────────────────────────────────────────────
def fetch_sector_map(date: str):
    logger.info("[SNAPSHOT] KRX 섹터 분류 수집 ...")
    frames = []
    for market in ["KOSPI", "KOSDAQ"]:
        try:
            df = stock.get_market_sector_classifications(date, market)
            df["market"] = market
            frames.append(df)
            logger.info(" - %s 섹터: %d 종목", market, len(df))
        except Exception as e:
            logger.warning(" - %s 섹터 실패: %s", market, e)
        time.sleep(API_DELAY)

    if frames:
        result = pd.concat(frames)
        path = os.path.join(BASE_DIR, "sector_map.csv")
        save_csv(result, path)


# ─────────────────────────────────────────────
# 메인 수집 루프
# ─────────────────────────────────────────────
def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== 06. 종목별 상세 데이터 수집 시작 (KOSPI200 + 코스닥150) ===")
    ensure_dir(BASE_DIR)

    td = today_str()
    sd = start_str()

    # 유니버스 구성
    logger.info("[유니버스] KOSPI200 + 코스닥150 종목 조회 중 ...")
    universe = build_universe(td)
    logger.info("[유니버스] 총 %d 종목 확정", len(universe))

    if not universe:
        logger.error("유니버스가 비어있습니다. 종료.")
        sys.exit(1)

    # 스냅샷 데이터 (1회 수집)
    if PYKRX_DETAIL_AVAILABLE:
        fetch_foreign_exhaustion(td)
        fetch_sector_map(td)
    else:
        logger.warning("pykrx 상세 API 사용 불가 — FDR OHLCV 중심으로 수집합니다.")

    # 종목별 수집
    total = len(universe)
    success_counts = {"ohlcv": 0, "fundamental": 0, "market_cap": 0, "shorting": 0}

    for i, (ticker, name) in enumerate(universe.items(), 1):
        logger.info("[%d/%d] %s (%s)", i, total, name, ticker)

        if fetch_ohlcv(ticker, sd, td):
            success_counts["ohlcv"] += 1
        time.sleep(API_DELAY)

        if PYKRX_DETAIL_AVAILABLE and fetch_fundamental(ticker, sd, td):
            success_counts["fundamental"] += 1
        time.sleep(API_DELAY)

        if PYKRX_DETAIL_AVAILABLE and fetch_market_cap(ticker, sd, td):
            success_counts["market_cap"] += 1
        time.sleep(API_DELAY)

        if PYKRX_DETAIL_AVAILABLE and fetch_shorting(ticker, sd, td):
            success_counts["shorting"] += 1
        time.sleep(API_DELAY)

        # 진행률 로그 (10종목마다)
        if i % 10 == 0:
            logger.info("  → 진행률: %d/%d (%.0f%%)", i, total, i / total * 100)

    logger.info("=== 수집 완료 ===")
    logger.info("  OHLCV:       %d/%d", success_counts["ohlcv"], total)
    logger.info("  Fundamental: %d/%d", success_counts["fundamental"], total)
    logger.info("  MarketCap:   %d/%d", success_counts["market_cap"], total)
    logger.info("  Shorting:    %d/%d", success_counts["shorting"], total)
    logger.info("  저장 경로: %s", BASE_DIR)


if __name__ == "__main__":
    run()
