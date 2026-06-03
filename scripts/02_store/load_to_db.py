import os
import sqlite3
import pandas as pd
import logging
import re

logger = logging.getLogger(__name__)

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw'))
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'database'))
DB_PATH = os.path.join(DB_DIR, 'quant_data.sqlite')

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def clean_table_name(filename):
    """CSV ?뚯씪紐낆쓣 SQLite ?뚯씠釉붾챸?쇰줈 ?곌린 醫뗪쾶 ?뺤젣"""
    name = os.path.splitext(filename)[0]
    # ?뱀닔臾몄옄 ?쒓굅 諛?怨듬갚???몃뜑?ㅼ퐫?대줈 蹂??    name = re.sub(r'\W+', '_', name).strip('_')
    return name

def load_csv_to_sqlite():
    logger.info("=== 02_Store: SQLite DB ?곗씠???곸옱 ?쒖옉 ===")
    ensure_dir(DB_DIR)

    conn = sqlite3.connect(DB_PATH)
    loaded_files = 0

    for category in os.listdir(RAW_DIR):
        category_path = os.path.join(RAW_DIR, category)
        if not os.path.isdir(category_path):
            continue

        for root, _, files in os.walk(category_path):
            for file in files:
                if file.endswith('.csv'):
                    file_path = os.path.join(root, file)
                    table_prefix = category
                    # adrs 泥섎읆 ?섏쐞 ?대뜑媛 ?덉쑝硫?prefix 異붽?
                    rel_dir = os.path.relpath(root, RAW_DIR)
                    if '\\' in rel_dir or '/' in rel_dir:
                        sub = os.path.basename(root)
                        table_prefix = f"{category}_{sub}"

                    base_name = clean_table_name(file)
                    table_name = f"{table_prefix}_{base_name}".lower()

                    try:
                        df = pd.read_csv(file_path)
                        # DB ?곸옱 (湲곗〈 ?뚯씠釉???뼱?곌린)
                        df.to_sql(table_name, conn, if_exists='replace', index=False)
                        loaded_files += 1
                        logger.debug(f" - Loaded {file} into table '{table_name}'")
                    except Exception as e:
                        logger.error(f"Failed to load {file_path} to DB: {e}")

    conn.close()
    logger.info(f"=== DB ?곸옱 ?꾨즺: 珥?{loaded_files}媛쒖쓽 CSV ?뚯씪??SQLite??留덉씠洹몃젅?댁뀡 ?섏뿀?듬땲?? ===")
    logger.info(f"DB Path: {DB_PATH}")

def run():
    load_csv_to_sqlite()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    run()
