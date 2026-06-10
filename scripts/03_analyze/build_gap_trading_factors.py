"""
갭 트레이딩 신호 팩터 구축.

소스: stock_detail_{ticker}_ohlcv (432종목, ~729일)

출력 컬럼:
  prev_close          : 전일 종가
  open                : 당일 시가
  gap_pct             : (시가 - 전일종가) / 전일종가
  gap_direction       : gap_up / gap_down / flat (|gap_pct| < 0.5% = flat)
  gap_filled_today    : 당일 중 갭 방향 반대로 전일종가까지 되돌림 여부 (0/1, flat=NaN)
  gap_fill_rate_60d   : 최근 60일 중 |gap_pct|>=0.5% 발생일의 당일 갭필 비율 (종목별 갭필 성향)
  volume_ratio_on_gap : 당일 거래량 / 20일 평균 거래량
  gap_pct_abs_pct_cross : 전 시장 |gap_pct| 백분위 (오늘 갭 크기가 시장에서 얼마나 큰지)
  gap_signal_score    : 0~1, |갭|백분위(50%) + 거래량비율 백분위(50%) → "오늘 주목할 갭"
  gap_bucket          : gap_up_strong(>=3%) > gap_up(>=0.5%) > flat > gap_down(<=-0.5%) > gap_down_strong(<=-3%)

출력 DB 테이블:
  factor_gap_trading_snapshot
  factor_gap_trading_catalog
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

VOL_WINDOW = 20
FILL_LOOKBACK = 60
SIGNIFICANT_GAP = 0.005  # 0.5%
STRONG_GAP = 0.03        # 3%
MIN_ROWS = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_ohlcv_tickers(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_detail_%_ohlcv'"
    ).fetchall()
    tickers = []
    for (name,) in rows:
        parts = name.split("_")
        if len(parts) >= 4:
            tickers.append(parts[-2])
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


def _gap_direction(gap_pct: float) -> str:
    if pd.isna(gap_pct):
        return "unknown"
    if gap_pct >= SIGNIFICANT_GAP:
        return "gap_up"
    if gap_pct <= -SIGNIFICANT_GAP:
        return "gap_down"
    return "flat"


def _gap_bucket(gap_pct: float) -> str:
    if pd.isna(gap_pct):
        return "unknown"
    if gap_pct >= STRONG_GAP:
        return "gap_up_strong"
    if gap_pct >= SIGNIFICANT_GAP:
        return "gap_up"
    if gap_pct <= -STRONG_GAP:
        return "gap_down_strong"
    if gap_pct <= -SIGNIFICANT_GAP:
        return "gap_down"
    return "flat"


def _compute_ticker(conn: sqlite3.Connection, ticker: str) -> dict | None:
    tbl = f"stock_detail_{ticker}_ohlcv"
    try:
        df = pd.read_sql(f"SELECT * FROM [{tbl}] ORDER BY 1", conn)
    except Exception:
        return None

    if len(df) < MIN_ROWS:
        return None

    date_col = df.columns[0]
    open_col = df.columns[1]
    high_col = df.columns[2]
    low_col = df.columns[3]
    close_col = df.columns[4]
    volume_col = df.columns[5]

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    for c in (open_col, high_col, low_col, close_col, volume_col):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=[date_col, open_col, high_col, low_col, close_col, volume_col])
    df = df.sort_values(date_col).reset_index(drop=True)

    if len(df) < MIN_ROWS:
        return None

    df["prev_close"] = df[close_col].shift(1)
    df["gap_pct"] = np.where(
        df["prev_close"] > 0, df[open_col] / df["prev_close"] - 1.0, np.nan
    )

    is_gap_up = df["gap_pct"] > 0
    filled_up = df[low_col] <= df["prev_close"]
    filled_down = df[high_col] >= df["prev_close"]
    df["gap_filled"] = np.where(
        df["gap_pct"].abs() < SIGNIFICANT_GAP, np.nan,
        np.where(is_gap_up, filled_up, filled_down).astype(float)
    )

    vol_ma20 = df[volume_col].rolling(VOL_WINDOW, min_periods=10).mean()
    df["volume_ratio"] = np.where(vol_ma20 > 0, df[volume_col] / vol_ma20, np.nan)

    last = df.iloc[-1]

    # 최근 FILL_LOOKBACK일 중 유의미한 갭(|gap_pct|>=0.5%) 발생일의 갭필 비율
    recent = df.tail(FILL_LOOKBACK)
    sig = recent[recent["gap_pct"].abs() >= SIGNIFICANT_GAP]
    gap_fill_rate_60d = float(sig["gap_filled"].mean()) if len(sig) > 0 else np.nan

    gap_pct = float(last["gap_pct"]) if pd.notna(last["gap_pct"]) else np.nan
    gap_filled_today = float(last["gap_filled"]) if pd.notna(last["gap_filled"]) else np.nan

    return {
        "ticker": ticker,
        "snapshot_date": str(last[date_col].date()),
        "close": float(last[close_col]),
        "prev_close": float(last["prev_close"]) if pd.notna(last["prev_close"]) else np.nan,
        "open": float(last[open_col]),
        "gap_pct": gap_pct,
        "gap_filled_today": gap_filled_today,
        "gap_fill_rate_60d": gap_fill_rate_60d,
        "volume_ratio_on_gap": float(last["volume_ratio"]) if pd.notna(last["volume_ratio"]) else np.nan,
    }


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    tickers = _load_ohlcv_tickers(conn)
    sector_map = _load_sector_map(conn)
    logger.info("%d개 종목 처리 시작", len(tickers))

    records = []
    for i, ticker in enumerate(tickers, 1):
        rec = _compute_ticker(conn, ticker)
        if rec:
            records.append(rec)
        if i % 100 == 0:
            logger.info("  %d/%d 완료", i, len(tickers))

    df = pd.DataFrame(records)
    if df.empty:
        logger.error("데이터 없음")
        return df

    df["sector"] = df["ticker"].map(sector_map).fillna("unknown")

    df["gap_direction"] = df["gap_pct"].apply(_gap_direction)
    df["gap_bucket"] = df["gap_pct"].apply(_gap_bucket)

    df["gap_pct_abs_pct_cross"] = df["gap_pct"].abs().rank(pct=True)
    df["volume_ratio_pct_cross"] = df["volume_ratio_on_gap"].rank(pct=True)

    df["gap_signal_score"] = df[["gap_pct_abs_pct_cross", "volume_ratio_pct_cross"]].mean(
        axis=1, skipna=True
    )

    logger.info("구축 완료: %d행", len(df))
    return df[[
        "ticker", "snapshot_date", "sector", "close",
        "prev_close", "open", "gap_pct", "gap_direction", "gap_bucket",
        "gap_filled_today", "gap_fill_rate_60d", "volume_ratio_on_gap",
        "gap_pct_abs_pct_cross", "gap_signal_score",
    ]]


CATALOG = [
    ("gap_pct",              "당일 시가갭 비율",        "(시가-전일종가)/전일종가, 양수=갭상승",                  "snapshot"),
    ("gap_direction",        "갭 방향",                "gap_up / gap_down / flat (|gap|<0.5%)",                  "snapshot"),
    ("gap_filled_today",     "당일 갭필 여부",          "0/1, 갭 방향 반대로 전일종가까지 되돌림",                 "snapshot"),
    ("gap_fill_rate_60d",    "60일 갭필 성향",          "0~1, 최근 60일 유의미한 갭의 당일 되돌림 비율 (종목 특성)", "snapshot"),
    ("volume_ratio_on_gap",  "갭 발생일 거래량 비율",    "당일 거래량 / 20일 평균 거래량",                          "snapshot"),
    ("gap_signal_score",     "갭 주목도 복합 점수",      "0~1, |갭|백분위(50%)+거래량비율백분위(50%)",              "snapshot"),
    ("gap_bucket",           "갭 크기 버킷",            "gap_up_strong(>=3%) > gap_up(>=0.5%) > flat > gap_down(<=-0.5%) > gap_down_strong(<=-3%)", "snapshot"),
]


def run():
    logger.info("gap_trading 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_gap_trading_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_gap_trading_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_gap_trading_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_gap_trading_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 갭 주목도 상위 20 (gap_signal_score) ===")
    print(df.nlargest(20, "gap_signal_score")[
        ["ticker", "sector", "gap_pct", "gap_bucket", "volume_ratio_on_gap", "gap_fill_rate_60d", "gap_signal_score"]
    ].to_string())
