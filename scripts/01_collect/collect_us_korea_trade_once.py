from pathlib import Path
from datetime import datetime, timezone
from io import StringIO
import json
import shutil
import sqlite3
import time

import pandas as pd
import requests

ROOT = Path(r'C:\claude cowork\01_projects\Anal_reports')
RAW_DIR = ROOT / 'data' / 'raw' / 'macro' / 'trade_stats'
DB_DIR = ROOT / 'data' / 'database'
DB_PATH = DB_DIR / 'quant_data.sqlite'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc).astimezone()
ts = now.strftime('%Y%m%d_%H%M%S')
downloaded_at = now.isoformat(timespec='seconds')

SERIES = {
    # U.S. monthly balance-of-payments trade, goods + services.
    'BOPTEXP': {
        'country': 'United States', 'country_code': 'US', 'flow': 'exports', 'partner': 'World',
        'scope': 'goods_and_services', 'basis': 'Balance of Payments', 'frequency': 'monthly',
        'unit': 'Millions of USD', 'seasonal_adjustment': 'Seasonally Adjusted',
        'title': 'U.S. Exports of Goods and Services, Balance of Payments Basis',
    },
    'BOPTIMP': {
        'country': 'United States', 'country_code': 'US', 'flow': 'imports', 'partner': 'World',
        'scope': 'goods_and_services', 'basis': 'Balance of Payments', 'frequency': 'monthly',
        'unit': 'Millions of USD', 'seasonal_adjustment': 'Seasonally Adjusted',
        'title': 'U.S. Imports of Goods and Services, Balance of Payments Basis',
    },
    # U.S. quarterly NIPA trade, useful for GDP linkage.
    'EXPGS': {
        'country': 'United States', 'country_code': 'US', 'flow': 'exports', 'partner': 'World',
        'scope': 'goods_and_services', 'basis': 'NIPA/GDP', 'frequency': 'quarterly',
        'unit': 'Billions of USD, SAAR', 'seasonal_adjustment': 'Seasonally Adjusted Annual Rate',
        'title': 'U.S. Exports of Goods and Services',
    },
    'IMPGS': {
        'country': 'United States', 'country_code': 'US', 'flow': 'imports', 'partner': 'World',
        'scope': 'goods_and_services', 'basis': 'NIPA/GDP', 'frequency': 'quarterly',
        'unit': 'Billions of USD, SAAR', 'seasonal_adjustment': 'Seasonally Adjusted Annual Rate',
        'title': 'U.S. Imports of Goods and Services',
    },
    # Korea monthly merchandise trade from OECD via FRED.
    'XTEXVA01KRM667S': {
        'country': 'South Korea', 'country_code': 'KR', 'flow': 'exports', 'partner': 'World',
        'scope': 'merchandise_commodities', 'basis': 'OECD International Merchandise Trade Statistics', 'frequency': 'monthly',
        'unit': 'USD, exchange-rate converted', 'seasonal_adjustment': 'Seasonally Adjusted',
        'title': 'International Merchandise Trade Statistics: Exports: Commodities for Korea',
    },
    'XTIMVA01KRM667S': {
        'country': 'South Korea', 'country_code': 'KR', 'flow': 'imports', 'partner': 'World',
        'scope': 'merchandise_commodities', 'basis': 'OECD International Merchandise Trade Statistics', 'frequency': 'monthly',
        'unit': 'USD, exchange-rate converted', 'seasonal_adjustment': 'Seasonally Adjusted',
        'title': 'International Merchandise Trade Statistics: Imports: Commodities for Korea',
    },
    # U.S.-Korea bilateral goods trade, useful for Korea exposure cross-checks.
    'EXPKR': {
        'country': 'United States', 'country_code': 'US', 'flow': 'exports', 'partner': 'South Korea',
        'scope': 'goods', 'basis': 'F.A.S. basis', 'frequency': 'monthly',
        'unit': 'Millions of USD', 'seasonal_adjustment': 'Not Seasonally Adjusted',
        'title': 'U.S. Exports of Goods by F.A.S. Basis to South Korea',
    },
    'IMPKR': {
        'country': 'United States', 'country_code': 'US', 'flow': 'imports', 'partner': 'South Korea',
        'scope': 'goods', 'basis': 'Customs basis', 'frequency': 'monthly',
        'unit': 'Millions of USD', 'seasonal_adjustment': 'Not Seasonally Adjusted',
        'title': 'U.S. Imports of Goods by Customs Basis from South Korea',
    },
}


def download_text(url, attempts=4, timeout=90):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Connection': 'close'}, timeout=timeout)
            r.raise_for_status()
            if len(r.text) < 20:
                raise RuntimeError(f'response too small: {len(r.text)} chars')
            return r.text
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f'failed to download {url}: {last_error}')


backup_path = None
if DB_PATH.exists():
    backup_path = DB_DIR / f'quant_data.sqlite.backup_trade_stats_{ts}'
    shutil.copy2(DB_PATH, backup_path)

