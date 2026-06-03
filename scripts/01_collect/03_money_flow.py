import datetime
import logging
import os

import FinanceDataReader as fdr
import pandas as pd
import requests
import yfinance as yf
from pykrx import stock


logger = logging.getLogger(__name__)
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "money_flow")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_latest_business_day():
    today = datetime.datetime.today()
    past_10_days = today - datetime.timedelta(days=10)
    df = fdr.DataReader("KS11", past_10_days, today)
    if not df.empty:
        return df.index[-1].strftime("%Y%m%d")
    return today.strftime("%Y%m%d")


def fetch_investor_net_purchases(date_str):
    logger.info("[%s] collecting KOSPI investor net purchases", date_str)
    investor_types = {
        "foreigner": "외국인",
        "institutional": "기관합계",
        "pension": "연기금",
    }

    for file_key, investor_type in investor_types.items():
        try:
            df = stock.get_market_net_purchases_of_equities_by_ticker(date_str, date_str, "KOSPI", investor_type)
            if not df.empty:
                df.to_csv(os.path.join(BASE_DIR, f"net_purchase_{file_key}_kospi.csv"))
                logger.info(" - %s net purchase collected: %s rows", investor_type, len(df))
        except Exception as e:
            logger.error(" - %s net purchase failed: %s", investor_type, e)


def fetch_short_selling(date_str):
    logger.info("[%s] collecting KOSPI short selling", date_str)
    try:
        df = stock.get_market_short_selling_by_ticker(date_str, market="KOSPI")
        if not df.empty:
            df.to_csv(os.path.join(BASE_DIR, "short_selling_kospi.csv"))
            logger.info(" - short selling collected: %s rows", len(df))
    except Exception as e:
        logger.error(" - short selling failed: %s", e)


def fetch_bitcoin():
    logger.info("[MONEY FLOW] collecting BTC-USD")
    try:
        df = yf.download("BTC-USD", period="10y", progress=False)
        if not df.empty:
            df.to_csv(os.path.join(BASE_DIR, "bitcoin.csv"))
            logger.info(" - BTC-USD collected: %s rows", len(df))
    except Exception as e:
        logger.error(" - BTC-USD failed: %s", e)


def read_naver_table(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=10)
    dfs = pd.read_html(res.text, encoding="euc-kr")
    if not dfs:
        return None
    df = dfs[0]
    df.dropna(how="all", inplace=True)
    return df


def fetch_naver_investor_derivatives():
    logger.info("[MONEY FLOW] collecting Naver investor derivative trends")
    today = datetime.datetime.today().strftime("%Y%m%d")
    sosoks = {"kosdaq_trend": "02", "futures_trend": "03"}

    for name, code in sosoks.items():
        url = f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={today}&sosok={code}"
        try:
            df = read_naver_table(url)
            if df is not None:
                df.to_csv(os.path.join(BASE_DIR, f"{name}.csv"), index=False, encoding="utf-8-sig")
                logger.info(" - %s collected", name)
        except Exception as e:
            logger.error(" - %s failed: %s", name, e)


def fetch_naver_program_trading():
    logger.info("[MONEY FLOW] collecting Naver program trading")
    today = datetime.datetime.today().strftime("%Y%m%d")
    markets = {"program_kospi": "", "program_kosdaq": "02"}

    for name, code in markets.items():
        url = f"https://finance.naver.com/sise/programDealTrendDay.naver?bizdate={today}&sosok={code}"
        try:
            df = read_naver_table(url)
            if df is not None:
                df.columns = ["_".join(col).strip() if isinstance(col, tuple) else col for col in df.columns.values]
                df.to_csv(os.path.join(BASE_DIR, f"{name}.csv"), index=False, encoding="utf-8-sig")
                logger.info(" - %s collected", name)
        except Exception as e:
            logger.error(" - %s failed: %s", name, e)


def fetch_naver_deposit():
    logger.info("[MONEY FLOW] collecting Naver customer deposit and credit balance")
    url = "https://finance.naver.com/sise/sise_deposit.naver"
    try:
        df = read_naver_table(url)
        if df is not None:
            df.columns = ["_".join(col).strip() if isinstance(col, tuple) else col for col in df.columns.values]
            df.to_csv(os.path.join(BASE_DIR, "market_funds_trend.csv"), index=False, encoding="utf-8-sig")
            logger.info(" - market funds trend collected")
    except Exception as e:
        logger.error(" - market funds trend failed: %s", e)


def fetch_naver_sector_returns():
    logger.info("[MONEY FLOW] collecting Naver sector returns")
    url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    try:
        df = read_naver_table(url)
        if df is not None:
            df.to_csv(os.path.join(BASE_DIR, "sector_returns.csv"), index=False, encoding="utf-8-sig")
            logger.info(" - sector returns collected: %s rows", len(df))
    except Exception as e:
        logger.error(" - sector returns failed: %s", e)


def run():
    logger.info("=== 03. Money flow collection started ===")
    ensure_dir(BASE_DIR)

    latest_date = get_latest_business_day()
    logger.info("business day: %s", latest_date)

    fetch_investor_net_purchases(latest_date)
    fetch_short_selling(latest_date)
    fetch_bitcoin()
    fetch_naver_investor_derivatives()
    fetch_naver_program_trading()
    fetch_naver_deposit()
    fetch_naver_sector_returns()

    logger.info("=== 03. Money flow collection finished ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
