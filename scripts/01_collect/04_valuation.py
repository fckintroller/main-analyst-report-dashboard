import os
import logging
import datetime
# from pykrx import stock
import FinanceDataReader as fdr
import OpenDartReader
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

logger = logging.getLogger(__name__)
BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw', 'valuation')

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_latest_business_day():
    today = datetime.datetime.today()
    past_10_days = today - datetime.timedelta(days=10)
    df = fdr.DataReader('KS11', past_10_days, today)
    if not df.empty:
        return df.index[-1].strftime("%Y%m%d")
    return today.strftime("%Y%m%d")

def fetch_fundamentals(date_str):
    logger.info(f"[{date_str}] KOSPI ??붾찘??PER/PBR) ?곗씠???섏쭛 ?쒖옉...")
    try:
        pass # stock.get_market_fundamental(date_str, market="KOSPI")
    except Exception as e:
        logger.error(f" - ??붾찘???섏쭛 ?ㅽ뙣: {e}")

def fetch_dart_filings():
    logger.info("[VALUATION] DART ?꾩옄怨듭떆(二쇱슂 ?대깽?? ?뱀씪 ?곗씠???섏쭛 ?쒖옉...")
    DART_API_KEY = os.environ.get("DART_API_KEY")
    if not DART_API_KEY:
        logger.warning(" - DART_API_KEY ?섍꼍蹂???꾨씫. 怨듭떆 ?섏쭛???ㅽ궢?⑸땲??")
        return

    try:
        dart = OpenDartReader(DART_API_KEY)
        today = datetime.datetime.today().strftime('%Y%m%d')
        df = dart.list(start=today, end=today)

        if df.empty:
            logger.info(" - ?뱀씪 ?묒닔??怨듭떆媛 ?놁뒿?덈떎.")
            return

        df.to_csv(os.path.join(BASE_DIR, 'dart_all_filings.csv'), index=False, encoding='utf-8-sig')

        # 1. 자기주식(자사주) 취득/처분 필터
        df_buyback = df[df['report_nm'].str.contains('자기주식|자사주', na=False, regex=True)]
        if not df_buyback.empty:
            df_buyback.to_csv(os.path.join(BASE_DIR, 'dart_buybacks.csv'), index=False, encoding='utf-8-sig')

        # 2. 배당 결정 필터
        df_dividend = df[df['report_nm'].str.contains('배당', na=False)]
        if not df_dividend.empty:
            df_dividend.to_csv(os.path.join(BASE_DIR, 'dart_dividends.csv'), index=False, encoding='utf-8-sig')

        # 3. 임원/최대주주/주식소유 변동 필터
        df_insider = df[df['report_nm'].str.contains('소유상황보고|임원ㆍ주요주주|최대주주|주식등의대량보유', na=False, regex=True)]
        if not df_insider.empty:
            df_insider.to_csv(os.path.join(BASE_DIR, 'dart_insiders.csv'), index=False, encoding='utf-8-sig')

        logger.info(
            " - DART 주요 이벤트 필터링 완료 (자사주: %d건, 배당: %d건, 지분변동: %d건)",
            len(df_buyback), len(df_dividend), len(df_insider)
        )

    except Exception as e:
        logger.error(f" - DART 怨듭떆 ?섏쭛 ?ㅽ뙣: {e}")

def fetch_adrs():
    logger.info("[VALUATION] ?쒓뎅 ???ADR 二쇨? ?섏쭛 ?쒖옉...")
    KOREAN_ADRS = {
        'Coupang': 'CPNG', 'Posco': 'PKX', 'SKTelecom': 'SKM', 'KT': 'KT',
        'KEPCO': 'KEP', 'LGDisplay': 'LPL', 'KBFinancial': 'KB', 'Shinhan': 'SHG', 'Woori': 'WF'
    }
    adrs_dir = os.path.join(BASE_DIR, 'adrs')
    ensure_dir(adrs_dir)

    for name, ticker in KOREAN_ADRS.items():
        try:
            df = fdr.DataReader(ticker, '2010-01-01')
            if not df.empty:
                df.to_csv(os.path.join(adrs_dir, f"{name}.csv"))
                logger.info(f" - {name} ({ticker}) ?섏쭛 ?꾨즺")
        except Exception as e:
            logger.error(f" - {name} ({ticker}) ?섏쭛 ?ㅽ뙣: {e}")

import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

def fetch_eps_consensus_for_ticker(ticker, session):
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    try:
        res = session.get(url, timeout=5)
        dfs = pd.read_html(res.text, encoding='euc-kr')
        for df in dfs:
            if "?곸뾽?댁씡" in str(df.values):
                # Save the full table to include PER, PBR, EPS, BPS, etc.
                return {'ticker': ticker, 'consensus_raw': df.to_json(force_ascii=False)}
    except Exception:
        pass
    return None

