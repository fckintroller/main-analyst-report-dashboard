"""unit tests for build_commodity_momentum_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_commodity_momentum_factors import (
    _score_from_zscore, _rolling_percentile, _cyclical_demand_regime, build, CATALOG,
)

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_score_from_zscore_range():
    s = pd.Series([-5, -3, 0, 3, 5])
    result = _score_from_zscore(s)
    assert (result >= 0).all() and (result <= 1).all()


def test_score_from_zscore_neutral():
    s = pd.Series([0.0])
    assert _score_from_zscore(s).iloc[0] == pytest.approx(0.5)


def test_rolling_percentile_basic():
    s = pd.Series(range(1, 13), dtype=float)  # 1..12, monotonically increasing
    pct = _rolling_percentile(s, window=12, min_periods=12)
    assert pct.iloc[-1] == pytest.approx(1.0)


def test_cyclical_demand_regime_labels():
    assert _cyclical_demand_regime(0.1) == "contraction"
    assert _cyclical_demand_regime(0.3) == "slowdown"
    assert _cyclical_demand_regime(0.5) == "neutral"
    assert _cyclical_demand_regime(0.7) == "expansion"
    assert _cyclical_demand_regime(0.9) == "boom"
    assert _cyclical_demand_regime(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 180, "최소 180개월(15년) 이상 데이터 기대"


def test_columns_exist(df):
    for col in ["copper_close", "wti_close", "brent_close",
                 "copper_ret_3m", "brent_ret_3m",
                 "commodity_cycle_score", "cyclical_demand_regime", "commodity_surge_flag"]:
        assert col in df.columns


def test_commodity_cycle_score_range(df):
    valid = df["commodity_cycle_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_pctile_range(df):
    for col in ["copper_pctile_3y", "brent_pctile_3y"]:
        valid = df[col].dropna()
        assert (valid >= 0).all() and (valid <= 1).all()


def test_commodity_surge_flag_binary(df):
    valid = df["commodity_surge_flag"].dropna()
    assert valid.isin([0, 1]).all()


def test_close_prices_positive(df):
    for col in ["copper_close", "wti_close", "brent_close"]:
        valid = df[col].dropna()
        assert (valid > 0).all()


def test_cyclical_demand_regime_valid_labels(df):
    valid = df["cyclical_demand_regime"].dropna().unique()
    allowed = {"contraction", "slowdown", "neutral", "expansion", "boom", "unknown"}
    assert set(valid).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 12
    for item in CATALOG:
        assert len(item) == 4
