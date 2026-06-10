"""unit tests for build_earnings_momentum_factors.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_earnings_momentum_factors import _growth, _bucket, build, CATALOG


def test_growth_normal():
    g, turnaround = _growth(150.0, 100.0)
    assert g == pytest.approx(0.5)
    assert turnaround == 0.0


def test_growth_turnaround():
    g, turnaround = _growth(100.0, -50.0)
    assert pd.isna(g)
    assert turnaround == 1.0


def test_growth_still_negative():
    g, turnaround = _growth(-50.0, -100.0)
    assert pd.isna(g)
    assert turnaround == 0.0


def test_growth_missing_data():
    g, turnaround = _growth(None, 100.0)
    assert pd.isna(g)
    assert pd.isna(turnaround)


def test_growth_clipping():
    g, turnaround = _growth(1000.0, 1.0)  # 999x growth
    assert g == pytest.approx(3.0)  # clipped to GROWTH_CLIP
    assert turnaround == 0.0


def test_bucket_thresholds():
    assert _bucket(0.5) == "strong_growth"
    assert _bucket(0.1) == "growth"
    assert _bucket(-0.05) == "flat"
    assert _bucket(-0.5) == "decline"
    assert _bucket(np.nan) == "no_data"


@pytest.fixture(scope="module")
def df():
    return build("2026-06-09")


def test_row_count(df):
    assert len(df) > 0


def test_score_range(df):
    valid = df["earnings_momentum_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_turnaround_flag_binary(df):
    valid = df["op_turnaround_flag"].dropna()
    assert set(valid.unique()).issubset({0.0, 1.0})


def test_bucket_values(df):
    allowed = {"strong_growth", "growth", "flat", "decline", "no_data"}
    assert set(df["earnings_growth_bucket"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 8
    for item in CATALOG:
        assert len(item) == 4
