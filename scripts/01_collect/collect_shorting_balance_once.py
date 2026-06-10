"""
pykrx로 종목별 공매도 잔고 시계열 수집.
출력: data/raw/factors/shorting_balance_monthly.csv  (월말 집계)

- KRX_ID / KRX_PW 환경변수 필요 (pykrx 공매도 API 인증)
- 수집 기간: LOOKBACK_MONTHS (기본 13개월, 최소 12개월 필요)
- 월말 잔고율 기준으로 집계
"""
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pykrx import stock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
OUT_PATH = PROJECT_ROOT / "data" / "raw" / "factors" / "shorting_balance_monthly.csv"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

LOOKBACK_MONTHS = 13   # 월별 모멘텀 12개월 계산에 필요한 최소값
API_DELAY = 0.1        # 종목당 딜레이(초) — 네트워크 레이턴시가 병목이므로 최소화
SAVE_EVERY = 50        # 종목마다 중간 저장

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_universe() -> list[str]:
    """기존 팩터 유니버스(가격 모멘텀 432종목) 우선 사용 — 전체 시장 2770종목 대신."""
    import sqlite3
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(
                "SELECT DISTINCT ticker FROM factor_stock_price_momentum_month",
                conn,
            )
            tickers = df["ticker"].astype(str).str.zfill(6).unique().tolist()
            if tickers:
                logger.info("유니버스: factor_stock_price_momentum_month에서 %d종목 로드", len(tickers))
                return tickers
    except Exception as e:
        logger.warning("DB 유니버스 로드 실패: %s", e)

    # 폴백: sector_map KOSPI 종목만
    if SECTOR_MAP_PATH.exists():
        df = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
        kospi = df[df.iloc[:, -1].astype(str).str.upper() == "KOSPI"]
        tickers = kospi.iloc[:, 0].astype(str).str.zfill(6).unique().tolist()
        logger.info("유니버스: sector_map KOSPI %d종목 사용", len(tickers))
        return tickers
    return []


def _date_range() -> tuple[str, str]:
    today = datetime.today()
    start = today - timedelta(days=LOOKBACK_MONTHS * 31 + 5)
    return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def fetch_shorting_monthly(ticker: str, from_date: str, to_date: str) -> pd.DataFrame | None:
    """종목의 일별 공매도 잔고 → 월말 집계로 변환."""
    try:
        df = stock.get_shorting_balance_by_date(from_date, to_date, ticker)
        if df is None or df.empty:
            return None

        df.index = pd.to_datetime(df.index)

        # 컬럼 정규화 (pykrx 버전에 따라 컬럼명 다를 수 있음)
        col_balance = next((c for c in df.columns if "잔고" in c and "비율" not in c and "비중" not in c), None)
        col_shares = next((c for c in df.columns if "상장" in c or "주식수" in c), None)
        # pykrx 버전에 따라 "비율" 또는 "비중"으로 반환됨
        col_ratio = next((c for c in df.columns if "비율" in c or "비중" in c), None)

        if col_balance is None or col_ratio is None:
            return None

        df = df.rename(columns={
            col_balance: "balance",
            col_ratio: "balance_ratio",
        })
        if col_shares:
            df = df.rename(columns={col_shares: "listed_shares"})

        # 월말 리샘플 (마지막 거래일)
        monthly = df.resample("ME").last()
        monthly["ticker"] = ticker
        monthly["period"] = monthly.index.strftime("%Y-%m-01")
        monthly = monthly.reset_index(drop=True)
        return monthly[["ticker", "period", "balance", "balance_ratio"] +
                       (["listed_shares"] if "listed_shares" in monthly.columns else [])]
    except Exception as e:
        logger.debug("  %s 수집 실패: %s", ticker, e)
        return None


def run():
    universe = _load_universe()
    if not universe:
        logger.error("종목 목록 없음")
        return

    from_date, to_date = _date_range()
    logger.info("공매도 잔고 수집 시작: %d종목, %s ~ %s", len(universe), from_date, to_date)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    errors = 0
    total = len(universe)

    for i, ticker in enumerate(universe, 1):
        result = fetch_shorting_monthly(ticker, from_date, to_date)
        if result is not None and not result.empty:
            frames.append(result)
        else:
            errors += 1
        time.sleep(API_DELAY)

        # 진행 상황 로그 + 중간 저장
        if i % SAVE_EVERY == 0 or i == total:
            logger.info("  %d/%d 처리 (수집: %d, 실패: %d)", i, total, len(frames), errors)
            if frames:
                df_partial = pd.concat(frames, ignore_index=True)
                df_partial.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    if not frames:
        logger.error("수집된 데이터 없음")
        return

    df_all = pd.concat(frames, ignore_index=True)
    df_all["balance"] = pd.to_numeric(df_all["balance"], errors="coerce")
    df_all["balance_ratio"] = pd.to_numeric(df_all["balance_ratio"], errors="coerce")

    df_all.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    logger.info("저장 완료: %s (%d행, %d종목)", OUT_PATH.name, len(df_all), df_all["ticker"].nunique())


if __name__ == "__main__":
    run()
