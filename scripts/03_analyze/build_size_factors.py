"""
사이즈(시가총액) 팩터 구축.

소스: stock_detail_{ticker}_market_cap (396종목, 일별, 2023-06 ~ 2026-06)
  컬럼(위치 기준): [0]=날짜, [1]=시가총액, [2]=거래량, [3]=거래대금, [4]=상장주식수

출력 컬럼 (월간):
  market_cap            : 월말 시가총액
  log_market_cap        : log10(시가총액)
  size_percentile_cross : 해당 월 시가총액 횡단면 백분위 (1에 가까울수록 대형주)
  size_bucket           : mega(>=0.95) > large(>=0.8) > mid(>=0.5) > small(>=0.2) > micro
  mcap_change_3m        : 3개월 시가총액 변화율 (자금유입/관심 집중도 프록시)
  small_cap_score       : 0~1, 1 - size_percentile_cross (높을수록 소형주 프리미엄 후보)

출력 DB 테이블:
  factor_size_month
  factor_size_catalog
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

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

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[mcap_col] = pd.to_numeric(df[mcap_col], errors="coerce")
    df = df.dropna(subset=[date_col, mcap_col])
    df = df[df[mcap_col] > 0].sort_values(date_col).set_index(date_col)

    if len(df) < MIN_ROWS:
        return None

    monthly_mcap = df[mcap_col].resample("ME").last()
    out = pd.DataFrame({"market_cap": monthly_mcap})
    out["log_market_cap"] = np.log10(out["market_cap"])
    out["mcap_change_3m"] = out["market_cap"].pct_change(3)

    out = out.reset_index().rename(columns={date_col: "period"})
    out["period"] = out["period"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-01")
    out["ticker"] = ticker
    return out


def _bucket_size(pct: float) -> str:
    if pd.isna(pct):
        return "unknown"
    if pct >= 0.95:
        return "mega"
    if pct >= 0.80:
        return "large"
    if pct >= 0.50:
        return "mid"
    if pct >= 0.20:
        return "small"
    return "micro"


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

    df["size_percentile_cross"] = df.groupby("period")["market_cap"].rank(pct=True)
    df["size_bucket"] = df["size_percentile_cross"].apply(_bucket_size)
    df["small_cap_score"] = 1.0 - df["size_percentile_cross"]

    logger.info("구축 완료: %d행 (%d종목)", len(df), df["ticker"].nunique())
    return df[[
        "ticker", "period", "sector", "market_cap", "log_market_cap",
        "size_percentile_cross", "size_bucket", "mcap_change_3m", "small_cap_score",
    ]].sort_values(["ticker", "period"])


CATALOG = [
    ("market_cap",            "시가총액 (원)",                "월말 기준",                                        "month"),
    ("log_market_cap",        "log10(시가총액)",              "분포 왜도 완화",                                    "month"),
    ("size_percentile_cross", "시가총액 횡단면 백분위",        "0~1, 1에 가까울수록 대형주",                        "month"),
    ("size_bucket",           "사이즈 버킷",                   "mega(>=0.95) > large(>=0.8) > mid(>=0.5) > small(>=0.2) > micro", "month"),
    ("mcap_change_3m",        "3개월 시가총액 변화율",         "자금유입/관심 집중도 프록시 (가격×유통주식수 변화 모두 반영)", "month"),
    ("small_cap_score",       "소형주 프리미엄 점수",          "0~1, 1 - size_percentile_cross (높을수록 소형주)",  "month"),
]


def run():
    logger.info("size 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_size_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_size_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_size_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_size_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    latest = df["period"].max()
    print(f"\n=== 최신 월({latest}) 사이즈 버킷 분포 ===")
    print(df[df["period"] == latest]["size_bucket"].value_counts())
