import importlib.util
from pathlib import Path

import pandas as pd


def load_module(path: Path, name: str = "regime_mod"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_classify_market_regime_labels_risk_on_and_risk_off():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "03_analyze" / "build_market_regime_adjusted_signals.py")
    df = pd.DataFrame(
        {
            "period": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "risk_off_composite_z": [-0.6, 1.4, 0.2],
            "vix_zscore_252d": [-0.2, 1.2, 0.1],
            "dxy_zscore_252d": [-0.1, 1.3, 1.2],
            "us_sp500_ret_60d_pct": [4.0, -3.0, 1.0],
            "korea_kospi_ret_60d_pct": [3.0, -4.0, 0.5],
            "korea_kosdaq_ret_60d_pct": [5.0, -6.0, 2.0],
            "korea_exports_yoy_pct": [8.0, -5.0, 4.0],
        }
    )
    out = mod.classify_market_regime(df)
    assert out.loc[0, "market_regime"] == "risk_on"
    assert out.loc[1, "market_regime"] == "risk_off"
    assert out.loc[2, "dollar_pressure_flag"] is True


def test_adjust_interest_signal_discounts_risk_off_and_rewards_risk_on():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "03_analyze" / "build_market_regime_adjusted_signals.py")
    base = pd.DataFrame(
        {
            "period": ["2026-01-01", "2026-01-01"],
            "group_name": ["semiconductor", "semiconductor"],
            "anchor_relative_ratio_winsorized": [10.0, 10.0],
            "anchor_relative_momentum_3m": [1.0, 1.0],
            "ratio_zscore_12m": [0.5, 0.5],
            "relative_rank_pct": [0.8, 0.8],
            "data_quality_score": [100, 100],
            "market_regime": ["risk_on", "risk_off"],
            "risk_off_score": [0.0, 2.0],
            "growth_on_flag": [True, False],
            "export_recovery_flag": [True, False],
        }
    )
    out = mod.adjust_interest_signals(base)
    assert out.loc[0, "regime_adjusted_interest_score"] > out.loc[1, "regime_adjusted_interest_score"]
    assert out.loc[0, "regime_adjusted_bucket"] in {"strong", "very_strong"}
    assert out.loc[1, "risk_discount_applied"] is True


def test_build_factor_catalog_contains_interest_regime_interactions():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "03_analyze" / "build_market_regime_adjusted_signals.py")
    catalog = mod.build_factor_catalog()
    assert set(catalog["factor_family"]) == {"market_macro_regime", "regime_adjusted_interest"}
    assert "regime_adjusted_interest_score" in set(catalog["factor_name"])
    assert "market_regime" in set(catalog["factor_name"])
