"""
OECD CLI 추가 국가 역사 시계열 1회 수집 (FRED 미러).
- 기존 01_macro.py에 없던 DEU/GBR/FRA/IND/BRA CLI를 FRED에서 1회 수집
- 이후 매일 01_macro.py fetch_fred_yields()가 증분 갱신
- 저장 경로: data/raw/macro/macro_indices/
- 실행: python scripts/01_collect/collect_oecd_cli_once.py
"""
import logging
import os
import time

import FinanceDataReader as fdr
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAVE_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "macro", "macro_indices")

CLI_SERIES = {
    "DEU_CLI": "DEULOLITONOSTSAM",
    "GBR_CLI": "GBRLOLITONOSTSAM",
    "FRA_CLI": "FRALOLITONOSTSAM",
    "IND_CLI": "INDLOLITONOSTSAM",
    "BRA_CLI": "BRALOLITONOSTSAM",
}


def run():
    os.makedirs(SAVE_DIR, exist_ok=True)
    for name, fred_code in CLI_SERIES.items():
        for attempt in range(3):
            try:
                df = fdr.DataReader(f"FRED:{fred_code}")
                if not df.empty:
                    path = os.path.join(SAVE_DIR, f"{name}.csv")
                    df.to_csv(path)
                    logger.info("OK  %s: %d행  %s ~ %s", name,
                                len(df), str(df.index[0].date()), str(df.index[-1].date()))
                break
            except Exception as e:
                logger.warning("%s 시도 %d 실패: %s", name, attempt + 1, e)
                time.sleep(2 ** attempt)
        else:
            logger.error("FAIL %s", name)
        time.sleep(0.5)


if __name__ == "__main__":
    run()
