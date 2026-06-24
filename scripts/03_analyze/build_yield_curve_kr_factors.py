"""
한국 국채 수익률곡선 (Level / Slope / Curvature) 팩터 구축 (월간 시계열).

신호:
  ① yield_level            : 금리 레벨 (1y/5y/10y 평균, %)
  ② yield_slope_10y1y      : 기간 스프레드 (10y - 1y, %p) — 양수=정상, 음수=역전
  ③ yield_curvature        : 곡률 (2*5y - 1y - 10y, %p) — 중기물 상대적 고/저평가(커브 휨 정도)

각 슬로프/곡률의 6M z-score + 36M(3년) 롤링 백분위 산출.
curve_regime = yield_slope_pctile_3y 기준 5단계 (deeply_inverted~steep)
curve_inversion_flag = yield_slope_10y1y < 0 (수익률곡선 역전, 경기침체 선행 신호)

해석: ㉛(신용스프레드)는 회사채-국고3y 신용 프리미엄을 다루는 반면,
       본 팩터는 국고채 자체의 기간구조(term structure)를 다룸 — 통화정책/성장 기대 변화 포착.
       slope 축소(역전 근접) → 은행/보험 등 금리민감 가치주 비중 축소, 성장주 상대 매력 검토.

출력 DB 테이블:
  factor_yield_curve_kr_month   : 월간 시계열
  factor_yield_curve_kr_catalog : 팩터 메타데이터
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

ZSCORE_WINDOW = 6      # 월 단위 rolling window (6M z-score)
MIN_ZSCORE_OBS = 3
PCTILE_WINDOW = 36     # 3년 롤링 백분위
MIN_PCTILE_OBS = 12


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_monthly(conn: sqlite3.Connection, table: str, date_col: str, val_col: str,
                  new_name: str) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT [{date_col}] AS date, [{val_col}] AS value FROM [{table}]", conn)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna().sort_values("date")
    # 월말 리샘플
    monthly = df.set_index("date")["value"].resample("ME").last().dropna()
    monthly.index = monthly.index.to_period("M").to_timestamp()
    monthly.name = new_name
    monthly.index.name = "period"
    return monthly.reset_index()


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=MIN_ZSCORE_OBS).mean()
    std = series.rolling(window, min_periods=MIN_ZSCORE_OBS).std()
    return (series - mean) / std.replace(0, np.nan)


def _rolling_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """자기 과거 window개월 내 현재값의 백분위 (0~1, 자기 자신 포함)"""
    return series.rolling(window, min_periods=min_periods).apply(
        lambda x: (x <= x[-1]).mean(), raw=True
    )


def _curve_regime(pctile: float) -> str:
    if pd.isna(pctile):
        return "unknown"
    if pctile < 0.2:
        return "deeply_inverted"
    if pctile < 0.4:
        return "inverted"
    if pctile < 0.6:
        return "flat"
    if pctile < 0.8:
        return "normal"
    return "steep"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 (일별 → 월말 리샘플) ──────────────────────
    gov1y  = _load_monthly(conn, "macro_macro_indices_kor_gov1y",  "date", "value", "kor_gov1y")
    gov5y  = _load_monthly(conn, "macro_macro_indices_kor_gov5y",  "date", "value", "kor_gov5y")
    gov10y = _load_monthly(conn, "macro_macro_indices_kor_gov10y", "date", "value", "kor_gov10y")
    gov30y = _load_monthly(conn, "macro_macro_indices_kor_gov30y", "date", "value", "kor_gov30y")

    # ── 병합 ─────────────────────────────────────────────────────
    base = (gov1y.merge(gov5y, on="period", how="outer")
                  .merge(gov10y, on="period", how="outer")
                  .merge(gov30y, on="period", how="outer")
                  .sort_values("period")
                  .reset_index(drop=True))

    # ── Level / Slope / Curvature ───────────────────────────────────
    base["yield_level"] = base[["kor_gov1y", "kor_gov5y", "kor_gov10y"]].mean(axis=1)
    base["yield_slope_10y1y"] = base["kor_gov10y"] - base["kor_gov1y"]
    base["yield_curvature"] = 2 * base["kor_gov5y"] - base["kor_gov1y"] - base["kor_gov10y"]

    # ── 레벨 전월대비 변화 ────────────────────────────────────────────
    base["yield_level_mom1m"] = base["yield_level"].diff(1)

    # ── 6M z-score ────────────────────────────────────────────────
    base["yield_slope_zscore_6m"] = _zscore(base["yield_slope_10y1y"], ZSCORE_WINDOW)
    base["yield_curvature_zscore_6m"] = _zscore(base["yield_curvature"], ZSCORE_WINDOW)

    # ── 3년 롤링 백분위 (절대 레벨 참고) ────────────────────────────
    base["yield_slope_pctile_3y"] = _rolling_percentile(
        base["yield_slope_10y1y"], PCTILE_WINDOW, MIN_PCTILE_OBS
    )

    # ── 커브 레짐 (3년 백분위 기준 5단계) ───────────────────────────
    base["curve_regime"] = base["yield_slope_pctile_3y"].apply(_curve_regime)

    # ── 역전 플래그 (10y-1y < 0) ─────────────────────────────────────
    base["curve_inversion_flag"] = (base["yield_slope_10y1y"] < 0).astype(int)

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "kor_gov1y", "kor_gov5y", "kor_gov10y", "kor_gov30y",
        "yield_level", "yield_level_mom1m",
        "yield_slope_10y1y", "yield_slope_zscore_6m", "yield_slope_pctile_3y",
        "yield_curvature", "yield_curvature_zscore_6m",
        "curve_regime", "curve_inversion_flag",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("kor_gov1y",                "한국 국고채 1년 금리",            "%, 일별→월말",                          "monthly"),
    ("kor_gov5y",                "한국 국고채 5년 금리",            "%, 일별→월말",                          "monthly"),
    ("kor_gov10y",               "한국 국고채 10년 금리",           "%, 일별→월말",                          "monthly"),
    ("kor_gov30y",                "한국 국고채 30년 금리 (2012-09~)", "%, 일별→월말, 이전 기간 NaN",            "monthly"),
    ("yield_level",              "금리 레벨 (1y/5y/10y 평균)",       "%, 통화정책 전반 수준",                  "monthly"),
    ("yield_level_mom1m",        "금리 레벨 전월대비 변화",          "%p",                                   "monthly"),
    ("yield_slope_10y1y",        "기간 스프레드 (10y-1y)",          "%p, 양수=정상 / 음수=역전",              "monthly"),
    ("yield_slope_zscore_6m",    "기간 스프레드 6M z-score",        "z-score",                              "monthly"),
    ("yield_slope_pctile_3y",    "기간 스프레드 3년 롤링 백분위",     "0~1, 1=3년래 최대 스프레드(가장 정상)",   "monthly"),
    ("yield_curvature",          "곡률 (2*5y-1y-10y)",             "%p, 양수=중기물 험프(고평가)",           "monthly"),
    ("yield_curvature_zscore_6m","곡률 6M z-score",                "z-score",                              "monthly"),
    ("curve_regime",             "수익률곡선 레짐",                 "deeply_inverted/inverted/flat/normal/steep (3년 백분위 기준)", "monthly"),
    ("curve_inversion_flag",     "수익률곡선 역전 플래그",          "0/1, 1=10y-1y<0 (역전, 경기침체 선행 신호)", "monthly"),
]


def run():
    logger.info("yield_curve_kr 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_yield_curve_kr_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_yield_curve_kr_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_yield_curve_kr_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_yield_curve_kr_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "yield_level", "yield_slope_10y1y",
                        "yield_curvature", "curve_regime", "curve_inversion_flag"]].to_string())
