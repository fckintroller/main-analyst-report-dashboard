import urllib.request
import json
import os
from datetime import datetime
from utils import load_calendar, save_calendar, load_json, logger, FIXED_EVENTS_PATH

def fetch_economic_calendar():
    # ForexFactory provides a public JSON feed for this week's events
    url = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        logger.error(f"[Calendar] 네트워크 또는 파싱 에러: {e}")
        return []

    country_map = {
        "USD": "미국", "EUR": "유로존", "GBP": "영국", "JPY": "일본", 
        "CAD": "캐나다", "AUD": "호주", "NZD": "뉴질랜드", "CHF": "스위스", 
        "CNY": "중국", "KRW": "한국"
    }

    def translate_title(title):
        t = title.lower()
        
        # 지표 매핑 딕셔너리
        mapping = {
            "cpi": "소비자물가지수",
            "inflation": "소비자물가지수",
            "core pce": "근원 개인소비지출 물가지수",
            "pce": "개인소비지출 물가지수",
            "ppi": "생산자물가지수",
            "unemployment claims": "신규 실업수당 청구건수",
            "jobless claims": "신규 실업수당 청구건수",
            "unemployment rate": "실업률",
            "non-farm": "비농업 고용지수",
            "nonfarm": "비농업 고용지수",
            "adp": "ADP 민간고용",
            "employment change": "고용 변동",
            "jolts": "JOLTs 구인구직",
            "job openings": "JOLTs 구인구직",
            "private payrolls": "민간 고용지수",
            "payroll": "고용지수",
            "interest rate": "기준금리 결정",
            "cash rate": "기준금리 결정",
            "bank rate": "기준금리 결정",
            "funds rate": "기준금리 결정",
            "monetary policy": "통화정책 성명",
            "rate statement": "금리 결정 성명",
            "press conference": "중앙은행 기자회견",
            "speaks": "중앙은행 총재 연설",
            "gdp": "국내총생산(GDP)",
            "retail sales": "소매판매",
            "pmi": "구매관리자지수(PMI)"
        }

        # 특수 매핑 (BOJ 등)
        if "boj" in t:
            if "rate" in t: return "일본은행(BOJ) 기준금리 결정"
            if "policy" in t or "statement" in t: return "일본은행(BOJ) 통화정책 성명"
            if "press" in t: return "일본은행(BOJ) 기자회견"
            if "core cpi" in t: return "일본은행(BOJ) 근원 소비자물가지수"
            return "일본은행(BOJ) 이벤트"

        # 일반 매핑 검색
        for key, val in mapping.items():
            if key in t:
                res = val
                if "m/m" in t: res += " 전월대비"
                elif "y/y" in t: res += " 전년동기대비"
                elif "q/q" in t: res += " 전분기대비"
                
                if "manufacturing" in t: res = "제조업 " + res
                elif "services" in t: res = "서비스업 " + res
                return res

        # Fallback 변환
        t = t.replace("french", "프랑스").replace("german", "독일").replace("spanish", "스페인").replace("italian", "이탈리아")
        t = t.replace("final", "확정치").replace("prelim", "예비치").replace("flash", "속보치")
        t = t.replace("m/m", "전월대비").replace("y/y", "전년동기대비").replace("q/q", "전분기대비")
        
        return title.replace("(CPI)", "").replace("(PPI)", "").strip()

    high_impact_events = []
    
    for event in data:
        t = event.get("title", "").lower()
        is_high_impact = event.get("impact") == "High"
        is_inflation = any(k in t for k in ["cpi", "ppi", "pce", "inflation"])
        is_employment = any(k in t for k in ["employment", "jobless", "unemployment", "payroll", "jolts", "adp"])
        is_policy = any(k in t for k in ["rate", "policy", "boj", "fomc", "ecb", "statement", "press conference"])
        
        if is_high_impact or is_inflation or is_employment or is_policy:
            date_str = event.get("date", "")
            if date_str:
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
                
    # 외부 파일에서 고정 이벤트 로드
    fixed_events = load_json(FIXED_EVENTS_PATH, [])
    
    # 중복을 피하면서 고정 이벤트 병합
    existing_keys = set([f"{e['date']}_{e['title']}" for e in high_impact_events])
    for fixed in fixed_events:
        if f"{fixed['date']}_{fixed['title']}" not in existing_keys:
            high_impact_events.append(fixed)
            
    return high_impact_events

def main():
    logger.info("[Calendar] 경제 캘린더 데이터 수집 시작...")
    events = fetch_economic_calendar()
    
    if not events:
        logger.warning("[Calendar] 금주 중요 경제 이벤트가 없거나 수집에 실패했습니다.")
        return

    existing_events = load_calendar()
    event_dict = { f"{e['date']}_{e['title']}": e for e in existing_events }
    
    new_count = 0
    for e in events:
        key = f"{e['date']}_{e['title']}"
        if key not in event_dict:
            event_dict[key] = e
            new_count += 1
            logger.info(f"  [신규 이벤트] {e['date']} | {e['country']} - {e['title']}")
            
    # 날짜순 정렬
    merged_events = list(event_dict.values())
    merged_events.sort(key=lambda x: x['date'])
    
    if save_calendar(merged_events):
        logger.info(f"[Calendar] 경제 캘린더 수집 완료. (총 {len(merged_events)}건, 신규 {new_count}건)")

if __name__ == "__main__":
    main()
