from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import sqlite3
import time

import pandas as pd
import yfinance as yf

ROOT = Path(r'C:\claude cowork\01_projects\Anal_reports')
RAW_DIR = ROOT / 'data' / 'raw' / 'macro' / 'global_indices'
DB_DIR = ROOT / 'data' / 'database'
DB_PATH = DB_DIR / 'quant_data.sqlite'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc).astimezone()
ts = now.strftime('%Y%m%d_%H%M%S')
downloaded_at = now.isoformat(timespec='seconds')

# Major country/region equity indices. Yahoo Finance symbols are used because no API key is required.
TARGETS = [
    {'region': 'North America', 'country': 'United States', 'index_name': 'S&P 500', 'slug': 'us_sp500', 'ticker': '^GSPC'},
    {'region': 'North America', 'country': 'United States', 'index_name': 'NASDAQ Composite', 'slug': 'us_nasdaq_composite', 'ticker': '^IXIC'},
    {'region': 'North America', 'country': 'United States', 'index_name': 'Dow Jones Industrial Average', 'slug': 'us_dow_jones', 'ticker': '^DJI'},
    {'region': 'North America', 'country': 'United States', 'index_name': 'Russell 2000', 'slug': 'us_russell_2000', 'ticker': '^RUT'},
    {'region': 'North America', 'country': 'Canada', 'index_name': 'S&P/TSX Composite', 'slug': 'canada_tsx_composite', 'ticker': '^GSPTSE'},
    {'region': 'North America', 'country': 'Mexico', 'index_name': 'S&P/BMV IPC', 'slug': 'mexico_ipc', 'ticker': '^MXX'},

    {'region': 'Asia', 'country': 'South Korea', 'index_name': 'KOSPI', 'slug': 'korea_kospi', 'ticker': '^KS11'},
    {'region': 'Asia', 'country': 'South Korea', 'index_name': 'KOSDAQ', 'slug': 'korea_kosdaq', 'ticker': '^KQ11'},
    {'region': 'Asia', 'country': 'Japan', 'index_name': 'Nikkei 225', 'slug': 'japan_nikkei_225', 'ticker': '^N225'},
    {'region': 'Asia', 'country': 'Japan', 'index_name': 'TOPIX', 'slug': 'japan_topix', 'ticker': '1306.T'},
    {'region': 'Asia', 'country': 'China', 'index_name': 'Shanghai Composite', 'slug': 'china_shanghai_composite', 'ticker': '000001.SS'},
    {'region': 'Asia', 'country': 'China', 'index_name': 'Shenzhen Component', 'slug': 'china_shenzhen_component', 'ticker': '399001.SZ'},
    {'region': 'Asia', 'country': 'Hong Kong', 'index_name': 'Hang Seng Index', 'slug': 'hongkong_hang_seng', 'ticker': '^HSI'},
    {'region': 'Asia', 'country': 'Taiwan', 'index_name': 'Taiwan Weighted Index', 'slug': 'taiwan_weighted', 'ticker': '^TWII'},
    {'region': 'Asia', 'country': 'India', 'index_name': 'NIFTY 50', 'slug': 'india_nifty_50', 'ticker': '^NSEI'},
    {'region': 'Asia', 'country': 'India', 'index_name': 'BSE SENSEX', 'slug': 'india_sensex', 'ticker': '^BSESN'},
    {'region': 'Asia', 'country': 'Indonesia', 'index_name': 'Jakarta Composite', 'slug': 'indonesia_jakarta_composite', 'ticker': '^JKSE'},
    {'region': 'Asia', 'country': 'Thailand', 'index_name': 'SET Index', 'slug': 'thailand_set', 'ticker': '^SET.BK'},
    {'region': 'Asia', 'country': 'Singapore', 'index_name': 'Straits Times Index', 'slug': 'singapore_sti', 'ticker': '^STI'},
    {'region': 'Asia', 'country': 'Vietnam', 'index_name': 'VN Index', 'slug': 'vietnam_vn_index', 'ticker': '^VNINDEX.VN'},

    {'region': 'Europe', 'country': 'Eurozone', 'index_name': 'EURO STOXX 50', 'slug': 'eurozone_euro_stoxx_50', 'ticker': '^STOXX50E'},
    {'region': 'Europe', 'country': 'Germany', 'index_name': 'DAX Performance Index', 'slug': 'germany_dax', 'ticker': '^GDAXI'},
    {'region': 'Europe', 'country': 'France', 'index_name': 'CAC 40', 'slug': 'france_cac_40', 'ticker': '^FCHI'},
    {'region': 'Europe', 'country': 'United Kingdom', 'index_name': 'FTSE 100', 'slug': 'uk_ftse_100', 'ticker': '^FTSE'},
    {'region': 'Europe', 'country': 'Italy', 'index_name': 'FTSE MIB', 'slug': 'italy_ftse_mib', 'ticker': 'FTSEMIB.MI'},
    {'region': 'Europe', 'country': 'Spain', 'index_name': 'IBEX 35', 'slug': 'spain_ibex_35', 'ticker': '^IBEX'},

    {'region': 'Oceania', 'country': 'Australia', 'index_name': 'S&P/ASX 200', 'slug': 'australia_asx_200', 'ticker': '^AXJO'},
    {'region': 'South America', 'country': 'Brazil', 'index_name': 'Bovespa Index', 'slug': 'brazil_bovespa', 'ticker': '^BVSP'},
]


