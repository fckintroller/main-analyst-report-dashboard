"""unit tests for build_ppi_inflation_cycle_kr_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_ppi_inflation_cycle_kr_factors import (
    _score_from_zscore, _rolling_percentile, _inflation_cycle_regime, build, CATALOG,
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


def test_inflation_cycle_regime_labels():
    assert _inflation_cycle_regime(0.1) == "disinflation"
    assert _inflation_cycle_regime(0.3) == "low"
    assert _inflation_cycle_regime(0.5) == "neutral"
    assert _inflation_cycle_regime(0.7) == "elevated"
    assert _inflation_cycle_regime(0.9) == "inflation_surge"
    assert _inflation_cycle_regime(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 180, "최소 180개월(15년) 이상 데이터 기대"


def test_columns_exist(df):
    for col in ["kor_ppi_index", "kor_ppi_yoy", "kor_ppi_yoy_chg3m",
                 "inflation_momentum_score", "inflation_cycle_regime", "inflation_accel_flag"]:
        assert col in df.columns


def test_inflation_momentum_score_range(df):
    valid = df["inflation_momentum_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_pctile_range(df):
    valid = df["kor_ppi_yoy_pctile_3y"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_inflation_accel_flag_binary(df):
    valid = df["inflation_accel_flag"].dropna()
    assert valid.isin([0, 1]).all()


def test_kor_ppi_index_positive(df):
    valid = df["kor_ppi_index"].dropna()
    assert (valid > 0).all()


def test_inflation_cycle_regime_valid_labels(df):
    valid = df["inflation_cycle_regime"].dropna().unique()
    allowed = {"disinflation", "low", "neutral", "elevated", "inflation_surge", "unknown"}
    assert set(valid).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 9
    for item in CATALOG:
        assert len(item) == 4
