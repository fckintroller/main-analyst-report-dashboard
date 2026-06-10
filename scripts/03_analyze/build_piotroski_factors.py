"""
Piotroski F-Score 팩터 구축.

원천: data/raw/valuation/dart_finstate/finstate_all.csv
      (collect_dart_finstate_once.py로 수집된 DART 연간 재무제표)

F-Score 9개 기준:
  [수익성]
  F1  ROA > 0                  : 당기순이익 / 자산총계 > 0
  F2  CFO > 0                  : 영업활동현금흐름 > 0
  F3  ΔROA > 0                 : 당기 ROA > 전기 ROA
  F4  CFO > 순이익 (발생주의)  : CFO/자산 > ROA (현금 이익 > 회계 이익)

  [레버리지·유동성]
  F5  Δ장기부채비율 < 0        : 비유동부채/자산 감소
  F6  Δ유동비율 > 0            : 유동자산/유동부채 증가
  F7  신주발행 없음             : 자본금 미증가

  [운영 효율성]
  F8  Δ매출총이익률 > 0        : 매출총이익/매출액 증가
  F9  Δ자산회전율 > 0          : 매출액/자산총계 증가

총점 0~9, 버킷: strong(8~9) / good(6~7) / neutral(4~5) / weak(2~3) / distress(0~1)

출력 DB:
  factor_piotroski_snapshot  : 종목별 스냅샷 (F1~F9 + 총점 + 점수)
  factor_piotroski_catalog   : 팩터 메타데이터
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH    = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
RAW_PATH   = PROJECT_ROOT / "data" / "raw" / "valuation" / "dart_finstate" / "finstate_all.csv"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

MIN_SECTOR_N = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_sector_map(conn: sqlite3.Connection) -> dict[str, str]:
    if SECTOR_MAP_PATH.exists():
        try:
            sm = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
            return dict(zip(sm.iloc[:, 0].astype(str).str.zfill(6), sm.iloc[:, 1].astype(str)))
        except Exception:
            pass
    try:
        df = pd.read_sql("SELECT DISTINCT ticker, sector FROM factor_valuation_per_pbr_month", conn)
        return dict(zip(df["ticker"], df["sector"]))
    except Exception:
        return {}


def _pivot(df: pd.DataFrame, ticker: str) -> dict[str, float]:
    """한 종목의 long-form 데이터를 {account_id_period: value} dict로 변환."""
    sub = df[df["ticker"] == ticker]
    result = {}
    for _, row in sub.iterrows():
        key = f"{row['account_id']}_{row['period']}"
        result[key] = float(row["amount"]) if pd.notna(row["amount"]) else np.nan
    return result


def _safe(d: dict, key: str) -> float:
    return d.get(key, np.nan)


def _f_score(d: dict) -> dict:
    """9개 Piotroski 기준을 계산해 dict로 반환."""
    # 원천값 추출
    ta_c  = _safe(d, "total_assets_current")
    ta_p  = _safe(d, "total_assets_prior")
    ni_c  = _safe(d, "net_income_current")
    ni_p  = _safe(d, "net_income_prior")
    cfo_c = _safe(d, "cfo_current")
    cfo_p = _safe(d, "cfo_prior")
    cl_c  = _safe(d, "current_liabilities_current")
    cl_p  = _safe(d, "current_liabilities_prior")
    ca_c  = _safe(d, "current_assets_current")
    ca_p  = _safe(d, "current_assets_prior")
    ncl_c = _safe(d, "noncurrent_liabilities_current")
    ncl_p = _safe(d, "noncurrent_liabilities_prior")
    cap_c = _safe(d, "capital_stock_current")
    cap_p = _safe(d, "capital_stock_prior")
    rev_c = _safe(d, "revenue_current")
    rev_p = _safe(d, "revenue_prior")
    gp_c  = _safe(d, "gross_profit_current")
    gp_p  = _safe(d, "gross_profit_prior")

    def flag(cond) -> int | float:
        return int(cond) if not (isinstance(cond, float) and pd.isna(cond)) else np.nan

    # 파생 지표
    roa_c  = (ni_c / ta_c)  if (pd.notna(ta_c)  and ta_c  > 0 and pd.notna(ni_c))  else np.nan
    roa_p  = (ni_p / ta_p)  if (pd.notna(ta_p)  and ta_p  > 0 and pd.notna(ni_p))  else np.nan
    cfo_a_c = (cfo_c / ta_c) if (pd.notna(ta_c) and ta_c  > 0 and pd.notna(cfo_c)) else np.nan
    lev_c  = (ncl_c / ta_c) if (pd.notna(ta_c)  and ta_c  > 0 and pd.notna(ncl_c)) else np.nan
    lev_p  = (ncl_p / ta_p) if (pd.notna(ta_p)  and ta_p  > 0 and pd.notna(ncl_p)) else np.nan
    cr_c   = (ca_c / cl_c)  if (pd.notna(cl_c)  and cl_c  > 0 and pd.notna(ca_c))  else np.nan
    cr_p   = (ca_p / cl_p)  if (pd.notna(cl_p)  and cl_p  > 0 and pd.notna(ca_p))  else np.nan
    gm_c   = (gp_c / rev_c) if (pd.notna(rev_c) and rev_c > 0 and pd.notna(gp_c))  else np.nan
    gm_p   = (gp_p / rev_p) if (pd.notna(rev_p) and rev_p > 0 and pd.notna(gp_p))  else np.nan
    at_c   = (rev_c / ta_c) if (pd.notna(ta_c)  and ta_c  > 0 and pd.notna(rev_c)) else np.nan
    at_p   = (rev_p / ta_p) if (pd.notna(ta_p)  and ta_p  > 0 and pd.notna(rev_p)) else np.nan

    # 9개 기준
    f1 = flag(roa_c  > 0)                                        if pd.notna(roa_c) else np.nan
    f2 = flag(cfo_c  > 0)                                        if pd.notna(cfo_c) else np.nan
    f3 = flag(roa_c  > roa_p)  if pd.notna(roa_c)  and pd.notna(roa_p)  else np.nan
    f4 = flag(cfo_a_c > roa_c) if pd.notna(cfo_a_c) and pd.notna(roa_c) else np.nan
    f5 = flag(lev_c  < lev_p)  if pd.notna(lev_c)  and pd.notna(lev_p)  else np.nan
    f6 = flag(cr_c   > cr_p)   if pd.notna(cr_c)   and pd.notna(cr_p)   else np.nan
    f7 = flag(pd.notna(cap_c) and pd.notna(cap_p) and cap_c <= cap_p)
    f8 = flag(gm_c   > gm_p)   if pd.notna(gm_c)   and pd.notna(gm_p)   else np.nan
    f9 = flag(at_c   > at_p)   if pd.notna(at_c)   and pd.notna(at_p)   else np.nan

    flags = [f1, f2, f3, f4, f5, f6, f7, f8, f9]
    valid = [f for f in flags if pd.notna(f)]
    f_total = sum(valid) if valid else np.nan

    return {
        "f1_roa_positive": f1,  "f2_cfo_positive": f2,
        "f3_roa_improving": f3, "f4_accrual_quality": f4,
        "f5_leverage_down": f5, "f6_liquidity_up": f6, "f7_no_dilution": f7,
        "f8_gross_margin_up": f8, "f9_asset_turnover_up": f9,
        "f_score": f_total,
        # 원천 파생지표 (참고용)
        "roa_current": roa_c, "cfo_to_assets": cfo_a_c,
        "current_ratio": cr_c, "gross_margin": gm_c, "asset_turnover": at_c,
        "leverage_ratio": lev_c,
    }


def _bucket(score) -> str:
    if pd.isna(score):
        return "unknown"
    s = int(score)
    if s >= 8: return "strong"
    if s >= 6: return "good"
    if s >= 4: return "neutral"
    if s >= 2: return "weak"
    return "distress"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"재무제표 원천 파일 없음: {RAW_PATH}")

    raw = pd.read_csv(RAW_PATH, encoding="utf-8-sig")
    raw["ticker"] = raw["ticker"].astype(str).str.zfill(6)
    logger.info("원천 데이터: %d행, %d종목", len(raw), raw["ticker"].nunique())

    sector_map = _load_sector_map(conn)
    tickers = raw["ticker"].unique().tolist()

    records = []
    for ticker in tickers:
        d = _pivot(raw, ticker)
        feat = _f_score(d)
        feat["ticker"] = ticker
        feat["bsns_year"] = raw[raw["ticker"] == ticker]["bsns_year"].iloc[0] \
                            if len(raw[raw["ticker"] == ticker]) > 0 else np.nan
        records.append(feat)

    df = pd.DataFrame(records)
    df["sector"] = df["ticker"].map(sector_map).fillna("unknown")

    # 섹터 내 F-Score 백분위
    df["f_score_sector_pct"] = df.groupby("sector")["f_score"].rank(pct=True)
    small_sectors = df.groupby("sector")["f_score"].count()
    small_sectors = small_sectors[small_sectors < MIN_SECTOR_N].index
    df.loc[df["sector"].isin(small_sectors), "f_score_sector_pct"] = np.nan

    # 0~1 정규화 점수 (F-Score/9)
    df["f_score_norm"] = (df["f_score"] / 9).clip(0, 1)

    df["f_bucket"] = df["f_score"].apply(_bucket)

    logger.info("F-Score 완료: %d종목, 유효 %d종목",
                len(df), df["f_score"].notna().sum())

    cols = [
        "ticker", "bsns_year", "sector",
        "f_score", "f_score_norm", "f_score_sector_pct", "f_bucket",
        "f1_roa_positive", "f2_cfo_positive", "f3_roa_improving", "f4_accrual_quality",
        "f5_leverage_down", "f6_liquidity_up", "f7_no_dilution",
        "f8_gross_margin_up", "f9_asset_turnover_up",
        "roa_current", "cfo_to_assets", "current_ratio", "gross_margin",
        "asset_turnover", "leverage_ratio",
    ]
    return df[[c for c in cols if c in df.columns]]


CATALOG = [
    ("f_score",              "Piotroski F-Score",              "0~9 정수",                                      "annual_snapshot"),
    ("f_score_norm",         "F-Score 정규화 점수",             "0~1 (= f_score/9)",                            "annual_snapshot"),
    ("f_score_sector_pct",   "섹터 내 F-Score 백분위",          "0~1",                                           "annual_snapshot"),
    ("f_bucket",             "F-Score 버킷",                    "strong(8~9)/good(6~7)/neutral/weak/distress",   "annual_snapshot"),
    ("f1_roa_positive",      "F1: ROA > 0",                    "1=충족",                                        "annual_snapshot"),
    ("f2_cfo_positive",      "F2: 영업현금흐름 > 0",            "1=충족",                                        "annual_snapshot"),
    ("f3_roa_improving",     "F3: ROA 개선",                    "1=전년 대비 상승",                               "annual_snapshot"),
    ("f4_accrual_quality",   "F4: CFO/자산 > ROA",              "1=현금이익이 회계이익보다 우량",                 "annual_snapshot"),
    ("f5_leverage_down",     "F5: 장기부채비율 감소",            "1=비유동부채/자산 전년 대비 감소",               "annual_snapshot"),
    ("f6_liquidity_up",      "F6: 유동비율 상승",                "1=유동자산/유동부채 전년 대비 증가",             "annual_snapshot"),
    ("f7_no_dilution",       "F7: 신주 미발행",                  "1=자본금 미증가",                               "annual_snapshot"),
    ("f8_gross_margin_up",   "F8: 매출총이익률 개선",            "1=전년 대비 상승",                               "annual_snapshot"),
    ("f9_asset_turnover_up", "F9: 자산회전율 개선",              "1=매출/자산 전년 대비 증가",                     "annual_snapshot"),
]


def run():
    logger.info("piotroski 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_piotroski_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_piotroski_snapshot 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_piotroski_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_piotroski_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== F-Score 상위 20 ===")
    print(df.nlargest(20, "f_score")[
        ["ticker", "sector", "f_score", "f_bucket",
         "roa_current", "gross_margin", "current_ratio"]
    ].assign(roa_pct=lambda d: (d["roa_current"]*100).round(1),
             gm_pct=lambda d: (d["gross_margin"]*100).round(1))
     .to_string())
