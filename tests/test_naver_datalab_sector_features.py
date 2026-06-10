import importlib.util
import sys
from pathlib import Path

import pandas as pd


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_build_features_adds_three_factor_family_columns():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "03_analyze" / "build_naver_datalab_sector_features.py", "naver_sector_features_test")
    periods = pd.date_range("2025-01-01", periods=14, freq="MS").strftime("%Y-%m-%d")
    rows = []
    for i, period in enumerate(periods):
        rows.append({"period": period, "group_name": "semiconductor", "keywords": "반도체|HBM", "chunk_id": 0, "ratio": 20 + i, "anchor_ratio": 50, "anchor_relative_ratio": 40 + i})
        rows.append({"period": period, "group_name": "bank", "keywords": "은행|은행주", "chunk_id": 1, "ratio": 50 - i, "anchor_ratio": 40, "anchor_relative_ratio": 125 - i})

    features = mod.build_features(pd.DataFrame(rows))

    assert {"recent_strength_score", "market_relative_score", "cross_sector_rank_score"}.issubset(features.columns)
    assert {"ratio_zscore_12m", "anchor_relative_zscore_12m", "relative_rank_pct"}.issubset(features.columns)
    assert features["factor_family_recent_strength"].iloc[0] == "same_sector_recent_strength"
    assert features["factor_family_market_relative"].iloc[0] == "market_relative_strength"
    assert features["factor_family_cross_sector"].iloc[0] == "cross_sector_current_rank"


def test_build_factor_catalog_classifies_candidates_into_three_groups():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "03_analyze" / "build_naver_datalab_sector_features.py", "naver_sector_catalog_test")

    catalog = mod.build_factor_catalog()

    families = set(catalog["factor_family"])
    assert families == {"same_sector_recent_strength", "market_relative_strength", "cross_sector_current_rank"}
    assert "ratio_momentum_3m" in set(catalog["factor_name"])
    assert "anchor_relative_zscore_12m" in set(catalog["factor_name"])
    assert "relative_rank_pct" in set(catalog["factor_name"])


def test_build_classified_long_outputs_one_row_per_family_per_sector_period():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "03_analyze" / "build_naver_datalab_sector_features.py", "naver_sector_long_test")
    features = pd.DataFrame([
        {
            "period": "2026-01-01",
            "group_name": "semiconductor",
            "keywords": "반도체|HBM",
            "recent_strength_score": 1.2,
            "market_relative_score": 0.7,
            "cross_sector_rank_score": 0.9,
            "recent_strength_bucket": "strong",
            "market_relative_bucket": "strong",
            "cross_sector_rank_bucket": "top",
        }
    ])

    long_df = mod.build_classified_long(features)

    assert len(long_df) == 3
    assert set(long_df["factor_family"]) == {"same_sector_recent_strength", "market_relative_strength", "cross_sector_current_rank"}
    assert set(long_df["signal_bucket"]) == {"strong", "top"}
