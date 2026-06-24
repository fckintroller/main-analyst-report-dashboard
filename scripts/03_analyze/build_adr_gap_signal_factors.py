"""
ADR 오버나잇 갭 시그널 팩터 구축.

소스: valuation_adrs_{name} (8개, 일별 2009-12-31 ~ 2026-06-04, yfinance OHLCV)
  컬럼: Unnamed: 0(날짜, 미국 거래일 기준), Open, High, Low, Close, Volume, Adj Close
  대상: KB금융(105560) 신한지주(055550) 우리금융지주(316140) POSCO홀딩스(005490)
        KT(030200) SK텔레콤(017670) 한국전력(015760) LG디스플레이(034220)
        ※ 쿠팡(coupang)은 국내 동일 종목이 없어 제외

비교: stock_detail_{ticker}_ohlcv (국내 일봉, 2023-06 ~ 2026-06)
  컬럼(위치 기준): [0]=날짜, [1]=시가, [4]=종가

정렬 로직:
  미국 ADR 거래일 D(미 동부시간) 종가는 한국시간 기준 D+1일 새벽에 형성됨
  → KRX D+1 거래일 시가 갭과 비교 (target_domestic_date = D + 1 캘린더일,
     실제 매칭은 국내 일봉 테이블에 존재하는 날짜만 사용, 휴장일은 NaN)

출력 컬럼 (일별):
  adr_close_usd          : ADR 종가 (USD)
  adr_ret_1d_pct          : ADR 전일대비 등락률 (%)
  adr_ret_5d_pct          : ADR 5거래일 등락률 (%)
  adr_ret_zscore_60d      : adr_ret_1d_pct의 자기 60일 z-score
  adr_gap_pctile_252d     : 0~1, adr_ret_1d_pct의 자기 252일 백분위 (롤링)
  gap_bucket               : strong_positive > positive > neutral > negative > strong_negative
  target_domestic_date     : 비교 대상 국내 거래일 (예측치)
  realized_gap_pct         : (국내 시가 - 전일 국내 종가) / 전일 국내 종가 * 100, 실현 갭 (검증/백테스트용)

출력 DB 테이블:
  factor_adr_gap_signal_daily
  factor_adr_gap_signal_catalog
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

ZSCORE_WINDOW = 60
PCTILE_WINDOW = 252

ADR_TICKER_MAP = {
    "kbfinancial": ("105560", "KB금융"),
    "shinhan":     ("055550", "신한지주"),
    "woori":       ("316140", "우리금융지주"),
    "posco":       ("005490", "POSCO홀딩스"),
    "kt":          ("030200", "KT"),
    "sktelecom":   ("017670", "SK텔레콤"),
    "kepco":       ("015760", "한국전력"),
    "lgdisplay":   ("034220", "LG디스플레이"),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _bucket_gap(ret_pct: float) -> str:
    if pd.isna(ret_pct):
        return "unknown"
    if ret_pct >= 1.5:
        return "strong_positive"
    if ret_pct >= 0.3:
        return "positive"
    if ret_pct <= -1.5:
        return "strong_negative"
    if ret_pct <= -0.3:
        return "negative"
    return "neutral"


def _load_domestic_ohlcv(conn: sqlite3.Connection, ticker: str) -> pd.DataFrame | None:
    tbl = f"stock_detail_{ticker}_ohlcv"
    try:
        df = pd.read_sql(f"SELECT * FROM [{tbl}] ORDER BY 1", conn)
    except Exception:
        return None
    date_col, open_col, close_col = df.columns[0], df.columns[1], df.columns[4]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[open_col] = pd.to_numeric(df[open_col], errors="coerce")
    df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    df["prev_close"] = df[close_col].shift(1)
    df["realized_gap_pct"] = np.where(
        df["prev_close"] > 0,
        (df[open_col] - df["prev_close"]) / df["prev_close"] * 100,
        np.nan,
    )
    return df[[date_col, "realized_gap_pct"]].rename(columns={date_col: "domestic_date"})


def _compute_one(conn: sqlite3.Connection, name: str, ticker: str, corp_name: str) -> pd.DataFrame | None:
    tbl = f"valuation_adrs_{name}"
    df = pd.read_sql(f"SELECT [Unnamed: 0] AS date, Close FROM [{tbl}] ORDER BY date", conn)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["date", "Close"]).sort_values("date")

    df["adr_ret_1d_pct"] = df["Close"].pct_change() * 100
    df["adr_ret_5d_pct"] = df["Close"].pct_change(5) * 100

    roll_mean = df["adr_ret_1d_pct"].rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).mean()
    roll_std = df["adr_ret_1d_pct"].rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).std()
    df["adr_ret_zscore_60d"] = np.where(roll_std > 0, (df["adr_ret_1d_pct"] - roll_mean) / roll_std, np.nan)

    df["adr_gap_pctile_252d"] = df["adr_ret_1d_pct"].rolling(PCTILE_WINDOW, min_periods=PCTILE_WINDOW).rank(pct=True)
    df["gap_bucket"] = df["adr_ret_1d_pct"].apply(_bucket_gap)

    df["target_domestic_date"] = df["date"] + pd.Timedelta(days=1)

    domestic = _load_domestic_ohlcv(conn, ticker)
    if domestic is not None:
        df = df.merge(domestic, left_on="target_domestic_date", right_on="domestic_date", how="left")
        df = df.drop(columns=["domestic_date"])
    else:
        df["realized_gap_pct"] = np.nan

    df["ticker"] = ticker
    df["corp_name_kr"] = corp_name
    df = df.rename(columns={"date": "date", "Close": "adr_close_usd"})
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df["target_domestic_date"] = df["target_domestic_date"].dt.strftime("%Y-%m-%d")
    return df


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    frames = []
    for name, (ticker, corp_name) in ADR_TICKER_MAP.items():
        out = _compute_one(conn, name, ticker, corp_name)
        if out is not None:
            frames.append(out)

    df = pd.concat(frames, ignore_index=True)
    logger.info("구축 완료: %d행 (%d종목)", len(df), df["ticker"].nunique())
    return df[[
        "ticker", "corp_name_kr", "date", "adr_close_usd",
        "adr_ret_1d_pct", "adr_ret_5d_pct", "adr_ret_zscore_60d",
        "adr_gap_pctile_252d", "gap_bucket",
        "target_domestic_date", "realized_gap_pct",
    ]].sort_values(["ticker", "date"])


CATALOG = [
    ("adr_ret_1d_pct",       "ADR 전일대비 등락률",     "%, 미국 거래일 기준 ADR 종가 변화율",                       "daily"),
    ("adr_ret_5d_pct",       "ADR 5거래일 등락률",      "%, 5거래일 누적 변화율",                                   "daily"),
    ("adr_ret_zscore_60d",   "ADR 등락률 60일 z-score", "자기 과거 60일 평균/표준편차 대비 z-score",                 "daily"),
    ("adr_gap_pctile_252d",  "ADR 갭 신호 백분위",      "0~1, 자기 과거 252거래일 중 adr_ret_1d_pct 상대 순위(롤링)", "daily"),
    ("gap_bucket",           "갭 시그널 버킷",          "strong_positive > positive > neutral > negative > strong_negative", "daily"),
    ("target_domestic_date", "비교 대상 국내 거래일",   "ADR 거래일 + 1캘린더일 (예측 대상)",                       "daily"),
    ("realized_gap_pct",     "실현 갭률",               "%, (국내 시가-전일종가)/전일종가, target_domestic_date 기준 (검증용)", "daily"),
]


def run():
    logger.info("adr_gap_signal 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_adr_gap_signal_daily", conn, if_exists="replace", index=False)
        logger.info("  → factor_adr_gap_signal_daily 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_adr_gap_signal_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_adr_gap_signal_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 종목별 최신 갭 시그널 ===")
    latest = df.sort_values("date").groupby("ticker").tail(1)
    print(latest[["ticker", "corp_name_kr", "date", "adr_ret_1d_pct", "gap_bucket", "target_domestic_date"]].to_string())
    print("\n=== 실현 갭과의 상관관계 (전체 기간) ===")
    valid = df.dropna(subset=["adr_ret_1d_pct", "realized_gap_pct"])
    print("n=", len(valid), "corr=", valid["adr_ret_1d_pct"].corr(valid["realized_gap_pct"]))
