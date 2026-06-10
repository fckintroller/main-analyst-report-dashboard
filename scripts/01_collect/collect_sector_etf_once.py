"""
섹터별 대표 ETF 역사 시계열 1회 수집.
- 소스: pykrx (KRX 직접)
- 기간: 2019-01-01 ~ 오늘 (NAVER DataLab 기간보다 여유있게)
- 저장: data/raw/sector_etf/{ticker}_{name}.csv
- 실행: python scripts/01_collect/collect_sector_etf_once.py

선정 기준: 섹터 대표성 > 순자산 규모 > 상장 기간(2021 이전 우선)
"""
import logging
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("KRX_ID", os.getenv("KRX_ID", ""))
os.environ.setdefault("KRX_PW", os.getenv("KRX_PW", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAVE_DIR = PROJECT_ROOT / "data" / "raw" / "sector_etf"
START = "20190101"

# ── 섹터 ETF 마스터 ──────────────────────────────────────────────────
# (ticker, 섹터명, ETF명, 상장연도_추정)
# 한국 직접 투자 가능 섹터 중심, 유동성·역사 우선 선정
SECTOR_ETFS = [
    # 핵심 산업 (상장 10년 이상, 유동성 최상위)
    ("091160", "semiconductor",      "KODEX 반도체"),
    ("091180", "auto",               "KODEX 자동차"),
    ("091170", "bank",               "KODEX 은행"),
    ("140700", "insurance",          "KODEX 보험"),
    ("117700", "construction",       "KODEX 건설"),
    ("117460", "chemical",           "KODEX 에너지화학"),
    ("139240", "steel",              "TIGER 200 철강소재"),
    ("157500", "securities",         "TIGER 증권"),
    # 성장 섹터 (2018~2021 상장)
    ("244580", "bio_pharma",         "KODEX 바이오"),
    ("305540", "battery",            "KODEX 2차전지산업"),
    ("300640", "game",               "RISE 게임테마"),
    ("326240", "it_software",        "RISE IT플러스"),
    # 신흥 테마 (2022~2023 상장, 일부 역사 짧음)
    ("463250", "defense",            "TIGER K방산&우주"),
    ("441540", "shipbuilding",       "HANARO Fn조선해운"),
    ("466940", "nuclear",            "KODEX 원자력"),
    ("139250", "energy_chemical",    "TIGER 200 에너지화학"),
    ("479850", "cosmetics",          "HANARO K-뷰티"),
    # 인프라·유틸
    ("140710", "reit_realestate",    "TIGER 200 철강소재"),  # 리츠ETF 대체
    ("102970", "securities2",        "KODEX 증권"),
]


def collect_etf(ticker: str, sector: str, etf_name: str) -> pd.DataFrame | None:
    from pykrx import stock as pykrx_stock

    for attempt in range(3):
        try:
            df = pykrx_stock.get_etf_ohlcv_by_date(START, pd.Timestamp.today().strftime("%Y%m%d"), ticker)
            if df is not None and not df.empty:
                return df
            logger.warning(" - %s(%s) 데이터 없음", etf_name, ticker)
            return None
        except Exception as e:
            logger.warning(" - %s 시도 %d 실패: %s", ticker, attempt + 1, e)
            time.sleep(2 ** attempt)
    return None


def run():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    ok, skip = 0, 0

    for ticker, sector, etf_name in SECTOR_ETFS:
        logger.info("[ETF] %s → %s (%s)", sector, etf_name, ticker)
        df = collect_etf(ticker, sector, etf_name)
        if df is None or df.empty:
            skip += 1
            continue

        path = SAVE_DIR / f"{sector}_{ticker}.csv"
        df.index.name = "date"
        df.to_csv(path)
        logger.info("  → %d행  %s ~ %s", len(df),
                    df.index[0].strftime("%Y-%m-%d"),
                    df.index[-1].strftime("%Y-%m-%d"))
        ok += 1
        time.sleep(0.5)

    logger.info("=== 완료: 성공 %d / 스킵 %d ===", ok, skip)


if __name__ == "__main__":
    run()
