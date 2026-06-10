import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_module(path: Path, name: str = "momentum_mod"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load():
    project = Path(__file__).resolve().parents[1]
    return load_module(project / "scripts" / "03_analyze" / "build_stock_price_momentum_factors.py")


def _make_monthly_panel(mod, n_months=15):
    periods = pd.date_range("2025-01-01", periods=n_months, freq="MS")
    rows = []
    # UP: 꾸준히 상승, 거래대금 최근 급증 / DOWN: 꾸준히 하락, 거래대금 평이
    rng = np.random.default_rng(42)
    for ticker, base_close, drift, turnover_spike in [("UP", 100.0, 0.05, True), ("DOWN", 100.0, -0.04, False)]:
        close = base_close
        for i, period in enumerate(periods):
            close = close * (1 + drift)
            turnover = 1_000_000.0 * (1 + rng.normal(0, 0.05))  # 약간의 변동성을 줘서 std=0 방지
            if turnover_spike and i == n_months - 1:
                turnover = 5_000_000.0
            rows.append({
                "ticker": ticker, "period": period, "close": close,
                "month_avg_turnover_value": turnover, "month_volatility": 0.02, "trading_days": 20,
            })
    return pd.DataFrame(rows)


def test_mom_12_1_uses_lookback_minus_skip_window():
    mod = _load()
    panel = _make_monthly_panel(mod)
    out = mod.add_momentum_factors(panel)
    up_last = out[out["ticker"] == "UP"].iloc[-1]
    down_last = out[out["ticker"] == "DOWN"].iloc[-1]
    assert up_last["mom_12_1"] > 0
    assert down_last["mom_12_1"] < 0
    assert up_last["mom_12_1"] > down_last["mom_12_1"]


def test_turnover_zscore_flags_recent_spike():
    mod = _load()
    panel = _make_monthly_panel(mod)
    out = mod.add_momentum_factors(panel)
    up_last = out[out["ticker"] == "UP"].iloc[-1]
    down_last = out[out["ticker"] == "DOWN"].iloc[-1]
    assert up_last["turnover_zscore_own"] > down_last["turnover_zscore_own"]
    assert up_last["turnover_zscore_own"] > 1.0


def test_momentum_score_ranks_uptrend_above_downtrend():
    mod = _load()
    panel = _make_monthly_panel(mod)
    out = mod.add_momentum_factors(panel)
    out = mod.add_momentum_score(out)
    up_last = out[out["ticker"] == "UP"].iloc[-1]
    down_last = out[out["ticker"] == "DOWN"].iloc[-1]
    assert up_last["momentum_score"] > down_last["momentum_score"]
    assert up_last["turnover_spike_flag"] == True or up_last["turnover_spike_flag"] is np.True_
    assert down_last["turnover_spike_flag"] == False or down_last["turnover_spike_flag"] is np.False_


def test_momentum_percentile_requires_minimum_universe_size():
    mod = _load()
    small = pd.DataFrame({
        "ticker": ["A", "B", "C"],
        "period": [pd.Timestamp("2026-01-01")] * 3,
        "close": [100, 200, 300],
        "month_avg_turnover_value": [1e6, 1e6, 1e6],
        "month_volatility": [0.02, 0.02, 0.02],
        "trading_days": [20, 20, 20],
    })
    out = mod.add_momentum_factors(small)
    assert out["momentum_percentile_cross"].isna().all()


def test_factor_catalog_has_expected_shape():
    mod = _load()
    catalog = mod.build_factor_catalog()
    assert set(catalog.columns) == {
        "factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use",
    }
    assert (catalog["factor_family"] == "stock_price_momentum").all()
    assert len(catalog) >= 4
