"""
섹터 ETF 자금흐름/상대강도 팩터 구축.

소스: data/raw/sector_etf/{sector}_{ticker}.csv (18개 섹터 대표 ETF, 2019-01 ~ 현재 일별)
  컬럼: date, NAV, 시가, 고가, 저가, 종가, 거래량, 거래대금, 기초지수

⑧(레짐 조정 섹터 관심도)이 NAVER 검색 관심도(투자자 관심) 기반인 것과 달리,
이 팩터는 ETF 가격·거래대금 기반 "실제 자금 흐름"을 측정 — 보완 관계.

출력 컬럼 (월간):
  close                : 월말 종가
  ret_1m / ret_3m       : 1개월/3개월 수익률
  turnover_value_avg    : 월평균 거래대금
  turnover_zscore_own_12m : 자기 과거 12개월 거래대금 z-score (자금 유입 강도)
  ret_1m_rank_cross     : 해당 월 18개 섹터 중 1개월 수익률 백분위 (상대강도)
  turnover_zscore_pct_cross : 해당 월 거래대금 z-score 백분위
  money_flow_score      : 0~1, ret_1m_rank_cross(50%) + turnover_zscore_pct_cross(50%)
  money_flow_bucket     : very_high > high > neutral > low > very_low

출력 DB 테이블:
  factor_sector_etf_flow_month
  factor_sector_etf_flow_catalog
"""
import logging
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_ETF_DIR = PROJECT_ROOT / "data" / "raw" / "sector_etf"

ZSCORE_WINDOW = 12
MIN_ROWS = 13  # 12개월 z-score + 최소 1개월

FILENAME_RE = re.compile(r"^(.+)_(\d{6})$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_etf_files() -> list[tuple[str, str, Path]]:
    """(group_name, ticker, path) 목록 반환."""
    out = []
    for path in sorted(SECTOR_ETF_DIR.glob("*.csv")):
        m = FILENAME_RE.match(path.stem)
        if not m:
            continue
        out.append((m.group(1), m.group(2), path))
    return out


def _compute_etf(group_name: str, ticker: str, path: Path) -> pd.DataFrame | None:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("종가", "거래대금"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "종가", "거래대금"]).sort_values("date").set_index("date")

    if len(df) < MIN_ROWS:
        return None

    monthly_close = df["종가"].resample("ME").last()
    monthly_turnover = df["거래대금"].resample("ME").mean()

    out = pd.DataFrame({
        "close": monthly_close,
        "turnover_value_avg": monthly_turnover,
    })
    out["ret_1m"] = out["close"].pct_change(1)
    out["ret_3m"] = out["close"].pct_change(3)

    roll_mean = out["turnover_value_avg"].rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).mean()
    roll_std = out["turnover_value_avg"].rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).std()
    out["turnover_zscore_own_12m"] = np.where(
        roll_std > 0, (out["turnover_value_avg"] - roll_mean) / roll_std, np.nan
    )

    out = out.reset_index().rename(columns={"date": "period"})
    out["period"] = out["period"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-01")
    out["group_name"] = group_name
    out["ticker"] = ticker
    return out


def _bucket_flow(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= 0.8:
        return "very_high"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "neutral"
    if score >= 0.2:
        return "low"
    return "very_low"


def build() -> pd.DataFrame:
    files = _load_etf_files()
    logger.info("%d개 섹터 ETF 처리 시작", len(files))

    frames = []
    for group_name, ticker, path in files:
        out = _compute_etf(group_name, ticker, path)
        if out is not None:
            frames.append(out)

    if not frames:
        logger.error("데이터 없음")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    df["ret_1m_rank_cross"] = df.groupby("period")["ret_1m"].rank(pct=True)
    df["turnover_zscore_pct_cross"] = df.groupby("period")["turnover_zscore_own_12m"].rank(pct=True)

    df["money_flow_score"] = df[["ret_1m_rank_cross", "turnover_zscore_pct_cross"]].mean(
        axis=1, skipna=True
    )
    df["money_flow_bucket"] = df["money_flow_score"].apply(_bucket_flow)

    logger.info("구축 완료: %d행 (%d섹터)", len(df), df["group_name"].nunique())
    return df[[
        "group_name", "ticker", "period", "close", "ret_1m", "ret_3m",
        "turnover_value_avg", "turnover_zscore_own_12m",
        "ret_1m_rank_cross", "turnover_zscore_pct_cross",
        "money_flow_score", "money_flow_bucket",
    ]]


CATALOG = [
    ("ret_1m",                  "섹터 ETF 1개월 수익률",       "월말 종가 기준 수익률",                              "month"),
    ("ret_3m",                  "섹터 ETF 3개월 수익률",       "월말 종가 기준 수익률",                              "month"),
    ("turnover_zscore_own_12m", "거래대금 자기 12개월 z-score","높을수록 평소 대비 자금 유입 활발",                   "month"),
    ("ret_1m_rank_cross",       "섹터간 1개월 수익률 백분위",   "0~1, 해당 월 18개 섹터 중 상대강도",                  "month"),
    ("turnover_zscore_pct_cross","섹터간 거래대금 z-score 백분위","0~1, 해당 월 자금유입 상대강도",                    "month"),
    ("money_flow_score",        "자금흐름 복합 점수",          "0~1, 상대강도(50%) + 거래대금유입(50%)",              "month"),
    ("money_flow_bucket",       "자금흐름 버킷",               "very_high > high > neutral > low > very_low",        "month"),
]


def run():
    logger.info("sector_etf_flow 팩터 구축 시작")
    df = build()

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("factor_sector_etf_flow_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_sector_etf_flow_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_sector_etf_flow_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_sector_etf_flow_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    latest = df["period"].max()
    print(f"\n=== 최신 월({latest}) 자금흐름 순위 ===")
    print(df[df["period"] == latest].sort_values("money_flow_score", ascending=False)[
        ["group_name", "ret_1m", "turnover_zscore_own_12m", "money_flow_score", "money_flow_bucket"]
    ].to_string(index=False))
