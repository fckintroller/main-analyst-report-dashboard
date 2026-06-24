"""
시장 수급 동향 팩터 구축 — KOSPI/KOSDAQ 투자자별 순매수 동향 (20년 일별).

소스:
  money_flow_market_trading_value_kospi_20y  (일별, 2006-06-01 ~ 2026-06-05, 4,933행)
  money_flow_market_trading_value_kosdaq_20y (일별, 2006-06-01 ~ 2026-06-05, 4,933행)
  컬럼: date, 개인, 외국인, 기관계, 연기금등 (그 외 금융투자/보험/투신/은행/기타금융/기타법인 등)
  ※ 단위는 원천 데이터(KRX) 그대로 — 상대비교(추세/백분위) 용도로만 사용

출력 컬럼 (시장×월간):
  indiv_net          : 월간 개인 순매수 합계
  foreign_net        : 월간 외국인 순매수 합계
  inst_net           : 월간 기관계 순매수 합계
  pension_net        : 월간 연기금등 순매수 합계
  foreign_net_pctile : 0~1, foreign_net의 전체 기간(시장별 약 240개월) 백분위
  inst_net_pctile    : 0~1, inst_net의 전체 기간 백분위
  pension_net_pctile : 0~1, pension_net의 전체 기간 백분위
  flow_score         : 0~1, mean(foreign_net_pctile, inst_net_pctile) — 수급 종합 점수
  flow_regime        : strong_inflow > inflow > neutral > outflow > strong_outflow

  ※ 백분위는 전체 샘플(2006-06~2026-06, 약 240개월) 기준 — 과거 시점 분석 시
     look-ahead 주의 (전체 기간 정보가 포함된 상대 순위)

출력 DB 테이블:
  factor_market_money_flow_month
  factor_market_money_flow_catalog
"""
import logging
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MARKETS = ["kospi", "kosdaq"]


def _bucket_flow(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= 0.8:
        return "strong_inflow"
    if score >= 0.6:
        return "inflow"
    if score >= 0.4:
        return "neutral"
    if score >= 0.2:
        return "outflow"
    return "strong_outflow"


def _load_market(conn: sqlite3.Connection, market: str) -> pd.DataFrame:
    sql = (
        'SELECT date, "개인" AS indiv, "외국인" AS foreign_, "기관계" AS inst, "연기금등" AS pension '
        f'FROM money_flow_market_trading_value_{market}_20y'
    )
    df = pd.read_sql(sql, conn)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")

    monthly = df.resample("ME").sum()
    monthly = monthly.rename(columns={
        "indiv": "indiv_net",
        "foreign_": "foreign_net",
        "inst": "inst_net",
        "pension": "pension_net",
    })

    monthly["foreign_net_pctile"] = monthly["foreign_net"].rank(pct=True)
    monthly["inst_net_pctile"] = monthly["inst_net"].rank(pct=True)
    monthly["pension_net_pctile"] = monthly["pension_net"].rank(pct=True)
    monthly["flow_score"] = monthly[["foreign_net_pctile", "inst_net_pctile"]].mean(axis=1)
    monthly["flow_regime"] = monthly["flow_score"].apply(_bucket_flow)

    monthly = monthly.reset_index().rename(columns={"date": "period"})
    monthly["period"] = monthly["period"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-01")
    monthly.insert(1, "market", market.upper())
    return monthly


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    frames = [_load_market(conn, market) for market in MARKETS]
    out = pd.concat(frames, ignore_index=True)
    logger.info("구축 완료: %d행 (%s)", len(out), ", ".join(MARKETS))
    return out[[
        "period", "market", "indiv_net", "foreign_net", "inst_net", "pension_net",
        "foreign_net_pctile", "inst_net_pctile", "pension_net_pctile",
        "flow_score", "flow_regime",
    ]]


CATALOG = [
    ("indiv_net",          "월간 개인 순매수 합계",     "양수=순매수, 음수=순매도 (원천 데이터 단위)",          "month"),
    ("foreign_net",        "월간 외국인 순매수 합계",   "양수=순매수, 음수=순매도 (원천 데이터 단위)",          "month"),
    ("inst_net",           "월간 기관계 순매수 합계",   "양수=순매수, 음수=순매도 (원천 데이터 단위)",          "month"),
    ("pension_net",        "월간 연기금등 순매수 합계", "양수=순매수, 음수=순매도 (원천 데이터 단위)",          "month"),
    ("foreign_net_pctile", "외국인 순매수 백분위",     "0~1, 전체 기간(약 240개월) 중 foreign_net 상대 순위", "month"),
    ("inst_net_pctile",    "기관계 순매수 백분위",     "0~1, 전체 기간 중 inst_net 상대 순위",                "month"),
    ("pension_net_pctile", "연기금 순매수 백분위",     "0~1, 전체 기간 중 pension_net 상대 순위",             "month"),
    ("flow_score",         "수급 종합 점수",           "0~1, mean(foreign_net_pctile, inst_net_pctile)",     "month"),
    ("flow_regime",        "수급 레짐",                "strong_inflow > inflow > neutral > outflow > strong_outflow", "month"),
]


def run():
    logger.info("market_money_flow 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_market_money_flow_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_market_money_flow_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_market_money_flow_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_market_money_flow_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 최근 6개월 시장 수급 레짐 ===")
    print(df[df["market"] == "KOSPI"][["period", "market", "flow_score", "flow_regime"]].tail(6))
    print(df[df["market"] == "KOSDAQ"][["period", "market", "flow_score", "flow_regime"]].tail(6))
