"""unit tests for build_size_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_size_factors import _bucket_size, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_size_thresholds():
    assert _bucket_size(0.97) == "mega"
    assert _bucket_size(0.85) == "large"
    assert _bucket_size(0.6) == "mid"
    assert _bucket_size(0.3) == "small"
    assert _bucket_size(0.1) == "micro"
    assert pd.isna(float("nan")) and _bucket_size(float("nan")) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) > 1000


def test_ticker_count(df):
    assert df["ticker"].nunique() >= 300


def test_size_percentile_range(df):
    valid = df["size_percentile_cross"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_small_cap_score_is_complement(df):
    valid = df.dropna(subset=["size_percentile_cross", "small_cap_score"])
    assert (valid["small_cap_score"] + valid["size_percentile_cross"]).sub(1.0).abs().max() < 1e-9


def test_bucket_values(df):
    allowed = {"mega", "large", "mid", "small", "micro", "unknown"}
    assert set(df["size_bucket"].unique()).issubset(allowed)


def test_period_format(df):
    assert df["period"].str.match(r"^\d{4}-\d{2}-01$").all()


def test_catalog_completeness():
    assert len(CATALOG) == 6
    for item in CATALOG:
        assert len(item) == 4
