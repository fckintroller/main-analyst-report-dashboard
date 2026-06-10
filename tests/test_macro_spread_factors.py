"""unit tests for build_macro_spread_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_macro_spread_factors import _score_from_zscore, _vix_regime, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_score_from_zscore_range():
    s = pd.Series([-5, -3, 0, 3, 5])
    result = _score_from_zscore(s)
    assert (result >= 0).all() and (result <= 1).all()


def test_score_from_zscore_neutral():
    s = pd.Series([0.0])
    assert _score_from_zscore(s).iloc[0] == pytest.approx(0.5)


def test_vix_regime_labels():
    assert _vix_regime(12) == "calm"
    assert _vix_regime(17) == "moderate"
    assert _vix_regime(22) == "elevated"
    assert _vix_regime(27) == "high"
    assert _vix_regime(35) == "extreme"
    assert _vix_regime(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 200, "최소 200개월 이상 데이터 기대"


def test_macro_score_range(df):
    valid = df["macro_risk_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_spread_columns_exist(df):
    for col in ["kor_spread_10y1y", "us_spread_10y2y", "hy_spread", "vix", "macro_risk_score"]:
        assert col in df.columns


def test_inversion_flags_binary(df):
    for col in ["kor_yield_inverted", "us_yield_inverted"]:
        valid = df[col].dropna()
        assert valid.isin([0, 1]).all()


def test_catalog_completeness():
    assert len(CATALOG) == 12
    for item in CATALOG:
        assert len(item) == 4
