"""unit tests for build_adr_gap_signal_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_adr_gap_signal_factors import _bucket_gap, build, CATALOG, ADR_TICKER_MAP

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_gap_thresholds():
    assert _bucket_gap(2.0) == "strong_positive"
    assert _bucket_gap(0.5) == "positive"
    assert _bucket_gap(0.0) == "neutral"
    assert _bucket_gap(-0.5) == "negative"
    assert _bucket_gap(-2.0) == "strong_negative"
    assert _bucket_gap(float("nan")) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) > 1000


def test_ticker_count(df):
    assert df["ticker"].nunique() == 8


def test_ticker_values(df):
    expected = {ticker for ticker, _ in ADR_TICKER_MAP.values()}
    assert set(df["ticker"].unique()) == expected


def test_gap_pctile_range(df):
    valid = df["adr_gap_pctile_252d"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_gap_bucket_values(df):
    allowed = {"strong_positive", "positive", "neutral", "negative", "strong_negative", "unknown"}
    assert set(df["gap_bucket"].unique()).issubset(allowed)


def test_date_format(df):
    assert df["date"].str.match(r"^\d{4}-\d{2}-\d{2}$").all()


def test_catalog_completeness():
    assert len(CATALOG) == 7
    for item in CATALOG:
        assert len(item) == 4
