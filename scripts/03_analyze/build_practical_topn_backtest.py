#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""실전형 월간 리밸런싱 TopN 백테스트 산출물 생성.

- 신호: 월말 t 시점의 월간 factor 테이블만 사용
- 수익률: 다음 월 close(t+1) / close(t) - 1
- 포트폴리오: 동일가중 Top20/30/50, 월간 리밸런싱
- 비용: turnover * cost_rate 차감. cost_rate는 월간 교체분에 대한 총 비용률(수수료/세금/슬리피지 합산 가정)

주의: KOSPI200/KOSDAQ150 공식 구성 이력이 없으므로 월별 시총 순위 proxy를 사용한다.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = PROJECT_DIR.parents[1]
DB_PATH = PROJECT_DIR / "data" / "database" / "quant_data.sqlite"
OUTPUT_ROOT = WORKSPACE_DIR / "02_outputs"

SCENARIOS = {
    "market_attractiveness_score": {
        "label": "종합 매력도",
        "components": ["scenario_a_momentum", "scenario_b_value_quality", "scenario_c_reversal", "scenario_d_large_stable"],
    },
    "scenario_a_momentum": {
        "label": "A 단기 모멘텀",
        "components": ["momentum_score", "flow_score", "liquidity_score"],
    },
    "scenario_b_value_quality": {
        "label": "B 가치+퀄리티",
        "components": ["valuation_score", "sector_value_rank_score", "roe_score", "quality_score"],
    },
    "scenario_c_reversal": {
        "label": "C 저평가 반등",
        "components": ["valuation_score", "reversal_score", "flow_score"],
    },
    "scenario_d_large_stable": {
        "label": "D 대형 안정",
        "components": ["large_stable_score", "liquidity_score", "quality_score"],
    },
}

TOPN_VALUES = [20, 30, 50]
COST_RATES = [0.0, 0.003, 0.006]
UNIVERSES = ["A_KOSPI200_PROXY", "B_PROJECT_DEFAULT", "C_SCREENABLE", "D_LARGE", "D_MID", "D_SMALL"]


def _read_sql(con: sqlite3.Connection, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, con)


def _rank_score(s: pd.Series, ascending: bool = True) -> pd.Series:
    """월별 cross-section percentile score. 높을수록 좋게 반환."""
    if s.notna().sum() <= 1:
        return pd.Series(np.nan, index=s.index)
    pct = s.rank(pct=True, ascending=ascending, method="average")
    return pct.astype(float)


