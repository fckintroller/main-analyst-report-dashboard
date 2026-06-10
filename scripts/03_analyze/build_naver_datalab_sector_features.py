"""
NAVER DataLab 섹터 관심도 모델링 전 1차 가공 레이어.

목적:
1. 같은 섹터 안에서 관심도가 최근 강해졌는가?
2. 시장 전체 검색 관심도 대비 특정 섹터가 강한가?
3. 전체 섹터 중 현재 관심도 순위가 높은가?

입력:
- data/raw/sentiment/naver_datalab/naver_datalab_sector_interest_factor_month.csv

출력:
- naver_datalab_sector_interest_features_month.csv
- naver_datalab_sector_interest_factor_catalog.csv
- naver_datalab_sector_interest_classified_month.csv
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "sentiment" / "naver_datalab"
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
FACTOR_INPUT = RAW_DIR / "naver_datalab_sector_interest_factor_month.csv"
FEATURES_OUTPUT = RAW_DIR / "naver_datalab_sector_interest_features_month.csv"
CATALOG_OUTPUT = RAW_DIR / "naver_datalab_sector_interest_factor_catalog.csv"
CLASSIFIED_OUTPUT = RAW_DIR / "naver_datalab_sector_interest_classified_month.csv"

FEATURES_TABLE = "sentiment_naver_datalab_sector_interest_month_features"
CATALOG_TABLE = "sentiment_naver_datalab_sector_interest_factor_catalog"
CLASSIFIED_TABLE = "sentiment_naver_datalab_sector_interest_month_classified"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _rolling_zscore(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    min_periods = min_periods or max(3, min(window, 6))
    mean = series.rolling(window, min_periods=min_periods).mean()
    std = series.rolling(window, min_periods=min_periods).std()
    return (series - mean) / std.replace(0, pd.NA)


def _bucket_recent(row: pd.Series) -> str:
    z = row.get("anchor_relative_zscore_12m")
    mom = row.get("anchor_relative_momentum_3m")
    if pd.isna(z) or pd.isna(mom):
        return "insufficient_history"
    if z >= 1.0 and mom > 0:
        return "strong"
    if z <= -1.0 and mom < 0:
        return "weakening"
    if z < 0 and mom > 0:
        return "recovering"
    if z > 0 and mom < 0:
        return "cooling"
    return "neutral"


def _bucket_market(row: pd.Series) -> str:
    z = row.get("anchor_relative_zscore_12m")
    val = row.get("anchor_relative_ratio_winsorized")
    if pd.isna(z) or pd.isna(val):
        return "insufficient_history"
    if z >= 1.0 and val >= 100:
        return "strong"
    if z <= -1.0 or val < 75:
        return "weak"
    return "neutral"


def _bucket_rank(rank_pct: float) -> str:
    if pd.isna(rank_pct):
        return "insufficient_peers"
    if rank_pct >= 0.8:
        return "top"
    if rank_pct <= 0.2:
        return "bottom"
    return "middle"


def build_features(factor_df: pd.DataFrame) -> pd.DataFrame:
    required = {"period", "group_name", "keywords", "chunk_id", "ratio", "anchor_ratio", "anchor_relative_ratio"}
    missing = required - set(factor_df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    df = factor_df.copy()
    df["period"] = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
    for col in ["ratio", "anchor_ratio", "anchor_relative_ratio"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values(["group_name", "period"]).reset_index(drop=True)

    df["low_anchor_flag"] = df["anchor_ratio"] < 5
    df["saturation_flag"] = df["ratio"] >= 99.5
    df["anchor_saturation_flag"] = df["anchor_ratio"] >= 99.5
    df["zero_ratio_flag"] = df["ratio"] <= 0
    df["missing_flag"] = df[["ratio", "anchor_ratio", "anchor_relative_ratio"]].isna().any(axis=1)
    df["data_quality_score"] = 100
    df.loc[df["low_anchor_flag"], "data_quality_score"] -= 30
    df.loc[df["saturation_flag"], "data_quality_score"] -= 10
    df.loc[df["anchor_saturation_flag"], "data_quality_score"] -= 10
    df.loc[df["zero_ratio_flag"], "data_quality_score"] -= 10
    df.loc[df["missing_flag"], "data_quality_score"] -= 50
    df["data_quality_score"] = df["data_quality_score"].clip(lower=0)

    low = df["anchor_relative_ratio"].quantile(0.01)
    high = df["anchor_relative_ratio"].quantile(0.99)
    df["anchor_relative_ratio_winsorized"] = df["anchor_relative_ratio"].clip(lower=low, upper=high)

    grouped = df.groupby("group_name", group_keys=False)
    df["ratio_momentum_1m"] = grouped["ratio"].diff(1)
    df["ratio_momentum_3m"] = grouped["ratio"].diff(3)
    df["ratio_momentum_6m"] = grouped["ratio"].diff(6)
    df["ratio_zscore_12m"] = grouped["ratio"].transform(lambda s: _rolling_zscore(s, 12, 6))
    df["ratio_zscore_24m"] = grouped["ratio"].transform(lambda s: _rolling_zscore(s, 24, 8))
    df["anchor_relative_momentum_1m"] = grouped["anchor_relative_ratio_winsorized"].diff(1)
    df["anchor_relative_momentum_3m"] = grouped["anchor_relative_ratio_winsorized"].diff(3)
    df["anchor_relative_momentum_6m"] = grouped["anchor_relative_ratio_winsorized"].diff(6)
    df["anchor_relative_zscore_12m"] = grouped["anchor_relative_ratio_winsorized"].transform(lambda s: _rolling_zscore(s, 12, 6))
    df["anchor_relative_zscore_24m"] = grouped["anchor_relative_ratio_winsorized"].transform(lambda s: _rolling_zscore(s, 24, 8))

    # 같은 월 전체 섹터 내 순위: anchor 보정값 중심으로 rank를 만든다.
    df["relative_rank"] = df.groupby("period")["anchor_relative_ratio_winsorized"].rank(method="average", ascending=True)
    df["relative_rank_pct"] = df.groupby("period")["anchor_relative_ratio_winsorized"].rank(pct=True, ascending=True)
    cs_mean = df.groupby("period")["anchor_relative_ratio_winsorized"].transform("mean")
    cs_std = df.groupby("period")["anchor_relative_ratio_winsorized"].transform("std")
    df["relative_zscore_cross_sectional"] = (df["anchor_relative_ratio_winsorized"] - cs_mean) / cs_std.replace(0, pd.NA)
    df["top_20pct_flag"] = df["relative_rank_pct"] >= 0.8
    df["bottom_20pct_flag"] = df["relative_rank_pct"] <= 0.2

    # 사용자가 요청한 3개 질문에 대응하는 후보 score와 분류명.
    df["factor_family_recent_strength"] = "same_sector_recent_strength"
    df["factor_family_market_relative"] = "market_relative_strength"
    df["factor_family_cross_sector"] = "cross_sector_current_rank"
    z12 = pd.to_numeric(df["anchor_relative_zscore_12m"], errors="coerce")
    mom3 = pd.to_numeric(df["anchor_relative_momentum_3m"], errors="coerce")
    df["recent_strength_score"] = z12.fillna(0.0) + (mom3.fillna(0.0) / 100)
    df["market_relative_score"] = z12.fillna(0.0)
    df["cross_sector_rank_score"] = df["relative_rank_pct"]
    df["recent_strength_bucket"] = df.apply(_bucket_recent, axis=1)
    df["market_relative_bucket"] = df.apply(_bucket_market, axis=1)
    df["cross_sector_rank_bucket"] = df["relative_rank_pct"].apply(_bucket_rank)

    cols = [
        "period", "group_name", "keywords", "chunk_id",
        "ratio", "anchor_ratio", "anchor_relative_ratio", "anchor_relative_ratio_winsorized",
        "low_anchor_flag", "saturation_flag", "anchor_saturation_flag", "zero_ratio_flag", "missing_flag", "data_quality_score",
        "ratio_momentum_1m", "ratio_momentum_3m", "ratio_momentum_6m", "ratio_zscore_12m", "ratio_zscore_24m",
        "anchor_relative_momentum_1m", "anchor_relative_momentum_3m", "anchor_relative_momentum_6m",
        "anchor_relative_zscore_12m", "anchor_relative_zscore_24m",
        "relative_rank", "relative_rank_pct", "relative_zscore_cross_sectional", "top_20pct_flag", "bottom_20pct_flag",
        "factor_family_recent_strength", "recent_strength_score", "recent_strength_bucket",
        "factor_family_market_relative", "market_relative_score", "market_relative_bucket",
        "factor_family_cross_sector", "cross_sector_rank_score", "cross_sector_rank_bucket",
    ]
    return df[cols]


def build_factor_catalog() -> pd.DataFrame:
    rows = [
        {
            "factor_family": "same_sector_recent_strength",
            "question": "같은 섹터 안에서 관심도가 최근 강해졌는가?",
            "factor_name": "ratio_momentum_1m",
            "source_column": "ratio",
            "interpretation": "전월 대비 같은 섹터 원본 상대 관심도 변화",
            "preferred_use": "보조",
        },
        {
            "factor_family": "same_sector_recent_strength",
            "question": "같은 섹터 안에서 관심도가 최근 강해졌는가?",
            "factor_name": "ratio_momentum_3m",
            "source_column": "ratio",
            "interpretation": "3개월 전 대비 같은 섹터 원본 상대 관심도 변화",
            "preferred_use": "핵심",
        },
        {
            "factor_family": "same_sector_recent_strength",
            "question": "같은 섹터 안에서 관심도가 최근 강해졌는가?",
            "factor_name": "ratio_zscore_12m",
            "source_column": "ratio",
            "interpretation": "최근 12개월 대비 같은 섹터 관심도 위치",
            "preferred_use": "핵심",
        },
        {
            "factor_family": "market_relative_strength",
            "question": "시장 전체 검색 관심도 대비 특정 섹터가 강한가?",
            "factor_name": "anchor_relative_ratio_winsorized",
            "source_column": "anchor_relative_ratio",
            "interpretation": "market_anchor 대비 섹터 상대 관심도(이상치 완화)",
            "preferred_use": "핵심",
        },
        {
            "factor_family": "market_relative_strength",
            "question": "시장 전체 검색 관심도 대비 특정 섹터가 강한가?",
            "factor_name": "anchor_relative_momentum_3m",
            "source_column": "anchor_relative_ratio_winsorized",
            "interpretation": "시장 anchor 대비 상대 관심도의 3개월 변화",
            "preferred_use": "핵심",
        },
        {
            "factor_family": "market_relative_strength",
            "question": "시장 전체 검색 관심도 대비 특정 섹터가 강한가?",
            "factor_name": "anchor_relative_zscore_12m",
            "source_column": "anchor_relative_ratio_winsorized",
            "interpretation": "시장 anchor 대비 상대 관심도의 12개월 z-score",
            "preferred_use": "핵심",
        },
        {
            "factor_family": "cross_sector_current_rank",
            "question": "전체 섹터 중 현재 관심도 순위가 높은가?",
            "factor_name": "relative_rank_pct",
            "source_column": "anchor_relative_ratio_winsorized",
            "interpretation": "동일 월 전체 섹터 중 anchor 보정 관심도 백분위 순위",
            "preferred_use": "핵심",
        },
        {
            "factor_family": "cross_sector_current_rank",
            "question": "전체 섹터 중 현재 관심도 순위가 높은가?",
            "factor_name": "relative_zscore_cross_sectional",
            "source_column": "anchor_relative_ratio_winsorized",
            "interpretation": "동일 월 전체 섹터 분포 내 표준화 위치",
            "preferred_use": "보조",
        },
        {
            "factor_family": "cross_sector_current_rank",
            "question": "전체 섹터 중 현재 관심도 순위가 높은가?",
            "factor_name": "top_20pct_flag",
            "source_column": "relative_rank_pct",
            "interpretation": "동일 월 관심도 상위 20% 섹터 여부",
            "preferred_use": "해석",
        },
    ]
    return pd.DataFrame(rows)


def build_classified_long(features: pd.DataFrame) -> pd.DataFrame:
    mappings = [
        ("same_sector_recent_strength", "recent_strength_score", "recent_strength_bucket"),
        ("market_relative_strength", "market_relative_score", "market_relative_bucket"),
        ("cross_sector_current_rank", "cross_sector_rank_score", "cross_sector_rank_bucket"),
    ]
    rows = []
    for _, row in features.iterrows():
        for family, score_col, bucket_col in mappings:
            rows.append({
                "period": row["period"],
                "group_name": row["group_name"],
                "keywords": row.get("keywords", ""),
                "factor_family": family,
                "signal_score": row.get(score_col),
                "signal_bucket": row.get(bucket_col),
                "data_quality_score": row.get("data_quality_score"),
            })
    return pd.DataFrame(rows)


def save_outputs(features: pd.DataFrame, catalog: pd.DataFrame, classified: pd.DataFrame, db_path: Path = DB_PATH) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    features.to_csv(FEATURES_OUTPUT, index=False, encoding="utf-8-sig")
    catalog.to_csv(CATALOG_OUTPUT, index=False, encoding="utf-8-sig")
    classified.to_csv(CLASSIFIED_OUTPUT, index=False, encoding="utf-8-sig")
    conn = sqlite3.connect(db_path)
    features.to_sql(FEATURES_TABLE, conn, if_exists="replace", index=False)
    catalog.to_sql(CATALOG_TABLE, conn, if_exists="replace", index=False)
    classified.to_sql(CLASSIFIED_TABLE, conn, if_exists="replace", index=False)
    conn.close()


def run(input_path: Path = FACTOR_INPUT, db_path: Path = DB_PATH) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    factor_df = pd.read_csv(input_path)
    features = build_features(factor_df)
    catalog = build_factor_catalog()
    classified = build_classified_long(features)
    save_outputs(features, catalog, classified, db_path)
    logger.info("features saved: %s (%d rows)", FEATURES_OUTPUT, len(features))
    logger.info("catalog saved: %s (%d rows)", CATALOG_OUTPUT, len(catalog))
    logger.info("classified saved: %s (%d rows)", CLASSIFIED_OUTPUT, len(classified))
    return features, catalog, classified


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build NAVER DataLab sector interest preprocessing features.")
    parser.add_argument("--input", default=str(FACTOR_INPUT))
    parser.add_argument("--db-path", default=str(DB_PATH))
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    run(Path(args.input), Path(args.db_path))
