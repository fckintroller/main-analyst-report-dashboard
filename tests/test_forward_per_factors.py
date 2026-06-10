"""단위 테스트: build_forward_per_factors.py"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "fwd_mod",
        _root() / "scripts" / "03_analyze" / "build_forward_per_factors.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── 픽스처 헬퍼 ─────────────────────────────────────────────

def _make_consensus_df(
    ticker: str,
    fwd_eps: float | None,
    fwd_per: float | None,
    trail_eps: float | None,
    trail_per: float | None,
    fwd_year: str = "2026",
) -> pd.DataFrame:
    """parse_consensus 에 넘길 최소 DataFrame 생성."""
    data = {
        f"(dummy_label, dummy_label, dummy_label)": {
            "0": "매출액", "9": "EPS", "10": "PER",
        },
        f"(dummy_annual_actual, '{fwd_year[:-1]}{int(fwd_year)-1}.12', 'IFRS연결')": {
            "9": trail_eps,
            "10": trail_per,
        },
        f"(dummy_annual_est, '{fwd_year}.12(E)', 'IFRS연결')": {
            "9": fwd_eps,
            "10": fwd_per,
        },
    }
    return pd.DataFrame({"ticker": [ticker], "consensus_raw": [json.dumps(data)]})


# ─── 1. parse_consensus: 기본 추출 ───────────────────────────

def test_parse_consensus_extracts_forward_and_trailing():
    mod = _load()
    df = _make_consensus_df("A001", fwd_eps=5000.0, fwd_per=10.0, trail_eps=2000.0, trail_per=15.0)
    result = mod.parse_consensus(df)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["ticker"] == "A001"
    assert row["forward_eps"] == pytest.approx(5000.0)
    assert row["forward_per_consensus"] == pytest.approx(10.0)
    assert row["trailing_eps"] == pytest.approx(2000.0)
    assert row["trailing_per_consensus"] == pytest.approx(15.0)


# ─── 2. forward_eps <= 0 이면 forward_per = NaN ──────────────

def test_negative_forward_eps_yields_nan_per():
    mod = _load()
    df = _make_consensus_df("A002", fwd_eps=-3000.0, fwd_per=None, trail_eps=1000.0, trail_per=8.0)
    parsed = mod.parse_consensus(df)
    parsed["sector"] = "테스트섹터"
    price_map = pd.Series({"A002": 50000.0})
    out = mod.compute_derived(parsed, price_map)
    assert np.isnan(out.loc[0, "forward_per"]), "적자 전망 EPS는 forward_per=NaN 이어야 함"


# ─── 3. forward_per 계산 정확성 ──────────────────────────────

def test_forward_per_calc_is_price_divided_by_eps():
    mod = _load()
    df = _make_consensus_df("A003", fwd_eps=10000.0, fwd_per=12.0, trail_eps=8000.0, trail_per=10.0)
    parsed = mod.parse_consensus(df)
    parsed["sector"] = "테스트섹터"
    price_map = pd.Series({"A003": 120000.0})
    out = mod.compute_derived(parsed, price_map)
    assert out.loc[0, "forward_per"] == pytest.approx(12.0, abs=0.01)  # 120000/10000


# ─── 4. eps_growth_expected 계산 ─────────────────────────────

def test_eps_growth_expected():
    mod = _load()
    df = _make_consensus_df("A004", fwd_eps=15000.0, fwd_per=8.0, trail_eps=10000.0, trail_per=12.0)
    parsed = mod.parse_consensus(df)
    parsed["sector"] = "테스트섹터"
    price_map = pd.Series({"A004": 150000.0})
    out = mod.compute_derived(parsed, price_map)
    assert out.loc[0, "eps_growth_expected"] == pytest.approx(0.5, abs=0.01)  # +50%


# ─── 5. 섹터 내 백분위: 저PER 종목이 더 낮은 백분위 ──────────

def test_sector_percentile_lower_per_gets_lower_rank():
    mod = _load()
    tickers = [f"T{i}" for i in range(6)]
    # 3종목씩 같은 섹터, forward EPS 같고 가격(=PER)만 다름
    rows = []
    for i, tkr in enumerate(tickers):
        rows.append({
            "ticker": tkr,
            "forward_year": 2026,
            "forward_eps": 10000.0,
            "forward_per_consensus": None,
            "trailing_eps": 8000.0,
            "trailing_per_consensus": 10.0,
            "sector": "섹터A",
        })
    df = pd.DataFrame(rows)
    price_map = pd.Series({tkr: (i + 1) * 50000 for i, tkr in enumerate(tickers)})
    df = mod.compute_derived(df, price_map)
    df = mod.add_sector_percentiles(df)
    lowest_per_pct = df.loc[df.ticker == "T0", "forward_per_sector_pct"].iloc[0]
    highest_per_pct = df.loc[df.ticker == "T5", "forward_per_sector_pct"].iloc[0]
    assert lowest_per_pct < highest_per_pct, "forward PER 낮을수록 섹터 내 백분위가 낮아야 함"


# ─── 6. 카탈로그 컬럼 검증 ────────────────────────────────────

def test_catalog_has_required_columns_and_rows():
    mod = _load()
    catalog = mod.build_catalog()
    required = {"factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"}
    assert required.issubset(set(catalog.columns))
    assert (catalog["factor_family"] == "forward_per").all()
    assert len(catalog) >= 4
