import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_module(path: Path, name: str = "flow_mod"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load():
    project = Path(__file__).resolve().parents[1]
    return load_module(project / "scripts" / "03_analyze" / "build_investor_flow_momentum_factors.py")


def _make_monthly_panel(mod, n_months=8):
    periods = pd.date_range("2025-07-01", periods=n_months, freq="MS")
    rows = []
    rng = np.random.default_rng(7)
    # INFLOW: 외국인 순매수 강도가 꾸준히 우상향 / OUTFLOW: 꾸준히 순매도 우위
    for ticker, base_ratio, drift in [("INFLOW", 0.0, 0.01), ("OUTFLOW", 0.0, -0.01)]:
        ratio = base_ratio
        for i, period in enumerate(periods):
            ratio = ratio + drift + rng.normal(0, 0.001)
            rows.append({
                "ticker": ticker, "period": period, "close": 50000.0,
                "volume_sum": 1_000_000.0, "foreign_net_sum": ratio * 1_000_000.0,
                "inst_net_sum": ratio * 0.5 * 1_000_000.0,
                "foreign_net_ratio": ratio, "inst_net_ratio": ratio * 0.5,
                "foreign_ratio_pct": 30.0 + i * (0.3 if ticker == "INFLOW" else -0.3),
                "trading_days": 20,
            })
    return pd.DataFrame(rows)


def test_flow_factors_change_uses_lag_window():
    mod = _load()
    panel = _make_monthly_panel(mod)
    out = mod.add_flow_factors(panel)
    inflow_last = out[out["ticker"] == "INFLOW"].iloc[-1]
    outflow_last = out[out["ticker"] == "OUTFLOW"].iloc[-1]
    assert inflow_last["foreign_net_ratio_change"] > 0
    assert outflow_last["foreign_net_ratio_change"] < 0


def test_zscore_returns_nan_when_std_zero():
    mod = _load()
    flat = pd.DataFrame({
        "ticker": ["FLAT"] * 6,
        "period": pd.date_range("2025-07-01", periods=6, freq="MS"),
        "foreign_net_ratio": [0.01] * 6,
        "inst_net_ratio": [0.01] * 6,
        "foreign_ratio_pct": [30.0] * 6,
    })
    out = mod.add_flow_factors(flat)
    col = f"foreign_net_ratio_zscore_own_{mod.OWN_HISTORY_WINDOW}m"
    assert out[col].isna().all()  # 표준편차 0 → 임의 보간하지 않고 N/A 유지


def test_flow_score_prefers_inflow_over_outflow():
    mod = _load()
    panel = _make_monthly_panel(mod)
    out = mod.add_flow_factors(panel)
    out = mod.add_flow_score(out)
    inflow_last = out[out["ticker"] == "INFLOW"].iloc[-1]
    outflow_last = out[out["ticker"] == "OUTFLOW"].iloc[-1]
    assert inflow_last["flow_score"] > outflow_last["flow_score"]
    assert inflow_last["flow_direction"] == "net_buying"
    assert outflow_last["flow_direction"] == "net_selling"


def test_cross_sectional_percentile_requires_minimum_universe():
    mod = _load()
    small = pd.DataFrame({
        "ticker": ["A", "B", "C"],
        "period": [pd.Timestamp("2026-01-01")] * 3,
        "foreign_net_ratio": [0.01, 0.02, -0.01],
        "inst_net_ratio": [0.0, 0.0, 0.0],
        "foreign_ratio_pct": [10.0, 20.0, 30.0],
    })
    out = mod.add_flow_factors(small)
    assert out["foreign_net_ratio_percentile_cross"].isna().all()


def test_factor_catalog_has_expected_shape():
    mod = _load()
    catalog = mod.build_factor_catalog()
    assert set(catalog.columns) == {
        "factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use",
    }
    assert (catalog["factor_family"] == "investor_flow_momentum").all()
    assert len(catalog) >= 4
