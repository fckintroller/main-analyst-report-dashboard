"""unit tests for build_gap_trading_factors.py"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_gap_trading_factors import _gap_direction, _gap_bucket, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_gap_direction():
    assert _gap_direction(0.01) == "gap_up"
    assert _gap_direction(-0.01) == "gap_down"
    assert _gap_direction(0.001) == "flat"
    assert _gap_direction(-0.001) == "flat"
    assert _gap_direction(np.nan) == "unknown"


def test_gap_bucket():
    assert _gap_bucket(0.05) == "gap_up_strong"
    assert _gap_bucket(0.01) == "gap_up"
    assert _gap_bucket(0.0) == "flat"
    assert _gap_bucket(-0.01) == "gap_down"
    assert _gap_bucket(-0.05) == "gap_down_strong"
    assert _gap_bucket(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 400


def test_gap_pct_reasonable(df):
    valid = df["gap_pct"].dropna()
    assert (valid.abs() < 0.5).all(), "갭은 통상 ±50% 미만"


def test_gap_fill_rate_range(df):
    valid = df["gap_fill_rate_60d"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_gap_filled_today_binary(df):
    valid = df["gap_filled_today"].dropna()
    assert set(valid.unique()).issubset({0.0, 1.0})


def test_gap_signal_score_range(df):
    valid = df["gap_signal_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_catalog_completeness():
    assert len(CATALOG) == 7
    for item in CATALOG:
        assert len(item) == 4
