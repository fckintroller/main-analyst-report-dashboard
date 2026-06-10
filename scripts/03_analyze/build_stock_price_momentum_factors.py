"""
개별 종목 가격·거래량 모멘텀 팩터 생성.

목적:
- 종목별 historical OHLCV에서 단기매매/모멘텀 관점에서 바로 참고할 수 있는
  "12-1 모멘텀, 최근 추세, 거래대금 급증, 변동성" 팩터 후보군을 만든다.

입력 raw:
- data/raw/stock_detail/{ticker}/ohlcv.csv (날짜, 시가, 고가, 저가, 종가, 거래량, 등락률)

출력 CSV:
- data/raw/factors/stock_price_momentum_month.csv
- data/raw/factors/stock_price_momentum_factor_catalog.csv

출력 SQLite 테이블:
- factor_stock_price_momentum_month
- factor_stock_price_momentum_catalog

Caveat:
- 모델 예측 결과가 아니라 모델링 전 1차 가공 팩터 후보군이다.
- 과거 이력이 부족해 비교 불가능한 구간은 N/A로 남기고 임의 보간하지 않는다.
- 거래대금은 일별 (종가 × 거래량) 근사치이며, 실제 체결 거래대금과는 오차가 있을 수 있다.
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

MOMENTUM_LOOKBACK = 12   # 모멘텀 측정 기준 과거 개월 수
MOMENTUM_SKIP = 1        # 최근 반전(reversal) 효과를 피하기 위해 제외하는 최근 개월 수
TURNOVER_WINDOW = 12     # 거래대금 z-score 산출 trailing 개월 수
VOL_WINDOW_DAYS = 63     # 변동성(일간 수익률 표준편차) 산출 trailing 거래일 수 (약 3개월)
MIN_CROSS_SECTION = 30   # 단면 percentile 산출 최소 종목 수


def discover_tickers() -> list[str]:
    tickers = []
    for child in sorted(STOCK_DETAIL_DIR.iterdir()):
        if child.is_dir() and (child / "ohlcv.csv").exists():
            tickers.append(child.name)
    return tickers


def load_ohlcv_panel(tickers: list[str]) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        path = STOCK_DETAIL_DIR / ticker / "ohlcv.csv"
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if df.empty or "날짜" not in df.columns or "종가" not in df.columns:
            continue
        df = df.rename(columns={"날짜": "date", "종가": "close", "거래량": "volume", "등락률": "change_pct"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "close"])
        df = df[df["close"] > 0]
        df["ticker"] = ticker
        df["daily_return"] = df["close"].pct_change()
        df["turnover_value"] = df["close"] * df["volume"]
        frames.append(df[["ticker", "date", "close", "volume", "change_pct", "daily_return", "turnover_value"]])
    if not frames:
        cols = ["ticker", "date", "close", "volume", "change_pct", "daily_return", "turnover_value"]
        return pd.DataFrame(columns=cols)
    panel = pd.concat(frames, ignore_index=True)
    return panel.sort_values(["ticker", "date"])


def build_monthly_panel(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return daily.assign(period=pd.Series(dtype="datetime64[ns]"))

    work = daily.copy()
    work["period"] = work["date"].dt.to_period("M").dt.to_timestamp()

    def _agg(group: pd.DataFrame) -> pd.Series:
        last = group.iloc[-1]
        return pd.Series({
            "close": last["close"],
            "month_avg_turnover_value": group["turnover_value"].mean(),
            "month_volatility": group["daily_return"].tail(VOL_WINDOW_DAYS).std(),
            "trading_days": len(group),
        })

    monthly = (
        work.groupby(["ticker", "period"])
        .apply(_agg, include_groups=False)
        .reset_index()
    )
    return monthly.sort_values(["ticker", "period"])


def add_momentum_factors(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.sort_values(["ticker", "period"]).copy()
    grp_close = out.groupby("ticker")["close"]

    out["ret_1m"] = grp_close.pct_change(1)
    out["ret_3m"] = grp_close.pct_change(3)
    out["ret_6m"] = grp_close.pct_change(6)
    out["ret_12m"] = grp_close.pct_change(MOMENTUM_LOOKBACK)

    close_skip = grp_close.shift(MOMENTUM_SKIP)
    close_lookback = grp_close.shift(MOMENTUM_LOOKBACK)
    out["mom_12_1"] = (close_skip - close_lookback) / close_lookback

    out["momentum_percentile_cross"] = out.groupby("period")["mom_12_1"].transform(
        lambda s: s.rank(pct=True, na_option="keep") if s.notna().sum() >= MIN_CROSS_SECTION else pd.Series(np.nan, index=s.index)
    )

    grp_turnover = out.groupby("ticker")["month_avg_turnover_value"]
    roll_mean = grp_turnover.transform(lambda s: s.rolling(TURNOVER_WINDOW, min_periods=6).mean())
    roll_std = grp_turnover.transform(lambda s: s.rolling(TURNOVER_WINDOW, min_periods=6).std())
    out["turnover_zscore_own"] = (out["month_avg_turnover_value"] - roll_mean) / roll_std
    out.loc[roll_std == 0, "turnover_zscore_own"] = np.nan

    return out


def add_momentum_score(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()

    mom_component = out["momentum_percentile_cross"]
    short_term = out["ret_1m"].clip(-0.3, 0.3) / 0.3
    turnover_component = out["turnover_zscore_own"].clip(-3, 3) / 3

    score_inputs = pd.concat([
        mom_component,
        (short_term + 1) / 2,             # -1~1 → 0~1로 스케일
        (turnover_component + 1) / 2,
    ], axis=1)
    out["momentum_score"] = score_inputs.mean(axis=1, skipna=True)
    out.loc[score_inputs.isna().all(axis=1), "momentum_score"] = np.nan

    conditions = [
        out["momentum_score"] >= 0.7,
        out["momentum_score"] >= 0.55,
        out["momentum_score"] <= 0.3,
        out["momentum_score"] <= 0.45,
    ]
    choices = ["strong_up", "up", "strong_down", "down"]
    out["momentum_bucket"] = np.select(conditions, choices, default="neutral")
    out.loc[out["momentum_score"].isna(), "momentum_bucket"] = "N/A"

    out["turnover_spike_flag"] = out["turnover_zscore_own"] >= 1.5
    out.loc[out["turnover_zscore_own"].isna(), "turnover_spike_flag"] = False

    return out


def build_factor_catalog() -> pd.DataFrame:
    rows = [
        ("stock_price_momentum", "최근 12개월(최근 1개월 제외) 가격 모멘텀이 시장 대비 강한가?",
         "mom_12_1 / momentum_percentile_cross", "종가",
         "Jegadeesh-Titman 12-1 모멘텀과 단면 백분위 (1에 가까울수록 모멘텀 강함)", "핵심"),
        ("stock_price_momentum", "최근 1~6개월 단기 추세는 어떤가?",
         "ret_1m / ret_3m / ret_6m", "종가",
         "최근 1/3/6개월 누적 수익률", "필터"),
        ("stock_price_momentum", "최근 거래대금이 평소 대비 급증했는가?",
         "turnover_zscore_own / turnover_spike_flag", "종가×거래량 근사 거래대금",
         "자기 과거 12개월 평균 대비 거래대금 z-score, 1.5 이상이면 급증 플래그", "핵심"),
        ("stock_price_momentum", "최근 변동성(리스크 크기)은 어느 정도인가?",
         "month_volatility", "일간 수익률",
         "최근 약 3개월(63거래일) 일간 수익률 표준편차", "필터"),
        ("stock_price_momentum", "종합적으로 단기 모멘텀이 강한 매수 후보인가?",
         "momentum_score / momentum_bucket", "모멘텀+단기추세+거래대금 합성",
         "0~1 합성 점수와 strong_down~strong_up 5단계 버킷", "핵심"),
    ]
    return pd.DataFrame(
        rows,
        columns=["factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"],
    )


def build_outputs(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = load_ohlcv_panel(tickers)
    monthly = build_monthly_panel(daily)
    monthly = add_momentum_factors(monthly)
    monthly = add_momentum_score(monthly)
    catalog = build_factor_catalog()
    return monthly, catalog


def save_outputs(monthly: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int | str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = OUTPUT_DIR / "stock_price_momentum_month.csv"
    catalog_path = OUTPUT_DIR / "stock_price_momentum_factor_catalog.csv"

    monthly_save = monthly.copy()
    monthly_save["period"] = pd.to_datetime(monthly_save["period"]).dt.strftime("%Y-%m-%d")

    monthly_save.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    monthly_save.to_sql("factor_stock_price_momentum_month", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_stock_price_momentum_catalog", conn, if_exists="replace", index=False)

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
