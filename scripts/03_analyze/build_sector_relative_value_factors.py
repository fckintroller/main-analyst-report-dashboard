"""
섹터 상대 PER/PBR + PBR/ROE + 가치/퀄리티 + 섹터 밸류 z-score 팩터 구축.

사용자 요청 팩터:
1. sector_relative_per  = 종목 PER / 동일 섹터 PER 중위값
2. sector_relative_pbr  = 종목 PBR / 동일 섹터 PBR 중위값
3. pbr_adjusted_by_roe  = PBR/ROE 및 섹터 내 ROE 대비 PBR 잔차
5. value_quality_score  = 섹터상대 저평가 + ROE 품질 합성 점수
6. sector_value_zscore  = 섹터 자체 PER/PBR 중위값의 과거 대비 z-score

입력 SQLite/CSV:
- factor_valuation_per_pbr_month: ticker×month PER/PBR/EPS/BPS/sector
- factor_roe_trend_month: ticker×month ROE
- data/raw/valuation/dart_finstate/finstate_all.csv: 최신 연간 BS/CF 원천(부채비율·FCF)

출력 CSV:
- data/raw/factors/sector_relative_value_month.csv
- data/raw/factors/sector_relative_value_catalog.csv

출력 SQLite 테이블:
- factor_sector_relative_value_month
- factor_sector_relative_value_catalog

주의:
- PER/PBR/ROE가 0 이하이거나 결측이면 임의 보간하지 않고 NaN 처리한다.
- 섹터 내 최소 표본 수 미만이면 섹터 상대/잔차 지표는 NaN 처리한다.
- 부채비율·FCF는 DART 최신 연간 스냅샷을 월간 패널에 ticker 기준으로 붙인다.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"
DART_FINSTATE_PATH = PROJECT_ROOT / "data" / "raw" / "valuation" / "dart_finstate" / "finstate_all.csv"

MIN_SECTOR_N = 5
SECTOR_HISTORY_WINDOW = 24
MIN_HISTORY_N = 12

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _safe_divide(num: pd.Series, den: pd.Series) -> pd.Series:
    den_clean = den.replace(0, np.nan)
    return num / den_clean


def _load_sector_map(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        sector = pd.read_sql("SELECT DISTINCT ticker, sector FROM factor_valuation_per_pbr_month", conn)
        sector["ticker"] = sector["ticker"].astype(str).str.zfill(6)
        return dict(zip(sector["ticker"], sector["sector"]))
    except Exception:
        return {}


def build_dart_financial_quality_snapshot(raw: pd.DataFrame, sector_map: dict[str, str]) -> pd.DataFrame:
    """DART annual long-form 원천에서 부채비율·FCF 품질 스냅샷을 만든다."""
    if raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    current = df[df["period"] == "current"].copy()
    wide = (
        current.pivot_table(index=["ticker", "bsns_year"], columns="account_id", values="amount", aggfunc="first")
        .reset_index()
        .rename_axis(columns=None)
    )

    for col in ["total_assets", "current_liabilities", "noncurrent_liabilities", "total_equity", "cfo", "capex"]:
        if col not in wide.columns:
            wide[col] = np.nan

    wide["sector"] = wide["ticker"].map(sector_map).fillna("unknown")
    wide["total_liabilities"] = wide["current_liabilities"] + wide["noncurrent_liabilities"]
    wide["debt_ratio"] = _safe_divide(wide["total_liabilities"], wide["total_equity"])
    wide.loc[wide["total_equity"] <= 0, "debt_ratio"] = np.nan
    wide["debt_to_assets"] = _safe_divide(wide["total_liabilities"], wide["total_assets"])
    wide.loc[wide["total_assets"] <= 0, "debt_to_assets"] = np.nan

    # DART CF의 유형자산 취득은 음수 또는 양수 표기 모두 가능하므로 절대 투자지출로 차감한다.
    wide["fcf"] = wide["cfo"] - wide["capex"].abs()
    wide.loc[wide["cfo"].isna() | wide["capex"].isna(), "fcf"] = np.nan
    wide["cfo_to_assets"] = _safe_divide(wide["cfo"], wide["total_assets"])
    wide["fcf_to_assets"] = _safe_divide(wide["fcf"], wide["total_assets"])
    wide.loc[wide["total_assets"] <= 0, ["cfo_to_assets", "fcf_to_assets"]] = np.nan
    wide["fcf_positive"] = np.where(wide["fcf"].notna(), (wide["fcf"] > 0).astype(float), np.nan)

    wide["debt_ratio_score"] = 1 - wide.groupby("sector")["debt_ratio"].rank(pct=True)
    wide["fcf_to_assets_score"] = wide.groupby("sector")["fcf_to_assets"].rank(pct=True)
    comps = wide[["debt_ratio_score", "fcf_to_assets_score", "fcf_positive"]]
    weights = pd.Series({"debt_ratio_score": 0.40, "fcf_to_assets_score": 0.45, "fcf_positive": 0.15})
    available = comps.notna().mul(weights, axis=1).sum(axis=1)
    wide["financial_quality_score"] = comps.mul(weights, axis=1).sum(axis=1) / available.replace(0, np.nan)
    wide.loc[available == 0, "financial_quality_score"] = np.nan

    cols = [
        "ticker", "bsns_year", "sector", "total_liabilities", "total_equity", "total_assets",
        "debt_ratio", "debt_to_assets", "cfo", "capex", "fcf", "cfo_to_assets", "fcf_to_assets",
        "fcf_positive", "debt_ratio_score", "fcf_to_assets_score", "financial_quality_score",
    ]
    return wide[cols]


def _load_financial_quality(conn: sqlite3.Connection) -> pd.DataFrame:
    if not DART_FINSTATE_PATH.exists():
        logger.warning("DART 재무제표 원천 파일 없음: %s", DART_FINSTATE_PATH)
        return pd.DataFrame()
    raw = pd.read_csv(DART_FINSTATE_PATH, encoding="utf-8-sig")
    return build_dart_financial_quality_snapshot(raw, _load_sector_map(conn))


def _load_inputs(conn: sqlite3.Connection) -> pd.DataFrame:
    val = pd.read_sql(
        """
        SELECT ticker, period, sector, PER, PBR, EPS, BPS,
               per_percentile_sector, pbr_percentile_sector,
               valuation_score, valuation_bucket
        FROM factor_valuation_per_pbr_month
        """,
        conn,
    )
    val["ticker"] = val["ticker"].astype(str).str.zfill(6)
    val["period"] = pd.to_datetime(val["period"], errors="coerce").dt.strftime("%Y-%m-01")
    for col in ["PER", "PBR", "EPS", "BPS", "per_percentile_sector", "pbr_percentile_sector", "valuation_score"]:
        val[col] = pd.to_numeric(val[col], errors="coerce")
    val.loc[val["PER"] <= 0, "PER"] = np.nan
    val.loc[val["PBR"] <= 0, "PBR"] = np.nan
    val.loc[val["BPS"] <= 0, "BPS"] = np.nan

    try:
        roe = pd.read_sql(
            "SELECT ticker, period, roe, roe_sector_pct_ts FROM factor_roe_trend_month",
            conn,
        )
        roe["ticker"] = roe["ticker"].astype(str).str.zfill(6)
        roe["period"] = pd.to_datetime(roe["period"], errors="coerce").dt.strftime("%Y-%m-01")
        roe["roe"] = pd.to_numeric(roe["roe"], errors="coerce")
        roe["roe_sector_pct_ts"] = pd.to_numeric(roe["roe_sector_pct_ts"], errors="coerce")
        df = val.merge(roe, on=["ticker", "period"], how="left")
    except Exception:
        df = val.copy()
        df["roe"] = _safe_divide(df["EPS"], df["BPS"])
        df["roe_sector_pct_ts"] = np.nan

    # factor_roe_trend_month가 비어있는 구간 보완: EPS/BPS implied ROE
    implied = _safe_divide(df["EPS"], df["BPS"])
    df["roe"] = df["roe"].where(df["roe"].notna(), implied)
    quality = _load_financial_quality(conn)
    if not quality.empty:
        df = df.merge(
            quality.drop(columns=["sector"], errors="ignore"),
            on="ticker",
            how="left",
        )
    for col in [
        "bsns_year", "debt_ratio", "debt_to_assets", "cfo", "capex", "fcf", "cfo_to_assets", "fcf_to_assets",
        "fcf_positive", "debt_ratio_score", "fcf_to_assets_score", "financial_quality_score",
    ]:
        if col not in df.columns:
            df[col] = np.nan
    return df.dropna(subset=["period"])


def add_sector_relative_multiples(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    sector_counts = out.groupby(["period", "sector"])["ticker"].transform("count")

    for col in ["PER", "PBR", "roe"]:
        median_col = f"sector_median_{col.lower()}"
        out[median_col] = out.groupby(["period", "sector"])[col].transform("median")
        out.loc[sector_counts < MIN_SECTOR_N, median_col] = np.nan

    out["sector_relative_per"] = _safe_divide(out["PER"], out["sector_median_per"])
    out["sector_relative_pbr"] = _safe_divide(out["PBR"], out["sector_median_pbr"])
    return out


def add_pbr_roe_adjusted(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    positive_roe = out["roe"].where(out["roe"] > 0)
    out["pbr_to_roe"] = _safe_divide(out["PBR"], positive_roe)

    # 같은 월·섹터 내 ROE-대비 PBR 위치: log(PBR) - median(log(PBR/ROE)) 방식의 단순 잔차
    out["sector_median_pbr_to_roe"] = out.groupby(["period", "sector"])["pbr_to_roe"].transform("median")
    sector_valid_counts = out.groupby(["period", "sector"])["pbr_to_roe"].transform(lambda s: s.notna().sum())
    out.loc[sector_valid_counts < MIN_SECTOR_N, "sector_median_pbr_to_roe"] = np.nan
    expected_pbr = out["roe"].where(out["roe"] > 0) * out["sector_median_pbr_to_roe"]
    out["pbr_roe_residual_sector"] = np.log(out["PBR"]) - np.log(expected_pbr)
    out.loc[(out["PBR"] <= 0) | (expected_pbr <= 0), "pbr_roe_residual_sector"] = np.nan

    # 낮을수록 ROE 대비 싸다. 섹터 내 백분위로 방향성을 맞춰 1=매력적
    residual_pct = out.groupby(["period", "sector"])["pbr_roe_residual_sector"].rank(pct=True)
    out["pbr_roe_adjusted_score"] = 1 - residual_pct
    out.loc[sector_valid_counts < MIN_SECTOR_N, "pbr_roe_adjusted_score"] = np.nan
    return out


def add_sector_value_zscores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values(["sector", "period", "ticker"])
    sector_month = (
        out.groupby(["sector", "period"], as_index=False)
        .agg(
            sector_median_per=("PER", "median"),
            sector_median_pbr=("PBR", "median"),
            sector_stock_count=("ticker", "count"),
        )
        .sort_values(["sector", "period"])
    )
    sector_month.loc[sector_month["sector_stock_count"] < MIN_SECTOR_N, ["sector_median_per", "sector_median_pbr"]] = np.nan

    for col in ["sector_median_per", "sector_median_pbr"]:
        mean = sector_month.groupby("sector")[col].transform(
            lambda s: s.rolling(SECTOR_HISTORY_WINDOW, min_periods=MIN_HISTORY_N).mean()
        )
        std = sector_month.groupby("sector")[col].transform(
            lambda s: s.rolling(SECTOR_HISTORY_WINDOW, min_periods=MIN_HISTORY_N).std()
        )
        zcol = col.replace("sector_median_", "sector_") + f"_zscore_{SECTOR_HISTORY_WINDOW}m"
        sector_month[zcol] = (sector_month[col] - mean) / std
        sector_month.loc[std == 0, zcol] = np.nan

    sector_month["sector_value_zscore"] = sector_month[
        [f"sector_per_zscore_{SECTOR_HISTORY_WINDOW}m", f"sector_pbr_zscore_{SECTOR_HISTORY_WINDOW}m"]
    ].mean(axis=1, skipna=True)
    sector_month.loc[
        sector_month[[f"sector_per_zscore_{SECTOR_HISTORY_WINDOW}m", f"sector_pbr_zscore_{SECTOR_HISTORY_WINDOW}m"]].isna().all(axis=1),
        "sector_value_zscore",
    ] = np.nan
    sector_month["sector_value_bucket"] = np.select(
        [
            sector_month["sector_value_zscore"] <= -1.0,
            sector_month["sector_value_zscore"] <= -0.3,
            sector_month["sector_value_zscore"] >= 1.0,
            sector_month["sector_value_zscore"] >= 0.3,
        ],
        ["historically_cheap", "cheap", "historically_rich", "rich"],
        default="neutral",
    )
    sector_month.loc[sector_month["sector_value_zscore"].isna(), "sector_value_bucket"] = "N/A"

    cols = [
        "sector", "period", "sector_stock_count",
        f"sector_per_zscore_{SECTOR_HISTORY_WINDOW}m",
        f"sector_pbr_zscore_{SECTOR_HISTORY_WINDOW}m",
        "sector_value_zscore", "sector_value_bucket",
    ]
    return out.merge(sector_month[cols], on=["sector", "period"], how="left")


def add_value_quality_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    per_cheap = 1 - out["sector_relative_per"].rank(pct=True)
    pbr_cheap = 1 - out["sector_relative_pbr"].rank(pct=True)

    # 기존 섹터 백분위가 있으면 우선 사용: 0=저멀티플, 1=고멀티플
    per_cheap = (1 - out["per_percentile_sector"]).where(out["per_percentile_sector"].notna(), per_cheap)
    pbr_cheap = (1 - out["pbr_percentile_sector"]).where(out["pbr_percentile_sector"].notna(), pbr_cheap)

    roe_quality = out["roe_sector_pct_ts"]
    if roe_quality.isna().all():
        roe_quality = out.groupby(["period", "sector"])["roe"].rank(pct=True)
    roe_quality = roe_quality.where(out["roe"] > 0)

    roe_vs_pbr = out["pbr_roe_adjusted_score"]
    debt_quality = out["debt_ratio_score"] if "debt_ratio_score" in out.columns else pd.Series(np.nan, index=out.index)
    fcf_quality = out["fcf_to_assets_score"] if "fcf_to_assets_score" in out.columns else pd.Series(np.nan, index=out.index)

    components = pd.concat(
        [
            per_cheap.rename("per_cheap"), pbr_cheap.rename("pbr_cheap"),
            roe_quality.rename("roe_quality"), roe_vs_pbr.rename("roe_vs_pbr"),
            debt_quality.rename("debt_quality"), fcf_quality.rename("fcf_quality"),
        ],
        axis=1,
    )
    weights = pd.Series({
        "per_cheap": 0.20, "pbr_cheap": 0.20, "roe_quality": 0.25,
        "roe_vs_pbr": 0.15, "debt_quality": 0.10, "fcf_quality": 0.10,
    })
    weighted = components.mul(weights, axis=1)
    available_w = components.notna().mul(weights, axis=1).sum(axis=1)
    out["value_quality_score"] = weighted.sum(axis=1) / available_w.replace(0, np.nan)
    out.loc[available_w == 0, "value_quality_score"] = np.nan
    has_debt_fcf = out[["debt_ratio_score", "fcf_to_assets_score"]].notna().any(axis=1) if {"debt_ratio_score", "fcf_to_assets_score"}.issubset(out.columns) else False
    out["quality_source"] = np.where(has_debt_fcf, "valuation_roe_debt_fcf", "valuation_roe_only")

    out["value_quality_bucket"] = np.select(
        [
            out["value_quality_score"] >= 0.75,
            out["value_quality_score"] >= 0.60,
            out["value_quality_score"] <= 0.25,
            out["value_quality_score"] <= 0.40,
        ],
        ["deep_value_quality", "value_quality", "avoid", "expensive_or_low_quality"],
        default="neutral",
    )
    out.loc[out["value_quality_score"].isna(), "value_quality_bucket"] = "N/A"
    return out


def build(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _load_inputs(conn)
    df = add_sector_relative_multiples(df)
    df = add_pbr_roe_adjusted(df)
    df = add_sector_value_zscores(df)
    df = add_value_quality_score(df)

    out_cols = [
        "ticker", "period", "sector", "PER", "PBR", "EPS", "BPS", "roe",
        "sector_median_per", "sector_median_pbr", "sector_median_roe",
        "sector_relative_per", "sector_relative_pbr",
        "pbr_to_roe", "sector_median_pbr_to_roe", "pbr_roe_residual_sector", "pbr_roe_adjusted_score",
        f"sector_per_zscore_{SECTOR_HISTORY_WINDOW}m", f"sector_pbr_zscore_{SECTOR_HISTORY_WINDOW}m",
        "sector_value_zscore", "sector_value_bucket",
        "bsns_year", "debt_ratio", "debt_to_assets", "cfo", "capex", "fcf", "cfo_to_assets", "fcf_to_assets",
        "fcf_positive", "debt_ratio_score", "fcf_to_assets_score", "financial_quality_score", "quality_source",
        "value_quality_score", "value_quality_bucket",
        "valuation_score", "valuation_bucket",
    ]
    monthly = df[out_cols].copy()

    catalog = build_catalog()
    return monthly, catalog


def build_catalog() -> pd.DataFrame:
    rows = [
        ("sector_relative_value", "sector_relative_per", "종목 PER / 동일 월·섹터 PER 중위값", "낮을수록 섹터 대비 저PER", "핵심", "1"),
        ("sector_relative_value", "sector_relative_pbr", "종목 PBR / 동일 월·섹터 PBR 중위값", "낮을수록 섹터 대비 저PBR", "핵심", "2"),
        ("sector_relative_value", "pbr_to_roe", "PBR / ROE", "ROE 1단위당 지불하는 장부가 배수. ROE<=0은 N/A", "해석", "3"),
        ("sector_relative_value", "pbr_roe_residual_sector", "log(PBR) - log(섹터 중앙 PBR/ROE × ROE)", "낮을수록 같은 섹터 ROE 대비 저평가", "핵심", "3"),
        ("sector_relative_value", "pbr_roe_adjusted_score", "섹터 내 PBR/ROE 잔차 역백분위", "1에 가까울수록 ROE 대비 싼 종목", "핵심", "3"),
        ("sector_relative_value", "debt_ratio", "(유동부채+비유동부채) / 자본총계", "낮을수록 재무 레버리지 부담이 낮음", "품질", "debt_fcf"),
        ("sector_relative_value", "fcf_to_assets", "(영업현금흐름 - |CAPEX|) / 자산총계", "높을수록 자산 대비 잉여현금흐름 창출력 우수", "품질", "debt_fcf"),
        ("sector_relative_value", "financial_quality_score", "저부채·FCF창출력·FCF양수 여부 합성", "1에 가까울수록 재무건전성+현금창출 품질 우수", "품질", "debt_fcf"),
        ("sector_relative_value", "value_quality_score", "저PER·저PBR·ROE수준·ROE대비PBR·저부채·FCF를 가중 합성", "1에 가까울수록 가치+품질 동시 충족", "핵심", "5"),
        ("sector_relative_value", "sector_value_zscore", "섹터 PER/PBR 중위값의 24개월 rolling z-score 평균", "음수일수록 해당 섹터 자체가 과거 대비 저평가", "섹터 필터", "6"),
    ]
    return pd.DataFrame(rows, columns=["factor_family", "factor_name", "definition", "interpretation", "preferred_use", "requested_no"])


def save_outputs(monthly: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int | str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = OUTPUT_DIR / "sector_relative_value_month.csv"
    catalog_path = OUTPUT_DIR / "sector_relative_value_catalog.csv"

    monthly.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    monthly.to_sql("factor_sector_relative_value_month", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_sector_relative_value_catalog", conn, if_exists="replace", index=False)

    return {
        "monthly_path": str(monthly_path),
        "catalog_path": str(catalog_path),
        "monthly_rows": len(monthly),
        "tickers": int(monthly["ticker"].nunique()),
        "period_min": str(monthly["period"].min()),
        "period_max": str(monthly["period"].max()),
        "catalog_rows": len(catalog),
        "non_null_sector_relative_per": int(monthly["sector_relative_per"].notna().sum()),
        "non_null_sector_relative_pbr": int(monthly["sector_relative_pbr"].notna().sum()),
        "non_null_pbr_roe_adjusted_score": int(monthly["pbr_roe_adjusted_score"].notna().sum()),
        "non_null_debt_ratio": int(monthly["debt_ratio"].notna().sum()),
        "non_null_fcf_to_assets": int(monthly["fcf_to_assets"].notna().sum()),
        "non_null_financial_quality_score": int(monthly["financial_quality_score"].notna().sum()),
        "non_null_value_quality_score": int(monthly["value_quality_score"].notna().sum()),
        "non_null_sector_value_zscore": int(monthly["sector_value_zscore"].notna().sum()),
    }


def run() -> dict[str, int | str]:
    logger.info("sector_relative_value 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        monthly, catalog = build(conn)
        result = save_outputs(monthly, catalog, conn)
    logger.info("완료: %s", result)
    return result


if __name__ == "__main__":
    print(run())
