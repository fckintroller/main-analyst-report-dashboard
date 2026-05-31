import json
import random

db_path = 'data/analyst_database.json'

with open(db_path, 'r', encoding='utf-8') as f:
    db = json.load(f)

# 한국 시장의 현실적인 투자의견 비율: 매수 90%, 홀딩 9%, 매도 1%
for rep in db.get('reports', []):
    rand_val = random.random()
    if rand_val < 0.90:
        rep['rating'] = "매수 (Buy)"
    elif rand_val < 0.99:
        rep['rating'] = "홀딩 (Hold)"
    else:
        rep['rating'] = "매도 (Sell)"

# 추천 종목(recommendations) 쪽도 동일하게 수정 (최근 리포트 위주)
for rec in db.get('recommendations', []):
    rand_val = random.random()
    if rand_val < 0.90:
        rec['current_rating'] = "매수 (Buy)"
    elif rand_val < 0.99:
        rec['current_rating'] = "홀딩 (Hold)"
    else:
        rec['current_rating'] = "매도 (Sell)"

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print("Ratings fixed to realistic Korean market ratios (90% Buy, 9% Hold, 1% Sell).")
