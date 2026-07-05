"""
중국 거시경제 팩터 구축 (월간).

원천 (collect_china_macro.py 수집 후):
  - macro_china_exports : FRED XTEXVA01CNM667S (중국 수출, USD mn)
  - macro_csi300_daily  : yfinance 000300.SS (CSI300 일별 종가)

신호:
  ① china_export_yoy       : 중국 수출 전년동월비
  ② china_export_yoy_z12m  : ① 12개월 z-score
  ③ china_export_score     : ② → 0~1 (높을수록 수출 호조)
  ④ csi300_monthly_ret     : CSI300 월간 수익률
  ⑤ csi300_ret_z6m         : ④ 6개월 z-score
  ⑥ csi300_momentum_score  : ⑤ → 0~1 (높을수록 CSI 모멘텀 강)
  ⑦ china_growth_score     : ③과 ⑥ 평균 (가용 데이터만)

출력 DB: factor_china_macro_month
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

EXPORT_ZSCORE_WINDOW = 12
CSI_ZSCORE_WINDOW = 6
MIN_OBS = 4

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=MIN_OBS).mean()
    std = series.rolling(window, min_periods=MIN_OBS).std()
    return (series - mean) / std.replace(0, np.nan)


def _score_from_zscore(z: pd.Series) -> pd.Series:
    return (z.clip(-3, 3) / 6 + 0.5).clip(0, 1)


def _load_exports(conn: sqlite3.Connection) -> pd.Series:
    try:
        df = pd.read_sql("SELECT date, value FROM macro_china_exports", conn)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().sort_values("date")
        monthly = df.set_index("date")["value"].resample("ME").last().dropna()
        monthly.index = monthly.index.to_period("M").to_timestamp()
        return monthly
    except Exception as e:
        logger.warning("중국 수출 데이터 로드 실패: %s", e)
        return pd.Series(dtype="float64")


def _load_csi300(conn: sqlite3.Connection) -> pd.Series:
    try:
        df = pd.read_sql("SELECT date, close FROM macro_csi300_daily", conn)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna().sort_values("date")
        monthly = df.set_index("date")["close"].resample("ME").last().dropna()
        monthly.index = monthly.index.to_period("M").to_timestamp()
        return monthly
    except Exception as e:
        logger.warning("CSI300 데이터 로드 실패: %s", e)
        return pd.Series(dtype="float64")


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    exports = _load_exports(conn)
    csi300 = _load_csi300(conn)

    # 공통 월간 인덱스 (두 시리즈의 합집합)
    all_periods = exports.index.union(csi300.index)
    base = pd.DataFrame(index=all_periods)
    base.index.name = "period"

    # ── 중국 수출 팩터 ──────────────────────────────────────────────
    if not exports.empty:
        base["china_exports"] = exports
        base["china_export_yoy"] = base["china_exports"].pct_change(12, fill_method=None)
        base["china_export_yoy_z12m"] = _zscore(base["china_export_yoy"], EXPORT_ZSCORE_WINDOW)
        base["china_export_score"] = _score_from_zscore(base["china_export_yoy_z12m"])
        logger.info("중국 수출 팩터: %d행, max=%s", base["china_export_score"].notna().sum(),
                    exports.index.max().strftime("%Y-%m-%d"))

    # ── CSI300 팩터 ────────────────────────────────────────────────
    if not csi300.empty:
        base["csi300_close"] = csi300
        base["csi300_monthly_ret"] = base["csi300_close"].pct_change(1, fill_method=None)
        base["csi300_ret_z6m"] = _zscore(base["csi300_monthly_ret"], CSI_ZSCORE_WINDOW)
        base["csi300_momentum_score"] = _score_from_zscore(base["csi300_ret_z6m"])
        logger.info("CSI300 팩터: %d행, max=%s", base["csi300_momentum_score"].notna().sum(),
                    csi300.index.max().strftime("%Y-%m-%d"))

    # ── 종합 중국 성장 점수 ─────────────────────────────────────────
    score_cols = [c for c in ["china_export_score", "csi300_momentum_score"] if c in base.columns]
    if score_cols:
        base["china_growth_score"] = base[score_cols].mean(axis=1, skipna=True)

    base = base.reset_index()
    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = ["period"]
    for c in ["china_exports", "china_export_yoy", "china_export_yoy_z12m", "china_export_score",
              "csi300_close", "csi300_monthly_ret", "csi300_ret_z6m", "csi300_momentum_score",
              "china_growth_score"]:
        if c in base.columns:
            cols.append(c)
    return base[cols].dropna(subset=["period"])


def run() -> pd.DataFrame:
    logger.info("china_macro 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        if df.empty:
            logger.error("china_macro 팩터 결과 없음 — collect_china_macro.py를 먼저 실행하세요")
            return df
        df.to_sql("factor_china_macro_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_china_macro_month 적재: %d행", len(df))
    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    if not df.empty:
        score_cols = [c for c in ["period", "china_export_yoy", "china_export_score",
                                   "csi300_monthly_ret", "csi300_momentum_score",
                                   "china_growth_score"] if c in df.columns]
        print(df.tail(12)[score_cols].to_string(index=False))
