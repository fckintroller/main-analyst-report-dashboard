"""unit tests for build_sector_etf_flow_factors.py"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_sector_etf_flow_factors import _bucket_flow, build, CATALOG, _load_etf_files


def test_load_etf_files():
    files = _load_etf_files()
    assert len(files) >= 15
    for group_name, ticker, path in files:
        assert len(ticker) == 6
        assert path.exists()


def test_bucket_flow_thresholds():
    assert _bucket_flow(0.9) == "very_high"
    assert _bucket_flow(0.7) == "high"
    assert _bucket_flow(0.5) == "neutral"
    assert _bucket_flow(0.3) == "low"
    assert _bucket_flow(0.1) == "very_low"


@pytest.fixture(scope="module")
def df():
    return build()


def test_row_count(df):
    assert len(df) > 100


def test_group_count(df):
    assert df["group_name"].nunique() >= 15


def test_money_flow_score_range(df):
    valid = df["money_flow_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_period_format(df):
    assert df["period"].str.match(r"^\d{4}-\d{2}-01$").all()


def test_catalog_completeness():
    assert len(CATALOG) == 7
    for item in CATALOG:
        assert len(item) == 4
