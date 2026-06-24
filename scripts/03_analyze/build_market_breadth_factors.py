"""
시장 폭(Breadth) 팩터 구축 — ADL(Advance/Decline Line) + TRIN(Arms Index).

소스:
  sentiment_kr_adl  (일별, 2024-06-03 ~ 2026-06-02): date, advancing, declining, unchanged, adl_cumulative
  sentiment_kr_trin (일별, 2024-06-03 ~ 2026-06-02): date, advancing, declining, adv_volume, dec_volume, trin, signal

출력 컬럼 (월간, 시장 전체 단일 시계열):
  adl_net_advances     : 월간 (상승 종목수 - 하락 종목수) 합계
  adl_cumulative_eom    : 월말 ADL 누적치
  trin_avg              : 월평균 TRIN (Arms Index, <1=매수세 우위)
  bullish_days_pct       : signal=Bullish 비율 (%)
  bearish_days_pct       : signal=Bearish 비율 (%)
  adl_trend_pctile       : 0~1, adl_net_advances의 전체 기간 백분위
  trin_pctile            : 0~1, trin_avg의 전체 기간 백분위 (TRIN 낮을수록 강세)
  breadth_score          : 0~1, mean(adl_trend_pctile, 1-trin_pctile) — 시장 폭 종합 점수
  breadth_regime         : broad_bullish > bullish > neutral > bearish > broad_bearish

  ※ 백분위는 전체 샘플(2024-06~2026-06, 24개월) 기준 — 표본이 짧아 절대 임계값보다
     상대적 추세 참고용으로 사용 권장 (look-ahead 주의)

출력 DB 테이블:
  factor_market_breadth_month
  factor_market_breadth_catalog
"""
import logging
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _bucket_breadth(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= 0.8:
        return "broad_bullish"
    if score >= 0.6:
        return "bullish"
    if score >= 0.4:
        return "neutral"
    if score >= 0.2:
        return "bearish"
    return "broad_bearish"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    adl = pd.read_sql("SELECT date, advancing, declining, adl_cumulative FROM sentiment_kr_adl", conn)
    trin = pd.read_sql("SELECT date, trin, signal FROM sentiment_kr_trin", conn)

    adl["date"] = pd.to_datetime(adl["date"])
    trin["date"] = pd.to_datetime(trin["date"])

    df = pd.merge(adl, trin, on="date", how="inner").sort_values("date").set_index("date")
    df["net_advances"] = df["advancing"] - df["declining"]

    monthly_net = df["net_advances"].resample("ME").sum()
    monthly_adl_eom = df["adl_cumulative"].resample("ME").last()
    monthly_trin_avg = df["trin"].resample("ME").mean()
    monthly_bullish_pct = df["signal"].eq("Bullish").resample("ME").mean() * 100
    monthly_bearish_pct = df["signal"].eq("Bearish").resample("ME").mean() * 100

    out = pd.DataFrame({
        "adl_net_advances": monthly_net,
        "adl_cumulative_eom": monthly_adl_eom,
        "trin_avg": monthly_trin_avg,
        "bullish_days_pct": monthly_bullish_pct,
        "bearish_days_pct": monthly_bearish_pct,
    })

    out["adl_trend_pctile"] = out["adl_net_advances"].rank(pct=True)
    out["trin_pctile"] = out["trin_avg"].rank(pct=True)
    out["breadth_score"] = out[["adl_trend_pctile"]].assign(
        inv_trin=1 - out["trin_pctile"]
    )[["adl_trend_pctile", "inv_trin"]].mean(axis=1)
    out["breadth_regime"] = out["breadth_score"].apply(_bucket_breadth)

    out = out.reset_index().rename(columns={"date": "period"})
    out["period"] = out["period"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-01")

    logger.info("구축 완료: %d개월", len(out))
    return out[[
        "period", "adl_net_advances", "adl_cumulative_eom", "trin_avg",
        "bullish_days_pct", "bearish_days_pct",
        "adl_trend_pctile", "trin_pctile", "breadth_score", "breadth_regime",
    ]]


CATALOG = [
    ("adl_net_advances",  "월간 순상승종목수",       "상승종목수-하락종목수 합계, 양수=상승종목 우세",        "month"),
    ("adl_cumulative_eom", "ADL 누적치(월말)",       "Advance/Decline Line 누적값, 추세 방향 참고",          "month"),
    ("trin_avg",          "월평균 TRIN(Arms Index)", "<1=매수세 우위(강세), >1=매도세 우위(약세)",            "month"),
    ("bullish_days_pct",   "강세 신호일 비율",       "%, signal=Bullish인 날의 비율",                       "month"),
    ("bearish_days_pct",   "약세 신호일 비율",       "%, signal=Bearish인 날의 비율",                       "month"),
    ("adl_trend_pctile",   "ADL 추세 백분위",        "0~1, 전체 기간(24개월) 중 adl_net_advances 상대 순위",  "month"),
    ("trin_pctile",        "TRIN 백분위",            "0~1, 전체 기간 중 trin_avg 상대 순위 (낮을수록 강세)",   "month"),
    ("breadth_score",      "시장 폭 종합 점수",       "0~1, mean(adl_trend_pctile, 1-trin_pctile)",         "month"),
    ("breadth_regime",     "시장 폭 레짐",           "broad_bullish > bullish > neutral > bearish > broad_bearish", "month"),
]


def run():
    logger.info("market_breadth 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_market_breadth_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_market_breadth_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_market_breadth_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_market_breadth_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 최근 6개월 시장 폭 레짐 ===")
    print(df[["period", "breadth_score", "breadth_regime"]].tail(6))
