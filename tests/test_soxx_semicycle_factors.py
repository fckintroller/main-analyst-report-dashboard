"""unit tests for build_soxx_semicycle_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_soxx_semicycle_factors import (
    _score_from_zscore, _rolling_percentile, _semi_cycle_regime, build, CATALOG,
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


def test_semi_cycle_regime_labels():
    assert _semi_cycle_regime(0.1) == "strong_down"
    assert _semi_cycle_regime(0.3) == "down"
    assert _semi_cycle_regime(0.5) == "neutral"
    assert _semi_cycle_regime(0.7) == "up"
    assert _semi_cycle_regime(0.9) == "strong_up"
    assert _semi_cycle_regime(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 100, "최소 100개월(8년 이상) 이상 데이터 기대"


def test_columns_exist(df):
    for col in ["soxx_close", "soxx_ret_1m", "soxx_ret_zscore_6m",
                 "semi_momentum_score", "semi_cycle_regime", "semi_rally_accel_flag"]:
        assert col in df.columns


def test_semi_momentum_score_range(df):
    valid = df["semi_momentum_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_pctile_range(df):
    valid = df["soxx_ret_pctile_3y"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_semi_rally_accel_flag_binary(df):
    valid = df["semi_rally_accel_flag"].dropna()
    assert valid.isin([0, 1]).all()


def test_soxx_close_positive(df):
    valid = df["soxx_close"].dropna()
    assert (valid > 0).all()


def test_semi_cycle_regime_valid_labels(df):
    valid = df["semi_cycle_regime"].dropna().unique()
    allowed = {"strong_down", "down", "neutral", "up", "strong_up", "unknown"}
    assert set(valid).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 9
    for item in CATALOG:
        assert len(item) == 4
