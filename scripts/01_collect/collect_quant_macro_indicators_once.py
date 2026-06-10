from pathlib import Path
from datetime import datetime, timezone
from io import StringIO
import json
import shutil
import sqlite3
import time

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(r'C:\claude cowork\01_projects\Anal_reports')
RAW_DIR = ROOT / 'data' / 'raw' / 'macro' / 'quant_macro_indicators'
DB_DIR = ROOT / 'data' / 'database'
DB_PATH = DB_DIR / 'quant_data.sqlite'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc).astimezone()
ts = now.strftime('%Y%m%d_%H%M%S')
downloaded_at = now.isoformat(timespec='seconds')

YAHOO_SERIES = {
    '^VIX': {
        'indicator': 'vix', 'name': 'CBOE Volatility Index', 'frequency': 'daily',
        'category': 'risk_sentiment', 'unit': 'Index', 'source': 'Yahoo Finance',
    },
    '^MOVE': {
        'indicator': 'move', 'name': 'ICE BofAML MOVE Index', 'frequency': 'daily',
        'category': 'bond_volatility', 'unit': 'Index', 'source': 'Yahoo Finance',
    },
    'DX-Y.NYB': {
        'indicator': 'dxy', 'name': 'U.S. Dollar Index', 'frequency': 'daily',
        'category': 'fx_liquidity', 'unit': 'Index', 'source': 'Yahoo Finance',
    },
}

# FRED is useful but can be slow/unavailable from this environment. The script tries short requests
# and records failures in metadata instead of blocking the whole collection.
FRED_SERIES = {
    'T10Y3M': {'indicator': 'us_10y_3m_spread', 'name': '10-Year Treasury Minus 3-Month Treasury', 'frequency': 'daily', 'category': 'yield_curve', 'unit': 'Percent', 'source': 'FRED'},
    'NFCI': {'indicator': 'chicago_fed_nfci', 'name': 'Chicago Fed National Financial Conditions Index', 'frequency': 'weekly', 'category': 'financial_conditions', 'unit': 'Index', 'source': 'FRED'},
    'ANFCI': {'indicator': 'chicago_fed_anfci', 'name': 'Chicago Fed Adjusted National Financial Conditions Index', 'frequency': 'weekly', 'category': 'financial_conditions', 'unit': 'Index', 'source': 'FRED'},
    'DFII10': {'indicator': 'us_10y_real_rate', 'name': '10-Year Treasury Inflation-Indexed Security', 'frequency': 'daily', 'category': 'real_rates', 'unit': 'Percent', 'source': 'FRED'},
    'T10YIE': {'indicator': 'us_10y_breakeven_inflation', 'name': '10-Year Breakeven Inflation Rate', 'frequency': 'daily', 'category': 'inflation_expectations', 'unit': 'Percent', 'source': 'FRED'},
    'BAMLC0A0CM': {'indicator': 'us_ig_oas', 'name': 'ICE BofA US Corporate Index OAS', 'frequency': 'daily', 'category': 'credit_spread', 'unit': 'Percent', 'source': 'FRED'},
    'KORLOLITOAASTSAM': {'indicator': 'korea_oecd_cli', 'name': 'OECD CLI Amplitude Adjusted: Korea', 'frequency': 'monthly', 'category': 'leading_indicator', 'unit': 'Index', 'source': 'FRED/OECD'},
    'USALOLITOAASTSAM': {'indicator': 'us_oecd_cli', 'name': 'OECD CLI Amplitude Adjusted: United States', 'frequency': 'monthly', 'category': 'leading_indicator', 'unit': 'Index', 'source': 'FRED/OECD'},
    'CHNLOLITOAASTSAM': {'indicator': 'china_oecd_cli', 'name': 'OECD CLI Amplitude Adjusted: China', 'frequency': 'monthly', 'category': 'leading_indicator', 'unit': 'Index', 'source': 'FRED/OECD'},
    'JPNLOLITOAASTSAM': {'indicator': 'japan_oecd_cli', 'name': 'OECD CLI Amplitude Adjusted: Japan', 'frequency': 'monthly', 'category': 'leading_indicator', 'unit': 'Index', 'source': 'FRED/OECD'},
    'XTIMVA01KRM667S': {'indicator': 'korea_imports', 'name': 'Korea Merchandise Imports', 'frequency': 'monthly', 'category': 'trade', 'unit': 'USD, exchange-rate converted', 'source': 'FRED/OECD'},
}

