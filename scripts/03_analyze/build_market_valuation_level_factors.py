"""
시장 밸류에이션 레벨 팩터 구축 — KOSPI 전체 PBR 히스토리컬 percentile.

소스:
  valuation_kospi_fundamental_history (일별, 2023-06-07 ~ 2026-06-05, 729행): date, kospi_pbr
  valuation_kospi_pbr_percentile      (스냅샷 1행, 2026-06-05): date, current_pbr, percentile,
                                        min_10y, max_10y, median_10y, mean_10y

출력 컬럼 (시장 전체 단일 시계열, 월간):
  pbr_eom        : 월말 KOSPI PBR
  pbr_avg        : 월평균 KOSPI PBR
  pbr_pctile_3y  : 0~1, 표본 기간(2023-06~2026-06, 약 36개월) 내 pbr_eom 백분위
  pbr_pctile_10y : 0~1, 10년 기준 percentile — valuation_kospi_pbr_percentile 스냅샷 기준,
                   스냅샷 일자가 속한 월에만 값 존재(그 외 월은 NaN/None)
  valuation_regime : very_cheap < cheap < neutral < expensive < very_expensive
                      (pbr_pctile_10y가 있으면 그 값을, 없으면 pbr_pctile_3y를 사용)

  ※ pbr_pctile_3y는 표본이 짧아(3년) look-ahead 주의 — 상대 추세 참고용
  ※ pbr_pctile_10y는 단일 스냅샷(2026-06-05)에서만 제공되는 10년 기준 절대 레벨로,
     "현재 시장이 10년래 어느 수준인지"를 보여주는 보조 참고치 (시계열 아님)

출력 DB 테이블:
  factor_market_valuation_level_month
  factor_market_valuation_level_catalog
"""
import logging
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _bucket_valuation(pctile: float) -> str:
    if pd.isna(pctile):
        return "unknown"
    if pctile >= 0.8:
        return "very_expensive"
    if pctile >= 0.6:
        return "expensive"
    if pctile >= 0.4:
        return "neutral"
    if pctile >= 0.2:
        return "cheap"
    return "very_cheap"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    hist = pd.read_sql("SELECT date, kospi_pbr FROM valuation_kospi_fundamental_history", conn)
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date").set_index("date")

    monthly_eom = hist["kospi_pbr"].resample("ME").last()
    monthly_avg = hist["kospi_pbr"].resample("ME").mean()

    out = pd.DataFrame({
        "pbr_eom": monthly_eom,
        "pbr_avg": monthly_avg,
    })
    out["pbr_pctile_3y"] = out["pbr_eom"].rank(pct=True)
    out["pbr_pctile_10y"] = pd.NA

    out = out.reset_index().rename(columns={"date": "period"})
    out["period"] = out["period"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-01")

    snapshot = pd.read_sql(
        "SELECT date, percentile FROM valuation_kospi_pbr_percentile ORDER BY date DESC LIMIT 1", conn
    )
    if not snapshot.empty:
        snap_date = pd.to_datetime(snapshot.iloc[0]["date"])
        snap_period = snap_date.to_period("M").to_timestamp().strftime("%Y-%m-01")
        snap_pctile_10y = snapshot.iloc[0]["percentile"] / 100.0
        mask = out["period"] == snap_period
        out.loc[mask, "pbr_pctile_10y"] = snap_pctile_10y

    out["valuation_regime"] = out["pbr_pctile_10y"].combine_first(out["pbr_pctile_3y"]).apply(_bucket_valuation)

    logger.info("구축 완료: %d개월", len(out))
    return out[["period", "pbr_eom", "pbr_avg", "pbr_pctile_3y", "pbr_pctile_10y", "valuation_regime"]]


CATALOG = [
    ("pbr_eom",          "월말 KOSPI PBR",          "코스피 전체 PBR (월말 기준)",                          "month"),
    ("pbr_avg",          "월평균 KOSPI PBR",        "코스피 전체 PBR (월간 평균)",                          "month"),
    ("pbr_pctile_3y",    "PBR 3년 백분위",          "0~1, 표본 기간(약 36개월) 내 pbr_eom 상대 순위",        "month"),
    ("pbr_pctile_10y",   "PBR 10년 백분위(스냅샷)", "0~1, 10년 기준 percentile — 스냅샷 해당 월에만 존재",   "month"),
    ("valuation_regime", "시장 밸류에이션 레짐",    "very_cheap < cheap < neutral < expensive < very_expensive", "month"),
]


def run():
    logger.info("market_valuation_level 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_market_valuation_level_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_market_valuation_level_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_market_valuation_level_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_market_valuation_level_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 최근 6개월 시장 밸류에이션 레벨 ===")
    print(df[["period", "pbr_eom", "pbr_pctile_3y", "pbr_pctile_10y", "valuation_regime"]].tail(6))
