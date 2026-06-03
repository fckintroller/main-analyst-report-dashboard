import os
import glob
import pandas as pd
import json
import logging

# 濡쒓굅 ?ㅼ젙
logger = logging.getLogger(__name__)

def export_to_web():
    logger.info("=== ????쒕낫???곕룞??JSON/JS ?뚯씪 ?앹꽦 ?쒖옉 ===")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_data_dir = os.path.abspath(os.path.join(base_dir, '..', '..', 'data', 'raw'))
    web_dir = os.path.abspath(os.path.join(base_dir, '..', '..', 'web'))

    if not os.path.exists(web_dir):
        os.makedirs(web_dir)

    quant_data = {
        'macro': {},
        'money_flow': {},
        'sentiment': {},
        'valuation': {}
    }

    # 1. Macro Data 異붿텧
    macro_files = glob.glob(os.path.join(raw_data_dir, 'macro', '**', '*.csv'), recursive=True)
    for file in macro_files:
        name = os.path.splitext(os.path.basename(file))[0]
        try:
            df = pd.read_csv(file)
            df.fillna('', inplace=True)
            quant_data['macro'][name] = df.to_dict(orient='records')
        except Exception as e:
            logger.warning(f"Error reading {file}: {e}")

    # 2. Money Flow Data 異붿텧
    money_files = glob.glob(os.path.join(raw_data_dir, 'money_flow', '*.csv'))
    for file in money_files:
        name = os.path.splitext(os.path.basename(file))[0]
        try:
            df = pd.read_csv(file)
            df.fillna('', inplace=True)
            quant_data['money_flow'][name] = df.to_dict(orient='records')
        except Exception as e:
            logger.warning(f"Error reading {file}: {e}")

    # 3. Valuation (DART / EPS) Data 異붿텧
    sentiment_json = os.path.join(raw_data_dir, 'sentiment', 'fear_greed.json')
    if os.path.exists(sentiment_json):
        try:
            with open(sentiment_json, 'r', encoding='utf-8') as f:
                quant_data['sentiment']['fear_greed'] = json.load(f)
        except Exception as e:
            logger.warning(f"Error reading {sentiment_json}: {e}")

    import FinanceDataReader as fdr
    try:
        krx = fdr.StockListing('KRX')[['Code', 'Name']].set_index('Code')
        krx_dict = krx['Name'].to_dict()
    except:
        krx_dict = {}

    val_files = glob.glob(os.path.join(raw_data_dir, 'valuation', '*.csv'))
    for file in val_files:
        name = os.path.splitext(os.path.basename(file))[0]
        try:
            # Ticker columns should be string
            df = pd.read_csv(file, dtype={'ticker': str, 'Code': str})
            df.fillna('', inplace=True)
            records = df.to_dict(orient='records')

            if name == 'earnings_consensus':
                for r in records:
                    t = str(r.get('ticker', '')).zfill(6)
                    r['ticker'] = t
                    r['corp_name'] = krx_dict.get(t, t)

            quant_data['valuation'][name] = records
        except Exception as e:
            logger.warning(f"Error reading {file}: {e}")

    # JS 蹂?섎줈 ?ㅽ봽
    js_content = "window.QUANT_DATA = " + json.dumps(quant_data, ensure_ascii=False) + ";"

    output_path = os.path.join(web_dir, 'quant_data.js')
    with open(output_path, 'w', encoding='utf-8-sig') as f:
        f.write(js_content)

    logger.info(f" - JS ?뚯씪 ?대낫?닿린 ?꾨즺: {output_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    export_to_web()
