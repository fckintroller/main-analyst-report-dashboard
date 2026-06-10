"""단위 테스트: build_peg_factors.py"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "peg_mod",
        _root() / "scripts" / "03_analyze" / "build_peg_factors.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_df(**kwargs) -> pd.DataFrame:
    defaults = {
        "ticker": ["A001"],
        "snapshot_date": ["2026-06-05"],
        "sector": ["섹터A"],
        "forward_per": [10.0],
        "eps_growth_expected": [0.20],  # +20%
        "forward_valuation_score": [0.6],
        "close_price": [100000.0],
        "forward_eps": [10000.0],
    }
    defaults.update(kwargs)
    return pd.DataFrame(defaults)


# ─── 1. PEG 기본 계산 ─────────────────────────────────────────

def test_peg_basic_calculation():
    mod = _load()
    df = _make_df(forward_per=[10.0], eps_growth_expected=[0.20])
    result = mod.compute_peg(df)
    # PEG = 10 / (0.20 * 100) = 10 / 20 = 0.5
    assert result.loc[0, "peg_ratio"] == pytest.approx(0.5, abs=0.001)


# ─── 2. 이익 역성장 종목은 PEG=NaN ───────────────────────────

def test_negative_growth_yields_nan_peg():
    mod = _load()
    df = _make_df(forward_per=[10.0], eps_growth_expected=[-0.10])
    result = mod.compute_peg(df)
    assert np.isnan(result.loc[0, "peg_ratio"]), "이익 역성장 종목은 PEG=NaN이어야 함"


# ─── 3. PEG>10 클리핑 ────────────────────────────────────────

def test_peg_clipped_at_10():
    mod = _load()
    df = _make_df(forward_per=[100.0], eps_growth_expected=[0.01])  # PEG=100
    result = mod.compute_peg(df)
    assert result.loc[0, "peg_ratio"] == pytest.approx(10.0, abs=0.001)


# ─── 4. 섹터 백분위 — 낮은 PEG가 낮은 백분위 ─────────────────

def test_low_peg_gets_low_sector_percentile():
    mod = _load()
    rows = []
    for i in range(6):
        rows.append({
            "ticker": f"T{i}",
            "snapshot_date": "2026-06-05",
            "sector": "섹터A",
            "forward_per": float((i + 1) * 10),  # 10,20,...,60
            "eps_growth_expected": 0.2,           # 동일 성장률
            "forward_valuation_score": 0.5,
            "close_price": 100000.0,
            "forward_eps": 10000.0,
        })
    df = pd.DataFrame(rows)
    df = mod.compute_peg(df)
    df = mod.add_sector_percentiles(df)
    low = df.loc[df.ticker == "T0", "peg_sector_pct"].iloc[0]
    high = df.loc[df.ticker == "T5", "peg_sector_pct"].iloc[0]
    assert low < high, "PEG 낮은 종목이 섹터 백분위도 낮아야 함"


# ─── 5. 섹터 내 MIN_SECTOR_N 미만이면 NaN ─────────────────────

def test_small_sector_yields_nan_percentile():
    mod = _load()
    rows = [
        {"ticker": "X1", "snapshot_date": "2026-06-05", "sector": "소형섹터",
         "forward_per": 10.0, "eps_growth_expected": 0.2,
         "forward_valuation_score": 0.5, "close_price": 100000.0, "forward_eps": 10000.0},
        {"ticker": "X2", "snapshot_date": "2026-06-05", "sector": "소형섹터",
         "forward_per": 15.0, "eps_growth_expected": 0.2,
         "forward_valuation_score": 0.5, "close_price": 100000.0, "forward_eps": 10000.0},
    ]
    df = pd.DataFrame(rows)
    df = mod.compute_peg(df)
    df = mod.add_sector_percentiles(df)
    assert df["peg_sector_pct"].isna().all(), "MIN_SECTOR_N 미만 섹터는 백분위=NaN"


# ─── 6. 버킷 경계값 ───────────────────────────────────────────

def test_peg_bucket_boundaries():
    mod = _load()
    cases = [
        (0.4, "deep_value"),
        (0.8, "cheap"),
        (1.2, "neutral"),
        (1.8, "rich"),
        (3.0, "expensive"),
    ]
    for peg_val, expected_bucket in cases:
        growth = 0.2  # 20%
        per = peg_val * 20  # PEG = PER / 20
        df = _make_df(forward_per=[per], eps_growth_expected=[growth])
        df = mod.compute_peg(df)
        df = mod.add_sector_percentiles(df)
        df = mod.add_peg_score(df)
        bucket = df.loc[0, "peg_bucket"]
        assert bucket == expected_bucket, f"PEG={peg_val} → expected {expected_bucket}, got {bucket}"


# ─── 7. 카탈로그 검증 ────────────────────────────────────────

def test_catalog_structure():
    mod = _load()
    catalog = mod.build_catalog()
    required = {"factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"}
    assert required.issubset(set(catalog.columns))
    assert (catalog["factor_family"] == "peg").all()
    assert len(catalog) >= 4
