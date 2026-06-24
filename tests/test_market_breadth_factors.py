"""unit tests for build_market_breadth_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_market_breadth_factors import _bucket_breadth, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_breadth_thresholds():
    assert _bucket_breadth(0.9) == "broad_bullish"
    assert _bucket_breadth(0.7) == "bullish"
    assert _bucket_breadth(0.5) == "neutral"
    assert _bucket_breadth(0.3) == "bearish"
    assert _bucket_breadth(0.1) == "broad_bearish"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 20


def test_period_format(df):
    assert df["period"].str.match(r"^\d{4}-\d{2}-01$").all()


def test_breadth_score_range(df):
    valid = df["breadth_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_trin_avg_positive(df):
    valid = df["trin_avg"].dropna()
    assert (valid > 0).all()


def test_breadth_regime_values(df):
    allowed = {"broad_bullish", "bullish", "neutral", "bearish", "broad_bearish", "unknown"}
    assert set(df["breadth_regime"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 9
    for item in CATALOG:
        assert len(item) == 4
