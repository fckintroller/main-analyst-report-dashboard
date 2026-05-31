import json
import random
import datetime

db_path = 'data/analyst_database.json'

with open(db_path, 'r', encoding='utf-8') as f:
    db = json.load(f)

analysts = db.get('analysts', [])
reports = db.get('reports', [])

# Generate fake reports
titles = [
    "실적 턴어라운드 본격화 기대", "하반기 어닝 서프라이즈 전망", 
    "신사업 모멘텀 부각", "마진율 개선세 뚜렷", 
    "밸류에이션 매력도 상승", "안정적인 캐시카우 역할 지속",
    "매크로 불확실성 속 방어주 매력", "경쟁 심화 우려 선반영",
    "CAPEX 투자 확대로 인한 외형 성장", "단기 악재 소멸 구간 진입",
    "저가 매수 유효 구간", "목표가 상향 리포트",
    "시장 컨센서스 상회", "글로벌 점유율 확대",
    "혁신 기술 도입에 따른 프리미엄"
]

ratings = ["매수 (Buy)", "매수 (Buy)", "매수 (Buy)", "홀딩 (Hold)", "홀딩 (Hold)", "매도 (Sell)"]

base_date = datetime.date(2025, 6, 20) # Current point in mock dashboard
new_reports = []
r_id = 2000

for analyst in analysts:
    for target in analyst.get('targets', []):
        # Generate 15 to 25 reports per stock per analyst
        num_reports = random.randint(15, 25)
        for _ in range(num_reports):
            days_ago = random.randint(0, 180) # Last 6 months
            r_date = base_date - datetime.timedelta(days=days_ago)
            
            rating = random.choice(ratings)
            base_price = random.randint(5, 500) * 1000
            if rating == "매수 (Buy)":
                target_price = int(base_price * random.uniform(1.1, 1.5))
            elif rating == "홀딩 (Hold)":
                target_price = int(base_price * random.uniform(0.9, 1.1))
            else:
                target_price = int(base_price * random.uniform(0.7, 0.9))
                
            # Round to nearest 100
            target_price = round(target_price, -2)
            
            new_reports.append({
                "id": f"r{r_id}",
                "analyst_id": analyst['id'],
                "stock_name": target,
                "title": f"{target}, {random.choice(titles)}",
                "rating": rating,
                "target_price": f"{target_price:,}원",
                "date": r_date.strftime("%Y-%m-%d")
            })
            r_id += 1

db['reports'].extend(new_reports)
# Sort by date
db['reports'].sort(key=lambda x: x['date'], reverse=True)

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"Added {len(new_reports)} new reports. Total reports: {len(db['reports'])}")
