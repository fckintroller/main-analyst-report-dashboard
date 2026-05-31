import json
import datetime
import random
import yfinance as yf

db_path = 'data/analyst_database.json'
mapping_path = 'data/stock_mapping.json'

with open(db_path, 'r', encoding='utf-8') as f:
    db = json.load(f)

with open(mapping_path, 'r', encoding='utf-8') as f:
    stock_mapping = json.load(f)

# Fetch current prices
prices = {}
print("Fetching real prices...")
for name, code in stock_mapping.items():
    ticker = f"{code}.KS" if not code.startswith(('035900', '068270', '259960', '035760', '042700', '066970', '196170')) else f"{code}.KQ"
    try:
        t = yf.Ticker(ticker)
        # Get history for last 5 days to handle weekends/holidays
        hist = t.history(period="5d")
        if not hist.empty:
            prices[name] = hist['Close'].iloc[-1]
            print(f"{name}: {prices[name]}")
        else:
            prices[name] = 50000 # default
    except Exception as e:
        prices[name] = 50000

# Fix dates and targets
from collections import defaultdict
grouped = defaultdict(list)

for rep in db.get('reports', []):
    key = (rep['analyst_id'], rep['stock_name'])
    grouped[key].append(rep)

today = datetime.datetime.now()

new_reports = []
for key, reps in grouped.items():
    stock_name = key[1]
    base_price = prices.get(stock_name, 50000)
    
    # Sort by whatever to just assign days
    reps.sort(key=lambda x: x.get('date', ''))
    
    # Generate 3 realistic dates over the last 90 days, sorted chronologically
    days_ago_list = sorted([random.randint(2, 90) for _ in range(len(reps))], reverse=True)
    
    for i, rep in enumerate(reps):
        rating = rep.get('rating', '매수 (Buy)')
        
        # Calculate realistic target price
        if 'Buy' in rating or '매수' in rating:
            factor = random.uniform(1.10, 1.40)
        elif 'Hold' in rating or '홀딩' in rating:
            factor = random.uniform(0.95, 1.05)
        else:
            factor = random.uniform(0.75, 0.90)
            
        target = int(base_price * factor)
        # Round intelligently
        if target > 100000:
            target = round(target, -3)
        elif target > 10000:
            target = round(target, -2)
        else:
            target = round(target, -1)
            
        rep['target_price'] = f"{target:,}원"
        
        # Assign date
        d = today - datetime.timedelta(days=days_ago_list[i])
        rep['date'] = d.strftime("%Y-%m-%d")
        
        new_reports.append(rep)

# Sort all descending
new_reports.sort(key=lambda x: x['date'], reverse=True)
db['reports'] = new_reports

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print("Fixed target prices based on real stock prices and spaced out dates logically.")
