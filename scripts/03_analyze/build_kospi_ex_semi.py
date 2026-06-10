"""
KOSPI 반도체 제외 지수(KOSPI ex-semiconductor) 정확 계산.

방법론:
  KRX 반도체 지수(5044)는 2022년 이전 삼성전자·SK하이닉스를 포함하지 않아
  역사적 비중이 4~6%로 과소 집계됨.

  정확한 계산을 위해 핵심 3종목 직접 시총 합산 방식 사용:
    - 005930 삼성전자     (~55% of 반도체 시총)
    - 000660 SK하이닉스   (~25% of 반도체 시총)
    - 005935 삼성전자우   (~10% of 반도체 시총)
  → 합산으로 반도체 시총의 ~90% 커버

  공식:
    w_t     = semi_mktcap_t / kospi_mktcap_t   (전일 비중 사용)
    ret_ex  = (KOSPI_ret - w_{t-1} * semi_ret) / (1 - w_{t-1})
    kospi_ex_semi_t = 100 * PROD(1 + ret_ex)   (기준점=첫 유효일)

  검증:
    KOSPI_ret = w * semi_ret + (1-w) * ex_semi_ret  ← 항등식

출력:
  data/raw/factors/kospi_ex_semiconductor_daily.csv
    columns: date, kospi, semi_mktcap, kospi_mktcap, semi_weight,
             kospi_ret, semi_ret, ex_semi_ret, kospi_ex_semi

실행:
  python scripts/03_analyze/build_kospi_ex_semi.py
"""
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("KRX_ID", os.getenv("KRX_ID", ""))
os.environ.setdefault("KRX_PW", os.getenv("KRX_PW", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAVE_DIR = PROJECT_ROOT / "data" / "raw" / "factors"
START = "20100101"

# 핵심 반도체 3종목 (반도체 시총의 ~90% 커버)
SEMI_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005935": "삼성전자우",
}
KOSPI_TICKER = "1001"


def fetch_stock_mktcap(ticker: str, name: str) -> pd.Series:
    from pykrx import stock
    end = pd.Timestamp.today().strftime("%Y%m%d")
    logger.info("[FETCH] %s(%s) 시가총액 %s~%s", name, ticker, START, end)
    for attempt in range(3):
        try:
            df = stock.get_market_cap_by_date(START, end, ticker)
            if not df.empty:
                s = df["시가총액"].rename(ticker)
                s.index = pd.to_datetime(s.index)
                return s
        except Exception as e:
            logger.warning(" 시도 %d 실패: %s", attempt + 1, e)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"[{name}] 시가총액 수집 실패")


def fetch_kospi_index() -> pd.DataFrame:
    from pykrx import stock
    end = pd.Timestamp.today().strftime("%Y%m%d")
    logger.info("[FETCH] KOSPI(1001) %s~%s", START, end)
    for attempt in range(3):
        try:
            df = stock.get_index_ohlcv(START, end, KOSPI_TICKER)
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                return df
        except Exception as e:
            logger.warning(" 시도 %d 실패: %s", attempt + 1, e)
            time.sleep(2 ** attempt)
    raise RuntimeError("KOSPI 지수 수집 실패")


