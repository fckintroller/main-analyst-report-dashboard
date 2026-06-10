"""
공매도 잔고 팩터 생성.

주요 팩터:
  - balance_ratio         : 공매도 잔고율 (잔고/상장주식수, %)
  - balance_ratio_1m_chg  : 전월 대비 잔고율 변화
  - balance_ratio_3m_chg  : 3개월 전 대비 잔고율 변화
  - balance_ratio_zscore_own_6m : 자기 과거 6개월 z-score
  - balance_ratio_pct_cross : 전 시장 대비 잔고율 백분위
  - shorting_pressure_score : 0~1 종합 (높을수록 공매도 압박 강함 = 주의)
  - short_squeeze_flag      : 잔고율 급감 + 가격 상승 동시 = 쇼트 스퀴즈 후보

해석:
  - shorting_pressure 높음 → 기관/외인 약세 베팅 집중 → 상승 시 쇼트 커버 가속
  - 잔고율 급감 구간 탐지 = 쇼트 스퀴즈 진입 초기 신호

입력:
  - data/raw/factors/shorting_balance_monthly.csv
  - data/raw/stock_detail/sector_map.csv (섹터 매핑)
  - factor_stock_price_momentum_month (DB) — 가격 모멘텀 참조

출력 CSV:
  - data/raw/factors/shorting_factors_month.csv
  - data/raw/factors/shorting_factor_catalog.csv

출력 SQLite:
  - factor_shorting_month
  - factor_shorting_catalog
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
SHORTING_PATH = PROJECT_ROOT / "data" / "raw" / "factors" / "shorting_balance_monthly.csv"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"

MIN_HISTORY = 3        # z-score 계산 최소 월수
MIN_SECTOR_N = 5       # 섹터 백분위 최소 종목 수
ZSCORE_WINDOW = 6      # 자기 과거 z-score 윈도우 (월)
SQUEEZE_DROP = -0.3    # 잔고율 3개월 변화가 이 값 이하 = 잔고 급감


def load_sector_map() -> pd.DataFrame:
    if not SECTOR_MAP_PATH.exists():
        return pd.DataFrame(columns=["ticker", "sector"])
    df = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
    df.columns = ["ticker", "name", "sector", "price", "change", "pct_change", "market_cap", "market"]
    return df[["ticker", "sector"]].drop_duplicates("ticker")


def load_price_momentum(conn: sqlite3.Connection) -> pd.DataFrame:
    """가격 모멘텀에서 ret_1m 가져와 쇼트 스퀴즈 플래그에 활용."""
    try:
        return pd.read_sql(
            "SELECT ticker, period, ret_1m FROM factor_stock_price_momentum_month",
            conn,
        )
    except Exception:
        return pd.DataFrame(columns=["ticker", "period", "ret_1m"])


# ──────────────────────────────────────────────────────────────
# 2. 모멘텀 지표 계산
# ──────────────────────────────────────────────────────────────
def add_momentum(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["ticker", "period"]).copy()

    # 전월/3개월 전 잔고율 변화 (절대 변화, %)
    out["balance_ratio_1m_chg"] = out.groupby("ticker")["balance_ratio"].diff(1)
    out["balance_ratio_3m_chg"] = out.groupby("ticker")["balance_ratio"].diff(3)

    # 자기 과거 6개월 z-score
    def _zscore_rolling(series: pd.Series) -> pd.Series:
        def _z(window):
            if len(window.dropna()) < MIN_HISTORY:
                return np.nan
            m, s = window.mean(), window.std()
            return (window.iloc[-1] - m) / s if s > 0 else 0.0
        return series.rolling(ZSCORE_WINDOW, min_periods=MIN_HISTORY).apply(_z, raw=False)

    out["balance_ratio_zscore_own_6m"] = out.groupby("ticker")["balance_ratio"].transform(_zscore_rolling)

    return out


# ──────────────────────────────────────────────────────────────
# 3. 횡단면 백분위 (전 시장)
# ──────────────────────────────────────────────────────────────
def add_cross_sectional(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["balance_ratio_pct_cross"] = out.groupby("period")["balance_ratio"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    return out


# ──────────────────────────────────────────────────────────────
# 4. 쇼트 스퀴즈 플래그 + 종합 점수
# ──────────────────────────────────────────────────────────────
def add_score_and_flags(df: pd.DataFrame, price_mom: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # 가격 모멘텀 결합
    if not price_mom.empty:
        out = out.merge(price_mom[["ticker", "period", "ret_1m"]], on=["ticker", "period"], how="left")
    else:
        out["ret_1m"] = np.nan

    # 쇼트 스퀴즈 플래그: 잔고율 3개월 급감(< SQUEEZE_DROP) + 당월 가격 상승(ret_1m > 0)
    out["short_squeeze_flag"] = (
        (out["balance_ratio_3m_chg"] < SQUEEZE_DROP) &
        (out["ret_1m"] > 0)
    ).fillna(False)

    # 공매도 압박 종합 점수 (0=압박 없음, 1=매우 강함)
    # 잔고율 백분위 + z-score 정규화 평균
    z_norm = out["balance_ratio_zscore_own_6m"].clip(-3, 3) / 6 + 0.5  # 0~1
    pct = out["balance_ratio_pct_cross"].fillna(0.5)
    components = pd.concat([pct, z_norm], axis=1)
    out["shorting_pressure_score"] = components.mean(axis=1)

    # 버킷
    def _bucket(score):
        if pd.isna(score):
            return "neutral"
        if score >= 0.75:
            return "very_high"
        if score >= 0.6:
            return "high"
        if score >= 0.4:
            return "neutral"
        if score >= 0.25:
            return "low"
        return "very_low"

    out["shorting_pressure_bucket"] = out["shorting_pressure_score"].map(_bucket)

    return out.drop(columns=["ret_1m"], errors="ignore")


# ──────────────────────────────────────────────────────────────
# 5. 카탈로그
# ──────────────────────────────────────────────────────────────
def build_catalog() -> pd.DataFrame:
    rows = [
        {
            "factor_family": "shorting",
            "question": "현재 공매도 잔고율이 높은가?",
            "factor_name": "balance_ratio",
            "source_column": "공매도잔고/상장주식수 (%)",
            "interpretation": "높을수록 기관/외인의 약세 베팅 집중",
            "preferred_use": "공매도 압박 1차 필터",
        },
        {
            "factor_family": "shorting",
            "question": "공매도 잔고율이 최근 급변했는가?",
            "factor_name": "balance_ratio_3m_chg",
            "source_column": "balance_ratio diff(3)",
            "interpretation": "음수 급락 = 쇼트 커버링 진행 중 (쇼트 스퀴즈 전조)",
            "preferred_use": "쇼트 스퀴즈 후보 탐지",
        },
        {
            "factor_family": "shorting",
            "question": "자기 과거 대비 잔고율이 이례적으로 높은가?",
            "factor_name": "balance_ratio_zscore_own_6m",
            "source_column": "balance_ratio rolling 6M z-score",
            "interpretation": "양수 높을수록 과거 대비 공매도 비중 급증",
            "preferred_use": "신규 공매도 집중 종목 탐지",
        },
        {
            "factor_family": "shorting",
            "question": "쇼트 스퀴즈 후보인가?",
            "factor_name": "short_squeeze_flag",
            "source_column": "balance_ratio_3m_chg < -0.3 AND ret_1m > 0",
            "interpretation": "True = 잔고 급감 + 주가 상승 동시 = 쇼트 커버링 가속 가능성",
            "preferred_use": "단기 모멘텀 강화 신호 보조",
        },
        {
            "factor_family": "shorting",
            "question": "종합 공매도 압박 강도는?",
            "factor_name": "shorting_pressure_score",
            "source_column": "balance_ratio_pct_cross + z-score 정규화 평균",
            "interpretation": "0~1, 높을수록 공매도 압박 강함 (상승 시 스퀴즈 잠재력)",
            "preferred_use": "전체 팩터 결합 시 리스크/기회 이중 신호",
        },
    ]
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────
def run() -> None:
    if not SHORTING_PATH.exists():
        print(f"[ERROR] 공매도 데이터 없음: {SHORTING_PATH}")
        print("  먼저 scripts/01_collect/collect_shorting_balance_once.py 를 실행하세요.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_name(f"quant_data_{ts}_before_shorting_factors.sqlite")
    shutil.copy2(DB_PATH, backup)
    print(f"DB 백업: {backup.name}")

    raw = pd.read_csv(SHORTING_PATH, encoding="utf-8-sig")
    raw["period"] = raw["period"].astype(str)
    print(f"공매도 원시 데이터: {len(raw)}행, {raw['ticker'].nunique()}종목, "
          f"{raw['period'].min()} ~ {raw['period'].max()}")

    # 섹터 병합
    sector_map = load_sector_map()
    raw = raw.merge(sector_map, on="ticker", how="left")

    df = add_momentum(raw)
    df = add_cross_sectional(df)

    with sqlite3.connect(DB_PATH) as conn:
        price_mom = load_price_momentum(conn)

    df = add_score_and_flags(df, price_mom)
    catalog = build_catalog()

    print(f"\n공매도 팩터 요약 (최신 기간):")
    latest = df[df["period"] == df["period"].max()]
    print(f"  종목 수: {len(latest)}")
    print(f"  압박 버킷 분포:\n{latest['shorting_pressure_bucket'].value_counts().to_string()}")
    print(f"  쇼트 스퀴즈 후보: {latest['short_squeeze_flag'].sum()}종목")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "shorting_factors_month.csv", index=False, encoding="utf-8-sig")
    catalog.to_csv(OUTPUT_DIR / "shorting_factor_catalog.csv", index=False, encoding="utf-8-sig")

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("factor_shorting_month", conn, if_exists="replace", index=False)
        catalog.to_sql("factor_shorting_catalog", conn, if_exists="replace", index=False)
        conn.commit()

    print(f"\n완료: factor_shorting_month {len(df)}행, factor_shorting_catalog {len(catalog)}행")


if __name__ == "__main__":
    run()
