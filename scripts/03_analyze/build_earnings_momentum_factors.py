"""
실적 모멘텀 (어닝 가속도) 팩터 구축.

소스: data/raw/valuation/earnings_consensus.csv (Naver Finance 컨센서스, 종목별 1행 JSON)
  - "최근 분기 실적" 키에서 분기별 매출액/영업이익/당기순이익/영업이익률/순이익률 추출
  - (E) 접미사가 붙은 분기는 추정치이므로 실적 모멘텀 계산에서 제외 (최신 실제 분기만 사용)

핵심 아이디어:
  - 최신 실제 분기(Q0) vs 1년전 동일분기(Q0-4) → YoY 성장
  - 최신 실제 분기(Q0) vs 직전 분기(Q-1) → QoQ 성장
  - 직전 분기의 YoY 성장(Q-1 vs Q-5)과 비교하여 "성장률이 가속 중인가" 판정 (earnings_accel_flag)
  - 적자→흑자 전환(흑자전환)은 turnaround_flag로 별도 표시 (growth % 무의미하므로 NaN 처리,
    랭킹용으로는 클리핑 상한값(3.0)을 부여)

출력 컬럼:
  latest_quarter        : 최신 실제 분기 (예: '2026.03')
  revenue / op_profit / net_profit / op_margin / net_margin : 최신 실제 분기 값
  revenue_yoy / op_profit_yoy / net_profit_yoy : YoY 성장률 (-3.0~3.0 클리핑, 흑자전환=NaN)
  op_profit_qoq / net_profit_qoq               : QoQ 성장률
  op_margin_chg_yoy     : 영업이익률 YoY 변화 (pp)
  op_turnaround_flag    : 영업이익 적자→흑자 전환 여부 (0/1)
  net_turnaround_flag   : 순이익 적자→흑자 전환 여부 (0/1)
  earnings_accel_flag   : 영업이익 YoY 성장률이 직전 분기 대비 가속 중인지 (0/1, 데이터 부족시 NaN)
  op_profit_yoy_sector_pct : 섹터 내 영업이익 YoY 성장 백분위 (흑자전환은 최상위로 처리)
  earnings_momentum_score  : 0~1, 성장 백분위(70%) + 가속 여부(30%)
  earnings_growth_bucket   : strong_growth > growth > flat > decline > no_data

출력 DB 테이블:
  factor_earnings_momentum_snapshot
  factor_earnings_momentum_catalog
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
CSV_PATH = PROJECT_ROOT / "data" / "raw" / "valuation" / "earnings_consensus.csv"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

MIN_SECTOR_N = 3
GROWTH_CLIP = 3.0  # ±300%

QUARTER_KEY_RE = re.compile(r"^\('최근 분기 실적', '(\d{4})\.(\d{2})(\(E\))?',")

FIELD_IDX = {
    "revenue": "0",
    "op_profit": "1",
    "net_profit": "2",
    "op_margin": "3",
    "net_margin": "4",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_sector_map() -> dict[str, str]:
    if SECTOR_MAP_PATH.exists():
        try:
            sm = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
            tk_col = sm.columns[0]
            sec_col = sm.columns[1] if sm.shape[1] >= 2 else sm.columns[0]
            return dict(zip(sm[tk_col].astype(str).str.zfill(6), sm[sec_col].astype(str)))
        except Exception:
            pass
    return {}


def _parse_quarters(raw_dict: dict) -> dict[tuple[int, int], dict]:
    """'최근 분기 실적' 중 (E) 아닌 실제 분기만 {(year, month): field_dict}로 반환."""
    quarters = {}
    for key, val in raw_dict.items():
        m = QUARTER_KEY_RE.match(key)
        if not m or m.group(3):  # (E) 추정치 제외
            continue
        year, month = int(m.group(1)), int(m.group(2))
        quarters[(year, month)] = val
    return quarters


def _field(qdict: dict | None, name: str) -> float | None:
    if qdict is None:
        return None
    v = qdict.get(FIELD_IDX[name])
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _growth(curr: float | None, prev: float | None) -> tuple[float, float]:
    """(growth_ratio, turnaround_flag) 반환. growth_ratio는 ±GROWTH_CLIP 클리핑."""
    if curr is None or prev is None:
        return np.nan, np.nan
    if prev > 0:
        g = curr / prev - 1.0
        return float(np.clip(g, -GROWTH_CLIP, GROWTH_CLIP)), 0.0
    if prev <= 0 and curr > 0:
        return np.nan, 1.0  # 흑자전환
    return np.nan, 0.0


def _compute_ticker(ticker: str, raw_json: str) -> dict | None:
    try:
        raw = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None

    quarters = _parse_quarters(raw)
    if len(quarters) < 2:
        return None

    keys_sorted = sorted(quarters.keys())
    q0_key = keys_sorted[-1]
    q0 = quarters[q0_key]

    qm1_key = keys_sorted[-2] if len(keys_sorted) >= 2 else None
    qm1 = quarters.get(qm1_key) if qm1_key else None

    yoy0_key = (q0_key[0] - 1, q0_key[1])
    yoy0 = quarters.get(yoy0_key)

    yoy_m1 = None
    if qm1_key:
        yoy_m1_key = (qm1_key[0] - 1, qm1_key[1])
        yoy_m1 = quarters.get(yoy_m1_key)

    revenue = _field(q0, "revenue")
    op_profit = _field(q0, "op_profit")
    net_profit = _field(q0, "net_profit")
    op_margin = _field(q0, "op_margin")
    net_margin = _field(q0, "net_margin")

    revenue_yoy, _ = _growth(revenue, _field(yoy0, "revenue"))
    op_profit_yoy, op_turnaround_flag = _growth(op_profit, _field(yoy0, "op_profit"))
    net_profit_yoy, net_turnaround_flag = _growth(net_profit, _field(yoy0, "net_profit"))

    op_profit_qoq, _ = _growth(op_profit, _field(qm1, "op_profit"))
    net_profit_qoq, _ = _growth(net_profit, _field(qm1, "net_profit"))

    op_margin_yoy0 = _field(yoy0, "op_margin")
    op_margin_chg_yoy = (
        op_margin - op_margin_yoy0 if op_margin is not None and op_margin_yoy0 is not None else np.nan
    )

    # 직전 분기의 YoY 성장 (가속 판정용)
    op_profit_yoy_prev, op_turnaround_prev = _growth(_field(qm1, "op_profit"), _field(yoy_m1, "op_profit"))

    earnings_accel_flag = np.nan
    if not pd.isna(op_profit_yoy) and not pd.isna(op_profit_yoy_prev):
        earnings_accel_flag = 1.0 if op_profit_yoy > op_profit_yoy_prev else 0.0
    elif op_turnaround_flag == 1.0 and op_turnaround_prev != 1.0:
        earnings_accel_flag = 1.0

    # 랭킹용 값: 흑자전환은 클리핑 상한으로 취급 (사실상 무한 성장)
    if op_turnaround_flag == 1.0:
        rank_value = GROWTH_CLIP
    else:
        rank_value = op_profit_yoy

    return {
        "ticker": ticker,
        "latest_quarter": f"{q0_key[0]}.{q0_key[1]:02d}",
        "revenue": revenue,
        "op_profit": op_profit,
        "net_profit": net_profit,
        "op_margin": op_margin,
        "net_margin": net_margin,
        "revenue_yoy": revenue_yoy,
        "op_profit_yoy": op_profit_yoy,
        "net_profit_yoy": net_profit_yoy,
        "op_profit_qoq": op_profit_qoq,
        "net_profit_qoq": net_profit_qoq,
        "op_margin_chg_yoy": op_margin_chg_yoy,
        "op_turnaround_flag": op_turnaround_flag,
        "net_turnaround_flag": net_turnaround_flag,
        "earnings_accel_flag": earnings_accel_flag,
        "_rank_value": rank_value,
    }


def _bucket(rank_value: float) -> str:
    if pd.isna(rank_value):
        return "no_data"
    if rank_value >= 0.30:
        return "strong_growth"
    if rank_value >= 0.0:
        return "growth"
    if rank_value >= -0.10:
        return "flat"
    return "decline"


def build(snapshot_date: str) -> pd.DataFrame:
    raw_df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", dtype={"ticker": str})
    raw_df["ticker"] = raw_df["ticker"].str.zfill(6)
    sector_map = _load_sector_map()
    logger.info("%d개 종목 컨센서스 로드", len(raw_df))

    records = []
    for _, row in raw_df.iterrows():
        rec = _compute_ticker(row["ticker"], row["consensus_raw"])
        if rec:
            records.append(rec)

    df = pd.DataFrame(records)
    if df.empty:
        logger.error("데이터 없음")
        return df

    df["snapshot_date"] = snapshot_date
    df["sector"] = df["ticker"].map(sector_map).fillna("unknown")

    def _pct_rank(group: pd.Series) -> pd.Series:
        valid = group.dropna()
        if len(valid) < MIN_SECTOR_N:
            return pd.Series(np.nan, index=group.index)
        return group.rank(pct=True, na_option="keep")

    df["op_profit_yoy_sector_pct"] = df.groupby("sector")["_rank_value"].transform(_pct_rank)

    def _composite(row: pd.Series) -> float:
        parts, weights = [], []
        if pd.notna(row["op_profit_yoy_sector_pct"]):
            parts.append(row["op_profit_yoy_sector_pct"]); weights.append(0.7)
        if pd.notna(row["earnings_accel_flag"]):
            parts.append(row["earnings_accel_flag"]); weights.append(0.3)
        if not parts:
            return np.nan
        tw = sum(weights)
        return sum(p * w for p, w in zip(parts, weights)) / tw

    df["earnings_momentum_score"] = df.apply(_composite, axis=1)
    df["earnings_growth_bucket"] = df["_rank_value"].apply(_bucket)

    logger.info("구축 완료: %d행", len(df))
    return df[[
        "ticker", "snapshot_date", "sector", "latest_quarter",
        "revenue", "op_profit", "net_profit", "op_margin", "net_margin",
        "revenue_yoy", "op_profit_yoy", "net_profit_yoy",
        "op_profit_qoq", "net_profit_qoq", "op_margin_chg_yoy",
        "op_turnaround_flag", "net_turnaround_flag", "earnings_accel_flag",
        "op_profit_yoy_sector_pct", "earnings_momentum_score", "earnings_growth_bucket",
    ]]


CATALOG = [
    ("op_profit_yoy",          "영업이익 YoY 성장률",     "최신 실제분기 vs 1년전 동일분기, ±300% 클리핑, 흑자전환=NaN", "snapshot"),
    ("op_profit_qoq",          "영업이익 QoQ 성장률",     "최신 실제분기 vs 직전분기, ±300% 클리핑",                 "snapshot"),
    ("op_margin_chg_yoy",      "영업이익률 YoY 변화",     "pp 단위, 양수=마진 개선",                                 "snapshot"),
    ("op_turnaround_flag",     "영업이익 흑자전환 여부",   "0/1, 전년동기 적자→당기 흑자",                            "snapshot"),
    ("earnings_accel_flag",    "실적 가속 여부",         "0/1, 영업이익 YoY 성장률이 직전분기 대비 가속",            "snapshot"),
    ("op_profit_yoy_sector_pct","섹터 내 영업이익 성장 백분위", "0~1, 흑자전환은 최상위로 처리",                       "snapshot"),
    ("earnings_momentum_score","실적 모멘텀 복합 점수",    "0~1, 성장 백분위(70%) + 가속 여부(30%)",                  "snapshot"),
    ("earnings_growth_bucket", "실적 성장 버킷",          "strong_growth(>=30%) > growth(>=0%) > flat(>=-10%) > decline > no_data", "snapshot"),
]


def run():
    logger.info("earnings_momentum 팩터 구축 시작")
    snapshot_date = datetime.fromtimestamp(CSV_PATH.stat().st_mtime).strftime("%Y-%m-%d")

    df = build(snapshot_date)

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("factor_earnings_momentum_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_earnings_momentum_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_earnings_momentum_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_earnings_momentum_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 실적 모멘텀 상위 20 (earnings_momentum_score) ===")
    print(df.nlargest(20, "earnings_momentum_score")[
        ["ticker", "sector", "latest_quarter", "op_profit_yoy", "earnings_accel_flag",
         "op_turnaround_flag", "earnings_momentum_score", "earnings_growth_bucket"]
    ].to_string())
