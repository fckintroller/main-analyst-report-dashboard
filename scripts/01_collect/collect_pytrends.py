"""
Google Trends (pytrends) 수집 스크립트 — 한국 주식 테마/종목 검색 모멘텀.
- 소스: Google Trends (키 불필요)
- 수집 기간: 최근 5년 (월별) + 최근 90일 (일별)
- 저장 경로: data/raw/sentiment/pytrends_{keyword}.csv
- 실행: python scripts/01_collect/collect_pytrends.py
- 주의: Google 요청 제한으로 주 1회(월요일)만 실행. 강제 실행: --force 인자 전달
"""
import logging
import os
import sys
import time
from datetime import datetime

import pandas as pd
from pytrends.request import TrendReq
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAVE_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "sentiment")

# 수집 대상 키워드 — 단기 모멘텀 포착용
# Google Trends는 한 번에 최대 5개 비교 가능
KEYWORD_GROUPS = [
    # 테마/섹터 모멘텀
    ["반도체", "2차전지", "AI", "바이오", "방산"],
    # 투자 심리
    ["주식", "코스피", "코스닥", "삼성전자", "ETF"],
    # 매크로 관심도
    ["금리", "환율", "인플레이션", "경기침체", "미국주식"],
]


def fetch_group(pytrends: TrendReq, keywords: list[str], timeframe: str) -> pd.DataFrame:
    for attempt in range(3):
        try:
            pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo="KR", gprop="")
            df = pytrends.interest_over_time()
            if df.empty:
                return pd.DataFrame()
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])
            return df
        except Exception as e:
            logger.warning("시도 %d 실패 (%s): %s", attempt + 1, keywords, e)
            time.sleep(10 * (attempt + 1))
    return pd.DataFrame()


def save_csv(keyword: str, df: pd.DataFrame, suffix: str = ""):
    os.makedirs(SAVE_DIR, exist_ok=True)
    safe_key = keyword.replace(" ", "_").replace("/", "_")
    path = os.path.join(SAVE_DIR, f"pytrends_{safe_key}{suffix}.csv")
    if os.path.exists(path):
        try:
            existing = pd.read_csv(path, index_col=0, parse_dates=True)
            new_rows = df[[keyword]] if keyword in df.columns else df
            new_rows = new_rows[~new_rows.index.isin(existing.index)]
            df_save = pd.concat([existing, new_rows]).sort_index()
        except Exception:
            df_save = df[[keyword]] if keyword in df.columns else df
    else:
        df_save = df[[keyword]] if keyword in df.columns else df
    df_save.columns = ["trend_score"]
    df_save.to_csv(path)


def run():
    # 주 1회 제한 — 월요일(0)에만 실행. --force 인자로 우회 가능
    force = "--force" in sys.argv
    if not force and datetime.today().weekday() != 0:
        logger.info("[Trends] 오늘은 월요일이 아님 (weekday=%d) — 스킵. 강제 실행: --force",
                    datetime.today().weekday())
        return

    os.makedirs(SAVE_DIR, exist_ok=True)
    pytrends = TrendReq(hl="ko", tz=540, timeout=(10, 30))
    ok, skip = 0, 0

    for group in KEYWORD_GROUPS:
        logger.info("[Trends] 그룹: %s", group)

        # 월별 (5년)
        df_monthly = fetch_group(pytrends, group, "today 5-y")
        if not df_monthly.empty:
            for kw in group:
                if kw in df_monthly.columns:
                    save_csv(kw, df_monthly, "_monthly")
                    logger.info(" - %s monthly: %d행", kw, len(df_monthly))
                    ok += 1
        else:
            logger.warning(" - 그룹 월별 수집 실패: %s", group)
            skip += len(group)

        time.sleep(5)

        # 일별 (90일)
        df_daily = fetch_group(pytrends, group, "today 3-m")
        if not df_daily.empty:
            for kw in group:
                if kw in df_daily.columns:
                    save_csv(kw, df_daily, "_daily")
                    logger.info(" - %s daily: %d행", kw, len(df_daily))
        else:
            logger.warning(" - 그룹 일별 수집 실패: %s", group)

        time.sleep(8)

    logger.info("=== pytrends 완료: 성공 %d / 실패 %d ===", ok, skip)


if __name__ == "__main__":
    run()
