"""
원자재(구리·원유) 모멘텀 팩터 구축 (월간 시계열).

신호:
  ① copper_close / brent_close / wti_close : 구리(USD/lb)·브렌트유·WTI(USD/bbl) 월말 종가
  ② copper_ret_3m / brent_ret_3m           : 3개월 수익률 (모멘텀)
  ③ copper_ret_zscore_6m / brent_ret_zscore_6m : 6M z-score (가속도)
  ④ copper_pctile_3y / brent_pctile_3y     : 3개월 수익률의 3년 롤링 백분위

commodity_cycle_score = 0~1, 구리·브렌트유 모멘텀 z-score 평균 → 글로벌 경기/원자재 수요 확장 정도
cyclical_demand_regime = 구리·브렌트유 3년 백분위 평균 기준 5단계 (contraction~boom)
commodity_surge_flag  = 구리·브렌트유 동시 6M z>1 (동반 급등 → 인플레/공급충격 경계)

해석: 구리("Dr. Copper")는 글로벌 산업 수요 선행지표(조선·철강·기계),
       브렌트/WTI는 정유·화학 원가·마진과 직결.
       cyclical_demand_regime=expansion/boom → 조선·철강·화학·정유 등 시클리컬 섹터 비중 확대 검토,
       commodity_surge_flag==1 → ㉟(PPI 인플레이션 사이클) 가속 가능성과 함께 원가 부담 업종 마진 점검.

출력 DB 테이블:
  factor_commodity_momentum_month   : 월간 시계열
  factor_commodity_momentum_catalog : 팩터 메타데이터
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


def _cyclical_demand_regime(pctile: float) -> str:
    if pd.isna(pctile):
        return "unknown"
    if pctile < 0.2:
        return "contraction"
    if pctile < 0.4:
        return "slowdown"
    if pctile < 0.6:
        return "neutral"
    if pctile < 0.8:
        return "expansion"
    return "boom"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 (일별 → 월말 리샘플, yfinance) ────────────────
    copper = _load_monthly(conn, "macro_commodities_copper", "Unnamed: 0", "Close", "copper_close")
    wti    = _load_monthly(conn, "macro_commodities_wti",    "Unnamed: 0", "Close", "wti_close")
    brent  = _load_monthly(conn, "macro_commodities_brent",  "Unnamed: 0", "Close", "brent_close")

    base = (copper.merge(wti, on="period", how="outer")
                   .merge(brent, on="period", how="outer")
                   .sort_values("period")
                   .reset_index(drop=True))

    # ── 모멘텀 (3개월 수익률) ────────────────────────────────────────
    base["copper_ret_3m"] = base["copper_close"].pct_change(3, fill_method=None)
    base["brent_ret_3m"] = base["brent_close"].pct_change(3, fill_method=None)

    # ── 6M z-score (가속도) ──────────────────────────────────────────
    base["copper_ret_zscore_6m"] = _zscore(base["copper_ret_3m"], ZSCORE_WINDOW)
    base["brent_ret_zscore_6m"] = _zscore(base["brent_ret_3m"], ZSCORE_WINDOW)

    # ── 3년 롤링 백분위 ────────────────────────────────────────────
    base["copper_pctile_3y"] = _rolling_percentile(
        base["copper_ret_3m"], PCTILE_WINDOW, MIN_PCTILE_OBS
    )
    base["brent_pctile_3y"] = _rolling_percentile(
        base["brent_ret_3m"], PCTILE_WINDOW, MIN_PCTILE_OBS
    )

    # ── 원자재 사이클 종합 점수 (0~1, 구리·브렌트 모멘텀 평균) ────────────
    avg_zscore = base[["copper_ret_zscore_6m", "brent_ret_zscore_6m"]].mean(axis=1)
    base["commodity_cycle_score"] = _score_from_zscore(avg_zscore)

    # ── 시클리컬 수요 레짐 (구리·브렌트 3년 백분위 평균 기준 5단계) ───────
    avg_pctile = base[["copper_pctile_3y", "brent_pctile_3y"]].mean(axis=1)
    base["cyclical_demand_regime"] = avg_pctile.apply(_cyclical_demand_regime)

    # ── 동반 급등 플래그 (구리·브렌트 동시 6M z>1) ─────────────────────
    base["commodity_surge_flag"] = (
        (base["copper_ret_zscore_6m"] > 1) & (base["brent_ret_zscore_6m"] > 1)
    ).astype(int)

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "copper_close", "wti_close", "brent_close",
        "copper_ret_3m", "brent_ret_3m",
        "copper_ret_zscore_6m", "brent_ret_zscore_6m",
        "copper_pctile_3y", "brent_pctile_3y",
        "commodity_cycle_score", "cyclical_demand_regime", "commodity_surge_flag",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("copper_close",            "구리 선물 월말 종가",              "USD/lb, 일별→월말 (yfinance)",        "monthly"),
    ("wti_close",                "WTI 원유 선물 월말 종가",          "USD/bbl, 일별→월말 (yfinance)",       "monthly"),
    ("brent_close",              "브렌트유 선물 월말 종가",          "USD/bbl, 일별→월말 (yfinance)",       "monthly"),
    ("copper_ret_3m",            "구리 3개월 수익률",               "비율",                                "monthly"),
    ("brent_ret_3m",              "브렌트유 3개월 수익률",           "비율",                                "monthly"),
    ("copper_ret_zscore_6m",      "구리 3개월 수익률 6M z-score",    "z-score, 모멘텀 가속도",               "monthly"),
    ("brent_ret_zscore_6m",        "브렌트유 3개월 수익률 6M z-score","z-score, 모멘텀 가속도",               "monthly"),
    ("copper_pctile_3y",          "구리 3개월 수익률 3년 롤링 백분위", "0~1, 1=3년래 최고 모멘텀",             "monthly"),
    ("brent_pctile_3y",            "브렌트유 3개월 수익률 3년 롤링 백분위", "0~1, 1=3년래 최고 모멘텀",          "monthly"),
    ("commodity_cycle_score",      "원자재 사이클 종합 점수",         "0~1, 높을수록 글로벌 수요 확장 모멘텀",  "monthly"),
    ("cyclical_demand_regime",     "시클리컬 수요 레짐",             "contraction/slowdown/neutral/expansion/boom", "monthly"),
    ("commodity_surge_flag",       "원자재 동반 급등 플래그",         "0/1, 1=구리·브렌트 동시 6M z>1(인플레/공급충격 경계)", "monthly"),
]


def run():
    logger.info("commodity_momentum 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_commodity_momentum_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_commodity_momentum_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_commodity_momentum_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_commodity_momentum_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "copper_close", "brent_close",
                        "commodity_cycle_score", "cyclical_demand_regime", "commodity_surge_flag"]].to_string())
