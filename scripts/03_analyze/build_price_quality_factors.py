"""
52주 신고가 근접도 + 볼륨 서프라이즈 팩터 구축.

소스: stock_detail_{ticker}_ohlcv (432종목, ~729일)

출력 컬럼:
  high_52w_proximity   : 현재가 / 52주 최고가 (1.0 = 신고가)
  high_52w_pct_from_high : (현재가 / 52주 최고가) - 1 (0 = 신고가, 음수 = 하락)
  volume_surge_20d     : 거래량 / 20일 평균 거래량
  volume_surge_60d     : 거래량 / 60일 평균 거래량
  high_52w_score       : 섹터 내 백분위
  volume_surge_score   : 시장 전체 백분위
  price_quality_score  : 0.6 × high_52w_score + 0.4 × volume_surge_score

출력 DB 테이블:
  factor_price_quality_snapshot
  factor_price_quality_catalog
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

WINDOW_52W = 252
WINDOW_VOL_SHORT = 20
WINDOW_VOL_LONG  = 60
MIN_ROWS = 60    # 최소 데이터 필요량
MIN_SECTOR_N = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_ohlcv_tickers(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_detail_%_ohlcv'"
    ).fetchall()
    tickers = []
    for (name,) in rows:
        parts = name.split("_")
        # stock_detail_XXXXXX_ohlcv → parts[-2] is ticker
        if len(parts) >= 4:
            tickers.append(parts[-2])
    return sorted(set(tickers))


def _load_sector_map(conn: sqlite3.Connection) -> dict[str, str]:
    """티커 → 섹터 매핑. sector_map.csv 우선, 없으면 factor_valuation에서."""
    if SECTOR_MAP_PATH.exists():
        try:
            sm = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
            # 첫 컬럼=티커, 두번째=섹터 (또는 마지막 컬럼이 거래소)
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


def _compute_ticker(conn: sqlite3.Connection, ticker: str) -> dict | None:
    tbl = f"stock_detail_{ticker}_ohlcv"
    try:
        df = pd.read_sql(f"SELECT * FROM [{tbl}] ORDER BY 1", conn)
    except Exception:
        return None

    if len(df) < MIN_ROWS:
        return None

    # 위치 기반 컬럼 참조 (한국어 컬럼명 인코딩 무관)
    date_col   = df.columns[0]
    close_col  = df.columns[4]
    volume_col = df.columns[5]

    df[date_col]   = pd.to_datetime(df[date_col], errors="coerce")
    df[close_col]  = pd.to_numeric(df[close_col],  errors="coerce")
    df[volume_col] = pd.to_numeric(df[volume_col], errors="coerce")
    df = df.dropna(subset=[date_col, close_col, volume_col]).sort_values(date_col)

    if len(df) < MIN_ROWS:
        return None

    # 52주 신고가
    df["rolling_high_52w"] = df[close_col].rolling(WINDOW_52W, min_periods=60).max()
    df["vol_ma_20"] = df[volume_col].rolling(WINDOW_VOL_SHORT, min_periods=10).mean()
    df["vol_ma_60"] = df[volume_col].rolling(WINDOW_VOL_LONG,  min_periods=20).mean()

    last = df.iloc[-1]
    close = float(last[close_col])
    volume = float(last[volume_col])
    rolling_high = float(last["rolling_high_52w"]) if pd.notna(last["rolling_high_52w"]) else np.nan
    vol_ma20 = float(last["vol_ma_20"]) if pd.notna(last["vol_ma_20"]) else np.nan
    vol_ma60 = float(last["vol_ma_60"]) if pd.notna(last["vol_ma_60"]) else np.nan

    high_52w_proximity    = (close / rolling_high) if (pd.notna(rolling_high) and rolling_high > 0) else np.nan
    high_52w_pct_from_high = (high_52w_proximity - 1.0) if pd.notna(high_52w_proximity) else np.nan
    volume_surge_20d = (volume / vol_ma20) if (pd.notna(vol_ma20) and vol_ma20 > 0) else np.nan
    volume_surge_60d = (volume / vol_ma60) if (pd.notna(vol_ma60) and vol_ma60 > 0) else np.nan

    return {
        "ticker": ticker,
        "snapshot_date": str(last[date_col].date()),
        "close": close,
        "rolling_high_52w": rolling_high,
        "high_52w_proximity": high_52w_proximity,
        "high_52w_pct_from_high": high_52w_pct_from_high,
        "volume": volume,
        "volume_surge_20d": volume_surge_20d,
        "volume_surge_60d": volume_surge_60d,
    }


def _bucket_52w(prox: float) -> str:
    if pd.isna(prox):
        return "unknown"
    if prox >= 0.97:
        return "near_high"
    if prox >= 0.90:
        return "strong"
    if prox >= 0.80:
        return "moderate"
    if prox >= 0.70:
        return "weak"
    return "far_from_high"


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

    # 섹터 내 52주 신고가 백분위 (높을수록 고점 근접 → 모멘텀 신호)
    df["high_52w_score"] = df.groupby("sector")["high_52w_proximity"].rank(pct=True)
    small_sectors = df.groupby("sector")["high_52w_proximity"].count()
    small_sectors = small_sectors[small_sectors < MIN_SECTOR_N].index
    df.loc[df["sector"].isin(small_sectors), "high_52w_score"] = np.nan

    # 시장 전체 볼륨 서프라이즈 백분위
    df["volume_surge_score"] = df["volume_surge_20d"].rank(pct=True)

    # 복합 점수
    def _composite(row: pd.Series) -> float:
        parts, weights = [], []
        if pd.notna(row["high_52w_score"]):
            parts.append(row["high_52w_score"]); weights.append(0.6)
        if pd.notna(row["volume_surge_score"]):
            parts.append(row["volume_surge_score"]); weights.append(0.4)
        if not parts:
            return np.nan
        tw = sum(weights)
        return sum(p * w for p, w in zip(parts, weights)) / tw

    df["price_quality_score"] = df.apply(_composite, axis=1)
    df["high_52w_bucket"] = df["high_52w_proximity"].apply(_bucket_52w)

    logger.info("구축 완료: %d행", len(df))
    return df[[
        "ticker", "snapshot_date", "sector",
        "close", "rolling_high_52w",
        "high_52w_proximity", "high_52w_pct_from_high",
        "high_52w_bucket",
        "volume", "volume_surge_20d", "volume_surge_60d",
        "high_52w_score", "volume_surge_score", "price_quality_score",
    ]]


CATALOG = [
    ("high_52w_proximity",    "52주 신고가 근접도",   "0~1, 1.0 = 신고가",                                 "snapshot"),
    ("high_52w_pct_from_high","52주 신고가 대비 괴리율","0 = 신고가, 음수 = 고점 대비 하락률",              "snapshot"),
    ("volume_surge_20d",      "볼륨 서프라이즈(20일)", "현재 거래량/20일 평균, 1.0=평균, 2.0=2배",          "snapshot"),
    ("high_52w_score",        "52주 신고가 섹터 백분위","0~1, 높을수록 신고가 근접 (모멘텀 신호)",           "snapshot"),
    ("price_quality_score",   "가격품질 복합 점수",    "0~1, 신고가근접 60% + 볼륨서프라이즈 40%",          "snapshot"),
]


def run():
    logger.info("price_quality 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_price_quality_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_price_quality_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_price_quality_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_price_quality_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 52주 신고가 근접 Top 20 ===")
    print(df.nlargest(20, "high_52w_proximity")[
        ["ticker", "sector", "high_52w_proximity", "volume_surge_20d", "price_quality_score"]
    ].to_string())