def normalize_yf_frame(df, target):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.reset_index()
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
    if 'date' not in df.columns and 'datetime' in df.columns:
        df = df.rename(columns={'datetime': 'date'})
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    for col in ['open', 'high', 'low', 'close', 'adj_close', 'volume']:
        if col not in df.columns:
            df[col] = pd.NA
    df['region'] = target['region']
    df['country'] = target['country']
    df['index_name'] = target['index_name']
    df['slug'] = target['slug']
    df['ticker'] = target['ticker']
    df['source'] = 'Yahoo Finance via yfinance'
    df['source_url'] = f'https://finance.yahoo.com/quote/{target["ticker"].replace("^", "%5E")}/'
    df['downloaded_at'] = downloaded_at
    return df[['date', 'region', 'country', 'index_name', 'slug', 'ticker', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'source', 'source_url', 'downloaded_at']]


backup_path = None
if DB_PATH.exists():
    backup_path = DB_DIR / f'quant_data.sqlite.backup_global_indices_{ts}'
    shutil.copy2(DB_PATH, backup_path)

frames = []
meta = []
for target in TARGETS:
    status = 'failed'
    message = ''
    df = pd.DataFrame()
    for attempt in range(1, 4):
        try:
            raw = yf.download(target['ticker'], start='2010-01-01', progress=False, auto_adjust=False, threads=False)
            if raw.empty:
                raise RuntimeError('empty download')
            df = normalize_yf_frame(raw, target)
            status = 'success'
            break
        except Exception as exc:
            message = str(exc)
            time.sleep(1.5 * attempt)
    if status == 'success':
        out_path = RAW_DIR / f'yahoo_{target["slug"]}_daily.csv'
        df.to_csv(out_path, index=False, encoding='utf-8-sig')
        frames.append(df)
        meta.append({**target, 'status': status, 'rows': len(df), 'start_date': df['date'].min(), 'end_date': df['date'].max(), 'message': ''})
    else:
        meta.append({**target, 'status': status, 'rows': 0, 'start_date': None, 'end_date': None, 'message': message})

long_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
meta_df = pd.DataFrame(meta)
long_path = RAW_DIR / 'global_indices_daily_long.csv'
meta_path = RAW_DIR / 'global_indices_metadata.csv'
long_df.to_csv(long_path, index=False, encoding='utf-8-sig')
meta_df.to_csv(meta_path, index=False, encoding='utf-8-sig')

conn = sqlite3.connect(DB_PATH)
long_df.to_sql('macro_global_indices_daily', conn, if_exists='replace', index=False)
meta_df.to_sql('macro_global_indices_metadata', conn, if_exists='replace', index=False)
for slug, sub in long_df.groupby('slug'):
    sub.to_sql(f'macro_global_indices_{slug}_daily', conn, if_exists='replace', index=False)
cur = conn.cursor()
cur.execute('CREATE INDEX IF NOT EXISTS idx_macro_global_indices_daily_date_slug ON macro_global_indices_daily(date, slug)')
for slug in long_df['slug'].unique() if not long_df.empty else []:
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_macro_global_indices_{slug}_daily_date ON macro_global_indices_{slug}_daily(date)')
conn.commit()

verify = []
for table in ['macro_global_indices_daily', 'macro_global_indices_metadata']:
    verify.append({'table': table, 'rows': cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]})
latest_by_index = cur.execute('''
    SELECT slug, country, index_name, ticker, MAX(date) AS latest_date, COUNT(*) AS rows
    FROM macro_global_indices_daily
    GROUP BY slug, country, index_name, ticker
    ORDER BY region, country, index_name
''').fetchall()
conn.close()

summary = {
    'downloaded_at': downloaded_at,
    'database': str(DB_PATH),
    'backup': str(backup_path) if backup_path else None,
    'raw_dir': str(RAW_DIR),
    'long_csv': str(long_path),
    'metadata_csv': str(meta_path),
    'target_count': len(TARGETS),
    'success_count': int((meta_df['status'] == 'success').sum()),
    'failed': meta_df[meta_df['status'] != 'success'][['country', 'index_name', 'ticker', 'message']].to_dict('records'),
    'verification': verify,
    'latest_by_index': latest_by_index,
}
summary_path = RAW_DIR / 'global_indices_collection_summary.json'
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
