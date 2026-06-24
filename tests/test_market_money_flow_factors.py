"""unit tests for build_market_money_flow_factors.py"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "03_analyze"))
from build_market_money_flow_factors import _bucket_flow, build, CATALOG, MARKETS

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "database" / "quant_data.sqlite"


def test_bucket_flow_thresholds():
    assert _bucket_flow(0.9) == "strong_inflow"
    assert _bucket_flow(0.7) == "inflow"
    assert _bucket_flow(0.5) == "neutral"
    assert _bucket_flow(0.3) == "outflow"
    assert _bucket_flow(0.1) == "strong_outflow"
    assert _bucket_flow(float("nan")) == "unknown"


@pytest.fixture(scope="module")
def df():
    with sqlite3.connect(DB_PATH) as conn:
        return build(conn)


def test_row_count(df):
    assert len(df) > 400


def test_market_values(df):
    assert set(df["market"].unique()) == {m.upper() for m in MARKETS}


def test_period_format(df):
    assert df["period"].str.match(r"^\d{4}-\d{2}-01$").all()


def test_pctile_range(df):
    for col in ["foreign_net_pctile", "inst_net_pctile", "pension_net_pctile", "flow_score"]:
        valid = df[col].dropna()
        assert (valid >= 0).all() and (valid <= 1).all()


def test_flow_regime_values(df):
    allowed = {"strong_inflow", "inflow", "neutral", "outflow", "strong_outflow", "unknown"}
    assert set(df["flow_regime"].unique()).issubset(allowed)


def test_catalog_completeness():
    assert len(CATALOG) == 9
    for item in CATALOG:
        assert len(item) == 4
