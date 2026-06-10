"""
ECOS StatisticSearch 기반 한국 핵심 지표 역사 시계열 1회 수집 스크립트.
- 수집 기간: 2010-01-01 ~ 현재
- 저장 경로: data/raw/macro/macro_indices/
- 실행: python scripts/01_collect/collect_ecos_history_once.py
"""
import logging
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAVE_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "macro", "macro_indices")
BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/10000/{stat}/{cycle}/{sd}/{ed}/{item}"

# (저장명, STAT_CODE, CYCLE, ITEM_CODE, 설명)
SERIES = [
    # 금리 — 일별 817Y002
    ("KOR_CALL_RATE",  "817Y002", "D", "010101000", "콜금리(1일,전체거래) %"),
    ("KOR_KORIBOR3M",  "817Y002", "D", "010150000", "KORIBOR(3개월) %"),
    ("KOR_KORIBOR6M",  "817Y002", "D", "010151000", "KORIBOR(6개월) %"),
    ("KOR_GOV1Y",      "817Y002", "D", "010190000", "국고채(1년) %"),
    ("KOR_GOV2Y",      "817Y002", "D", "010195000", "국고채(2년) %"),
    ("KOR_GOV3Y",      "817Y002", "D", "010200000", "국고채(3년) %"),
    ("KOR_GOV5Y",      "817Y002", "D", "010200001", "국고채(5년) %"),
    ("KOR_GOV10Y",     "817Y002", "D", "010210000", "국고채(10년) %"),
    ("KOR_GOV20Y",     "817Y002", "D", "010220000", "국고채(20년) %"),
    ("KOR_GOV30Y",     "817Y002", "D", "010230000", "국고채(30년) %"),
    ("KOR_CORP_AA",    "817Y002", "D", "010300000", "회사채(3년,AA-) %"),
    ("KOR_CORP_BBB",   "817Y002", "D", "010320000", "회사채(3년,BBB-) %"),
    ("KOR_CD91",       "817Y002", "D", "010502000", "CD(91일) %"),
    ("KOR_CP91",       "817Y002", "D", "010503000", "CP(91일) %"),
    ("KOR_KOFR",       "817Y002", "D", "010901000", "KOFR(공시RFR) %"),
    # 기준금리 — 월별 722Y001
    ("KOR_BASE_RATE",  "722Y001", "M", "0101000",   "한국은행 기준금리 %"),
    # 생산자물가지수 — 월별 404Y014
    ("KOR_PPI",        "404Y014", "M", "*AA",        "생산자물가지수 총지수 (2020=100)"),
    # M2: StatisticSearch는 2004년 이전만 제공 → 01_macro.py KeyStatisticList 누적 방식 유지
    # 외환보유액 합계 — 월별 732Y001
    ("KOR_FX_RESERVES","732Y001", "M", "99",         "외환보유액 합계 백만달러"),
]


def date_range(cycle: str):
    """cycle에 맞는 start/end 날짜 문자열 반환."""
    if cycle == "D":
        return "20100101", pd.Timestamp.today().strftime("%Y%m%d")
    else:  # M, Q, A
        return "201001", pd.Timestamp.today().strftime("%Y%m")


def fetch_series(key: str, name: str, stat: str, cycle: str, item: str) -> pd.DataFrame:
    sd, ed = date_range(cycle)
    url = BASE_URL.format(key=key, stat=stat, cycle=cycle, sd=sd, ed=ed, item=item)
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=20)
            data = resp.json()
            rows = data.get("StatisticSearch", {}).get("row", [])
            if not rows:
                code = data.get("RESULT", {}).get("CODE", "")
                msg  = data.get("RESULT", {}).get("MESSAGE", "")
                logger.warning(" - %s: 데이터 없음 (%s %s)", name, code, msg)
                return pd.DataFrame()
            df = pd.DataFrame(rows)[["TIME", "DATA_VALUE"]]
            df.columns = ["date", "value"]
            df["value"] = pd.to_numeric(df["value"].str.replace(",", ""), errors="coerce")
            if cycle == "D":
                df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
            else:
                df["date"] = pd.to_datetime(df["date"].str[:6].apply(lambda x: f"{x[:4]}-{x[4:6]}-01"), errors="coerce")
            df = df.dropna().set_index("date").sort_index()
            return df
        except Exception as e:
            logger.warning(" - %s 시도 %d 실패: %s", name, attempt + 1, e)
            time.sleep(2 ** attempt)
    return pd.DataFrame()


def save_csv(df: pd.DataFrame, name: str):
    path = os.path.join(SAVE_DIR, f"{name}.csv")
    os.makedirs(SAVE_DIR, exist_ok=True)
    if os.path.exists(path):
        try:
            existing = pd.read_csv(path, index_col=0, parse_dates=True)
            existing.index.name = "date"
            df = pd.concat([existing, df[~df.index.isin(existing.index)]]).sort_index()
        except Exception:
            pass
    df.to_csv(path)


def run():
    key = os.environ.get("ECOS_API_KEY")
    if not key:
        logger.error("ECOS_API_KEY 미설정 — 종료")
        return

    os.makedirs(SAVE_DIR, exist_ok=True)
    ok, skip = 0, 0

    for name, stat, cycle, item, desc in SERIES:
        logger.info("[ECOS] %s (%s)", name, desc)
        df = fetch_series(key, name, stat, cycle, item)
        if df.empty:
            skip += 1
            continue
        save_csv(df, name)
        logger.info(" -> %d rows, %s ~ %s", len(df), df.index[0].date(), df.index[-1].date())
        ok += 1
        time.sleep(0.3)  # ECOS rate limit 준수

    logger.info("=== 완료: 성공 %d / 실패·스킵 %d ===", ok, skip)


if __name__ == "__main__":
    run()