def fetch_all_eps_consensus():
    logger.info("[VALUATION] ??醫낅ぉ(KOSPI/KOSDAQ) ?ㅼ쟻 而⑥꽱?쒖뒪 ?섏쭛 ?쒖옉 (?쒓컙???ㅼ냼 ?뚯슂?⑸땲??...")
    try:
        df_krx = fdr.StockListing('KRX')
        tickers = df_krx['Code'].tolist()
        results = []

        with requests.Session() as session:
            session.headers.update({'User-Agent': 'Mozilla/5.0'})
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(fetch_eps_consensus_for_ticker, t, session) for t in tickers]
                for i, future in enumerate(futures):
                    res = future.result()
                    if res:
                        results.append(res)
                    if i > 0 and i % 500 == 0:
                        logger.info(f" - {i}/{len(tickers)} 醫낅ぉ ?щ·留??꾨즺...")

        if results:
            df_res = pd.DataFrame(results)
            df_res.to_csv(os.path.join(BASE_DIR, 'earnings_consensus.csv'), index=False, encoding='utf-8-sig')
            logger.info(f" - ?ㅼ쟻 而⑥꽱?쒖뒪 ?섏쭛 ?꾨즺: 珥?{len(df_res)} 醫낅ぉ 異붿텧 ?깃났")
    except Exception as e:
        logger.error(f" - ?ㅼ쟻 而⑥꽱?쒖뒪 ?섏쭛 ?ㅽ뙣: {e}")

def fetch_kospi_pbr():
    """pykrx로 KOSPI 전체 PBR/PER/배당수익률 이력 수집 및 분위수 계산 (증분 업데이트)."""
    logger.info("[VALUATION] KOSPI 펀더멘털 이력 수집 중 (pykrx)...")
    hist_path = os.path.join(BASE_DIR, "kospi_fundamental_history.csv")
    pct_path  = os.path.join(BASE_DIR, "kospi_pbr_percentile.csv")

    try:
        from pykrx import stock

        # 증분 업데이트: 기존 파일 마지막 날짜 다음부터만 수집
        if os.path.exists(hist_path):
            existing = pd.read_csv(hist_path, index_col=0, parse_dates=True)
            start = (existing.index[-1] + datetime.timedelta(days=1)).strftime("%Y%m%d")
        else:
            existing = pd.DataFrame()
            start = "20100101"

        today_str = datetime.datetime.today().strftime("%Y%m%d")

        if start > today_str:
            logger.info(" - KOSPI 펀더멘털 이미 최신 상태")
            hist = existing
        else:
            new_df = stock.get_index_fundamental_by_date(start, today_str, "1001")
            if new_df is not None and not new_df.empty:
                hist = pd.concat([existing, new_df]) if not existing.empty else new_df
                hist = hist[~hist.index.duplicated(keep="last")].sort_index()
                hist.to_csv(hist_path)
                logger.info(" - KOSPI 펀더멘털 저장 완료: 총 %d rows (신규 %d)", len(hist), len(new_df))
            else:
                logger.warning(" - pykrx 반환 데이터 없음 (기존 파일 유지)")
                hist = existing

        if hist.empty:
            return

        # PBR 분위수 계산
        pbr_col = next((c for c in hist.columns if "PBR" in c.upper()), None)
        per_col = next((c for c in hist.columns if "PER" in c.upper()), None)
        div_col = next((c for c in hist.columns
                        if "배당" in c or "DIV" in c.upper() or "YIELD" in c.upper()), None)

        if pbr_col is None:
            logger.warning(" - PBR 컬럼을 찾을 수 없음 (컬럼: %s)", list(hist.columns))
            return

        pbr     = hist[pbr_col].replace(0, float("nan")).dropna()
        current = float(pbr.iloc[-1])
        pct_rank = round(float((pbr < current).mean() * 100), 1)

        row = {
            "date":        str(pbr.index[-1])[:10],
            "current_pbr": round(current, 3),
            "percentile":  pct_rank,
            "min_10y":     round(pbr.min(), 3),
            "max_10y":     round(pbr.max(), 3),
            "median_10y":  round(pbr.median(), 3),
            "mean_10y":    round(pbr.mean(), 3),
        }

        if per_col:
            per = hist[per_col].replace(0, float("nan")).dropna()
            if not per.empty:
                row["current_per"]     = round(float(per.iloc[-1]), 2)
                row["per_percentile"]  = round(float((per < row["current_per"]).mean() * 100), 1)
        if div_col:
            div = hist[div_col].replace(0, float("nan")).dropna()
            if not div.empty:
                row["current_div_yield"] = round(float(div.iloc[-1]), 3)

        pd.DataFrame([row]).to_csv(pct_path, index=False)
        logger.info(
            " - KOSPI PBR: %.2f배 → 10년 기준 %.1f%%ile (중앙값 %.2f배 / 최저 %.2f배 / 최고 %.2f배)",
            current, pct_rank, row["median_10y"], row["min_10y"], row["max_10y"]
        )

    except ImportError:
        logger.warning(" - pykrx 미설치 — KOSPI PBR 수집 건너뜀")
    except Exception as e:
        logger.error(" - KOSPI PBR 수집 실패: %s", e)


def run():
    logger.info("=== 04. 媛移?諛?湲곗뾽 (Valuation) ?곗씠???섏쭛 ?쒖옉 ===")
    ensure_dir(BASE_DIR)

    latest_date = get_latest_business_day()
    fetch_fundamentals(latest_date)
    fetch_adrs()
    fetch_dart_filings()
    fetch_all_eps_consensus()
    fetch_kospi_pbr()

    logger.info("=== 04. 媛移?諛?湲곗뾽 (Valuation) ?곗씠???섏쭛 ?꾨즺 ===")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    run()
