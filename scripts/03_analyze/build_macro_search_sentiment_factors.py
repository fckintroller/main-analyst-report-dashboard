"""
거시 검색 트렌드 심리 팩터 구축 — Google Trends 매크로/테마 키워드 (주간, 5년).

소스:
  sentiment_pytrends_{keyword}_monthly (주간, 2021-05-30 ~ 2026-05-31, 262행 × 15개 키워드)
  컬럼: date, trend_score (0~100, Google Trends 상대 검색량 지수 — 키워드별 자체 정규화)

  키워드 그룹:
    거시 불안(anxiety): 경기침체, 인플레이션, 금리, 환율
    리테일 관심(retail): 주식, 코스피, 코스닥, 미국주식, etf, 삼성전자
    테마(theme): 반도체, 2차전지, ai, 바이오, 방산

출력 컬럼 (시장 전체 단일 시계열, 월간):
  macro_anxiety_score      : 0~1, mean(거시 불안 키워드별 trend_score 자체-기간 백분위)
  retail_interest_score    : 0~1, mean(리테일 관심 키워드별 trend_score 자체-기간 백분위)
  theme_semiconductor_score: 0~1, '반도체' trend_score 자체-기간 백분위
  theme_battery_score      : 0~1, '2차전지' trend_score 자체-기간 백분위
  theme_ai_score           : 0~1, 'ai' trend_score 자체-기간 백분위
  theme_bio_score          : 0~1, '바이오' trend_score 자체-기간 백분위
  theme_defense_score       : 0~1, '방산' trend_score 자체-기간 백분위
  anxiety_level             : very_high > high > neutral > low > very_low (macro_anxiety_score 기준)
  interest_level            : very_high > high > neutral > low > very_low (retail_interest_score 기준)

  ※ 키워드별 trend_score는 검색 배치별로 정규화 기준이 달라 키워드 간 절대값 비교는
     의미 없음 — 반드시 "키워드 자체 기간 내 백분위"로만 사용
  ※ 백분위는 전체 샘플(2021-05~2026-05, 약 60개월) 기준 — look-ahead 주의

출력 DB 테이블:
  factor_macro_search_sentiment_month
  factor_macro_search_sentiment_catalog
"""
import logging
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ANXIETY_KEYWORDS = ["경기침체", "인플레이션", "금리", "환율"]
RETAIL_KEYWORDS = ["주식", "코스피", "코스닥", "미국주식", "etf", "삼성전자"]
THEME_KEYWORDS = {
    "반도체": "theme_semiconductor_score",
    "2차전지": "theme_battery_score",
    "ai": "theme_ai_score",
    "바이오": "theme_bio_score",
    "방산": "theme_defense_score",
}


def _bucket_level(score: float) -> str:
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


def _load_keyword_pctile(conn: sqlite3.Connection, keyword: str) -> pd.Series:
    df = pd.read_sql(f'SELECT date, trend_score FROM "sentiment_pytrends_{keyword}_monthly"', conn)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    monthly = df["trend_score"].resample("ME").mean()
    return monthly.rank(pct=True)


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    pctiles = {}
    for keyword in set(ANXIETY_KEYWORDS) | set(RETAIL_KEYWORDS) | set(THEME_KEYWORDS):
        pctiles[keyword] = _load_keyword_pctile(conn, keyword)

    index = pctiles[next(iter(pctiles))].index
    out = pd.DataFrame(index=index)

    out["macro_anxiety_score"] = pd.concat([pctiles[k] for k in ANXIETY_KEYWORDS], axis=1).mean(axis=1)
    out["retail_interest_score"] = pd.concat([pctiles[k] for k in RETAIL_KEYWORDS], axis=1).mean(axis=1)
    for keyword, col in THEME_KEYWORDS.items():
        out[col] = pctiles[keyword]

    out["anxiety_level"] = out["macro_anxiety_score"].apply(_bucket_level)
    out["interest_level"] = out["retail_interest_score"].apply(_bucket_level)

    out.index.name = "period"
    out = out.reset_index()
    out["period"] = out["period"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-01")

    logger.info("구축 완료: %d개월", len(out))
    return out[[
        "period", "macro_anxiety_score", "retail_interest_score",
        "theme_semiconductor_score", "theme_battery_score", "theme_ai_score",
        "theme_bio_score", "theme_defense_score", "anxiety_level", "interest_level",
    ]]


CATALOG = [
    ("macro_anxiety_score",       "거시 불안 검색 점수",     "0~1, 경기침체/인플레이션/금리/환율 검색량 백분위 평균",  "month"),
    ("retail_interest_score",     "리테일 관심 검색 점수",   "0~1, 주식/코스피/코스닥/미국주식/etf/삼성전자 검색량 백분위 평균", "month"),
    ("theme_semiconductor_score", "반도체 테마 검색 점수",   "0~1, '반도체' 검색량 자체-기간 백분위",                "month"),
    ("theme_battery_score",       "2차전지 테마 검색 점수",  "0~1, '2차전지' 검색량 자체-기간 백분위",               "month"),
    ("theme_ai_score",            "AI 테마 검색 점수",       "0~1, 'AI' 검색량 자체-기간 백분위",                    "month"),
    ("theme_bio_score",           "바이오 테마 검색 점수",   "0~1, '바이오' 검색량 자체-기간 백분위",                "month"),
    ("theme_defense_score",       "방산 테마 검색 점수",     "0~1, '방산' 검색량 자체-기간 백분위",                  "month"),
    ("anxiety_level",             "거시 불안 레벨",          "very_high > high > neutral > low > very_low",         "month"),
    ("interest_level",            "리테일 관심 레벨",        "very_high > high > neutral > low > very_low",         "month"),
]


def run():
    logger.info("macro_search_sentiment 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_macro_search_sentiment_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_macro_search_sentiment_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG, columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_macro_search_sentiment_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_macro_search_sentiment_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print("\n=== 최근 6개월 거시 검색 트렌드 심리 ===")
    print(df[["period", "macro_anxiety_score", "retail_interest_score", "anxiety_level", "interest_level"]].tail(6))
