"""
밸류에이션 복합 팩터 (Value Composite) 구축.

소스:
  - factor_valuation_per_pbr_month  (PER/PBR 섹터 백분위 + valuation_score)
  - factor_forward_per_snapshot     (선행PER + forward_valuation_score)
  - factor_peg_snapshot             (PEG + peg_composite_score)

출력 DB 테이블:
  - factor_value_composite_snapshot  : 종목별 스냅샷
  - factor_value_composite_catalog   : 팩터 메타데이터
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 가중치 — 가용 소스에 따라 동적 재조정
W_VALUATION = 0.35   # trailing PER/PBR
W_FORWARD   = 0.40   # forward PER
W_PEG       = 0.25   # PEG


def _load_valuation(conn: sqlite3.Connection) -> pd.DataFrame:
    latest = conn.execute(
        "SELECT MAX(period) FROM factor_valuation_per_pbr_month"
    ).fetchone()[0]
    df = pd.read_sql(
        "SELECT ticker, sector, valuation_score, per_percentile_sector, pbr_percentile_sector "
        f"FROM factor_valuation_per_pbr_month WHERE period = '{latest}'",
        conn,
    )
    df["snapshot_date"] = latest
    return df


def _load_forward(conn: sqlite3.Connection) -> pd.DataFrame:
    latest = conn.execute(
        "SELECT MAX(snapshot_date) FROM factor_forward_per_snapshot"
    ).fetchone()[0]
    return pd.read_sql(
        "SELECT ticker, forward_valuation_score, forward_per, forward_per_sector_pct "
        f"FROM factor_forward_per_snapshot WHERE snapshot_date = '{latest}'",
        conn,
    )


def _load_peg(conn: sqlite3.Connection) -> pd.DataFrame:
    latest = conn.execute(
        "SELECT MAX(snapshot_date) FROM factor_peg_snapshot"
    ).fetchone()[0]
    return pd.read_sql(
        "SELECT ticker, peg_composite_score, peg_ratio "
        f"FROM factor_peg_snapshot WHERE snapshot_date = '{latest}'",
        conn,
    )


def _trailing_score(row: pd.Series) -> float:
    """per/pbr 섹터 백분위에서 0-1 trailing value score 재계산.
    per_pct_inv = 1 - per_percentile_sector (낮은 PER = 높은 점수)
    """
    per_pct = row.get("per_percentile_sector")
    pbr_pct = row.get("pbr_percentile_sector")
    valid = []
    if pd.notna(per_pct):
        valid.append(1.0 - float(per_pct))
    if pd.notna(pbr_pct):
        valid.append(1.0 - float(pbr_pct))
    return np.mean(valid) if valid else np.nan


def _compute_composite(row: pd.Series) -> float:
    """가용한 소스의 가중치를 재조정해 합산. 모든 소스는 0-1 범위."""
    scores, weights = [], []

    tv = _trailing_score(row)
    if pd.notna(tv):
        scores.append(tv)
        weights.append(W_VALUATION)

    if pd.notna(row.get("forward_valuation_score")):
        scores.append(np.clip(float(row["forward_valuation_score"]), 0, 1))
        weights.append(W_FORWARD)

    if pd.notna(row.get("peg_composite_score")):
        scores.append(np.clip(float(row["peg_composite_score"]), 0, 1))
        weights.append(W_PEG)

    if not scores:
        return np.nan

    total_w = sum(weights)
    return sum(s * w for s, w in zip(scores, weights)) / total_w


def _bucket(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= 0.75:
        return "deep_value"
    if score >= 0.6:
        return "value"
    if score >= 0.4:
        return "neutral"
    if score >= 0.25:
        return "growth"
    return "expensive"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    val_df  = _load_valuation(conn)
    fwd_df  = _load_forward(conn)
    peg_df  = _load_peg(conn)

    df = val_df.merge(fwd_df, on="ticker", how="left") \
               .merge(peg_df, on="ticker", how="left")

    df["value_composite_score"] = df.apply(_compute_composite, axis=1)

    # 소스 플래그 (진단용)
    df["has_forward"] = df["forward_valuation_score"].notna().astype(int)
    df["has_peg"]     = df["peg_composite_score"].notna().astype(int)

    # 섹터 내 백분위
    df["value_composite_sector_pct"] = df.groupby("sector")["value_composite_score"].rank(pct=True)

    df["value_bucket"] = df["value_composite_score"].apply(_bucket)

    MIN_SECTOR_N = 5
    sector_counts = df.groupby("sector")["value_composite_score"].count()
    small_sectors = sector_counts[sector_counts < MIN_SECTOR_N].index
    df.loc[df["sector"].isin(small_sectors), "value_composite_sector_pct"] = np.nan

    return df[[
        "ticker", "snapshot_date", "sector",
        "valuation_score", "forward_valuation_score", "peg_composite_score",
        "value_composite_score", "value_composite_sector_pct",
        "has_forward", "has_peg",
        "per_percentile_sector", "pbr_percentile_sector",
        "forward_per", "peg_ratio",
        "value_bucket",
    ]]


CATALOG = [
    ("value_composite_score",         "밸류에이션 복합 점수",     "0~1, 1에 가까울수록 저평가", "snapshot"),
    ("value_composite_sector_pct",    "섹터 내 복합 밸류 백분위", "0~1",                          "snapshot"),
    ("value_bucket",                  "밸류에이션 버킷",          "deep_value/value/neutral/growth/expensive", "snapshot"),
    ("has_forward",                   "선행PER 가용 여부",         "0/1",                          "snapshot"),
    ("has_peg",                       "PEG 가용 여부",             "0/1",                          "snapshot"),
]


def run():
    logger.info("value_composite 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_value_composite_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_value_composite_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_value_composite_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_value_composite_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df[["ticker", "sector", "value_composite_score", "value_bucket"]].sort_values(
        "value_composite_score", ascending=False).head(20).to_string())
