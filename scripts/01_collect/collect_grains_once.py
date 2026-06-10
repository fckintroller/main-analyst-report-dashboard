from pathlib import Path
from datetime import datetime, timezone
import shutil
import sqlite3
import json
import re
import time
from io import StringIO

import requests
import pandas as pd
import yfinance as yf

ROOT = Path(r'C:\claude cowork\01_projects\Anal_reports')
RAW_DIR = ROOT / 'data' / 'raw' / 'macro' / 'grains'
DB_DIR = ROOT / 'data' / 'database'
DB_PATH = DB_DIR / 'quant_data.sqlite'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc).astimezone()
ts = now.strftime('%Y%m%d_%H%M%S')
downloaded_at = now.isoformat(timespec='seconds')

backup_path = None
if DB_PATH.exists():
    backup_path = DB_DIR / f'quant_data.sqlite.backup_grains_{ts}'
    shutil.copy2(DB_PATH, backup_path)


def slugify(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_')


def download_bytes(url, headers=None, timeout=120, min_bytes=1, attempts=4):
    headers = headers or {'User-Agent': 'Mozilla/5.0'}
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            if len(resp.content) < min_bytes:
                raise RuntimeError(f'download too small: {len(resp.content)} bytes')
            return resp.content
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f'failed to download {url}: {last_error}')


def marketing_year_start(marketing_year):
    m = re.match(r'^(\d{4})/(\d{2})$', str(marketing_year).strip())
    if not m:
        return None
    return int(m.group(1))


def month_date(marketing_year, month_name, marketing_year_start_month):
    start_year = marketing_year_start(marketing_year)
    if start_year is None:
        return None
    month_num = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
    }[month_name.lower()]
    # Marketing-year months before the starting month belong to the next calendar year.
    year = start_year if month_num >= marketing_year_start_month else start_year + 1
    return f'{year}-{month_num:02d}-01'


def parse_ers_price_sheet(xlsx_path, sheet_name, commodity_map, month_columns, default_unit, source_url, downloaded_at, marketing_year_start_month):
    raw_sheet = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None, engine='openpyxl')
    header = raw_sheet.iloc[1].tolist()
    month_col_map = {}
    for idx, name in enumerate(header):
        key = str(name).strip().lower()
        if key in [m.lower() for m in month_columns]:
            month_col_map[key] = idx
    rows = []
    current_label = None
    for _, row in raw_sheet.iloc[2:].iterrows():
        first = row.iloc[0]
        if isinstance(first, str):
            stripped = first.strip()
            if stripped.startswith('1/') or stripped.lower().startswith('source:') or stripped.lower().startswith('date run:'):
                break
            if stripped:
                current_label = stripped
        if not current_label or current_label not in commodity_map:
            continue
        marketing_year = row.iloc[1]
        if not re.match(r'^\d{4}/\d{2}$', str(marketing_year).strip()):
            continue
        spec = commodity_map[current_label]
        for month_name in month_columns:
            col = month_col_map.get(month_name.lower())
            if col is None:
                continue
            value = pd.to_numeric(row.iloc[col], errors='coerce')
            if pd.isna(value):
                continue
            rows.append({
                'commodity': spec['commodity'],
                'commodity_name': spec.get('commodity_name', spec['commodity'].title()),
                'price_type': spec.get('price_type', 'price_received_by_farmers'),
                'market': spec.get('market'),
                'grade': spec.get('grade'),
                'marketing_year': str(marketing_year).strip(),
                'date': month_date(str(marketing_year).strip(), month_name, marketing_year_start_month),
                'month': month_name,
                'value': float(value),
                'unit': spec.get('unit', default_unit),
                'source': 'USDA ERS Feed Grains Yearbook Tables - All Years',
                'source_sheet': sheet_name,
                'source_url': source_url,
                'downloaded_at': downloaded_at,
            })
    return pd.DataFrame(rows)