def build_ex_semi(kospi_df: pd.DataFrame,
                  semi_mktcap_series: list[pd.Series]) -> pd.DataFrame:
    # KOSPI 종가 + 전체 시총
    close_k   = kospi_df["종가"].rename("kospi")
    mktcap_k  = kospi_df["상장시가총액"].rename("kospi_mktcap")

    # 반도체 3종목 시총 합산
    semi_total = pd.concat(semi_mktcap_series, axis=1).sum(axis=1).rename("semi_mktcap")

    df = pd.concat([close_k, mktcap_k, semi_total], axis=1)
    df = df[df["semi_mktcap"] > 0].dropna().sort_index()

    # 일별 수익률
    df["kospi_ret"] = df["kospi"].pct_change()

    # 반도체 수익률 ≈ 삼성전자 수익률로 대표 (시총 비중 가장 큼)
    # 정확도를 위해 시총 가중 반도체 수익률 계산
    # ret_semi_weighted = SUM(stock_ret_i * mktcap_{i,t-1}) / SUM(mktcap_{i,t-1})
    stock_rets = {}
    stock_mktcaps = {}
    for s in semi_mktcap_series:
        mc = s.reindex(df.index)
        # 해당 종목 일별 수익률 = 시총 변화(주식 수 불변 가정) / 전일 시총
        stock_rets[s.name]    = mc.pct_change()
        stock_mktcaps[s.name] = mc.shift(1)

    ret_df  = pd.DataFrame(stock_rets)
    wgt_df  = pd.DataFrame(stock_mktcaps)
    wgt_sum = wgt_df.sum(axis=1)
    # 시총가중 반도체 수익률
    df["semi_ret"] = (ret_df * wgt_df).sum(axis=1) / wgt_sum

    # 전일 반도체 비중
    df["semi_weight"] = (df["semi_mktcap"] / df["kospi_mktcap"]).shift(1)

    # KOSPI ex-반도체 일별 수익률
    w = df["semi_weight"]
    df["ex_semi_ret"] = (df["kospi_ret"] - w * df["semi_ret"]) / (1 - w)

    # 검증: KOSPI_ret ≈ w * semi_ret + (1-w) * ex_semi_ret
    reconstruct = w * df["semi_ret"] + (1 - w) * df["ex_semi_ret"]
    err = (df["kospi_ret"] - reconstruct).abs().max()
    logger.info("검증 최대 오차: %.2e", err)

    # 지수 누적 (첫 유효일 기준 100)
    valid_mask = df["ex_semi_ret"].notna() & df["semi_weight"].notna()
    first_idx  = df[valid_mask].index[0]
    df.loc[first_idx:, "kospi_ex_semi"] = (
        (1 + df.loc[first_idx:, "ex_semi_ret"].fillna(0)).cumprod() * 100
    )

    return df[[
        "kospi", "semi_mktcap", "kospi_mktcap", "semi_weight",
        "kospi_ret", "semi_ret", "ex_semi_ret", "kospi_ex_semi"
    ]]


def run():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    # 데이터 수집
    kospi_df = fetch_kospi_index()
    semi_series = []
    for ticker, name in SEMI_STOCKS.items():
        s = fetch_stock_mktcap(ticker, name)
        semi_series.append(s)
        time.sleep(0.5)

    # 계산
    df = build_ex_semi(kospi_df, semi_series)

    # 결과 출력
    latest = df.dropna(subset=["semi_weight"]).iloc[-1]
    logger.info("=== 최신 현황 (%s) ===", df.index[-1].date())
    logger.info("  KOSPI:                %8.2f", latest["kospi"])
    logger.info("  반도체 시총:           %,.0f조", latest["semi_mktcap"] / 1e12)
    logger.info("  KOSPI 전체 시총:       %,.0f조", latest["kospi_mktcap"] / 1e12)
    logger.info("  반도체 비중(전일):      %5.1f%%", latest["semi_weight"] * 100)
    logger.info("  KOSPI ex-반도체:       %8.2f  (기준=100)", latest["kospi_ex_semi"])
    logger.info("  KOSPI 1일 수익률:      %+6.2f%%", latest["kospi_ret"] * 100)
    logger.info("  반도체 1일 수익률:     %+6.2f%%", latest["semi_ret"] * 100)
    logger.info("  ex-반도체 수익률:      %+6.2f%%", latest["ex_semi_ret"] * 100)

    # 연도별 비중 출력
    logger.info("=== 연도별 반도체 비중(삼성+SK+삼성우) ===")
    for yr, w in df.groupby(df.index.year)["semi_weight"].mean().items():
        logger.info("  %d: %.1f%%", yr, w * 100)

    # 저장
    path = SAVE_DIR / "kospi_ex_semiconductor_daily.csv"
    df.index.name = "date"
    df.to_csv(path)
    logger.info("저장: %s  (%d행)", path, len(df))


if __name__ == "__main__":
    run()
