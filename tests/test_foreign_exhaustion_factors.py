"""unit tests for build_foreign_exhaustion_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_foreign_exhaustion_factors import _bucket_pct, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_pct_thresholds():
    assert _bucket_pct(0.9) == "very_high"
    assert _bucket_pct(0.7) == "high"
    assert _bucket_pct(0.5) == "mid"
    assert _bucket_pct(0.3) == "low"
    assert _bucket_pct(0.1) == "very_low"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) > 2000


def test_market_values(df):
    assert set(df["market"].unique()).issubset({"KOSPI", "KOSDAQ"})


def test_foreign_ownership_pct_cross_range(df):
    valid = df["foreign_ownership_pct_cross"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_foreign_room_score_range(df):
    valid = df["foreign_room_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_ownership_bucket_values(df):
    allowed = {"very_high", "high", "mid", "low", "very_low", "unknown"}
    assert set(df["ownership_bucket"].unique()).issubset(allowed)


def test_room_bucket_values(df):
    allowed = {"very_high", "high", "mid", "low", "very_low", "unknown"}
    assert set(df["room_bucket"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 7
    for item in CATALOG:
        assert len(item) == 4
