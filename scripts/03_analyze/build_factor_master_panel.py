"""
팩터 마스터 패널 1단계 구축.

분산된 월간/스냅샷 팩터를 ticker×period 기준 `factor_master_month`로 병합하고,
팩터 헬스 리포트와 데이터 품질 리포트를 산출한다.

원칙:
- 결측 데이터는 임의 보간하지 않는다.
- 스냅샷 팩터는 최신 월에만 ticker 기준으로 붙이고 snapshot_date/stale flag를 분리한다.
- 합성 점수는 존재하는 컴포넌트만 평균한다.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
BACKUP_DIR = PROJECT_ROOT / "data" / "database" / "backups"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CORE_FACTOR_COLS = [
    "value_score",
    "quality_score",
    "momentum_score",
    "flow_score",
    "sentiment_score",
    "macro_regime_score",
]
SNAPSHOT_DATE_COLS = ["news_snapshot_date", "minute_snapshot_date", "target_snapshot_date"]
DEFAULT_STALE_DAYS = 7
SOURCE_STALE_RULES = {
    "news": {"date_col": "news_snapshot_date", "flag_col": "news_stale_flag", "allowed_lag_days": 3, "score_col": "sentiment_score"},
    "minute": {"date_col": "minute_snapshot_date", "flag_col": "minute_stale_flag", "allowed_lag_days": 0, "score_col": "minute_tick_score"},
    "target_price": {"date_col": "target_snapshot_date", "flag_col": "target_stale_flag", "allowed_lag_days": 14, "score_col": "target_price_score"},
}


TABLE_SPECS = {
    "momentum": ("factor_stock_price_momentum_month", [
        "ticker", "period", "close", "ret_1m", "ret_3m", "ret_6m", "ret_12m", "momentum_score",
        "month_avg_turnover_value", "month_volatility",
    ]),
    "size": ("factor_size_month", ["ticker", "period", "sector", "market_cap", "size_bucket", "small_cap_score"]),
    "liquidity": ("factor_liquidity_turnover_month", [
        "ticker", "period", "turnover_value_avg", "turnover_ratio", "liquidity_score",
    ]),
    "valuation": ("factor_valuation_per_pbr_month", [
        "ticker", "period", "PER", "PBR", "valuation_score", "rerating_momentum_score",
    ]),
    "sector_value": ("factor_sector_relative_value_month", [
        "ticker", "period", "value_quality_score", "sector_value_zscore", "balance_sheet_quality_score",
        "cashflow_quality_score", "earnings_stability_score", "fcf_to_assets", "debt_ratio", "financial_quality_score",
    ]),
    "roe": ("factor_roe_trend_month", ["ticker", "period", "roe", "roe_sector_pct_ts"]),
    "flow": ("factor_investor_flow_momentum_month", [
        "ticker", "period", "flow_score", "foreign_net_ratio", "inst_net_ratio",
    ]),
    "news": ("factor_news_sentiment_snapshot", [
        "ticker", "news_sentiment_score", "net_sentiment_ratio", "latest_headline_date",
    ]),
    "minute": ("factor_minute_tick_snapshot", ["ticker", "minute_tick_score", "trade_date"]),
    "target_price": ("factor_consensus_revision_snapshot", [
        "ticker", "snapshot_date", "history_points", "target_price_score", "revision_acceleration_score",
        "strong_swing_candidate_flag", "value_trap_revision_warning",
    ]),
    "shorting": ("factor_shorting_month", [
        "ticker", "period", "shorting_pressure_score", "balance_ratio",
        "balance_ratio_zscore_own_6m", "short_squeeze_flag",
    ]),
}


def _normalize_ticker(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.upper().str.zfill(6)


def _normalize_period(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    out = dt.dt.strftime("%Y-%m")
    raw = series.astype(str).str.slice(0, 7)
    return out.fillna(raw)


def _clip01(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(0, 1)


def _weighted_mean(frame: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="float64")
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    if weights is None:
        available = numeric.notna().sum(axis=1)
        out = numeric.sum(axis=1, min_count=1) / available.replace(0, np.nan)
    else:
        weight = pd.Series(weights, dtype="float64")
        cols = [c for c in numeric.columns if c in weight.index]
        numeric = numeric[cols]
        weight = weight[cols]
        available_weight = numeric.notna().mul(weight, axis=1).sum(axis=1)
        out = numeric.mul(weight, axis=1).sum(axis=1, min_count=1) / available_weight.replace(0, np.nan)
    return out.clip(0, 1)


def _read_table(conn: sqlite3.Connection, table: str, columns: list[str]) -> pd.DataFrame:
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return pd.DataFrame(columns=columns)
    actual = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    selected = [c for c in columns if c in actual]
    if not selected:
        return pd.DataFrame(columns=columns)
    df = pd.read_sql(f"SELECT {', '.join(selected)} FROM {table}", conn)
    for col in columns:
        if col not in df.columns:
            df[col] = np.nan
    return df[columns]


def load_inputs(conn: sqlite3.Connection | None = None) -> dict[str, pd.DataFrame]:
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True
    try:
        inputs = {name: _read_table(conn, table, cols) for name, (table, cols) in TABLE_SPECS.items()}
        # 이름/시장 정보 fallback: size와 valuation의 sector 중심으로 구성한다.
        names = pd.DataFrame()
        try:
            names = pd.read_sql("SELECT DISTINCT ticker, name, market FROM stock_master", conn)
        except Exception:
            tickers = set()
            for key in ["momentum", "size", "valuation", "flow"]:
                if "ticker" in inputs[key].columns:
                    tickers.update(inputs[key]["ticker"].dropna().astype(str).str.zfill(6).tolist())
            names = pd.DataFrame({"ticker": sorted(tickers)})
        inputs["names"] = names
        return inputs
    finally:
        if close_conn:
            conn.close()


def _prepare_monthly(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["ticker"] = _normalize_ticker(out["ticker"])
    out["period"] = _normalize_period(out["period"])
    return out.drop_duplicates(["ticker", "period"], keep="last")


def _base_monthly_panel(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    monthly_keys = ["momentum", "size", "liquidity", "valuation", "sector_value", "roe", "flow", "shorting"]
    base_parts = []
    for key in monthly_keys:
        df = _prepare_monthly(inputs.get(key, pd.DataFrame()))
        if not df.empty:
            base_parts.append(df[["ticker", "period"]])
    if not base_parts:
        return pd.DataFrame(columns=["ticker", "period"])
    base = pd.concat(base_parts, ignore_index=True).drop_duplicates().sort_values(["period", "ticker"])
    return base.reset_index(drop=True)


def _merge_monthly(base: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    panel = base.copy()
    for key in ["momentum", "size", "liquidity", "valuation", "sector_value", "roe", "flow", "shorting"]:
        df = _prepare_monthly(inputs.get(key, pd.DataFrame()))
        if df.empty:
            continue
        panel = panel.merge(df, on=["ticker", "period"], how="left", suffixes=("", f"_{key}"))
    if "sector_size" in panel.columns and "sector" not in panel.columns:
        panel = panel.rename(columns={"sector_size": "sector"})
    return panel


def _latest_snapshot(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if df.empty or "ticker" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out["ticker"] = _normalize_ticker(out["ticker"])
    if date_col in out.columns:
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.sort_values(date_col)
    return out.drop_duplicates("ticker", keep="last")


def _attach_snapshots(panel: pd.DataFrame, inputs: dict[str, pd.DataFrame], as_of_date: str | None) -> pd.DataFrame:
    if panel.empty:
        return panel
    latest_period = panel["period"].max()
    as_of = pd.to_datetime(as_of_date or pd.Timestamp.today().strftime("%Y-%m-%d"), errors="coerce")

    news = _latest_snapshot(inputs.get("news", pd.DataFrame()), "latest_headline_date")
    if not news.empty:
        news = news.rename(columns={"latest_headline_date": "news_snapshot_date"})
        news["sentiment_score"] = _clip01(news["news_sentiment_score"])
        panel = panel.merge(
            news[["ticker", "sentiment_score", "net_sentiment_ratio", "news_snapshot_date"]],
            on="ticker",
            how="left",
        )
    else:
        panel["sentiment_score"] = np.nan
        panel["news_snapshot_date"] = pd.NaT

    minute = _latest_snapshot(inputs.get("minute", pd.DataFrame()), "trade_date")
    if not minute.empty:
        minute = minute.rename(columns={"trade_date": "minute_snapshot_date"})
        minute["minute_tick_score"] = _clip01(minute["minute_tick_score"])
        panel = panel.merge(minute[["ticker", "minute_tick_score", "minute_snapshot_date"]], on="ticker", how="left")
    else:
        panel["minute_tick_score"] = np.nan
        panel["minute_snapshot_date"] = pd.NaT

    target = _latest_snapshot(inputs.get("target_price", pd.DataFrame()), "snapshot_date")
    if not target.empty:
        target = target.rename(columns={"snapshot_date": "target_snapshot_date"})
        for col in ["target_price_score", "revision_acceleration_score"]:
            if col in target.columns:
                target[col] = _clip01(target[col])
        keep = [
            "ticker", "target_snapshot_date", "history_points", "target_price_score", "revision_acceleration_score",
            "strong_swing_candidate_flag", "value_trap_revision_warning",
        ]
        panel = panel.merge(target[[c for c in keep if c in target.columns]], on="ticker", how="left")
    else:
        panel["target_snapshot_date"] = pd.NaT
        panel["history_points"] = np.nan
        panel["target_price_score"] = np.nan
        panel["revision_acceleration_score"] = np.nan
        panel["strong_swing_candidate_flag"] = np.nan
        panel["value_trap_revision_warning"] = np.nan

    not_latest = panel["period"] != latest_period
    for col in [
        "sentiment_score", "net_sentiment_ratio", "news_snapshot_date", "minute_tick_score", "minute_snapshot_date",
        "target_snapshot_date", "history_points", "target_price_score", "revision_acceleration_score",
        "strong_swing_candidate_flag", "value_trap_revision_warning",
    ]:
        if col in panel.columns:
            panel.loc[not_latest, col] = np.nan

    panel["news_stale_flag"] = _stale_flag(panel.get("news_snapshot_date"), as_of, SOURCE_STALE_RULES["news"]["allowed_lag_days"])
    panel["minute_stale_flag"] = _stale_flag(panel.get("minute_snapshot_date"), as_of, SOURCE_STALE_RULES["minute"]["allowed_lag_days"])
    panel["target_stale_flag"] = _stale_flag(panel.get("target_snapshot_date"), as_of, SOURCE_STALE_RULES["target_price"]["allowed_lag_days"])
    panel["news_age_days"] = _age_days(panel.get("news_snapshot_date"), as_of)
    panel["minute_age_days"] = _age_days(panel.get("minute_snapshot_date"), as_of)
    panel["target_age_days"] = _age_days(panel.get("target_snapshot_date"), as_of)
    panel.loc[not_latest, [
        "news_stale_flag", "minute_stale_flag", "target_stale_flag",
        "news_age_days", "minute_age_days", "target_age_days",
    ]] = 0
    return panel


def _stale_flag(dates: pd.Series | None, as_of: pd.Timestamp, allowed_lag_days: int = DEFAULT_STALE_DAYS) -> pd.Series:
    if dates is None:
        return pd.Series(dtype="int64")
    parsed = pd.to_datetime(dates, errors="coerce")
    if pd.isna(as_of):
        return pd.Series(0, index=parsed.index, dtype="int64")
    stale = parsed.notna() & ((as_of - parsed).dt.days > allowed_lag_days)
    return stale.astype(int)


def _age_days(dates: pd.Series | None, as_of: pd.Timestamp) -> pd.Series:
    if dates is None:
        return pd.Series(dtype="float64")
    parsed = pd.to_datetime(dates, errors="coerce")
    if pd.isna(as_of):
        return pd.Series(np.nan, index=parsed.index, dtype="float64")
    return (as_of - parsed).dt.days.astype("float64")


def _macro_regime_by_period(panel: pd.DataFrame) -> pd.Series:
    # 1단계에서는 시장 레짐 전용 테이블이 종목 단위가 아니므로 중립값으로 명시한다.
    # 결측 보간이 아니라 "미반영 중립" 컴포넌트로 두어 coverage_count에는 포함하지 않는다.
    return pd.Series(0.5, index=panel.index, dtype="float64")


def build_factor_master_panel(inputs: dict[str, pd.DataFrame], as_of_date: str | None = None) -> pd.DataFrame:
    base = _base_monthly_panel(inputs)
    if base.empty:
        return pd.DataFrame()
    panel = _merge_monthly(base, inputs)
    panel = _attach_snapshots(panel, inputs, as_of_date)

    # 컴포넌트 점수: 기존 원천 점수를 우선 사용하고, 결측은 보간하지 않는다.
    panel["value_score"] = _weighted_mean(panel[[c for c in ["valuation_score", "value_quality_score"] if c in panel.columns]])
    panel["quality_score"] = _weighted_mean(panel[[c for c in [
        "financial_quality_score", "balance_sheet_quality_score", "cashflow_quality_score", "earnings_stability_score", "roe_sector_pct_ts",
    ] if c in panel.columns]])
    if "momentum_score" in panel.columns:
        panel["momentum_score"] = _clip01(panel["momentum_score"])
    else:
        panel["momentum_score"] = np.nan
    if "flow_score" in panel.columns:
        panel["flow_score"] = _clip01(panel["flow_score"])
    else:
        panel["flow_score"] = np.nan
    panel["sentiment_score"] = _clip01(panel.get("sentiment_score", pd.Series(np.nan, index=panel.index)))
    panel["sentiment_score_raw"] = panel["sentiment_score"]
    if "news_stale_flag" in panel.columns:
        # 뉴스감성은 3일 초과 미갱신 시 점수 영향 축소(결측 보간이 아니라 stale penalty).
        panel.loc[pd.to_numeric(panel["news_stale_flag"], errors="coerce").fillna(0) > 0, "sentiment_score"] *= 0.5
    panel["macro_regime_score"] = _macro_regime_by_period(panel)

    # 공매도 팩터: shorting_pressure_score 방향 반전 (낮을수록 매수 우호)
    if "shorting_pressure_score" in panel.columns:
        panel["short_score"] = (1.0 - _clip01(panel["shorting_pressure_score"])).clip(0, 1)
    else:
        panel["short_score"] = np.nan

    trade_factor_cols = ["value_score", "quality_score", "momentum_score", "flow_score", "sentiment_score"]
    quality_factor_cols = trade_factor_cols + ["target_price_score"]
    available_quality_cols = [c for c in quality_factor_cols if c in panel.columns]
    panel["coverage_count"] = panel[trade_factor_cols].notna().sum(axis=1)
    panel["coverage_score"] = (panel["coverage_count"] / len(trade_factor_cols)).clip(0, 1)
    panel["factor_coverage_score"] = panel["coverage_score"]
    panel["missing_factor_count"] = panel[available_quality_cols].isna().sum(axis=1) if available_quality_cols else 0
    panel["ticker_missing_rate"] = (panel["missing_factor_count"] / max(len(available_quality_cols), 1)).clip(0, 1)

    stale_cols = [c for c in ["news_stale_flag", "minute_stale_flag", "target_stale_flag"] if c in panel.columns]
    panel["stale_factor_count"] = panel[stale_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) if stale_cols else 0
    panel["stale_factor_flag"] = (panel["stale_factor_count"] > 0).astype(int)
    panel["stale_penalty"] = (panel["stale_factor_count"] / max(len(stale_cols), 1)).clip(0, 1)
    panel["data_freshness_score"] = (1 - panel["stale_penalty"]).clip(0, 1)
    panel["source_failure_count"] = panel["stale_factor_count"] + panel["missing_factor_count"]
    panel["source_failure_flag"] = (panel["source_failure_count"] > 0).astype(int)
    panel["minute_usable_for_trading_flag"] = (~(
        panel.get("minute_tick_score", pd.Series(np.nan, index=panel.index)).notna()
        & (pd.to_numeric(panel.get("minute_stale_flag", pd.Series(0, index=panel.index)), errors="coerce").fillna(0) > 0)
    )).astype(int)
    panel["data_quality_penalty"] = (
        panel["ticker_missing_rate"] * 0.45
        + panel["stale_penalty"] * 0.45
        + panel["source_failure_flag"] * 0.10
    ).clip(0, 1)

    panel["raw_composite_score"] = _weighted_mean(panel[CORE_FACTOR_COLS], weights={
        "value_score": 0.22,
        "quality_score": 0.22,
        "momentum_score": 0.22,
        "flow_score": 0.16,
        "sentiment_score": 0.10,
        "macro_regime_score": 0.08,
    })
    panel["composite_score"] = (panel["raw_composite_score"] * (1 - panel["data_quality_penalty"] * 0.35)).clip(0, 1)
    panel["confidence_score"] = (
        panel["coverage_score"] * 0.55 + panel["data_freshness_score"] * 0.30 + (1 - panel["data_quality_penalty"]) * 0.15
    ).clip(0, 1)
    panel["usable_for_trading_flag"] = (
        (panel["coverage_score"] >= 0.4)
        & (panel["data_freshness_score"] >= 0.5)
        & (panel["minute_usable_for_trading_flag"] == 1)
    ).astype(int)

    names = inputs.get("names", pd.DataFrame()).copy()
    if not names.empty and "ticker" in names.columns:
        names["ticker"] = _normalize_ticker(names["ticker"])
        keep = [c for c in ["ticker", "name", "market"] if c in names.columns]
        panel = panel.merge(names[keep].drop_duplicates("ticker"), on="ticker", how="left")

    ordered = [
        "ticker", "name", "market", "sector", "period", "close", "market_cap", "size_bucket",
        "PER", "PBR", "roe", "ret_1m", "ret_3m", "ret_6m", "ret_12m",
        "value_score", "quality_score", "momentum_score", "flow_score", "sentiment_score", "macro_regime_score",
        "raw_composite_score", "composite_score", "coverage_count", "coverage_score", "factor_coverage_score",
        "data_freshness_score", "data_quality_penalty", "confidence_score",
        "ticker_missing_rate", "missing_factor_count", "stale_penalty", "stale_factor_count", "stale_factor_flag",
        "source_failure_count", "source_failure_flag", "usable_for_trading_flag", "minute_usable_for_trading_flag",
        "news_snapshot_date", "minute_snapshot_date", "target_snapshot_date",
        "news_age_days", "minute_age_days", "target_age_days",
        "news_stale_flag", "minute_stale_flag", "target_stale_flag",
        "target_price_score", "revision_acceleration_score", "history_points",
        "short_score", "shorting_pressure_score", "balance_ratio",
        "balance_ratio_zscore_own_6m", "short_squeeze_flag",
    ]
    for col in ordered:
        if col not in panel.columns:
            panel[col] = np.nan
    extra = [c for c in panel.columns if c not in ordered]
    return panel[ordered + extra].sort_values(["period", "composite_score", "ticker"], ascending=[True, False, True]).reset_index(drop=True)


def _forward_return(panel: pd.DataFrame) -> pd.Series:
    if "close" not in panel.columns:
        return pd.Series(np.nan, index=panel.index)
    ordered = panel.sort_values(["ticker", "period"]).copy()
    ordered["forward_return_1m"] = ordered.groupby("ticker")["close"].shift(-1) / ordered["close"] - 1
    return ordered.sort_index()["forward_return_1m"]


def build_factor_health_report(panel: pd.DataFrame, factor_cols: Iterable[str] | None = None, quantile: float = 0.2) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    work = panel.copy()
    work["forward_return_1m"] = _forward_return(work)
    if factor_cols is None:
        factor_cols = CORE_FACTOR_COLS + ["composite_score"]
    rows = []
    for factor in factor_cols:
        if factor not in work.columns:
            continue
        spreads = []
        ics = []
        periods = []
        coverage = []
        for period, g in work.groupby("period"):
            valid = g[[factor, "forward_return_1m"]].apply(pd.to_numeric, errors="coerce")
            score_valid = valid[factor].notna()
            coverage.append(float(score_valid.mean()) if len(valid) else np.nan)
            valid = valid.dropna()
            if len(valid) < 3:
                continue
            top_n = max(1, int(np.ceil(len(valid) * quantile)))
            bottom_n = max(1, int(np.ceil(len(valid) * quantile)))
            ranked = valid.sort_values(factor)
            spread = ranked.tail(top_n)["forward_return_1m"].mean() - ranked.head(bottom_n)["forward_return_1m"].mean()
            if valid[factor].nunique(dropna=True) < 2 or valid["forward_return_1m"].nunique(dropna=True) < 2:
                ic = np.nan
            else:
                ic = valid[factor].rank(pct=True).corr(valid["forward_return_1m"].rank(pct=True))
            spreads.append(float(spread) if pd.notna(spread) else np.nan)
            ics.append(float(ic) if pd.notna(ic) else np.nan)
            periods.append(period)
        spread_s = pd.Series(spreads, dtype="float64")
        ic_s = pd.Series(ics, dtype="float64")
        recent_3m_spread = float(spread_s.tail(3).mean()) if not spread_s.dropna().empty else np.nan
        spread_mean = float(spread_s.mean()) if not spread_s.dropna().empty else np.nan
        ic_mean = float(ic_s.mean()) if not ic_s.dropna().empty else np.nan
        effectiveness = _effectiveness_score(recent_3m_spread, ic_mean)
        rows.append({
            "factor_name": factor,
            "months": len(periods),
            "latest_period": max(periods) if periods else work["period"].max(),
            "coverage_mean": float(pd.Series(coverage, dtype="float64").mean()) if coverage else np.nan,
            "top_bottom_spread_mean": spread_mean,
            "rank_ic_mean": ic_mean,
            "recent_3m_spread": recent_3m_spread,
            "recent_effectiveness_score": effectiveness,
            "health_bucket": _health_bucket(effectiveness),
        })
    return pd.DataFrame(rows)


def _effectiveness_score(spread: float, ic: float) -> float:
    spread_part = 0.5 if pd.isna(spread) else 1 / (1 + np.exp(-spread * 25))
    ic_part = 0.5 if pd.isna(ic) else (np.clip(ic, -1, 1) + 1) / 2
    return float(np.clip(spread_part * 0.6 + ic_part * 0.4, 0, 1))


def _health_bucket(score: float) -> str:
    if pd.isna(score):
        return "insufficient"
    if score >= 0.65:
        return "effective"
    if score >= 0.45:
        return "neutral"
    return "weak"


def build_data_quality_report(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    cols = [
        "ticker", "period", "coverage_score", "factor_coverage_score", "data_freshness_score",
        "data_quality_penalty", "ticker_missing_rate", "missing_factor_count", "stale_penalty",
        "stale_factor_count", "stale_factor_flag", "source_failure_count", "source_failure_flag",
        "usable_for_trading_flag", "minute_usable_for_trading_flag", "confidence_score",
        "news_snapshot_date", "minute_snapshot_date", "target_snapshot_date",
        "news_age_days", "minute_age_days", "target_age_days",
        "news_stale_flag", "minute_stale_flag", "target_stale_flag",
    ]
    out = panel[[c for c in cols if c in panel.columns]].copy()
    if "factor_coverage_score" not in out.columns and "coverage_score" in out.columns:
        out = out.rename(columns={"coverage_score": "factor_coverage_score"})
    elif "coverage_score" in out.columns:
        out = out.drop(columns=["coverage_score"])
    for col in ["factor_coverage_score", "data_freshness_score", "confidence_score", "data_quality_penalty", "ticker_missing_rate", "stale_penalty"]:
        if col in out.columns:
            out[col] = _clip01(out[col])
    return out


def build_source_staleness_report(inputs: dict[str, pd.DataFrame], panel: pd.DataFrame, as_of_date: str | None = None) -> pd.DataFrame:
    as_of = pd.to_datetime(as_of_date or pd.Timestamp.today().strftime("%Y-%m-%d"), errors="coerce")
    latest_period = panel["period"].max() if not panel.empty and "period" in panel.columns else ""
    specs = [
        ("news", "뉴스감성", "factor_news_sentiment_snapshot", "latest_headline_date", SOURCE_STALE_RULES["news"]["allowed_lag_days"]),
        ("minute", "분봉 체결강도", "factor_minute_tick_snapshot", "trade_date", SOURCE_STALE_RULES["minute"]["allowed_lag_days"]),
        ("target_price", "목표주가 컨센서스", "factor_consensus_revision_snapshot", "snapshot_date", SOURCE_STALE_RULES["target_price"]["allowed_lag_days"]),
        ("momentum", "가격 모멘텀", "factor_stock_price_momentum_month", "period", 45),
        ("flow", "수급 모멘텀", "factor_investor_flow_momentum_month", "period", 45),
        ("valuation", "밸류에이션", "factor_valuation_per_pbr_month", "period", 45),
        ("sector_value", "가치/퀄리티", "factor_sector_relative_value_month", "period", 45),
        ("shorting", "공매도 압력", "factor_shorting_month", "period", 45),
    ]
    rows = []
    for key, label, table, date_col, allowed in specs:
        df = inputs.get(key, pd.DataFrame()).copy()
        row_count = int(len(df)) if df is not None else 0
        ticker_count = int(df["ticker"].astype(str).nunique()) if row_count and "ticker" in df.columns else 0
        latest = None
        age_days = np.nan
        stale = 1
        if row_count and date_col in df.columns:
            parsed = pd.to_datetime(df[date_col], errors="coerce")
            latest_ts = parsed.max()
            if pd.notna(latest_ts):
                # _month 팩터(period 컬럼)는 "YYYY-MM-01" 형태 → 해당 월 마지막 영업일 or 오늘 중 작은 값으로 표시
                if date_col == "period":
                    month_end = latest_ts + pd.offsets.MonthEnd(0)
                    bdates = pd.bdate_range(latest_ts, month_end)
                    last_bdate = bdates[-1] if len(bdates) > 0 else month_end
                    effective_ts = min(last_bdate, as_of) if pd.notna(as_of) else last_bdate
                else:
                    effective_ts = latest_ts
                latest = effective_ts.strftime("%Y-%m-%d")
                age_days = float((as_of - effective_ts).days) if pd.notna(as_of) else np.nan
                stale = int(age_days > allowed) if pd.notna(age_days) else 1
        source_failure = int(row_count == 0 or stale == 1)
        quality_score = float(np.clip(1 - (0.55 * stale + 0.45 * source_failure), 0, 1))
        rows.append({
            "source_key": key,
            "source_name": label,
            "table_name": table,
            "latest_date": latest or "",
            "latest_period": latest_period,
            "age_days": age_days,
            "allowed_lag_days": allowed,
            "row_count": row_count,
            "ticker_count": ticker_count,
            "latest_date_stale_flag": stale,
            "source_failure_flag": source_failure,
            "source_quality_score": quality_score,
            "guidance": _source_guidance(key, stale, source_failure),
        })
    return pd.DataFrame(rows)


def _source_guidance(key: str, stale: int, source_failure: int) -> str:
    if source_failure and key == "minute":
        return "당일 분봉 없음: minute factor 거래 사용 금지"
    if stale and key == "news":
        return "3일 초과 뉴스 미갱신: 감성 점수 영향 축소"
    if stale and key == "target_price":
        return "목표주가 스냅샷 노후: 신뢰도 하향"
    if source_failure:
        return "source failure 확인 필요"
    return "OK"


def build_catalog() -> pd.DataFrame:
    rows = [
        ("factor_master_month", "composite_score", "종목별 월간 팩터 종합점수", "존재하는 value/quality/momentum/flow/sentiment/macro 점수 가중평균"),
        ("factor_master_month", "confidence_score", "거래 활용 신뢰도", "coverage_score 70% + data_freshness_score 30%"),
        ("factor_master_month", "coverage_score", "핵심 팩터 커버리지", "사용 가능한 핵심 팩터 수 / 5"),
        ("factor_health_report", "recent_effectiveness_score", "최근 팩터 유효성", "최근 3개월 top-bottom spread와 rank IC 조합"),
        ("factor_health_report", "top_bottom_spread_mean", "상하위 분위 수익률 차이", "월별 상위 분위 평균 forward return - 하위 분위 평균"),
        ("factor_data_quality_month", "data_freshness_score", "스냅샷 신선도", "stale 스냅샷 비율 차감"),
        ("factor_data_quality_month", "factor_coverage_score", "종목별 팩터 커버리지", "사용 가능한 핵심 팩터 수 / 5"),
        ("factor_data_quality_month", "data_quality_penalty", "데이터 품질 페널티", "종목 결측률·스냅샷 노후화·source failure 합성 페널티"),
        ("factor_data_quality_month", "usable_for_trading_flag", "거래 활용 가능 플래그", "커버리지/신선도/분봉 사용 가능 조건 통과 여부"),
        ("factor_data_quality_month", "stale_factor_flag", "노후 데이터 플래그", "as_of 기준 7일 초과 스냅샷 존재 여부"),
        ("factor_source_staleness", "source_quality_score", "소스별 신뢰도", "최신일자 지연 및 source failure 기반 소스 품질 점수"),
        ("factor_master_month", "raw_composite_score", "품질 페널티 전 종합점수", "팩터 원점수 기반 종합점수"),
    ]
    return pd.DataFrame(rows, columns=["output_table", "factor_name", "description_kr", "formula"])


def _backup_db() -> Path | None:
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"quant_data_{stamp}_before_factor_master_phase1.sqlite"
    shutil.copy2(DB_PATH, backup)
    return backup


def run(as_of_date: str | None = None) -> dict[str, pd.DataFrame]:
    logger.info("팩터 마스터 패널 1단계 구축 시작")
    backup = _backup_db()
    if backup:
        logger.info("DB 백업 생성: %s", backup)
    with sqlite3.connect(DB_PATH) as conn:
        inputs = load_inputs(conn)
        panel = build_factor_master_panel(inputs, as_of_date=as_of_date)
        health = build_factor_health_report(panel)
        quality = build_data_quality_report(panel)
        source_staleness = build_source_staleness_report(inputs, panel, as_of_date=as_of_date)
        catalog = build_catalog()

        if panel.empty:
            raise RuntimeError("factor_master_month 산출 결과가 비어 있습니다")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        panel.to_csv(OUTPUT_DIR / "factor_master_month.csv", index=False, encoding="utf-8-sig")
        health.to_csv(OUTPUT_DIR / "factor_health_report.csv", index=False, encoding="utf-8-sig")
        quality.to_csv(OUTPUT_DIR / "factor_data_quality_month.csv", index=False, encoding="utf-8-sig")
        source_staleness.to_csv(OUTPUT_DIR / "factor_source_staleness.csv", index=False, encoding="utf-8-sig")
        catalog.to_csv(OUTPUT_DIR / "factor_master_catalog.csv", index=False, encoding="utf-8-sig")

        panel.to_sql("factor_master_month", conn, if_exists="replace", index=False)
        health.to_sql("factor_health_report", conn, if_exists="replace", index=False)
        quality.to_sql("factor_data_quality_month", conn, if_exists="replace", index=False)
        source_staleness.to_sql("factor_source_staleness", conn, if_exists="replace", index=False)
        catalog.to_sql("factor_master_catalog", conn, if_exists="replace", index=False)
        conn.commit()

    logger.info(
        "완료: factor_master_month %d행(%s~%s), factor_health_report %d행, factor_data_quality_month %d행, factor_source_staleness %d행",
        len(panel), panel["period"].min(), panel["period"].max(), len(health), len(quality), len(source_staleness),
    )
    return {"panel": panel, "health": health, "quality": quality, "source_staleness": source_staleness, "catalog": catalog}


if __name__ == "__main__":
    outputs = run()
    panel = outputs["panel"]
    print("\n=== factor_master_month 검증 ===")
    print(f"rows={len(panel):,}, period={panel['period'].min()}~{panel['period'].max()}, tickers={panel['ticker'].nunique():,}")
    print(panel.sort_values(["period", "composite_score"], ascending=[False, False]).head(10)[
        ["period", "ticker", "name", "composite_score", "confidence_score", "coverage_score", "stale_factor_flag"]
    ].to_string(index=False))
