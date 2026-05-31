import json
import datetime
import random

db_path = 'data/analyst_database.json'
today = datetime.datetime.now()

with open(db_path, 'r', encoding='utf-8') as f:
    db = json.load(f)

def fix_future_date(date_str):
    if not date_str:
        return date_str
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        if d > today:
            # If the date is in the future, randomly assign a date in the last 30 days
            days_ago = random.randint(0, 30)
            new_d = today - datetime.timedelta(days=days_ago)
            return new_d.strftime("%Y-%m-%d")
    except:
        pass
    return date_str

for rep in db.get('reports', []):
    rep['date'] = fix_future_date(rep['date'])

for rec in db.get('recommendations', []):
    rec['date'] = fix_future_date(rec['date'])
    
# Sort reports by date again
db['reports'].sort(key=lambda x: x['date'], reverse=True)

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print("Fixed future dates.")
