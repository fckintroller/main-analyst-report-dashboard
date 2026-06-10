"""
매크로 스프레드 팩터 구축 (월간 시계열).

신호:
  ① 한국 장단기 금리 스프레드  : kor_gov10y - kor_gov1y
  ② 미국 장단기 금리 스프레드  : DGS10 - DGS2
  ③ HY 크레딧 스프레드         : BAMLH0A0HYM2
  ④ HY-IG 추가 스프레드        : BAMLH0A0HYM2 - BAMLC0A0CM
  ⑤ VIX                        : yahoo_vix close

각 신호별 6M z-score + 방향성 기반 0~1 점수 산출.
macro_risk_score = kor_spread_score×0.25 + us_spread_score×0.15
                 + credit_score×0.35 + vix_score×0.25

해석: 높을수록 리스크-온(위험자산 선호), 낮을수록 리스크-오프.

출력 DB 테이블:
  factor_macro_spread_month   : 월간 시계열
  factor_macro_spread_catalog : 팩터 메타데이터
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

ZSCORE_WINDOW = 6    # 월 단위 rolling window
MIN_ZSCORE_OBS = 3

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
    std  = series.rolling(window, min_periods=MIN_ZSCORE_OBS).std()
    return (series - mean) / std.replace(0, np.nan)


def _score_from_zscore(z: pd.Series) -> pd.Series:
    """z-score → 0~1 점수. clip(-3,3)/6 + 0.5"""
    return (z.clip(-3, 3) / 6 + 0.5).clip(0, 1)


def _vix_regime(v: float) -> str:
    if pd.isna(v):
        return "unknown"
    if v < 15:
        return "calm"
    if v < 20:
        return "moderate"
    if v < 25:
        return "elevated"
    if v < 30:
        return "high"
    return "extreme"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 ──────────────────────────────────────────
    kor10 = _load_monthly(conn, "macro_macro_indices_kor_gov10y",  "date",  "value", "kor_gov10y")
    kor1  = _load_monthly(conn, "macro_macro_indices_kor_gov1y",   "date",  "value", "kor_gov1y")
    dgs10 = _load_monthly(conn, "macro_macro_indices_dgs10",       "DATE",  "DGS10", "us_gov10y")
    dgs2  = _load_monthly(conn, "macro_macro_indices_dgs2",        "DATE",  "DGS2",  "us_gov2y")
    hy    = _load_monthly(conn, "macro_macro_indices_bamlh0a0hym2","DATE",  "BAMLH0A0HYM2", "hy_spread")
    ig    = _load_monthly(conn, "macro_macro_indices_bamlc0a0cm",  "DATE",  "BAMLC0A0CM",   "ig_spread")
    vix   = _load_monthly(conn,
                          "macro_quant_macro_indicators_yahoo_vix", "date", "close", "vix")

    # ── 병합 ─────────────────────────────────────────────────────
    base = (kor10.merge(kor1,  on="period", how="outer")
                 .merge(dgs10, on="period", how="outer")
                 .merge(dgs2,  on="period", how="outer")
                 .merge(hy,    on="period", how="outer")
                 .merge(ig,    on="period", how="outer")
                 .merge(vix,   on="period", how="outer")
                 .sort_values("period"))

    # ── 스프레드 계산 ─────────────────────────────────────────────
    base["kor_spread_10y1y"]  = base["kor_gov10y"] - base["kor_gov1y"]
    base["us_spread_10y2y"]   = base["us_gov10y"]  - base["us_gov2y"]
    base["credit_spread_hy"]  = base["hy_spread"]
    base["credit_spread_hy_ig"] = base["hy_spread"] - base["ig_spread"]

    # ── 6M z-score ────────────────────────────────────────────────
    for col, zname in [
        ("kor_spread_10y1y",    "kor_spread_z6m"),
        ("us_spread_10y2y",     "us_spread_z6m"),
        ("credit_spread_hy",    "hy_spread_z6m"),
        ("vix",                 "vix_z6m"),
    ]:
        base[zname] = _zscore(base[col], ZSCORE_WINDOW)

    # ── 1M 변화 ───────────────────────────────────────────────────
    base["kor_spread_mom1m"] = base["kor_spread_10y1y"].diff(1)
    base["hy_spread_mom1m"]  = base["credit_spread_hy"].diff(1)
    base["vix_mom1m"]        = base["vix"].diff(1)

    # ── 점수 (0~1, 높을수록 리스크-온) ──────────────────────────
    # 장단기 스프레드: 높을수록 좋음(정상 곡선, 경기 확장)
    base["kor_spread_score"] = _score_from_zscore(base["kor_spread_z6m"])
    base["us_spread_score"]  = _score_from_zscore(base["us_spread_z6m"])

    # HY 스프레드: 낮을수록 좋음(위험선호) → 부호 반전 z-score
    base["credit_score"] = _score_from_zscore(-base["hy_spread_z6m"])

    # VIX: 낮을수록 좋음 → 부호 반전
    base["vix_score"] = _score_from_zscore(-base["vix_z6m"])

    # 복합 매크로 리스크 점수
    def _macro_score(row: pd.Series) -> float:
        parts, weights = [], []
        if pd.notna(row["kor_spread_score"]):
            parts.append(row["kor_spread_score"]); weights.append(0.25)
        if pd.notna(row["us_spread_score"]):
            parts.append(row["us_spread_score"]); weights.append(0.15)
        if pd.notna(row["credit_score"]):
            parts.append(row["credit_score"]);    weights.append(0.35)
        if pd.notna(row["vix_score"]):
            parts.append(row["vix_score"]);       weights.append(0.25)
        if not parts:
            return np.nan
        return sum(p * w for p, w in zip(parts, weights)) / sum(weights)

    base["macro_risk_score"] = base.apply(_macro_score, axis=1)

    base["vix_regime"] = base["vix"].apply(_vix_regime)

    # ── 역전 플래그 ───────────────────────────────────────────────
    base["kor_yield_inverted"] = (base["kor_spread_10y1y"] < 0).astype(int)
    base["us_yield_inverted"]  = (base["us_spread_10y2y"]  < 0).astype(int)

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "kor_gov10y", "kor_gov1y", "kor_spread_10y1y",
        "kor_spread_z6m", "kor_spread_mom1m", "kor_spread_score", "kor_yield_inverted",
        "us_gov10y", "us_gov2y", "us_spread_10y2y",
        "us_spread_z6m", "us_spread_score", "us_yield_inverted",
        "hy_spread", "ig_spread", "credit_spread_hy_ig",
        "hy_spread_z6m", "hy_spread_mom1m", "credit_score",
        "vix", "vix_z6m", "vix_mom1m", "vix_score", "vix_regime",
        "macro_risk_score",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("kor_spread_10y1y",    "한국 장단기 스프레드(10Y-1Y)",    "bp 단위, 양수=정상, 음수=역전", "monthly"),
    ("kor_spread_score",    "한국 장단기 점수",                "0~1, 높을수록 경기확장 시나리오", "monthly"),
    ("kor_yield_inverted",  "한국 수익률 곡선 역전 플래그",    "0=정상, 1=역전",                  "monthly"),
    ("us_spread_10y2y",     "미국 장단기 스프레드(10Y-2Y)",    "bp 단위",                         "monthly"),
    ("us_spread_score",     "미국 장단기 점수",                "0~1",                             "monthly"),
    ("us_yield_inverted",   "미국 수익률 곡선 역전 플래그",    "0=정상, 1=역전",                  "monthly"),
    ("hy_spread",           "HY 크레딧 스프레드(BAML)",        "%, 높을수록 위험회피",             "monthly"),
    ("credit_score",        "크레딧 환경 점수",                "0~1, 높을수록 위험선호(스프레드 축소)", "monthly"),
    ("vix",                 "VIX 공포지수",                    "포인트",                           "monthly"),
    ("vix_score",           "VIX 점수",                        "0~1, 높을수록 시장 안정",          "monthly"),
    ("vix_regime",          "VIX 레짐",                        "calm/moderate/elevated/high/extreme", "monthly"),
    ("macro_risk_score",    "매크로 복합 리스크-온 점수",      "0~1, 높을수록 위험자산 선호 환경", "monthly"),
]


def run():
    logger.info("macro_spread 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_macro_spread_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_macro_spread_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_macro_spread_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_macro_spread_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "kor_spread_10y1y", "hy_spread", "vix",
                        "macro_risk_score", "vix_regime"]].to_string())
