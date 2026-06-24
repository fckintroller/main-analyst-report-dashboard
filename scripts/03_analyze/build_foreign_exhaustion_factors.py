"""
외국인 보유비중 / 한도소진율 팩터 구축.

소스: stock_market_snapshot_{kospi,kosdaq}_foreign_exhaustion_by_ticker_20260605 (단면)
  컬럼(위치 기준): [0]=티커, [1]=상장주식수, [2]=외국인보유주식수, [3]=외국인지분율(%),
                   [4]=한도수량, [5]=한도소진율(%)

출력 컬럼 (스냅샷):
  foreign_ownership_pct        : 외국인 지분율 (%)
  limit_exhaustion_pct         : 외국인 한도소진율 (%)
  foreign_ownership_pct_cross  : 0~1, 전체 종목 대비 지분율 횡단면 백분위
  limit_exhaustion_pct_cross   : 0~1, 전체 종목 대비 한도소진율 횡단면 백분위
  foreign_room_score           : 0~1, 1 - 한도소진율/100 (높을수록 외국인 추가 매수 여력 많음)
  ownership_bucket              : 지분율 버킷, very_high > high > mid > low > very_low
  room_bucket                   : 매수여력 버킷, very_high > high > mid > low > very_low (very_low=소진 임박)

출력 DB 테이블:
  factor_foreign_exhaustion_snapshot
  factor_foreign_exhaustion_catalog
"""
import logging
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

SNAPSHOT_DATE = "2026-06-05"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


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


def _load_market(conn: sqlite3.Connection, market: str) -> pd.DataFrame:
    tbl = f"stock_market_snapshot_{market}_foreign_exhaustion_by_ticker_20260605"
    df = pd.read_sql(f"SELECT * FROM [{tbl}]", conn)
    df = df.rename(columns={
        df.columns[0]: "ticker",
        df.columns[1]: "shares_outstanding",
        df.columns[2]: "foreign_shares_held",
        df.columns[3]: "foreign_ownership_pct",
        df.columns[4]: "foreign_limit_shares",
        df.columns[5]: "limit_exhaustion_pct",
    })
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    df["market"] = market.upper()
    for col in ["shares_outstanding", "foreign_shares_held", "foreign_ownership_pct",
                "foreign_limit_shares", "limit_exhaustion_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _bucket_pct(pct: float) -> str:
    if pd.isna(pct):
        return "unknown"
    if pct >= 0.8:
        return "very_high"
    if pct >= 0.6:
        return "high"
    if pct >= 0.4:
        return "mid"
    if pct >= 0.2:
        return "low"
    return "very_low"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    sector_map = _load_sector_map(conn)

    frames = [_load_market(conn, m) for m in ("kospi", "kosdaq")]
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["shares_outstanding", "foreign_ownership_pct", "limit_exhaustion_pct"])
    df["snapshot_date"] = SNAPSHOT_DATE
    df["sector"] = df["ticker"].map(sector_map).fillna("unknown")

    df["foreign_ownership_pct_cross"] = df["foreign_ownership_pct"].rank(pct=True)
    df["limit_exhaustion_pct_cross"] = df["limit_exhaustion_pct"].rank(pct=True)
    df["foreign_room_score"] = (1 - df["limit_exhaustion_pct"] / 100.0).clip(0, 1)

    df["ownership_bucket"] = df["foreign_ownership_pct_cross"].apply(_bucket_pct)
    df["room_bucket"] = df["foreign_room_score"].apply(_bucket_pct)

    logger.info("구축 완료: %d행 (%d종목)", len(df), df["ticker"].nunique())
    return df[[
        "ticker", "snapshot_date", "sector", "market",
        "shares_outstanding", "foreign_shares_held", "foreign_limit_shares",
        "foreign_ownership_pct", "limit_exhaustion_pct",
        "foreign_ownership_pct_cross", "limit_exhaustion_pct_cross",
        "foreign_room_score", "ownership_bucket", "room_bucket",
    ]].sort_values("ticker")


CATALOG = [
    ("foreign_ownership_pct",       "외국인 지분율",          "%, 전체 상장주식 대비 외국인 보유 비중",                 "snapshot"),
    ("limit_exhaustion_pct",        "외국인 한도소진율",      "%, 외국인 투자한도 대비 소진 비율 (한도 없으면 지분율과 동일)", "snapshot"),
    ("foreign_ownership_pct_cross", "외국인 지분율 횡단면 백분위", "0~1, 전체 종목 중 상대 순위",                     "snapshot"),
    ("limit_exhaustion_pct_cross",  "한도소진율 횡단면 백분위",   "0~1, 전체 종목 중 상대 순위",                     "snapshot"),
    ("foreign_room_score",          "외국인 매수여력 점수",   "0~1, 1 - 한도소진율/100 (높을수록 추가 매수 여력 큼)",    "snapshot"),
    ("ownership_bucket",            "외국인 지분율 버킷",     "very_high > high > mid > low > very_low",            "snapshot"),
    ("room_bucket",                 "매수여력 버킷",          "very_high > high > mid > low > very_low (very_low=소진 임박)", "snapshot"),
]


def run():
    logger.info("foreign_exhaustion 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_foreign_exhaustion_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_foreign_exhaustion_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_foreign_exhaustion_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_foreign_exhaustion_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 외국인 지분율 버킷 분포 ===")
    print(df["ownership_bucket"].value_counts())
    print("\n=== 매수여력 버킷 분포 ===")
    print(df["room_bucket"].value_counts())
