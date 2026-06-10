"""unit tests for build_technical_meanrev_factors.py"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_technical_meanrev_factors import _rsi, _bucket_meanrev, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_rsi_all_gains_is_100():
    close = pd.Series(range(1, 41), dtype=float)  # monotonically increasing
    rsi = _rsi(close)
    assert rsi.iloc[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    close = pd.Series(range(40, 0, -1), dtype=float)  # monotonically decreasing
    rsi = _rsi(close)
    assert rsi.iloc[-1] == pytest.approx(0.0)


def test_rsi_flat_is_nan():
    close = pd.Series([100.0] * 40)
    rsi = _rsi(close)
    assert pd.isna(rsi.iloc[-1])


def test_bucket_thresholds():
    assert _bucket_meanrev(20) == "oversold"
    assert _bucket_meanrev(35) == "weak_oversold"
    assert _bucket_meanrev(50) == "neutral"
    assert _bucket_meanrev(60) == "weak_overbought"
    assert _bucket_meanrev(80) == "overbought"
    assert _bucket_meanrev(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 400


def test_rsi_range(df):
    valid = df["rsi_14"].dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_meanrev_score_range(df):
    valid = df["meanrev_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_bucket_values(df):
    allowed = {"oversold", "weak_oversold", "neutral", "weak_overbought", "overbought", "unknown"}
    assert set(df["meanrev_bucket"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 6
    for item in CATALOG:
        assert len(item) == 4
