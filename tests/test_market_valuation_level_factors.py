"""unit tests for build_market_valuation_level_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_market_valuation_level_factors import _bucket_valuation, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_valuation_thresholds():
    assert _bucket_valuation(0.9) == "very_expensive"
    assert _bucket_valuation(0.7) == "expensive"
    assert _bucket_valuation(0.5) == "neutral"
    assert _bucket_valuation(0.3) == "cheap"
    assert _bucket_valuation(0.1) == "very_cheap"
    assert _bucket_valuation(float("nan")) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 30


def test_period_format(df):
    assert df["period"].str.match(r"^\d{4}-\d{2}-01$").all()


def test_pbr_pctile_3y_range(df):
    valid = df["pbr_pctile_3y"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_pbr_pctile_10y_single_snapshot(df):
    non_null = df["pbr_pctile_10y"].dropna()
    assert len(non_null) == 1
    val = non_null.iloc[0]
    assert 0 <= val <= 1


def test_valuation_regime_values(df):
    allowed = {"very_expensive", "expensive", "neutral", "cheap", "very_cheap", "unknown"}
    assert set(df["valuation_regime"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 5
    for item in CATALOG:
        assert len(item) == 4