EXISTING_SERIES = {
    'macro_macro_indices_dgs10': {'value_col': 'DGS10', 'date_col': 'DATE', 'indicator': 'us_10y_yield', 'name': 'U.S. 10-Year Treasury Constant Maturity', 'frequency': 'daily', 'category': 'rates', 'unit': 'Percent'},
    'macro_macro_indices_dgs2': {'value_col': 'DGS2', 'date_col': 'DATE', 'indicator': 'us_2y_yield', 'name': 'U.S. 2-Year Treasury Constant Maturity', 'frequency': 'daily', 'category': 'rates', 'unit': 'Percent'},
    'macro_macro_indices_bamlh0a0hym2': {'value_col': 'BAMLH0A0HYM2', 'date_col': 'DATE', 'indicator': 'us_high_yield_oas', 'name': 'ICE BofA US High Yield OAS', 'frequency': 'daily', 'category': 'credit_spread', 'unit': 'Percent'},
    'macro_macro_indices_cpiaucsl': {'value_col': 'CPIAUCSL', 'date_col': 'DATE', 'indicator': 'us_cpi', 'name': 'U.S. CPI All Urban Consumers', 'frequency': 'monthly', 'category': 'inflation', 'unit': 'Index 1982-84=100'},
    'macro_macro_indices_unrate': {'value_col': 'UNRATE', 'date_col': 'DATE', 'indicator': 'us_unemployment_rate', 'name': 'U.S. Unemployment Rate', 'frequency': 'monthly', 'category': 'labor', 'unit': 'Percent'},
    'macro_macro_indices_m2sl': {'value_col': 'M2SL', 'date_col': 'DATE', 'indicator': 'us_m2', 'name': 'U.S. M2 Money Stock', 'frequency': 'monthly', 'category': 'liquidity', 'unit': 'Billions of USD'},
    'macro_macro_indices_walcl': {'value_col': 'WALCL', 'date_col': 'DATE', 'indicator': 'fed_total_assets', 'name': 'Federal Reserve Total Assets', 'frequency': 'weekly', 'category': 'liquidity', 'unit': 'Millions of USD'},
    'macro_macro_indices_kor_exports': {'value_col': 'XTEXVA01KRM667S', 'date_col': 'DATE', 'indicator': 'korea_exports', 'name': 'Korea Merchandise Exports', 'frequency': 'monthly', 'category': 'trade', 'unit': 'USD, exchange-rate converted'},
}


def flatten_yahoo_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower().replace(' ', '_') for c in df.columns]
    else:
        df.columns = [str(c).lower().replace(' ', '_') for c in df.columns]
    return df


def fetch_yahoo():
    rows, meta = [], []
    for ticker, spec in YAHOO_SERIES.items():
        try:
            df = yf.download(ticker, start='2010-01-01', progress=False, auto_adjust=False, timeout=30)
            if df.empty:
                raise RuntimeError('empty dataframe')
            df = flatten_yahoo_columns(df).reset_index()
            date_col = 'Date' if 'Date' in df.columns else 'date'
            df = df.rename(columns={date_col: 'date'})
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            df['ticker'] = ticker
            df['indicator'] = spec['indicator']
            df['indicator_name'] = spec['name']
            df['category'] = spec['category']
            df['frequency'] = spec['frequency']
            df['unit'] = spec['unit']
            df['source'] = spec['source']
            df['source_url'] = f'https://finance.yahoo.com/quote/{ticker}'
            df['downloaded_at'] = downloaded_at
            keep = ['date', 'indicator', 'indicator_name', 'category', 'frequency', 'ticker', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'unit', 'source', 'source_url', 'downloaded_at']
            for c in keep:
                if c not in df.columns:
                    df[c] = pd.NA
            out = df[keep].copy()
            out.to_csv(RAW_DIR / f'yahoo_{spec["indicator"]}.csv', index=False, encoding='utf-8-sig')
            rows.append(out)
            meta.append({**spec, 'series_id': ticker, 'status': 'success', 'rows': len(out), 'start_date': out['date'].min(), 'end_date': out['date'].max(), 'message': ''})
        except Exception as exc:
            meta.append({**spec, 'series_id': ticker, 'status': 'failed', 'rows': 0, 'start_date': None, 'end_date': None, 'message': str(exc)})
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(), meta)


def fetch_fred_short(series_id, timeout=12):
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Connection': 'close'}, timeout=(5, timeout))
    r.raise_for_status()
    if len(r.text) < 20:
        raise RuntimeError(f'response too small: {len(r.text)} chars')
    return r.text


