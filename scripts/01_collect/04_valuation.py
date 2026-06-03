import os
import logging
import datetime
# from pykrx import stock
import FinanceDataReader as fdr
import OpenDartReader

logger = logging.getLogger(__name__)
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'raw', 'valuation')

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

        # 1. ?먭린二쇱떇(?먯궗二? 痍⑤뱷/泥섎텇 ?꾪꽣留?        df_buyback = df[df['report_nm'].str.contains('?먭린二쇱떇', na=False)]
        if not df_buyback.empty:
            df_buyback.to_csv(os.path.join(BASE_DIR, 'dart_buybacks.csv'), index=False, encoding='utf-8-sig')

        # 2. 諛곕떦 寃곗젙 ?꾪꽣留?        df_dividend = df[df['report_nm'].str.contains('諛곕떦', na=False)]
        if not df_dividend.empty:
            df_dividend.to_csv(os.path.join(BASE_DIR, 'dart_dividends.csv'), index=False, encoding='utf-8-sig')

        # 3. ?꾩썝/理쒕?二쇱＜ 吏遺?蹂???꾪꽣留?        df_insider = df[df['report_nm'].str.contains('?뚯쑀?곹솴蹂닿퀬??, na=False)]
        if not df_insider.empty:
            df_insider.to_csv(os.path.join(BASE_DIR, 'dart_insiders.csv'), index=False, encoding='utf-8-sig')

        logger.info(f" - DART 二쇱슂 ?대깽???꾪꽣留??꾨즺 (?먯궗二? {len(df_buyback)}嫄? 諛곕떦: {len(df_dividend)}嫄? 吏遺꾨??? {len(df_insider)}嫄?")

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

def run():
    logger.info("=== 04. 媛移?諛?湲곗뾽 (Valuation) ?곗씠???섏쭛 ?쒖옉 ===")
    ensure_dir(BASE_DIR)

    latest_date = get_latest_business_day()
    fetch_fundamentals(latest_date)
    fetch_adrs()
    fetch_dart_filings()
    fetch_all_eps_consensus()

    logger.info("=== 04. 媛移?諛?湲곗뾽 (Valuation) ?곗씠???섏쭛 ?꾨즺 ===")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    run()
