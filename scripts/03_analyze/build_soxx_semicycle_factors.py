"""
글로벌 반도체 사이클 팩터 구축 (SOXX 기반, 월간 시계열).

신호:
  ① soxx_close          : SOXX(PHLX 반도체지수 ETF) 월말 종가 (USD)
  ② soxx_ret_1m/3m      : 1개월/3개월 수익률
  ③ soxx_ret_zscore_6m  : 1개월 수익률의 6M z-score (모멘텀 가속도)
  ④ soxx_ret_pctile_3y  : 3개월 수익률의 3년 롤링 백분위
  ⑤ soxx_volatility_1m  : 월간 실현변동성 (일별수익률 std, 연환산)

semi_momentum_score = 0~1, 높을수록 반도체 업황 모멘텀 강함 (soxx_ret_zscore_6m 기반)
semi_cycle_regime   = soxx_ret_pctile_3y 기준 5단계 (strong_down~strong_up)
semi_rally_accel_flag = 1개월 수익률 6M z>1 & 추가 상승 동시 충족 시 1 (가속 랠리)

해석: 한국 시가총액 1·2위(삼성전자/SK하이닉스)가 반도체 비중이 높아
       SOXX(미국 반도체 ETF) 모멘텀이 한국 반도체 섹터에 선행/동행하는 경향.
       ㉙(거시 검색 트렌드, theme_semiconductor_score)·⑳(섹터ETF자금흐름, semiconductor)와 보완 사용.

출력 DB 테이블:
  factor_soxx_semicycle_month   : 월간 시계열
  factor_soxx_semicycle_catalog : 팩터 메타데이터
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


def _load_soxx_daily(conn: sqlite3.Connection) -> pd.DataFrame:
    """yfinance 덤프(상단 2행이 Ticker/Date 메타 헤더) → 정제된 일별 시계열"""
    df = pd.read_sql("SELECT [Price] AS date, [Close] AS close FROM macro_macro_indices_soxx", conn)
    df = df.iloc[2:].copy()  # 상단 2행(Ticker/Date 메타) 제거
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna().sort_values("date")


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


def _semi_cycle_regime(pctile: float) -> str:
    if pd.isna(pctile):
        return "unknown"
    if pctile < 0.2:
        return "strong_down"
    if pctile < 0.4:
        return "down"
    if pctile < 0.6:
        return "neutral"
    if pctile < 0.8:
        return "up"
    return "strong_up"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 (일별) ──────────────────────────────────────
    daily = _load_soxx_daily(conn)
    daily["daily_ret"] = daily["close"].pct_change(fill_method=None)
    daily["period"] = daily["date"].dt.to_period("M").dt.to_timestamp()

    # ── 월말 종가 + 월간 실현변동성(일별수익률 std, 연환산) ────────────
    monthly_close = daily.groupby("period")["close"].last()
    monthly_vol = daily.groupby("period")["daily_ret"].std() * np.sqrt(252)

    base = pd.DataFrame({
        "soxx_close": monthly_close,
        "soxx_volatility_1m": monthly_vol,
    }).reset_index().sort_values("period").reset_index(drop=True)

    # ── 모멘텀 (수익률) ──────────────────────────────────────────────
    base["soxx_ret_1m"] = base["soxx_close"].pct_change(1, fill_method=None)
    base["soxx_ret_3m"] = base["soxx_close"].pct_change(3, fill_method=None)

    # ── 1개월 수익률 6M z-score (모멘텀 가속도) ────────────────────────
    base["soxx_ret_zscore_6m"] = _zscore(base["soxx_ret_1m"], ZSCORE_WINDOW)

    # ── 3개월 수익률의 3년 롤링 백분위 ───────────────────────────────
    base["soxx_ret_pctile_3y"] = _rolling_percentile(
        base["soxx_ret_3m"], PCTILE_WINDOW, MIN_PCTILE_OBS
    )

    # ── 반도체 모멘텀 점수 (0~1, 높을수록 업황 강세) ───────────────────
    base["semi_momentum_score"] = _score_from_zscore(base["soxx_ret_zscore_6m"])

    # ── 반도체 사이클 레짐 (3년 백분위 기준 5단계) ─────────────────────
    base["semi_cycle_regime"] = base["soxx_ret_pctile_3y"].apply(_semi_cycle_regime)

    # ── 가속 랠리 플래그 (1개월 수익률 6M z>1 & 추가 상승) ─────────────
    base["semi_rally_accel_flag"] = (
        (base["soxx_ret_zscore_6m"] > 1) & (base["soxx_ret_1m"] > 0)
    ).astype(int)

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "soxx_close", "soxx_ret_1m", "soxx_ret_3m",
        "soxx_ret_zscore_6m", "soxx_ret_pctile_3y", "soxx_volatility_1m",
        "semi_momentum_score", "semi_cycle_regime", "semi_rally_accel_flag",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("soxx_close",            "SOXX(PHLX 반도체지수 ETF) 월말 종가", "USD, 일별→월말",                     "monthly"),
    ("soxx_ret_1m",           "SOXX 전월대비 수익률",              "비율",                               "monthly"),
    ("soxx_ret_3m",           "SOXX 3개월 수익률",                 "비율",                               "monthly"),
    ("soxx_ret_zscore_6m",    "SOXX 1개월 수익률 6M z-score",      "z-score, 모멘텀 가속도",              "monthly"),
    ("soxx_ret_pctile_3y",    "SOXX 3개월 수익률 3년 롤링 백분위",  "0~1, 1=3년래 최고 모멘텀",            "monthly"),
    ("soxx_volatility_1m",    "SOXX 월간 실현변동성(연환산)",       "비율, 일별수익률 std*sqrt(252)",      "monthly"),
    ("semi_momentum_score",   "반도체 모멘텀 점수",                "0~1, 높을수록 업황 모멘텀 강함",       "monthly"),
    ("semi_cycle_regime",     "반도체 사이클 레짐",                "strong_down/down/neutral/up/strong_up", "monthly"),
    ("semi_rally_accel_flag", "반도체 가속 랠리 플래그",            "0/1, 1=1개월수익률 6M z>1 & 추가 상승", "monthly"),
]


def run():
    logger.info("soxx_semicycle 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_soxx_semicycle_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_soxx_semicycle_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_soxx_semicycle_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_soxx_semicycle_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "soxx_close", "soxx_ret_zscore_6m",
                        "semi_momentum_score", "semi_cycle_regime", "semi_rally_accel_flag"]].to_string())
