import json
import os
import datetime
import urllib.request
import ast
import time
from utils import (
    load_db, load_stocks, load_calendar, logger,
    JS_PATH, CSV_PATH, MD_PATH, OUTPUTS_DIR
)

import random

def generate_js_bridge(db_data, market_data, calendar_data, ir_data_dict):
    """자바스크립트 브릿지 파일 갱신"""
    try:
        with open(JS_PATH, "w", encoding="utf-8") as f:
            f.write(f"window.ANALYST_DATABASE = {json.dumps(db_data, ensure_ascii=False, indent=2)};\n")
            f.write(f"window.MARKET_DATA = {json.dumps(market_data, ensure_ascii=False, indent=2)};\n")
            f.write(f"window.CALENDAR_DATA = {json.dumps(calendar_data, ensure_ascii=False, indent=2)};\n")
            f.write(f"window.IR_DATA = {json.dumps(ir_data_dict, ensure_ascii=False, indent=2)};\n")
        logger.info(f"  [JS 브릿지] {JS_PATH} 업데이트 완료")
        return True
    except Exception as e:
        logger.error(f"  [JS 브릿지] 업데이트 실패: {e}")
        return False

def generate_csv(db_data):
    """구글 시트 연동용 CSV 갱신"""
    try:
        lines = ["연도/시기,부문(섹터),애널리스트 이름,소속 증권사,평가 등급,핵심 투자 관점 및 시그니처 분석\n"]
        for a in db_data.get("analysts", []):
            evaluation_clean = a['evaluation'].replace(',', ' ').replace('\n', ' ').strip()
            line = f"2025 하반기,{a['merged_sector']},{a['name']},{a['firm']},{a['awards'].split(',')[0]},{evaluation_clean}\n"
            lines.append(line)
            
        with open(CSV_PATH, "w", encoding="utf-8-sig") as f:
            f.writelines(lines)
        logger.info(f"  [CSV] {CSV_PATH} 업데이트 완료")
    except Exception as e:
        logger.error(f"  [CSV] 업데이트 실패: {e}")

def compile_markdown(db_data):
    """마크다운 보고서 동적 생성"""
    analysts = db_data.get("analysts", [])
    recommendations = sorted(db_data.get("recommendations", []), key=lambda x: x["date"], reverse=True)
    
    alerts_content = ""
    for r in recommendations:
        badge = "🟢 상향 (Upgrade)" if r["change_type"] == "upgrade" else "🔴 하향 (Downgrade)"
        comment_clean = r["comment"].replace("\n", " ")
        analyst_info = next((f"{a['firm']} {a['name']} {a['position']}" for a in analysts if a['id'] == r['analyst_id']), '외부 기고가')
        alerts_content += f"""
### {badge} {r['stock_name']} ({r['stock_code']})
*   **담당 애널리스트**: {analyst_info}
*   **변경 내역**: `{r['previous_rating']}` $\\rightarrow$ **`{r['current_rating']}`** (목표가: {r['target_price']})
*   **의견 조정일**: {r['date']}
*   **리서치 코멘트**: *"{comment_clean}"*
---
"""
    if not alerts_content:
        alerts_content = "\n*현재 감지된 신규 투자의견 변경 알림이 없습니다.*\n"

    sectors_map = {}
    for a in analysts:
        sector = a["merged_sector"]
        sectors_map.setdefault(sector, []).append(a)

    sectors_content = ""
    for sector_name, member_list in sectors_map.items():
        sectors_content += f"\n## 📂 {sector_name} 부문\n"
        for a in member_list:
            targets_str = ", ".join(a["targets"])
            sectors_content += f"""
### 👤 {a['firm']} {a['name']} {a['position']}
> **"{a['awards']}"**
*   **시그니처 평가**: {a['evaluation']}
*   **핵심 커버 종목**: `{targets_str}`
"""
        sectors_content += "---\n"

    table_rows = ""
    for a in analysts:
        table_rows += f"| 2025 하반기 | {a['merged_sector']} | {a['name']} | {a['firm']} | {a['awards'].split(',')[0]} | {a['evaluation']} |\n"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    markdown_template = f"""# [대한민국 최정상급 베스트 애널리스트 핵심 데이터베이스]

> **"주식 시장의 1등 펀드매니저들이 가장 신뢰하는 브레인들의 투자 전략 분석 데이터베이스"**
> **최종 업데이트 일시**: `{now_str}`

---

## 📢 [실시간 알림] 핵심 투자의견 변동 추적 (Upgrade/Downgrade)

{alerts_content}

---

## 📁 5대 핵심 시너지 섹터별 최우수 애널리스트 상세 프로필

{sectors_content}

---

## 📊 구글 시트 연동 전체 마스터 테이블

| 연도/시기 | 부문 (결합 섹터) | 애널리스트 이름 | 소속 증권사 | 대표 평가 등급 | 핵심 투자 관점 및 시그니처 분석 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{table_rows}
---
"""
    return markdown_template