def fetch_fred():
    rows, meta = [], []
    for series_id, spec in FRED_SERIES.items():
        try:
            text = fetch_fred_short(series_id)
            (RAW_DIR / f'fred_{series_id}.csv').write_text(text, encoding='utf-8')
            df = pd.read_csv(StringIO(text))
            df = df.rename(columns={'observation_date': 'date', series_id: 'value'})
            df['value'] = pd.to_numeric(df['value'].replace('.', pd.NA), errors='coerce')
            df = df.dropna(subset=['value']).copy()
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            df['indicator'] = spec['indicator']
            df['indicator_name'] = spec['name']
            df['category'] = spec['category']
            df['frequency'] = spec['frequency']
            df['series_id'] = series_id
            df['unit'] = spec['unit']
            df['source'] = spec['source']
            df['source_url'] = f'https://fred.stlouisfed.org/series/{series_id}'
            df['downloaded_at'] = downloaded_at
            out = df[['date','indicator','indicator_name','category','frequency','series_id','value','unit','source','source_url','downloaded_at']].copy()
            rows.append(out)
            meta.append({**spec, 'series_id': series_id, 'status': 'success', 'rows': len(out), 'start_date': out['date'].min(), 'end_date': out['date'].max(), 'message': ''})
        except Exception as exc:
            meta.append({**spec, 'series_id': series_id, 'status': 'failed', 'rows': 0, 'start_date': None, 'end_date': None, 'message': str(exc)[:300]})
        time.sleep(0.5)
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(), meta)


def read_existing(conn):
    rows, meta = [], []
    cur = conn.cursor()
    for table, spec in EXISTING_SERIES.items():
        exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not exists:
            meta.append({**spec, 'series_id': table, 'source': 'Existing SQLite table', 'status': 'missing', 'rows': 0, 'start_date': None, 'end_date': None, 'message': 'table not found'})
            continue
        try:
            df = pd.read_sql_query(f'SELECT "{spec["date_col"]}" AS date, "{spec["value_col"]}" AS value FROM "{table}"', conn)
            df['value'] = pd.to_numeric(df['value'].replace('.', pd.NA), errors='coerce')
            df = df.dropna(subset=['value']).copy()
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
            df = df.dropna(subset=['date']).copy()
            df['indicator'] = spec['indicator']
            df['indicator_name'] = spec['name']
            df['category'] = spec['category']
            df['frequency'] = spec['frequency']
            df['series_id'] = table
            df['unit'] = spec['unit']
            df['source'] = 'Existing SQLite table'
            df['source_url'] = ''
            df['downloaded_at'] = downloaded_at
            out = df[['date','indicator','indicator_name','category','frequency','series_id','value','unit','source','source_url','downloaded_at']].copy()
            rows.append(out)
            meta.append({**spec, 'series_id': table, 'source': 'Existing SQLite table', 'status': 'success', 'rows': len(out), 'start_date': out['date'].min(), 'end_date': out['date'].max(), 'message': ''})
        except Exception as exc:
            meta.append({**spec, 'series_id': table, 'source': 'Existing SQLite table', 'status': 'failed', 'rows': 0, 'start_date': None, 'end_date': None, 'message': str(exc)[:300]})
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(), meta)


