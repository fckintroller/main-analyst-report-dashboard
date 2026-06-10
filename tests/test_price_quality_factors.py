"""unit tests for build_price_quality_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_price_quality_factors import _bucket_52w, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_near_high():
    assert _bucket_52w(1.00) == "near_high"
    assert _bucket_52w(0.97) == "near_high"


def test_bucket_levels():
    assert _bucket_52w(0.95) == "strong"
    assert _bucket_52w(0.85) == "moderate"
    assert _bucket_52w(0.75) == "weak"
    assert _bucket_52w(0.60) == "far_from_high"
    assert _bucket_52w(np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 400, "431행 이상 기대"


def test_proximity_range(df):
    valid = df["high_52w_proximity"].dropna()
    assert (valid > 0).all() and (valid <= 1.0001).all(), "근접도는 0~1 범위"


def test_volume_surge_positive(df):
    valid = df["volume_surge_20d"].dropna()
    assert (valid > 0).all()


def test_score_range(df):
    valid = df["price_quality_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_catalog_completeness():
    assert len(CATALOG) == 5
    for item in CATALOG:
        assert len(item) == 4
