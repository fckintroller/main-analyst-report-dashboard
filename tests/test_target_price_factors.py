"""단위 테스트: build_target_price_factors.py"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "tp_mod",
        _root() / "scripts" / "03_analyze" / "build_target_price_factors.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_price_df(tickers, prices, sectors) -> pd.DataFrame:
    return pd.DataFrame({"ticker": tickers, "close_price": prices, "sector": sectors})


def _make_tp_df(tickers, target_prices, opinion_scores) -> pd.DataFrame:
    return pd.DataFrame({
        "ticker": tickers,
        "target_price": target_prices,
        "opinion_score": opinion_scores,
        "opinion_text": ["매수"] * len(tickers),
    })


# ─── 1. 괴리율 기본 계산 ──────────────────────────────────────

def test_tp_divergence_basic():
    mod = _load()
    price_df = _make_price_df(["A001"], [80000.0], ["섹터A"])
    tp_df = _make_tp_df(["A001"], [100000.0], [4.0])
    result = mod.compute_divergence(tp_df, price_df)
    assert result.loc[0, "tp_divergence"] == pytest.approx(0.25, abs=0.001)  # (100000-80000)/80000 = 25%


# ─── 2. 목표주가 0이면 NaN ───────────────────────────────────

def test_zero_target_price_yields_nan():
    mod = _load()
    price_df = _make_price_df(["A002"], [80000.0], ["섹터A"])
    tp_df = _make_tp_df(["A002"], [0.0], [None])
    result = mod.compute_divergence(tp_df, price_df)
    assert np.isnan(result.loc[0, "tp_divergence"])


# ─── 3. 높은 괴리율이 높은 섹터 백분위 ──────────────────────

def test_high_divergence_gets_high_sector_pct():
    mod = _load()
    tickers = [f"T{i}" for i in range(5)]
    prices = [100000.0] * 5
    # 목표주가 차별화: T4가 가장 높은 상승여력
    targets = [80000.0, 90000.0, 100000.0, 120000.0, 150000.0]
    price_df = _make_price_df(tickers, prices, ["섹터A"] * 5)
    tp_df = _make_tp_df(tickers, targets, [4.0] * 5)
    df = mod.compute_divergence(tp_df, price_df)
    df = mod.add_sector_percentiles(df)
    lowest = df.loc[df.ticker == "T0", "tp_divergence_sector_pct"].iloc[0]
    highest = df.loc[df.ticker == "T4", "tp_divergence_sector_pct"].iloc[0]
    assert highest > lowest


# ─── 4. 버킷 경계값 검증 ─────────────────────────────────────

def test_bucket_boundaries():
    mod = _load()
    cases = [
        (0.35, "deep_value"),
        (0.20, "cheap"),
        (0.05, "neutral"),
        (-0.05, "rich"),
        (-0.15, "expensive"),
    ]
    for div, expected in cases:
        price = 100000.0
        target = price * (1 + div)
        price_df = _make_price_df(["X"], [price], ["섹터A"])
        tp_df = _make_tp_df(["X"], [target], [4.0])
        df = mod.compute_divergence(tp_df, price_df)
        df = mod.add_sector_percentiles(df)
        df = mod.add_score(df)
        bucket = df.loc[0, "target_price_bucket"]
        assert bucket == expected, f"괴리율={div:.0%} → expected {expected}, got {bucket}"


# ─── 5. 의견점수 정규화 ──────────────────────────────────────

def test_opinion_score_normalization():
    mod = _load()
    price_df = _make_price_df(["A003"], [100000.0], ["섹터A"])
    tp_df = _make_tp_df(["A003"], [120000.0], [5.0])  # 만점
    df = mod.compute_divergence(tp_df, price_df)
    assert df.loc[0, "opinion_score_norm"] == pytest.approx(1.0, abs=0.001)

    tp_df2 = _make_tp_df(["A003"], [120000.0], [1.0])  # 최저
    df2 = mod.compute_divergence(tp_df2, price_df)
    assert df2.loc[0, "opinion_score_norm"] == pytest.approx(0.0, abs=0.001)


# ─── 6. 카탈로그 검증 ────────────────────────────────────────

def test_catalog_structure():
    mod = _load()
    catalog = mod.build_catalog()
    required = {"factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"}
    assert required.issubset(set(catalog.columns))
    assert (catalog["factor_family"] == "target_price").all()
    assert len(catalog) >= 4
