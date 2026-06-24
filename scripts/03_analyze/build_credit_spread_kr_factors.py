"""
한국 신용스프레드 팩터 구축 (월간 시계열).

신호:
  ① AA- 신용스프레드   : kor_corp_aa  - kor_gov3y   (투자등급 프리미엄)
  ② BBB- 신용스프레드  : kor_corp_bbb - kor_gov3y   (저등급 프리미엄)
  ③ 등급간 스프레드    : kor_corp_bbb - kor_corp_aa (BBB-AA, "정크 프리미엄" 프록시)

각 스프레드의 6M z-score + 36M(3년) 롤링 백분위 산출.
credit_score = 0~1, 높을수록 위험선호(스프레드 축소, risk-on)
credit_regime = bbb_aa_spread_pctile_3y 기준 5단계 (very_tight~very_wide)

해석: 등급간 스프레드(③) 급확대 = 신용 경계감 고조(risk-off 선행 신호).
       ⑭(macro_spread)의 미국 HY 스프레드와 상호 보완 — 국내 신용 사이클 전용.

출력 DB 테이블:
  factor_credit_spread_kr_month   : 월간 시계열
  factor_credit_spread_kr_catalog : 팩터 메타데이터
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


def _credit_regime(pctile: float) -> str:
    if pd.isna(pctile):
        return "unknown"
    if pctile < 0.2:
        return "very_tight"
    if pctile < 0.4:
        return "tight"
    if pctile < 0.6:
        return "neutral"
    if pctile < 0.8:
        return "wide"
    return "very_wide"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 (일별 → 월말 리샘플) ──────────────────────
    aa  = _load_monthly(conn, "macro_macro_indices_kor_corp_aa",  "date", "value", "kor_corp_aa")
    bbb = _load_monthly(conn, "macro_macro_indices_kor_corp_bbb", "date", "value", "kor_corp_bbb")
    gov = _load_monthly(conn, "macro_macro_indices_kor_gov3y",    "date", "value", "kor_gov3y")

    # ── 병합 ─────────────────────────────────────────────────────
    base = (aa.merge(bbb, on="period", how="outer")
              .merge(gov, on="period", how="outer")
              .sort_values("period")
              .reset_index(drop=True))

    # ── 스프레드 계산 (%p) ───────────────────────────────────────
    base["aa_spread"] = base["kor_corp_aa"] - base["kor_gov3y"]
    base["bbb_spread"] = base["kor_corp_bbb"] - base["kor_gov3y"]
    base["bbb_aa_spread"] = base["kor_corp_bbb"] - base["kor_corp_aa"]

    # ── 6M z-score ────────────────────────────────────────────────
    base["aa_spread_z6m"] = _zscore(base["aa_spread"], ZSCORE_WINDOW)
    base["bbb_aa_spread_z6m"] = _zscore(base["bbb_aa_spread"], ZSCORE_WINDOW)

    # ── 1M 변화 ───────────────────────────────────────────────────
    base["aa_spread_mom1m"] = base["aa_spread"].diff(1)
    base["bbb_aa_spread_mom1m"] = base["bbb_aa_spread"].diff(1)

    # ── 3년 롤링 백분위 (절대 레벨 참고) ────────────────────────────
    base["bbb_aa_spread_pctile_3y"] = _rolling_percentile(
        base["bbb_aa_spread"], PCTILE_WINDOW, MIN_PCTILE_OBS
    )

    # ── 신용 환경 점수 (0~1, 높을수록 risk-on=스프레드 축소) ────────
    base["credit_score"] = _score_from_zscore(-base["bbb_aa_spread_z6m"])

    # ── 신용 레짐 (3년 백분위 기준 5단계) ───────────────────────────
    base["credit_regime"] = base["bbb_aa_spread_pctile_3y"].apply(_credit_regime)

    # ── 급확대 플래그 (등급간 스프레드 6M z>1 & 전월대비 확대) ──────
    base["spread_widening_flag"] = (
        (base["bbb_aa_spread_z6m"] > 1) & (base["bbb_aa_spread_mom1m"] > 0)
    ).astype(int)

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "kor_corp_aa", "kor_corp_bbb", "kor_gov3y",
        "aa_spread", "bbb_spread", "bbb_aa_spread",
        "aa_spread_z6m", "bbb_aa_spread_z6m",
        "aa_spread_mom1m", "bbb_aa_spread_mom1m",
        "bbb_aa_spread_pctile_3y",
        "credit_score", "credit_regime", "spread_widening_flag",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("kor_corp_aa",            "한국 회사채 AA- 3년 금리",        "%, 일별→월말",                       "monthly"),
    ("kor_corp_bbb",           "한국 회사채 BBB- 3년 금리",       "%, 일별→월말",                       "monthly"),
    ("kor_gov3y",              "한국 국고채 3년 금리",            "%, 일별→월말",                       "monthly"),
    ("aa_spread",              "AA- 신용스프레드(AA-국고3y)",     "%p, 투자등급 프리미엄",               "monthly"),
    ("bbb_spread",             "BBB- 신용스프레드(BBB-국고3y)",   "%p, 저등급 프리미엄",                 "monthly"),
    ("bbb_aa_spread",          "등급간 스프레드(BBB-AA)",         "%p, 높을수록 신용 경계감 고조",        "monthly"),
    ("aa_spread_z6m",          "AA- 스프레드 6M z-score",         "z-score",                            "monthly"),
    ("bbb_aa_spread_z6m",      "등급간 스프레드 6M z-score",      "z-score",                            "monthly"),
    ("aa_spread_mom1m",        "AA- 스프레드 전월대비 변화",      "%p",                                 "monthly"),
    ("bbb_aa_spread_mom1m",    "등급간 스프레드 전월대비 변화",   "%p",                                 "monthly"),
    ("bbb_aa_spread_pctile_3y","등급간 스프레드 3년 롤링 백분위", "0~1, 1=3년래 최대 스프레드(최악)",     "monthly"),
    ("credit_score",           "신용 환경 점수",                  "0~1, 높을수록 위험선호(스프레드 축소)", "monthly"),
    ("credit_regime",          "신용 레짐",                       "very_tight/tight/neutral/wide/very_wide", "monthly"),
    ("spread_widening_flag",   "스프레드 급확대 플래그",          "0/1, 1=등급간 스프레드 가속 확대(경계 신호)", "monthly"),
]


def run():
    logger.info("credit_spread_kr 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_credit_spread_kr_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_credit_spread_kr_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_credit_spread_kr_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_credit_spread_kr_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "bbb_aa_spread", "bbb_aa_spread_z6m",
                        "credit_score", "credit_regime", "spread_widening_flag"]].to_string())
