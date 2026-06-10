"""unit tests for build_value_composite_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_value_composite_factors import _compute_composite, _bucket, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


# ──────────────────────────────────────────────
# 단위 테스트
# ──────────────────────────────────────────────

def test_compute_composite_all_sources():
    row = pd.Series({
        "valuation_score": 0.8,
        "forward_valuation_score": 0.9,
        "peg_composite_score": 0.7,
    })
    score = _compute_composite(row)
    assert 0 < score < 1


def test_compute_composite_partial():
    """forward/peg 없을 때 trailing PER/PBR 백분위만으로 계산."""
    # per_pct=0.2, pbr_pct=0.3 → trailing_score = (0.8+0.7)/2 = 0.75
    row = pd.Series({
        "per_percentile_sector": 0.2,
        "pbr_percentile_sector": 0.3,
        "forward_valuation_score": np.nan,
        "peg_composite_score": np.nan,
    })
    score = _compute_composite(row)
    assert score == pytest.approx(0.75, rel=1e-6)


def test_compute_composite_all_nan():
    row = pd.Series({
        "valuation_score": np.nan,
        "forward_valuation_score": np.nan,
        "peg_composite_score": np.nan,
    })
    assert np.isnan(_compute_composite(row))


def test_bucket_labels():
    assert _bucket(0.80) == "deep_value"
    assert _bucket(0.65) == "value"
    assert _bucket(0.50) == "neutral"
    assert _bucket(0.30) == "growth"
    assert _bucket(0.10) == "expensive"
    assert _bucket(np.nan) == "unknown"


# ──────────────────────────────────────────────
# 통합 테스트 (DB 필요)
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) > 100, "395행 이상 기대"


def test_score_range(df):
    valid = df["value_composite_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_sector_pct_range(df):
    valid = df["value_composite_sector_pct"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_catalog_completeness():
    assert len(CATALOG) == 5
    for item in CATALOG:
        assert len(item) == 4