# 1) World Bank Pink Sheet monthly grain/agri prices.
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
wanted = {
    'soybeans': 'Soybeans',
    'soybean_oil': 'Soybean oil',
    'soybean_meal': 'Soybean meal',
    'barley': 'Barley',
    'maize': 'Maize',
    'sorghum': 'Sorghum',
    'rice_thai_5pct': 'Rice, Thai 5%',
    'rice_thai_25pct': 'Rice, Thai 25%',
    'rice_thai_a1': 'Rice, Thai A.1',
    'rice_vietnamese_5pct': 'Rice, Viet Namese 5%',
    'wheat_us_srw': 'Wheat, US SRW',
    'wheat_us_hrw': 'Wheat, US HRW',
}

long_rows = []
missing_wb = []
for slug, label in wanted.items():
    idxs = [i for i, v in names.items() if str(v).strip().lower() == label.strip().lower()]
    if not idxs:
        missing_wb.append(label)
        continue
    idx = idxs[0]
    unit = str(units.iloc[idx]).strip()
    sub = pd.DataFrame({
        'period': data.iloc[:, period_col].astype(str),
        'commodity': slug,
        'commodity_name': label,
        'price_usd': pd.to_numeric(data.iloc[:, idx].replace('…', pd.NA), errors='coerce'),
        'unit': unit,
    })
    sub = sub.dropna(subset=['price_usd'])
    sub['date'] = pd.PeriodIndex(sub['period'].str.replace('M', '-', regex=False), freq='M').to_timestamp().strftime('%Y-%m-%d')
    sub['source'] = 'World Bank Commodity Price Data (Pink Sheet), Monthly Prices'
    sub['source_url'] = wb_url
    sub['downloaded_at'] = downloaded_at
    sub['worldbank_update_text'] = update_text
    sub = sub[['date', 'period', 'commodity', 'commodity_name', 'price_usd', 'unit', 'source', 'source_url', 'downloaded_at', 'worldbank_update_text']]
    long_rows.append(sub)

wb_long = pd.concat(long_rows, ignore_index=True)
wb_long_path = RAW_DIR / 'worldbank_grains_monthly_long.csv'
wb_long.to_csv(wb_long_path, index=False, encoding='utf-8-sig')
for commodity, sub in wb_long.groupby('commodity'):
    sub.to_csv(RAW_DIR / f'worldbank_{commodity}_monthly.csv', index=False, encoding='utf-8-sig')

# 2) Stooq latest grains snapshot. Regex parser avoids heavy JS/ads HTML parsing.
stooq_url = 'https://stooq.com/t/?i=555'
html = requests.get(stooq_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60).text
stooq_symbols = {
    'KE.F': 'hard_red_winter_wheat',
    'ML.F': 'milling_wheat',
    'MW.F': 'spring_wheat_mpls',
    'RS.F': 'canola',
    'XR.F': 'rapeseed',
    'ZC.F': 'corn',
    'ZL.F': 'soybean_oil',
    'ZM.F': 'soybean_meal',
    'ZO.F': 'oats',
    'ZR.F': 'rough_rice',
    'ZS.F': 'soybean',
    'ZW.F': 'wheat',
}
stooq_rows = []
for symbol, commodity in stooq_symbols.items():
    sym_lower = symbol.lower()
    # Row pattern based on Stooq table cells: symbol, name, last, change %, change value, time/date.
    pat = (
        rf'<a href=q/\?s={re.escape(sym_lower)}>{re.escape(symbol)}</a>.*?'
        rf'<td[^>]*align=left>(?P<name>.*?)</td>.*?'
        rf'<span id=aq_{re.escape(sym_lower)}_c\d+>(?P<last>.*?)</span>.*?'
        rf'<span id=aq_{re.escape(sym_lower)}_m1>.*?<span id=c\d+>(?P<change_pct>.*?)</span>.*?'
        rf'<span id=aq_{re.escape(sym_lower)}_m2>.*?<span id=c\d+>(?P<change_value>.*?)</span>.*?'
        rf'<span id=aq_{re.escape(sym_lower)}_t\d+>(?P<quote_time_or_date>.*?)</span>'
    )
    m = re.search(pat, html, flags=re.S | re.I)
    if not m:
        continue
    row = {k: re.sub('<.*?>', '', v).strip() for k, v in m.groupdict().items()}
    stooq_rows.append({
        'symbol': symbol,
        'commodity': commodity,
        'name': row['name'],
        'last': pd.to_numeric(row['last'].replace(',', ''), errors='coerce'),
        'change_pct': row['change_pct'],
        'change_value': pd.to_numeric(row['change_value'].replace(',', ''), errors='coerce'),
        'quote_time_or_date': row['quote_time_or_date'],
        'source': 'Stooq Grains quote table / Barchart commodities quotes per Stooq disclosure',
        'source_url': stooq_url,
        'downloaded_at': downloaded_at,
    })
