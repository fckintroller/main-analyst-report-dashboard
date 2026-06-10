"""
종목별 외국인·기관 수급(순매매) 모멘텀 팩터 생성.

목적:
- 종목별 historical 외국인/기관 순매매 거래량에서 "최근 수급이 유입세인가 유출세인가,
  방향이 가속/둔화되고 있는가, 외국인 보유비중이 늘고 있는가"를
  단기매매 관점의 1차 팩터 후보군으로 정리한다.

입력 raw:
- data/raw/stock_detail/{ticker}/investor_trend.csv
  (collect_stock_investor_trend_once.py로 신규 수집한 일별 외국인/기관 순매매거래량,
   외국인 보유주수·보유율 — Naver Finance, 약 12개월 lookback)

출력 CSV:
- data/raw/factors/investor_flow_momentum_month.csv
- data/raw/factors/investor_flow_momentum_factor_catalog.csv

출력 SQLite 테이블:
- factor_investor_flow_momentum_month
- factor_investor_flow_momentum_catalog

Caveat:
- 모델 예측 결과가 아니라 모델링 전 1차 가공 팩터 후보군이다.
- 신규 수집 데이터라 historical이 약 12개월로 짧다 → z-score 등 자기 과거 비교 윈도우를
  6개월로 좁게 설정했고, 그래도 부족한 구간은 N/A로 남기고 임의 보간하지 않는다.
- 순매매거래량은 종목별 절대 규모 차이가 커서, 그 달의 총 거래량 대비 비율
  (순매매강도 = 순매매거래량 합 / 거래량 합)로 정규화해 비교 가능하게 만든다.
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

OWN_HISTORY_WINDOW = 6   # 자기 과거 z-score trailing 개월 수 (수집 이력이 짧아 6개월로 설정)
MOMENTUM_LAG = 1         # 수급 가속도(전월 대비 변화) 비교 시차 (개월)
MIN_CROSS_SECTION = 30   # 단면 percentile 산출 최소 종목 수


def discover_tickers() -> list[str]:
    tickers = []
    for child in sorted(STOCK_DETAIL_DIR.iterdir()):
        if child.is_dir() and (child / "investor_trend.csv").exists():
            tickers.append(child.name)
    return tickers


def load_investor_trend_panel(tickers: list[str]) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        path = STOCK_DETAIL_DIR / ticker / "investor_trend.csv"
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if df.empty or "date" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["ticker"] = ticker
        frames.append(df[["ticker", "date", "close", "volume", "inst_net_volume", "foreign_net_volume", "foreign_ratio_pct"]])
    if not frames:
        cols = ["ticker", "date", "close", "volume", "inst_net_volume", "foreign_net_volume", "foreign_ratio_pct"]
        return pd.DataFrame(columns=cols)
    panel = pd.concat(frames, ignore_index=True)
    return panel.sort_values(["ticker", "date"])


def build_monthly_panel(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return daily.assign(period=pd.Series(dtype="datetime64[ns]"))

    work = daily.copy()
    work["period"] = work["date"].dt.to_period("M").dt.to_timestamp()

    def _agg(group: pd.DataFrame) -> pd.Series:
        volume_sum = group["volume"].sum()
        return pd.Series({
            "close": group["close"].iloc[-1],
            "volume_sum": volume_sum,
            "foreign_net_sum": group["foreign_net_volume"].sum(),
            "inst_net_sum": group["inst_net_volume"].sum(),
            "foreign_net_ratio": group["foreign_net_volume"].sum() / volume_sum if volume_sum else np.nan,
            "inst_net_ratio": group["inst_net_volume"].sum() / volume_sum if volume_sum else np.nan,
            "foreign_ratio_pct": group["foreign_ratio_pct"].iloc[-1],
            "trading_days": len(group),
        })

    monthly = (
        work.groupby(["ticker", "period"])
        .apply(_agg, include_groups=False)
        .reset_index()
    )
    return monthly.sort_values(["ticker", "period"])


def add_flow_factors(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.sort_values(["ticker", "period"]).copy()

    grp_foreign = out.groupby("ticker")["foreign_net_ratio"]
    grp_inst = out.groupby("ticker")["inst_net_ratio"]
    grp_foreign_pct = out.groupby("ticker")["foreign_ratio_pct"]

    out["foreign_net_ratio_change"] = grp_foreign.diff(MOMENTUM_LAG)
    out["inst_net_ratio_change"] = grp_inst.diff(MOMENTUM_LAG)
    out["foreign_ratio_pct_change"] = grp_foreign_pct.diff(MOMENTUM_LAG)

    roll_mean = grp_foreign.transform(lambda s: s.rolling(OWN_HISTORY_WINDOW, min_periods=3).mean())
    roll_std = grp_foreign.transform(lambda s: s.rolling(OWN_HISTORY_WINDOW, min_periods=3).std())
    out[f"foreign_net_ratio_zscore_own_{OWN_HISTORY_WINDOW}m"] = (out["foreign_net_ratio"] - roll_mean) / roll_std
    out.loc[roll_std == 0, f"foreign_net_ratio_zscore_own_{OWN_HISTORY_WINDOW}m"] = np.nan

    out["foreign_net_ratio_percentile_cross"] = out.groupby("period")["foreign_net_ratio"].transform(
        lambda s: s.rank(pct=True, na_option="keep") if s.notna().sum() >= MIN_CROSS_SECTION else pd.Series(np.nan, index=s.index)
    )

    return out


def add_flow_score(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()

    cross_component = out["foreign_net_ratio_percentile_cross"]
    zscore_component = (out[f"foreign_net_ratio_zscore_own_{OWN_HISTORY_WINDOW}m"].clip(-3, 3) + 3) / 6
    accel_component = (out["foreign_net_ratio_change"].clip(-0.1, 0.1) + 0.1) / 0.2

    score_inputs = pd.concat([cross_component, zscore_component, accel_component], axis=1)
    out["flow_score"] = score_inputs.mean(axis=1, skipna=True)
    out.loc[score_inputs.isna().all(axis=1), "flow_score"] = np.nan

    conditions = [
        out["flow_score"] >= 0.7,
        out["flow_score"] >= 0.55,
        out["flow_score"] <= 0.3,
        out["flow_score"] <= 0.45,
    ]
    choices = ["strong_inflow", "inflow", "strong_outflow", "outflow"]
    out["flow_bucket"] = np.select(conditions, choices, default="neutral")
    out.loc[out["flow_score"].isna(), "flow_bucket"] = "N/A"

    out["flow_direction"] = np.select(
        [out["foreign_net_ratio"] > 0.005, out["foreign_net_ratio"] < -0.005],
        ["net_buying", "net_selling"],
        default="flat",
    )
    out.loc[out["foreign_net_ratio"].isna(), "flow_direction"] = "N/A"

    return out


def build_factor_catalog() -> pd.DataFrame:
    rows = [
        ("investor_flow_momentum", "최근 한 달 외국인·기관이 순매수했는가, 순매도했는가?",
         "foreign_net_ratio / inst_net_ratio", "외국인·기관 순매매거래량 합계 ÷ 총 거래량 합계",
         "월간 거래량 대비 순매매 강도 (양수=순매수 우위, 음수=순매도 우위)", "핵심"),
        ("investor_flow_momentum", "외국인 수급 방향이 전월 대비 가속/둔화되고 있는가?",
         "foreign_net_ratio_change / inst_net_ratio_change", "월간 순매매강도 변화",
         f"{MOMENTUM_LAG}개월 전 대비 순매매강도 변화 (양수=매수 가속 또는 매도 둔화)", "핵심"),
        ("investor_flow_momentum", "지금 외국인 수급이 이 종목 자신의 최근 추세 대비 이례적인가?",
         f"foreign_net_ratio_zscore_own_{OWN_HISTORY_WINDOW}m", "월간 순매매강도",
         f"자기 과거 {OWN_HISTORY_WINDOW}개월 평균 대비 z-score (수집 이력이 짧아 6개월 윈도우 사용, 절대치가 클수록 이례적)", "필터"),
        ("investor_flow_momentum", "다른 종목들과 비교했을 때 외국인 수급 강도가 강한 편인가?",
         "foreign_net_ratio_percentile_cross", "월간 순매매강도",
         "같은 달 전 종목 대비 백분위 (1에 가까울수록 외국인 순매수 강도 상위)", "필터"),
        ("investor_flow_momentum", "외국인 보유비중이 늘고 있는가?",
         "foreign_ratio_pct / foreign_ratio_pct_change", "외국인 보유율(%)",
         "월말 외국인 보유율과 전월 대비 변화(%p) — 양수면 보유비중 확대", "해석"),
        ("investor_flow_momentum", "종합적으로 수급이 우호적인 매수 후보인가?",
         "flow_score / flow_bucket / flow_direction", "수급 강도+가속도+단면순위 합성",
         "0~1 합성 점수, strong_outflow~strong_inflow 5단계 버킷, net_buying/flat/net_selling 방향 라벨", "핵심"),
    ]
    return pd.DataFrame(
        rows,
        columns=["factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"],
    )


def build_outputs(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = load_investor_trend_panel(tickers)
    monthly = build_monthly_panel(daily)
    monthly = add_flow_factors(monthly)
    monthly = add_flow_score(monthly)
    catalog = build_factor_catalog()
    return monthly, catalog


def save_outputs(monthly: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int | str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = OUTPUT_DIR / "investor_flow_momentum_month.csv"
    catalog_path = OUTPUT_DIR / "investor_flow_momentum_factor_catalog.csv"

    monthly_save = monthly.copy()
    monthly_save["period"] = pd.to_datetime(monthly_save["period"]).dt.strftime("%Y-%m-%d")

    monthly_save.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    monthly_save.to_sql("factor_investor_flow_momentum_month", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_investor_flow_momentum_catalog", conn, if_exists="replace", index=False)

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
