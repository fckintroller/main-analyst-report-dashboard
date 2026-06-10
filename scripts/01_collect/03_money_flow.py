import datetime
import logging
import os
import time

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


def fetch_market_trading_value_history(years=20):
    logger.info("[MONEY FLOW] collecting %sy KOSPI/KOSDAQ investor net purchase history", years)
    today = datetime.datetime.today()
    start = today - datetime.timedelta(days=365 * years + 10)
    fromdate = start.strftime("%Y%m%d")
    todate = today.strftime("%Y%m%d")

    for file_key, market in {"kospi": "KOSPI", "kosdaq": "KOSDAQ"}.items():
        try:
            df = stock.get_market_trading_value_by_date(
                fromdate,
                todate,
                market,
                on="순매수",
                detail=False,
                freq="d",
            )
            if df.empty:
                logger.warning(" - %s investor history returned empty", market)
                continue

            df = df.reset_index()
            if "날짜" in df.columns:
                df.rename(columns={"날짜": "date"}, inplace=True)
            else:
                df.rename(columns={df.columns[0]: "date"}, inplace=True)
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            output_path = os.path.join(BASE_DIR, f"market_trading_value_{file_key}_20y.csv")
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(" - %s investor history collected: %s rows", market, len(df))
            time.sleep(0.5)
        except Exception as e:
            logger.error(" - %s investor history failed: %s", market, e)


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


def normalize_naver_columns(df):
    df = df.copy()
    df.columns = [
        col[-1] if isinstance(col, tuple) and col[-1] else str(col)
        for col in df.columns.values
    ]
    return df


def parse_naver_short_date(value):
    yy, mm, dd = [int(part) for part in str(value).split(".")]
    current_yy = datetime.datetime.today().year % 100
    year = 2000 + yy if yy <= current_yy else 1900 + yy
    return datetime.datetime(year, mm, dd)


def fetch_naver_investor_trend_history(years=20):
    logger.info("[MONEY FLOW] collecting %sy Naver investor trend history", years)
    end = datetime.datetime.today()
    start = end - datetime.timedelta(days=365 * years + 10)
    bizdate = end.strftime("%Y%m%d")
    markets = {
        "kospi": "01",
        "kosdaq": "02",
    }

    for file_key, sosok in markets.items():
        rows = []
        page = 1
        while True:
            url = f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate}&sosok={sosok}&page={page}"
            try:
                df = read_naver_table(url)
            except Exception as e:
                logger.error(" - Naver %s investor history page %s failed: %s", file_key, page, e)
                break

            if df is None or df.empty:
                break

            df = normalize_naver_columns(df)
            df = df[df["날짜"].notna()].copy()
            if df.empty:
                break

            df["date"] = df["날짜"].apply(parse_naver_short_date)
            rows.append(df)

            oldest = df["date"].min()
            if oldest < start:
                break
            page += 1

        if not rows:
            logger.warning(" - Naver %s investor history returned empty", file_key)
            continue

        out = pd.concat(rows, ignore_index=True)
        out = out[out["date"] >= start].copy()
        out.sort_values("date", inplace=True)
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        out["외국인합계"] = out.get("외국인")
        out["기관합계"] = out.get("기관계")
        out.to_csv(
            os.path.join(BASE_DIR, f"market_trading_value_{file_key}_20y.csv"),
            index=False,
            encoding="utf-8-sig",
        )
        logger.info(" - Naver %s investor history collected: %s rows", file_key.upper(), len(out))


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
    fetch_market_trading_value_history()
    fetch_naver_investor_trend_history()
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
