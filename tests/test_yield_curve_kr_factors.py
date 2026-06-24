"""unit tests for build_yield_curve_kr_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_yield_curve_kr_factors import (
    _rolling_percentile, _curve_regime, build, CATALOG,
)

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_rolling_percentile_basic():
    s = pd.Series(range(1, 13), dtype=float)  # 1..12, monotonically increasing
    pct = _rolling_percentile(s, window=12, min_periods=12)
    assert pct.iloc[-1] == pytest.approx(1.0)


def test_curve_regime_labels():
    assert _curve_regime(0.1) == "deeply_inverted"
    assert _curve_regime(0.3) == "inverted"
    assert _curve_regime(0.5) == "flat"
    assert _curve_regime(0.7) == "normal"
    assert _curve_regime(0.9) == "steep"
    assert _curve_regime(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 180, "최소 180개월(15년) 이상 데이터 기대"


def test_columns_exist(df):
    for col in ["kor_gov1y", "kor_gov5y", "kor_gov10y", "yield_level",
                 "yield_slope_10y1y", "yield_curvature", "curve_regime", "curve_inversion_flag"]:
        assert col in df.columns


def test_yield_slope_pctile_range(df):
    valid = df["yield_slope_pctile_3y"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_curve_inversion_flag_binary(df):
    valid = df["curve_inversion_flag"].dropna()
    assert valid.isin([0, 1]).all()


def test_curve_inversion_flag_consistency(df):
    rows = df.dropna(subset=["yield_slope_10y1y"])
    expected = (rows["yield_slope_10y1y"] < 0).astype(int)
    assert (rows["curve_inversion_flag"] == expected).all()


def test_gov30y_partial_coverage_nan_allowed(df):
    # 30y는 2012-09 이전 NaN이 허용됨 (임의 보간 없음)
    assert df["kor_gov30y"].isna().any()
    assert df["kor_gov30y"].notna().any()


def test_curve_regime_valid_labels(df):
    valid = df["curve_regime"].dropna().unique()
    allowed = {"deeply_inverted", "inverted", "flat", "normal", "steep", "unknown"}
    assert set(valid).issubset(allowed)


def test_yield_level_positive(df):
    valid = df["yield_level"].dropna()
    assert (valid > 0).all()


def test_catalog_completeness():
    assert len(CATALOG) == 13
    for item in CATALOG:
        assert len(item) == 4