def fetch_market_data(db_data):
    """코스피 및 종목별 주가 데이터를 네이버 금융 API를 통해 수집"""
    ticker_map = load_stocks()
    unique_stocks = {"KOSPI"}
    for a in db_data.get("analysts", []):
        unique_stocks.update(a.get("targets", []))
    for rep in db_data.get("reports", []):
        unique_stocks.add(rep["stock_name"])

    today = datetime.datetime.now()
    start_time = (today - datetime.timedelta(days=365)).strftime("%Y%m%d")
    end_time = today.strftime("%Y%m%d")

    def fetch_naver_json(symbol):
        url = f"https://api.finance.naver.com/siseJson.naver?symbol={symbol}&requestType=1&startTime={start_time}&endTime={end_time}&timeframe=week"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as response:
                raw = response.read().decode('utf-8', errors='ignore')
                # 작은따옴표를 큰따옴표로 변환하여 표준 JSON 형식으로 변환
                clean = raw.strip().replace("'", '"').replace("\n", "").replace("\t", "").replace(",]", "]").replace(",,", ",")
                return json.loads(clean)[1:]
        except Exception as e:
            logger.error(f"  [데이터 패치] {symbol} 실패: {e}")
            return []

    def fetch_naver_ir_data(symbol):
        import re
        import ssl
        ssl_context = ssl._create_unverified_context()
        ir_list = []
        page = 1
        keep_fetching = True
        
        while keep_fetching and page <= 20: # 무한 루프 방지
            url = f"https://finance.naver.com/item/news_notice.naver?code={symbol}&page={page}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req, context=ssl_context) as response:
                    html = response.read().decode('euc-kr', errors='ignore')
                    pattern = re.compile(r'<td class="title">.*?<a[^>]*>(.*?)</a>.*?<td class="date">(.*?)</td>', re.IGNORECASE | re.DOTALL)
                    
                    matches = list(pattern.finditer(html))
                    if not matches:
                        break
                        
                    for match in matches:
                        title = match.group(1).strip()
                        date_str = match.group(2).strip()
                        clean_date = date_str.split()[0].replace('.', '-')
                        
                        if clean_date < '2025-06-01':
                            keep_fetching = False
                            continue
                            
                        if any(k in title for k in ['기업설명회', '실적', 'IR', '영업잠정실적', '안내', '매출']):
                            clean_title = re.sub(r'<[^>]+>', '', title).strip()
                            ir_list.append({"date": clean_date, "title": clean_title})
            except Exception as e:
                logger.error(f"  [에러] {symbol} IR 데이터 다운로드 실패: {e}")
                break
            
            page += 1
            time.sleep(0.1)
            
        return ir_list

    logger.info("  [데이터 패치] KOSPI 다운로드 중...")
    kospi_rows = fetch_naver_json("KOSPI")
    if not kospi_rows:
        return {"dates": [], "series": {}}

    dates = [f"{str(row[0])[:4]}-{str(row[0])[4:6]}-{str(row[0])[6:]}" for row in kospi_rows]
    series = {"KOSPI": [round(float(row[4]), 2) for row in kospi_rows]}
    series_ohlc = {"KOSPI": [{"o": round(float(row[1]), 2), "h": round(float(row[2]), 2), "l": round(float(row[3]), 2), "c": round(float(row[4]), 2)} for row in kospi_rows]}

    ir_data_dict = {}

    for stock in unique_stocks:
        if stock == "KOSPI": continue
        ticker = ticker_map.get(stock)
        if not ticker:
            series[stock] = [0] * len(dates)
            continue
            
        logger.info(f"  [데이터 패치] {stock} ({ticker}) 다운로드 중...")
        stock_rows = fetch_naver_json(ticker)
        
        if not stock_rows:
            series[stock] = [0] * len(dates)
            series_ohlc[stock] = [{"o": 0, "h": 0, "l": 0, "c": 0}] * len(dates)
        else:
            date_to_price = {f"{str(row[0])[:4]}-{str(row[0])[4:6]}-{str(row[0])[6:]}": float(row[4]) for row in stock_rows}
            date_to_ohlc = {f"{str(row[0])[:4]}-{str(row[0])[4:6]}-{str(row[0])[6:]}": {"o": float(row[1]), "h": float(row[2]), "l": float(row[3]), "c": float(row[4])} for row in stock_rows}
            prices = []
            ohlc_prices = []
            last_price = 0
            last_ohlc = {"o": 0, "h": 0, "l": 0, "c": 0}
            for d in dates:
                if d in date_to_price:
                    last_price = date_to_price[d]
                    last_ohlc = date_to_ohlc[d]
                prices.append(int(round(last_price, -2)))
                ohlc_prices.append({"o": int(round(last_ohlc["o"], -2)), "h": int(round(last_ohlc["h"], -2)), "l": int(round(last_ohlc["l"], -2)), "c": int(round(last_ohlc["c"], -2))})
            series[stock] = prices
            series_ohlc[stock] = ohlc_prices
        
        logger.info(f"  [IR 패치] {stock} ({ticker}) 공시 데이터 다운로드 중...")
        ir_rows = fetch_naver_ir_data(ticker)
        if ir_rows:
            ir_data_dict[stock] = ir_rows
            
        time.sleep(0.05)
        
    return {"dates": dates, "series": series, "series_ohlc": series_ohlc}, ir_data_dict

def main():
    logger.info("[Updater] 업데이트 프로세스 시작...")
    db_data = load_db()
    market_data, ir_data_dict = fetch_market_data(db_data)
    calendar_data = load_calendar()
    
    if generate_js_bridge(db_data, market_data, calendar_data, ir_data_dict):
        generate_csv(db_data)
        
        markdown_content = compile_markdown(db_data)
        with open(MD_PATH, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"  [마크다운] {MD_PATH} 업데이트 완료")
        
        # 백업 생성
        if os.path.exists(OUTPUTS_DIR):
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_path = os.path.join(OUTPUTS_DIR, f"{timestamp}_Anal_reports.md")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info(f"  [백업] {backup_path} 저장 완료")
            
    logger.info("[Updater] 모든 업데이트가 완료되었습니다.")

if __name__ == "__main__":
    main()
