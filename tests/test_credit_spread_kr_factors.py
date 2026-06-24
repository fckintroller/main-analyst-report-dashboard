"""unit tests for build_credit_spread_kr_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_credit_spread_kr_factors import (
    _score_from_zscore, _rolling_percentile, _credit_regime, build, CATALOG,
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
    # 마지막 값(12)은 자기 윈도우 내 최대값 → 백분위 1.0
    assert pct.iloc[-1] == pytest.approx(1.0)


def test_credit_regime_labels():
    assert _credit_regime(0.1) == "very_tight"
    assert _credit_regime(0.3) == "tight"
    assert _credit_regime(0.5) == "neutral"
    assert _credit_regime(0.7) == "wide"
    assert _credit_regime(0.9) == "very_wide"
    assert _credit_regime(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 180, "최소 180개월(15년) 이상 데이터 기대"


def test_spread_columns_exist(df):
    for col in ["aa_spread", "bbb_spread", "bbb_aa_spread",
                 "credit_score", "credit_regime"]:
        assert col in df.columns


def test_credit_score_range(df):
    valid = df["credit_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_pctile_range(df):
    valid = df["bbb_aa_spread_pctile_3y"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_widening_flag_binary(df):
    valid = df["spread_widening_flag"].dropna()
    assert valid.isin([0, 1]).all()


def test_bbb_aa_spread_positive(df):
    # BBB-는 AA-보다 항상 신용도가 낮으므로 금리가 더 높아야 함
    valid = df["bbb_aa_spread"].dropna()
    assert (valid > 0).all()


def test_catalog_completeness():
    assert len(CATALOG) == 14
    for item in CATALOG:
        assert len(item) == 4