stooq_df = pd.DataFrame(stooq_rows)
stooq_path = RAW_DIR / 'stooq_grains_latest.csv'
stooq_df.to_csv(stooq_path, index=False, encoding='utf-8-sig')

# 3) Yahoo Finance daily futures where symbols are available.
yf_targets = {
    'corn': 'ZC=F',
    'hard_red_winter_wheat': 'KE=F',
    'wheat_cbot': 'ZW=F',
    'soybean': 'ZS=F',
    'soybean_oil': 'ZL=F',
    'soybean_meal': 'ZM=F',
    'rough_rice': 'ZR=F',
    'oats': 'ZO=F',
}
yf_meta = []
for commodity, ticker in yf_targets.items():
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
        df['commodity'] = commodity
        df['ticker'] = ticker
        df['source'] = 'Yahoo Finance via yfinance'
        df['source_url'] = f'https://finance.yahoo.com/quote/{ticker.replace("=", "%3D")}/'
        df['downloaded_at'] = downloaded_at
        out = RAW_DIR / f'yahoo_{commodity}_daily.csv'
        df.to_csv(out, index=False, encoding='utf-8-sig')
        yf_meta.append({'commodity': commodity, 'ticker': ticker, 'status': 'success', 'rows': len(df), 'start_date': df['date'].min(), 'end_date': df['date'].max(), 'message': ''})
    except Exception as e:
        yf_meta.append({'commodity': commodity, 'ticker': ticker, 'status': 'failed', 'rows': 0, 'start_date': None, 'end_date': None, 'message': str(e)})
yf_meta_df = pd.DataFrame(yf_meta)
yf_meta_path = RAW_DIR / 'yahoo_grains_metadata.csv'
yf_meta_df.to_csv(yf_meta_path, index=False, encoding='utf-8-sig')

# 4) USDA ERS and FRED supplements for stale Barley/Sorghum World Bank series.
ers_url = 'https://www.ers.usda.gov/media/5764/feed-grains-yearbook-tables-all-years.xlsx?v=37284'
ers_xlsx = RAW_DIR / f'usda_ers_feed_grains_yearbook_all_years_{ts}.xlsx'
ers_content = download_bytes(
    ers_url,
    headers={'User-Agent': 'Mozilla/5.0', 'Connection': 'close'},
    timeout=180,
    min_bytes=800_000,
    attempts=5,
)
ers_xlsx.write_bytes(ers_content)

sorghum_months = ['September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August']
barley_months = ['June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May']

ers_sorghum_farm = parse_ers_price_sheet(
    ers_xlsx,
    'FGYearbookTable09',
    {'Sorghum, dollars per bushel': {'commodity': 'sorghum', 'commodity_name': 'Sorghum', 'unit': 'USD/bushel'}},
    sorghum_months,
    'USD/bushel',
    ers_url,
    downloaded_at,
    marketing_year_start_month=9,
)
ers_barley_farm = parse_ers_price_sheet(
    ers_xlsx,
    'FGYearbookTable10',
    {
        'Barley': {'commodity': 'barley', 'commodity_name': 'Barley', 'price_type': 'price_received_by_farmers_all_barley', 'unit': 'USD/bushel'},
        'Feed barley': {'commodity': 'barley', 'commodity_name': 'Feed barley', 'price_type': 'price_received_by_farmers_feed_barley', 'unit': 'USD/bushel'},
        'Malting barley': {'commodity': 'barley', 'commodity_name': 'Malting barley', 'price_type': 'price_received_by_farmers_malting_barley', 'unit': 'USD/bushel'},
    },
    barley_months,
    'USD/bushel',
    ers_url,
    downloaded_at,
    marketing_year_start_month=6,
)
ers_farm_df = pd.concat([ers_sorghum_farm, ers_barley_farm], ignore_index=True)
ers_farm_df.to_csv(RAW_DIR / 'usda_ers_barley_sorghum_farm_price_monthly.csv', index=False, encoding='utf-8-sig')

