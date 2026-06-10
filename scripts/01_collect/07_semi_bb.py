"""
07_semi_bb.py — SEMI 반도체 장비 Book-to-Bill (B/B) 비율 수집

SEMI.org에서 매월 발표하는 북미 반도체 장비 수주/출하 비율.
  B/B > 1.0 → 수주 > 출하 → 장비 투자 확대 국면 (삼성/SK 선행 12~18개월)
  B/B < 1.0 → 수주 < 출하 → 장비 투자 위축 국면

저장 경로: data/raw/macro/macro_indices/SEMI_BB.csv
컬럼: date (YYYY-MM-DD), billings_3ma (3개월 평균 출하, M$), bookings_3ma (수주), bb_ratio
"""

import json
import logging
import os
import re
import subprocess
import datetime

import requests
import pandas as pd

logger = logging.getLogger(__name__)

BASE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "macro", "macro_indices"
)
OUTPUT = os.path.join(BASE_DIR, "SEMI_BB.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# ─────────────────────────────────────────────────────────────────
# 1. Puppeteer 기반 스크래핑 (JS 렌더링 필요한 사이트 대응)
# ─────────────────────────────────────────────────────────────────

def _scrape_via_puppeteer() -> dict | None:
    """07_semi_bb_browser.js를 Node.js로 실행해 B/B 비율 수집."""
    browser_script = os.path.join(os.path.dirname(__file__), "07_semi_bb_browser.js")
    if not os.path.exists(browser_script):
        return None

    for node_cmd in ("node", "node.exe"):
        try:
            result = subprocess.run(
                [node_cmd, browser_script],
                capture_output=True, text=True, timeout=90,
                cwd=os.path.dirname(__file__),
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if data.get("success") and data.get("bb_ratio"):
                    logger.info("[SEMI] Puppeteer 수집 성공 (%s): B/B=%.3f",
                                data.get("source"), data["bb_ratio"])
                    return data
                else:
                    logger.warning("[SEMI] Puppeteer: %s", data.get("error", "unknown"))
            break
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            logger.warning("[SEMI] Puppeteer 타임아웃")
            break
        except Exception as e:
            logger.warning("[SEMI] Puppeteer 실행 오류: %s", e)
            break
    return None


# ─────────────────────────────────────────────────────────────────
# 2. HTTP 기반 스크래핑 (fallback)
# ─────────────────────────────────────────────────────────────────

def _parse_bb_from_text(text: str) -> dict | None:
    """
    SEMI 보도자료 텍스트에서 B/B 비율과 출하·수주 금액 추출.
    예: "book-to-bill ratio of 1.05"  /  "billings: $3.52 billion"
    """
    bb = re.search(r"book.to.bill\s*(?:ratio\s*(?:was|of|:)?\s*)?([\d]+\.[\d]+)", text, re.I)
    bill = re.search(r"billed?\w*\s*(?:of|:)?\s*\$?([\d,]+\.?\d*)\s*(billion|million)", text, re.I)
    book = re.search(r"booked?\w*\s*(?:of|:)?\s*\$?([\d,]+\.?\d*)\s*(billion|million)", text, re.I)

    if not bb:
        return None

    def _to_m(val_str, unit):
        v = float(val_str.replace(",", ""))
        return round(v * 1000 if unit.lower() == "billion" else v, 1)

    return {
        "bb_ratio":     round(float(bb.group(1)), 3),
        "billings_3ma": _to_m(*bill.group(1, 2)) if bill else None,
        "bookings_3ma": _to_m(*book.group(1, 2)) if book else None,
    }


def _infer_report_date(text: str) -> str | None:
    """보도자료 제목/본문에서 기준 월 추출 → YYYY-MM-01 반환."""
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    m = re.search(
        r"(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\s+(\d{4})",
        text, re.I
    )
    if m:
        mon = months[m.group(1).lower()]
        yr  = int(m.group(2))
        return f"{yr}-{mon:02d}-01"
    return None


def _scrape_semi_latest() -> dict | None:
    """SEMI.org 보도자료 목록에서 최신 B/B 보고서를 찾아 파싱."""
    listing_url = (
        "https://www.semi.org/en/products-services/market-data/semi-billings"
    )
    try:
        r = requests.get(listing_url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        # 보도자료 링크 탐색 (URL 패턴으로 필터)
        links = re.findall(
            r'href="(/en/news-media-press-releases/semi-press-releases/[^"]*billings[^"]*)"',
            r.text, re.I
        )
        if not links:
            # 대안: 페이지 내 "book-to-bill" 직접 파싱
            parsed = _parse_bb_from_text(r.text)
            if parsed:
                date = _infer_report_date(r.text) or datetime.date.today().strftime("%Y-%m-01")
                return {"date": date, **parsed}
            return None

        pr_url = "https://www.semi.org" + links[0]
        pr = requests.get(pr_url, headers=HEADERS, timeout=20)
        pr.raise_for_status()

        parsed = _parse_bb_from_text(pr.text)
        if not parsed:
            return None

        date = _infer_report_date(pr.text) or _infer_report_date(pr_url)
        if not date:
            date = datetime.date.today().strftime("%Y-%m-01")
        return {"date": date, **parsed}

    except Exception as e:
        logger.warning("[SEMI] 스크래핑 실패: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────
# 2. 이력 CSV 관리
# ─────────────────────────────────────────────────────────────────

def _load_history() -> pd.DataFrame:
    if os.path.exists(OUTPUT):
        try:
            df = pd.read_csv(OUTPUT, index_col=0, parse_dates=True)
            df.index.name = "date"
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["billings_3ma", "bookings_3ma", "bb_ratio"])


def _save_history(df: pd.DataFrame):
    df.sort_index(inplace=True)
    df.to_csv(OUTPUT)


def _append_record(record: dict) -> bool:
    """새 레코드가 기존에 없을 때만 추가. 추가 시 True 반환."""
    hist = _load_history()
    date = pd.to_datetime(record["date"])
    if date in hist.index:
        return False
    row = pd.DataFrame(
        [{k: v for k, v in record.items() if k != "date"}],
        index=pd.DatetimeIndex([date], name="date"),
    )
    _save_history(pd.concat([hist, row]))
    return True


# ─────────────────────────────────────────────────────────────────
# 3. 진입점
# ─────────────────────────────────────────────────────────────────

def run():
    logger.info("=== 07. SEMI B/B 비율 수집 시작 ===")
    os.makedirs(BASE_DIR, exist_ok=True)

    # Puppeteer 우선, HTTP fallback 순서로 시도
    record = _scrape_via_puppeteer() or _scrape_semi_latest()
    if record:
        added = _append_record(record)
        if added:
            logger.info(
                " - SEMI B/B 신규 저장: %s → B/B=%.3f, 출하=$%.0fM, 수주=$%.0fM",
                record["date"],
                record["bb_ratio"],
                record.get("billings_3ma") or 0,
                record.get("bookings_3ma") or 0,
            )
        else:
            logger.info(" - SEMI B/B 이미 최신 (%s)", record["date"])
    else:
        logger.warning(
            " - SEMI B/B 자동 수집 실패 — 수동 업데이트 필요\n"
            "   https://www.semi.org/en/products-services/market-data/semi-billings\n"
            "   → %s 에 {date, billings_3ma, bookings_3ma, bb_ratio} 행 추가",
            OUTPUT,
        )

    # 이력 요약 로그
    hist = _load_history()
    if not hist.empty and "bb_ratio" in hist.columns:
        latest = hist["bb_ratio"].dropna()
        if not latest.empty:
            logger.info(
                " - SEMI B/B 이력: %d rows / 최신=%.3f / 평균=%.3f",
                len(latest), latest.iloc[-1], latest.mean(),
            )

    logger.info("=== 07. SEMI B/B 비율 수집 완료 ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
