"""
시장/매크로 regime 기반 NAVER DataLab 섹터 관심도 조정 팩터 생성.

목적:
- 섹터 관심도 신호를 시장/매크로 환경으로 할인/가중한다.
- 예측 모델이 아니라 모델링 전 regime-aware factor 후보군이다.

입력 SQLite 테이블:
- sentiment_naver_datalab_sector_interest_month_features
- macro_quant_factors_daily
- macro_quant_factors_monthly

출력 CSV:
- data/raw/factors/market_macro_regime_month.csv
- data/raw/factors/regime_adjusted_sector_interest_month.csv
- data/raw/factors/regime_adjusted_factor_catalog.csv

출력 SQLite 테이블:
- factor_market_macro_regime_month
- factor_regime_adjusted_sector_interest_month
- factor_regime_adjusted_catalog
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"

DAILY_REGIME_FACTORS = [
    "risk_off_composite_z",
    "vix_zscore_252d",
    "dxy_zscore_252d",
    "us_10y_2y_spread",
    "us_sp500_ret_60d_pct",
    "korea_kospi_ret_60d_pct",
    "korea_kosdaq_ret_60d_pct",
]
MONTHLY_REGIME_FACTORS = ["korea_exports_yoy_pct"]

EXPORT_SENSITIVE_SECTORS = {
    "semiconductor",
    "auto",
    "shipbuilding",
    "steel",
    "chemical",
    "refinery",
    "machinery",
    "display",
    "it_parts",
    "power_equipment",
    "defense",
}
GROWTH_SENSITIVE_SECTORS = {
    "battery",
    "internet",
    "game",
    "bio_pharma",
    "medical_device",
    "robot",
    "ai_software",
    "semiconductor",
    "it_parts",
    "display",
}


def _to_month_start(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values).dt.to_period("M").dt.to_timestamp()


def load_monthly_regime_inputs(conn: sqlite3.Connection) -> pd.DataFrame:
    daily = pd.read_sql(
        "select date, factor, value from macro_quant_factors_daily "
        f"where factor in ({','.join(['?'] * len(DAILY_REGIME_FACTORS))})",
        conn,
        params=DAILY_REGIME_FACTORS,
    )
    monthly = pd.read_sql(
        "select date, factor, value from macro_quant_factors_monthly "
        f"where factor in ({','.join(['?'] * len(MONTHLY_REGIME_FACTORS))})",
        conn,
        params=MONTHLY_REGIME_FACTORS,
    )

    frames = []
    if not daily.empty:
        daily["date"] = pd.to_datetime(daily["date"])
        daily["period"] = _to_month_start(daily["date"])
        daily = daily.sort_values(["factor", "date"]).groupby(["period", "factor"], as_index=False).tail(1)
        frames.append(daily[["period", "factor", "value"]])
    if not monthly.empty:
        monthly["date"] = pd.to_datetime(monthly["date"])
        monthly["period"] = _to_month_start(monthly["date"])
        monthly = monthly.sort_values(["factor", "date"]).groupby(["period", "factor"], as_index=False).tail(1)
        frames.append(monthly[["period", "factor", "value"]])
    if not frames:
        raise RuntimeError("No regime input factors found in SQLite")

    long = pd.concat(frames, ignore_index=True)
    wide = long.pivot_table(index="period", columns="factor", values="value", aggfunc="last").reset_index()
    wide.columns.name = None
    return wide.sort_values("period").reset_index(drop=True)


def classify_market_regime(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in DAILY_REGIME_FACTORS + MONTHLY_REGIME_FACTORS:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    risk_components = pd.concat(
        [
            out["risk_off_composite_z"],
            out["vix_zscore_252d"],
            out["dxy_zscore_252d"] * 0.5,
            -out["us_sp500_ret_60d_pct"] / 10.0,
        ],
        axis=1,
    )
    out["risk_off_score"] = risk_components.mean(axis=1, skipna=True)

    out["risk_on_flag"] = (
        (out["risk_off_composite_z"] < 0)
        & (out["vix_zscore_252d"] < 0.5)
        & (out["us_sp500_ret_60d_pct"] > 0)
    )
    out["risk_off_flag"] = (
        (out["risk_off_composite_z"] > 1)
        | (out["vix_zscore_252d"] > 1)
        | (out["risk_off_score"] > 1)
    )
    out["dollar_pressure_flag"] = out["dxy_zscore_252d"] > 1
    out["growth_on_flag"] = (
        (out["korea_kosdaq_ret_60d_pct"] > out["korea_kospi_ret_60d_pct"])
        & (out["korea_kosdaq_ret_60d_pct"] > 0)
    )
    out["export_recovery_flag"] = out["korea_exports_yoy_pct"] > 0

    regimes = []
    for _, row in out.iterrows():
        if bool(row["risk_off_flag"]):
            regimes.append("risk_off")
        elif bool(row["risk_on_flag"]):
            regimes.append("risk_on")
        elif bool(row["dollar_pressure_flag"]):
            regimes.append("dollar_pressure")
        else:
            regimes.append("neutral")
    out["market_regime"] = regimes

    for col in ["risk_on_flag", "risk_off_flag", "dollar_pressure_flag", "growth_on_flag", "export_recovery_flag"]:
        out[col] = out[col].map(lambda x: True if bool(x) else False).astype(object)
    return out


def _pct_rank(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").rank(pct=True)


def adjust_interest_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    numeric_cols = [
        "anchor_relative_ratio_winsorized",
        "anchor_relative_momentum_3m",
        "ratio_zscore_12m",
        "relative_rank_pct",
        "data_quality_score",
        "risk_off_score",
    ]
    for col in numeric_cols:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # 월별 cross-section percentile로 스케일 통일.
    if "period" in out.columns:
        group = out.groupby("period", group_keys=False)
        out["interest_level_pct"] = group["anchor_relative_ratio_winsorized"].apply(_pct_rank)
        out["interest_momentum_pct"] = group["anchor_relative_momentum_3m"].apply(_pct_rank)
        out["interest_zscore_pct"] = group["ratio_zscore_12m"].apply(_pct_rank)
    else:
        out["interest_level_pct"] = _pct_rank(out["anchor_relative_ratio_winsorized"])
        out["interest_momentum_pct"] = _pct_rank(out["anchor_relative_momentum_3m"])
        out["interest_zscore_pct"] = _pct_rank(out["ratio_zscore_12m"])

    out["base_interest_score"] = (
        out["interest_level_pct"].fillna(0.5) * 0.35
        + out["interest_momentum_pct"].fillna(0.5) * 0.30
        + out["interest_zscore_pct"].fillna(0.5) * 0.20
        + out["relative_rank_pct"].fillna(0.5) * 0.15
    )

    dollar_pressure = out["dollar_pressure_flag"].astype(bool) if "dollar_pressure_flag" in out.columns else pd.Series(False, index=out.index)
    growth_on = out["growth_on_flag"].astype(bool) if "growth_on_flag" in out.columns else pd.Series(False, index=out.index)
    export_recovery = out["export_recovery_flag"].astype(bool) if "export_recovery_flag" in out.columns else pd.Series(False, index=out.index)

    risk_discount = np.where(out["market_regime"].eq("risk_off"), 0.75, 1.0)
    risk_discount = np.where(dollar_pressure, risk_discount * 0.90, risk_discount)

    risk_on_boost = np.where(out["market_regime"].eq("risk_on"), 1.12, 1.0)
    growth_boost = np.where(
        growth_on & out["group_name"].isin(GROWTH_SENSITIVE_SECTORS),
        1.08,
        1.0,
    )
    export_boost = np.where(
        export_recovery & out["group_name"].isin(EXPORT_SENSITIVE_SECTORS),
        1.08,
        1.0,
    )
    quality_mult = out["data_quality_score"].fillna(100).clip(lower=0, upper=100) / 100.0

    out["risk_discount_applied"] = (risk_discount < 1.0).astype(object)
    out["growth_boost_applied"] = (growth_boost > 1.0).astype(object)
    out["export_boost_applied"] = (export_boost > 1.0).astype(object)
    out["regime_multiplier"] = risk_discount * risk_on_boost * growth_boost * export_boost * quality_mult
    out["regime_adjusted_interest_score"] = (out["base_interest_score"] * out["regime_multiplier"]).clip(0, 1.5)

    conditions = [
        out["regime_adjusted_interest_score"] >= 0.9,
        out["regime_adjusted_interest_score"] >= 0.7,
        out["regime_adjusted_interest_score"] >= 0.5,
        out["regime_adjusted_interest_score"] < 0.3,
    ]
    choices = ["very_strong", "strong", "neutral", "weak"]
    out["regime_adjusted_bucket"] = np.select(conditions, choices, default="moderate")
    return out


def build_factor_catalog() -> pd.DataFrame:
    rows = [
        ("market_macro_regime", "지금 시장이 risk-on/risk-off/달러압박/중립 중 어디인가?", "market_regime", "market_regime", "시장 국면 라벨", "필터"),
        ("market_macro_regime", "위험회피 강도가 높은가?", "risk_off_score", "risk_off_score", "위험회피 종합 점수", "핵심"),
        ("market_macro_regime", "성장주/테마주에 우호적인가?", "growth_on_flag", "growth_on_flag", "KOSDAQ 상대 모멘텀 기반 성장주 환경", "필터"),
        ("market_macro_regime", "외수/제조업에 우호적인가?", "export_recovery_flag", "export_recovery_flag", "한국 수출 증가율 양수 여부", "필터"),
        ("regime_adjusted_interest", "관심도 신호를 시장 regime으로 조정하면 강한가?", "base_interest_score", "base_interest_score", "관심도 레벨/모멘텀/z-score/rank 조합", "기초"),
        ("regime_adjusted_interest", "regime 조정 후 관심도 신호가 강한가?", "regime_adjusted_interest_score", "regime_adjusted_interest_score", "risk-off 할인, risk-on/growth/export 가중 후 점수", "핵심"),
        ("regime_adjusted_interest", "조정 신호의 해석 bucket은?", "regime_adjusted_bucket", "regime_adjusted_bucket", "very_strong/strong/moderate/neutral/weak", "해석"),
        ("regime_adjusted_interest", "risk-off/달러압박 할인이 적용됐는가?", "risk_discount_applied", "risk_discount_applied", "위험 국면 할인 여부", "품질/해석"),
        ("regime_adjusted_interest", "외수/제조업 가중이 적용됐는가?", "export_boost_applied", "export_boost_applied", "수출 회복 + 외수 제조업 섹터 가중", "해석"),
    ]
    return pd.DataFrame(rows, columns=["factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"])


def load_interest_features(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql("select * from sentiment_naver_datalab_sector_interest_month_features", conn)
    df["period"] = _to_month_start(df["period"])
    return df


def build_outputs(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    regime = classify_market_regime(load_monthly_regime_inputs(conn))
    features = load_interest_features(conn)
    merged = features.merge(regime, on="period", how="left")
    adjusted = adjust_interest_signals(merged)
    catalog = build_factor_catalog()
    return regime, adjusted, catalog


def save_outputs(regime: pd.DataFrame, adjusted: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int | str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    regime_path = OUTPUT_DIR / "market_macro_regime_month.csv"
    adjusted_path = OUTPUT_DIR / "regime_adjusted_sector_interest_month.csv"
    catalog_path = OUTPUT_DIR / "regime_adjusted_factor_catalog.csv"

    regime_save = regime.copy()
    adjusted_save = adjusted.copy()
    for df in [regime_save, adjusted_save]:
        if "period" in df.columns:
            df["period"] = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")

    regime_save.to_csv(regime_path, index=False, encoding="utf-8-sig")
    adjusted_save.to_csv(adjusted_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    regime_save.to_sql("factor_market_macro_regime_month", conn, if_exists="replace", index=False)
    adjusted_save.to_sql("factor_regime_adjusted_sector_interest_month", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_regime_adjusted_catalog", conn, if_exists="replace", index=False)

    return {
        "regime_path": str(regime_path),
        "adjusted_path": str(adjusted_path),
        "catalog_path": str(catalog_path),
        "regime_rows": len(regime_save),
        "adjusted_rows": len(adjusted_save),
        "catalog_rows": len(catalog),
    }


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        regime, adjusted, catalog = build_outputs(conn)
        result = save_outputs(regime, adjusted, catalog, conn)
    print(result)


if __name__ == "__main__":
    main()