ers_sorghum_cash = parse_ers_price_sheet(
    ers_xlsx,
    'FGYearbookTable13',
    {
        'No. 2 yellow, Gulf Coast Ports, TX': {'commodity': 'sorghum', 'commodity_name': 'Sorghum', 'price_type': 'cash_price', 'market': 'Gulf Coast Ports, TX', 'grade': 'No. 2 yellow', 'unit': 'USD/cwt'},
        'No. 2 yellow, Kansas City, MO': {'commodity': 'sorghum', 'commodity_name': 'Sorghum', 'price_type': 'cash_price', 'market': 'Kansas City, MO', 'grade': 'No. 2 yellow', 'unit': 'USD/cwt'},
        'No. 2 yellow, Central Kansas, KS': {'commodity': 'sorghum', 'commodity_name': 'Sorghum', 'price_type': 'cash_price', 'market': 'Central Kansas, KS', 'grade': 'No. 2 yellow', 'unit': 'USD/cwt'},
    },
    sorghum_months,
    'USD/cwt',
    ers_url,
    downloaded_at,
    marketing_year_start_month=9,
)
ers_barley_cash = parse_ers_price_sheet(
    ers_xlsx,
    'FGYearbookTable14',
    {
        'Barley, No. 2 feed, Golden Triangle, MT': {'commodity': 'barley', 'commodity_name': 'Barley', 'price_type': 'cash_price', 'market': 'Golden Triangle, MT', 'grade': 'No. 2 feed', 'unit': 'USD/bushel'},
        'Barley, No. 2 or better malting, Golden Triangle, MT': {'commodity': 'barley', 'commodity_name': 'Barley', 'price_type': 'cash_price', 'market': 'Golden Triangle, MT', 'grade': 'No. 2 or better malting', 'unit': 'USD/bushel'},
    },
    barley_months,
    'USD/bushel',
    ers_url,
    downloaded_at,
    marketing_year_start_month=6,
)
ers_cash_df = pd.concat([ers_sorghum_cash, ers_barley_cash], ignore_index=True)
ers_cash_df.to_csv(RAW_DIR / 'usda_ers_barley_sorghum_cash_price_monthly.csv', index=False, encoding='utf-8-sig')

fred_targets = {
    'PBARLUSDM': {'commodity': 'barley', 'unit_or_index_type': 'USD/metric ton', 'description': 'Global price of Barley, FRED/IMF'},
    'WPU01220101': {'commodity': 'barley', 'unit_or_index_type': 'PPI index', 'description': 'BLS PPI: Barley'},
    'WPU01220501': {'commodity': 'sorghum', 'unit_or_index_type': 'PPI index', 'description': 'BLS PPI: Sorghum'},
}
fred_rows = []
fred_meta = []
for series_id, spec in fred_targets.items():
    fred_url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    try:
        content = download_bytes(fred_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=120, min_bytes=100, attempts=3)
        fred_raw_path = RAW_DIR / f'fred_{series_id}.csv'
        fred_raw_path.write_bytes(content)
        fdf = pd.read_csv(StringIO(content.decode('utf-8')))
        value_col = series_id
        fdf = fdf.rename(columns={'observation_date': 'date', value_col: 'value'})
        fdf['value'] = pd.to_numeric(fdf['value'].replace('.', pd.NA), errors='coerce')
        fdf = fdf.dropna(subset=['value'])
        for _, row in fdf.iterrows():
            fred_rows.append({
                'commodity': spec['commodity'],
                'fred_series_id': series_id,
                'date': row['date'],
                'value': float(row['value']),
                'unit_or_index_type': spec['unit_or_index_type'],
                'description': spec['description'],
                'source': 'FRED graph CSV',
                'source_url': fred_url,
                'downloaded_at': downloaded_at,
            })
        fred_meta.append({'series_id': series_id, 'status': 'success', 'rows': len(fdf), 'start_date': fdf['date'].min(), 'end_date': fdf['date'].max(), 'message': ''})
    except Exception as exc:
        fred_meta.append({'series_id': series_id, 'status': 'failed', 'rows': 0, 'start_date': None, 'end_date': None, 'message': str(exc)})
