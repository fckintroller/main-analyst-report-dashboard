import urllib.request
import re
import json
import os
import datetime
from utils import load_db, save_db, logger

def fetch_recent_reports():
    url = 'https://finance.naver.com/research/company_list.naver'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read().decode('euc-kr', errors='ignore')
    except Exception as e:
        logger.error(f"[Crawler] 네트워크 에러: {e}")
        return []

    # <tbody> 부분만 추출
    try:
        table_html = html.split('type_1')[1].split('</table>')[0]
    except IndexError:
        logger.error("[Crawler] HTML 파싱 에러")
        return []

    # 정규식 패턴 (종목명, 링크, 제목, 증권사, 작성일)
    pattern = re.compile(
        r'<td style="padding-left:10">.*?title="([^"]+)".*?</td>.*?<td>\s*<a href="company_read.naver\?nid=([^&]+).*?>(.*?)</a>.*?</td>.*?<td[^>]*>(.*?)</td>.*?<td class="date"[^>]*>(.*?)</td>',
        re.DOTALL
    )

    reports = []
    for match in pattern.finditer(table_html):
        stock_name = match.group(1).strip()
        report_id = match.group(2).strip()
        title_raw = match.group(3)
        # HTML 태그 제거
        title = re.sub(r'<[^>]+>', '', title_raw).strip()
        firm = match.group(4).strip()
        date_raw = match.group(5).strip()
        
        # 26.05.29 -> 2026-05-29
        parts = date_raw.split('.')
        if len(parts) == 3:
            date = f"20{parts[0]}-{parts[1]}-{parts[2]}"
        else:
            date = date_raw

        reports.append({
            "report_id": report_id,
            "stock_name": stock_name,
            "title": title,
            "firm": firm,
            "date": date
        })
    return reports

def main():
    logger.info("[Crawler] 네이버 금융 리서치 최신 보고서 크롤링 시작...")
    new_reports = fetch_recent_reports()
    
    if not new_reports:
        logger.warning("[Crawler] 추출된 리포트가 없습니다.")
        return

    db = load_db()
    existing_reports = db.setdefault("reports", [])
    # 중복 체크를 위한 복합 키 생성 (날짜_종목명_제목)
    existing_keys = {f"{r.get('date')}_{r.get('stock_name')}_{r.get('title')}" for r in existing_reports}
    
    # DB에 등록된 애널리스트 및 관심 종목 맵
    valid_stocks = set()
    firm_analyst_map = {} # firm -> list of analyst_ids
    for a in db.get("analysts", []):
        valid_stocks.update(a.get("targets", []))
        firm = a.get("firm")
        if firm not in firm_analyst_map:
            firm_analyst_map[firm] = []
        firm_analyst_map[firm].append(a.get("id"))

    added_count = 0
    for r in new_reports:
        # 복합 키 기반 중복 체크
        report_key = f"{r['date']}_{r['stock_name']}_{r['title']}"
        if report_key in existing_keys:
            continue
            
        # 관심 종목(DB에 등록된)만 필터링할지 여부: 일단 모두 넣지 않고, DB 타겟 종목 위주로 필터링
        if r["stock_name"] not in valid_stocks:
            continue
            
        # 해당 증권사의 애널리스트 찾기 (정확한 애널리스트 이름이 안나오므로 임의 매핑 혹은 첫번째 배정)
        analyst_id = "external_analyst"
        if r["firm"] in firm_analyst_map and len(firm_analyst_map[r["firm"]]) > 0:
            analyst_id = firm_analyst_map[r["firm"]][0]
            
        new_entry = {
            "analyst_id": analyst_id,
            "stock_name": r["stock_name"],
            "stock_code": "000000", # 임시
            "title": r["title"],
            "summary": "네이버 금융에서 자동 수집된 최신 리포트입니다.",
            "date": r["date"],
            "rating": "매수", # 기본값
            "target_price": "미정"
        }
        
        # 제목에서 목표가 및 투자의견 추론 시도
        if "유지" in r["title"] or "Hold" in r["title"]:
            new_entry["rating"] = "홀딩"
        elif "하향" in r["title"] or "Sell" in r["title"]:
            new_entry["rating"] = "매도"
            
        # 간단한 숫자 추출
        prices = re.findall(r'(\d+,\d+|\d+)원', r["title"])
        if prices:
            new_entry["target_price"] = prices[-1] + "원"
            
        # --- 외부 기고가 및 목표가 미정 리포트 필터링 ---
        if new_entry["analyst_id"] == "external_analyst" or new_entry["target_price"] in ("미정", "N/A", "", "0"):
            continue
            
        existing_reports.append(new_entry)
        added_count += 1
        logger.info(f"  [수집] {r['stock_name']} - {r['title']}")

    if added_count > 0:
        save_db(db)
        logger.info(f"[Crawler] 성공적으로 {added_count}개의 새로운 리포트를 데이터베이스에 추가했습니다.")
    else:
        logger.info("[Crawler] 업데이트할 새로운 리포트가 없습니다.")

if __name__ == "__main__":
    main()