def _mean_available(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    existing = [c for c in cols if c in df.columns]
    if not existing:
        return pd.Series(np.nan, index=df.index)
    return df[existing].mean(axis=1, skipna=True)


def _load_panel(db_path: Path = DB_PATH) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    try:
        momentum = _read_sql(con, """
            SELECT ticker, period, close, ret_1m, ret_3m, ret_6m, ret_12m, momentum_score, month_avg_turnover_value, month_volatility
            FROM factor_stock_price_momentum_month
        """)
        size = _read_sql(con, """
            SELECT ticker, period, sector, market_cap, size_percentile_cross, size_bucket, small_cap_score
            FROM factor_size_month
        """)
        liquidity = _read_sql(con, """
            SELECT ticker, period, turnover_value_avg, turnover_ratio, liquidity_score
            FROM factor_liquidity_turnover_month
        """)
        valuation = _read_sql(con, """
            SELECT ticker, period, PER, PBR, per_percentile_sector, pbr_percentile_sector, valuation_score, rerating_momentum_score
            FROM factor_valuation_per_pbr_month
        """)
        sector_value = _read_sql(con, """
            SELECT ticker, period, value_quality_score, sector_value_zscore, sector_relative_per, sector_relative_pbr,
                   balance_sheet_quality_score, cashflow_quality_score, earnings_stability_score, fcf_to_assets, debt_ratio, financial_quality_score
            FROM factor_sector_relative_value_month
        """)
        roe = _read_sql(con, """
            SELECT ticker, period, roe, roe_sector_pct_ts
            FROM factor_roe_trend_month
        """)
        flow = _read_sql(con, """
            SELECT ticker, period, flow_score, foreign_net_ratio, inst_net_ratio
            FROM factor_investor_flow_momentum_month
        """)
        names_tables = _read_sql(con, """
            SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_market_snapshot_ticker_names_%' ORDER BY name DESC LIMIT 1
        """)
        names = pd.DataFrame(columns=["ticker", "name", "market"])
        if not names_tables.empty:
            t = names_tables.iloc[0]["name"]
            names = _read_sql(con, f'SELECT ticker, name, market FROM "{t}"')
    finally:
        con.close()

    panel = momentum.copy()
    for df in [size, liquidity, valuation, sector_value, roe, flow]:
        panel = panel.merge(df, on=["ticker", "period"], how="left")
    if not names.empty:
        panel = panel.merge(names.drop_duplicates("ticker"), on="ticker", how="left")

    panel["period"] = pd.to_datetime(panel["period"]).dt.to_period("M").astype(str)
    panel = panel.sort_values(["ticker", "period"])
    panel["fwd_1m_ret"] = panel.groupby("ticker")["close"].shift(-1) / panel["close"] - 1

    # 월별 proxy universe: 시총 순위 기반. 공식 구성 이력 아님.
    panel["market_cap_rank_month"] = panel.groupby("period")["market_cap"].rank(ascending=False, method="first")
    panel["project_universe_b"] = panel["market_cap_rank_month"] <= 350
    panel["kospi200_proxy"] = panel["market_cap_rank_month"] <= 200
    panel["all_listed_screenable"] = (
        panel["market_cap"].notna()
        & panel["close"].notna()
        & panel["fwd_1m_ret"].notna()
        & (panel.get("turnover_value_avg", pd.Series(0, index=panel.index)).fillna(0) > 0)
    )

    # 월별 상대 점수. 모든 점수는 높을수록 좋음.
    grouped = panel.groupby("period", group_keys=False)
    panel["market_cap_score"] = grouped["market_cap"].transform(lambda s: _rank_score(s, ascending=True))
    panel["large_stable_score"] = grouped["market_cap"].transform(lambda s: _rank_score(s, ascending=True))
    panel["sector_value_rank_score"] = grouped["sector_value_zscore"].transform(lambda s: _rank_score(s, ascending=False))
    panel["roe_score"] = grouped["roe"].transform(lambda s: _rank_score(s, ascending=True))
    panel["quality_score"] = _mean_available(panel, ["value_quality_score", "balance_sheet_quality_score", "cashflow_quality_score", "earnings_stability_score"])
    panel["reversal_score"] = _mean_available(panel, ["rerating_momentum_score", "sector_value_rank_score", "valuation_score"])

    for key, spec in SCENARIOS.items():
        if key == "market_attractiveness_score":
            continue
        panel[key] = _mean_available(panel, spec["components"])
    panel["market_attractiveness_score"] = _mean_available(panel, SCENARIOS["market_attractiveness_score"]["components"])

    return panel


def filter_universe(panel: pd.DataFrame, universe: str) -> pd.DataFrame:
    if universe == "A_KOSPI200_PROXY":
        return panel[panel["kospi200_proxy"]].copy()
    if universe == "B_PROJECT_DEFAULT":
        return panel[panel["project_universe_b"]].copy()
    if universe == "C_SCREENABLE":
        return panel[panel["all_listed_screenable"]].copy()
    if universe == "D_LARGE":
        return panel[panel["size_bucket"].eq("large")].copy()
    if universe == "D_MID":
        return panel[panel["size_bucket"].eq("mid")].copy()
    if universe == "D_SMALL":
        return panel[panel["size_bucket"].eq("small")].copy()
    raise ValueError(f"unknown universe: {universe}")


def max_drawdown(nav: pd.Series) -> float:
    if nav.empty:
        return float("nan")
    peak = nav.cummax()
    dd = nav / peak - 1
    return float(dd.min())


def calc_cagr(nav: pd.Series) -> float:
    if len(nav) < 2:
        return float("nan")
    years = len(nav) / 12.0
    if years <= 0 or nav.iloc[0] <= 0 or nav.iloc[-1] <= 0:
        return float("nan")
    return float(nav.iloc[-1] ** (1 / years) - 1)


def simulate_monthly_topn(
    panel: pd.DataFrame,
    scenario: str,
    topn: int,
    universe: str,
    cost_rate: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = filter_universe(panel, universe)
    rows = rows[rows[scenario].notna() & rows["fwd_1m_ret"].notna()].copy()
    monthly = []
    selections = []
    prev_set: set[str] = set()
    nav = 1.0
    bench_nav = 1.0
    for period, g in rows.groupby("period", sort=True):
        ranked = g.sort_values([scenario, "market_cap"], ascending=[False, False]).head(topn).copy()
        min_required = min(topn, 5)
        if len(ranked) < min_required:
            continue
        current_set = set(ranked["ticker"].astype(str))
        overlap = len(current_set & prev_set) / topn if prev_set else 0.0
        turnover = 1.0 - overlap if prev_set else 1.0
        gross_ret = float(ranked["fwd_1m_ret"].mean())
        net_ret = gross_ret - cost_rate * turnover
        bench_ret = float(g["fwd_1m_ret"].mean())
        nav *= 1 + net_ret
        bench_nav *= 1 + bench_ret
        hit_ratio = float((ranked["fwd_1m_ret"] > 0).mean())
        monthly.append({
            "period": period,
            "scenario": scenario,
            "scenario_label": SCENARIOS[scenario]["label"],
            "topn": topn,
            "universe": universe,
            "cost_rate": cost_rate,
            "selected_count": int(len(ranked)),
            "gross_return": gross_ret,
            "net_return": net_ret,
            "benchmark_return": bench_ret,
            "excess_return": net_ret - bench_ret,
            "turnover": turnover,
            "hit_ratio": hit_ratio,
            "nav": nav,
            "benchmark_nav": bench_nav,
            "excess_nav": nav / bench_nav if bench_nav else np.nan,
        })
        for rank, (_, r) in enumerate(ranked.iterrows(), start=1):
            selections.append({
                "period": period,
                "scenario": scenario,
                "scenario_label": SCENARIOS[scenario]["label"],
                "topn": topn,
                "universe": universe,
                "cost_rate": cost_rate,
                "rank": rank,
                "ticker": r.get("ticker"),
                "name": r.get("name"),
                "sector": r.get("sector"),
                "score": r.get(scenario),
                "fwd_1m_ret": r.get("fwd_1m_ret"),
                "market_cap": r.get("market_cap"),
            })
        prev_set = current_set
    return pd.DataFrame(monthly), pd.DataFrame(selections)


def summarize_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    out = []
    if monthly.empty:
        return pd.DataFrame()
    keys = ["scenario", "scenario_label", "topn", "universe", "cost_rate"]
    for key, g in monthly.groupby(keys, sort=True):
        g = g.sort_values("period")
        nav = g["nav"].astype(float)
        bench = g["benchmark_nav"].astype(float)
        monthly_std = float(g["net_return"].std(ddof=0)) if len(g) else np.nan
        out.append({
            "scenario": key[0],
            "scenario_label": key[1],
            "topn": key[2],
            "universe": key[3],
            "cost_rate": key[4],
            "months": int(len(g)),
            "start_period": str(g["period"].iloc[0]),
            "end_period": str(g["period"].iloc[-1]),
            "total_return": float(nav.iloc[-1] - 1),
            "benchmark_total_return": float(bench.iloc[-1] - 1),
            "excess_total_return": float(nav.iloc[-1] / bench.iloc[-1] - 1) if bench.iloc[-1] else np.nan,
            "cagr": calc_cagr(nav),
            "benchmark_cagr": calc_cagr(bench),
            "avg_monthly_return": float(g["net_return"].mean()),
            "avg_benchmark_return": float(g["benchmark_return"].mean()),
            "avg_excess_return": float(g["excess_return"].mean()),
            "monthly_win_rate": float((g["excess_return"] > 0).mean()),
            "hit_ratio": float(g["hit_ratio"].mean()),
            "avg_turnover": float(g["turnover"].mean()),
            "mdd": max_drawdown(nav),
            "benchmark_mdd": max_drawdown(bench),
            "volatility_annualized": monthly_std * math.sqrt(12) if not math.isnan(monthly_std) else np.nan,
            "sharpe_like": (float(g["net_return"].mean()) / monthly_std * math.sqrt(12)) if monthly_std and not math.isnan(monthly_std) else np.nan,
        })
    return pd.DataFrame(out)


def build_backtest(panel: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if panel is None:
        panel = _load_panel()
    monthly_parts = []
    selection_parts = []
    scenarios = list(SCENARIOS.keys())
    for universe in UNIVERSES:
        for scenario in scenarios:
            for topn in TOPN_VALUES:
                for cost_rate in COST_RATES:
                    m, s = simulate_monthly_topn(panel, scenario, topn, universe, cost_rate)
                    if not m.empty:
                        monthly_parts.append(m)
                    if not s.empty:
                        selection_parts.append(s)
    monthly = pd.concat(monthly_parts, ignore_index=True) if monthly_parts else pd.DataFrame()
    selections = pd.concat(selection_parts, ignore_index=True) if selection_parts else pd.DataFrame()
    summary = summarize_monthly(monthly)
    coverage = panel.groupby("period").agg(
        total_rows=("ticker", "count"),
        b_project_default=("project_universe_b", "sum"),
        a_kospi200_proxy=("kospi200_proxy", "sum"),
        c_screenable=("all_listed_screenable", "sum"),
        valid_forward_return=("fwd_1m_ret", lambda s: int(s.notna().sum())),
        valid_market_attractiveness=("market_attractiveness_score", lambda s: int(s.notna().sum())),
    ).reset_index()
    return summary, monthly, selections, coverage


def _write_report(out_dir: Path, summary: pd.DataFrame, monthly: pd.DataFrame, selections: pd.DataFrame, coverage: pd.DataFrame) -> None:
    best = pd.DataFrame()
    if not summary.empty:
        base = summary[(summary["universe"] == "B_PROJECT_DEFAULT") & (summary["cost_rate"] == 0.003)].copy()
        if not base.empty:
            best = base.sort_values(["excess_total_return", "mdd"], ascending=[False, False]).head(10)
    lines = [
        "# 실전형 월간 리밸런싱 TopN 백테스트",
        "",
        "## 결론",
        "- 월말 신호로 다음 달 수익률을 검증하는 월간 리밸런싱 NAV 백테스트를 생성했습니다.",
        "- 공식 KOSPI200/KOSDAQ150 구성 이력이 아니라 월별 시총 순위 proxy를 사용하므로, 결과는 실전 검증용 1차 근사치입니다.",
        "- 비용은 turnover × cost_rate 방식으로 0%, 0.3%, 0.6%를 비교했습니다.",
        "",
        "## 산출물",
        f"- summary_practical_topn.csv: {len(summary):,} rows",
        f"- monthly_practical_topn_returns.csv: {len(monthly):,} rows",
        f"- monthly_practical_topn_selections.csv: {len(selections):,} rows",
        f"- coverage_by_period.csv: {len(coverage):,} rows",
        "",
    ]
    if not best.empty:
        lines += ["## B 기본 유니버스·비용 0.3% 기준 상위 조합", ""]
        cols = ["scenario_label", "topn", "months", "total_return", "benchmark_total_return", "excess_total_return", "mdd", "monthly_win_rate", "avg_turnover"]
        lines.append(best[cols].to_markdown(index=False))
        lines.append("")
    lines += [
        "## 해석 주의",
        "- `signal at month t → fwd_1m_ret at t+1` 구조로 look-ahead를 줄였지만, 일부 재무/컨센서스 팩터의 실제 공시 가능 시차는 추가 보수 조정이 필요합니다.",
        "- 거래비용은 단순 비용률 모델입니다. 호가충격/상한가/거래정지/체결 가능성은 아직 반영하지 않았습니다.",
        "- B 기본은 프로젝트 정책상 기본값이지만 여기서는 월별 시총 상위 350 proxy입니다.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    panel = _load_panel(args.db)
    summary, monthly, selections, coverage = build_backtest(panel)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = args.output_dir or (OUTPUT_ROOT / f"{ts}_practical_topn_backtest")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary.to_csv(out_dir / "summary_practical_topn.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(out_dir / "monthly_practical_topn_returns.csv", index=False, encoding="utf-8-sig")
    selections.to_csv(out_dir / "monthly_practical_topn_selections.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(out_dir / "coverage_by_period.csv", index=False, encoding="utf-8-sig")
    panel.to_csv(out_dir / "panel_snapshot_used.csv", index=False, encoding="utf-8-sig")
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "db_path": str(args.db),
        "scenarios": SCENARIOS,
        "topn_values": TOPN_VALUES,
        "cost_rates": COST_RATES,
        "universes": UNIVERSES,
        "method": "월말 신호 TopN 동일가중 월간 리밸런싱 NAV; fwd_1m_ret 사용; 비용=turnover*cost_rate; universe는 월별 시총 proxy",
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(out_dir, summary, monthly, selections, coverage)

    print(json.dumps({
        "output_dir": str(out_dir),
        "summary_rows": int(len(summary)),
        "monthly_rows": int(len(monthly)),
        "selection_rows": int(len(selections)),
        "coverage_rows": int(len(coverage)),
        "period_min": str(coverage["period"].min()) if not coverage.empty else "",
        "period_max": str(coverage["period"].max()) if not coverage.empty else "",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
