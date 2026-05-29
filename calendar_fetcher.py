import urllib.request
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALENDAR_PATH = os.path.join(BASE_DIR, "economic_calendar.json")

def fetch_economic_calendar():
    # ForexFactory provides a public JSON feed for this week's events
    url = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"[Calendar] 네트워크 또는 파싱 에러: {e}")
        return []

    high_impact_events = []
    
    for event in data:
        # 3-star importance on investing.com is equivalent to 'High' impact here
        if event.get("impact") == "High":
            # date comes in format "2026-05-25T01:00:00-04:00"
            date_str = event.get("date", "")
            if date_str:
                # Extract just the YYYY-MM-DD part
                date_only = date_str.split('T')[0]
                
                # We also want to map the country (currency) to a more readable name if needed,
                # but "USD", "EUR", "KRW" is fine.
                
                high_impact_events.append({
                    "date": date_only,
                    "title": event.get("title", ""),
                    "country": event.get("country", ""),
                    "impact": "High"
                })
                
    # 2026년 5~7월 확정된 주요 글로벌 경제 지표 (미래 일정 표시용 하드코딩)
    fixed_future_events = [
        {"date": "2026-06-04", "title": "ECB Interest Rate Decision", "country": "EUR", "impact": "High"},
        {"date": "2026-06-05", "title": "US Non-Farm Payrolls", "country": "USD", "impact": "High"},
        {"date": "2026-06-10", "title": "US CPI m/m & y/y", "country": "USD", "impact": "High"},
        {"date": "2026-06-10", "title": "FOMC Statement & Fed Funds Rate", "country": "USD", "impact": "High"},
        {"date": "2026-06-18", "title": "BOE Official Bank Rate", "country": "GBP", "impact": "High"},
        {"date": "2026-06-25", "title": "US Final GDP q/q", "country": "USD", "impact": "High"},
        {"date": "2026-07-02", "title": "US Non-Farm Payrolls", "country": "USD", "impact": "High"},
        {"date": "2026-07-10", "title": "US CPI m/m & y/y", "country": "USD", "impact": "High"},
        {"date": "2026-07-29", "title": "FOMC Statement & Fed Funds Rate", "country": "USD", "impact": "High"}
    ]
    
    # 중복을 피하면서 고정 이벤트 병합
    existing_keys = set([f"{e['date']}_{e['title']}" for e in high_impact_events])
    for fixed in fixed_future_events:
        if f"{fixed['date']}_{fixed['title']}" not in existing_keys:
            high_impact_events.append(fixed)
            
    return high_impact_events

def main():
    print("[Calendar] 경제 캘린더 데이터 수집 시작...")
    events = fetch_economic_calendar()
    
    if not events:
        print("[Calendar] 금주 중요 경제 이벤트가 없거나 수집에 실패했습니다.")
        # 빈 파일이라도 생성해둡니다.
        with open(CALENDAR_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        return

    # 기존 캘린더 데이터와 병합 (중복 방지)
    existing_events = []
    if os.path.exists(CALENDAR_PATH):
        try:
            with open(CALENDAR_PATH, "r", encoding="utf-8") as f:
                existing_events = json.load(f)
        except:
            existing_events = []

    # 병합 로직 (고유 키: date + title)
    event_dict = { f"{e['date']}_{e['title']}": e for e in existing_events }
    
    new_count = 0
    for e in events:
        key = f"{e['date']}_{e['title']}"
        if key not in event_dict:
            event_dict[key] = e
            new_count += 1
            print(f"  [신규 이벤트] {e['date']} | {e['country']} - {e['title']}")
            
    # 날짜순 정렬
    merged_events = list(event_dict.values())
    merged_events.sort(key=lambda x: x['date'])
    
    with open(CALENDAR_PATH, "w", encoding="utf-8") as f:
        json.dump(merged_events, f, ensure_ascii=False, indent=2)
        
    print(f"[Calendar] 경제 캘린더 수집 완료. (총 {len(merged_events)}건, 신규 {new_count}건)")

if __name__ == "__main__":
    main()
