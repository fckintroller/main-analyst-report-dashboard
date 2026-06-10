"""unit tests for build_liquidity_turnover_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_liquidity_turnover_factors import _bucket_liquidity, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_liquidity_thresholds():
    assert _bucket_liquidity(0.9) == "very_high"
    assert _bucket_liquidity(0.7) == "high"
    assert _bucket_liquidity(0.5) == "neutral"
    assert _bucket_liquidity(0.3) == "low"
    assert _bucket_liquidity(0.1) == "very_low"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) > 1000


def test_ticker_count(df):
    assert df["ticker"].nunique() >= 300


def test_turnover_ratio_positive(df):
    valid = df["turnover_ratio"].dropna()
    assert (valid >= 0).all()


def test_liquidity_score_range(df):
    valid = df["liquidity_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_period_format(df):
    assert df["period"].str.match(r"^\d{4}-\d{2}-01$").all()


def test_bucket_values(df):
    allowed = {"very_high", "high", "neutral", "low", "very_low", "unknown"}
    assert set(df["liquidity_bucket"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 6
    for item in CATALOG:
        assert len(item) == 4
