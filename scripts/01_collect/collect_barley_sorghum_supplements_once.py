from pathlib import Path
from datetime import datetime, timezone
from io import StringIO
import json
import re
import shutil
import sqlite3
import time

import pandas as pd
import requests

ROOT = Path(r'C:\claude cowork\01_projects\Anal_reports')
RAW_DIR = ROOT / 'data' / 'raw' / 'macro' / 'grains'
DB_DIR = ROOT / 'data' / 'database'
DB_PATH = DB_DIR / 'quant_data.sqlite'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc).astimezone()
ts = now.strftime('%Y%m%d_%H%M%S')
downloaded_at = now.isoformat(timespec='seconds')

ERS_URL = 'https://www.ers.usda.gov/media/5764/feed-grains-yearbook-tables-all-years.xlsx?v=37284'
FRED_TARGETS = {
    'PBARLUSDM': {'commodity': 'barley', 'unit_or_index_type': 'USD/metric ton', 'description': 'Global price of Barley, FRED/IMF'},
    'WPU01220101': {'commodity': 'barley', 'unit_or_index_type': 'PPI index', 'description': 'BLS PPI: Barley'},
    'WPU01220501': {'commodity': 'sorghum', 'unit_or_index_type': 'PPI index', 'description': 'BLS PPI: Sorghum'},
}


def download_bytes(url, headers=None, timeout=120, min_bytes=1, attempts=5):
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
    return int(m.group(1)) if m else None


def month_date(marketing_year, month_name, marketing_year_start_month):
    start_year = marketing_year_start(marketing_year)
    if start_year is None:
        return None
    month_num = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
    }[month_name.lower()]
    year = start_year if month_num >= marketing_year_start_month else start_year + 1
    return f'{year}-{month_num:02d}-01'


def parse_ers_price_sheet(xlsx_path, sheet_name, commodity_map, month_columns, default_unit, marketing_year_start_month):
    raw_sheet = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None, engine='openpyxl')
    header = raw_sheet.iloc[1].tolist()
    month_col_map = {str(name).strip().lower(): idx for idx, name in enumerate(header)}
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
        marketing_year = str(row.iloc[1]).strip()
        if not re.match(r'^\d{4}/\d{2}$', marketing_year):
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
                'marketing_year': marketing_year,
                'date': month_date(marketing_year, month_name, marketing_year_start_month),
                'month': month_name,
                'value': float(value),
                'unit': spec.get('unit', default_unit),
                'source': 'USDA ERS Feed Grains Yearbook Tables - All Years',
                'source_sheet': sheet_name,
                'source_url': ERS_URL,
                'downloaded_at': downloaded_at,
            })
    return pd.DataFrame(rows)


backup_path = None
if DB_PATH.exists():
    backup_path = DB_DIR / f'quant_data.sqlite.backup_barley_sorghum_{ts}'
    shutil.copy2(DB_PATH, backup_path)

ers_xlsx = RAW_DIR / f'usda_ers_feed_grains_yearbook_all_years_{ts}.xlsx'
ers_content = download_bytes(
    ERS_URL,
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
    marketing_year_start_month=6,
)
ers_farm_df = pd.concat([ers_sorghum_farm, ers_barley_farm], ignore_index=True)
ers_farm_path = RAW_DIR / 'usda_ers_barley_sorghum_farm_price_monthly.csv'
ers_farm_df.to_csv(ers_farm_path, index=False, encoding='utf-8-sig')

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
    marketing_year_start_month=6,
)
ers_cash_df = pd.concat([ers_sorghum_cash, ers_barley_cash], ignore_index=True)
ers_cash_path = RAW_DIR / 'usda_ers_barley_sorghum_cash_price_monthly.csv'
ers_cash_df.to_csv(ers_cash_path, index=False, encoding='utf-8-sig')

fred_rows = []
fred_meta = []
for series_id, spec in FRED_TARGETS.items():
    fred_url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    try:
        content = download_bytes(fred_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=120, min_bytes=100, attempts=3)
        fred_raw_path = RAW_DIR / f'fred_{series_id}.csv'
        fred_raw_path.write_bytes(content)
        fdf = pd.read_csv(StringIO(content.decode('utf-8')))
        fdf = fdf.rename(columns={'observation_date': 'date', series_id: 'value'})
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
fred_path = RAW_DIR / 'fred_barley_sorghum_monthly.csv'
fred_meta_path = RAW_DIR / 'fred_barley_sorghum_metadata.csv'
fred_df.to_csv(fred_path, index=False, encoding='utf-8-sig')
fred_meta_df.to_csv(fred_meta_path, index=False, encoding='utf-8-sig')

