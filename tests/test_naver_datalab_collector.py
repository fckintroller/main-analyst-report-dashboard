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


def test_parse_response_to_frame_returns_long_dataframe():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "collect_naver_datalab_once.py", "naver_datalab_test")

    payload = {
        "startDate": "2026-05-01",
        "endDate": "2026-06-01",
        "timeUnit": "week",
        "results": [
            {
                "title": "battery_theme",
                "keywords": ["2차전지", "배터리"],
                "data": [
                    {"period": "2026-05-05", "ratio": 12.5},
                    {"period": "2026-05-12", "ratio": 17},
                ],
            }
        ],
    }

    df = mod.parse_response_to_frame(payload)

    assert list(df.columns) == ["period", "group_name", "keywords", "ratio"]
    assert len(df) == 2
    assert df.loc[0, "group_name"] == "battery_theme"
    assert df.loc[0, "keywords"] == "2차전지|배터리"
    assert df.loc[1, "ratio"] == 17.0


def test_build_payload_uses_keyword_groups_and_date_range():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "collect_naver_datalab_once.py", "naver_datalab_test_payload")

    payload = mod.build_payload(
        keyword_groups=[{"groupName": "power", "keywords": ["전력", "송전망"]}],
        start_date="2026-01-01",
        end_date="2026-06-01",
        time_unit="month",
    )

    assert payload == {
        "startDate": "2026-01-01",
        "endDate": "2026-06-01",
        "timeUnit": "month",
        "keywordGroups": [{"groupName": "power", "keywords": ["전력", "송전망"]}],
    }


def test_save_frame_writes_csv_with_expected_filename(tmp_path):
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "collect_naver_datalab_once.py", "naver_datalab_test_save")
    df = pd.DataFrame([
        {"period": "2026-05-01", "group_name": "battery_theme", "keywords": "2차전지|배터리", "ratio": 1.0}
    ])

    path = mod.save_frame(df, tmp_path, "theme_interest", "month")

    assert path.name == "naver_datalab_theme_interest_month.csv"
    loaded = pd.read_csv(path)
    assert loaded.loc[0, "group_name"] == "battery_theme"
    assert loaded.loc[0, "ratio"] == 1.0


def test_chunk_keyword_groups_limits_each_request_to_five_groups():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "collect_naver_datalab_once.py", "naver_datalab_test_chunk")
    groups = [{"groupName": f"g{i}", "keywords": [f"k{i}"]} for i in range(12)]

    chunks = list(mod.chunk_keyword_groups(groups, max_groups=5))

    assert [len(chunk) for chunk in chunks] == [5, 5, 2]
    assert chunks[0][0]["groupName"] == "g0"
    assert chunks[-1][-1]["groupName"] == "g11"


def test_sector_universe_contains_broad_quant_sector_coverage():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "collect_naver_datalab_once.py", "naver_datalab_test_sector_universe")

    groups = mod.get_keyword_groups("sector")
    names = {group["groupName"] for group in groups}

    assert len(groups) >= 30
    assert {"semiconductor", "battery", "auto", "shipbuilding", "bank", "bio_pharma", "defense"}.issubset(names)


def test_chunk_keyword_groups_with_anchor_keeps_each_request_at_five_groups():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "collect_naver_datalab_once.py", "naver_datalab_test_anchor_chunk")
    groups = [{"groupName": f"sector_{i}", "keywords": [f"k{i}"]} for i in range(10)]
    anchor = {"groupName": "market_anchor", "keywords": ["코스피", "코스닥", "주식"]}

    chunks = list(mod.chunk_keyword_groups_with_anchor(groups, anchor, max_groups=5))

    assert [len(chunk) for chunk in chunks] == [5, 5, 3]
    assert all(chunk[0]["groupName"] == "market_anchor" for chunk in chunks)
    assert all(len(chunk) <= 5 for chunk in chunks)


def test_calculate_anchor_normalized_factors_adds_relative_metrics():
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "collect_naver_datalab_once.py", "naver_datalab_test_factor")
    df = pd.DataFrame([
        {"period": "2026-01-01", "group_name": "market_anchor", "keywords": "코스피|코스닥|주식", "ratio": 50.0, "chunk_id": 0},
        {"period": "2026-01-01", "group_name": "semiconductor", "keywords": "반도체|HBM", "ratio": 25.0, "chunk_id": 0},
        {"period": "2026-02-01", "group_name": "market_anchor", "keywords": "코스피|코스닥|주식", "ratio": 40.0, "chunk_id": 0},
        {"period": "2026-02-01", "group_name": "semiconductor", "keywords": "반도체|HBM", "ratio": 60.0, "chunk_id": 0},
    ])

    factors = mod.calculate_anchor_normalized_factors(df)

    assert list(factors["group_name"].unique()) == ["semiconductor"]
    assert factors.loc[0, "anchor_ratio"] == 50.0
    assert factors.loc[0, "anchor_relative_ratio"] == 50.0
    assert factors.loc[1, "anchor_relative_ratio"] == 150.0
    assert "momentum_1p" in factors.columns
