"""
종목별 PER/PBR 밸류에이션 모멘텀 팩터 생성.

목적:
- 개별 종목의 PER/PBR을 같은 섹터(업종) 내 단면(cross-section) 및 자기 과거 이력과 비교해
  "지금 이 종목이 섹터 내에서 싸 보이는가 / 비싸 보이는가 / 빠르게 재평가되고 있는가"를
  모델링 전 1차 팩터 후보군으로 정리한다.

입력 raw:
- data/raw/stock_detail/{ticker}/fundamental.csv (날짜, BPS, PER, PBR, EPS, DIV, DPS)
- data/raw/stock_detail/sector_map.csv (종목코드, 업종명, market 등)

출력 CSV:
- data/raw/factors/valuation_per_pbr_month.csv
- data/raw/factors/valuation_per_pbr_factor_catalog.csv

출력 SQLite 테이블:
- factor_valuation_per_pbr_month
- factor_valuation_per_pbr_catalog

Caveat:
- 모델 예측 결과가 아니라 모델링 전 1차 가공 팩터 후보군이다.
- PER/PBR이 음수이거나 결측인 구간은 N/A로 남기고 임의 보간하지 않는다.
- 섹터 매핑이 없는 종목은 sector=NaN 으로 남고 섹터 백분위는 NaN 처리된다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
STOCK_DETAIL_DIR = PROJECT_ROOT / "data" / "raw" / "stock_detail"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"
SECTOR_MAP_PATH = STOCK_DETAIL_DIR / "sector_map.csv"

OWN_HISTORY_WINDOW = 24   # 자기 과거 z-score 산출 시 사용할 trailing 개월 수
MOMENTUM_LAG = 3          # 밸류에이션 모멘텀(리레이팅) 비교 시차 (개월)
MIN_SECTOR_CROSS_SECTION = 5  # 섹터 내 단면 percentile 계산을 위한 최소 종목 수


def load_sector_map() -> pd.DataFrame:
    """sector_map.csv에서 ticker→sector(업종명) 매핑을 로드한다."""
    if not SECTOR_MAP_PATH.exists():
        return pd.DataFrame(columns=["ticker", "sector"])
    df = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
    df.columns = ["ticker", "name", "sector", "price", "change", "pct_change", "market_cap", "market"]
    return df[["ticker", "sector"]].drop_duplicates("ticker")


def discover_tickers() -> list[str]:
    tickers = []
    for child in sorted(STOCK_DETAIL_DIR.iterdir()):
        if child.is_dir() and (child / "fundamental.csv").exists():
            tickers.append(child.name)
    return tickers


def load_fundamental_panel(tickers: list[str]) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        path = STOCK_DETAIL_DIR / ticker / "fundamental.csv"
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if df.empty or "날짜" not in df.columns:
            continue
        df = df.rename(columns={"날짜": "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["ticker"] = ticker
        frames.append(df[["ticker", "date", "PER", "PBR", "EPS", "BPS", "DIV", "DPS"]])
    if not frames:
        return pd.DataFrame(columns=["ticker", "date", "PER", "PBR", "EPS", "BPS", "DIV", "DPS"])
    panel = pd.concat(frames, ignore_index=True)
    # PER/PBR 0 이하는 적자/자본잠식 등으로 비교 불가 → 결측 처리(임의 보간 금지)
    for col in ["PER", "PBR"]:
        panel.loc[panel[col] <= 0, col] = np.nan
    return panel


def to_month_end_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """일별 패널을 종목별 월말(그 달의 마지막 관측치) 패널로 축약한다."""
    if panel.empty:
        return panel.assign(period=pd.Series(dtype="datetime64[ns]"))
    work = panel.copy()
    work["period"] = work["date"].dt.to_period("M").dt.to_timestamp()
    work = work.sort_values(["ticker", "date"])
    monthly = work.groupby(["ticker", "period"], as_index=False).last()
    return monthly[["ticker", "period", "PER", "PBR", "EPS", "BPS", "DIV", "DPS"]]


def _sector_percentile(group: pd.Series) -> pd.Series:
    valid = group.dropna()
    if len(valid) < MIN_SECTOR_CROSS_SECTION:
        return pd.Series(np.nan, index=group.index)
    return group.rank(pct=True, na_option="keep")


def add_cross_sectional_factors(monthly: pd.DataFrame) -> pd.DataFrame:
    """섹터 내 단면 백분위 산출. sector 컬럼이 NaN인 종목은 NaN으로 처리된다."""
    out = monthly.copy()
    for col in ["PER", "PBR"]:
        out[f"{col.lower()}_percentile_sector"] = (
            out.groupby(["period", "sector"])[col].transform(_sector_percentile)
        )
    return out


def add_own_history_factors(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.sort_values(["ticker", "period"]).copy()

    for col in ["PER", "PBR"]:
        lower = col.lower()
        grp = out.groupby("ticker")[col]

        roll_mean = grp.transform(lambda s: s.rolling(OWN_HISTORY_WINDOW, min_periods=12).mean())
        roll_std = grp.transform(lambda s: s.rolling(OWN_HISTORY_WINDOW, min_periods=12).std())
        out[f"{lower}_zscore_own_{OWN_HISTORY_WINDOW}m"] = (out[col] - roll_mean) / roll_std
        out.loc[roll_std == 0, f"{lower}_zscore_own_{OWN_HISTORY_WINDOW}m"] = np.nan

        lagged = grp.shift(MOMENTUM_LAG)
        momentum = (out[col] - lagged) / lagged.abs()
        out[f"{lower}_rerating_momentum_{MOMENTUM_LAG}m"] = momentum

    return out


def add_valuation_score(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()

    # 점수: 섹터 내 percentile이 낮을수록(=섹터 내 싸 보일수록), 자기 과거 대비 z-score가 낮을수록 valuation_score를 높게
    per_cheap = 1 - out["per_percentile_sector"]
    pbr_cheap = 1 - out["pbr_percentile_sector"]
    per_z_cheap = -out[f"per_zscore_own_{OWN_HISTORY_WINDOW}m"].clip(-3, 3) / 3
    pbr_z_cheap = -out[f"pbr_zscore_own_{OWN_HISTORY_WINDOW}m"].clip(-3, 3) / 3

    components = pd.concat([per_cheap, pbr_cheap, per_z_cheap, pbr_z_cheap], axis=1)
    out["valuation_score"] = components.mean(axis=1, skipna=True)
    out.loc[components.isna().all(axis=1), "valuation_score"] = np.nan

    conditions = [
        out["valuation_score"] >= 0.7,
        out["valuation_score"] >= 0.55,
        out["valuation_score"] <= 0.3,
        out["valuation_score"] <= 0.45,
    ]
    choices = ["deep_value", "cheap", "expensive", "rich"]
    out["valuation_bucket"] = np.select(conditions, choices, default="neutral")
    out.loc[out["valuation_score"].isna(), "valuation_bucket"] = "N/A"

    rerating_cols = [f"per_rerating_momentum_{MOMENTUM_LAG}m", f"pbr_rerating_momentum_{MOMENTUM_LAG}m"]
    out["rerating_momentum_score"] = out[rerating_cols].mean(axis=1, skipna=True)
    out.loc[out[rerating_cols].isna().all(axis=1), "rerating_momentum_score"] = np.nan
    out["rerating_direction"] = np.select(
        [out["rerating_momentum_score"] > 0.05, out["rerating_momentum_score"] < -0.05],
        ["re_rating_up", "de_rating_down"],
        default="flat",
    )
    out.loc[out["rerating_momentum_score"].isna(), "rerating_direction"] = "N/A"

    return out


def build_factor_catalog() -> pd.DataFrame:
    rows = [
        ("valuation_per_pbr", "지금 이 종목의 PER/PBR이 같은 섹터(업종) 내에서 어느 위치인가?",
         "per_percentile_sector / pbr_percentile_sector", "PER/PBR",
         "같은 달 동일 섹터 내 종목 대비 백분위(0=섹터 내 가장 쌈, 1=섹터 내 가장 비쌈)", "필터"),
        ("valuation_per_pbr", "이 종목 자신의 과거 밸류에이션 대비 지금은 싼 편인가?",
         f"per_zscore_own_{OWN_HISTORY_WINDOW}m / pbr_zscore_own_{OWN_HISTORY_WINDOW}m", "PER/PBR",
         f"자기 과거 {OWN_HISTORY_WINDOW}개월 평균 대비 z-score (낮을수록 자기 역사상 저평가)", "핵심"),
        ("valuation_per_pbr", "최근 밸류에이션이 빠르게 재평가(re-rating)되고 있는가?",
         f"per_rerating_momentum_{MOMENTUM_LAG}m / pbr_rerating_momentum_{MOMENTUM_LAG}m", "PER/PBR",
         f"{MOMENTUM_LAG}개월 전 대비 PER/PBR 변화율 (양수=re-rating, 멀티플 확대 / 음수=de-rating, 멀티플 축소)", "핵심"),
        ("valuation_per_pbr", "종합적으로 저평가 신호로 볼 수 있는가?",
         "valuation_score / valuation_bucket", "PER/PBR 합성",
         "단면 백분위 + 자기 과거 z-score를 합성한 0~1 점수 (deep_value~rich 5단계 버킷)", "핵심"),
        ("valuation_per_pbr", "밸류에이션 재평가 방향은 상승(de-rating)인가 하락(re-rating)인가?",
         "rerating_momentum_score / rerating_direction", "PER/PBR 모멘텀 합성",
         "PER/PBR 모멘텀 평균과 방향 라벨(re_rating_up/flat/de_rating_down)", "해석"),
    ]
    return pd.DataFrame(
        rows,
        columns=["factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"],
    )


def build_outputs(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = load_fundamental_panel(tickers)
    monthly = to_month_end_panel(panel)
    sector_map = load_sector_map()
    monthly = monthly.merge(sector_map, on="ticker", how="left")
    monthly = add_cross_sectional_factors(monthly)
    monthly = add_own_history_factors(monthly)
    monthly = add_valuation_score(monthly)
    catalog = build_factor_catalog()
    return monthly, catalog


def save_outputs(monthly: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int | str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = OUTPUT_DIR / "valuation_per_pbr_month.csv"
    catalog_path = OUTPUT_DIR / "valuation_per_pbr_factor_catalog.csv"

    monthly_save = monthly.copy()
    monthly_save["period"] = pd.to_datetime(monthly_save["period"]).dt.strftime("%Y-%m-%d")

    monthly_save.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    monthly_save.to_sql("factor_valuation_per_pbr_month", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_valuation_per_pbr_catalog", conn, if_exists="replace", index=False)

    return {
        "monthly_path": str(monthly_path),
        "catalog_path": str(catalog_path),
        "monthly_rows": len(monthly_save),
        "tickers": int(monthly_save["ticker"].nunique()),
        "period_min": monthly_save["period"].min(),
        "period_max": monthly_save["period"].max(),
        "catalog_rows": len(catalog),
    }


def main() -> None:
    tickers = discover_tickers()
    with sqlite3.connect(DB_PATH) as conn:
        monthly, catalog = build_outputs(tickers)
        result = save_outputs(monthly, catalog, conn)
    print(result)


if __name__ == "__main__":
    main()
