"""
PEG (Price/Earnings-to-Growth) 밸류에이션 팩터 생성.

PEG = forward_per / (eps_growth_expected × 100)

해석:
  PEG < 0.5  : 성장 대비 매우 저평가
  PEG 0.5~1.0: 성장 대비 합리적 (저평가~적정)
  PEG 1.0~2.0: 성장 대비 약간 비쌈
  PEG > 2.0  : 성장 대비 과대평가

조건:
  - eps_growth_expected > 0 (이익 역성장 종목은 PEG 무의미 → NaN)
  - forward_per > 0

입력:
  - factor_forward_per_snapshot (DB) — forward_per, eps_growth_expected, sector

출력 CSV:
  - data/raw/factors/peg_snapshot.csv
  - data/raw/factors/peg_factor_catalog.csv

출력 SQLite:
  - factor_peg_snapshot
  - factor_peg_catalog
"""

from __future__ import annotations

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"

SNAPSHOT_DATE = "2026-06-05"
MIN_SECTOR_N = 3  # 섹터 내 PEG 백분위 산출 최소 종목 수

PEG_THRESHOLDS = {
    "deep_value": 0.5,
    "cheap": 1.0,
    "neutral": 1.5,
    "rich": 2.0,
}


# ──────────────────────────────────────────────────────────────
# 1. 데이터 로드
# ──────────────────────────────────────────────────────────────
def load_forward_per(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT ticker, snapshot_date, sector,
               forward_per, eps_growth_expected, forward_valuation_score,
               close_price, forward_eps
        FROM factor_forward_per_snapshot
        """,
        conn,
    )
    return df


# ──────────────────────────────────────────────────────────────
# 2. PEG 계산
# ──────────────────────────────────────────────────────────────
def compute_peg(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # eps_growth_expected: 소수점 형태 (0.5 = +50%)
    # PEG 표준 공식: PER / 성장률(%) = forward_per / (eps_growth_expected * 100)
    growth_pct = out["eps_growth_expected"] * 100

    out["peg_ratio"] = np.where(
        (out["forward_per"] > 0) & (growth_pct > 0),
        out["forward_per"] / growth_pct,
        np.nan,
    )

    # 극단값 클리핑: PEG > 10은 분석 의미 없음 (초고PEG)
    out["peg_ratio"] = out["peg_ratio"].clip(upper=10.0)

    return out


# ──────────────────────────────────────────────────────────────
# 3. 섹터 내 백분위
# ──────────────────────────────────────────────────────────────
def add_sector_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    def _pct_rank(group: pd.Series) -> pd.Series:
        valid = group.dropna()
        if len(valid) < MIN_SECTOR_N:
            return pd.Series(np.nan, index=group.index)
        return group.rank(pct=True, na_option="keep")

    out["peg_sector_pct"] = out.groupby("sector")["peg_ratio"].transform(_pct_rank)

    # 전 시장 백분위 (참고용)
    valid_mask = out["peg_ratio"].notna()
    out.loc[valid_mask, "peg_mkt_pct"] = out.loc[valid_mask, "peg_ratio"].rank(pct=True)
    out["peg_mkt_pct"] = out["peg_mkt_pct"].where(valid_mask)

    return out


# ──────────────────────────────────────────────────────────────
# 4. PEG 종합 점수
# ──────────────────────────────────────────────────────────────
def add_peg_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # PEG가 낮을수록 좋음 → 섹터 백분위 반전
    peg_component = 1.0 - out["peg_sector_pct"]  # 낮은 PEG = 높은 점수

    # forward valuation score 와 결합 (각 0.5 가중)
    # forward_valuation_score가 있으면 결합, 없으면 peg_component만 사용
    fwd_score = out["forward_valuation_score"]
    has_both = peg_component.notna() & fwd_score.notna()
    has_peg_only = peg_component.notna() & fwd_score.isna()
    has_fwd_only = peg_component.isna() & fwd_score.notna()

    score = pd.Series(np.nan, index=out.index)
    score[has_both] = peg_component[has_both] * 0.5 + fwd_score[has_both] * 0.5
    score[has_peg_only] = peg_component[has_peg_only]
    score[has_fwd_only] = fwd_score[has_fwd_only]
    out["peg_composite_score"] = score

    # 버킷: PEG 절대값 기준
    def _bucket(peg):
        if pd.isna(peg):
            return "no_coverage"  # 이익 역성장 또는 커버리지 없음
        if peg < PEG_THRESHOLDS["deep_value"]:
            return "deep_value"
        if peg < PEG_THRESHOLDS["cheap"]:
            return "cheap"
        if peg < PEG_THRESHOLDS["neutral"]:
            return "neutral"
        if peg < PEG_THRESHOLDS["rich"]:
            return "rich"
        return "expensive"

    out["peg_bucket"] = out["peg_ratio"].map(_bucket)

    return out


# ──────────────────────────────────────────────────────────────
# 5. 카탈로그
# ──────────────────────────────────────────────────────────────
def build_catalog() -> pd.DataFrame:
    rows = [
        {
            "factor_family": "peg",
            "question": "이 종목의 PER은 예상 이익 성장률에 비해 비싼가?",
            "factor_name": "peg_ratio",
            "source_column": "forward_per / (eps_growth_expected × 100)",
            "interpretation": "낮을수록 성장 대비 저평가. 1.0 이하=합리적, 0.5 이하=매력적",
            "preferred_use": "성장주 밸류에이션 필터; 이익 역성장 종목 제외",
        },
        {
            "factor_family": "peg",
            "question": "섹터 내에서 PEG가 낮은 편인가?",
            "factor_name": "peg_sector_pct",
            "source_column": "peg_ratio",
            "interpretation": "0=섹터 내 가장 저PEG(매력적), 1=가장 고PEG(비쌈)",
            "preferred_use": "섹터 로테이션 및 종목 선별 필터",
        },
        {
            "factor_family": "peg",
            "question": "PEG와 선행PER을 종합하면 종합 점수는?",
            "factor_name": "peg_composite_score",
            "source_column": "peg_sector_pct + forward_valuation_score",
            "interpretation": "0~1, 높을수록 성장+밸류 모두 매력적",
            "preferred_use": "1차 스크리닝 점수로 활용",
        },
        {
            "factor_family": "peg",
            "question": "PEG 절대값 기준 어느 구간인가?",
            "factor_name": "peg_bucket",
            "source_column": "peg_ratio",
            "interpretation": "deep_value(<0.5) > cheap(<1) > neutral(<1.5) > rich(<2) > expensive",
            "preferred_use": "직관적 분류 레이블로 활용",
        },
    ]
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────
# 6. DB 저장
# ──────────────────────────────────────────────────────────────
def save_to_db(df: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> None:
    df.to_sql("factor_peg_snapshot", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_peg_catalog", conn, if_exists="replace", index=False)
    conn.commit()


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────
def run() -> None:
    # DB 백업
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_name(f"quant_data_{ts}_before_peg_factors.sqlite")
    shutil.copy2(DB_PATH, backup)
    print(f"DB 백업: {backup.name}")

    with sqlite3.connect(DB_PATH) as conn:
        raw = load_forward_per(conn)

    print(f"forward_per 로드: {len(raw)}행")

    df = compute_peg(raw)
    df = add_sector_percentiles(df)
    df = add_peg_score(df)

    valid_peg = df["peg_ratio"].notna().sum()
    print(f"PEG 산출 가능: {valid_peg}종목 / {len(df)}종목 전체")
    print(f"PEG 분포: {df['peg_ratio'].describe().round(2).to_dict()}")
    print(f"버킷 분포:\n{df['peg_bucket'].value_counts().to_string()}")

    catalog = build_catalog()

    # CSV 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "peg_snapshot.csv", index=False, encoding="utf-8-sig")
    catalog.to_csv(OUTPUT_DIR / "peg_factor_catalog.csv", index=False, encoding="utf-8-sig")

    # DB 저장
    with sqlite3.connect(DB_PATH) as conn:
        save_to_db(df, catalog, conn)

    print(f"\n완료: factor_peg_snapshot {len(df)}행, factor_peg_catalog {len(catalog)}행 DB 적재")


if __name__ == "__main__":
    run()
