"""
외국인 선물 수급 팩터 구축.

원천: money_flow_futures_trend (일별 투자자별 코스피200 선물 순매수, 계약 수)
  - 날짜: "YY.MM.DD" 형식
  - 외국인: 외국인 선물 순매수 (계약 수)

신호 (일별):
  ① foreign_futures_net       : 외국인 선물 순매수 원자료
  ② foreign_futures_cum20d    : 20일 누적 순매수
  ③ foreign_futures_flow_score: 60일 z-score → 0~1 (높을수록 외국인 선물 순매수 모멘텀 강)

신호 (월별 집계):
  ④ futures_flow_monthly_score: 해당 월 마지막 영업일 기준 flow_score

출력:
  - DB: factor_futures_flow_daily (일별), factor_futures_flow_month (월별)
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

ZSCORE_WINDOW = 60
MIN_ZSCORE_OBS = 20
CUM_WINDOW = 20

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _parse_date(series: pd.Series) -> pd.Series:
    """'YY.MM.DD' 형식 → datetime. 2000년대 가정."""
    parsed = pd.to_datetime("20" + series.astype(str).str.strip(), format="%Y%m%d", errors="coerce")
    # "26.07.03" → "2026.07.03" 형식 처리
    fallback = pd.to_datetime(
        series.astype(str).str.strip().str.replace(".", "-", regex=False)
        .apply(lambda s: "20" + s if len(s) == 8 else s),
        format="%Y-%m-%d",
        errors="coerce",
    )
    return parsed.fillna(fallback)


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=MIN_ZSCORE_OBS).mean()
    std = series.rolling(window, min_periods=MIN_ZSCORE_OBS).std()
    return (series - mean) / std.replace(0, np.nan)


def _score_from_zscore(z: pd.Series) -> pd.Series:
    return (z.clip(-3, 3) / 6 + 0.5).clip(0, 1)


def build(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_sql("SELECT * FROM money_flow_futures_trend", conn)

    date_col = "날짜"
    foreign_col = "외국인"

    df["date"] = _parse_date(df[date_col])
    df[foreign_col] = pd.to_numeric(df[foreign_col], errors="coerce")
    df = df.dropna(subset=["date", foreign_col]).sort_values("date").reset_index(drop=True)

    if df.empty:
        logger.warning("선물수급 데이터 없음")
        return pd.DataFrame(), pd.DataFrame()

    df["foreign_futures_net"] = df[foreign_col]
    df["foreign_futures_cum20d"] = df["foreign_futures_net"].rolling(CUM_WINDOW, min_periods=5).sum()
    df["foreign_futures_z60d"] = _zscore(df["foreign_futures_cum20d"], ZSCORE_WINDOW)
    df["foreign_futures_flow_score"] = _score_from_zscore(df["foreign_futures_z60d"])

    daily = df[["date", "foreign_futures_net", "foreign_futures_cum20d",
                "foreign_futures_z60d", "foreign_futures_flow_score"]].copy()
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")

    # 월별 집계: 해당 월 마지막 거래일 기준 flow_score
    df_m = df.copy()
    df_m["period"] = df_m["date"].dt.to_period("M").dt.to_timestamp()
    monthly = (df_m.groupby("period")
               .apply(lambda g: g.sort_values("date").iloc[-1])
               .reset_index(drop=True))
    monthly = monthly[["period", "foreign_futures_net", "foreign_futures_cum20d",
                        "foreign_futures_z60d", "foreign_futures_flow_score"]].rename(
        columns={"foreign_futures_flow_score": "futures_flow_monthly_score"})
    monthly["period"] = monthly["period"].dt.strftime("%Y-%m-01")

    logger.info("일별: %d행 (max=%s)", len(daily), daily["date"].max())
    logger.info("월별: %d행 (max=%s)", len(monthly), monthly["period"].max())
    return daily, monthly


def run() -> None:
    logger.info("futures_flow 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        daily, monthly = build(conn)
        if not daily.empty:
            daily.to_sql("factor_futures_flow_daily", conn, if_exists="replace", index=False)
            logger.info("  → factor_futures_flow_daily 적재: %d행", len(daily))
        if not monthly.empty:
            monthly.to_sql("factor_futures_flow_month", conn, if_exists="replace", index=False)
            logger.info("  → factor_futures_flow_month 적재: %d행", len(monthly))
    logger.info("완료")


if __name__ == "__main__":
    run()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM factor_futures_flow_daily ORDER BY date DESC LIMIT 10", conn)
        print(df.to_string(index=False))