def read_market_from_global_indices(conn):
    # Korea index levels were confirmed by the user as intentional/correct for this workspace,
    # so KOSPI/KOSDAQ momentum is included in quant factor calculation.
    mapping = {
        'us_sp500': {'table': 'macro_global_indices_us_sp500_daily', 'date_col': 'date', 'value_col': 'close', 'name': 'S&P 500'},
        'korea_kospi': {'table': 'macro_indices_kospi', 'date_col': 'Date', 'value_col': 'Close', 'name': 'KOSPI'},
        'korea_kosdaq': {'table': 'macro_indices_kosdaq', 'date_col': 'Date', 'value_col': 'Close', 'name': 'KOSDAQ'},
    }
    rows = []
    cur = conn.cursor()
    for indicator, spec in mapping.items():
        table = spec['table']
        if not cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            continue
        df = pd.read_sql_query(f'SELECT "{spec["date_col"]}" AS date, "{spec["value_col"]}" AS close FROM "{table}"', conn)
        df['value'] = pd.to_numeric(df['close'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
        df = df.dropna(subset=['date','value']).copy()
        df['indicator'] = indicator
        df['indicator_name'] = spec['name']
        df['category'] = 'equity_index'
        df['frequency'] = 'daily'
        df['series_id'] = table
        df['unit'] = 'Index'
        df['source'] = 'Existing SQLite table'
        df['source_url'] = ''
        df['downloaded_at'] = downloaded_at
        rows.append(df[['date','indicator','indicator_name','category','frequency','series_id','value','unit','source','source_url','downloaded_at']])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_factors(market_daily, existing_long, fred_long):
    # Daily factor table: pivot daily indicators and calculate spreads, z-scores, momentum.
    parts = []
    if not market_daily.empty:
        y = market_daily[['date','indicator','close']].rename(columns={'close':'value'})
        parts.append(y)
    if not existing_long.empty:
        parts.append(existing_long[['date','indicator','value']])
    if not fred_long.empty:
        parts.append(fred_long[['date','indicator','value']])
    if not parts:
        return pd.DataFrame(), pd.DataFrame()
    base = pd.concat(parts, ignore_index=True)
    base['date'] = pd.to_datetime(base['date'])
    piv = base.pivot_table(index='date', columns='indicator', values='value', aggfunc='last').sort_index()

    factors = pd.DataFrame(index=piv.index)
    if {'us_10y_yield','us_2y_yield'}.issubset(piv.columns):
        factors['us_10y_2y_spread'] = piv['us_10y_yield'] - piv['us_2y_yield']
    if 'us_10y_3m_spread' in piv.columns:
        factors['us_10y_3m_spread'] = piv['us_10y_3m_spread']
    for col in ['vix','move','dxy','us_high_yield_oas','us_ig_oas']:
        if col in piv.columns:
            factors[f'{col}_zscore_252d'] = (piv[col] - piv[col].rolling(252, min_periods=60).mean()) / piv[col].rolling(252, min_periods=60).std()
    for col in ['dxy','us_sp500','korea_kospi','korea_kosdaq','vix','move']:
        if col in piv.columns:
            factors[f'{col}_ret_60d_pct'] = piv[col].pct_change(60, fill_method=None) * 100
    if {'vix','us_high_yield_oas','dxy'}.issubset(piv.columns):
        vz = (piv['vix'] - piv['vix'].rolling(252, min_periods=60).mean()) / piv['vix'].rolling(252, min_periods=60).std()
        hz = (piv['us_high_yield_oas'] - piv['us_high_yield_oas'].rolling(252, min_periods=60).mean()) / piv['us_high_yield_oas'].rolling(252, min_periods=60).std()
        dz = (piv['dxy'] - piv['dxy'].rolling(252, min_periods=60).mean()) / piv['dxy'].rolling(252, min_periods=60).std()
        factors['risk_off_composite_z'] = pd.concat([vz, hz, dz], axis=1).mean(axis=1)
    daily = factors.reset_index().melt(id_vars='date', var_name='factor', value_name='value').dropna()
    daily['date'] = daily['date'].dt.strftime('%Y-%m-%d')
    daily['frequency'] = 'daily'
    daily['downloaded_at'] = downloaded_at

    # Monthly factor table: end-of-month resample of macro indicators.
    monthly_cols = [c for c in ['us_cpi','us_unemployment_rate','us_m2','fed_total_assets','korea_exports','korea_imports','korea_oecd_cli','us_oecd_cli','china_oecd_cli','japan_oecd_cli'] if c in piv.columns]
    mf = pd.DataFrame()
    if monthly_cols:
        mp = piv[monthly_cols].resample('ME').last()
        out = pd.DataFrame(index=mp.index)
        for col in ['us_cpi','us_m2','fed_total_assets','korea_exports','korea_imports']:
            if col in mp.columns:
                out[f'{col}_yoy_pct'] = mp[col].pct_change(12, fill_method=None) * 100
        if 'us_unemployment_rate' in mp.columns:
            out['us_unemployment_rate_chg_12m'] = mp['us_unemployment_rate'] - mp['us_unemployment_rate'].shift(12)
        for col in ['korea_oecd_cli','us_oecd_cli','china_oecd_cli','japan_oecd_cli']:
            if col in mp.columns:
                out[f'{col}_chg_3m'] = mp[col] - mp[col].shift(3)
        if {'korea_exports','korea_imports'}.issubset(mp.columns):
            out['korea_trade_balance_value'] = mp['korea_exports'] - mp['korea_imports']
        mf = out.reset_index().melt(id_vars='date', var_name='factor', value_name='value').dropna()
        mf['date'] = mf['date'].dt.strftime('%Y-%m-%d')
        mf['frequency'] = 'monthly'
        mf['downloaded_at'] = downloaded_at
    return daily, mf


backup_path = None
if DB_PATH.exists():
    backup_path = DB_DIR / f'quant_data.sqlite.backup_quant_macro_{ts}'
    shutil.copy2(DB_PATH, backup_path)

conn = sqlite3.connect(DB_PATH)
yahoo_daily, yahoo_meta = fetch_yahoo()
fred_long, fred_meta = fetch_fred()
existing_long, existing_meta = read_existing(conn)
market_existing = read_market_from_global_indices(conn)

# Add market index close series to indicator long table for factor reproducibility.
indicator_long = pd.concat([existing_long, fred_long, market_existing], ignore_index=True) if any(not x.empty for x in [existing_long, fred_long, market_existing]) else pd.DataFrame()
metadata = pd.DataFrame(yahoo_meta + fred_meta + existing_meta)

daily_factors, monthly_factors = build_factors(yahoo_daily, indicator_long, fred_long)

# Persist raw combined files.
yahoo_daily.to_csv(RAW_DIR / 'quant_macro_yahoo_daily.csv', index=False, encoding='utf-8-sig')
indicator_long.to_csv(RAW_DIR / 'quant_macro_indicator_long.csv', index=False, encoding='utf-8-sig')
metadata.to_csv(RAW_DIR / 'quant_macro_metadata.csv', index=False, encoding='utf-8-sig')
daily_factors.to_csv(RAW_DIR / 'quant_macro_factors_daily.csv', index=False, encoding='utf-8-sig')
monthly_factors.to_csv(RAW_DIR / 'quant_macro_factors_monthly.csv', index=False, encoding='utf-8-sig')

# SQLite tables.
yahoo_daily.to_sql('macro_quant_market_indicators_daily', conn, if_exists='replace', index=False)
indicator_long.to_sql('macro_quant_indicators_long', conn, if_exists='replace', index=False)
metadata.to_sql('macro_quant_metadata', conn, if_exists='replace', index=False)
daily_factors.to_sql('macro_quant_factors_daily', conn, if_exists='replace', index=False)
monthly_factors.to_sql('macro_quant_factors_monthly', conn, if_exists='replace', index=False)
cur = conn.cursor()
for table, cols in {
    'macro_quant_market_indicators_daily': 'date, indicator',
    'macro_quant_indicators_long': 'date, indicator',
    'macro_quant_factors_daily': 'date, factor',
    'macro_quant_factors_monthly': 'date, factor',
}.items():
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date_key ON {table}({cols})')
conn.commit()

verify = []
for table in ['macro_quant_market_indicators_daily','macro_quant_indicators_long','macro_quant_factors_daily','macro_quant_factors_monthly','macro_quant_metadata']:
    cnt = cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    cols = [c[1] for c in cur.execute(f'PRAGMA table_info({table})')]
    dcol = 'date' if 'date' in cols else None
    rng = None
    if dcol and cnt:
        rng = cur.execute(f'SELECT MIN(date), MAX(date) FROM {table}').fetchone()
    verify.append({'table': table, 'rows': cnt, 'date_range': rng})
latest_daily = cur.execute('''
    SELECT factor, MAX(date) AS latest_date, ROUND(value, 4) AS value
    FROM macro_quant_factors_daily t
    WHERE date = (SELECT MAX(date) FROM macro_quant_factors_daily t2 WHERE t2.factor=t.factor)
    GROUP BY factor
    ORDER BY factor
''').fetchall()
latest_monthly = cur.execute('''
    SELECT factor, MAX(date) AS latest_date, ROUND(value, 4) AS value
    FROM macro_quant_factors_monthly t
    WHERE date = (SELECT MAX(date) FROM macro_quant_factors_monthly t2 WHERE t2.factor=t.factor)
    GROUP BY factor
    ORDER BY factor
''').fetchall()
conn.close()

summary = {
    'downloaded_at': downloaded_at,
    'database': str(DB_PATH),
    'backup': str(backup_path) if backup_path else None,
    'raw_dir': str(RAW_DIR),
    'verification': verify,
    'metadata_status': metadata[['series_id','indicator','status','rows','start_date','end_date','message']].to_dict('records') if not metadata.empty else [],
    'latest_daily_factors': latest_daily,
    'latest_monthly_factors': latest_monthly,
}
(RAW_DIR / 'quant_macro_collection_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
