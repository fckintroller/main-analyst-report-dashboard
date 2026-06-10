from pathlib import Path
from datetime import datetime, timezone
import shutil
import sqlite3
import json

import requests
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup

ROOT = Path(r'C:\claude cowork\01_projects\Anal_reports')
RAW_DIR = ROOT / 'data' / 'raw' / 'macro' / 'nonferrous_metals'
DB_DIR = ROOT / 'data' / 'database'
DB_PATH = DB_DIR / 'quant_data.sqlite'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc).astimezone()
ts = now.strftime('%Y%m%d_%H%M%S')
downloaded_at = now.isoformat(timespec='seconds')

backup_path = None
if DB_PATH.exists():
    backup_path = DB_DIR / f'quant_data.sqlite.backup_{ts}'
    shutil.copy2(DB_PATH, backup_path)

wb_url = 'https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx'
wb_xlsx = RAW_DIR / f'worldbank_CMO_Historical_Data_Monthly_{ts}.xlsx'
r = requests.get(wb_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=90)
r.raise_for_status()
wb_xlsx.write_bytes(r.content)

raw = pd.read_excel(wb_xlsx, sheet_name='Monthly Prices', header=None, engine='openpyxl')
update_text = ''
for val in raw.iloc[:6, 0].dropna().astype(str).tolist():
    if 'Updated on' in val:
        update_text = val
        break
names = raw.iloc[4]
units = raw.iloc[5]
data = raw.iloc[6:].copy()
period_col = 0
wanted = ['Aluminum', 'Copper', 'Lead', 'Tin', 'Nickel', 'Zinc']
if any(str(x).strip() == 'Cobalt' for x in names.dropna()):
    wanted.append('Cobalt')

long_rows = []
missing_wb = []
for metal in wanted:
    idxs = [i for i, v in names.items() if str(v).strip().lower() == metal.lower()]
    if not idxs:
        missing_wb.append(metal)
        continue
    idx = idxs[0]
    unit = str(units.iloc[idx]).strip()
    sub = pd.DataFrame({
        'period': data.iloc[:, period_col].astype(str),
        'metal': metal.lower(),
        'metal_name': metal,
        'price_usd': pd.to_numeric(data.iloc[:, idx].replace('…', pd.NA), errors='coerce'),
        'unit': unit,
    })
    sub = sub.dropna(subset=['price_usd'])
    sub['date'] = pd.PeriodIndex(sub['period'].str.replace('M', '-', regex=False), freq='M').to_timestamp().strftime('%Y-%m-%d')
    sub['source'] = 'World Bank Commodity Price Data (Pink Sheet), Monthly Prices'
    sub['source_url'] = wb_url
    sub['downloaded_at'] = downloaded_at
    sub['worldbank_update_text'] = update_text
    sub = sub[['date', 'period', 'metal', 'metal_name', 'price_usd', 'unit', 'source', 'source_url', 'downloaded_at', 'worldbank_update_text']]
    long_rows.append(sub)

wb_long = pd.concat(long_rows, ignore_index=True)
wb_long_path = RAW_DIR / 'worldbank_nonferrous_metals_monthly_long.csv'
wb_long.to_csv(wb_long_path, index=False, encoding='utf-8-sig')
for metal, sub in wb_long.groupby('metal'):
    sub.to_csv(RAW_DIR / f'worldbank_{metal}_monthly.csv', index=False, encoding='utf-8-sig')

stooq_url = 'https://stooq.com/t/?i=554'
html = requests.get(stooq_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60).text
soup = BeautifulSoup(html, 'html.parser')
stooq_symbols = {
    'HG.F': 'copper', 'O0.F': 'zinc', 'Q0.F': 'nickel', 'Q8.F': 'aluminum',
    'R0.F': 'lead', 'S4.F': 'tin', 'U8.F': 'cobalt'
}
stooq_rows = []
for tr in soup.find_all('tr'):
    cells = [c.get_text(strip=True) for c in tr.find_all(['td', 'th'])]
    if cells and cells[0] in stooq_symbols and len(cells) >= 6:
        stooq_rows.append({
            'symbol': cells[0],
            'metal': stooq_symbols[cells[0]],
            'name': cells[1],
            'last': pd.to_numeric(cells[2].replace(',', ''), errors='coerce'),
            'change_pct': cells[3],
            'change_value': pd.to_numeric(cells[4].replace(',', ''), errors='coerce'),
            'quote_time_or_date': cells[5],
            'source': 'Stooq Metals quote table / Barchart commodities quotes per Stooq disclosure',
            'source_url': stooq_url,
            'downloaded_at': downloaded_at,
        })
stooq_df = pd.DataFrame(stooq_rows)
stooq_path = RAW_DIR / 'stooq_nonferrous_metals_latest.csv'
stooq_df.to_csv(stooq_path, index=False, encoding='utf-8-sig')

