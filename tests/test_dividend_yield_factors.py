"""unit tests for build_dividend_yield_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_dividend_yield_factors import _bucket_dividend, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_dividend_no_dividend():
    assert _bucket_dividend(float("nan"), 0) == "no_dividend"


def test_bucket_dividend_thresholds():
    assert _bucket_dividend(0.9, 1) == "very_high"
    assert _bucket_dividend(0.7, 1) == "high"
    assert _bucket_dividend(0.5, 1) == "mid"
    assert _bucket_dividend(0.3, 1) == "low"
    assert _bucket_dividend(0.1, 1) == "very_low"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) > 2000


def test_market_values(df):
    assert set(df["market"].unique()).issubset({"KOSPI", "KOSDAQ"})


def test_div_yield_score_range(df):
    valid = df["div_yield_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_no_dividend_bucket_for_zero_div(df):
    zero_div = df[df["div_yield_pct"] <= 0]
    assert (zero_div["dividend_bucket"] == "no_dividend").all()


def test_has_dividend_flag_binary(df):
    assert set(df["has_dividend_flag"].unique()).issubset({0, 1})


def test_bucket_values(df):
    allowed = {"no_dividend", "very_low", "low", "mid", "high", "very_high", "unknown"}
    assert set(df["dividend_bucket"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 7
    for item in CATALOG:
        assert len(item) == 4
