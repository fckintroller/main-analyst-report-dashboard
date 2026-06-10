"""
애널리스트 컨센서스 목표주가 괴리율 팩터 생성.

주요 팩터:
  - tp_divergence       : (목표주가 - 현재주가) / 현재주가 (상승여력)
  - opinion_score       : 투자의견 점수 (1=매도, 5=강매수)
  - tp_divergence_sector_pct : 섹터 내 상승여력 백분위
  - target_price_score  : 0~1 종합 점수 (상승여력 + 투자의견 합성)
  - target_price_bucket : deep_value > cheap > neutral > rich > expensive

해석:
  - tp_divergence 높음 = 애널리스트 목표주가 대비 현재 주가 크게 할인 = 저평가
  - opinion_score 높음 = 애널리스트 다수 매수 추천

입력:
  - data/raw/valuation/analyst_target_price.csv
  - factor_forward_per_snapshot (DB) — 현재 종가, 섹터 정보

출력 CSV:
  - data/raw/factors/target_price_snapshot.csv
  - data/raw/factors/target_price_factor_catalog.csv

출력 SQLite:
  - factor_target_price_snapshot
  - factor_target_price_catalog
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
TP_PATH = PROJECT_ROOT / "data" / "raw" / "valuation" / "analyst_target_price.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"

SNAPSHOT_DATE = "2026-06-09"
MIN_SECTOR_N = 3   # 섹터 내 백분위 최소 종목 수


# ──────────────────────────────────────────────────────────────
# 1. 데이터 로드
# ──────────────────────────────────────────────────────────────
def load_price_and_sector(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT ticker, close_price, sector FROM factor_forward_per_snapshot",
        conn,
    )
    return df


def load_target_prices() -> pd.DataFrame:
    if not TP_PATH.exists():
        raise FileNotFoundError(f"목표주가 파일 없음: {TP_PATH}\n먼저 collect_analyst_target_price_once.py를 실행하세요.")
    df = pd.read_csv(TP_PATH, encoding="utf-8-sig")
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    return df


# ──────────────────────────────────────────────────────────────
# 2. 목표주가 괴리율 계산
# ──────────────────────────────────────────────────────────────
def compute_divergence(tp_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
    merged = price_df.merge(tp_df, on="ticker", how="inner")

    # 목표주가 괴리율: (목표주가 / 현재주가) - 1
    merged["tp_divergence"] = np.where(
        (merged["target_price"] > 0) & (merged["close_price"] > 0),
        merged["target_price"] / merged["close_price"] - 1,
        np.nan,
    )

    # 투자의견 점수 정규화 (1~5 → 0~1)
    merged["opinion_score_norm"] = np.where(
        merged["opinion_score"].notna(),
        (merged["opinion_score"] - 1) / 4,
        np.nan,
    )

    merged["snapshot_date"] = SNAPSHOT_DATE
    return merged


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

    # 괴리율 높을수록 저평가 → 높은 백분위가 좋음
    out["tp_divergence_sector_pct"] = out.groupby("sector")["tp_divergence"].transform(_pct_rank)
    out["tp_divergence_mkt_pct"] = out["tp_divergence"].rank(pct=True)

    return out


# ──────────────────────────────────────────────────────────────
# 4. 종합 점수
# ──────────────────────────────────────────────────────────────
def add_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    tp_component = out["tp_divergence_sector_pct"]  # 높을수록 저평가
    op_component = out["opinion_score_norm"]

    has_both = tp_component.notna() & op_component.notna()
    has_tp_only = tp_component.notna() & op_component.isna()
    has_op_only = tp_component.isna() & op_component.notna()

    score = pd.Series(np.nan, index=out.index)
    score[has_both] = tp_component[has_both] * 0.65 + op_component[has_both] * 0.35
    score[has_tp_only] = tp_component[has_tp_only]
    score[has_op_only] = op_component[has_op_only]
    out["target_price_score"] = score

    # 버킷: 괴리율 절대값 기준
    def _bucket(div):
        if pd.isna(div):
            return "no_coverage"
        if div >= 0.30:
            return "deep_value"   # 30% 이상 상승여력
        if div >= 0.15:
            return "cheap"        # 15~30%
        if div >= 0.00:
            return "neutral"      # 0~15%
        if div >= -0.10:
            return "rich"         # -10~0% (목표주가 소폭 하회)
        return "expensive"        # -10% 이상 하회

    out["target_price_bucket"] = out["tp_divergence"].map(_bucket)

    return out


# ──────────────────────────────────────────────────────────────
# 5. 카탈로그
# ──────────────────────────────────────────────────────────────
def build_catalog() -> pd.DataFrame:
    rows = [
        {
            "factor_family": "target_price",
            "question": "현재 주가가 애널리스트 목표주가 대비 얼마나 싼가?",
            "factor_name": "tp_divergence",
            "source_column": "target_price / close_price - 1",
            "interpretation": "양수 높을수록 상승여력 큼. 0.3+=deep_value, 0.15~0.3=cheap",
            "preferred_use": "밸류에이션 팩터와 함께 1차 스크리닝 필터",
        },
        {
            "factor_family": "target_price",
            "question": "애널리스트들의 투자의견이 우호적인가?",
            "factor_name": "opinion_score",
            "source_column": "Naver 투자의견 평균 점수 (1=매도, 5=강매수)",
            "interpretation": "4.0 이상 = 매수 우세, 3.0 이하 = 중립~매도 우세",
            "preferred_use": "강한 매수 컨센서스 필터",
        },
        {
            "factor_family": "target_price",
            "question": "섹터 내에서 상승여력이 높은 편인가?",
            "factor_name": "tp_divergence_sector_pct",
            "source_column": "tp_divergence",
            "interpretation": "0=섹터 내 가장 낮은 상승여력, 1=가장 높음",
            "preferred_use": "섹터 로테이션 및 종목 선별",
        },
        {
            "factor_family": "target_price",
            "question": "목표주가 + 투자의견 종합 점수는?",
            "factor_name": "target_price_score",
            "source_column": "tp_divergence_sector_pct × 0.65 + opinion_score_norm × 0.35",
            "interpretation": "0~1, 높을수록 애널리스트 관점 저평가·매력",
            "preferred_use": "전체 팩터 결합 시 밸류에이션 보조 신호",
        },
    ]
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────
def run() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_name(f"quant_data_{ts}_before_target_price_factors.sqlite")
    shutil.copy2(DB_PATH, backup)
    print(f"DB 백업: {backup.name}")

    tp_df = load_target_prices()
    print(f"목표주가 로드: {len(tp_df)}종목 (목표주가 있음: {tp_df['target_price'].notna().sum()})")

    with sqlite3.connect(DB_PATH) as conn:
        price_df = load_price_and_sector(conn)

    df = compute_divergence(tp_df, price_df)
    df = add_sector_percentiles(df)
    df = add_score(df)

    valid_tp = df["tp_divergence"].notna().sum()
    print(f"괴리율 산출: {valid_tp}종목 / {len(df)}종목 전체")
    print(f"괴리율 분포: {df['tp_divergence'].describe().round(3).to_dict()}")
    print(f"버킷 분포:\n{df['target_price_bucket'].value_counts().to_string()}")

    if valid_tp > 0:
        top5 = df.nlargest(5, "tp_divergence")[["ticker", "sector", "tp_divergence", "opinion_score", "target_price_bucket"]]
        print(f"\n상승여력 상위 5종목:\n{top5.to_string(index=False)}")

    catalog = build_catalog()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "target_price_snapshot.csv", index=False, encoding="utf-8-sig")
    catalog.to_csv(OUTPUT_DIR / "target_price_factor_catalog.csv", index=False, encoding="utf-8-sig")

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("factor_target_price_snapshot", conn, if_exists="replace", index=False)
        catalog.to_sql("factor_target_price_catalog", conn, if_exists="replace", index=False)
        conn.commit()

    print(f"\n완료: factor_target_price_snapshot {len(df)}행, factor_target_price_catalog {len(catalog)}행")


if __name__ == "__main__":
    run()
