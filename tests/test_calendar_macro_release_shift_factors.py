import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_module(path: Path, name: str = "shift_mod"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load():
    project = Path(__file__).resolve().parents[1]
    return load_module(project / "scripts" / "03_analyze" / "build_calendar_macro_release_shift_factors.py")


def _make_panel(mod, n=30):
    dates = pd.date_range("2023-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(11)
    rows = []
    # STABLE: 변화폭이 항상 비슷 (이례적 변화 없음) / SPIKE: 마지막에 큰 점프
    for series_id, base, step, spike_last in [("STABLE", 100.0, 1.0, False), ("SPIKE", 100.0, 1.0, True)]:
        value = base
        for i, d in enumerate(dates):
            value = value + step + rng.normal(0, 0.05)
            if spike_last and i == n - 1:
                value = value + 20.0  # 평소 변화(약 1.0) 대비 훨씬 큰 점프
            rows.append({"series_id": series_id, "date": d, "value": value})
    return pd.DataFrame(rows)


def test_value_change_is_simple_diff():
    mod = _load()
    panel = _make_panel(mod)
    out = mod.add_release_shift_factors(panel)
    stable = out[out["series_id"] == "STABLE"].iloc[5]
    prev = out[out["series_id"] == "STABLE"].iloc[4]
    assert np.isclose(stable["value_change"], stable["value"] - prev["value"])


def test_release_shift_zscore_flags_unusual_jump():
    mod = _load()
    panel = _make_panel(mod)
    out = mod.add_release_shift_factors(panel)
    spike_last = out[out["series_id"] == "SPIKE"].iloc[-1]
    stable_last = out[out["series_id"] == "STABLE"].iloc[-1]
    assert spike_last["release_shift_zscore"] > 2.0
    assert spike_last["release_shift_bucket"] == "large_positive_shift"
    assert stable_last["release_shift_bucket"] in {"normal", "positive_shift", "negative_shift"}


def test_zscore_is_na_when_history_too_short():
    mod = _load()
    short_panel = pd.DataFrame({
        "series_id": ["X"] * 5,
        "date": pd.date_range("2026-01-01", periods=5, freq="MS"),
        "value": [10.0, 11.0, 12.0, 13.0, 14.0],
    })
    out = mod.add_release_shift_factors(short_panel)
    assert out["release_shift_zscore"].isna().all()  # MIN_PERIODS(12) 미만 → 임의 보간하지 않고 N/A


def test_calendar_match_label_is_attached():
    mod = _load()
    panel = pd.DataFrame({
        "series_id": ["PAYEMS", "UNKNOWN_SERIES"],
        "date": [pd.Timestamp("2026-01-01")] * 2,
        "value": [100.0, 200.0],
    })
    out = mod.add_release_shift_factors(panel)
    assert out.loc[out["series_id"] == "PAYEMS", "calendar_match"].iloc[0] == "비농업 고용지수"
    assert out.loc[out["series_id"] == "UNKNOWN_SERIES", "calendar_match"].iloc[0] == "N/A"


def test_factor_catalog_documents_proxy_limitation():
    mod = _load()
    catalog = mod.build_factor_catalog()
    assert set(catalog.columns) == {
        "factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use",
    }
    assert (catalog["factor_family"] == "macro_release_shift").all()
    # 컨센서스 대비 서프라이즈가 아님을 catalog에서 명시해야 한다 (데이터 한계 투명성)
    joined = " ".join(catalog["interpretation"].tolist())
    assert "forecast" in joined or "컨센서스" in joined
