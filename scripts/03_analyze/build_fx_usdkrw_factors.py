"""
원/달러 환율 모멘텀 팩터 구축 (월간 시계열).

신호:
  ① usd_krw_close       : 원/달러 환율 종가 (월말)
  ② usd_krw_ret_1m/3m   : 전월/3개월 수익률 (원화 약세 시 양수)
  ③ usd_krw_zscore_6m   : 환율 6M z-score (레벨)
  ④ usd_krw_pctile_3y   : 환율 3년 롤링 백분위 (0=3년래 최저=원화 최강)

won_strength_score = 0~1, 높을수록 원화 강세 (환율 6M z-score가 낮음)
fx_regime = usd_krw_pctile_3y 기준 5단계 (won_very_strong~won_very_weak)
rapid_depreciation_flag = 환율이 6M 평균 대비 높고(z>1) 추가 상승 중 → 원화 급약세 경계

해석: ⑦(macro_spread, 미국 금리/달러 환경)·⑨(외국인 수급)와 상호 보완 —
       원화 약세(usd_krw 상승) 가속은 외국인 자금 유출 압력 및 수입 인플레 우려로 연결.

출력 DB 테이블:
  factor_fx_usdkrw_month   : 월간 시계열
  factor_fx_usdkrw_catalog : 팩터 메타데이터
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


def _score_from_zscore(z: pd.Series) -> pd.Series:
    """z-score → 0~1 점수. clip(-3,3)/6 + 0.5"""
    return (z.clip(-3, 3) / 6 + 0.5).clip(0, 1)


def _rolling_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """자기 과거 window개월 내 현재값의 백분위 (0~1, 자기 자신 포함)"""
    return series.rolling(window, min_periods=min_periods).apply(
        lambda x: (x <= x[-1]).mean(), raw=True
    )


def _fx_regime(pctile: float) -> str:
    if pd.isna(pctile):
        return "unknown"
    if pctile < 0.2:
        return "won_very_strong"
    if pctile < 0.4:
        return "won_strong"
    if pctile < 0.6:
        return "neutral"
    if pctile < 0.8:
        return "won_weak"
    return "won_very_weak"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 (일별 → 월말 리샘플) ──────────────────────
    fx = _load_monthly(conn, "macro_exchange_rates_usd_krw", "Unnamed: 0", "Close", "usd_krw_close")

    base = fx.sort_values("period").reset_index(drop=True)

    # ── 모멘텀 (수익률) ──────────────────────────────────────────
    base["usd_krw_ret_1m"] = base["usd_krw_close"].pct_change(1, fill_method=None)
    base["usd_krw_ret_3m"] = base["usd_krw_close"].pct_change(3, fill_method=None)

    # ── 6M z-score (레벨) ────────────────────────────────────────
    base["usd_krw_zscore_6m"] = _zscore(base["usd_krw_close"], ZSCORE_WINDOW)

    # ── 3년 롤링 백분위 (절대 레벨 참고) ────────────────────────────
    base["usd_krw_pctile_3y"] = _rolling_percentile(
        base["usd_krw_close"], PCTILE_WINDOW, MIN_PCTILE_OBS
    )

    # ── 원화 강도 점수 (0~1, 높을수록 원화 강세=환율 하락) ──────────
    base["won_strength_score"] = _score_from_zscore(-base["usd_krw_zscore_6m"])

    # ── 환율 레짐 (3년 백분위 기준 5단계) ───────────────────────────
    base["fx_regime"] = base["usd_krw_pctile_3y"].apply(_fx_regime)

    # ── 급격한 원화 약세 플래그 (6M z>1 & 추가 상승 중) ──────────────
    base["rapid_depreciation_flag"] = (
        (base["usd_krw_zscore_6m"] > 1) & (base["usd_krw_ret_1m"] > 0)
    ).astype(int)

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "usd_krw_close", "usd_krw_ret_1m", "usd_krw_ret_3m",
        "usd_krw_zscore_6m", "usd_krw_pctile_3y",
        "won_strength_score", "fx_regime", "rapid_depreciation_flag",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("usd_krw_close",          "원/달러 환율 종가(월말)",          "원, 일별→월말",                       "monthly"),
    ("usd_krw_ret_1m",         "환율 전월대비 수익률",            "비율, 양수=원화 약세",                 "monthly"),
    ("usd_krw_ret_3m",         "환율 3개월 수익률",               "비율, 양수=원화 약세",                 "monthly"),
    ("usd_krw_zscore_6m",      "환율 6M z-score",                 "z-score",                            "monthly"),
    ("usd_krw_pctile_3y",      "환율 3년 롤링 백분위",            "0~1, 1=3년래 최고환율(원화 최약세)",   "monthly"),
    ("won_strength_score",     "원화 강도 점수",                  "0~1, 높을수록 원화 강세(환율 하락)",   "monthly"),
    ("fx_regime",              "환율 레짐",                       "won_very_strong/won_strong/neutral/won_weak/won_very_weak", "monthly"),
    ("rapid_depreciation_flag","원화 급약세 플래그",              "0/1, 1=환율 6M z>1 & 추가 상승(약세 가속)", "monthly"),
]


def run():
    logger.info("fx_usdkrw 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_fx_usdkrw_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_fx_usdkrw_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_fx_usdkrw_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_fx_usdkrw_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "usd_krw_close", "usd_krw_zscore_6m",
                        "won_strength_score", "fx_regime", "rapid_depreciation_flag"]].to_string())
