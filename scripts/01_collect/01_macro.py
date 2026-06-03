import logging
import os

import FinanceDataReader as fdr
import yfinance as yf


logger = logging.getLogger(__name__)
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "macro")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


INDICES = {
    "KOSPI": "KS11",
    "KOSDAQ": "KQ11",
    "DowJones": "DJI",
    "NASDAQ": "IXIC",
    "S&P500": "US500",
    "Nikkei225": "N225",
    "FTSE100": "FTSE",
    "Shanghai": "SSEC",
}

EXCHANGE_RATES = {
    "USD_KRW": "USD/KRW",
    "JPY_KRW": "JPY/KRW",
    "EUR_KRW": "EUR/KRW",
}

COMMODITIES = {
    "WTI": "CL=F",
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Corn": "ZC=F",
    "Wheat": "KE=F",
    "Soybean": "ZS=F",
}

MACRO_YF = {
    "TNX": "^TNX",
    "DXY": "DX-Y.NYB",
}

FRED_TICKERS = {
    "DGS10": "DGS10",
    "DGS2": "DGS2",
    "WALCL": "WALCL",
    "M2SL": "M2SL",
    "BAMLH0A0HYM2": "BAMLH0A0HYM2",
    "CPIAUCSL": "CPIAUCSL",
    "UNRATE": "UNRATE",
    "KOR_EXPORTS": "XTEXVA01KRM667S",
}


def fetch_fdr_data(category_name, targets_dict, start_date="2010-01-01"):
    save_path = os.path.join(BASE_DIR, category_name)
    ensure_dir(save_path)
    logger.info("[MACRO] collecting %s data", category_name)

    for name, ticker in targets_dict.items():
        try:
            df = fdr.DataReader(ticker, start_date)
            if not df.empty:
                df.to_csv(os.path.join(save_path, f"{name}.csv"))
                logger.info(" - %s (%s) collected: %s rows", name, ticker, len(df))
        except Exception as e:
            logger.error(" - %s (%s) failed: %s", name, ticker, e)


def fetch_yf_macro():
    save_path = os.path.join(BASE_DIR, "macro_indices")
    ensure_dir(save_path)
    logger.info("[MACRO] collecting Yahoo Finance macro data")

    for name, ticker in MACRO_YF.items():
        try:
            df = yf.download(ticker, period="10y", progress=False)
            if not df.empty:
                df.to_csv(os.path.join(save_path, f"{name}.csv"))
                logger.info(" - %s (%s) collected: %s rows", name, ticker, len(df))
        except Exception as e:
            logger.error(" - %s (%s) failed: %s", name, ticker, e)


def fetch_fred_yields():
    save_path = os.path.join(BASE_DIR, "macro_indices")
    ensure_dir(save_path)
    logger.info("[MACRO] collecting FRED macro data")

    for name, ticker in FRED_TICKERS.items():
        try:
            df = fdr.DataReader(f"FRED:{ticker}")
            if not df.empty:
                df.to_csv(os.path.join(save_path, f"{name}.csv"))
                logger.info(" - %s collected: %s rows", name, len(df))
        except Exception as e:
            logger.error(" - %s failed: %s", name, e)


def run():
    logger.info("=== 01. Macro collection started ===")
    ensure_dir(BASE_DIR)
    fetch_fdr_data("indices", INDICES)
    fetch_fdr_data("exchange_rates", EXCHANGE_RATES)
    fetch_fdr_data("commodities", COMMODITIES)
    fetch_yf_macro()
    fetch_fred_yields()
    logger.info("=== 01. Macro collection finished ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
