import math
from pathlib import Path
import sys

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts" / "03_analyze"))

import build_practical_topn_backtest as bt


def _sample_panel():
    rows = []
    periods = ["2024-01", "2024-02", "2024-03", "2024-04"]
    for p_idx, period in enumerate(periods):
        for i in range(1, 7):
            rows.append({
                "period": period,
                "ticker": f"T{i:03d}",
                "name": f"종목{i}",
                "sector": "테스트",
                "market_cap": 1000 - i,
                "size_bucket": "large" if i <= 3 else "mid",
                "project_universe_b": True,
                "kospi200_proxy": i <= 4,
                "all_listed_screenable": True,
                "market_attractiveness_score": 1.0 - i * 0.05 + p_idx * 0.01,
                "scenario_a_momentum": 1.0 - i * 0.04,
                "scenario_b_value_quality": 1.0 - i * 0.03,
                "scenario_c_reversal": 1.0 - i * 0.02,
                "scenario_d_large_stable": 1.0 - i * 0.01,
                "fwd_1m_ret": 0.10 if i <= 2 else -0.02,
            })
    return pd.DataFrame(rows)


def test_max_drawdown_and_cagr_are_path_based():
    nav = pd.Series([1.0, 1.2, 0.9, 1.35])
    assert round(bt.max_drawdown(nav), 4) == -0.25
    assert bt.calc_cagr(pd.Series([1.0] * 12 + [1.12])) > 0


def test_simulate_monthly_topn_applies_turnover_cost():
    panel = _sample_panel()
    gross, _ = bt.simulate_monthly_topn(panel, "market_attractiveness_score", 2, "B_PROJECT_DEFAULT", 0.0)
    costly, sel = bt.simulate_monthly_topn(panel, "market_attractiveness_score", 2, "B_PROJECT_DEFAULT", 0.01)
    assert len(gross) == 4
    assert len(sel) == 8
    assert costly.iloc[0]["net_return"] == gross.iloc[0]["gross_return"] - 0.01
    assert costly["nav"].iloc[-1] < gross["nav"].iloc[-1]
    assert (gross["hit_ratio"] == 1.0).all()


def test_summary_contains_practical_metrics():
    panel = _sample_panel()
    monthly, _ = bt.simulate_monthly_topn(panel, "market_attractiveness_score", 2, "B_PROJECT_DEFAULT", 0.003)
    summary = bt.summarize_monthly(monthly)
    row = summary.iloc[0]
    for col in ["total_return", "benchmark_total_return", "excess_total_return", "mdd", "monthly_win_rate", "avg_turnover", "sharpe_like"]:
        assert col in summary.columns
        assert row[col] == row[col] or math.isnan(row[col])
    assert row["months"] == 4
    assert row["topn"] == 2


def test_build_backtest_respects_universe_labels(monkeypatch):
    panel = _sample_panel()
    monkeypatch.setattr(bt, "TOPN_VALUES", [2])
    monkeypatch.setattr(bt, "COST_RATES", [0.0])
    monkeypatch.setattr(bt, "UNIVERSES", ["A_KOSPI200_PROXY", "B_PROJECT_DEFAULT", "D_LARGE"])
    summary, monthly, selections, coverage = bt.build_backtest(panel)
    assert set(summary["universe"]) == {"A_KOSPI200_PROXY", "B_PROJECT_DEFAULT", "D_LARGE"}
    assert not monthly.empty
    assert not selections.empty
    assert set(["b_project_default", "a_kospi200_proxy", "valid_forward_return"]).issubset(coverage.columns)
