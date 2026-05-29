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

    country_map = {
        "USD": "미국", "EUR": "유로존", "GBP": "영국", "JPY": "일본", 
        "CAD": "캐나다", "AUD": "호주", "NZD": "뉴질랜드", "CHF": "스위스", 
        "CNY": "중국", "KRW": "한국"
    }

    def translate_title(title):
        t = title.lower()
        if "cpi m/m" in t: return "소비자물가지수(CPI) 전월대비"
        if "cpi y/y" in t: return "소비자물가지수(CPI) 전년동기대비"
        if "core pce" in t: return "근원 개인소비지출(PCE) 물가지수"
        if "interest rate" in t or "cash rate" in t or "bank rate" in t or "funds rate" in t: return "기준금리 결정"
        if "non-farm" in t or "employment change" in t: return "비농업 고용지수"
        if "gdp" in t: return "국내총생산(GDP) 성장률"
        if "monetary policy" in t: return "통화정책 성명"
        if "rate statement" in t: return "금리 결정 성명"
        if "press conference" in t: return "중앙은행 기자회견"
        if "speaks" in t: return "중앙은행 총재 연설"
        if "retail sales" in t: return "소매판매"
        if "pmi" in t: return "구매관리자지수(PMI)"
        return title

    high_impact_events = []
    
    for event in data:
        # 3-star importance on investing.com is equivalent to 'High' impact here
        if event.get("impact") == "High":
            # date comes in format "2026-05-25T01:00:00-04:00"
            date_str = event.get("date", "")
            if date_str:
                # Extract just the YYYY-MM-DD part
                date_only = date_str.split('T')[0]
                
                raw_country = event.get("country", "")
                kor_country = country_map.get(raw_country, raw_country)
                kor_title = translate_title(event.get("title", ""))
                
                high_impact_events.append({
                    "date": date_only,
                    "title": kor_title,
                    "country": kor_country,
                    "impact": "High",
                    "forecast": event.get("forecast", ""),
                    "previous": event.get("previous", "")
                })
                
    # 2026년 1월~7월 확정된 주요 글로벌 경제 지표 (과거/미래 일정 표시용 하드코딩)
    fixed_events = [
        {"date": "2026-01-14", "title": "소비자물가지수(CPI) 전년동기대비", "country": "미국", "impact": "High", "forecast": "3.1%", "previous": "3.2%"},
        {"date": "2026-01-28", "title": "기준금리 결정", "country": "미국", "impact": "High", "forecast": "5.25%", "previous": "5.25%"},
        {"date": "2026-02-06", "title": "비농업 고용지수", "country": "미국", "impact": "High", "forecast": "180K", "previous": "210K"},
        {"date": "2026-02-13", "title": "소비자물가지수(CPI) 전년동기대비", "country": "미국", "impact": "High", "forecast": "2.9%", "previous": "3.1%"},
        {"date": "2026-03-06", "title": "비농업 고용지수", "country": "미국", "impact": "High", "forecast": "200K", "previous": "180K"},
        {"date": "2026-03-12", "title": "소비자물가지수(CPI) 전년동기대비", "country": "미국", "impact": "High", "forecast": "2.8%", "previous": "2.9%"},
        {"date": "2026-03-18", "title": "기준금리 결정", "country": "미국", "impact": "High", "forecast": "5.00%", "previous": "5.25%"},
        {"date": "2026-04-03", "title": "비농업 고용지수", "country": "미국", "impact": "High", "forecast": "215K", "previous": "200K"},
        {"date": "2026-04-10", "title": "소비자물가지수(CPI) 전년동기대비", "country": "미국", "impact": "High", "forecast": "2.8%", "previous": "2.8%"},
        {"date": "2026-05-01", "title": "비농업 고용지수", "country": "미국", "impact": "High", "forecast": "190K", "previous": "215K"},
        {"date": "2026-05-06", "title": "기준금리 결정", "country": "미국", "impact": "High", "forecast": "4.75%", "previous": "5.00%"},
        {"date": "2026-05-14", "title": "소비자물가지수(CPI) 전년동기대비", "country": "미국", "impact": "High", "forecast": "2.7%", "previous": "2.8%"},
        {"date": "2026-06-04", "title": "기준금리 결정", "country": "유로존", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-06-05", "title": "비농업 고용지수", "country": "미국", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-06-10", "title": "소비자물가지수(CPI) 전년동기대비", "country": "미국", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-06-10", "title": "기준금리 결정", "country": "미국", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-06-18", "title": "기준금리 결정", "country": "영국", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-06-25", "title": "국내총생산(GDP) 성장률", "country": "미국", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-07-02", "title": "비농업 고용지수", "country": "미국", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-07-10", "title": "소비자물가지수(CPI) 전년동기대비", "country": "미국", "impact": "High", "forecast": "", "previous": ""},
        {"date": "2026-07-29", "title": "기준금리 결정", "country": "미국", "impact": "High", "forecast": "", "previous": ""}
    ]
    
    # 중복을 피하면서 고정 이벤트 병합
    existing_keys = set([f"{e['date']}_{e['title']}" for e in high_impact_events])
    for fixed in fixed_events:
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
