"""
한국 PPI(생산자물가지수) 인플레이션 사이클 팩터 구축 (월간 시계열).

신호:
  ① kor_ppi_index         : 생산자물가지수 원자료 (2010-01~)
  ② kor_ppi_mom           : 전월대비 변화율 (%)
  ③ kor_ppi_yoy           : 전년동월비 변화율 (%) — 인플레이션 압력의 핵심 지표
  ④ kor_ppi_yoy_chg3m     : YoY의 3개월 변화 (가속/감속, %p)

kor_ppi_yoy의 12M z-score + 36M(3년) 롤링 백분위 산출.
inflation_momentum_score = 0~1, 높을수록 인플레이션 가속 국면
inflation_cycle_regime   = kor_ppi_yoy_pctile_3y 기준 5단계 (disinflation~inflation_surge)
inflation_accel_flag     = YoY 12M z>1 & 3개월 변화(가속) 동시 충족 시 1

해석: 생산자물가는 기업 원가 압력의 선행지표 — PPI YoY 가속(inflation_accel_flag==1)은
       소재/원가 비중 높은 업종 마진 압박 + 기준금리 인상 압력으로 연결.
       ㉟은 OECD CLI(2024-01 이후 FRED 갱신 중단으로 제외)를 대체하는 국내 경기/물가 사이클 팩터로,
       ㉜(원/달러 환율, 수입물가)·㉛(신용스프레드, 통화정책 환경)과 함께 매크로 레짐 보조 지표로 활용.

출력 DB 테이블:
  factor_ppi_inflation_cycle_kr_month   : 월간 시계열
  factor_ppi_inflation_cycle_kr_catalog : 팩터 메타데이터
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
T5YIFR_PATH = PROJECT_ROOT / "data" / "raw" / "macro" / "macro_indices" / "T5YIFR.csv"

ZSCORE_WINDOW = 12     # 월 단위 rolling window (12M z-score, YoY 시리즈 특성상)
MIN_ZSCORE_OBS = 6
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
    monthly = df.set_index("date")["value"].resample("ME").last().dropna()
    monthly.index = monthly.index.to_period("M").to_timestamp()
    monthly.name = new_name
    monthly.index.name = "period"
    return monthly.reset_index()


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=MIN_ZSCORE_OBS).mean()
    std = series.rolling(window, min_periods=MIN_ZSCORE_OBS).std()
    return (series - mean) / std.replace(0, np.nan)


def _score_from_zscore(z: pd.Series) -> pd.Series:
    """z-score → 0~1 점수. clip(-3,3)/6 + 0.5"""
    return (z.clip(-3, 3) / 6 + 0.5).clip(0, 1)


def _rolling_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """자기 과거 window개월 내 현재값의 백분위 (0~1, 자기 자신 포함)"""
    return series.rolling(window, min_periods=min_periods).apply(
        lambda x: (x <= x[-1]).mean(), raw=True
    )


def _inflation_cycle_regime(pctile: float) -> str:
    if pd.isna(pctile):
        return "unknown"
    if pctile < 0.2:
        return "disinflation"
    if pctile < 0.4:
        return "low"
    if pctile < 0.6:
        return "neutral"
    if pctile < 0.8:
        return "elevated"
    return "inflation_surge"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 (월간) ──────────────────────────────────────
    base = _load_monthly(conn, "macro_macro_indices_kor_ppi", "date", "value", "kor_ppi_index")
    base = base.sort_values("period").reset_index(drop=True)

    # ── 변화율 ──────────────────────────────────────────────────────
    base["kor_ppi_mom"] = base["kor_ppi_index"].pct_change(1, fill_method=None) * 100
    base["kor_ppi_yoy"] = base["kor_ppi_index"].pct_change(12, fill_method=None) * 100
    base["kor_ppi_yoy_chg3m"] = base["kor_ppi_yoy"].diff(3)

    # ── 12M z-score ───────────────────────────────────────────────
    base["kor_ppi_yoy_zscore_12m"] = _zscore(base["kor_ppi_yoy"], ZSCORE_WINDOW)

    # ── 3년 롤링 백분위 ────────────────────────────────────────────
    base["kor_ppi_yoy_pctile_3y"] = _rolling_percentile(
        base["kor_ppi_yoy"], PCTILE_WINDOW, MIN_PCTILE_OBS
    )

    # ── 인플레이션 모멘텀 점수 (0~1, 높을수록 인플레 가속) ──────────────
    base["inflation_momentum_score"] = _score_from_zscore(base["kor_ppi_yoy_zscore_12m"])

    # PPI 공표 lag(2개월)로 최근 기간 미수록 → T5YIFR(미국 5년 기대인플레이션)으로 행 확장
    # PPI max 이후의 T5YIFR 월말 값으로 신규 행을 추가해 inflation_momentum_score를 채움
    try:
        t5 = pd.read_csv(T5YIFR_PATH, parse_dates=["DATE"])
        t5["value"] = pd.to_numeric(t5["T5YIFR"], errors="coerce")
        t5 = t5.dropna(subset=["value"]).sort_values("DATE")
        t5_monthly = t5.set_index("DATE")["value"].resample("ME").last().dropna()
        t5_monthly.index = t5_monthly.index.to_period("M").to_timestamp()
        t5_z = _zscore(t5_monthly, ZSCORE_WINDOW)
        t5_score = _score_from_zscore(t5_z)

        ppi_max = base["period"].max()
        t5_new = t5_score[t5_score.index > ppi_max]
        if not t5_new.empty:
            new_rows = pd.DataFrame({
                "period": t5_new.index,
                "inflation_momentum_score": t5_new.values,
            })
            base = pd.concat([base, new_rows], ignore_index=True).sort_values("period").reset_index(drop=True)
            logger.info("  T5YIFR proxy rows 추가: %d행 (max=%s)", len(t5_new), t5_new.index.max().strftime("%Y-%m-%d"))
    except Exception as e:
        logger.warning("  T5YIFR proxy 확장 실패 (무시): %s", e)

    # ── 인플레이션 사이클 레짐 (3년 백분위 기준 5단계) ───────────────────
    base["inflation_cycle_regime"] = base["kor_ppi_yoy_pctile_3y"].apply(_inflation_cycle_regime)

    # ── 가속 인플레 플래그 (YoY 12M z>1 & 3개월 변화 가속) ──────────────
    base["inflation_accel_flag"] = (
        (base["kor_ppi_yoy_zscore_12m"] > 1) & (base["kor_ppi_yoy_chg3m"] > 0)
    ).astype(int)

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "kor_ppi_index", "kor_ppi_mom", "kor_ppi_yoy", "kor_ppi_yoy_chg3m",
        "kor_ppi_yoy_zscore_12m", "kor_ppi_yoy_pctile_3y",
        "inflation_momentum_score", "inflation_cycle_regime", "inflation_accel_flag",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("kor_ppi_index",            "한국 생산자물가지수(PPI) 원자료",  "지수, 월간",                            "monthly"),
    ("kor_ppi_mom",               "PPI 전월대비 변화율",            "%",                                    "monthly"),
    ("kor_ppi_yoy",                "PPI 전년동월비 변화율",          "%, **핵심**",                          "monthly"),
    ("kor_ppi_yoy_chg3m",          "PPI YoY의 3개월 변화",           "%p, 가속(+)/감속(-)",                  "monthly"),
    ("kor_ppi_yoy_zscore_12m",     "PPI YoY 12M z-score",            "z-score",                              "monthly"),
    ("kor_ppi_yoy_pctile_3y",      "PPI YoY 3년 롤링 백분위",         "0~1, 1=3년래 최고 인플레이션",          "monthly"),
    ("inflation_momentum_score",   "인플레이션 모멘텀 점수",          "0~1, 높을수록 인플레 가속",             "monthly"),
    ("inflation_cycle_regime",     "인플레이션 사이클 레짐",          "disinflation/low/neutral/elevated/inflation_surge", "monthly"),
    ("inflation_accel_flag",       "가속 인플레 플래그",             "0/1, 1=YoY 12M z>1 & 3개월 변화 가속(경계 신호)", "monthly"),
]


def run():
    logger.info("ppi_inflation_cycle_kr 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_ppi_inflation_cycle_kr_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_ppi_inflation_cycle_kr_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_ppi_inflation_cycle_kr_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_ppi_inflation_cycle_kr_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "kor_ppi_yoy", "kor_ppi_yoy_zscore_12m",
                        "inflation_momentum_score", "inflation_cycle_regime", "inflation_accel_flag"]].to_string())
