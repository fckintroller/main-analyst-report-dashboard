"""unit tests for build_fx_usdkrw_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_fx_usdkrw_factors import (
    _score_from_zscore, _rolling_percentile, _fx_regime, build, CATALOG,
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


def test_fx_regime_labels():
    assert _fx_regime(0.1) == "won_very_strong"
    assert _fx_regime(0.3) == "won_strong"
    assert _fx_regime(0.5) == "neutral"
    assert _fx_regime(0.7) == "won_weak"
    assert _fx_regime(0.9) == "won_very_weak"
    assert _fx_regime(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 180, "최소 180개월(15년) 이상 데이터 기대"


def test_columns_exist(df):
    for col in ["usd_krw_close", "usd_krw_ret_1m", "usd_krw_zscore_6m",
                 "won_strength_score", "fx_regime", "rapid_depreciation_flag"]:
        assert col in df.columns


def test_won_strength_score_range(df):
    valid = df["won_strength_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_pctile_range(df):
    valid = df["usd_krw_pctile_3y"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_rapid_depreciation_flag_binary(df):
    valid = df["rapid_depreciation_flag"].dropna()
    assert valid.isin([0, 1]).all()


def test_usd_krw_close_positive(df):
    valid = df["usd_krw_close"].dropna()
    assert (valid > 0).all()


def test_fx_regime_valid_labels(df):
    valid = df["fx_regime"].dropna().unique()
    allowed = {"won_very_strong", "won_strong", "neutral", "won_weak", "won_very_weak", "unknown"}
    assert set(valid).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 8
    for item in CATALOG:
        assert len(item) == 4
