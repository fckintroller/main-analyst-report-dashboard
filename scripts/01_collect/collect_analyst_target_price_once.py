"""
Naver Finance coinfo 페이지에서 종목별 애널리스트 컨센서스 목표주가/투자의견 수집.
출력: data/raw/valuation/analyst_target_price.csv
"""
import logging
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = PROJECT_ROOT / "data" / "raw" / "valuation" / "analyst_target_price.csv"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "config" / "sector_map.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REQUEST_DELAY = 0.3
MAX_RETRIES = 3
TIMEOUT = 8


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    return s


def _load_universe() -> list[str]:
    if SECTOR_MAP_PATH.exists():
        df = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
        return df.iloc[:, 0].astype(str).str.zfill(6).unique().tolist()
    # 폴백: forward_per_snapshot에서 ticker 목록 사용
    snap = PROJECT_ROOT / "data" / "raw" / "factors" / "forward_per_snapshot.csv"
    if snap.exists():
        df = pd.read_csv(snap, encoding="utf-8-sig")
        return df["ticker"].astype(str).str.zfill(6).unique().tolist()
    return []


def fetch_one(ticker: str, session: requests.Session) -> dict | None:
    url = f"https://finance.naver.com/item/coinfo.naver?code={ticker}&target=price"
    for attempt in range(MAX_RETRIES):
        try:
            res = session.get(url, timeout=TIMEOUT)
            if res.status_code != 200:
                return None
            text = res.content.decode("euc-kr", errors="replace")
            soup = BeautifulSoup(text, "lxml")

            # 목표주가 블록: th에 "목표주가" 포함된 행
            target_price = None
            opinion_score = None
            opinion_text = None

            for th in soup.find_all("th"):
                if "목표주가" in (th.get_text() or ""):
                    td = th.find_next_sibling("td")
                    if td is None:
                        break
                    ems = td.find_all("em")
                    # 첫 번째 em: 투자의견 숫자, 그 다음 텍스트: 매수/중립 등
                    # 두 번째 em: 목표주가 숫자
                    for em in ems:
                        raw = em.get_text(strip=True).replace(",", "")
                        if re.fullmatch(r"\d+(\.\d+)?", raw):
                            val = float(raw)
                            if val < 10:  # 투자의견 점수 (1~5)
                                opinion_score = val
                                span = em.parent if em.parent else em
                                opinion_text = span.get_text(strip=True).replace(str(em.get_text(strip=True)), "").strip() or None
                            else:  # 목표주가 (수백~수백만)
                                target_price = val
                    break

            if target_price is None and opinion_score is None:
                return None

            return {
                "ticker": ticker,
                "target_price": target_price,
                "opinion_score": opinion_score,
                "opinion_text": opinion_text,
            }

        except requests.RequestException:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            continue
    return None


def collect(tickers: list[str]) -> pd.DataFrame:
    session = _make_session()
    rows = []
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        result = fetch_one(ticker, session)
        if result:
            rows.append(result)
        time.sleep(REQUEST_DELAY)
        if i % 100 == 0:
            logger.info("  %d/%d 완료 (수집: %d건)", i, total, len(rows))
    logger.info("수집 완료: %d/%d 종목", len(rows), total)
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["ticker", "target_price", "opinion_score", "opinion_text"])


def run():
    universe = _load_universe()
    if not universe:
        logger.error("종목 목록을 불러올 수 없습니다.")
        return
    logger.info("목표주가 수집 시작: %d 종목", len(universe))
    df = collect(universe)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    logger.info("저장 완료: %s (%d행)", OUT_PATH, len(df))


if __name__ == "__main__":
    run()