yf_targets = {'copper': 'HG=F', 'aluminum': 'ALI=F'}
yf_meta = []
for metal, ticker in yf_targets.items():
    try:
        df = yf.download(ticker, start='2010-01-01', progress=False, auto_adjust=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        if df.empty:
            raise RuntimeError('empty download')
        df = df.reset_index()
        df.columns = [str(c).lower().replace(' ', '_') for c in df.columns]
        if 'date' not in df.columns and 'datetime' in df.columns:
            df = df.rename(columns={'datetime': 'date'})
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df['metal'] = metal
        df['ticker'] = ticker
        df['source'] = 'Yahoo Finance via yfinance'
        df['source_url'] = f'https://finance.yahoo.com/quote/{ticker.replace("=", "%3D")}/'
        df['downloaded_at'] = downloaded_at
        out = RAW_DIR / f'yahoo_{metal}_daily.csv'
        df.to_csv(out, index=False, encoding='utf-8-sig')
        yf_meta.append({'metal': metal, 'ticker': ticker, 'status': 'success', 'rows': len(df), 'start_date': df['date'].min(), 'end_date': df['date'].max(), 'message': ''})
    except Exception as e:
        yf_meta.append({'metal': metal, 'ticker': ticker, 'status': 'failed', 'rows': 0, 'start_date': None, 'end_date': None, 'message': str(e)})
yf_meta_df = pd.DataFrame(yf_meta)
yf_meta_path = RAW_DIR / 'yahoo_nonferrous_metals_metadata.csv'
yf_meta_df.to_csv(yf_meta_path, index=False, encoding='utf-8-sig')

coverage_rows = []
for metal, sub in wb_long.groupby('metal'):
    coverage_rows.append({
        'dataset': 'worldbank_monthly', 'metal': metal, 'source': 'World Bank Pink Sheet',
        'rows': len(sub), 'start_date': sub['date'].min(), 'end_date': sub['date'].max(),
        'unit': sub['unit'].iloc[0], 'source_url': wb_url, 'downloaded_at': downloaded_at,
        'status': 'success', 'note': update_text
    })
for _, row in stooq_df.iterrows():
    coverage_rows.append({
        'dataset': 'stooq_latest', 'metal': row['metal'], 'source': 'Stooq',
        'rows': 1, 'start_date': row['quote_time_or_date'], 'end_date': row['quote_time_or_date'],
        'unit': 'quote table unit as displayed by Stooq/Barchart', 'source_url': stooq_url,
        'downloaded_at': downloaded_at, 'status': 'success', 'note': row['name']
    })
for _, row in yf_meta_df.iterrows():
    coverage_rows.append({
        'dataset': 'yahoo_daily', 'metal': row['metal'], 'source': 'Yahoo Finance via yfinance',
        'rows': int(row['rows']), 'start_date': row['start_date'], 'end_date': row['end_date'],
        'unit': 'exchange-traded futures price; see Yahoo instrument',
        'source_url': f'https://finance.yahoo.com/quote/{row["ticker"].replace("=", "%3D")}/',
        'downloaded_at': downloaded_at, 'status': row['status'], 'note': row['message']
    })
metadata_df = pd.DataFrame(coverage_rows)
metadata_path = RAW_DIR / 'nonferrous_metals_metadata.csv'
metadata_df.to_csv(metadata_path, index=False, encoding='utf-8-sig')

conn = sqlite3.connect(DB_PATH)
wb_long.to_sql('macro_nonferrous_metals_worldbank_monthly', conn, if_exists='replace', index=False)
for metal, sub in wb_long.groupby('metal'):
    sub.to_sql(f'macro_nonferrous_metals_{metal}_monthly', conn, if_exists='replace', index=False)
stooq_df.to_sql('macro_nonferrous_metals_stooq_latest', conn, if_exists='replace', index=False)
yf_meta_df.to_sql('macro_nonferrous_metals_yahoo_metadata', conn, if_exists='replace', index=False)
metadata_df.to_sql('macro_nonferrous_metals_metadata', conn, if_exists='replace', index=False)
for metal in yf_targets:
    csv_path = RAW_DIR / f'yahoo_{metal}_daily.csv'
    if csv_path.exists():
        pd.read_csv(csv_path).to_sql(f'macro_nonferrous_metals_{metal}_daily_yahoo', conn, if_exists='replace', index=False)
cur = conn.cursor()
for table in ['macro_nonferrous_metals_worldbank_monthly'] + [f'macro_nonferrous_metals_{m}_monthly' for m in sorted(wb_long.metal.unique())]:
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date_metal ON {table}(date, metal)')
for table in ['macro_nonferrous_metals_copper_daily_yahoo', 'macro_nonferrous_metals_aluminum_daily_yahoo']:
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date ON {table}(date)')
conn.commit()

verify = []
for table in ['macro_nonferrous_metals_worldbank_monthly', 'macro_nonferrous_metals_stooq_latest', 'macro_nonferrous_metals_metadata', 'macro_nonferrous_metals_copper_daily_yahoo', 'macro_nonferrous_metals_aluminum_daily_yahoo']:
    try:
        row = cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()
        verify.append({'table': table, 'rows': row[0]})
    except Exception as e:
        verify.append({'table': table, 'rows': None, 'error': str(e)})
latest = cur.execute('SELECT metal, MAX(date), COUNT(*) FROM macro_nonferrous_metals_worldbank_monthly GROUP BY metal ORDER BY metal').fetchall()
conn.close()

summary = {
    'downloaded_at': downloaded_at,
    'database': str(DB_PATH),
    'backup': str(backup_path) if backup_path else None,
    'raw_dir': str(RAW_DIR),
    'worldbank_xlsx': str(wb_xlsx),
    'worldbank_long_csv': str(wb_long_path),
    'stooq_latest_csv': str(stooq_path),
    'metadata_csv': str(metadata_path),
    'yahoo_metadata_csv': str(yf_meta_path),
    'worldbank_update_text': update_text,
    'missing_worldbank_metals': missing_wb,
    'verification': verify,
    'worldbank_latest_by_metal': latest,
    'yahoo_downloads': yf_meta,
}
summary_path = RAW_DIR / 'nonferrous_metals_collection_summary.json'
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
