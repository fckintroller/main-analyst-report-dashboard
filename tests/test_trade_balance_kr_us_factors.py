"""unit tests for build_trade_balance_kr_us_factors.py"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_trade_balance_kr_us_factors import (
    _score_from_zscore, _export_cycle_regime, build, CATALOG,
)

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_score_from_zscore_range():
    s = pd.Series([-5, -3, 0, 3, 5])
    result = _score_from_zscore(s)
    assert (result >= 0).all() and (result <= 1).all()


def test_score_from_zscore_neutral():
    s = pd.Series([0.0])
    assert _score_from_zscore(s).iloc[0] == pytest.approx(0.5)


def test_export_cycle_regime_quadrants():
    assert _export_cycle_regime(0.05, 0.01) == "expansion"
    assert _export_cycle_regime(0.05, -0.01) == "slowdown"
    assert _export_cycle_regime(-0.05, 0.01) == "recovery"
    assert _export_cycle_regime(-0.05, -0.01) == "contraction"
    assert _export_cycle_regime(np.nan, 0.01) == "unknown"
    assert _export_cycle_regime(0.05, np.nan) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) >= 180, "최소 180개월(15년) 이상 데이터 기대"


def test_columns_exist(df):
    for col in ["korea_exports", "korea_imports", "korea_trade_balance",
                 "us_korea_trade_balance", "korea_exports_yoy",
                 "export_momentum_score", "export_cycle_regime"]:
        assert col in df.columns


def test_export_momentum_score_range(df):
    valid = df["export_momentum_score"].dropna()
    assert (valid >= 0).all() and (valid <= 1).all()


def test_korea_trade_balance_consistency(df):
    valid = df.dropna(subset=["korea_exports", "korea_imports", "korea_trade_balance"])
    diff = (valid["korea_trade_balance"] - (valid["korea_exports"] - valid["korea_imports"])).abs()
    assert (diff < 1e-6).all()


def test_korea_exports_positive(df):
    valid = df["korea_exports"].dropna()
    assert (valid > 0).all()


def test_export_cycle_regime_valid_labels(df):
    valid = df["export_cycle_regime"].dropna().unique()
    allowed = {"expansion", "slowdown", "recovery", "contraction", "unknown"}
    assert set(valid).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 12
    for item in CATALOG:
        assert len(item) == 4
