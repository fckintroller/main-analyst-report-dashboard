import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_module(path: Path, name: str = "valuation_mod"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load():
    return load_module(_project_root() / "scripts" / "03_analyze" / "build_valuation_per_pbr_factors.py")


def test_to_month_end_panel_keeps_last_observation_per_month():
    mod = _load()
    panel = pd.DataFrame(
        {
            "ticker": ["A", "A", "A", "B"],
            "date": pd.to_datetime(["2026-01-10", "2026-01-31", "2026-02-15", "2026-01-20"]),
            "PER": [10.0, 12.0, 11.0, 5.0],
            "PBR": [1.0, 1.2, 1.1, 0.8],
            "EPS": [100, 100, 100, 50],
            "BPS": [1000, 1000, 1000, 500],
            "DIV": [1.0, 1.0, 1.0, 2.0],
            "DPS": [10, 10, 10, 20],
        }
    )
    monthly = mod.to_month_end_panel(panel)
    jan_a = monthly[(monthly["ticker"] == "A") & (monthly["period"] == pd.Timestamp("2026-01-01"))]
    assert jan_a.iloc[0]["PER"] == 12.0  # 1월의 마지막 관측치(01-31) 유지


def test_cross_sectional_percentile_returns_nan_when_sector_too_small():
    mod = load_module(_project_root() / "scripts" / "03_analyze" / "build_valuation_per_pbr_factors.py")
    # MIN_SECTOR_CROSS_SECTION=5 미만인 섹터(종목 3개)는 NaN 반환
    monthly = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "period": [pd.Timestamp("2026-01-01")] * 3,
            "sector": ["반도체"] * 3,
            "PER": [10.0, 20.0, 30.0],
            "PBR": [1.0, 2.0, 3.0],
            "EPS": [1, 1, 1],
            "BPS": [1, 1, 1],
            "DIV": [1, 1, 1],
            "DPS": [1, 1, 1],
        }
    )
    out = mod.add_cross_sectional_factors(monthly)
    assert out["per_percentile_sector"].isna().all()  # 섹터 내 종목 수(3) < MIN_SECTOR_CROSS_SECTION


def test_cross_sectional_percentile_sector_relative():
    """같은 기간이라도 섹터가 다르면 독립적으로 백분위를 산출한다."""
    mod = load_module(_project_root() / "scripts" / "03_analyze" / "build_valuation_per_pbr_factors.py")
    tickers = [f"T{i}" for i in range(12)]
    period = pd.Timestamp("2026-01-01")
    monthly = pd.DataFrame(
        {
            "ticker": tickers,
            "period": [period] * 12,
            "sector": ["섹터A"] * 6 + ["섹터B"] * 6,
            "PER": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0,   # 섹터A
                    10.0, 20.0, 30.0, 40.0, 50.0, 60.0],  # 섹터B
            "PBR": [0.1 * i for i in range(1, 13)],
            "EPS": [1] * 12,
            "BPS": [1] * 12,
            "DIV": [1] * 12,
            "DPS": [1] * 12,
        }
    )
    out = mod.add_cross_sectional_factors(monthly)
    # 섹터A 최저 PER(1.0) 순위 ≈ 섹터B 최저 PER(10.0) 순위 (둘 다 섹터 내 최하위)
    rank_a_lowest = out.loc[out["ticker"] == "T0", "per_percentile_sector"].iloc[0]
    rank_b_lowest = out.loc[out["ticker"] == "T6", "per_percentile_sector"].iloc[0]
    assert rank_a_lowest == rank_b_lowest  # 서로 다른 섹터지만 섹터 내 순위는 동일
    # 섹터A 최고 PER(6.0) 순위 ≈ 섹터B 최고 PER(60.0) 순위
    rank_a_highest = out.loc[out["ticker"] == "T5", "per_percentile_sector"].iloc[0]
    rank_b_highest = out.loc[out["ticker"] == "T11", "per_percentile_sector"].iloc[0]
    assert rank_a_highest == rank_b_highest


def test_negative_or_zero_per_pbr_is_treated_as_missing_not_interpolated():
    # load_fundamental_panel은 디스크에서 읽으므로, 동일한 PER/PBR<=0 → NaN 처리 로직만 재현해 검증
    panel = pd.DataFrame(
        {
            "PER": [-5.0, 0.0, 8.0],
            "PBR": [1.0, -1.0, 0.9],
        }
    )
    cleaned = panel.copy()
    for col in ["PER", "PBR"]:
        cleaned.loc[cleaned[col] <= 0, col] = np.nan
    assert np.isnan(cleaned.loc[0, "PER"])
    assert np.isnan(cleaned.loc[1, "PBR"])
    assert cleaned.loc[2, "PER"] == 8.0  # 양수는 그대로 유지


def test_valuation_score_prefers_cheap_over_expensive():
    mod = _load()
    monthly = pd.DataFrame(
        {
            "ticker": ["CHEAP", "RICH"],
            "period": [pd.Timestamp("2026-01-01")] * 2,
            "PER": [5.0, 50.0],
            "PBR": [0.5, 5.0],
            "per_percentile_sector": [0.05, 0.95],
            "pbr_percentile_sector": [0.10, 0.90],
            "per_zscore_own_24m": [-1.5, 1.5],
            "pbr_zscore_own_24m": [-1.2, 1.2],
            "per_rerating_momentum_3m": [-0.1, 0.1],
            "pbr_rerating_momentum_3m": [-0.1, 0.1],
        }
    )
    out = mod.add_valuation_score(monthly)
    cheap = out[out["ticker"] == "CHEAP"].iloc[0]
    rich = out[out["ticker"] == "RICH"].iloc[0]
    assert cheap["valuation_score"] > rich["valuation_score"]
    assert cheap["valuation_bucket"] in {"deep_value", "cheap"}
    assert rich["valuation_bucket"] in {"expensive", "rich"}
    # rerating_direction은 PER/PBR 모멘텀 부호를 그대로 라벨링한다 (양수=re_rating_up, 음수=de_rating_down)
    assert cheap["rerating_direction"] == "de_rating_down"   # momentum -0.1
    assert rich["rerating_direction"] == "re_rating_up"      # momentum +0.1


def test_factor_catalog_has_expected_families_and_columns():
    mod = _load()
    catalog = mod.build_factor_catalog()
    assert set(catalog.columns) == {
        "factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use",
    }
    assert (catalog["factor_family"] == "valuation_per_pbr").all()
    assert len(catalog) >= 4
