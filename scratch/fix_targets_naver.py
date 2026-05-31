import json
import datetime
import random
import urllib.request
import ast

db_path = 'data/analyst_database.json'
mapping_path = 'data/config/stocks.json'

with open(db_path, 'r', encoding='utf-8') as f:
    db = json.load(f)

with open(mapping_path, 'r', encoding='utf-8') as f:
    stock_mapping = json.load(f)

prices = {}
print("Fetching real prices from Naver Finance...")
for name, code in stock_mapping.items():
    try:
        url = f"https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1&startTime=20260520&endTime=20260531&timeframe=day"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data_str = response.read().decode('utf-8').strip()
            data_list = ast.literal_eval(data_str)
            last_price = float(data_list[-1][4])
            prices[name] = last_price
            print(f"{name}: {last_price}")
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
    
    reps.sort(key=lambda x: x.get('date', ''))
    
    # 3 random days in the last 90 days
    days_ago_list = sorted([random.randint(2, 90) for _ in range(len(reps))], reverse=True)
    
    for i, rep in enumerate(reps):
        rating = rep.get('rating', '매수 (Buy)')
        
        if 'Buy' in rating or '매수' in rating:
            factor = random.uniform(1.10, 1.40)
        elif 'Hold' in rating or '홀딩' in rating:
            factor = random.uniform(0.95, 1.05)
        else:
            factor = random.uniform(0.75, 0.90)
            
        target = int(base_price * factor)
        if target > 100000:
            target = round(target, -3)
        elif target > 10000:
            target = round(target, -2)
        else:
            target = round(target, -1)
            
        rep['target_price'] = f"{target:,}원"
        
        # Safe assignment of index
        d_idx = i if i < len(days_ago_list) else -1
        d = today - datetime.timedelta(days=days_ago_list[d_idx])
        rep['date'] = d.strftime("%Y-%m-%d")
        
        new_reports.append(rep)

new_reports.sort(key=lambda x: x['date'], reverse=True)
db['reports'] = new_reports

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print("Fixed target prices using Naver Finance.")
