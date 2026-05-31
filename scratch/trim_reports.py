import json

db_path = 'data/analyst_database.json'

with open(db_path, 'r', encoding='utf-8') as f:
    db = json.load(f)

# Group reports by stock and analyst
from collections import defaultdict
grouped = defaultdict(list)

for rep in db.get('reports', []):
    key = (rep['analyst_id'], rep['stock_name'])
    grouped[key].append(rep)

trimmed_reports = []
for key, reps in grouped.items():
    # Sort by date descending
    reps.sort(key=lambda x: x['date'], reverse=True)
    # Keep only the latest 3 reports
    trimmed_reports.extend(reps[:3])

# Sort all trimmed reports by date
trimmed_reports.sort(key=lambda x: x['date'], reverse=True)

db['reports'] = trimmed_reports

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"Trimmed reports. Total is now {len(trimmed_reports)}")
