import urllib.request
from bs4 import BeautifulSoup
import json
import os
import re

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")
CONFIG_DIR = os.path.join(DATA_DIR, "config")
MAPPING_PATH = os.path.join(CONFIG_DIR, "stocks.json")
OUTPUT_PATH = os.path.join(DATA_DIR, "heatmap_database.json")

def load_json(path, default):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default

stock_mapping = load_json(MAPPING_PATH, {})
# 역매핑 (코드 -> 종목명)
code_to_name = {code: name for name, code in stock_mapping.items()}

# 섹터 매핑 (간소화)
def get_sector(stock_name):
    # 주요 반도체
    if stock_name in ["삼성전자", "SK하이닉스", "한미반도체", "이수페타시스"]:
        return "반도체 (Semiconductors)"
    if stock_name in ["네이버", "NAVER", "카카오", "크래프톤", "엔씨소프트"]:
        return "플랫폼 & 게임"
    if stock_name in ["현대차", "기아", "현대모비스"]:
        return "자동차 & 부품"
    if stock_name in ["LG에너지솔루션", "삼성SDI", "LG화학", "에코프로"]:
        return "2차전지"
    if stock_name in ["한화에어로스페이스", "LIG넥스원", "한국항공우주"]:
        return "방산"
    if stock_name in ["셀트리온", "삼성바이오로직스", "알테오젠"]:
        return "제약·바이오"
    if stock_name in ["KB금융", "신한지주", "하나금융지주", "메리츠금융지주"]:
        return "금융 & 지주사"
    return "기타"

def infer_rating(title):
    buy_keywords = ["매수", "상향", "Buy", "최선호", "탑픽", "성장", "호조", "서프라이즈", "기대", "개선"]
    sell_keywords = ["매도", "하향", "Sell", "보수적", "부진", "하회", "쇼크", "우려"]
    hold_keywords = ["유지", "Hold", "중립"]
    
    title_lower = title.lower()
    
    # Sell/Hold keywords usually are stronger indicators if present
    for kw in sell_keywords:
        if kw in title_lower:
            return "매도 (Sell)"
    for kw in hold_keywords:
        if kw in title_lower:
            return "홀딩 (Hold)"
    for kw in buy_keywords:
        if kw in title_lower:
            return "매수 (Buy)"
            
    return "투자의견 없음 (N/A)"

print("Starting web scrape from Naver Finance Research...")
all_reports = []
seen = set()

for page in range(1, 51):  # 50 pages = ~1500 reports
    url = f"https://finance.naver.com/research/company_list.naver?&page={page}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('euc-kr', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')
            
            table = soup.find('table', {'class': 'type_1'})
            if not table:
                continue
                
            rows = table.find_all('tr')
            for row in rows[2:]:
                cols = row.find_all('td')
                if len(cols) >= 5:
                    stock = cols[0].text.strip()
                    title = cols[1].text.strip()
                    firm = cols[2].text.strip()
                    date_str = cols[4].text.strip() # yy.mm.dd
                    
                    if not stock or not title:
                        continue
                        
                    # 26.05.29 -> 2026-05-29
                    parts = date_str.split('.')
                    if len(parts) == 3:
                        date = f"20{parts[0]}-{parts[1]}-{parts[2]}"
                    else:
                        date = date_str
                        
                    uid = f"{stock}_{date}_{firm}"
                    if uid in seen:
                        continue
                    seen.add(uid)
                    
                    rating = infer_rating(title)
                    sector = get_sector(stock)
                    
                    all_reports.append({
                        "stock_name": stock,
                        "date": date,
                        "rating": rating,
                        "merged_sector": sector
                    })
    except Exception as e:
        print(f"Error on page {page}:", e)
        
    if page % 10 == 0:
        print(f"Scraped page {page}/50. Total reports: {len(all_reports)}")

# Save JSON
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump({"heatmap_reports": all_reports}, f, ensure_ascii=False, indent=2)

print(f"Scraping completed. Extracted {len(all_reports)} reports. Saved to {OUTPUT_PATH}")
