import datetime
import json
import logging
import os

import FinanceDataReader as fdr
import fear_and_greed
import yfinance as yf
from pykrx import stock


logger = logging.getLogger(__name__)
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "sentiment")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def fetch_cnn_fear_and_greed():
    logger.info("[SENTIMENT] collecting CNN Fear & Greed")
    try:
        fng = fear_and_greed.get()
        data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "value": fng.value,
            "description": fng.description,
            "last_update": str(fng.last_update),
        }
        with open(os.path.join(BASE_DIR, "fear_greed.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(" - Fear & Greed collected: %s (%s)", fng.value, fng.description)
    except Exception as e:
        logger.error(" - Fear & Greed failed: %s", e)


def fetch_sentiment_indices():
    logger.info("[SENTIMENT] collecting VIX/TRIN/MOVE/SKEW/SOX/VKOSPI")
    yf_tickers = {"VIX": "^VIX", "TRIN": "^TRIN", "MOVE": "^MOVE", "SKEW": "^SKEW", "SOX": "^SOX"}

    for name, ticker in yf_tickers.items():
        try:
            df = yf.download(ticker, period="10y", progress=False)
            if not df.empty:
                df.to_csv(os.path.join(BASE_DIR, f"{name.lower()}.csv"))
                logger.info(" - %s collected: %s rows", name, len(df))
        except Exception as e:
            logger.error(" - %s failed: %s", name, e)

    try:
        df_vkospi = fdr.DataReader("VKOSPI", "2010-01-01")
        if not df_vkospi.empty:
            df_vkospi.to_csv(os.path.join(BASE_DIR, "vkospi.csv"))
            logger.info(" - VKOSPI collected: %s rows", len(df_vkospi))
    except Exception as e:
        logger.error(" - VKOSPI failed: %s", e)


def fetch_kospi_adr():
    logger.info("[SENTIMENT] calculating KOSPI ADR")
    try:
        today = datetime.datetime.today()
        past_60_days = today - datetime.timedelta(days=60)
        df_kospi = fdr.DataReader("KS11", past_60_days, today)
        target_days = df_kospi.index[-20:]

        adv_sum = 0
        dec_sum = 0

        for date in target_days:
            date_str = date.strftime("%Y%m%d")
            change_dict = stock.get_market_price_change_indicator(date_str, "KOSPI")
            if "상승" in change_dict and "하락" in change_dict:
                adv_sum += change_dict["상승"]
                dec_sum += change_dict["하락"]

        adr = (adv_sum / dec_sum) * 100 if dec_sum > 0 else 100
        status = "Overbought" if adr >= 120 else "Oversold" if adr <= 75 else "Neutral"
        data = {
            "date": target_days[-1].strftime("%Y-%m-%d"),
            "advancing_20d": adv_sum,
            "declining_20d": dec_sum,
            "ADR_percent": round(adr, 2),
            "status": status,
        }

        with open(os.path.join(BASE_DIR, "kospi_adr.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(" - KOSPI ADR collected: %s%% (%s)", data["ADR_percent"], status)
    except Exception as e:
        logger.error(" - KOSPI ADR failed: %s", e)


def run():
    logger.info("=== 02. Sentiment collection started ===")
    ensure_dir(BASE_DIR)
    fetch_cnn_fear_and_greed()
    fetch_sentiment_indices()
    fetch_kospi_adr()
    logger.info("=== 02. Sentiment collection finished ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
