"""
매크로 발표 지표 historical 실제치(actual) 수집 — "캘린더 서프라이즈" 팩터용 (1회성).

배경 (중요, 데이터 한계):
- data/economic_calendar.json (ForexFactory 피드 기반)에는 forecast/previous는 있으나
  "actual"(발표 실제치) 필드가 원천적으로 존재하지 않는다 (이번 주 일정 피드라 발표 전).
- ForexFactory의 과거 캘린더(actual·forecast 동시 제공)는 비공개 API/유료이거나
  웹페이지 스크래핑이 필요해 약관·안정성 문제가 있다.
- 따라서 "컨센서스(forecast) 대비 서프라이즈"는 무료 소스로 계산 불가능하다.
  (절대 임의로 forecast 값을 추정/보간하지 않는다)

대안 (이 스크립트의 실제 수집 대상):
- FRED(이미 FRED_API_KEY 설정됨)에서 동일 주제의 매크로 지표 "실제 발표치" 시계열을
  수집한다. 이를 바탕으로 "발표치가 직전 대비/자기 과거 추세 대비 얼마나 이례적으로
  변했는가"를 계산하는 "발표치 추세-이탈(actual-vs-own-history shift) 팩터"를 만든다.
  → 이는 컨센서스 대비 서프라이즈가 아니라 "발표 자체의 변화가 이례적인 정도"이며,
    build_calendar_macro_surprise_factors.py에서 그 차이를 명확히 문서화한다.

수집 시리즈 (economic_calendar.json의 고빈도 항목과 매칭):
- PAYEMS  (비농업 고용지수, Total Nonfarm Payrolls)
- CPIAUCSL(소비자물가지수, CPI)
- FEDFUNDS(기준금리, Federal Funds Effective Rate)
- UNRATE  (실업률, Unemployment Rate)
- ICSA    (신규 실업수당 청구건수, Initial Claims)

저장 경로:
- data/raw/macro/release_history/{series_id}.csv  (date, value)

실행:
    python scripts/01_collect/collect_macro_release_history_once.py
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "macro" / "release_history"
ERROR_LOG_PATH = PROJECT_ROOT / "error.log"
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 3.0
LOOKBACK_YEARS = 15

SERIES = {
    "PAYEMS": {"name_kr": "비농업 고용지수(전체 비농업 고용자수)", "calendar_match": "비농업 고용지수", "frequency": "monthly", "unit": "Thousands of Persons"},
    "CPIAUCSL": {"name_kr": "소비자물가지수(CPI, 전체 도시 소비자)", "calendar_match": "소비자물가지수", "frequency": "monthly", "unit": "Index 1982-1984=100"},
    "FEDFUNDS": {"name_kr": "연방기금 실효금리", "calendar_match": "기준금리 결정", "frequency": "monthly", "unit": "Percent"},
    "UNRATE": {"name_kr": "실업률", "calendar_match": "실업률", "frequency": "monthly", "unit": "Percent"},
    "ICSA": {"name_kr": "신규 실업수당 청구건수", "calendar_match": "신규 실업수당 청구건수", "frequency": "weekly", "unit": "Number"},
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_error_handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [macro_release_history] %(message)s"))
logger.addHandler(_error_handler)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    return session


def fetch_series(session: requests.Session, series_id: str, api_key: str) -> pd.DataFrame | None:
    cutoff = pd.Timestamp.today() - pd.DateOffset(years=LOOKBACK_YEARS)
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": cutoff.strftime("%Y-%m-%d"),
    }
    last_error: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            res = session.get(FRED_API_URL, params=params, timeout=30)
            res.raise_for_status()
            payload = res.json()
            obs = payload.get("observations", [])
            if not obs:
                raise RuntimeError("observations 응답이 비어 있음")
            df = pd.DataFrame(obs)[["date", "value"]]
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")  # FRED 결측치는 "." 문자열 → NaN
            df = df.dropna(subset=["date"])
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            return df[["date", "value"]].reset_index(drop=True)
        except Exception as exc:  # noqa: BLE001 - 시리즈 단위 오류는 재시도/스킵 대상
            last_error = exc
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
    logger.error("[%s] FRED 시리즈 수집 실패 (최대 %s회 재시도): %s", series_id, RETRY_ATTEMPTS, last_error)
    return None


def run(api_key: str) -> dict[str, int]:
    session = build_session()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    collected, failed = 0, 0
    for series_id, meta in SERIES.items():
        df = fetch_series(session, series_id, api_key)
        if df is None or df.empty:
            failed += 1
            continue
        out_path = OUTPUT_DIR / f"{series_id}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        collected += 1
        logger.info("[%s] %s: %s행 저장 (%s ~ %s)", series_id, meta["name_kr"], len(df), df["date"].min(), df["date"].max())
        time.sleep(0.5)
    return {"collected": collected, "failed": failed, "total": len(SERIES)}


def main() -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.error("[MACRO RELEASE HISTORY] FRED_API_KEY 환경변수가 없어 수집을 건너뜁니다.")
        print({"collected": 0, "failed": len(SERIES), "total": len(SERIES), "error": "FRED_API_KEY missing"})
        return
    logger.info("[MACRO RELEASE HISTORY] FRED %s개 시리즈 수집 시작 (lookback=%s년)", len(SERIES), LOOKBACK_YEARS)
    result = run(api_key)
    logger.info("[MACRO RELEASE HISTORY] 완료: %s", result)
    print(result)


if __name__ == "__main__":
    main()