metadata_rows = []
for dataset, df in [('usda_ers_farm_price_monthly', ers_farm_df), ('usda_ers_cash_price_monthly', ers_cash_df)]:
    for commodity, sub in df.groupby('commodity'):
        metadata_rows.append({
            'dataset': dataset,
            'commodity': commodity,
            'source': 'USDA ERS Feed Grains Yearbook Tables - All Years',
            'rows': len(sub),
            'start_date': sub['date'].min(),
            'end_date': sub['date'].max(),
            'unit': '; '.join(sorted(set(sub['unit'].dropna().astype(str)))),
            'source_url': ERS_URL,
            'downloaded_at': downloaded_at,
            'status': 'success',
            'note': '; '.join(sorted(set(sub['source_sheet'].dropna().astype(str)))),
        })
for _, row in fred_meta_df.iterrows():
    spec = FRED_TARGETS.get(row['series_id'], {})
    metadata_rows.append({
        'dataset': 'fred_monthly',
        'commodity': spec.get('commodity'),
        'source': 'FRED graph CSV',
        'rows': int(row['rows']),
        'start_date': row['start_date'],
        'end_date': row['end_date'],
        'unit': spec.get('unit_or_index_type'),
        'source_url': f'https://fred.stlouisfed.org/series/{row["series_id"]}',
        'downloaded_at': downloaded_at,
        'status': row['status'],
        'note': row['message'] or spec.get('description'),
    })
metadata_df = pd.DataFrame(metadata_rows)
metadata_path = RAW_DIR / 'barley_sorghum_supplements_metadata.csv'
metadata_df.to_csv(metadata_path, index=False, encoding='utf-8-sig')

conn = sqlite3.connect(DB_PATH)
ers_farm_df.to_sql('macro_grains_usda_ers_farm_price_monthly', conn, if_exists='replace', index=False)
ers_cash_df.to_sql('macro_grains_usda_ers_cash_price_monthly', conn, if_exists='replace', index=False)
fred_df.to_sql('macro_grains_fred_monthly', conn, if_exists='replace', index=False)
fred_meta_df.to_sql('macro_grains_fred_metadata', conn, if_exists='replace', index=False)
metadata_df.to_sql('macro_grains_barley_sorghum_supplements_metadata', conn, if_exists='replace', index=False)
cur = conn.cursor()
for table in ['macro_grains_usda_ers_farm_price_monthly', 'macro_grains_usda_ers_cash_price_monthly', 'macro_grains_fred_monthly']:
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date_commodity ON {table}(date, commodity)')
conn.commit()

verify = []
for table in ['macro_grains_usda_ers_farm_price_monthly', 'macro_grains_usda_ers_cash_price_monthly', 'macro_grains_fred_monthly', 'macro_grains_fred_metadata', 'macro_grains_barley_sorghum_supplements_metadata']:
    verify.append({'table': table, 'rows': cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]})
latest_farm = cur.execute("""
    SELECT commodity, price_type, MAX(date), ROUND(value, 4), unit
    FROM macro_grains_usda_ers_farm_price_monthly
    WHERE date IN (SELECT MAX(date) FROM macro_grains_usda_ers_farm_price_monthly m2 WHERE m2.commodity=macro_grains_usda_ers_farm_price_monthly.commodity AND m2.price_type=macro_grains_usda_ers_farm_price_monthly.price_type)
    GROUP BY commodity, price_type
    ORDER BY commodity, price_type
""").fetchall()
latest_cash = cur.execute("""
    SELECT commodity, market, grade, MAX(date), ROUND(value, 4), unit
    FROM macro_grains_usda_ers_cash_price_monthly
    WHERE date IN (SELECT MAX(date) FROM macro_grains_usda_ers_cash_price_monthly m2 WHERE m2.commodity=macro_grains_usda_ers_cash_price_monthly.commodity AND m2.market=macro_grains_usda_ers_cash_price_monthly.market AND m2.grade=macro_grains_usda_ers_cash_price_monthly.grade)
    GROUP BY commodity, market, grade
    ORDER BY commodity, market, grade
""").fetchall()
latest_fred = cur.execute("""
    SELECT commodity, fred_series_id, MAX(date), ROUND(value, 4), unit_or_index_type
    FROM macro_grains_fred_monthly
    WHERE date IN (SELECT MAX(date) FROM macro_grains_fred_monthly m2 WHERE m2.fred_series_id=macro_grains_fred_monthly.fred_series_id)
    GROUP BY commodity, fred_series_id
    ORDER BY commodity, fred_series_id
""").fetchall()
conn.close()

summary = {
    'downloaded_at': downloaded_at,
    'database': str(DB_PATH),
    'backup': str(backup_path) if backup_path else None,
    'raw_dir': str(RAW_DIR),
    'usda_ers_xlsx': str(ers_xlsx),
    'usda_ers_farm_price_csv': str(ers_farm_path),
    'usda_ers_cash_price_csv': str(ers_cash_path),
    'fred_monthly_csv': str(fred_path),
    'fred_metadata_csv': str(fred_meta_path),
    'metadata_csv': str(metadata_path),
    'verification': verify,
    'latest_farm': latest_farm,
    'latest_cash': latest_cash,
    'latest_fred': latest_fred,
    'fred_downloads': fred_meta,
}
summary_path = RAW_DIR / 'barley_sorghum_supplements_summary.json'
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
