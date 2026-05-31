import json
import datetime
import random

db_path = 'data/analyst_database.json'

with open(db_path, 'r', encoding='utf-8') as f:
    db = json.load(f)

# Shift all report dates to center around today (2026-05-31)
# Specifically, we want the generated 6 months to end at 2026-05-31.
# The original base date was 2025-06-20. The difference is 345 days.

for rep in db.get('reports', []):
    if rep['date']:
        try:
            d = datetime.datetime.strptime(rep['date'], "%Y-%m-%d")
            # If the date is in 2024 or 2025, shift it by 345 days
            if d.year in [2024, 2025]:
                new_d = d + datetime.timedelta(days=345)
                rep['date'] = new_d.strftime("%Y-%m-%d")
        except:
            pass

for rec in db.get('recommendations', []):
    if rec['date']:
        try:
            d = datetime.datetime.strptime(rec['date'], "%Y-%m-%d")
            if d.year in [2024, 2025]:
                new_d = d + datetime.timedelta(days=345)
                rec['date'] = new_d.strftime("%Y-%m-%d")
        except:
            pass

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print("Dates shifted to 2026.")