fred_df = pd.DataFrame(fred_rows)
fred_meta_df = pd.DataFrame(fred_meta)
fred_df.to_csv(RAW_DIR / 'fred_barley_sorghum_monthly.csv', index=False, encoding='utf-8-sig')
fred_meta_df.to_csv(RAW_DIR / 'fred_barley_sorghum_metadata.csv', index=False, encoding='utf-8-sig')

# 5) Metadata.
coverage_rows = []
for commodity, sub in wb_long.groupby('commodity'):
    coverage_rows.append({
        'dataset': 'worldbank_monthly', 'commodity': commodity, 'source': 'World Bank Pink Sheet',
        'rows': len(sub), 'start_date': sub['date'].min(), 'end_date': sub['date'].max(),
        'unit': sub['unit'].iloc[0], 'source_url': wb_url, 'downloaded_at': downloaded_at,
        'status': 'success', 'note': update_text
    })
for _, row in stooq_df.iterrows():
    coverage_rows.append({
        'dataset': 'stooq_latest', 'commodity': row['commodity'], 'source': 'Stooq',
        'rows': 1, 'start_date': row['quote_time_or_date'], 'end_date': row['quote_time_or_date'],
        'unit': 'quote table unit as displayed by Stooq/Barchart', 'source_url': stooq_url,
        'downloaded_at': downloaded_at, 'status': 'success', 'note': row['name']
    })
for _, row in yf_meta_df.iterrows():
    coverage_rows.append({
        'dataset': 'yahoo_daily', 'commodity': row['commodity'], 'source': 'Yahoo Finance via yfinance',
        'rows': int(row['rows']), 'start_date': row['start_date'], 'end_date': row['end_date'],
        'unit': 'exchange-traded futures price; see Yahoo instrument',
        'source_url': f'https://finance.yahoo.com/quote/{row["ticker"].replace("=", "%3D")}/',
        'downloaded_at': downloaded_at, 'status': row['status'], 'note': row['message']
    })
for (dataset, source_df, unit_col) in [
    ('usda_ers_farm_price_monthly', ers_farm_df, 'unit'),
    ('usda_ers_cash_price_monthly', ers_cash_df, 'unit'),
]:
    if not source_df.empty:
        for commodity, sub in source_df.groupby('commodity'):
            coverage_rows.append({
                'dataset': dataset, 'commodity': commodity, 'source': 'USDA ERS Feed Grains Yearbook Tables - All Years',
                'rows': len(sub), 'start_date': sub['date'].min(), 'end_date': sub['date'].max(),
                'unit': '; '.join(sorted(set(sub[unit_col].dropna().astype(str)))), 'source_url': ers_url,
                'downloaded_at': downloaded_at, 'status': 'success', 'note': '; '.join(sorted(set(sub['source_sheet'].dropna().astype(str))))
            })
for _, row in fred_meta_df.iterrows():
    spec = fred_targets.get(row['series_id'], {})
    coverage_rows.append({
        'dataset': 'fred_monthly', 'commodity': spec.get('commodity'), 'source': 'FRED graph CSV',
        'rows': int(row['rows']), 'start_date': row['start_date'], 'end_date': row['end_date'],
        'unit': spec.get('unit_or_index_type'), 'source_url': f'https://fred.stlouisfed.org/series/{row["series_id"]}',
        'downloaded_at': downloaded_at, 'status': row['status'], 'note': row['message'] or spec.get('description')
    })
metadata_df = pd.DataFrame(coverage_rows)
metadata_path = RAW_DIR / 'grains_metadata.csv'
metadata_df.to_csv(metadata_path, index=False, encoding='utf-8-sig')

