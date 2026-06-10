"""
DART 연간 재무제표 수집 (Piotroski F-Score 원천 데이터).

최신 사업보고서(reprt_code=11011) → finstate_all 호출
→ BS / IS / CF 3개 재무제표 핵심 계정과목 추출
→ data/raw/valuation/dart_finstate/finstate_all.csv 저장

출력 컬럼:
  ticker, corp_code, bsns_year, fs_div,
  sj_div, account_nm, thstrm_amount, frmtrm_amount, bfefrmtrm_amount

실행:
    python scripts/01_collect/collect_dart_finstate_once.py
    python scripts/01_collect/collect_dart_finstate_once.py --tickers 005930,000660
"""
import argparse
import logging
import os
import time
from pathlib import Path

import OpenDartReader
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

OUT_PATH = PROJECT_ROOT / "data" / "raw" / "valuation" / "dart_finstate" / "finstate_all.csv"
DB_PATH  = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

RETRY      = 3
DELAY      = 0.4   # 종목 간 딜레이(초)
SAVE_EVERY = 30    # 중간 저장 빈도

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# 추출 대상 계정과목 키워드 매핑
# (sj_div, keywords) → 계정 식별자
ACCOUNT_MAP: list[tuple[str, str, list[str]]] = [
    # --- 재무상태표 (BS) ---
    ("BS", "total_assets",        ["자산총계"]),
    ("BS", "current_assets",      ["유동자산"]),
    ("BS", "current_liabilities", ["유동부채"]),
    ("BS", "noncurrent_liabilities", ["비유동부채"]),
    ("BS", "total_equity",        ["자본총계", "자본합계"]),
    ("BS", "capital_stock",       ["자본금"]),
    # --- 손익계산서 (IS) ---
    ("IS", "revenue",             ["수익(매출액)", "매출액", "영업수익"]),
    ("IS", "gross_profit",        ["매출총이익", "매출총손익"]),
    ("IS", "operating_income",    ["영업이익", "영업손익"]),
    ("IS", "net_income",          ["당기순이익", "당기순손익", "분기순이익"]),
    # --- 현금흐름표 (CF) ---
    ("CF", "cfo",                 ["영업활동현금흐름", "영업활동으로인한현금흐름",
                                   "영업활동으로 인한 현금흐름"]),
]


def _to_num(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(str(val).replace(",", ""))
    except Exception:
        return None


def _extract_account(df: pd.DataFrame, sj_div: str, keywords: list[str],
                     col: str) -> float | None:
    # finstate_all은 IS 대신 CIS(포괄손익계산서)를 반환하므로 둘 다 검색
    divs = [sj_div, "CIS"] if sj_div == "IS" else [sj_div]
    sub = df[df["sj_div"].isin(divs)]
    for kw in keywords:
        match = sub[sub["account_nm"].str.contains(kw, na=False, regex=False)]
        if len(match) > 0:
            return _to_num(match.iloc[0][col])
    return None


def _fetch_one(dart: "OpenDartReader", ticker: str,
               years: list[int]) -> list[dict]:
    """한 종목의 재무제표를 수집. 가장 최신 가용 연도 사용."""
    corp_code = dart.find_corp_code(ticker)
    if not corp_code:
        return []

    raw_df = None
    used_year = None
    for year in years:
        for attempt in range(RETRY):
            try:
                df = dart.finstate_all(ticker, year, reprt_code="11011", fs_div="CFS")
                if df is not None and not df.empty:
                    raw_df = df
                    used_year = year
                    break
            except Exception as e:
                if attempt < RETRY - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.debug("  %s %d 수집 실패: %s", ticker, year, e)
        if raw_df is not None:
            break

    # CFS 없으면 OFS 시도
    if raw_df is None:
        for year in years:
            try:
                df = dart.finstate_all(ticker, year, reprt_code="11011", fs_div="OFS")
                if df is not None and not df.empty:
                    raw_df = df
                    used_year = year
                    break
            except Exception:
                pass

    if raw_df is None:
        return []

    # 컬럼명 정규화 (대소문자 허용)
    raw_df.columns = [c.lower() for c in raw_df.columns]
    if "sj_div" not in raw_df.columns or "account_nm" not in raw_df.columns:
        return []

    records = []
    for sj_div, acct_id, keywords in ACCOUNT_MAP:
        for col, period in [("thstrm_amount", "current"), ("frmtrm_amount", "prior"),
                            ("bfefrmtrm_amount", "prior2")]:
            val = _extract_account(raw_df, sj_div, keywords, col)
            if val is not None:
                records.append({
                    "ticker":    ticker,
                    "corp_code": corp_code,
                    "bsns_year": used_year,
                    "period":    period,
                    "sj_div":    sj_div,
                    "account_id": acct_id,
                    "amount":    val,
                })
    return records


def _load_universe() -> list[str]:
    import sqlite3
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(
                "SELECT DISTINCT ticker FROM factor_stock_price_momentum_month",
                conn
            )
            return df["ticker"].astype(str).str.zfill(6).tolist()
    except Exception:
        return []


def run(tickers: list[str] | None = None):
    dart = OpenDartReader(os.getenv("DART_API_KEY", ""))
    universe = tickers or _load_universe()
    logger.info("수집 대상: %d종목", len(universe))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    errors = 0
    total = len(universe)

    for i, ticker in enumerate(universe, 1):
        recs = _fetch_one(dart, ticker, years=[2024, 2023])
        if recs:
            all_records.extend(recs)
        else:
            errors += 1
        time.sleep(DELAY)

        if i % SAVE_EVERY == 0 or i == total:
            logger.info("  %d/%d  수집: %d종목, 실패: %d", i, total,
                        len(set(r["ticker"] for r in all_records)), errors)
            if all_records:
                pd.DataFrame(all_records).to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    logger.info("완료: %s (%d행)", OUT_PATH.name, len(all_records))
    return pd.DataFrame(all_records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str, default=None,
                        help="쉼표 구분 종목코드 (e.g. 005930,000660)")
    args = parser.parse_args()
    tickers = [t.strip().zfill(6) for t in args.tickers.split(",")] if args.tickers else None
    run(tickers)