rows = []
metadata = []
for series_id, spec in SERIES.items():
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    try:
        text = download_text(url)
        raw_path = RAW_DIR / f'fred_{series_id}.csv'
        raw_path.write_text(text, encoding='utf-8')
        df = pd.read_csv(StringIO(text))
        df = df.rename(columns={'observation_date': 'date', series_id: 'value'})
        df['value'] = pd.to_numeric(df['value'].replace('.', pd.NA), errors='coerce')
        df = df.dropna(subset=['value']).copy()
        for _, row in df.iterrows():
            rows.append({
                'date': row['date'],
                'country': spec['country'],
                'country_code': spec['country_code'],
                'flow': spec['flow'],
                'partner': spec['partner'],
                'scope': spec['scope'],
                'basis': spec['basis'],
                'frequency': spec['frequency'],
                'value': float(row['value']),
                'unit': spec['unit'],
                'seasonal_adjustment': spec['seasonal_adjustment'],
                'series_id': series_id,
                'series_title': spec['title'],
                'source': 'FRED graph CSV',
                'source_url': f'https://fred.stlouisfed.org/series/{series_id}',
                'downloaded_at': downloaded_at,
            })
        metadata.append({
            **spec,
            'series_id': series_id,
            'status': 'success',
            'rows': len(df),
            'start_date': df['date'].min(),
            'end_date': df['date'].max(),
            'source_url': f'https://fred.stlouisfed.org/series/{series_id}',
            'downloaded_at': downloaded_at,
            'message': '',
        })
    except Exception as exc:
        metadata.append({
            **spec,
            'series_id': series_id,
            'status': 'failed',
            'rows': 0,
            'start_date': None,
            'end_date': None,
            'source_url': f'https://fred.stlouisfed.org/series/{series_id}',
            'downloaded_at': downloaded_at,
            'message': str(exc),
        })

long_df = pd.DataFrame(rows)
metadata_df = pd.DataFrame(metadata)
monthly_df = long_df[long_df['frequency'] == 'monthly'].copy()
quarterly_df = long_df[long_df['frequency'] == 'quarterly'].copy()

long_path = RAW_DIR / 'us_korea_trade_fred_long.csv'
monthly_path = RAW_DIR / 'us_korea_trade_fred_monthly.csv'
quarterly_path = RAW_DIR / 'us_trade_fred_quarterly_nipa.csv'
metadata_path = RAW_DIR / 'us_korea_trade_fred_metadata.csv'
long_df.to_csv(long_path, index=False, encoding='utf-8-sig')
monthly_df.to_csv(monthly_path, index=False, encoding='utf-8-sig')
quarterly_df.to_csv(quarterly_path, index=False, encoding='utf-8-sig')
metadata_df.to_csv(metadata_path, index=False, encoding='utf-8-sig')

conn = sqlite3.connect(DB_PATH)
long_df.to_sql('macro_trade_us_korea_fred', conn, if_exists='replace', index=False)
monthly_df.to_sql('macro_trade_us_korea_monthly', conn, if_exists='replace', index=False)
quarterly_df.to_sql('macro_trade_us_quarterly_nipa', conn, if_exists='replace', index=False)
metadata_df.to_sql('macro_trade_us_korea_metadata', conn, if_exists='replace', index=False)
for series_id, sub in long_df.groupby('series_id') if not long_df.empty else []:
    sub.to_sql(f'macro_trade_{series_id.lower()}', conn, if_exists='replace', index=False)
cur = conn.cursor()
cur.execute('CREATE INDEX IF NOT EXISTS idx_macro_trade_us_korea_fred_date_series ON macro_trade_us_korea_fred(date, series_id)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_macro_trade_us_korea_monthly_date_series ON macro_trade_us_korea_monthly(date, series_id)')
conn.commit()

verify = []
for table in ['macro_trade_us_korea_fred', 'macro_trade_us_korea_monthly', 'macro_trade_us_quarterly_nipa', 'macro_trade_us_korea_metadata']:
    verify.append({'table': table, 'rows': cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]})
latest = cur.execute('''
    SELECT series_id, country, flow, partner, scope, frequency, MAX(date) AS latest_date, ROUND(value, 4), unit
    FROM macro_trade_us_korea_fred t
    WHERE date = (SELECT MAX(date) FROM macro_trade_us_korea_fred t2 WHERE t2.series_id = t.series_id)
    GROUP BY series_id, country, flow, partner, scope, frequency, unit
    ORDER BY country, partner, flow, series_id
''').fetchall()
conn.close()

summary = {
    'downloaded_at': downloaded_at,
    'database': str(DB_PATH),
    'backup': str(backup_path) if backup_path else None,
    'raw_dir': str(RAW_DIR),
    'long_csv': str(long_path),
    'monthly_csv': str(monthly_path),
    'quarterly_csv': str(quarterly_path),
    'metadata_csv': str(metadata_path),
    'series_count': len(SERIES),
    'success_count': int((metadata_df['status'] == 'success').sum()),
    'failed': metadata_df[metadata_df['status'] != 'success'][['series_id', 'message']].to_dict('records'),
    'verification': verify,
    'latest': latest,
}
summary_path = RAW_DIR / 'us_korea_trade_collection_summary.json'
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