# 5) SQLite load.
conn = sqlite3.connect(DB_PATH)
wb_long.to_sql('macro_grains_worldbank_monthly', conn, if_exists='replace', index=False)
for commodity, sub in wb_long.groupby('commodity'):
    sub.to_sql(f'macro_grains_{commodity}_monthly', conn, if_exists='replace', index=False)
stooq_df.to_sql('macro_grains_stooq_latest', conn, if_exists='replace', index=False)
yf_meta_df.to_sql('macro_grains_yahoo_metadata', conn, if_exists='replace', index=False)
ers_farm_df.to_sql('macro_grains_usda_ers_farm_price_monthly', conn, if_exists='replace', index=False)
ers_cash_df.to_sql('macro_grains_usda_ers_cash_price_monthly', conn, if_exists='replace', index=False)
fred_df.to_sql('macro_grains_fred_monthly', conn, if_exists='replace', index=False)
fred_meta_df.to_sql('macro_grains_fred_metadata', conn, if_exists='replace', index=False)
metadata_df.to_sql('macro_grains_metadata', conn, if_exists='replace', index=False)
for commodity in yf_targets:
    csv_path = RAW_DIR / f'yahoo_{commodity}_daily.csv'
    if csv_path.exists():
        pd.read_csv(csv_path).to_sql(f'macro_grains_{commodity}_daily_yahoo', conn, if_exists='replace', index=False)
cur = conn.cursor()
for table in ['macro_grains_worldbank_monthly'] + [f'macro_grains_{c}_monthly' for c in sorted(wb_long.commodity.unique())]:
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date_commodity ON {table}(date, commodity)')
for table in ['macro_grains_usda_ers_farm_price_monthly', 'macro_grains_usda_ers_cash_price_monthly', 'macro_grains_fred_monthly']:
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date_commodity ON {table}(date, commodity)')
for commodity in yf_targets:
    table = f'macro_grains_{commodity}_daily_yahoo'
    try:
        cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date ON {table}(date)')
    except sqlite3.OperationalError:
        pass
conn.commit()

verify = []
base_verify = [
    'macro_grains_worldbank_monthly',
    'macro_grains_stooq_latest',
    'macro_grains_metadata',
    'macro_grains_usda_ers_farm_price_monthly',
    'macro_grains_usda_ers_cash_price_monthly',
    'macro_grains_fred_monthly',
    'macro_grains_fred_metadata',
]
base_verify += [f'macro_grains_{commodity}_daily_yahoo' for commodity in yf_targets]
for table in base_verify:
    try:
        row = cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()
        verify.append({'table': table, 'rows': row[0]})
    except Exception as e:
        verify.append({'table': table, 'rows': None, 'error': str(e)})
latest = cur.execute('SELECT commodity, MAX(date), COUNT(*) FROM macro_grains_worldbank_monthly GROUP BY commodity ORDER BY commodity').fetchall()
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
    'usda_ers_xlsx': str(ers_xlsx),
    'usda_ers_farm_price_csv': str(RAW_DIR / 'usda_ers_barley_sorghum_farm_price_monthly.csv'),
    'usda_ers_cash_price_csv': str(RAW_DIR / 'usda_ers_barley_sorghum_cash_price_monthly.csv'),
    'fred_monthly_csv': str(RAW_DIR / 'fred_barley_sorghum_monthly.csv'),
    'worldbank_update_text': update_text,
    'missing_worldbank_commodities': missing_wb,
    'stooq_rows': len(stooq_df),
    'verification': verify,
    'worldbank_latest_by_commodity': latest,
    'usda_ers_farm_latest_by_commodity': ers_farm_df.groupby(['commodity', 'price_type'])['date'].max().reset_index().values.tolist() if not ers_farm_df.empty else [],
    'usda_ers_cash_latest_by_commodity': ers_cash_df.groupby(['commodity', 'market', 'grade'])['date'].max().reset_index().values.tolist() if not ers_cash_df.empty else [],
    'fred_downloads': fred_meta,
    'yahoo_downloads': yf_meta,
}
summary_path = RAW_DIR / 'grains_collection_summary.json'
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
