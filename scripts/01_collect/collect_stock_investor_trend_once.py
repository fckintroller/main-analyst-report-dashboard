"""
종목별 외국인/기관 순매매 거래량 historical 수집 (1회성, Naver Finance 스크래핑).

배경:
- pykrx의 투자자별 순매수 API(get_market_net_purchases_of_equities_by_ticker 등)는
  KRX_ID/KRX_PW 로그인이 필요하나 .env에 비어 있어 사용 불가 (06_stock_detail.py의
  fetch_net_purchase도 동일한 이유로 net_purchase.csv를 만들어내지 못한 상태).
- 로그인 없이 종목별 일별 외국인/기관 순매매거래량 historical을 제공하는
  Naver Finance 종목 수급 페이지(frgn.naver)를 페이지네이션으로 수집한다.

소스:
- https://finance.naver.com/item/frgn.naver?code={ticker}&page={n}

저장 경로:
- data/raw/stock_detail/{ticker}/investor_trend.csv
  컬럼: date, close, volume, inst_net_volume(기관 순매매량), foreign_net_volume(외국인 순매매량),
        foreign_shares(외국인 보유주수), foreign_ratio_pct(외국인 보유율 %)

실행:
    python scripts/01_collect/collect_stock_investor_trend_once.py
    python scripts/01_collect/collect_stock_investor_trend_once.py --tickers 005930,000660
    python scripts/01_collect/collect_stock_investor_trend_once.py --lookback-months 12 --max-pages 40

주의:
- requests.Session() + User-Agent 헤더 사용, 페이지 요청 간 딜레이를 둔다 (차단 방지).
- 네트워크 실패는 최소 3회 재시도 + 지수 백오프 후 error.log에 기록하고 다음 종목으로 진행한다
  (파이프라인 전체를 중단하지 않는다).
- 이미 investor_trend.csv가 있는 종목은 기본적으로 건너뛴다 (--overwrite로 강제 재수집).
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STOCK_DETAIL_DIR = PROJECT_ROOT / "data" / "raw" / "stock_detail"
ERROR_LOG_PATH = PROJECT_ROOT / "error.log"

REQUEST_TIMEOUT = 15
PAGE_DELAY = 0.25            # 페이지 요청 간 딜레이 (초) — 차단 방지
RETRY_ATTEMPTS = 3           # 최소 3회 재시도
RETRY_BASE_DELAY = 2.0       # 지수 백오프 기준 (2s, 4s, 8s ...)
DEFAULT_LOOKBACK_MONTHS = 12
DEFAULT_MAX_PAGES = 40       # 페이지당 약 10개 영업일 → 40페이지 ≈ 약 18~19개월 상한

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

COLUMN_MAP = {
    "날짜_날짜": "date",
    "종가_종가": "close",
    "거래량_거래량": "volume",
    "기관_순매매량": "inst_net_volume",
    "외국인_순매매량": "foreign_net_volume",
    "외국인_보유주수": "foreign_shares",
    "외국인_보유율": "foreign_ratio_pct",
}
OUTPUT_COLUMNS = ["date", "close", "volume", "inst_net_volume", "foreign_net_volume", "foreign_shares", "foreign_ratio_pct"]
REQUIRED_FLAT_COLUMNS = {"날짜_날짜", "외국인_순매매량"}


def find_history_table(tables: list[pd.DataFrame]) -> pd.DataFrame | None:
    """페이지 내 여러 테이블 중 날짜·외국인 순매매 이력 테이블을 컬럼 구조로 찾아낸다.

    Naver 페이지 레이아웃은 종목 종류(우선주 등)에 따라 테이블 순서가 달라지므로
    고정 인덱스(tables[3]) 대신 기대하는 컬럼 조합으로 식별한다.
    """
    for table in tables:
        if not isinstance(table.columns, pd.MultiIndex):
            continue
        flat_cols = {"_".join(str(part) for part in col) for col in table.columns}
        if REQUIRED_FLAT_COLUMNS.issubset(flat_cols):
            return table
    return None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_error_handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [investor_trend] %(message)s"))
logger.addHandler(_error_handler)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def discover_tickers() -> list[str]:
    tickers = []
    for child in sorted(STOCK_DETAIL_DIR.iterdir()):
        if child.is_dir() and (child / "ohlcv.csv").exists():
            tickers.append(child.name)
    return tickers


def fetch_page(session: requests.Session, ticker: str, page: int) -> pd.DataFrame | None:
    """Naver 종목 수급 페이지 1개를 받아 정제된 DataFrame으로 반환한다.

    네트워크/파싱 오류는 최소 RETRY_ATTEMPTS회 재시도(지수 백오프) 후
    None을 반환하며, 마지막 오류는 error.log에 남긴다.
    """
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page={page}"
    last_error: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            res = session.get(url, timeout=REQUEST_TIMEOUT)
            res.raise_for_status()
            res.encoding = "euc-kr"
            tables = pd.read_html(StringIO(res.text))
            found = find_history_table(tables)
            if found is None:
                # 이 종목/페이지에는 외국인·기관 수급 이력 테이블이 없음 (우선주 등 레이아웃 차이 또는 이력 종료)
                return pd.DataFrame(columns=OUTPUT_COLUMNS)
            raw = found.copy()
            raw.columns = ["_".join(str(part) for part in col) for col in raw.columns]
            raw = raw.dropna(how="all")
            raw = raw.rename(columns=COLUMN_MAP)
            raw = raw[raw["date"].notna()].copy()
            if raw.empty:
                return raw
            raw["date"] = pd.to_datetime(raw["date"], format="%Y.%m.%d", errors="coerce")
            raw = raw.dropna(subset=["date"])
            for col in ["close", "volume", "inst_net_volume", "foreign_net_volume", "foreign_shares"]:
                raw[col] = pd.to_numeric(raw[col], errors="coerce")
            raw["foreign_ratio_pct"] = (
                raw["foreign_ratio_pct"].astype(str).str.replace("%", "", regex=False).pipe(pd.to_numeric, errors="coerce")
            )
            return raw[OUTPUT_COLUMNS]
        except Exception as exc:  # noqa: BLE001 - 페이지 단위 오류는 재시도/스킵 대상
            last_error = exc
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
    logger.error("[%s] page %s 수집 실패 (최대 %s회 재시도): %s", ticker, page, RETRY_ATTEMPTS, last_error)
    return None


def fetch_ticker_history(
    session: requests.Session,
    ticker: str,
    start_date: pd.Timestamp,
    max_pages: int,
) -> pd.DataFrame:
    pages = []
    for page in range(1, max_pages + 1):
        df = fetch_page(session, ticker, page)
        if df is None:
            # 해당 페이지는 재시도 후에도 실패 → 스킵하고 다음 페이지 계속 (파이프라인 중단 금지)
            time.sleep(PAGE_DELAY)
            continue
        if df.empty:
            break
        pages.append(df)
        if df["date"].min() <= start_date:
            break
        time.sleep(PAGE_DELAY)

    if not pages:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    out = pd.concat(pages, ignore_index=True)
    out = out.drop_duplicates(subset=["date"]).sort_values("date")
    out = out[out["date"] >= start_date].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.reset_index(drop=True)


def save_ticker_history(ticker: str, history: pd.DataFrame) -> bool:
    if history.empty:
        return False
    out_path = STOCK_DETAIL_DIR / ticker / "investor_trend.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(out_path, index=False, encoding="utf-8-sig")
    return True


def run(tickers: list[str], lookback_months: int, max_pages: int, overwrite: bool) -> dict[str, int]:
    session = build_session()
    start_date = pd.Timestamp(datetime.today() - timedelta(days=30 * lookback_months))

    collected, skipped, failed = 0, 0, 0
    for i, ticker in enumerate(tickers, start=1):
        out_path = STOCK_DETAIL_DIR / ticker / "investor_trend.csv"
        if out_path.exists() and not overwrite:
            skipped += 1
            continue
        try:
            history = fetch_ticker_history(session, ticker, start_date, max_pages)
            if save_ticker_history(ticker, history):
                collected += 1
                logger.info("[%s/%s] %s: %s행 저장 (%s ~ %s)", i, len(tickers), ticker, len(history),
                            history["date"].min(), history["date"].max())
            else:
                failed += 1
                logger.error("[%s] 수집 결과가 비어 있어 저장하지 않음", ticker)
        except Exception as exc:  # noqa: BLE001 - 종목 단위 오류는 기록 후 다음 종목으로 (파이프라인 중단 금지)
            failed += 1
            logger.error("[%s] 종목 수집 실패: %s", ticker, exc)

    return {"collected": collected, "skipped": skipped, "failed": failed, "total": len(tickers)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="종목별 외국인/기관 순매매 historical 수집 (Naver Finance)")
    parser.add_argument("--tickers", type=str, default=None, help="콤마로 구분된 종목코드 목록 (미지정 시 stock_detail 전체)")
    parser.add_argument("--lookback-months", type=int, default=DEFAULT_LOOKBACK_MONTHS)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--overwrite", action="store_true", help="기존 investor_trend.csv가 있어도 재수집")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else discover_tickers()
    logger.info("[INVESTOR TREND] 대상 %s종목, lookback=%s개월, max_pages=%s", len(tickers), args.lookback_months, args.max_pages)
    result = run(tickers, args.lookback_months, args.max_pages, args.overwrite)
    logger.info("[INVESTOR TREND] 완료: %s", result)
    print(result)


if __name__ == "__main__":
    main()
