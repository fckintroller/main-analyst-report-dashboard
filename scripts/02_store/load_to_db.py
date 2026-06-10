import logging
import os
import re
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database"))
DB_PATH = os.path.join(DB_DIR, "quant_data.sqlite")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def clean_table_name(value):
    """파일/폴더명을 SQLite 테이블명으로 안전하게 변환한다."""
    name = os.path.splitext(str(value))[0]
    name = re.sub(r"\W+", "_", name).strip("_")
    return name.lower()


def table_name_for_csv(file_path, raw_dir):
    """raw 하위 CSV 경로를 충돌 없는 SQLite 테이블명으로 변환한다.

    예:
    - raw/macro/indices/KOSPI.csv             -> macro_indices_kospi
    - raw/stock_detail/005930/ohlcv.csv       -> stock_detail_005930_ohlcv
    - raw/stock_detail/sector_map.csv         -> stock_detail_sector_map
    """
    file_path = Path(file_path)
    raw_dir = Path(raw_dir)
    rel = file_path.relative_to(raw_dir)
    parts = [clean_table_name(part) for part in rel.parts]
    parts[-1] = clean_table_name(file_path.stem)
    return "_".join(part for part in parts if part)


def load_csv_to_sqlite(raw_dir=RAW_DIR, db_path=DB_PATH):
    logger.info("=== 02_Store: SQLite DB 데이터 적재 시작 ===")
    raw_dir = Path(raw_dir)
    db_path = Path(db_path)
    ensure_dir(db_path.parent)

    conn = sqlite3.connect(db_path)
    loaded_files = 0

    if not raw_dir.exists():
        logger.warning("RAW_DIR가 없습니다: %s", raw_dir)
        conn.close()
        return 0

    for file_path in sorted(raw_dir.rglob("*.csv")):
        try:
            table_name = table_name_for_csv(file_path, raw_dir)
            df = pd.read_csv(file_path)
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            loaded_files += 1
            logger.debug(" - Loaded %s into table '%s'", file_path, table_name)
        except Exception as e:
            logger.error("Failed to load %s to DB: %s", file_path, e)

    conn.close()
    logger.info("=== DB 적재 완료: 총 %d개 CSV 파일을 SQLite로 마이그레이션 ===", loaded_files)
    logger.info("DB Path: %s", db_path)
    return loaded_files


def run():
    load_csv_to_sqlite()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
