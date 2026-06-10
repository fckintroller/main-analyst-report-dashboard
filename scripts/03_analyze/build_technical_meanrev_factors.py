"""
기술적 과매수/과매도 (평균회귀) 팩터 구축.

소스: stock_detail_{ticker}_ohlcv (432종목, ~729일)

출력 컬럼:
  rsi_14            : RSI(14, Wilder 평활) — 30 미만=과매도, 70 초과=과매수
  bb_percent_b      : 볼린저밴드 %B = (종가-하단)/(상단-하단), 20일·2표준편차
  disparity_20      : 종가/20일이평 - 1 (이격도)
  disparity_60      : 종가/60일이평 - 1 (이격도)
  rsi_oversold_pct  : RSI 전 시장 백분위 반전 (낮을수록 과매도 → 점수 높음)
  bb_oversold_pct   : %B 전 시장 백분위 반전
  disparity_oversold_pct : 이격도(20일) 전 시장 백분위 반전
  meanrev_score     : 0~1, 위 3개 평균 (높을수록 과매도 → 단기 반등 후보)
  meanrev_bucket    : oversold > weak_oversold > neutral > weak_overbought > overbought (RSI 기준)

출력 DB 테이블:
  factor_technical_meanrev_snapshot
  factor_technical_meanrev_catalog
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

RSI_WINDOW = 14
BB_WINDOW = 20
BB_STD = 2.0
DISPARITY_SHORT = 20
DISPARITY_LONG = 60
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


def _rsi(close: pd.Series, window: int = RSI_WINDOW) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), np.nan)
    return rsi


def _compute_ticker(conn: sqlite3.Connection, ticker: str) -> dict | None:
    tbl = f"stock_detail_{ticker}_ohlcv"
    try:
        df = pd.read_sql(f"SELECT * FROM [{tbl}] ORDER BY 1", conn)
    except Exception:
        return None

    if len(df) < MIN_ROWS:
        return None

    date_col = df.columns[0]
    close_col = df.columns[4]

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
    df = df.dropna(subset=[date_col, close_col]).sort_values(date_col)

    if len(df) < MIN_ROWS:
        return None

    close = df[close_col]

    df["rsi_14"] = _rsi(close, RSI_WINDOW)

    ma20 = close.rolling(BB_WINDOW, min_periods=BB_WINDOW).mean()
    std20 = close.rolling(BB_WINDOW, min_periods=BB_WINDOW).std()
    upper = ma20 + BB_STD * std20
    lower = ma20 - BB_STD * std20
    band_width = upper - lower
    df["bb_percent_b"] = np.where(band_width > 0, (close - lower) / band_width, np.nan)

    ma60 = close.rolling(DISPARITY_LONG, min_periods=DISPARITY_LONG).mean()
    df["disparity_20"] = np.where(ma20 > 0, close / ma20 - 1.0, np.nan)
    df["disparity_60"] = np.where(ma60 > 0, close / ma60 - 1.0, np.nan)

    last = df.iloc[-1]

    return {
        "ticker": ticker,
        "snapshot_date": str(last[date_col].date()),
        "close": float(last[close_col]),
        "rsi_14": float(last["rsi_14"]) if pd.notna(last["rsi_14"]) else np.nan,
        "bb_percent_b": float(last["bb_percent_b"]) if pd.notna(last["bb_percent_b"]) else np.nan,
        "disparity_20": float(last["disparity_20"]) if pd.notna(last["disparity_20"]) else np.nan,
        "disparity_60": float(last["disparity_60"]) if pd.notna(last["disparity_60"]) else np.nan,
    }


def _bucket_meanrev(rsi: float) -> str:
    if pd.isna(rsi):
        return "unknown"
    if rsi < 30:
        return "oversold"
    if rsi < 45:
        return "weak_oversold"
    if rsi <= 55:
        return "neutral"
    if rsi <= 70:
        return "weak_overbought"
    return "overbought"


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

    # 전 시장 백분위 반전 (낮을수록 과매도 → 점수 높음)
    df["rsi_oversold_pct"] = 1.0 - df["rsi_14"].rank(pct=True)
    df["bb_oversold_pct"] = 1.0 - df["bb_percent_b"].rank(pct=True)
    df["disparity_oversold_pct"] = 1.0 - df["disparity_20"].rank(pct=True)

    df["meanrev_score"] = df[
        ["rsi_oversold_pct", "bb_oversold_pct", "disparity_oversold_pct"]
    ].mean(axis=1, skipna=True)

    df["meanrev_bucket"] = df["rsi_14"].apply(_bucket_meanrev)

    logger.info("구축 완료: %d행", len(df))
    return df[[
        "ticker", "snapshot_date", "sector", "close",
        "rsi_14", "bb_percent_b", "disparity_20", "disparity_60",
        "rsi_oversold_pct", "bb_oversold_pct", "disparity_oversold_pct",
        "meanrev_score", "meanrev_bucket",
    ]]


CATALOG = [
    ("rsi_14",            "RSI(14, Wilder 평활)",   "0~100, 30 미만=과매도, 70 초과=과매수",        "snapshot"),
    ("bb_percent_b",      "볼린저밴드 %B (20일,2표준편차)", "0=하단밴드, 1=상단밴드, 범위 밖 가능",     "snapshot"),
    ("disparity_20",      "20일 이격도",            "종가/20일이평 - 1, 음수=이평선 아래",          "snapshot"),
    ("disparity_60",      "60일 이격도",            "종가/60일이평 - 1, 음수=이평선 아래",          "snapshot"),
    ("meanrev_score",     "평균회귀 복합 점수",      "0~1, 높을수록 과매도(단기 반등 후보)",         "snapshot"),
    ("meanrev_bucket",    "RSI 구간 버킷",          "oversold > weak_oversold > neutral > weak_overbought > overbought", "snapshot"),
]


def run():
    logger.info("technical_meanrev 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_technical_meanrev_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_technical_meanrev_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_technical_meanrev_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_technical_meanrev_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 과매도 상위 20 (meanrev_score) ===")
    print(df.nlargest(20, "meanrev_score")[
        ["ticker", "sector", "rsi_14", "bb_percent_b", "disparity_20", "meanrev_score", "meanrev_bucket"]
    ].to_string())
