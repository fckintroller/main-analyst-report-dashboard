"""
중국 거시경제 데이터 수집.

원천:
  - FRED: XTEXVA01CNM667S (중국 수출, USD mn, 월간)
           XTIMVA01CNM667S (중국 수입, USD mn, 월간)
  - yfinance: 000300.SS (CSI300 지수, 일별)

저장:
  - data/raw/macro/china/china_exports.csv
  - data/raw/macro/china/china_imports.csv
  - data/raw/macro/china/csi300_daily.csv
  - DB: macro_china_exports, macro_china_imports, macro_csi300_daily
"""
import logging
import os
import sqlite3
import time
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "macro" / "china"
OUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")
FRED_KEY = os.getenv("FRED_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FRED_SERIES = {
    "china_exports": "XTEXVA01CNM667S",
    "china_imports": "XTIMVA01CNM667S",
}


def _fetch_fred(series_id: str, retries: int = 3) -> pd.DataFrame:
    url = "https://api.stlouisfed.org/fred/series/observations"
    for attempt in range(retries):
        try:
            r = requests.get(url, params={
                "series_id": series_id, "api_key": FRED_KEY,
                "file_type": "json", "observation_start": "2010-01-01",
            }, timeout=15)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            df = pd.DataFrame(obs)[["date", "value"]]
            df["date"] = pd.to_datetime(df["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna()
            return df
        except Exception as e:
            logger.warning("FRED %s 시도 %d 실패: %s", series_id, attempt + 1, e)
            time.sleep(2 ** attempt)
    return pd.DataFrame(columns=["date", "value"])


def _fetch_csi300(retries: int = 3) -> pd.DataFrame:
    for attempt in range(retries):
        try:
            ticker = yf.Ticker("000300.SS")
            df = ticker.history(start="2010-01-01", auto_adjust=True)
            if df.empty:
                raise ValueError("empty response")
            df = df[["Close"]].reset_index()
            df.columns = ["date", "close"]
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            return df.dropna()
        except Exception as e:
            logger.warning("CSI300 시도 %d 실패: %s", attempt + 1, e)
            time.sleep(2 ** attempt)
    return pd.DataFrame(columns=["date", "close"])


def _save_and_store(df: pd.DataFrame, csv_path: Path, table: str,
                    conn: sqlite3.Connection, date_col: str = "date") -> int:
    if df.empty:
        logger.warning("  %s 데이터 없음", table)
        return 0
    existing_csv = pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame()
    df_new = df.copy()
    df_new[date_col] = df_new[date_col].astype(str)
    if not existing_csv.empty:
        existing_csv[date_col] = existing_csv[date_col].astype(str)
        max_existing = existing_csv[date_col].max()
        df_new = df_new[df_new[date_col] > max_existing]
    if df_new.empty:
        logger.info("  %s 신규 없음", table)
        all_df = df.copy()
        all_df[date_col] = all_df[date_col].astype(str)
        all_df.to_sql(table, conn, if_exists="replace", index=False)
        return 0
    result = pd.concat([existing_csv, df_new], ignore_index=True).drop_duplicates(date_col)
    result.to_csv(csv_path, index=False, encoding="utf-8-sig")
    result.to_sql(table, conn, if_exists="replace", index=False)
    added = len(df_new)
    logger.info("  %s: +%d행, 전체 %d행, max=%s", table, added, len(result), result[date_col].max())
    return added


def run():
    logger.info("중국 거시경제 데이터 수집 시작")
    with sqlite3.connect(DB_PATH) as conn:
        for name, sid in FRED_SERIES.items():
            logger.info("FRED %s 수집 중 (%s)", name, sid)
            df = _fetch_fred(sid)
            _save_and_store(df, OUT_DIR / f"{name}.csv", f"macro_{name}", conn)

        logger.info("CSI300 일별 수집 중")
        df_csi = _fetch_csi300()
        _save_and_store(df_csi, OUT_DIR / "csi300_daily.csv", "macro_csi300_daily", conn, "date")

    logger.info("완료")


if __name__ == "__main__":
    run()
