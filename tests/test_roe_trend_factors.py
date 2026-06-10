"""unit tests for build_roe_trend_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_roe_trend_factors import _roe_bucket, _compute_trend_features, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_roe_bucket_labels():
    assert _roe_bucket(0.25) == "high_quality"
    assert _roe_bucket(0.15) == "quality"
    assert _roe_bucket(0.08) == "average"
    assert _roe_bucket(0.02) == "low"
    assert _roe_bucket(-0.05) == "negative"
    assert _roe_bucket(np.nan) == "unknown"


def test_compute_trend_features_minimal():
    """최소 데이터(1개월)로도 crash 없이 동작."""
    df = pd.DataFrame({"period": ["2026-06-01"], "roe": [0.15], "ticker": ["999999"]})
    feat = _compute_trend_features(df)
    assert feat is not None
    assert feat["roe_current"] == pytest.approx(0.15)
    assert np.isnan(feat["roe_mom_3m"])


def test_compute_trend_features_full():
    """13개월 데이터 → YoY 변화 계산."""
    periods = pd.date_range("2025-06-01", periods=13, freq="MS").strftime("%Y-%m-01")
    roe_vals = np.linspace(0.10, 0.20, 13)  # 10% → 20% 상승
    df = pd.DataFrame({"period": periods, "roe": roe_vals, "ticker": ["000001"] * 13})
    feat = _compute_trend_features(df)
    assert feat["roe_mom_1y"] == pytest.approx(0.10, rel=0.01)
    assert feat["roe_improving"] == 1


@pytest.fixture(scope="module")
def snap_ts():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_snapshot_row_count(snap_ts):
    snap, _ = snap_ts
    assert len(snap) >= 300


def test_roe_score_range(snap_ts):
    snap, _ = snap_ts
    valid = snap["roe_composite_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_sector_pct_range(snap_ts):
    snap, _ = snap_ts
    valid = snap["roe_sector_pct"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_timeseries_row_count(snap_ts):
    _, ts = snap_ts
    assert len(ts) >= 5000


def test_catalog_completeness():
    assert len(CATALOG) == 8
    for item in CATALOG:
        assert len(item) == 4
