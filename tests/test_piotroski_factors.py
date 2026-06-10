"""unit tests for build_piotroski_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_piotroski_factors import _f_score, _bucket, build, CATALOG

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"

# ──────────────────────────────────────────────
# 단위 테스트
# ──────────────────────────────────────────────

def _make_d(overrides: dict = {}) -> dict:
    """기본 재무 데이터 (건전한 회사 모형)."""
    base = {
        "total_assets_current":         1_000_000,
        "total_assets_prior":             900_000,
        "net_income_current":              80_000,
        "net_income_prior":                60_000,
        "cfo_current":                    100_000,
        "cfo_prior":                       70_000,
        "current_assets_current":         400_000,
        "current_assets_prior":           350_000,
        "current_liabilities_current":    200_000,
        "current_liabilities_prior":      200_000,
        "noncurrent_liabilities_current": 150_000,
        "noncurrent_liabilities_prior":   180_000,
        "capital_stock_current":           50_000,
        "capital_stock_prior":             50_000,
        "revenue_current":                520_000,  # AT_c=0.52 > AT_p=0.50 → F9=1
        "revenue_prior":                  450_000,
        "gross_profit_current":           150_000,
        "gross_profit_prior":             120_000,
    }
    base.update(overrides)
    return base


def test_full_positive_score():
    """건전한 회사 → 모든 기준 충족 (9점)."""
    d = _make_d()
    r = _f_score(d)
    assert r["f_score"] == 9
    assert r["f1_roa_positive"] == 1
    assert r["f2_cfo_positive"] == 1
    assert r["f7_no_dilution"] == 1


def test_roa_negative():
    """순손실 → F1=0, F3=0."""
    d = _make_d({"net_income_current": -10_000, "net_income_prior": 5_000})
    r = _f_score(d)
    assert r["f1_roa_positive"] == 0
    assert r["f3_roa_improving"] == 0


def test_cfo_negative():
    """영업현금흐름 음수 → F2=0."""
    d = _make_d({"cfo_current": -5_000})
    r = _f_score(d)
    assert r["f2_cfo_positive"] == 0


def test_accrual_quality_fail():
    """CFO < 순이익 (발생주의 조작 의심) → F4=0."""
    # net_income/assets = 80/1000 = 0.08
    # cfo/assets = 30/1000 = 0.03 → F4=0
    d = _make_d({"cfo_current": 30_000})
    r = _f_score(d)
    assert r["f4_accrual_quality"] == 0


def test_dilution_detected():
    """자본금 증가 → F7=0."""
    d = _make_d({"capital_stock_current": 60_000})
    r = _f_score(d)
    assert r["f7_no_dilution"] == 0


def test_missing_data_nan():
    """핵심 데이터 누락 → NaN으로 처리."""
    d = {"total_assets_current": np.nan, "net_income_current": 50_000}
    r = _f_score(d)
    assert np.isnan(r["f1_roa_positive"]) or r["f1_roa_positive"] is None


def test_bucket_labels():
    assert _bucket(9)   == "strong"
    assert _bucket(8)   == "strong"
    assert _bucket(7)   == "good"
    assert _bucket(5)   == "neutral"
    assert _bucket(3)   == "weak"
    assert _bucket(1)   == "distress"
    assert _bucket(np.nan) == "unknown"


# ──────────────────────────────────────────────
# 통합 테스트 (DB 필요)
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 50, "최소 50종목 기대"


def test_f_score_integer_range(df):
    valid = df["f_score"].dropna()
    assert (valid >= 0).all() and (valid <= 9).all()
    assert valid.apply(lambda x: x == int(x)).all(), "정수 여야 함"


def test_f_score_norm_range(df):
    valid = df["f_score_norm"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_sector_pct_range(df):
    valid = df["f_score_sector_pct"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_catalog_completeness():
    assert len(CATALOG) == 13
    for item in CATALOG:
        assert len(item) == 4
