"""unit tests for build_macro_search_sentiment_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_macro_search_sentiment_factors import _bucket_level, build, CATALOG, THEME_KEYWORDS

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_level_thresholds():
    assert _bucket_level(0.9) == "very_high"
    assert _bucket_level(0.7) == "high"
    assert _bucket_level(0.5) == "neutral"
    assert _bucket_level(0.3) == "low"
    assert _bucket_level(0.1) == "very_low"
    assert _bucket_level(float("nan")) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 50


def test_period_format(df):
    assert df["period"].str.match(r"^\d{4}-\d{2}-01$").all()


def test_score_ranges(df):
    cols = ["macro_anxiety_score", "retail_interest_score"] + list(THEME_KEYWORDS.values())
    for col in cols:
        valid = df[col].dropna()
        assert (valid >= 0).all() and (valid <= 1).all()


def test_level_values(df):
    allowed = {"very_high", "high", "neutral", "low", "very_low", "unknown"}
    assert set(df["anxiety_level"].unique()).issubset(allowed)
    assert set(df["interest_level"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 9
    for item in CATALOG:
        assert len(item) == 4
