"""
매크로 발표 지표 "추세-이탈(release shift)" 팩터 생성 — 캘린더 서프라이즈의 현실적 대안.

배경 (중요, 데이터 한계 — 반드시 읽을 것):
- 원래 목표였던 "캘린더 서프라이즈"(발표 실제치가 시장 컨센서스 예상치 대비 얼마나
  벗어났는가, surprise = actual - forecast)는 "컨센서스 forecast" 시계열을 무료로
  구할 수 없어 계산이 불가능하다.
  · data/economic_calendar.json(ForexFactory 피드)에는 forecast/previous는 있으나
    이번 주 일정이라 "actual"이 원천적으로 없다.
  · 과거 발표의 actual+forecast를 함께 제공하는 곳은 비공개 API/유료 데이터이거나
    스크래핑이 필요해(약관·안정성 문제) 이 프로젝트의 수집 규칙(공식 API/공개 피드)에
    맞지 않는다.
  · "절대 임의 보간 금지" 원칙상 forecast 값을 추정해 만들어낼 수도 없다.

대안 설계:
- collect_macro_release_history_once.py로 수집한 FRED "실제 발표치" 시계열에서,
  "이번 발표가 직전 대비/자기 과거 변화 패턴 대비 얼마나 이례적으로 변했는가"를
  계산한다. 즉 컨센서스 대비 서프라이즈가 아니라 "발표치 자체 추세로부터의 이탈도"이며,
  이를 "서프라이즈의 1차 근사(proxy)"로 캐치한다 — 이름과 해석에 그 차이를 명시한다.

입력 raw:
- data/raw/macro/release_history/{series_id}.csv (FRED 실제 발표치, date/value)

출력 CSV:
- data/raw/factors/macro_release_shift_period.csv
- data/raw/factors/macro_release_shift_factor_catalog.csv

출력 SQLite 테이블:
- factor_macro_release_shift_period
- factor_macro_release_shift_catalog

Caveat:
- 모델 예측 결과가 아니라 모델링 전 1차 가공 팩터 후보군이다.
- 이 팩터는 "컨센서스 대비 서프라이즈"가 아니라 "발표치의 자기 과거 변화 패턴 대비
  이례성"이다 — 이름(release_shift)과 해석 문구에서 이 차이를 분명히 한다.
- 변화 표준편차가 0이거나 trailing 관측치가 부족한 구간은 N/A로 남기고 임의 보간하지 않는다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
RELEASE_HISTORY_DIR = PROJECT_ROOT / "data" / "raw" / "macro" / "release_history"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"

ROLL_WINDOW = 24      # 변화폭 z-score 산출 trailing 관측치 수 (월간=약 2년, 주간=약 6개월)
MIN_PERIODS = 12      # rolling 최소 관측치 수

SERIES_META = {
    "PAYEMS": {"name_kr": "비농업 고용지수", "calendar_match": "비농업 고용지수", "frequency": "monthly"},
    "CPIAUCSL": {"name_kr": "소비자물가지수(CPI)", "calendar_match": "소비자물가지수", "frequency": "monthly"},
    "FEDFUNDS": {"name_kr": "연방기금 실효금리(기준금리 proxy)", "calendar_match": "기준금리 결정", "frequency": "monthly"},
    "UNRATE": {"name_kr": "실업률", "calendar_match": "실업률", "frequency": "monthly"},
    "ICSA": {"name_kr": "신규 실업수당 청구건수", "calendar_match": "신규 실업수당 청구건수", "frequency": "weekly"},
}


def discover_series() -> list[str]:
    return [sid for sid in SERIES_META if (RELEASE_HISTORY_DIR / f"{sid}.csv").exists()]


def load_release_panel(series_ids: list[str]) -> pd.DataFrame:
    frames = []
    for series_id in series_ids:
        path = RELEASE_HISTORY_DIR / f"{series_id}.csv"
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if df.empty or "date" not in df.columns or "value" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "value"])
        df["series_id"] = series_id
        frames.append(df[["series_id", "date", "value"]])
    if not frames:
        return pd.DataFrame(columns=["series_id", "date", "value"])
    panel = pd.concat(frames, ignore_index=True)
    return panel.sort_values(["series_id", "date"])


def add_release_shift_factors(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["series_id", "date"]).copy()
    grp_value = out.groupby("series_id")["value"]

    out["value_change"] = grp_value.diff(1)
    prev_value = grp_value.shift(1)
    out["value_change_pct"] = out["value_change"] / prev_value.abs()
    out.loc[prev_value == 0, "value_change_pct"] = np.nan

    grp_change = out.groupby("series_id")["value_change"]
    roll_mean = grp_change.transform(lambda s: s.rolling(ROLL_WINDOW, min_periods=MIN_PERIODS).mean())
    roll_std = grp_change.transform(lambda s: s.rolling(ROLL_WINDOW, min_periods=MIN_PERIODS).std())
    out["release_shift_zscore"] = (out["value_change"] - roll_mean) / roll_std
    out.loc[roll_std == 0, "release_shift_zscore"] = np.nan

    conditions = [
        out["release_shift_zscore"] >= 1.5,
        out["release_shift_zscore"] >= 0.5,
        out["release_shift_zscore"] <= -1.5,
        out["release_shift_zscore"] <= -0.5,
    ]
    choices = ["large_positive_shift", "positive_shift", "large_negative_shift", "negative_shift"]
    out["release_shift_bucket"] = np.select(conditions, choices, default="normal")
    out.loc[out["release_shift_zscore"].isna(), "release_shift_bucket"] = "N/A"

    out["calendar_match"] = out["series_id"].map(lambda s: SERIES_META.get(s, {}).get("calendar_match", "N/A"))
    out["indicator_name_kr"] = out["series_id"].map(lambda s: SERIES_META.get(s, {}).get("name_kr", "N/A"))
    return out


def build_factor_catalog() -> pd.DataFrame:
    rows = [
        ("macro_release_shift", "이번 발표치가 직전 발표 대비 얼마나, 어느 방향으로 변했는가?",
         "value_change / value_change_pct", "FRED 발표 실제치(actual)",
         "직전 관측치 대비 절대/비율 변화 (양수=지표 상승, 음수=하락 — 지표 성격에 따라 호재/악재 해석은 달라짐)", "필터"),
        ("macro_release_shift", "이번 변화가 이 지표의 평소 변화 패턴 대비 이례적으로 큰가?",
         "release_shift_zscore / release_shift_bucket", "발표치 변화량",
         (f"자기 과거 {ROLL_WINDOW}개 관측치의 변화량 분포 대비 z-score. "
          "주의: 이는 '컨센서스(forecast) 대비 서프라이즈'가 아니라 "
          "'발표치 자체의 추세 대비 이탈도'이다 — 무료 데이터로는 forecast 시계열을 구할 수 없어 "
          "서프라이즈의 1차 근사(proxy)로만 사용할 것"), "핵심"),
        ("macro_release_shift", "이 발표가 economic_calendar.json의 어떤 일정과 매칭되는가?",
         "calendar_match / indicator_name_kr", "지표 매핑",
         "economic_calendar.json에 등장하는 지표명과의 매칭 라벨 (캘린더 일정 + 발표치 이력을 함께 참고할 때 사용)", "참고"),
    ]
    return pd.DataFrame(
        rows,
        columns=["factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"],
    )


def build_outputs(series_ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = load_release_panel(series_ids)
    enriched = add_release_shift_factors(panel)
    catalog = build_factor_catalog()
    return enriched, catalog


def save_outputs(panel: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int | str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    period_path = OUTPUT_DIR / "macro_release_shift_period.csv"
    catalog_path = OUTPUT_DIR / "macro_release_shift_factor_catalog.csv"

    panel_save = panel.copy()
    panel_save["date"] = pd.to_datetime(panel_save["date"]).dt.strftime("%Y-%m-%d")

    panel_save.to_csv(period_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    panel_save.to_sql("factor_macro_release_shift_period", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_macro_release_shift_catalog", conn, if_exists="replace", index=False)

    return {
        "period_path": str(period_path),
        "catalog_path": str(catalog_path),
        "rows": len(panel_save),
        "series": int(panel_save["series_id"].nunique()),
        "date_min": panel_save["date"].min(),
        "date_max": panel_save["date"].max(),
        "catalog_rows": len(catalog),
    }


def main() -> None:
    series_ids = discover_series()
    with sqlite3.connect(DB_PATH) as conn:
        panel, catalog = build_outputs(series_ids)
        result = save_outputs(panel, catalog, conn)
    print(result)


if __name__ == "__main__":
    main()
