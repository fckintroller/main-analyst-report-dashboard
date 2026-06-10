"""
종목별 DART 공시 이벤트 historical 수집 (1회성).

배경:
- 04_valuation.py의 fetch_dart_filings()는 "오늘 하루"만 수집하는 스냅샷이라
  (valuation_dart_all_filings 테이블 709행, rcept_dt 전부 동일 날짜) 이벤트 빈도/추세
  팩터를 만들 수 없다.
- OpenDartReader.list(corp=종목코드, start=, end=)는 종목 단위로 최대 약 1년 범위의
  공시 이력을 반환한다 (확인됨: 005930 1년치 2,620건).

소스:
- DART 공시검색 API (OpenDartReader), 인증: .env의 DART_API_KEY (정본 1개만 사용)

저장 경로:
- data/raw/valuation/dart_events/{ticker}.csv
  (자사주/배당/임원·주요주주 지분변동 등 이벤트성 공시만 필터링하여 저장)

실행:
    python scripts/01_collect/collect_dart_event_history_once.py
    python scripts/01_collect/collect_dart_event_history_once.py --tickers 005930,000660 --lookback-months 12

주의:
- 종목 단위 호출 실패는 최소 3회 재시도(지수 백오프) 후 error.log에 기록하고
  다음 종목으로 진행한다 (파이프라인 중단 금지).
- 이미 결과 파일이 있는 종목은 기본적으로 건너뛴다 (--overwrite로 강제 재수집).
"""
from __future__ import annotations

import argparse
import logging
import queue
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

STOCK_DETAIL_DIR = PROJECT_ROOT / "data" / "raw" / "stock_detail"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "valuation" / "dart_events"
ERROR_LOG_PATH = PROJECT_ROOT / "error.log"

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 3.0
TICKER_DELAY = 0.3
CALL_TIMEOUT_SECONDS = 30  # OpenDartReader 내부 HTTP 호출에 타임아웃이 없어 행(hang) 방지용으로 직접 제한
DEFAULT_LOOKBACK_MONTHS = 12


def _call_with_timeout(func, *args, timeout=CALL_TIMEOUT_SECONDS, **kwargs):
    """OpenDartReader 호출이 응답 없이 멈추는 것을 막기 위한 데몬 스레드 기반 타임아웃 래퍼.

    타임아웃 시 호출 스레드는 강제 종료할 수 없으므로 daemon=True로 버려두고
    (프로세스 종료 시 정리됨) 다음 종목으로 진행한다 — 매번 새 스레드를 쓰므로
    한 종목이 행(hang)되어도 이후 종목 수집을 막지 않는다.
    """
    result_queue: "queue.Queue" = queue.Queue(maxsize=1)

    def _target():
        try:
            result_queue.put(("ok", func(*args, **kwargs)))
        except Exception as exc:  # noqa: BLE001 - 호출 스레드의 예외를 호출자 스레드로 전달
            result_queue.put(("error", exc))

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    try:
        status, payload = result_queue.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError(f"{timeout}초 내 응답 없음 (행 가능성, 스레드는 백그라운드에 방치)") from exc
    if status == "error":
        raise payload
    return payload

# report_nm 필터: 자사주(취득/처분), 배당 결정, 임원·주요주주 지분 변동
EVENT_PATTERNS = {
    "buyback": r"자기주식|자사주",
    "dividend": r"배당",
    "insider": r"소유상황보고|임원ㆍ주요주주|최대주주|주식등의대량보유",
}
EVENT_REGEX = "|".join(EVENT_PATTERNS.values())

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_error_handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [dart_event_history] %(message)s"))
logger.addHandler(_error_handler)


def discover_tickers() -> list[str]:
    tickers = []
    for child in sorted(STOCK_DETAIL_DIR.iterdir()):
        if child.is_dir() and (child / "ohlcv.csv").exists():
            tickers.append(child.name)
    return tickers


def classify_event(report_nm: str) -> str:
    for label, pattern in EVENT_PATTERNS.items():
        if pd.notna(report_nm) and pd.Series([report_nm]).str.contains(pattern, regex=True).iloc[0]:
            return label
    return "other"


def fetch_ticker_events(dart, ticker: str, start: str, end: str) -> pd.DataFrame | None:
    last_error: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            df = _call_with_timeout(dart.list, corp=ticker, start=start, end=end)
            if df is None or df.empty:
                return pd.DataFrame(columns=["rcept_dt", "corp_name", "stock_code", "report_nm", "rcept_no", "event_type"])
            df = df[df["report_nm"].str.contains(EVENT_REGEX, na=False, regex=True)].copy()
            if df.empty:
                return df
            df["event_type"] = df["report_nm"].map(classify_event)
            return df[["rcept_dt", "corp_name", "stock_code", "report_nm", "rcept_no", "event_type"]].reset_index(drop=True)
        except Exception as exc:  # noqa: BLE001 - 종목 단위 오류는 재시도/스킵 대상
            last_error = exc
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
    logger.error("[%s] DART 공시 이력 수집 실패 (최대 %s회 재시도): %s", ticker, RETRY_ATTEMPTS, last_error)
    return None


def run(dart, tickers: list[str], lookback_months: int, overwrite: bool) -> dict[str, int]:
    end = date.today()
    start = end - timedelta(days=30 * lookback_months)
    start_str, end_str = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    collected, skipped, failed, empty = 0, 0, 0, 0
    for i, ticker in enumerate(tickers, start=1):
        out_path = OUTPUT_DIR / f"{ticker}.csv"
        if out_path.exists() and not overwrite:
            skipped += 1
            continue

        df = fetch_ticker_events(dart, ticker, start_str, end_str)
        if df is None:
            failed += 1
            continue
        if df.empty:
            empty += 1
            # 이벤트가 없는 것도 유효한 결과 → 빈 파일로 저장해 "재수집 대상 아님"을 표시
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            logger.info("[%s/%s] %s: 이벤트 없음 (0건)", i, len(tickers), ticker)
        else:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            collected += 1
            logger.info("[%s/%s] %s: %s건 저장 (%s ~ %s)", i, len(tickers), ticker, len(df),
                        df["rcept_dt"].min(), df["rcept_dt"].max())
        time.sleep(TICKER_DELAY)

    return {"collected": collected, "empty": empty, "skipped": skipped, "failed": failed, "total": len(tickers)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="종목별 DART 공시 이벤트 historical 수집")
    parser.add_argument("--tickers", type=str, default=None, help="콤마로 구분된 종목코드 목록 (미지정 시 stock_detail 전체)")
    parser.add_argument("--lookback-months", type=int, default=DEFAULT_LOOKBACK_MONTHS)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.environ.get("DART_API_KEY")
    if not api_key:
        logger.error("[DART EVENT HISTORY] DART_API_KEY 환경변수가 없어 수집을 건너뜁니다.")
        print({"collected": 0, "empty": 0, "skipped": 0, "failed": 0, "total": 0, "error": "DART_API_KEY missing"})
        return

    import OpenDartReader
    dart = OpenDartReader(api_key)

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else discover_tickers()
    logger.info("[DART EVENT HISTORY] 대상 %s종목, lookback=%s개월", len(tickers), args.lookback_months)
    result = run(dart, tickers, args.lookback_months, args.overwrite)
    logger.info("[DART EVENT HISTORY] 완료: %s", result)
    print(result)


if __name__ == "__main__":
    main()
