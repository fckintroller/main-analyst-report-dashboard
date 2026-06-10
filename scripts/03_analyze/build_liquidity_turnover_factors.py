"""
유동성 / 거래회전율 팩터 구축.

소스: stock_detail_{ticker}_market_cap (396종목, 일별, 2023-06 ~ 2026-06)
  컬럼(위치 기준): [0]=날짜, [1]=시가총액, [2]=거래량, [3]=거래대금, [4]=상장주식수

출력 컬럼 (월간):
  market_cap                  : 월말 시가총액
  turnover_value_avg          : 월평균 거래대금
  turnover_ratio               : 월평균 거래대금 / 월말 시가총액 (일평균 회전율 proxy)
  turnover_ratio_zscore_own_12m: 자기 과거 12개월 대비 회전율 z-score (관심 집중/소외 전환 추세)
  turnover_ratio_pct_cross     : 해당 월 회전율 횡단면 백분위
  zscore_pct_cross             : 해당 월 회전율 z-score 횡단면 백분위
  liquidity_score              : 0~1, 위 두 백분위 평균
  liquidity_bucket              : very_high > high > neutral > low > very_low

출력 DB 테이블:
  factor_liquidity_turnover_month
  factor_liquidity_turnover_catalog
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

ZSCORE_WINDOW = 12
MIN_ROWS = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_market_cap_tickers(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_detail_%_market_cap'"
    ).fetchall()
    tickers = []
    for (name,) in rows:
        parts = name.split("_")
        if len(parts) >= 4:
            tickers.append(parts[-3])
    return sorted(set(tickers))


def _load_sector_map(conn: sqlite3.Connection) -> dict[str, str]:
    """티커 → 섹터 매핑. sector_map.csv 우선, 없으면 factor_valuation에서."""
    if SECTOR_MAP_PATH.exists():
        try:
            sm = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
            tk_col = sm.columns[0]
            sec_col = sm.columns[1] if sm.shape[1] >= 2 else sm.columns[0]
            return dict(zip(sm[tk_col].astype(str).str.zfill(6), sm[sec_col].astype(str)))
        except Exception:
            pass

    try:
        df = pd.read_sql(
            "SELECT DISTINCT ticker, sector FROM factor_valuation_per_pbr_month", conn
        )
        return dict(zip(df["ticker"], df["sector"]))
    except Exception:
        return {}


def _compute_ticker(conn: sqlite3.Connection, ticker: str) -> pd.DataFrame | None:
    tbl = f"stock_detail_{ticker}_market_cap"
    try:
        df = pd.read_sql(f"SELECT * FROM [{tbl}] ORDER BY 1", conn)
    except Exception:
        return None

    if len(df) < MIN_ROWS:
        return None

    date_col = df.columns[0]
    mcap_col = df.columns[1]
    turnover_col = df.columns[3]

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[mcap_col] = pd.to_numeric(df[mcap_col], errors="coerce")
    df[turnover_col] = pd.to_numeric(df[turnover_col], errors="coerce")
    df = df.dropna(subset=[date_col, mcap_col, turnover_col])
    df = df[df[mcap_col] > 0].sort_values(date_col).set_index(date_col)

    if len(df) < MIN_ROWS:
        return None

    monthly_mcap = df[mcap_col].resample("ME").last()
    monthly_turnover = df[turnover_col].resample("ME").mean()

    out = pd.DataFrame({
        "market_cap": monthly_mcap,
        "turnover_value_avg": monthly_turnover,
    })
    out["turnover_ratio"] = np.where(
        out["market_cap"] > 0, out["turnover_value_avg"] / out["market_cap"], np.nan
    )

    roll_mean = out["turnover_ratio"].rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).mean()
    roll_std = out["turnover_ratio"].rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).std()
    out["turnover_ratio_zscore_own_12m"] = np.where(
        roll_std > 0, (out["turnover_ratio"] - roll_mean) / roll_std, np.nan
    )

    out = out.reset_index().rename(columns={date_col: "period"})
    out["period"] = out["period"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-01")
    out["ticker"] = ticker
    return out


def _bucket_liquidity(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= 0.8:
        return "very_high"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "neutral"
    if score >= 0.2:
        return "low"
    return "very_low"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    tickers = _load_market_cap_tickers(conn)
    sector_map = _load_sector_map(conn)
    logger.info("%d개 종목 처리 시작", len(tickers))

    frames = []
    for i, ticker in enumerate(tickers, 1):
        out = _compute_ticker(conn, ticker)
        if out is not None:
            frames.append(out)
        if i % 100 == 0:
            logger.info("  %d/%d 완료", i, len(tickers))

    if not frames:
        logger.error("데이터 없음")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["sector"] = df["ticker"].map(sector_map).fillna("unknown")

    df["turnover_ratio_pct_cross"] = df.groupby("period")["turnover_ratio"].rank(pct=True)
    df["zscore_pct_cross"] = df.groupby("period")["turnover_ratio_zscore_own_12m"].rank(pct=True)

    df["liquidity_score"] = df[["turnover_ratio_pct_cross", "zscore_pct_cross"]].mean(
        axis=1, skipna=True
    )
    df.loc[
        df[["turnover_ratio_pct_cross", "zscore_pct_cross"]].isna().all(axis=1), "liquidity_score"
    ] = np.nan
    df["liquidity_bucket"] = df["liquidity_score"].apply(_bucket_liquidity)

    logger.info("구축 완료: %d행 (%d종목)", len(df), df["ticker"].nunique())
    return df[[
        "ticker", "period", "sector", "market_cap", "turnover_value_avg",
        "turnover_ratio", "turnover_ratio_zscore_own_12m",
        "turnover_ratio_pct_cross", "zscore_pct_cross",
        "liquidity_score", "liquidity_bucket",
    ]].sort_values(["ticker", "period"])


CATALOG = [
    ("turnover_ratio",                "거래회전율 proxy",            "월평균 거래대금 / 월말 시가총액",                     "month"),
    ("turnover_ratio_zscore_own_12m", "회전율 자기 12개월 z-score",  "양수=평소보다 활발(관심 집중), 음수=소외",            "month"),
    ("turnover_ratio_pct_cross",      "회전율 횡단면 백분위",        "0~1, 해당 월 전 종목 중 상대 순위",                   "month"),
    ("zscore_pct_cross",              "회전율 변화 횡단면 백분위",   "0~1, 회전율 z-score의 해당 월 상대 순위",             "month"),
    ("liquidity_score",               "유동성 복합 점수",            "0~1, turnover_ratio_pct_cross + zscore_pct_cross 평균", "month"),
    ("liquidity_bucket",              "유동성 버킷",                 "very_high > high > neutral > low > very_low",         "month"),
]


def run():
    logger.info("liquidity_turnover 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_liquidity_turnover_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_liquidity_turnover_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_liquidity_turnover_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_liquidity_turnover_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    latest = df["period"].max()
    print(f"\n=== 최신 월({latest}) 유동성 버킷 분포 ===")
    print(df[df["period"] == latest]["liquidity_bucket"].value_counts())
