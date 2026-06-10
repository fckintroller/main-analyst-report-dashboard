"""단위 테스트: build_shorting_factors.py"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "short_mod",
        _root() / "scripts" / "03_analyze" / "build_shorting_factors.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_monthly(ticker: str, periods: list[str], ratios: list[float], sector: str = "섹터A") -> pd.DataFrame:
    return pd.DataFrame({
        "ticker": ticker,
        "period": periods,
        "balance": [r * 1000000 for r in ratios],
        "balance_ratio": ratios,
        "sector": sector,
    })


# ─── 1. 1개월 변화 계산 ──────────────────────────────────────

def test_balance_ratio_1m_chg():
    mod = _load()
    periods = ["2026-01-01", "2026-02-01", "2026-03-01"]
    df = _make_monthly("A001", periods, [1.0, 1.5, 1.2])
    result = mod.add_momentum(df)
    assert result.loc[result["period"] == "2026-02-01", "balance_ratio_1m_chg"].iloc[0] == pytest.approx(0.5, abs=0.001)
    assert result.loc[result["period"] == "2026-03-01", "balance_ratio_1m_chg"].iloc[0] == pytest.approx(-0.3, abs=0.001)


# ─── 2. 3개월 변화 계산 ──────────────────────────────────────

def test_balance_ratio_3m_chg():
    mod = _load()
    periods = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    df = _make_monthly("A001", periods, [1.0, 1.5, 2.0, 1.3])
    result = mod.add_momentum(df)
    val = result.loc[result["period"] == "2026-04-01", "balance_ratio_3m_chg"].iloc[0]
    assert val == pytest.approx(0.3, abs=0.001)


# ─── 3. 전 시장 백분위 ───────────────────────────────────────

def test_cross_sectional_percentile():
    mod = _load()
    # 같은 기간 4종목, 잔고율 1,2,3,4%
    periods = ["2026-06-01"] * 4
    rows = []
    for i, ratio in enumerate([1.0, 2.0, 3.0, 4.0]):
        rows.append({
            "ticker": f"T{i}", "period": "2026-06-01",
            "balance": ratio * 1e6, "balance_ratio": ratio, "sector": "섹터A"
        })
    df = pd.DataFrame(rows)
    df = mod.add_momentum(df)
    result = mod.add_cross_sectional(df)
    pct_min = result.loc[result.ticker == "T0", "balance_ratio_pct_cross"].iloc[0]
    pct_max = result.loc[result.ticker == "T3", "balance_ratio_pct_cross"].iloc[0]
    assert pct_min < pct_max


# ─── 4. 쇼트 스퀴즈 플래그 ──────────────────────────────────

def test_short_squeeze_flag():
    mod = _load()
    periods = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    df = _make_monthly("A001", periods, [3.0, 2.5, 2.0, 1.5])  # 3개월 변화 = -1.5 < -0.3
    df = mod.add_momentum(df)
    df = mod.add_cross_sectional(df)
    price_mom = pd.DataFrame({
        "ticker": ["A001"],
        "period": ["2026-04-01"],
        "ret_1m": [0.05],  # 양수 = 상승
    })
    result = mod.add_score_and_flags(df, price_mom)
    flag = result.loc[result["period"] == "2026-04-01", "short_squeeze_flag"].iloc[0]
    assert flag is True or flag == 1, "잔고 급감 + 가격 상승 = 쇼트 스퀴즈 플래그 True"


# ─── 5. 가격 하락 시 스퀴즈 플래그 False ─────────────────────

def test_no_squeeze_when_price_falling():
    mod = _load()
    periods = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    df = _make_monthly("A001", periods, [3.0, 2.5, 2.0, 1.5])
    df = mod.add_momentum(df)
    df = mod.add_cross_sectional(df)
    price_mom = pd.DataFrame({
        "ticker": ["A001"],
        "period": ["2026-04-01"],
        "ret_1m": [-0.03],  # 하락
    })
    result = mod.add_score_and_flags(df, price_mom)
    flag = result.loc[result["period"] == "2026-04-01", "short_squeeze_flag"].iloc[0]
    assert not flag, "가격 하락 시 쇼트 스퀴즈 플래그 False"


# ─── 6. 카탈로그 검증 ────────────────────────────────────────

def test_catalog_structure():
    mod = _load()
    catalog = mod.build_catalog()
    required = {"factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"}
    assert required.issubset(set(catalog.columns))
    assert (catalog["factor_family"] == "shorting").all()
    assert len(catalog) >= 5
