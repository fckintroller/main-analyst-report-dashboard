"""
배당수익률 팩터 구축.

소스: stock_market_snapshot_{kospi,kosdaq}_fundamental_by_ticker_{snapshot_date}
  컬럼(위치 기준): [0]=티커, [1]=BPS, [2]=PER, [3]=PBR, [4]=EPS, [5]=DIV(배당수익률 %), [6]=DPS(주당배당금)

⚠️ 단일 시점 스냅샷 (KRX pykrx 펀더멘털 일괄 조회) → 시계열 백테스트 불가, 횡단면 스크리닝 전용.
   DIV=0인 종목은 무배당(또는 데이터 없음)으로 처리하며 백분위 산출에서 제외.

출력 컬럼:
  market               : KOSPI/KOSDAQ
  bps, per, pbr, eps   : 펀더멘털 참고값 (그대로)
  div_yield_pct        : 배당수익률(%) = DIV
  dps                  : 주당 배당금(원)
  has_dividend_flag    : DIV > 0 이면 1, 아니면 0
  div_yield_score      : 0~1, 배당 지급 종목(DIV>0) 중 배당수익률 백분위
  div_yield_sector_pct : 섹터 내 배당수익률 백분위 (섹터 내 배당지급 종목 수 < MIN_SECTOR_N 이면 NaN)
  dividend_bucket      : no_dividend / very_low / low / mid / high / very_high

출력 DB 테이블:
  factor_dividend_yield_snapshot
  factor_dividend_yield_catalog
"""
import logging
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

MIN_SECTOR_N = 5

TABLE_RE = re.compile(r"^stock_market_snapshot_(kospi|kosdaq)_fundamental_by_ticker_(\d{8})$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_fundamental_tables(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """(market, snapshot_date, table_name) 목록 반환."""
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    out = []
    for (name,) in rows:
        m = TABLE_RE.match(name)
        if m:
            out.append((m.group(1).upper(), f"{m.group(2)[:4]}-{m.group(2)[4:6]}-{m.group(2)[6:]}", name))
    return out


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


def _bucket_dividend(score: float, has_dividend: int) -> str:
    if not has_dividend:
        return "no_dividend"
    if pd.isna(score):
        return "unknown"
    if score >= 0.8:
        return "very_high"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "mid"
    if score >= 0.2:
        return "low"
    return "very_low"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    tables = _load_fundamental_tables(conn)
    if not tables:
        logger.error("펀더멘털 스냅샷 테이블 없음")
        return pd.DataFrame()

    sector_map = _load_sector_map(conn)

    frames = []
    for market, snapshot_date, tbl in tables:
        df = pd.read_sql(f"SELECT * FROM [{tbl}]", conn)
        df.columns = ["ticker", "bps", "per", "pbr", "eps", "div_yield_pct", "dps"]
        df["ticker"] = df["ticker"].astype(str).str.zfill(6)
        df["market"] = market
        df["snapshot_date"] = snapshot_date
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    for col in ("bps", "per", "pbr", "eps", "div_yield_pct", "dps"):
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["sector"] = out["ticker"].map(sector_map).fillna("unknown")
    out["has_dividend_flag"] = (out["div_yield_pct"] > 0).astype(int)

    payers = out["div_yield_pct"].where(out["has_dividend_flag"] == 1)
    out["div_yield_score"] = payers.rank(pct=True)

    def _sector_pct(group: pd.DataFrame) -> pd.Series:
        payer_yield = group["div_yield_pct"].where(group["has_dividend_flag"] == 1)
        if payer_yield.notna().sum() < MIN_SECTOR_N:
            return pd.Series(np.nan, index=group.index)
        return payer_yield.rank(pct=True)

    out["div_yield_sector_pct"] = out.groupby("sector", group_keys=False).apply(
        _sector_pct, include_groups=False
    )

    out["dividend_bucket"] = [
        _bucket_dividend(s, h) for s, h in zip(out["div_yield_score"], out["has_dividend_flag"])
    ]

    logger.info("구축 완료: %d행 (배당지급 %d종목)", len(out), int(out["has_dividend_flag"].sum()))
    return out[[
        "ticker", "snapshot_date", "sector", "market",
        "bps", "per", "pbr", "eps", "div_yield_pct", "dps",
        "has_dividend_flag", "div_yield_score", "div_yield_sector_pct", "dividend_bucket",
    ]].sort_values(["ticker"])


CATALOG = [
    ("div_yield_pct",        "배당수익률 (%)",        "KRX pykrx 펀더멘털 DIV, 0이면 무배당/데이터없음", "snapshot"),
    ("dps",                  "주당 배당금 (원)",      "DPS",                                              "snapshot"),
    ("has_dividend_flag",    "배당 지급 여부",        "DIV > 0 이면 1, 아니면 0",                          "snapshot"),
    ("div_yield_score",      "배당수익률 백분위",     "0~1, 배당지급 종목 중 상대 순위 (높을수록 고배당)", "snapshot"),
    ("div_yield_sector_pct", "섹터 내 배당수익률 백분위", "섹터 내 배당지급 종목 < 5개면 NaN",              "snapshot"),
    ("dividend_bucket",      "배당 버킷",             "no_dividend / very_low~very_high (5단계)",         "snapshot"),
    ("per / pbr / bps / eps","펀더멘털 참고값",       "KRX pykrx 스냅샷 그대로 (밸류에이션 교차검증용)",   "snapshot"),
]


def run():
    logger.info("dividend_yield 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_dividend_yield_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_dividend_yield_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_dividend_yield_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_dividend_yield_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 배당 버킷 분포 ===")
    print(df["dividend_bucket"].value_counts())
    print("\n=== 고배당 상위 10 ===")
    print(df.nlargest(10, "div_yield_pct")[["ticker", "sector", "market", "div_yield_pct", "dps", "dividend_bucket"]].to_string(index=False))
