import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_module(path: Path, name: str = "dart_event_mod"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load():
    project = Path(__file__).resolve().parents[1]
    return load_module(project / "scripts" / "03_analyze" / "build_dart_event_signal_factors.py")


def _make_events(n_months=8):
    periods = pd.date_range("2025-07-01", periods=n_months, freq="MS")
    rows = []
    # ACTIVE: 매달 자사주+배당 공시가 있고, 마지막 달에 내부자 신고가 평소보다 급증
    # QUIET: 이벤트가 전혀 없음
    for i, period in enumerate(periods):
        rows.append({"ticker": "ACTIVE", "rcept_dt": period, "event_type": "buyback"})
        rows.append({"ticker": "ACTIVE", "rcept_dt": period, "event_type": "dividend"})
        insider_count = 1 if i < n_months - 1 else 6  # 마지막 달에 급증
        for _ in range(insider_count):
            rows.append({"ticker": "ACTIVE", "rcept_dt": period, "event_type": "insider"})
    return pd.DataFrame(rows)


def _tickers():
    return ["ACTIVE", "QUIET"]


def test_monthly_panel_fills_zero_for_tickers_without_events():
    mod = _load()
    events = _make_events()
    monthly = mod.build_monthly_panel(events, _tickers())
    quiet = monthly[monthly["ticker"] == "QUIET"]
    assert (quiet["total_count"] == 0).all()
    assert (quiet["buyback_count"] == 0).all()


def test_event_flag_is_true_only_when_count_positive():
    mod = _load()
    events = _make_events()
    monthly = mod.build_monthly_panel(events, _tickers())
    out = mod.add_event_factors(monthly)
    active = out[out["ticker"] == "ACTIVE"]
    quiet = out[out["ticker"] == "QUIET"]
    assert (active["buyback_event_flag"]).all()
    assert not (quiet["buyback_event_flag"]).any()


def test_insider_zscore_flags_unusual_spike():
    mod = _load()
    events = _make_events()
    monthly = mod.build_monthly_panel(events, _tickers())
    out = mod.add_event_factors(monthly)
    active_last = out[out["ticker"] == "ACTIVE"].iloc[-1]
    zscore_col = f"insider_count_zscore_own_{mod.OWN_HISTORY_WINDOW}m"
    assert active_last[zscore_col] > 1.5


def test_zscore_returns_nan_when_std_zero():
    mod = _load()
    events = pd.DataFrame({
        "ticker": ["FLAT"] * 6,
        "rcept_dt": pd.date_range("2025-07-01", periods=6, freq="MS"),
        "event_type": ["buyback"] * 6,
    })
    monthly = mod.build_monthly_panel(events, ["FLAT"])
    out = mod.add_event_factors(monthly)
    col = f"buyback_count_zscore_own_{mod.OWN_HISTORY_WINDOW}m"
    assert out[col].isna().all()  # 항상 1건씩 → 표준편차 0 → 임의 보간하지 않고 N/A 유지


def test_event_score_prefers_active_over_quiet_and_catalog_documents_caveat():
    mod = _load()
    events = _make_events()
    monthly = mod.build_monthly_panel(events, _tickers())
    out = mod.add_event_factors(monthly)
    out = mod.add_event_score(out)
    active_last = out[out["ticker"] == "ACTIVE"].iloc[-1]
    quiet_last = out[out["ticker"] == "QUIET"].iloc[-1]
    assert active_last["event_activity_score"] > quiet_last["event_activity_score"]
    assert active_last["event_activity_bucket"] in {"high_activity", "elevated_activity"}

    catalog = mod.build_factor_catalog()
    assert set(catalog.columns) == {
        "factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use",
    }
    assert (catalog["factor_family"] == "dart_event_signal").all()
    # 매수/매도 방향을 구분하지 못한다는 한계가 catalog에 명시되어야 한다 (데이터 투명성)
    joined = " ".join(catalog["interpretation"].tolist())
    assert "매수" in joined and "방향" in joined
